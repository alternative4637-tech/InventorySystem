import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
import os
from pathlib import Path
from decimal import Decimal, InvalidOperation
import re
import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))


DATABASE_NAME = "inventory_system"
LOCAL_MYSQL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ROLE_NAMES = {"Super Admin", "Admin", "Staff"}
PRODUCT_MANAGER_ROLES = {"Super Admin", "Admin"}
MAX_PRODUCT_QUANTITY = 2147483647
MAX_PRODUCT_ID = 2147483647

CREAM = "#F8F1E7"
BROWN = "#70452B"
BROWN_HOVER = "#8C5A3C"


def filter_inventory_products(products, search_text):
    """Return loaded products matching an ID or name, without a database query."""
    search_term = search_text.strip().casefold()
    if not search_term:
        return list(products)

    return [
        product
        for product in products
        if search_term in str(product[0])
        or search_term in str(product[1]).casefold()
    ]

# Role permissions for Admin and Staff remain explicit below. Super Admin has
# full access to every feature in this map.
FEATURES = {
    "inventory": {
        "title": "Inventory",
        "roles": ROLE_NAMES,
        "status": "Read-only product inventory.",
    },
    "product_management": {
        "title": "Product Management",
        "roles": PRODUCT_MANAGER_ROLES,
        "status": "Add, edit, and adjust stock. Product deletion is disabled.",
    },
    "sales": {
        "title": "Sales",
        "roles": {"Admin", "Staff"},
        "status": "Sales screens are not implemented yet.",
    },
    "product_search": {
        "title": "Product Search",
        "roles": set(),
        "status": "Role access is waiting for group confirmation.",
    },
    "sales_history": {
        "title": "Sales History",
        "roles": set(),
        "status": "Role access is waiting for group confirmation.",
    },
    "reports": {
        "title": "Reports",
        "roles": {"Admin"},
        "status": "Report screens are not implemented yet.",
    },
}


class DatabaseConfigurationError(Exception):
    """A safe, user-facing database configuration or connection problem."""

# -----------------------------
# DATABASE CONNECTION
# -----------------------------

def connect_to_database():
    """Connect only to the configured local inventory_system database."""
    settings = {
        "host": os.getenv("MYSQL_HOST", "").strip(),
        "port": os.getenv("MYSQL_PORT", "").strip(),
        "user": os.getenv("MYSQL_USER", "").strip(),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "").strip(),
    }

    missing = [
        f"MYSQL_{name.upper()}"
        for name, value in settings.items()
        if not value
    ]
    if missing:
        raise DatabaseConfigurationError(
            "Database settings are missing from .env: " + ", ".join(missing)
        )

    if settings["host"].lower() not in LOCAL_MYSQL_HOSTS:
        raise DatabaseConfigurationError(
            "MYSQL_HOST must be localhost, 127.0.0.1, or ::1."
        )

    if settings["database"] != DATABASE_NAME:
        raise DatabaseConfigurationError(
            "MYSQL_DATABASE must be set to inventory_system."
        )

    try:
        settings["port"] = int(settings["port"])
    except ValueError:
        raise DatabaseConfigurationError("MYSQL_PORT must be a number.") from None

    if not 1 <= settings["port"] <= 65535:
        raise DatabaseConfigurationError("MYSQL_PORT must be between 1 and 65535.")

    try:
        connection = mysql.connector.connect(**settings)
    except mysql.connector.Error:
        # Connector errors can include connection details, so keep the message generic.
        raise DatabaseConfigurationError(
            "Could not connect to the local MySQL server for inventory_system. "
            "Check the .env settings and make sure MySQL Server is running."
        ) from None

    if connection.database != DATABASE_NAME:
        connection.close()
        raise DatabaseConfigurationError(
            "The connection did not select inventory_system."
        )

    return connection


# -----------------------------
# REGISTER USER
# -----------------------------

def register_user(username, password, role):
    if not username.strip() or not password:
        return False, "Username and password are required."

    # The initial Super Admin is created only by setup_super_admin.py.
    # Normal account creation must never assign this privileged role.
    if role == "Super Admin":
        return False, "Super Admin accounts can only be created during initial setup."

    if role not in ("Admin", "Staff"):
        return False, "Invalid user role."

    try:
        connection = connect_to_database()
    except DatabaseConfigurationError as error:
        return False, str(error)

    cursor = None

    try:
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        cursor = connection.cursor()

        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
            """,
            (username.strip(), password_hash, role)
        )

        connection.commit()
        return True, "Account saved successfully."

    except mysql.connector.IntegrityError:
        connection.rollback()
        return False, "That username already exists."

    except mysql.connector.Error:
        connection.rollback()
        return False, "Could not save the account."

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


def create_account_for_actor(actor_role, username, password, confirmation, role):
    """Authorize and validate dashboard account creation before registration."""
    if actor_role != "Super Admin":
        return False, "Only the Super Admin can create accounts."

    username = username.strip()
    if not username or not password or not confirmation:
        return False, "Please complete all fields."
    if len(username) > 50:
        return False, "Username must be 50 characters or fewer."
    if password != confirmation:
        return False, "The passwords do not match."
    if role not in ("Admin", "Staff"):
        return False, "Choose Admin or Staff for the new account."

    return register_user(username, password, role)


# -----------------------------
# PRODUCT VALIDATION AND WRITES
# -----------------------------

def _can_manage_products(role):
    """Return whether an authenticated role may change product records."""
    return role in PRODUCT_MANAGER_ROLES


def _validate_product_name(product_name):
    if not isinstance(product_name, str):
        return None, "Product name is required."
    name = product_name.strip()
    if not name:
        return None, "Product name is required."
    if len(name) > 100:
        return None, "Product name must be 100 characters or fewer."
    return name, None


def _validate_quantity(quantity_value):
    text = str(quantity_value).strip()
    if not re.fullmatch(r"[0-9]+", text):
        return None, "Quantity must be a whole number of zero or more."
    try:
        quantity = int(text)
    except ValueError:
        return None, "Enter a valid whole-number quantity."
    if quantity > MAX_PRODUCT_QUANTITY:
        return None, "Quantity exceeds the maximum supported amount."
    return quantity, None


def _validate_price(price_value):
    text = str(price_value).strip()
    if not re.fullmatch(r"(?:[0-9]+(?:\.[0-9]{1,2})?|\.[0-9]{1,2})", text):
        return None, "Price must be a nonnegative amount with up to two decimal places."
    try:
        price = Decimal(text)
    except InvalidOperation:
        return None, "Enter a valid price."

    if not price.is_finite() or price < 0:
        return None, "Price cannot be negative."
    if price > Decimal("99999999.99"):
        return None, "Price exceeds the maximum supported amount."
    return price.quantize(Decimal("0.01")), None


def _validate_product_id(product_id_value):
    text = str(product_id_value).strip()
    if not re.fullmatch(r"[0-9]+", text):
        return None, "Select a valid product."
    try:
        product_id = int(text)
    except ValueError:
        return None, "Select a valid product."
    if not 1 <= product_id <= MAX_PRODUCT_ID:
        return None, "Select a valid product."
    return product_id, None


def stock_status(quantity):
    """Return the flowchart's stock label for a validated quantity."""
    quantity = int(quantity)
    if quantity == 0:
        return "Out of Stock"
    if quantity <= 5:
        return "Low Stock"
    return "In Stock"


