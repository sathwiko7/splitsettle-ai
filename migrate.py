import sqlite3
from pathlib import Path


DB_PATH = Path("splitsettle.db")


def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()

    return any(row[1] == column_name for row in columns)


def add_column(cursor, table_name, column_name, definition):
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(
            f"ALTER TABLE {table_name} "
            f"ADD COLUMN {column_name} {definition}"
        )
        print(f"Added: {table_name}.{column_name}")
    else:
        print(f"Already exists: {table_name}.{column_name}")


def main():
    if not DB_PATH.exists():
        print("ERROR: splitsettle.db was not found.")
        return

    connection = sqlite3.connect(DB_PATH)
    cursor = connection.cursor()

    try:
        # AI RECOVERY FIELDS

        add_column(
            cursor,
            "settlement",
            "recovery_status",
            "TEXT DEFAULT 'none'"
        )

        add_column(
            cursor,
            "settlement",
            "recovery_option",
            "TEXT"
        )

        add_column(
            cursor,
            "settlement",
            "promised_amount",
            "REAL"
        )

        add_column(
            cursor,
            "settlement",
            "promised_date",
            "TEXT"
        )

        add_column(
            cursor,
            "settlement",
            "recovery_note",
            "TEXT"
        )

        # PAYMENT TRACKING FIELDS

        add_column(
            cursor,
            "settlement",
            "paid_amount",
            "REAL DEFAULT 0"
        )

        add_column(
            cursor,
            "settlement",
            "payment_link_amount",
            "REAL"
        )

        add_column(
            cursor,
            "settlement",
            "payment_link_paid",
            "INTEGER DEFAULT 0"
        )

        connection.commit()

        print()
        print("===================================")
        print("Database migration completed.")
        print("Existing data was preserved.")
        print("===================================")

    except Exception as exc:
        connection.rollback()

        print()
        print("===================================")
        print("DATABASE MIGRATION FAILED")
        print(f"Error: {exc}")
        print("No changes were committed.")
        print("===================================")

    finally:
        connection.close()


if __name__ == "__main__":
    main()