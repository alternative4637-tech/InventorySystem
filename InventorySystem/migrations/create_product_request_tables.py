"""Create the four reviewed product-request support tables.

This script is intentionally manual. It is not called by the Tkinter app.
Run it with Python's -u option so each stage is reported immediately.
It performs read-only metadata checks before issuing the four CREATE TABLE
statements. It never drops or replaces tables.
"""

from __future__ import annotations

import sys
from pathlib import Path


# Make the project root importable when this file is run from migrations/.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import mysql.connector

from main import DatabaseConfigurationError, connect_to_database


DATABASE_NAME = "inventory_system"
TARGET_TABLES = (
    "product_requests",
    "product_request_events",
    "app_notifications",
    "product_audit_events",
)
FOREIGN_KEY_NAMES = (
    "fk_product_requests_requester",
    "fk_product_requests_reviewer",
    "fk_product_requests_product",
    "fk_request_events_request",
    "fk_request_events_product",
    "fk_request_events_actor",
    "fk_notifications_recipient",
    "fk_notifications_event",
    "fk_product_audit_product",
    "fk_product_audit_actor",
)


class PreflightError(Exception):
    """A safe reason to stop before any CREATE TABLE statement."""


CREATE_STATEMENTS = (
    (
        "product_requests",
        """CREATE TABLE `inventory_system`.`product_requests` (
            `request_id` INT NOT NULL AUTO_INCREMENT,
            `linked_product_id` INT NULL DEFAULT NULL,
            `product_name` VARCHAR(100) NOT NULL,
            `requested_quantity` INT NOT NULL,
            `requested_price` DECIMAL(10, 2) NOT NULL,
            `approved_quantity` INT NULL DEFAULT NULL,
            `approved_price` DECIMAL(10, 2) NULL DEFAULT NULL,
            `status` ENUM('Pending', 'Approved', 'Rejected')
                NOT NULL DEFAULT 'Pending',
            `requested_by` INT NOT NULL,
            `requested_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `reviewed_by` INT NULL DEFAULT NULL,
            `reviewed_at` DATETIME(6) NULL DEFAULT NULL,
            `decision_note` VARCHAR(500) NULL DEFAULT NULL,

            PRIMARY KEY (`request_id`),
            UNIQUE KEY `uq_product_requests_linked_product`
                (`linked_product_id`),
            KEY `ix_product_requests_status_time`
                (`status`, `requested_at`, `request_id`),
            KEY `ix_product_requests_requester_time`
                (`requested_by`, `requested_at`, `request_id`),
            KEY `ix_product_requests_reviewer_time`
                (`reviewed_by`, `reviewed_at`, `request_id`),

            CONSTRAINT `fk_product_requests_requester`
                FOREIGN KEY (`requested_by`)
                REFERENCES `inventory_system`.`users` (`user_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_product_requests_reviewer`
                FOREIGN KEY (`reviewed_by`)
                REFERENCES `inventory_system`.`users` (`user_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_product_requests_product`
                FOREIGN KEY (`linked_product_id`)
                REFERENCES `inventory_system`.`products` (`product_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT
        ) ENGINE=InnoDB""",
    ),
    (
        "product_request_events",
        """CREATE TABLE `inventory_system`.`product_request_events` (
            `event_id` INT NOT NULL AUTO_INCREMENT,
            `request_id` INT NOT NULL,
            `product_id` INT NULL DEFAULT NULL,
            `actor_user_id` INT NOT NULL,
            `actor_role` ENUM('Staff', 'Admin', 'Super Admin') NOT NULL,
            `event_type` ENUM(
                'Submitted',
                'ApprovedAsRequested',
                'ApprovedWithChanges',
                'Rejected'
            ) NOT NULL,
            `event_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `product_name_snapshot` VARCHAR(100) NOT NULL,
            `requested_quantity_snapshot` INT NOT NULL,
            `requested_price_snapshot` DECIMAL(10, 2) NOT NULL,
            `approved_quantity_snapshot` INT NULL DEFAULT NULL,
            `approved_price_snapshot` DECIMAL(10, 2) NULL DEFAULT NULL,
            `decision_note` VARCHAR(500) NULL DEFAULT NULL,

            PRIMARY KEY (`event_id`),
            KEY `ix_request_events_request_time`
                (`request_id`, `event_at`, `event_id`),
            KEY `ix_request_events_actor_time`
                (`actor_user_id`, `event_at`),
            KEY `ix_request_events_product` (`product_id`),

            CONSTRAINT `fk_request_events_request`
                FOREIGN KEY (`request_id`)
                REFERENCES `inventory_system`.`product_requests` (`request_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_request_events_product`
                FOREIGN KEY (`product_id`)
                REFERENCES `inventory_system`.`products` (`product_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_request_events_actor`
                FOREIGN KEY (`actor_user_id`)
                REFERENCES `inventory_system`.`users` (`user_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT
        ) ENGINE=InnoDB""",
    ),
    (
        "app_notifications",
        """CREATE TABLE `inventory_system`.`app_notifications` (
            `notification_id` INT NOT NULL AUTO_INCREMENT,
            `recipient_user_id` INT NOT NULL,
            `event_id` INT NOT NULL,
            `created_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `read_at` DATETIME(6) NULL DEFAULT NULL,

            PRIMARY KEY (`notification_id`),
            UNIQUE KEY `uq_notifications_recipient_event`
                (`recipient_user_id`, `event_id`),
            KEY `ix_notifications_recipient_read_time`
                (`recipient_user_id`, `read_at`, `created_at`),

            CONSTRAINT `fk_notifications_recipient`
                FOREIGN KEY (`recipient_user_id`)
                REFERENCES `inventory_system`.`users` (`user_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_notifications_event`
                FOREIGN KEY (`event_id`)
                REFERENCES `inventory_system`.`product_request_events` (`event_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT
        ) ENGINE=InnoDB""",
    ),
    (
        "product_audit_events",
        """CREATE TABLE `inventory_system`.`product_audit_events` (
            `event_id` INT NOT NULL AUTO_INCREMENT,
            `product_id` INT NOT NULL,
            `actor_user_id` INT NOT NULL,
            `actor_role` ENUM('Admin', 'Super Admin') NOT NULL,
            `event_type` ENUM(
                'DirectAdded',
                'Edited',
                'StockChanged',
                'Archived'
            ) NOT NULL,
            `event_at` DATETIME(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
            `product_name_before` VARCHAR(100) NULL DEFAULT NULL,
            `product_name_after` VARCHAR(100) NULL DEFAULT NULL,
            `quantity_before` INT NULL DEFAULT NULL,
            `quantity_after` INT NULL DEFAULT NULL,
            `price_before` DECIMAL(10, 2) NULL DEFAULT NULL,
            `price_after` DECIMAL(10, 2) NULL DEFAULT NULL,
            `product_status_before` ENUM(
                'Active', 'Approval Pending', 'Archived'
            ) NULL DEFAULT NULL,
            `product_status_after` ENUM(
                'Active', 'Approval Pending', 'Archived'
            ) NULL DEFAULT NULL,

            PRIMARY KEY (`event_id`),
            KEY `ix_product_audit_product_time`
                (`product_id`, `event_at`, `event_id`),
            KEY `ix_product_audit_actor_time`
                (`actor_user_id`, `event_at`),

            CONSTRAINT `fk_product_audit_product`
                FOREIGN KEY (`product_id`)
                REFERENCES `inventory_system`.`products` (`product_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT,
            CONSTRAINT `fk_product_audit_actor`
                FOREIGN KEY (`actor_user_id`)
                REFERENCES `inventory_system`.`users` (`user_id`)
                ON UPDATE RESTRICT ON DELETE RESTRICT
        ) ENGINE=InnoDB""",
    ),
)


