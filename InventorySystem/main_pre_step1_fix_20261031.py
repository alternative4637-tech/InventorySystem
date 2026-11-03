import tkinter as tk
from tkinter import ttk
import os
from pathlib import Path
import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().with_name(".env"))


DATABASE_NAME = "inventory_system"
LOCAL_MYSQL_HOSTS = {"localhost", "127.0.0.1", "::1"}
ROLE_NAMES = {"Super Admin", "Admin", "Staff"}

CREAM = "#F8F1E7"
BROWN = "#70452B"
BROWN_HOVER = "#8C5A3C"

# These are only the permissions clearly shown in the project flowchart.
# Product search and sales history stay unavailable until the group confirms
# which roles may use them. All available destinations are still placeholders.
FEATURES = {
    "inventory": {
        "title": "Inventory",
        "roles": ROLE_NAMES,
        "status": "Inventory screens are not implemented yet.",
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

    missing = [name for name, value in settings.items() if not value]
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

    if role not in ("Admin", "Super Admin", "Staff"):
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
    return bool(feature and role in feature["roles"])


def open_feature_placeholder(parent, role, feature_key):
    """Open a clearly marked placeholder without accessing the database."""
    if not role_can_open_feature(role, feature_key):
        return

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


def open_dashboard(username, role):
    """Show role-aware navigation; all destinations are placeholders for now."""
    if role not in ROLE_NAMES:
        raise ValueError("The account has an unsupported role.")

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
        text="Choose a section. Available sections are placeholders in this step.",
        font=("Arial", 10),
        bg=CREAM,
        fg="#5C5148",
    ).pack(anchor="w", padx=34, pady=(0, 18))

    navigation = tk.Frame(dashboard, bg=CREAM)
    navigation.pack(fill="both", expand=True, padx=28)

    for index, feature_key in enumerate(
        ("inventory", "sales", "product_search", "sales_history", "reports")
    ):
        feature = FEATURES[feature_key]
        row, column = divmod(index, 2)
        card = tk.Frame(navigation, bg="white", bd=1, relief="solid")
        card.grid(row=row, column=column, padx=8, pady=8, sticky="nsew")
        navigation.grid_columnconfigure(column, weight=1, uniform="feature")
        navigation.grid_rowconfigure(row, weight=1, uniform="feature_row")

        allowed = role_can_open_feature(role, feature_key)
        note = (
            feature["status"]
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
            text="Open placeholder" if allowed else "Unavailable",
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
        text="Unconfirmed permissions remain unavailable. No inventory or sales actions are active.",
        font=("Arial", 9),
        bg=CREAM,
        fg="#5C5148",
        wraplength=550,
        justify="left",
    ).pack(side="left")

    def logout():
        dashboard.destroy()
        root.deiconify()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        message.config(text="", fg="red")
        username_entry.focus_set()

    tk.Button(
        footer,
        text="LOG OUT",
        command=logout,
        font=("Arial", 10, "bold"),
        bg=BROWN,
        fg="white",
        activebackground=BROWN_HOVER,
        activeforeground="white",
        width=14,
        cursor="hand2",
    ).pack(side="right")

    dashboard.protocol("WM_DELETE_WINDOW", logout)


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
