import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def get_db_connection():
    try:
        with psycopg.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            connect_timeout=5
        ) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user;")
                result = cur.fetchone()
                if result is not None:
                    print("Database connection successful.")
                else:
                    print("Database connection failed.")

    except Exception as e:
        print(f"Error connecting to the database: {e}")

if __name__ == "__main__":
    get_db_connection()
            