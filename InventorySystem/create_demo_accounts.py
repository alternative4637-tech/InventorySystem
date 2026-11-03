"""One-time local creation of the requested Admin and Staff demo accounts.

Run from the InventorySystem directory with its .venv Python. Password input
is hidden. This script is deliberately limited to inventory_system.
"""

from getpass import getpass
import os
from pathlib import Path
import sys

import bcrypt
import mysql.connector
from dotenv import load_dotenv


DATABASE_NAME = "inventory_system"
LOCAL_HOST = "127.0.0.1"
ACCOUNTS = (("Admin", "Admin"), ("Staff", "Staff"))
MAX_BCRYPT_PASSWORD_BYTES = 72


def load_connection_settings():
    """Load project settings explicitly and force the local approved schema."""
    env_path = Path(__file__).resolve().with_name(".env")
    if not env_path.is_file() or not load_dotenv(env_path, override=True):
        raise RuntimeError("Project .env could not be loaded.")

    settings = {
        "host": LOCAL_HOST,
        "port": os.getenv("MYSQL_PORT", "").strip(),
        "user": os.getenv("MYSQL_USER", "").strip(),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "").strip(),
    }
    required = ("MYSQL_PORT", "MYSQL_USER", "MYSQL_PASSWORD", "MYSQL_DATABASE")
    missing = [name for name in required if not os.getenv(name, "").strip()]
    if missing:
        raise RuntimeError("Missing required .env setting(s): " + ", ".join(missing))
    if settings["database"] != DATABASE_NAME:
        raise RuntimeError("MYSQL_DATABASE must be inventory_system; no connection was attempted.")
    try:
        settings["port"] = int(settings["port"])
    except ValueError:
        raise RuntimeError("MYSQL_PORT must be a number.") from None
    if not 1 <= settings["port"] <= 65535:
        raise RuntimeError("MYSQL_PORT is outside the valid range.")
    return settings


def get_confirmed_password():
    password = getpass("Enter the requested demo password (input hidden): ")
    confirmation = getpass("Re-enter the same password (input hidden): ")
    if password != confirmation:
        raise RuntimeError("Password entries did not match; no account changes were made.")
    if not password:
        raise RuntimeError("Password cannot be empty; no account changes were made.")
    if len(password.encode("utf-8")) > MAX_BCRYPT_PASSWORD_BYTES:
        raise RuntimeError("Password exceeds bcrypt's supported length; no account changes were made.")
    return password


def safe_mysql_error_message(error, settings, password=None, password_hash=None):
    """Return server diagnostics with every configured secret/value redacted."""
    text = getattr(error, "msg", "") or "Database connector returned no message."
    values_to_redact = list(settings.values()) if settings else []
    values_to_redact.extend((password, password_hash))
    for value in values_to_redact:
        if value is None:
            continue
        value = str(value)
        if value:
            text = text.replace(value, "<redacted>")
    return text[:500]


def create_accounts():
    connection = None
    cursor = None
    transaction_started = False
    committed = False
    current_operation = "load local project configuration"
    settings = None
    password = None
    password_hash = None
    try:
        settings = load_connection_settings()
        password = get_confirmed_password()
        current_operation = "open MySQL connection"
        connection = mysql.connector.connect(**settings)
        current_operation = "confirm selected database"
        if connection.database != DATABASE_NAME:
            raise RuntimeError("Connection did not select inventory_system; no changes were made.")

        current_operation = "open users table cursor"
        cursor = connection.cursor()

        # Validate the existing table structure and transactional engine.
        current_operation = "inspect users table columns"
        cursor.execute("SHOW COLUMNS FROM users")
        columns = {row[0] for row in cursor.fetchall()}
        required_columns = {"user_id", "username", "password_hash", "role", "is_active"}
        if not required_columns.issubset(columns):
            raise RuntimeError("users table structure did not match expectations; no changes were made.")
        current_operation = "inspect users table storage engine"
        cursor.execute(
            "SELECT ENGINE FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
            (DATABASE_NAME, "users"),
        )
        engine_row = cursor.fetchone()
        if not engine_row or engine_row[0] != "InnoDB":
            raise RuntimeError("users table is not confirmed as InnoDB; no changes were made.")

        # Complete all read-only preflight checks first. With autocommit off,
        # these SELECT/SHOW statements may open an implicit read transaction.
        current_operation = "check whether Admin or Staff usernames already exist"
        cursor.execute(
            "SELECT username, role FROM users WHERE username IN (%s, %s)",
            ("Admin", "Staff"),
        )
        existing = cursor.fetchall()
        if existing:
            found = ", ".join(f"{username} (role: {role})" for username, role in existing)
            raise RuntimeError(
                "Creation stopped because requested username(s) already exist: " + found
                + ". No accounts were added."
            )

        # Compute the same bcrypt hash used by the application before opening
        # the write transaction, keeping password work outside the transaction.
        current_operation = "hash requested password with bcrypt"
        password_hash = bcrypt.hashpw(
            password.encode("utf-8"), bcrypt.gensalt()
        ).decode("utf-8")

        # End any implicit read transaction before starting the one and only
        # account-creation transaction. Unique username constraints still
        # protect against a concurrent insert after the duplicate preflight;
        # a conflict then aborts and rolls back this entire write transaction.
        if connection.in_transaction:
            current_operation = "finish preliminary read-only checks"
            connection.rollback()

        current_operation = "start account transaction"
        connection.start_transaction()
        transaction_started = True

        for username, role in ACCOUNTS:
            current_operation = f"insert {role} account"
            cursor.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
                (username, password_hash, role),
            )

        current_operation = "verify both inserted usernames and roles"
        cursor.execute(
            "SELECT username, role FROM users WHERE username IN (%s, %s)",
            ("Admin", "Staff"),
        )
        verified = set(cursor.fetchall())
        if verified != {("Admin", "Admin"), ("Staff", "Staff")}:
            raise RuntimeError("Post-insert verification failed; transaction will be rolled back.")

        current_operation = "commit both account rows"
        connection.commit()
        committed = True
        transaction_started = False
        print("Success: exactly the requested Admin and Staff accounts were created.")
        return True
    except Exception as error:
        if connection is not None and transaction_started and not committed:
            try:
                connection.rollback()
            except mysql.connector.Error:
                pass
        if isinstance(error, RuntimeError):
            print(f"Stopped: {error}")
        elif isinstance(error, mysql.connector.Error):
            error_number = getattr(error, "errno", None)
            sqlstate = getattr(error, "sqlstate", None)
            details = safe_mysql_error_message(error, settings, password, password_hash)
            print(f"Stopped during operation: {current_operation}.")
            print(f"Database error type: {type(error).__name__}.")
            print(f"MySQL error number: {error_number if error_number is not None else 'unavailable'}.")
            if sqlstate:
                print(f"SQLSTATE: {sqlstate}.")
            print(f"Database message: {details}")
            print("The transaction was rolled back if it had started.")
        else:
            print("Stopped: account creation did not complete; the transaction was rolled back if started.")
        return False
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


if __name__ == "__main__":
    sys.exit(0 if create_accounts() else 1)
