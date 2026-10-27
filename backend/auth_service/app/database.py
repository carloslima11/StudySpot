import psycopg2  # pyright: ignore[reportMissingModuleSource]

def get_db_connection():
    try:
        connection = psycopg2.connect(
            host="localhost",
            database="studyspot",
            user="postgres",
            password="admin1234",
        )

        print("Database connection established.")
        return connection
    except psycopg2.Error as e:
        print(f"Error connecting to the database: {e}")
        return None

    if __name__ == "__main__":
        conn = get_db_connection()
        if conn:
            conn.close()
            print("Database connection closed.")