def delete_product(role, product_id_value):
    """Delete only the selected product; preserve FK-referenced history."""
    if role != "Admin":
        return False, "Only Admin can delete products."
    product_id, error = _validate_product_id(product_id_value)
    if error:
        return False, error
    connection = None
    cursor = None
    try:
        connection = connect_to_database()
        cursor = connection.cursor()
        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        if cursor.rowcount == 0:
            connection.rollback()
            return False, "That product could not be found. Refresh the table and try again."
        connection.commit()
        return True, "Product deleted successfully."
    except DatabaseConfigurationError as error:
        _rollback_product_change(connection)
        return False, str(error)
    except mysql.connector.IntegrityError:
        _rollback_product_change(connection)
        return False, "This product is referenced by request or audit records and cannot be deleted. Those records were preserved."
    except mysql.connector.Error:
        _rollback_product_change(connection)
        return False, "The product could not be deleted. No related records were removed."
    finally:
        _close_product_resources(cursor, connection)


def _rollback_product_change(connection):
    if connection is None:
        return
    try:
        connection.rollback()
    except mysql.connector.Error:
        pass


def _close_product_resources(cursor, connection):
    if cursor is not None:
        try:
            cursor.close()
        except mysql.connector.Error:
            pass
    if connection is not None:
        try:
            connection.close()
        except mysql.connector.Error:
            pass


def _execute_product_write(role, query, parameters, success_message, product_id=None):
    """Run one authorized product write with commit, rollback, and cleanup."""
    if not _can_manage_products(role):
        return False, "Only Admin and Super Admin can manage products."

    connection = None
    cursor = None
    try:
        connection = connect_to_database()
        cursor = connection.cursor()
        cursor.execute(query, parameters)

        if product_id is not None and cursor.rowcount == 0:
            # An UPDATE of unchanged values may report rowcount zero. Check
            # whether the selected product still exists before reporting.
            cursor.execute(
                "SELECT product_id FROM products WHERE product_id = %s",
                (product_id,),
            )
            if cursor.fetchone() is None:
                connection.rollback()
                return False, "That product could not be found. Refresh the table and try again."

        connection.commit()
        return True, success_message
    except DatabaseConfigurationError as error:
        _rollback_product_change(connection)
        return False, str(error)
    except mysql.connector.Error:
        _rollback_product_change(connection)
        return False, "The product could not be saved. Check the database connection and try again."
    finally:
        _close_product_resources(cursor, connection)


def add_product(role, product_name, quantity_value, price_value):
    """Add a product after checking authorization and every input field."""
    if not _can_manage_products(role):
        return False, "Only Admin and Super Admin can manage products."

    name, error = _validate_product_name(product_name)
    if error:
        return False, error
    quantity, error = _validate_quantity(quantity_value)
    if error:
        return False, error
    price, error = _validate_price(price_value)
    if error:
        return False, error

    return _execute_product_write(
        role,
        "INSERT INTO products (product_name, quantity, price) VALUES (%s, %s, %s)",
        (name, quantity, price),
        "Product added successfully.",
    )


def edit_product(role, product_id_value, product_name, quantity_value, price_value):
    """Edit the name, quantity, and price of an existing product."""
    if not _can_manage_products(role):
        return False, "Only Admin and Super Admin can manage products."

    product_id, error = _validate_product_id(product_id_value)
    if error:
        return False, error
    name, error = _validate_product_name(product_name)
    if error:
        return False, error
    quantity, error = _validate_quantity(quantity_value)
    if error:
        return False, error
    price, error = _validate_price(price_value)
    if error:
        return False, error

    return _execute_product_write(
        role,
        "UPDATE products SET product_name = %s, quantity = %s, price = %s WHERE product_id = %s",
        (name, quantity, price, product_id),
        "Product updated successfully.",
        product_id,
    )


def set_product_stock(role, product_id_value, new_quantity_value):
    """Set stock to a new total quantity rather than applying a delta."""
    if not _can_manage_products(role):
        return False, "Only Admin and Super Admin can manage products."

    product_id, error = _validate_product_id(product_id_value)
    if error:
        return False, error
    new_quantity, error = _validate_quantity(new_quantity_value)
    if error:
        return False, error

    return _execute_product_write(
        role,
        "UPDATE products SET quantity = %s WHERE product_id = %s",
        (new_quantity, product_id),
        "Stock quantity updated successfully.",
        product_id,
    )


# -----------------------------
# CHECK LOGIN DETAILS
# -----------------------------

def authenticate_user(username, password):
    try:
        connection = connect_to_database()
    except DatabaseConfigurationError as error:
        return None, str(error)

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """
            SELECT username, password_hash, role, is_active
            FROM users
            WHERE username = %s
            """,
            (username.strip(),)
        )

        user = cursor.fetchone()

        if user is None:
            return None, "Invalid username or password."

        if not user["is_active"]:
            return None, "This account is inactive."

        password_hash = user["password_hash"].encode("utf-8")

        if not bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash
        ):
            return None, "Invalid username or password."

        return user, "Login successful."

    except mysql.connector.Error:
        return None, "A database error occurred."

    except (ValueError, TypeError):
        return None, "Could not verify the account."

    finally:
        if cursor is not None:
            cursor.close()

        connection.close()


# -----------------------------
# ROLE-AWARE NAVIGATION
# -----------------------------

def role_can_open_feature(role, feature_key):
    """Check access using the role returned by database authentication."""
    feature = FEATURES.get(feature_key)
    if role in {"Super Admin", "Admin"}:
        return feature is not None
    return bool(feature and role in feature["roles"])


