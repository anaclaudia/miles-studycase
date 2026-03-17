import os
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv()  # loads variables from .env into os.environ

app = Flask(__name__)

# --- DB config from environment variables ---
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "webapp_db"),
    "user":     os.getenv("DB_USER", "test"),
    "password": os.getenv("DB_PASSWORD", "test"),
}

USERNAMES = [
    "alice", "bob", "charlie", "diana", "eve",
    "frank", "grace", "hank", "ivy", "jack","jenny","joão",
    "Pedro", "Clarisse", "Bjorn"
]

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Create the users table and seed usernames if empty."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE
                );
            """)
            # Seed only if the table is empty
            cur.execute("SELECT COUNT(*) FROM users;")
            if cur.fetchone()[0] == 0:
                cur.executemany(
                    "INSERT INTO users (username) VALUES (%s) ON CONFLICT DO NOTHING;",
                    [(u,) for u in USERNAMES],
                )
        conn.commit()

def pick_random_username():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT username FROM users ORDER BY RANDOM() LIMIT 1;")
            row = cur.fetchone()
            return row[0] if row else "stranger"

# --- Routes ---

@app.route("/")
def index():
    username = pick_random_username()
    return f"<h1>Welcome to the Miles DevOps Case Study {username}</h1>"

@app.route("/healthcheck")
def healthcheck():
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
        return jsonify(status="ok", database="reachable"), 200
    except Exception as e:
        return jsonify(status="error", database="unreachable", detail=str(e)), 503

# --- Entry point ---

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000)