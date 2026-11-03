"""A beginner-friendly terminal inventory app for the existing MySQL table."""

import os
from decimal import Decimal, InvalidOperation

import mysql.connector
from dotenv import load_dotenv
from mysql.connector import Error


# Load private settings from .env. The database and table are pre-existing.
load_dotenv()


def connect_to_database():
    """Connect to the configured database, or explain which settings are missing."""
    settings = {
        "host": os.getenv("MYSQL_HOST", "").strip(),
        "port": os.getenv("MYSQL_PORT", "").strip(),
        "user": os.getenv("MYSQL_USER", "").strip(),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "").strip(),
    }

    missing = [key for key, value in settings.items() if not value]
    if missing:
        print("Database settings are incomplete in .env: " + ", ".join(missing))
        print("Fill in those values, then run the program again. Do not share your password.")
        return None

    try:
        settings["port"] = int(settings["port"])
        return mysql.connector.connect(**settings)
    except ValueError:
        print("MYSQL_PORT in .env must be a number.")
    except Error as error:
        # Connector errors may contain connection details, so do not echo them verbatim.
        print(f"Could not connect to MySQL ({error.__class__.__name__}). Check .env and MySQL Server.")
    return None


def read_non_empty_text(prompt):
    """Ask until the user enters text that is not blank."""
    while True:
        value = input(prompt).strip()
        if value:
            return value
        print("Please enter a value.")


def read_non_negative_integer(prompt):
    """Read a whole number that is zero or greater."""
    while True:
        value = input(prompt).strip()
        try:
            number = int(value)
            if number >= 0:
                return number
        except ValueError:
            pass
        print("Enter a whole number that is 0 or greater.")


def read_non_negative_price(prompt):
    """Read a valid non-negative price with at most two decimal places."""
    while True:
        value = input(prompt).strip()
        try:
            price = Decimal(value)
            if price.is_finite() and price >= 0 and price.as_tuple().exponent >= -2:
                return price
        except InvalidOperation:
            pass
        print("Enter a valid price that is 0 or greater, with up to 2 decimal places.")


def add_product(cursor, connection):
    name = read_non_empty_text("Product name: ")
    quantity = read_non_negative_integer("Quantity: ")
    price = read_non_negative_price("Price: ")
    cursor.execute(
        "INSERT INTO products (product_name, quantity, price) VALUES (%s, %s, %s)",
        (name, quantity, price),
    )
    connection.commit()
    print(f"Product added with ID {cursor.lastrowid}.")


def display_products(cursor):
    cursor.execute("SELECT product_id, product_name, quantity, price FROM products ORDER BY product_id")
    products = cursor.fetchall()
    if not products:
        print("No products found.")
        return
    print("\nID | Product name | Quantity | Price")
    print("-" * 55)
    for product_id, name, quantity, price in products:
        print(f"{product_id} | {name} | {quantity} | {price}")


def search_product(cursor):
    product_id = read_non_negative_integer("Product ID: ")
    cursor.execute(
        "SELECT product_id, product_name, quantity, price FROM products WHERE product_id = %s",
        (product_id,),
    )
    product = cursor.fetchone()
    if product:
        print("ID | Product name | Quantity | Price")
        print(f"{product[0]} | {product[1]} | {product[2]} | {product[3]}")
    else:
        print("No product found with that ID.")


def update_product(cursor, connection):
    product_id = read_non_negative_integer("Product ID to update: ")
    cursor.execute("SELECT product_id FROM products WHERE product_id = %s", (product_id,))
    if cursor.fetchone() is None:
        print("No product found with that ID.")
        return

    name = read_non_empty_text("New product name: ")
    quantity = read_non_negative_integer("New quantity: ")
    price = read_non_negative_price("New price: ")
    cursor.execute(
        "UPDATE products SET product_name = %s, quantity = %s, price = %s WHERE product_id = %s",
        (name, quantity, price, product_id),
    )
    connection.commit()
    print("Product updated.")


def delete_product(cursor, connection):
    product_id = read_non_negative_integer("Product ID to delete: ")
    cursor.execute(
        "SELECT product_id, product_name FROM products WHERE product_id = %s",
        (product_id,),
    )
    product = cursor.fetchone()
    if product is None:
        print("No product found with that ID.")
        return

    answer = input(f"Delete '{product[1]}' (ID {product[0]})? Type yes to confirm: ").strip().lower()
    if answer == "yes":
        cursor.execute("DELETE FROM products WHERE product_id = %s", (product_id,))
        connection.commit()
        print("Product deleted.")
    else:
        print("Deletion cancelled.")


def main():
    connection = connect_to_database()
    if connection is None:
        return

    cursor = None
    try:
        cursor = connection.cursor()
        actions = {
            "1": add_product,
            "2": display_products,
            "3": search_product,
            "4": update_product,
            "5": delete_product,
        }

        while True:
            print("\n=== Inventory Management System ===")
            print("1. Add product")
            print("2. Display all products")
            print("3. Search product by ID")
            print("4. Update product")
            print("5. Delete product")
            print("0. Exit")
            choice = input("Choose an option: ").strip()

            if choice == "0":
                print("Goodbye.")
                break
            action = actions.get(choice)
            if action is None:
                print("Choose one of the listed options.")
                continue
            try:
                if choice == "2" or choice == "3":
                    action(cursor)
                else:
                    action(cursor, connection)
            except Error as error:
                connection.rollback()
                print(f"Database operation failed ({error.__class__.__name__}); no changes were committed.")
            except (KeyboardInterrupt, EOFError):
                print("\nInput cancelled.")
    except Error as error:
        print(f"Could not prepare database access ({error.__class__.__name__}).")
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
        print("Database connection closed.")


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\nProgram stopped.")