def report(message):
    """Print a progress message immediately without exposing configuration."""
    print(message, flush=True)


def check_preflight(cursor):
    """Read metadata only and stop if assumptions or names differ."""
    cursor.execute(
        """SELECT TABLE_NAME, ENGINE
           FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_SCHEMA = %s
             AND TABLE_NAME IN ('users', 'products')""",
        (DATABASE_NAME,),
    )
    engines = {table: engine for table, engine in cursor.fetchall()}
    if engines != {"users": "InnoDB", "products": "InnoDB"}:
        raise PreflightError("Expected users and products InnoDB tables were not confirmed.")

    cursor.execute(
        """SELECT TABLE_NAME
           FROM INFORMATION_SCHEMA.TABLES
           WHERE TABLE_SCHEMA = %s
             AND TABLE_NAME IN (%s, %s, %s, %s)""",
        (DATABASE_NAME, *TARGET_TABLES),
    )
    existing_tables = [row[0] for row in cursor.fetchall()]
    if existing_tables:
        raise PreflightError(
            "One or more target tables already exist: " + ", ".join(existing_tables)
        )

    cursor.execute(
        """SELECT CONSTRAINT_NAME
           FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS
           WHERE CONSTRAINT_SCHEMA = %s
             AND CONSTRAINT_NAME IN (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (DATABASE_NAME, *FOREIGN_KEY_NAMES),
    )
    if cursor.fetchall():
        raise PreflightError("A proposed foreign-key constraint name is already in use.")

    cursor.execute(
        """SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE,
                  IS_NULLABLE, COLUMN_KEY, EXTRA
           FROM INFORMATION_SCHEMA.COLUMNS
           WHERE TABLE_SCHEMA = %s
             AND ((TABLE_NAME = 'users' AND COLUMN_NAME = 'user_id')
               OR (TABLE_NAME = 'products' AND COLUMN_NAME = 'product_id'))""",
        (DATABASE_NAME,),
    )
    primary_columns = {
        (table, column): (column_type, nullable, key, extra)
        for table, column, column_type, nullable, key, extra in cursor.fetchall()
    }
    expected = {
        ("users", "user_id"): ("int", "NO", "PRI", "auto_increment"),
        ("products", "product_id"): ("int", "NO", "PRI", "auto_increment"),
    }
    if primary_columns != expected:
        raise PreflightError("Referenced user/product key definitions differ from the reviewed assumptions.")


def verify_created_tables(cursor):
    """Verify table engines, expected columns, indexes, and foreign keys."""
    expected_columns = {
        "product_requests": {
            "request_id", "linked_product_id", "product_name", "requested_quantity",
            "requested_price", "approved_quantity", "approved_price", "status",
            "requested_by", "requested_at", "reviewed_by", "reviewed_at", "decision_note",
        },
        "product_request_events": {
            "event_id", "request_id", "product_id", "actor_user_id", "actor_role",
            "event_type", "event_at", "product_name_snapshot", "requested_quantity_snapshot",
            "requested_price_snapshot", "approved_quantity_snapshot",
            "approved_price_snapshot", "decision_note",
        },
        "app_notifications": {
            "notification_id", "recipient_user_id", "event_id", "created_at", "read_at",
        },
        "product_audit_events": {
            "event_id", "product_id", "actor_user_id", "actor_role", "event_type",
            "event_at", "product_name_before", "product_name_after", "quantity_before",
            "quantity_after", "price_before", "price_after", "product_status_before",
            "product_status_after",
        },
    }
    expected_indexes = {
        "product_requests": {
            "PRIMARY": 0, "uq_product_requests_linked_product": 0,
            "ix_product_requests_status_time": 1,
            "ix_product_requests_requester_time": 1,
            "ix_product_requests_reviewer_time": 1,
        },
        "product_request_events": {
            "PRIMARY": 0, "ix_request_events_request_time": 1,
            "ix_request_events_actor_time": 1, "ix_request_events_product": 1,
        },
        "app_notifications": {
            "PRIMARY": 0, "uq_notifications_recipient_event": 0,
            "ix_notifications_recipient_read_time": 1,
        },
        "product_audit_events": {
            "PRIMARY": 0, "ix_product_audit_product_time": 1,
            "ix_product_audit_actor_time": 1,
        },
    }
    expected_foreign_keys = {
        ("product_requests", "fk_product_requests_requester", "requested_by", "users", "user_id"),
        ("product_requests", "fk_product_requests_reviewer", "reviewed_by", "users", "user_id"),
        ("product_requests", "fk_product_requests_product", "linked_product_id", "products", "product_id"),
        ("product_request_events", "fk_request_events_request", "request_id", "product_requests", "request_id"),
        ("product_request_events", "fk_request_events_product", "product_id", "products", "product_id"),
        ("product_request_events", "fk_request_events_actor", "actor_user_id", "users", "user_id"),
        ("app_notifications", "fk_notifications_recipient", "recipient_user_id", "users", "user_id"),
        ("app_notifications", "fk_notifications_event", "event_id", "product_request_events", "event_id"),
        ("product_audit_events", "fk_product_audit_product", "product_id", "products", "product_id"),
        ("product_audit_events", "fk_product_audit_actor", "actor_user_id", "users", "user_id"),
    }

    table_placeholders = ", ".join(["%s"] * len(TARGET_TABLES))
    cursor.execute(
        f"""SELECT TABLE_NAME, ENGINE
            FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({table_placeholders})""",
        (DATABASE_NAME, *TARGET_TABLES),
    )
    engines = {table: engine for table, engine in cursor.fetchall()}
    if engines != {table: "InnoDB" for table in TARGET_TABLES}:
        raise RuntimeError("Table engine verification did not match the proposal.")

    for table, columns in expected_columns.items():
        cursor.execute(
            """SELECT COLUMN_NAME
               FROM INFORMATION_SCHEMA.COLUMNS
               WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s""",
            (DATABASE_NAME, table),
        )
        if {row[0] for row in cursor.fetchall()} != columns:
            raise RuntimeError(f"Column verification failed for {table}.")

    actual_indexes = {table: {} for table in TARGET_TABLES}
    cursor.execute(
        f"""SELECT TABLE_NAME, INDEX_NAME, NON_UNIQUE
            FROM INFORMATION_SCHEMA.STATISTICS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME IN ({table_placeholders})""",
        (DATABASE_NAME, *TARGET_TABLES),
    )
    for table, index_name, non_unique in cursor.fetchall():
        actual_indexes[table][index_name] = non_unique
    if actual_indexes != expected_indexes:
        raise RuntimeError("Index verification did not match the proposal.")

    cursor.execute(
        f"""SELECT kcu.TABLE_NAME, kcu.CONSTRAINT_NAME, kcu.COLUMN_NAME,
                  kcu.REFERENCED_TABLE_NAME, kcu.REFERENCED_COLUMN_NAME,
                  rc.UPDATE_RULE, rc.DELETE_RULE
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE AS kcu
            JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS AS tc
              ON tc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
             AND tc.TABLE_NAME = kcu.TABLE_NAME
             AND tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS AS rc
              ON rc.CONSTRAINT_SCHEMA = kcu.CONSTRAINT_SCHEMA
             AND rc.TABLE_NAME = kcu.TABLE_NAME
             AND rc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            WHERE kcu.TABLE_SCHEMA = %s
              AND tc.CONSTRAINT_TYPE = 'FOREIGN KEY'
              AND kcu.TABLE_NAME IN ({table_placeholders})""",
        (DATABASE_NAME, *TARGET_TABLES),
    )
    actual_foreign_keys = set()
    for table, name, column, ref_table, ref_column, update_rule, delete_rule in cursor.fetchall():
        actual_foreign_keys.add((table, name, column, ref_table, ref_column))
        if update_rule != "RESTRICT" or delete_rule != "RESTRICT":
            raise RuntimeError("A foreign-key deletion/update rule did not match the proposal.")
    if actual_foreign_keys != expected_foreign_keys:
        raise RuntimeError("Foreign-key verification did not match the proposal.")


def main():
    connection = None
    cursor = None
    created_tables = []
    current_table = None
    try:
        report("CONNECTING: inventory_system")
        connection = connect_to_database()
        if connection.database != DATABASE_NAME:
            raise PreflightError("Connected database verification failed.")
        cursor = connection.cursor()

        report("PREFLIGHT: checking existing tables, names, engines, and referenced keys")
        check_preflight(cursor)
        report("PREFLIGHT: passed")

        for table_name, statement in CREATE_STATEMENTS:
            current_table = table_name
            report(f"CREATE: starting {table_name}")
            cursor.execute(statement)
            created_tables.append(table_name)
            report(f"CREATE: succeeded {table_name}")
            current_table = None

        report("VERIFY: checking columns, indexes, foreign keys, and engines")
        verify_created_tables(cursor)
        report("VERIFY: passed")
        report("COMPLETED: all four approved tables created and verified")
        return 0

    except PreflightError as error:
        report(f"STOP: preflight failed: {error}")
        report("CREATED_TABLES: none")
        return 2
    except mysql.connector.Error as error:
        # Connector messages can include connection/configuration details.
        code = getattr(error, "errno", None)
        safe_code = f" (error code {code})" if isinstance(code, int) else ""
        if created_tables:
            report("STOP: database operation failed" + safe_code)
            report("CREATED_TABLES: " + ", ".join(created_tables))
        else:
            report("STOP: database operation failed" + safe_code)
            report("CREATED_TABLES: none")
        if current_table is not None:
            report(f"FAILED_OR_UNCERTAIN_TABLE: {current_table}")
            report("Do not rerun until read-only metadata verification is reviewed.")
        return 3
    except Exception as error:
        # Do not emit exception text, which may contain SQL or connection details.
        if created_tables:
            report("STOP: verification or unexpected failure; no cleanup was attempted")
            report("CREATED_TABLES: " + ", ".join(created_tables))
        else:
            report("STOP: verification or unexpected failure before any table was confirmed")
            report("CREATED_TABLES: none")
        if current_table is not None:
            report(f"FAILED_OR_UNCERTAIN_TABLE: {current_table}")
        return 4
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
    sys.exit(main())
