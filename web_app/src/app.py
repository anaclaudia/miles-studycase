import os
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv("/app/.env")  # explicit path — works regardless of cwd

app = Flask(__name__)

# --- DB config from environment variables ---
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "devops_db"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

USERNAMES = [
    "alice", "bob", "charlie", "diana", "eve",
    "frank", "grace", "hank", "ivy", "jack",
]

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Create the users table and sync USERNAMES list into it.

    New names are inserted, removed names are left untouched so that
    historical data is preserved.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE
                );
            """)
            # Insert only names that are not already in the table
            cur.executemany(
                "INSERT INTO users (username) VALUES (%s) ON CONFLICT (username) DO NOTHING;",
                [(u,) for u in USERNAMES],
            )
            cur.execute("SELECT COUNT(*) FROM users WHERE username = ANY(%s);", (USERNAMES,))
            inserted = len(USERNAMES) - cur.fetchone()[0]
        conn.commit()
    if inserted:
        print(f"[init_db] inserted {inserted} new username(s) into the database.")

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
    app.run(host="0.0.0.0", port=5000)import os
import psycopg2
from dotenv import load_dotenv
from flask import Flask, jsonify

load_dotenv("/app/.env")  # explicit path — works regardless of cwd

app = Flask(__name__)

# --- DB config from environment variables ---
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     os.getenv("DB_PORT", "5432"),
    "dbname":   os.getenv("DB_NAME", "devops_db"),
    "user":     os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}

USERNAMES = [
    "alice", "bob", "charlie", "diana", "Eve", "Clarisse", "João"
    "frank", "grace", "hank", "ivy", "jack", "Jenny"
]

def get_conn():
    return psycopg2.connect(**DB_CONFIG)

def init_db():
    """Create the users table and sync USERNAMES list into it.

    New names are inserted, removed names are left untouched so that
    historical data is preserved.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(100) NOT NULL UNIQUE
                );
            """)
            # Insert only names that are not already in the table
            cur.executemany(
                "INSERT INTO users (username) VALUES (%s) ON CONFLICT (username) DO NOTHING;",
                [(u,) for u in USERNAMES],
            )
            cur.execute("SELECT COUNT(*) FROM users WHERE username = ANY(%s);", (USERNAMES,))
            inserted = len(USERNAMES) - cur.fetchone()[0]
        conn.commit()
    if inserted:
        print(f"[init_db] inserted {inserted} new username(s) into the database.")

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