def open_feature_placeholder(parent, role, feature_key):
    """Open an implemented screen or a clearly marked placeholder."""
    if not role_can_open_feature(role, feature_key):
        return

    if role == "Admin":
        return open_admin_feature(parent, feature_key)

    if feature_key == "inventory":
        return open_inventory_screen(parent, role)
    if feature_key == "product_management":
        return open_product_management_screen(parent, role)
    if role == "Super Admin" and feature_key == "product_search":
        return open_product_search_screen(parent, role)
    if role == "Super Admin" and feature_key in {"sales", "sales_history", "reports"}:
        return open_super_admin_sales_pending_screen(parent, feature_key)

    feature = FEATURES[feature_key]
    screen = tk.Toplevel(parent)
    screen.title(f"TambayanTea.ph - {feature['title']}")
    screen.geometry("480x280")
    screen.resizable(False, False)
    screen.configure(bg=CREAM)

    tk.Label(
        screen,
        text=feature["title"],
        font=("Arial", 22, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(pady=(32, 12))
    tk.Label(
        screen,
        text=feature["status"],
        font=("Arial", 12),
        bg=CREAM,
        fg=BROWN,
        wraplength=400,
    ).pack(pady=8)
    tk.Label(
        screen,
        text="Placeholder only. No database records are read or changed.",
        font=("Arial", 10),
        bg=CREAM,
        fg="#5C5148",
        wraplength=400,
    ).pack(pady=8)
    tk.Button(
        screen,
        text="Close",
        command=screen.destroy,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        width=14,
    ).pack(pady=18)


def open_product_search_screen(parent, role):
    """Search real product rows already stored in inventory_system.products."""
    if role not in {"Admin", "Super Admin"} or not role_can_open_feature(role, "product_search"):
        return None

    screen = tk.Toplevel(parent)
    screen.title("TambayanTea.ph - Product Search")
    screen.geometry("820x520")
    screen.resizable(False, False)
    screen.configure(bg=CREAM)
    tk.Label(screen, text="Product Search", font=("Arial", 22, "bold"),
             bg=CREAM, fg=BROWN).pack(anchor="w", padx=28, pady=(22, 10))
    search_row = tk.Frame(screen, bg=CREAM)
    search_row.pack(fill="x", padx=28, pady=(0, 12))
    tk.Label(search_row, text="Search by product ID or name:", bg=CREAM,
             fg="#3D332C").pack(side="left", padx=(0, 10))
    search_text = tk.StringVar(value="")
    ttk.Entry(search_row, textvariable=search_text, width=42).pack(side="left")

    table = ttk.Treeview(screen, columns=("product_id", "product_name", "quantity", "price"),
                         show="headings", selectmode="browse", height=15)
    for column, title in (("product_id", "Product ID"), ("product_name", "Product Name"),
                          ("quantity", "Quantity"), ("price", "Price")):
        table.heading(column, text=title)
    table.column("product_id", width=110, anchor="center", stretch=False)
    table.column("product_name", width=400, anchor="w")
    table.column("quantity", width=120, anchor="center", stretch=False)
    table.column("price", width=120, anchor="e", stretch=False)
    table.pack(fill="both", expand=True, padx=28, pady=8)
    status = tk.Label(screen, text="Loading products...", bg=CREAM, fg=BROWN,
                      wraplength=750, justify="left")
    status.pack(anchor="w", padx=28, pady=(4, 8))
    products = []

    def display_matches(*_args):
        table.delete(*table.get_children())
        matches = filter_inventory_products(products, search_text.get())
        for product_id, name, quantity, price in matches:
            table.insert("", "end", values=(product_id, name, quantity, f"{price:.2f}"))
        if not products:
            status.config(text="No products have been added yet.")
        elif not matches:
            status.config(text="No products match your search.")
        else:
            status.config(text=f"Showing {len(matches)} matching product(s).")

    def load_products():
        products.clear()
        conn = cursor = None
        try:
            conn = connect_to_database()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT product_id, product_name, quantity, price "
                "FROM products ORDER BY product_id"
            )
            products.extend(cursor.fetchall())
            display_matches()
        except DatabaseConfigurationError as error:
            status.config(text=str(error), fg="#9B1C1C")
        except mysql.connector.Error:
            status.config(text="Could not search inventory_system.products.", fg="#9B1C1C")
        finally:
            _close_product_resources(cursor, conn)

    search_text.trace_add("write", display_matches)
    controls = tk.Frame(screen, bg=CREAM)
    controls.pack(fill="x", padx=28, pady=(4, 16))
    tk.Button(controls, text="Refresh", command=load_products, bg=BROWN,
              fg="white", activebackground=BROWN_HOVER).pack(side="left")
    tk.Button(controls, text="Back", command=screen.destroy, bg=BROWN,
              fg="white", activebackground=BROWN_HOVER).pack(side="right")
    load_products()
    return screen


def open_super_admin_sales_pending_screen(parent, feature_key):
    """Explain that sales features await a real, approved data schema."""
    if not role_can_open_feature("Super Admin", feature_key):
        return None
    feature = FEATURES[feature_key]
    screen = tk.Toplevel(parent)
    screen.title(f"TambayanTea.ph - {feature['title']}")
    screen.geometry("540x300")
    screen.resizable(False, False)
    screen.configure(bg=CREAM)
    tk.Label(screen, text=feature["title"], font=("Arial", 22, "bold"),
             bg=CREAM, fg=BROWN).pack(pady=(32, 14))
    tk.Label(screen,
             text="This feature requires sales/order tables. The current inventory_system schema has no sales records to display. No sample data has been created.",
             font=("Arial", 11), bg=CREAM, fg="#5C5148", wraplength=470,
             justify="center").pack(padx=24, pady=10)
    tk.Button(screen, text="Back", command=screen.destroy, bg=BROWN,
              fg="white", activebackground=BROWN_HOVER, width=14).pack(pady=20)
    return screen


def open_inventory_screen(parent, role):
    """Display products from inventory_system.products without edit controls."""
    if not role_can_open_feature(role, "inventory"):
        return

    screen = tk.Toplevel(parent)
    screen.title("TambayanTea.ph - Inventory")
    screen.geometry("820x520")
    screen.resizable(False, False)
    screen.configure(bg=CREAM)

    tk.Label(
        screen,
        text="Product Inventory",
        font=("Arial", 22, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(anchor="w", padx=28, pady=(24, 4))
    tk.Label(
        screen,
        text=f"Signed in as {role}  |  Read-only view",
        font=("Arial", 10),
        bg=CREAM,
        fg="#5C5148",
    ).pack(anchor="w", padx=28, pady=(0, 14))

    search_frame = tk.Frame(screen, bg=CREAM)
    search_frame.pack(fill="x", padx=28, pady=(0, 10))
    tk.Label(
        search_frame,
        text="Search by product ID or name:",
        font=("Arial", 10),
        bg=CREAM,
        fg="#3D332C",
    ).pack(side="left", padx=(0, 10))
    search_text = tk.StringVar(value="")
    search_entry = ttk.Entry(search_frame, textvariable=search_text, width=36)
    search_entry.pack(side="left")

    table_frame = tk.Frame(screen, bg=CREAM)
    table_frame.pack(fill="both", expand=True, padx=28)
    columns = ("product_id", "product_name", "quantity", "price")
    table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        selectmode="browse",
        height=14,
    )
    table.heading("product_id", text="Product ID")
    table.heading("product_name", text="Product Name")
    table.heading("quantity", text="Quantity")
    table.heading("price", text="Price")
    table.column("product_id", width=100, anchor="center", stretch=False)
    table.column("product_name", width=400, anchor="w")
    table.column("quantity", width=130, anchor="center", stretch=False)
    table.column("price", width=130, anchor="e", stretch=False)

    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    status = tk.Label(
        screen,
        text="",
        font=("Arial", 10),
        bg=CREAM,
        fg=BROWN,
        wraplength=760,
        justify="left",
    )
    status.pack(anchor="w", padx=28, pady=(10, 4))

    loaded_products = []

    def display_filtered_products(*_args):
        """Filter the products already loaded in memory; do not query MySQL."""
        for item in table.get_children():
            table.delete(item)

        if not loaded_products:
            status.config(text="No products have been added yet.", fg=BROWN)
            return

        matches = filter_inventory_products(loaded_products, search_text.get())

        if not matches:
            status.config(text="No products match your search.", fg=BROWN)
            return

        for product_id, product_name, quantity, price in matches:
            table.insert(
                "",
                "end",
                values=(product_id, product_name, quantity, f"{price:.2f}"),
            )
        if search_term:
            status.config(
                text=f"Showing {len(matches)} matching product(s). This screen is read-only.",
                fg=BROWN,
            )
        else:
            status.config(
                text=f"Showing {len(matches)} product(s). This screen is read-only.",
                fg=BROWN,
            )

    search_text.trace_add("write", display_filtered_products)

    def refresh_inventory():
        loaded_products.clear()
        for item in table.get_children():
            table.delete(item)
        status.config(text="Loading inventory...")

        connection = None
        cursor = None
        try:
            connection = connect_to_database()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT product_id, product_name, quantity, price
                FROM products
                ORDER BY product_id
                """
            )
            products = cursor.fetchall()
            loaded_products.extend(products)
            display_filtered_products()
        except DatabaseConfigurationError as error:
            status.config(text=str(error), fg="#9B1C1C")
        except mysql.connector.Error:
            status.config(
                text="Could not load inventory from inventory_system. "
                "Check the MySQL connection and try again.",
                fg="#9B1C1C",
            )
        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except mysql.connector.Error:
                    pass
            if connection is not None:
                try:
                    connection.close()
                except mysql.connector.Error:
                    pass

    controls = tk.Frame(screen, bg=CREAM)
    controls.pack(fill="x", padx=28, pady=(8, 20))
    tk.Button(
        controls,
        text="Refresh",
        command=refresh_inventory,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        width=14,
    ).pack(side="left")
    tk.Button(
        controls,
        text="Back to Dashboard",
        command=screen.destroy,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        width=20,
    ).pack(side="right")

    refresh_inventory()
    return screen


def open_product_management_screen(parent, role):
    """Show product management controls only to Admin and Super Admin."""
    if not _can_manage_products(role):
        return None

    screen = tk.Toplevel(parent)
    screen.title("TambayanTea.ph - Product Management")
    screen.geometry("900x620")
    screen.resizable(False, False)
    screen.configure(bg=CREAM)

    tk.Label(
        screen,
        text="Product Management",
        font=("Arial", 22, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(anchor="w", padx=28, pady=(22, 4))
    tk.Label(
        screen,
        text=f"Signed in as {role}  |  Product changes are restricted to authorized roles",
        font=("Arial", 10),
        bg=CREAM,
        fg="#5C5148",
    ).pack(anchor="w", padx=28, pady=(0, 12))

    table_frame = tk.Frame(screen, bg=CREAM)
    table_frame.pack(fill="both", expand=True, padx=28)
    columns = ("product_id", "product_name", "quantity", "price")
    table = ttk.Treeview(
        table_frame,
        columns=columns,
        show="headings",
        selectmode="browse",
        height=14,
    )
    for column, heading in (
        ("product_id", "Product ID"),
        ("product_name", "Product Name"),
        ("quantity", "Quantity"),
        ("price", "Price"),
    ):
        table.heading(column, text=heading)
    table.column("product_id", width=100, anchor="center", stretch=False)
    table.column("product_name", width=430, anchor="w")
    table.column("quantity", width=140, anchor="center", stretch=False)
    table.column("price", width=140, anchor="e", stretch=False)
    scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    status = tk.Label(
        screen,
        text="",
        font=("Arial", 10),
        bg=CREAM,
        fg=BROWN,
        wraplength=840,
        justify="left",
    )
    status.pack(anchor="w", padx=28, pady=(8, 4))

    def refresh_products():
        for item in table.get_children():
            table.delete(item)
        status.config(text="Loading products...", fg=BROWN)

        connection = None
        cursor = None
        try:
            connection = connect_to_database()
            cursor = connection.cursor()
            cursor.execute(
                """
                SELECT product_id, product_name, quantity, price
                FROM products
                ORDER BY product_id
                """
            )
            products = cursor.fetchall()
            if not products:
                status.config(text="No products have been added yet.", fg=BROWN)
                return

            for product_id, product_name, quantity, price in products:
                table.insert(
                    "",
                    "end",
                    iid=str(product_id),
                    values=(product_id, product_name, quantity, f"{price:.2f}"),
                )
            status.config(
                text=f"Showing {len(products)} product(s).",
                fg=BROWN,
            )
        except DatabaseConfigurationError as error:
            status.config(text=str(error), fg="#9B1C1C")
        except mysql.connector.Error:
            status.config(
                text="Could not load products from inventory_system. Check the database connection and try again.",
                fg="#9B1C1C",
            )
        finally:
            _close_product_resources(cursor, connection)

    def selected_product():
        selection = table.selection()
        if not selection:
            messagebox.showwarning(
                "Select a product",
                "Choose a product from the table first.",
                parent=screen,
            )
            return None
        values = table.item(selection[0], "values")
        if not values or len(values) != 4:
            messagebox.showerror(
                "Product unavailable",
                "Refresh the table and select the product again.",
                parent=screen,
            )
            return None
        return values

    def add_selected_product():
        open_product_form(screen, role, refresh_products)

    def edit_selected_product():
        product = selected_product()
        if product is not None:
            open_product_form(screen, role, refresh_products, product)

    def set_selected_stock():
        product = selected_product()
        if product is None:
            return
        product_id, product_name, current_quantity, _price = product
        dialog = tk.Toplevel(screen)
        dialog.title("Set Stock Quantity")
        dialog.geometry("420x240")
        dialog.resizable(False, False)
        dialog.configure(bg=CREAM)
        dialog.transient(screen)
        dialog.grab_set()

        tk.Label(
            dialog,
            text=f"Set stock for {product_name}",
            font=("Arial", 14, "bold"),
            bg=CREAM,
            fg=BROWN,
            wraplength=380,
        ).pack(anchor="w", padx=22, pady=(20, 8))
        tk.Label(
            dialog,
            text=f"Current quantity: {current_quantity}. Enter the new total quantity:",
            font=("Arial", 10),
            bg=CREAM,
            fg="#5C5148",
            wraplength=370,
        ).pack(anchor="w", padx=22, pady=(0, 8))
        quantity_entry = ttk.Entry(dialog, width=24)
        quantity_entry.insert(0, str(current_quantity))
        quantity_entry.pack(anchor="w", padx=22, pady=(0, 12))

        def save_stock():
            success, result_message = set_product_stock(
                role, product_id, quantity_entry.get()
            )
            if success:
                messagebox.showinfo("Stock updated", result_message, parent=dialog)
                dialog.destroy()
                refresh_products()
            else:
                messagebox.showerror("Stock not updated", result_message, parent=dialog)

        tk.Button(
            dialog,
            text="Save New Total",
            command=save_stock,
            bg=BROWN,
            fg="white",
            activebackground=BROWN_HOVER,
        ).pack(anchor="w", padx=22)

    actions = tk.Frame(screen, bg=CREAM)
    actions.pack(fill="x", padx=28, pady=(6, 18))
    for label, command in (
        ("Add Product", add_selected_product),
        ("Edit Product", edit_selected_product),
        ("Set Stock", set_selected_stock),
        ("Refresh", refresh_products),
    ):
        tk.Button(
            actions,
            text=label,
            command=command,
            bg=BROWN,
            fg="white",
            activebackground=BROWN_HOVER,
            activeforeground="white",
            cursor="hand2",
            padx=8,
        ).pack(side="left", padx=(0, 7))
    tk.Button(
        actions,
        text="Back to Dashboard",
        command=screen.destroy,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        padx=8,
    ).pack(side="right")

    refresh_products()
    return screen


def open_product_form(parent, role, refresh_callback, product=None):
    """Show the add/edit form; all database authorization remains in helpers."""
    if not _can_manage_products(role):
        return None

    editing = product is not None
    dialog = tk.Toplevel(parent)
    dialog.title("Edit Product" if editing else "Add Product")
    dialog.geometry("440x360")
    dialog.resizable(False, False)
    dialog.configure(bg=CREAM)
    dialog.transient(parent)
    dialog.grab_set()

    tk.Label(
        dialog,
        text="Edit Product" if editing else "Add Product",
        font=("Arial", 18, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(anchor="w", padx=24, pady=(20, 14))

    fields = tk.Frame(dialog, bg=CREAM)
    fields.pack(fill="x", padx=24)
    entries = {}
    initial = {
        "Product Name": product[1] if editing else "",
        "Quantity": product[2] if editing else "0",
        "Price": product[3] if editing else "0.00",
    }
    for row, label_text in enumerate(("Product Name", "Quantity", "Price")):
        tk.Label(
            fields,
            text=label_text,
            font=("Arial", 10),
            bg=CREAM,
            fg="#3D332C",
        ).grid(row=row, column=0, sticky="w", pady=8)
        entry = ttk.Entry(fields, width=32)
        entry.grid(row=row, column=1, padx=(16, 0), pady=8)
        entry.insert(0, str(initial[label_text]))
        entries[label_text] = entry

    def save_product():
        if editing:
            result = edit_product(
                role,
                product[0],
                entries["Product Name"].get(),
                entries["Quantity"].get(),
                entries["Price"].get(),
            )
        else:
            result = add_product(
                role,
                entries["Product Name"].get(),
                entries["Quantity"].get(),
                entries["Price"].get(),
            )

        success, result_message = result
        if success:
            messagebox.showinfo(
                "Product saved",
                result_message,
                parent=dialog,
            )
            dialog.destroy()
            refresh_callback()
        else:
            messagebox.showerror(
                "Product not saved",
                result_message,
                parent=dialog,
            )

    tk.Button(
        dialog,
        text="Save Product",
        command=save_product,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        width=18,
    ).pack(anchor="w", padx=24, pady=18)
    return dialog


def open_dashboard(username, role):
    """Show role-aware navigation; all destinations are placeholders for now."""
    if role not in ROLE_NAMES:
        raise ValueError("The account has an unsupported role.")

    if role == "Admin":
        return open_admin_dashboard(username)

    dashboard = tk.Toplevel(root)
    dashboard.title("TambayanTea.ph - Dashboard")
    dashboard.geometry("820x610")
    dashboard.resizable(False, False)
    dashboard.configure(bg=CREAM)

    header = tk.Frame(dashboard, bg=CREAM)
    header.pack(fill="x", padx=32, pady=(26, 12))

    tk.Label(
        header,
        text="TambayanTea.ph",
        font=("Arial", 24, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(side="left")
    tk.Label(
        header,
        text=f"Signed in as {username}  |  {role}",
        font=("Arial", 11, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(side="right", pady=9)

    tk.Label(
        dashboard,
        text="Dashboard",
        font=("Arial", 19, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(anchor="w", padx=34, pady=(4, 3))
    tk.Label(
        dashboard,
        text="Inventory is read-only. Product Management is available to Admin and Super Admin.",
        font=("Arial", 10),
        bg=CREAM,
        fg="#5C5148",
    ).pack(anchor="w", padx=34, pady=(0, 18))

    navigation = tk.Frame(dashboard, bg=CREAM)
    navigation.pack(fill="both", expand=True, padx=28)

    for index, feature_key in enumerate(
        (
            "inventory",
            "product_management",
            "sales",
            "product_search",
            "sales_history",
            "reports",
        )
    ):
        feature = FEATURES[feature_key]
        row, column = divmod(index, 2)
        card = tk.Frame(navigation, bg="white", bd=1, relief="solid")
        card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
        navigation.grid_columnconfigure(column, weight=1, uniform="feature")
        navigation.grid_rowconfigure(row, weight=1, uniform="feature_row")

        allowed = role_can_open_feature(role, feature_key)
        note = (
            (
                "Search stored products by ID or name."
                if role == "Super Admin" and feature_key == "product_search"
                else (
                    "Requires sales/order tables; no sales records exist in the current schema."
                    if role == "Super Admin" and feature_key in {"sales", "sales_history", "reports"}
                    else feature["status"]
                )
            )
            if allowed
            else "Unavailable until this role's access is confirmed."
        )
        tk.Label(
            card,
            text=feature["title"],
            font=("Arial", 14, "bold"),
            bg="white",
            fg=BROWN,
        ).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(
            card,
            text=note,
            font=("Arial", 9),
            bg="white",
            fg="#5C5148",
            wraplength=300,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 10))
        tk.Button(
            card,
            text=(
                "Open Inventory"
                if feature_key == "inventory" and allowed
                else (
                    "Open Product Management"
                    if feature_key == "product_management" and allowed
                    else (
                        {
                            "sales": "Open Sales",
                            "product_search": "Open Product Search",
                            "sales_history": "Open Sales History",
                            "reports": "Open Reports",
                        }.get(feature_key, "Open placeholder")
                        if role == "Super Admin" and allowed
                        else ("Open placeholder" if allowed else "Unavailable")
                    )
                )
            ),
            command=lambda key=feature_key: open_feature_placeholder(
                dashboard, role, key
            ),
            state=tk.NORMAL if allowed else tk.DISABLED,
            font=("Arial", 10, "bold"),
            bg=BROWN,
            fg="white",
            disabledforeground="#777777",
            activebackground=BROWN_HOVER,
            activeforeground="white",
            cursor="hand2" if allowed else "arrow",
            width=22,
        ).pack(anchor="w", padx=16, pady=(0, 14))

    footer = tk.Frame(dashboard, bg=CREAM)
    footer.pack(fill="x", padx=34, pady=(8, 22))
    tk.Label(
        footer,
        text="Staff inventory remains read-only. Product changes are limited to Admin and Super Admin.",
        font=("Arial", 9),
        bg=CREAM,
        fg="#5C5148",
        wraplength=550,
        justify="left",
    ).pack(side="left")

    def logout():
        if not messagebox.askyesno(
            "Log Out",
            "Are you sure you want to log out?",
            parent=dashboard,
        ):
            return
        dashboard.destroy()
        root.deiconify()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        message.config(text="", fg="red")
        username_entry.focus_set()

    logout_button = tk.Button(
        header if role == "Super Admin" else footer,
        text="Log Out",
        command=logout,
        font=("Arial", 12, "bold"),
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        width=16,
        padx=10,
        pady=7,
        cursor="hand2",
    )
    logout_button.pack(side="right", padx=(12, 0))

    dashboard.protocol("WM_DELETE_WINDOW", logout)


def open_admin_dashboard(username):
    """Admin-only dashboard with the six role-authorized feature options."""
    dashboard = tk.Toplevel(root)
    dashboard.title("TambayanTea.ph - Admin Dashboard")
    dashboard.geometry("900x700")
    dashboard.resizable(False, False)
    dashboard.configure(bg=CREAM)
    tk.Label(dashboard, text="Admin Dashboard", font=("Arial", 24, "bold"),
             bg=CREAM, fg=BROWN).pack(anchor="w", padx=32, pady=(28, 6))
    tk.Label(dashboard, text=f"Signed in as {username}  |  Admin",
             font=("Arial", 11), bg=CREAM, fg="#5C5148").pack(anchor="w", padx=34, pady=(0, 12))

    navigation = tk.Frame(dashboard, bg=CREAM)
    navigation.pack(fill="both", expand=True, padx=26, pady=(0, 8))
    admin_features = (
        ("inventory", "Inventory", "View and adjust current product stock."),
        ("product_management", "Product Management", "Manage product records."),
        ("sales", "Sales", "Requires sales/order tables; no sales workflow is configured."),
        ("product_search", "Product Search", "Search stored products by ID or name."),
        ("sales_history", "Sales History", "Requires sales/order tables; no sales history is stored."),
        ("reports", "Reports", "Requires sales/order tables; reports use actual recorded sales only."),
    )
    for index, (feature_key, title, description) in enumerate(admin_features):
        row, column = divmod(index, 2)
        card = tk.Frame(navigation, bg="white", bd=1, relief="solid")
        card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
        navigation.grid_columnconfigure(column, weight=1, uniform="admin_feature")
        navigation.grid_rowconfigure(row, weight=1, uniform="admin_feature_row")
        tk.Label(card, text=title, font=("Arial", 14, "bold"), bg="white",
                 fg=BROWN).pack(anchor="w", padx=16, pady=(13, 4))
        tk.Label(card, text=description, font=("Arial", 9), bg="white",
                 fg="#5C5148", wraplength=330, justify="left").pack(
                     anchor="w", padx=16, pady=(0, 8)
                 )
        tk.Button(card, text=f"Open {title}",
                  command=lambda key=feature_key: open_feature_placeholder(
                      dashboard, "Admin", key
                  ), font=("Arial", 10, "bold"), bg=BROWN, fg="white",
                  activebackground=BROWN_HOVER, activeforeground="white",
                  cursor="hand2", width=23).pack(anchor="w", padx=16, pady=(0, 12))

    def logout():
        if not messagebox.askyesno("Log Out", "Are you sure you want to log out?", parent=dashboard):
            return
        dashboard.destroy()
        root.deiconify()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        message.config(text="", fg="red")
        username_entry.focus_set()

    tk.Button(dashboard, text="Log Out", command=logout, bg=BROWN, fg="white",
              activebackground=BROWN_HOVER, cursor="hand2", width=18).pack(pady=(22, 8))
    dashboard.protocol("WM_DELETE_WINDOW", logout)
    return dashboard


def open_admin_feature(parent, feature_key):
    """Route Admin features to working screens or a clear schema blocker."""
    if not role_can_open_feature("Admin", feature_key):
        return None
    if feature_key == "inventory":
        return open_admin_inventory(parent)
    if feature_key == "product_management":
        return open_admin_products(parent)
    if feature_key == "product_search":
        return open_product_search_screen(parent, "Admin")
    return open_admin_sales_notice(parent, feature_key)


def open_admin_sales_notice(parent, feature_key):
    """Report missing sales data structures without presenting fake screens."""
    titles = {
        "sales": "Sales",
        "sales_history": "Sales History",
        "reports": "Reports",
    }
    if feature_key not in titles:
        return None
    messagebox.showinfo(
        f"{titles[feature_key]} unavailable",
        f"{titles[feature_key]} requires sales/order tables in inventory_system. "
        "The current database has no sales/order data structures. No sales data "
        "was created. An approved migration is required before this feature can work.",
        parent=parent,
    )
    return None


def _admin_screen_allowed(parent):
    """Admin screens receive the authenticated Admin dashboard as parent."""
    return parent is not None and parent.title().endswith("Admin Dashboard")


def open_admin_products(parent):
    if not _admin_screen_allowed(parent):
        return None
    screen = tk.Toplevel(parent)
    screen.title("Manage Product")
    screen.geometry("800x480")
    screen.configure(bg=CREAM)
    tk.Label(screen, text="Manage Product", font=("Arial", 20, "bold"), bg=CREAM, fg=BROWN).pack(pady=16)
    tk.Label(screen, text="Add/Edit require the approved Category schema migration. Product fields: Product Name, Category (Tea or Coffee), Price.",
             bg=CREAM, fg="#5C5148", wraplength=740).pack(padx=20, pady=8)
    tk.Label(screen, text="Add and Edit are pending the Category migration. Quantity is managed under Manage Inventory.",
             bg=CREAM, fg="#8A3B22", wraplength=740).pack(padx=20, pady=4)
    table = ttk.Treeview(screen, columns=("id", "name", "price"), show="headings", selectmode="browse", height=10)
    for col, label in (("id", "Product ID"), ("name", "Product Name"), ("price", "Price")):
        table.heading(col, text=label)
    table.pack(fill="both", expand=True, padx=24, pady=10)
    def refresh():
        table.delete(*table.get_children())
        conn = cur = None
        try:
            conn = connect_to_database(); cur = conn.cursor()
            cur.execute("SELECT product_id, product_name, price FROM products ORDER BY product_id")
            for pid, name, price in cur.fetchall():
                table.insert("", "end", iid=str(pid), values=(pid, name, f"{price:.2f}"))
        except (DatabaseConfigurationError, mysql.connector.Error) as error:
            messagebox.showerror("Products unavailable", str(error) if isinstance(error, DatabaseConfigurationError) else "Could not load products.", parent=screen)
        finally:
            _close_product_resources(cur, conn)
    def delete_selected():
        selection = table.selection()
        if not selection:
            messagebox.showwarning("Select a product", "Choose a product first.", parent=screen); return
        product = table.item(selection[0], "values")
        if not messagebox.askyesno("Confirm Delete", f"Delete product '{product[1]}'? This cannot be undone.", parent=screen):
            return
        success, result = delete_product("Admin", product[0])
        if success:
            refresh()
        else:
            messagebox.showerror("Product not deleted", result, parent=screen)
    controls = tk.Frame(screen, bg=CREAM); controls.pack(fill="x", padx=24, pady=(0, 16))
    tk.Button(controls, text="Delete", command=delete_selected, bg=BROWN, fg="white").pack(side="left", padx=5)
    tk.Button(controls, text="Refresh", command=refresh, bg=BROWN, fg="white").pack(side="left", padx=5)
    tk.Button(controls, text="Back to Dashboard", command=screen.destroy, bg=BROWN, fg="white").pack(side="right")
    refresh()
    return screen


def open_admin_inventory(parent):
    if not _admin_screen_allowed(parent):
        return None
    screen = tk.Toplevel(parent); screen.title("Manage Inventory"); screen.geometry("800x500"); screen.configure(bg=CREAM)
    tk.Label(screen, text="Manage Inventory", font=("Arial", 20, "bold"), bg=CREAM, fg=BROWN).pack(pady=14)
    table = ttk.Treeview(screen, columns=("id", "name", "quantity", "status"), show="headings", selectmode="browse", height=12)
    for col, label in (("id", "Product ID"), ("name", "Product Name"), ("quantity", "Quantity"), ("status", "Stock Status")):
        table.heading(col, text=label)
    table.pack(fill="both", expand=True, padx=24, pady=10)
    def refresh():
        table.delete(*table.get_children()); conn = cur = None
        try:
            conn = connect_to_database(); cur = conn.cursor()
            cur.execute("SELECT product_id, product_name, quantity FROM products ORDER BY product_id")
            for pid, name, quantity in cur.fetchall():
                table.insert("", "end", iid=str(pid), values=(pid, name, quantity, stock_status(quantity)))
        except (DatabaseConfigurationError, mysql.connector.Error) as error:
            messagebox.showerror("Inventory unavailable", str(error) if isinstance(error, DatabaseConfigurationError) else "Could not load inventory.", parent=screen)
        finally:
            _close_product_resources(cur, conn)
    def adjust():
        selection = table.selection()
        if not selection:
            messagebox.showwarning("Select an item", "Choose an item first.", parent=screen); return
        row = table.item(selection[0], "values")
        value = simpledialog.askstring("Adjust Item", f"New total quantity for {row[1]}:", initialvalue=row[2], parent=screen)
        if value is None: return
        success, result = set_product_stock("Admin", row[0], value)
        if success: refresh()
        else: messagebox.showerror("Stock not updated", result, parent=screen)
    controls = tk.Frame(screen, bg=CREAM); controls.pack(fill="x", padx=24, pady=(0, 16))
    tk.Button(controls, text="Adjust Item", command=adjust, bg=BROWN, fg="white").pack(side="left")
    tk.Button(controls, text="Refresh", command=refresh, bg=BROWN, fg="white").pack(side="left", padx=8)
    tk.Button(controls, text="Back to Dashboard", command=screen.destroy, bg=BROWN, fg="white").pack(side="right")
    refresh(); return screen


def open_admin_reports(parent):
    if not _admin_screen_allowed(parent):
        return None
    screen = tk.Toplevel(parent); screen.title("View Reports"); screen.geometry("600x360"); screen.configure(bg=CREAM)
    tk.Label(screen, text="View Reports", font=("Arial", 20, "bold"), bg=CREAM, fg=BROWN).pack(pady=22)
    tk.Label(screen, text="Reports are pending an approved sales/order schema. No sales records are available in the current database schema.",
             bg=CREAM, fg="#5C5148", wraplength=520).pack(padx=24, pady=15)
    tk.Button(screen, text="Back", command=screen.destroy, bg=BROWN, fg="white").pack(pady=20)
    return screen


def open_account_creation_window(parent, actor_role):
    """Open the account form only for the authenticated Super Admin role."""
    if actor_role != "Super Admin":
        messagebox.showerror(
            "Access denied",
            "Only the Super Admin can create accounts.",
            parent=parent,
        )
        return

    window = tk.Toplevel(parent)
    window.title("Create/Register Account")
    window.geometry("460x430")
    window.resizable(False, False)
    window.configure(bg=CREAM)

    tk.Label(
        window,
        text="Create/Register Account",
        font=("Arial", 18, "bold"),
        bg=CREAM,
        fg=BROWN,
    ).pack(anchor="w", padx=28, pady=(24, 12))

    form = tk.Frame(window, bg=CREAM)
    form.pack(fill="x", padx=28)

    tk.Label(form, text="Username", bg=CREAM, fg=BROWN).grid(
        row=0, column=0, sticky="w", pady=8
    )
    username_entry = ttk.Entry(form, width=32)
    username_entry.grid(row=0, column=1, padx=(12, 0), pady=8)

    tk.Label(form, text="Password", bg=CREAM, fg=BROWN).grid(
        row=1, column=0, sticky="w", pady=8
    )
    password_entry = ttk.Entry(form, width=32, show="*")
    password_entry.grid(row=1, column=1, padx=(12, 0), pady=8)

    tk.Label(form, text="Confirm Password", bg=CREAM, fg=BROWN).grid(
        row=2, column=0, sticky="w", pady=8
    )
    confirmation_entry = ttk.Entry(form, width=32, show="*")
    confirmation_entry.grid(row=2, column=1, padx=(12, 0), pady=8)

    tk.Label(form, text="Account Role", bg=CREAM, fg=BROWN).grid(
        row=3, column=0, sticky="w", pady=8
    )
    selected_role = tk.StringVar(value="Staff")
    ttk.Combobox(
        form,
        textvariable=selected_role,
        values=("Admin", "Staff"),
        state="readonly",
        width=29,
    ).grid(row=3, column=1, padx=(12, 0), pady=8)

    def create_account():
        # Recheck authorization at the action boundary; the role selection is
        # only the new account's role and cannot grant the current user access.
        if actor_role != "Super Admin":
            messagebox.showerror(
                "Access denied",
                "Only the Super Admin can create accounts.",
                parent=window,
            )
            return

        success, result_message = create_account_for_actor(
            actor_role=actor_role,
            username=username_entry.get(),
            password=password_entry.get(),
            confirmation=confirmation_entry.get(),
            role=selected_role.get(),
        )
        password_entry.delete(0, tk.END)
        confirmation_entry.delete(0, tk.END)

        if success:
            username_entry.delete(0, tk.END)
            messagebox.showinfo(
                "Account created",
                result_message,
                parent=window,
            )
        else:
            messagebox.showerror(
                "Account not created",
                result_message,
                parent=window,
            )

    tk.Button(
        window,
        text="Create Account",
        command=create_account,
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        cursor="hand2",
        width=20,
    ).pack(anchor="w", padx=28, pady=22)


# -----------------------------
# LOGIN WINDOW
# -----------------------------

def main():
    global root, username_entry, password_entry, message

    root = tk.Tk()
    root.title("TambayanTea.ph - Login")
    root.geometry("500x400")
    root.resizable(False, False)
    root.configure(bg="#F8F1E7")

    title = tk.Label(
        root,
        text="TambayanTea.ph",
        font=("Arial", 24, "bold"),
        bg="#F8F1E7",
        fg="#70452B"
    )
    title.pack(pady=(35, 5))

    subtitle = tk.Label(
        root,
        text="Product Inventory and Sales Tracking System",
        font=("Arial", 10),
        bg="#F8F1E7",
        fg="#70452B"
    )
    subtitle.pack(pady=(0, 20))

    form = tk.Frame(root, bg="#F8F1E7")
    form.pack()

    tk.Label(
        form,
        text="Username",
        font=("Arial", 11),
        bg="#F8F1E7"
    ).grid(row=0, column=0, sticky="w", pady=8)

    username_entry = ttk.Entry(form, width=30)
    username_entry.grid(row=0, column=1, padx=10, pady=8)

    tk.Label(
        form,
        text="Password",
        font=("Arial", 11),
        bg="#F8F1E7"
    ).grid(row=1, column=0, sticky="w", pady=8)

    password_entry = ttk.Entry(form, width=30, show="*")
    password_entry.grid(row=1, column=1, padx=10, pady=8)

    message = tk.Label(
        root,
        text="",
        font=("Arial", 10),
        bg="#F8F1E7",
        fg="red",
        wraplength=420
    )
    message.pack(pady=5)

    def login():
        username = username_entry.get().strip()
        password = password_entry.get()

        if not username or not password:
            message.config(
                text="Please enter your username and password.",
                fg="red"
            )
            return

        user, result_message = authenticate_user(username, password)

        if user is None:
            message.config(text=result_message, fg="red")
            return

        # The role comes only from the authenticated users-table record.
        if user["role"] not in ROLE_NAMES:
            message.config(text="This account has an unsupported role.", fg="red")
            return

        message.config(text="", fg="red")
        root.withdraw()

        open_dashboard(
            username=user["username"],
            role=user["role"]
        )

    login_button = tk.Button(
        root,
        text="LOGIN",
        command=login,
        font=("Arial", 11, "bold"),
        bg="#70452B",
        fg="white",
        activebackground="#8C5A3C",
        activeforeground="white",
        width=18,
        cursor="hand2"
    )
    login_button.pack(pady=10)

    # Press Enter to log in
    root.bind("<Return>", lambda event: login())

    root.mainloop()


if __name__ == "__main__":
    main()
