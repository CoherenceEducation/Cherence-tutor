import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env file

def get_db_connection():
    """Connect to the MySQL database."""
    try:
        connection = mysql.connector.connect(
            host=os.getenv("DB_HOST"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            database=os.getenv("DB_NAME"),
            port=int(os.getenv("DB_PORT", 3306))
        )
        if connection.is_connected():
            print("✅ Database connected successfully")
        return connection
    except Error as e:
        print(f"Database connection error: {e}")
        return None

def main():
    conn = get_db_connection()
    if conn:
        cursor = conn.cursor()
        cursor.execute("SELECT NOW();")
        result = cursor.fetchone()
        print("🕒 Current DB time:", result[0])
        cursor.close()
        conn.close()
    else:
        print("❌ Database connection failed.")

if __name__ == "__main__":
    main()