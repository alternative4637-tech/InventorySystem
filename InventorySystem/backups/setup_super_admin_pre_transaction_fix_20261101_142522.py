"""One-time local setup for the first TambayanTea.ph Super Admin account.

Run this script directly from a local terminal. It is deliberately separate
from the Tkinter startup flow and does not accept passwords as command-line
arguments.
"""

from getpass import getpass
import sys

import bcrypt
import mysql.connector

from main import DatabaseConfigurationError, connect_to_database


SUPER_ADMIN_ROLE = "Super Admin"
LOCK_NAME = "tambayantea_inventory_system_initial_super_admin"
LOCK_WAIT_SECONDS = 10
MIN_PASSWORD_LENGTH = 12
MAX_BCRYPT_PASSWORD_BYTES = 72


def validate_credentials(username, password, confirmation):
    """Return a safe validation message, or None when input is acceptable."""
    username = username.strip()
    if not username:
        return "Username is required."
    if len(username) > 50:
        return "Username must be 50 characters or fewer."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use a password with at least {MIN_PASSWORD_LENGTH} characters."
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        return "Password is too long for bcrypt. Use no more than 72 UTF-8 bytes."
    if password != confirmation:
        return "The password entries do not match."
    return None


def create_initial_super_admin(username, password):
    """Create the first Super Admin, or refuse if setup is already complete."""
    connection = None
    cursor = None
    lock_acquired = False
    transaction_started = False
    committed = False

    try:
        connection = connect_to_database()
        # connect_to_database verifies the configured and selected database.
        if connection.database != "inventory_system":
            print("Setup stopped: the connection did not select inventory_system.")
            return False

        cursor = connection.cursor()
        cursor.execute("SELECT GET_LOCK(%s, %s)", (LOCK_NAME, LOCK_WAIT_SECONDS))
        lock_result = cursor.fetchone()[0]
        if lock_result != 1:
            print("Setup could not acquire the setup lock. No account was created.")
            return False
        lock_acquired = True

        # Count every Super Admin, including inactive accounts.
        cursor.execute(
            "SELECT COUNT(*) FROM users WHERE role = %s",
            (SUPER_ADMIN_ROLE,),
        )
        existing_count = cursor.fetchone()[0]
        if existing_count != 0:
            print("A Super Admin account already exists. Setup was refused.")
            return False

        # Hash only after the guarded count check; never print or log this value.
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(),
        ).decode("utf-8")

        connection.start_transaction()
        transaction_started = True
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (%s, %s, %s)
            """,
            (username.strip(), password_hash, SUPER_ADMIN_ROLE),
        )
        connection.commit()
        committed = True
        transaction_started = False
        print("Initial Super Admin account created successfully.")
        return True

    except DatabaseConfigurationError as error:
        print(f"Setup stopped: {error}")
        return False
    except mysql.connector.IntegrityError:
        if connection is not None and transaction_started:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass
        print("Setup was refused because a conflicting account already exists.")
        return False
    except mysql.connector.Error:
        if connection is not None and transaction_started and not committed:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass
        print("A database operation failed. No account was created.")
        return False
    except Exception:
        if connection is not None and transaction_started and not committed:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass
        print("Setup could not be completed. Check the setup status before retrying.")
        return False
    finally:
        if cursor is not None and lock_acquired:
            try:
                cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
                cursor.fetchone()
            except mysql.connector.Error:
                # Closing the connection also releases a connection-scoped lock.
                pass
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


def main():
    """Prompt securely and start the one-time setup operation."""
    try:
        username = input("Choose a username (up to 50 characters): ").strip()
        password = getpass("Choose a password (hidden): ")
        confirmation = getpass("Confirm the password (hidden): ")
    except (EOFError, KeyboardInterrupt):
        print("Setup cancelled. No account was created.")
        return 1

    validation_message = validate_credentials(username, password, confirmation)
    if validation_message:
        print(validation_message)
        return 1

    return 0 if create_initial_super_admin(username, password) else 1


if __name__ == "__main__":
    sys.exit(main())
