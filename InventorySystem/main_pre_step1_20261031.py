import tkinter as tk
from tkinter import ttk
import os
import bcrypt
import mysql.connector
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# DATABASE CONNECTION
# -----------------------------

def connect_to_database():
    try:
        connection = mysql.connector.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "inventory_system")
        )
        return connection

    except (mysql.connector.Error, ValueError):
        return None


# -----------------------------
# REGISTER USER
# -----------------------------

def register_user(username, password, role):
    if not username.strip() or not password:
        return False, "Username and password are required."

    if role not in ("Admin", "Super Admin", "Staff"):
        return False, "Invalid user role."

    connection = connect_to_database()

    if connection is None:
        return False, "Could not connect to the database."

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
    connection = connect_to_database()

    if connection is None:
        return None, "Could not connect to the database."

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
# ROLE DASHBOARD
# -----------------------------

def open_dashboard(username, role):
    dashboard = tk.Toplevel()
    dashboard.title("TambayanTea.ph - Dashboard")
    dashboard.geometry("650x450")
    dashboard.resizable(False, False)
    dashboard.configure(bg="#F8F1E7")

    tk.Label(
        dashboard,
        text="TambayanTea.ph",
        font=("Arial", 24, "bold"),
        bg="#F8F1E7",
        fg="#70452B"
    ).pack(pady=(35, 10))

    tk.Label(
        dashboard,
        text=f"Welcome, {username}!",
        font=("Arial", 16, "bold"),
        bg="#F8F1E7",
        fg="#70452B"
    ).pack(pady=5)

    tk.Label(
        dashboard,
        text=f"Role: {role}",
        font=("Arial", 12),
        bg="#F8F1E7",
        fg="#70452B"
    ).pack(pady=5)

    tk.Label(
        dashboard,
        text="Your dashboard is ready.",
        font=("Arial", 11),
        bg="#F8F1E7",
        fg="#26733D"
    ).pack(pady=15)

    tk.Label(
        dashboard,
        text="Inventory, sales, and reports will be added here.",
        font=("Arial", 10),
        bg="#F8F1E7",
        fg="#70452B"
    ).pack(pady=5)

    def logout():
        dashboard.destroy()
        root.deiconify()
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        message.config(text="", fg="red")

    tk.Button(
        dashboard,
        text="LOG OUT",
        command=logout,
        font=("Arial", 11, "bold"),
        bg="#70452B",
        fg="white",
        activebackground="#8C5A3C",
        activeforeground="white",
        width=18,
        cursor="hand2"
    ).pack(pady=25)

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