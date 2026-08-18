from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import psycopg
from psycopg.rows import dict_row
from pathlib import Path
from functools import wraps
from datetime import datetime
from urllib.parse import quote_plus
from io import BytesIO
import uuid
import os

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "property_marketplace.db"
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
USE_POSTGRES = bool(DATABASE_URL)
UPLOAD_FOLDER = BASE_DIR / "static" / "uploads"
UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "replace-this-with-a-long-random-secret-key")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024

PROPERTY_TYPES = [
    "Office",
    "Retail",
    "Warehouse",
    "Industrial",
    "Workshop",
    "Land",
    "Commercial Building",
    "Business Premises",
]

class PostgresResult:
    def __init__(self, cursor, lastrowid=None):
        self.cursor = cursor
        self.lastrowid = lastrowid

    def fetchone(self):
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()


class PostgresConnection:
    """
    Small compatibility wrapper so the rest of this beginner-friendly app
    can keep using ? placeholders and cursor.lastrowid.
    """

    def __init__(self, connection):
        self.connection = connection

    def _translate(self, sql):
        return sql.replace("?", "%s")

    def execute(self, sql, params=()):
        translated = self._translate(sql)
        stripped = sql.lstrip().upper()

        needs_id = (
            stripped.startswith("INSERT INTO USERS")
            or stripped.startswith("INSERT INTO PROPERTIES")
        )

        if needs_id and "RETURNING ID" not in stripped:
            translated = translated.rstrip().rstrip(";") + " RETURNING id"

            cursor = self.connection.execute(
                translated,
                params
            )

            row = cursor.fetchone()

            return PostgresResult(
                cursor,
                lastrowid=row["id"]
            )

        cursor = self.connection.execute(
            translated,
            params
        )

        return PostgresResult(cursor)

    def executescript(self, script):
        # PostgreSQL can execute this schema block in one call.
        self.connection.execute(script)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()


def get_db():
    if USE_POSTGRES:
        connection = psycopg.connect(
            DATABASE_URL,
            row_factory=dict_row,
            connect_timeout=10
        )

        return PostgresConnection(
            connection
        )

    conn = sqlite3.connect(
        DB_PATH,
        check_same_thread=False,
        timeout=30
    )

    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")

    return conn


def column_exists(conn, table_name, column_name):
    if USE_POSTGRES:
        row = conn.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
            AND table_name = ?
            AND column_name = ?
            LIMIT 1
            """,
            (
                table_name,
                column_name,
            ),
        ).fetchone()

        return row is not None

    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()

    return any(
        column["name"] == column_name
        for column in columns
    )


def run_migrations(conn):
    # Add the new phone fields to an existing database without deleting listings.
    if not column_exists(conn, "properties", "phone"):
        conn.execute("ALTER TABLE properties ADD COLUMN phone TEXT")

    if not column_exists(conn, "properties", "show_phone"):
        conn.execute(
            "ALTER TABLE properties "
            "ADD COLUMN show_phone INTEGER NOT NULL DEFAULT 1"
        )

    if not column_exists(conn, "properties", "price_on_application"):
        conn.execute(
            "ALTER TABLE properties "
            "ADD COLUMN price_on_application INTEGER NOT NULL DEFAULT 0"
        )

    if not column_exists(conn, "properties", "parking_comment"):
        conn.execute(
            "ALTER TABLE properties "
            "ADD COLUMN parking_comment TEXT"
        )

    if not column_exists(conn, "property_images", "sort_order"):
        conn.execute(
            "ALTER TABLE property_images "
            "ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
        )

        rows = conn.execute(
            "SELECT id, property_id FROM property_images ORDER BY property_id, id"
        ).fetchall()

        counters = {}

        for row in rows:
            property_id = row["property_id"]
            order_value = counters.get(property_id, 0)

            conn.execute(
                "UPDATE property_images SET sort_order = ? WHERE id = ?",
                (order_value, row["id"])
            )

            counters[property_id] = order_value + 1

    if not column_exists(conn, "property_images", "image_data"):
        if USE_POSTGRES:
            conn.execute(
                "ALTER TABLE property_images ADD COLUMN image_data BYTEA"
            )
        else:
            conn.execute(
                "ALTER TABLE property_images ADD COLUMN image_data BLOB"
            )

    if not column_exists(conn, "property_images", "mime_type"):
        conn.execute(
            "ALTER TABLE property_images ADD COLUMN mime_type TEXT"
        )

    conn.commit()

def init_db():
    conn = get_db()
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        user_type TEXT NOT NULL DEFAULT 'seeker',
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS properties (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        title TEXT NOT NULL,
        property_type TEXT NOT NULL,
        address TEXT NOT NULL,
        city TEXT NOT NULL,
        postcode TEXT NOT NULL,
        listing_type TEXT NOT NULL CHECK(listing_type IN ('Lease', 'Sale')),
        price REAL NOT NULL,
        price_on_application INTEGER NOT NULL DEFAULT 0,
        price_period TEXT NOT NULL,
        size_sqft REAL NOT NULL,
        parking INTEGER NOT NULL DEFAULT 0,
        parking_comment TEXT,
        phone TEXT,
        show_phone INTEGER NOT NULL DEFAULT 1,
        description TEXT NOT NULL,
        features TEXT,
        availability_date TEXT,
        views INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS property_images (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        image_data BLOB,
        mime_type TEXT,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS favourites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        property_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        UNIQUE(user_id, property_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        sender_id INTEGER,
        sender_name TEXT NOT NULL,
        sender_email TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id INTEGER NOT NULL,
        seeker_id INTEGER NOT NULL,
        advertiser_id INTEGER NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(property_id, seeker_id, advertiser_id),
        FOREIGN KEY (property_id) REFERENCES properties(id) ON DELETE CASCADE,
        FOREIGN KEY (seeker_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (advertiser_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS chat_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL,
        sender_id INTEGER NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
        FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """

    if USE_POSTGRES:
        schema = schema.replace(
            "INTEGER PRIMARY KEY AUTOINCREMENT",
            "SERIAL PRIMARY KEY"
        )
        schema = schema.replace(
            "image_data BLOB",
            "image_data BYTEA"
        )

    conn.executescript(schema)

    run_migrations(conn)

    # Remove only the built-in demo data.
    # Real users and their listings are left untouched.
    demo_user = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("demo@example.com",)
    ).fetchone()

    if demo_user:
        conn.execute(
            "DELETE FROM properties WHERE user_id = ?",
            (demo_user["id"],)
        )

        conn.execute(
            "DELETE FROM users WHERE id = ?",
            (demo_user["id"],)
        )

    conn.commit()
    conn.close()

def current_user():
    if "user_id" not in session:
        return None
    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()
    conn.close()
    return user

@app.context_processor
def inject_globals():
    return {
        "current_user": current_user(),
        "property_types": PROPERTY_TYPES,
    }

def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def maps_url_for_property(prop):
    # Search Google Maps using only the postcode, not the private street address.
    return (
        "https://www.google.com/maps/search/?api=1&query="
        + quote_plus(prop["postcode"])
    )


def property_image(property_id):
    conn = get_db()

    image = conn.execute(
        """
        SELECT id, filename, image_data
        FROM property_images
        WHERE property_id = ?
        ORDER BY sort_order, id
        LIMIT 1
        """,
        (property_id,),
    ).fetchone()

    conn.close()

    if image:
        if image["image_data"]:
            return url_for(
                "property_image_file",
                image_id=image["id"]
            )

        if image["filename"] != "placeholder":
            return url_for(
                "static",
                filename=f"uploads/{image['filename']}"
            )

    return (
        "https://images.unsplash.com/"
        "photo-1497366811353-6870744d04b2"
        "?auto=format&fit=crop&w=1200&q=80"
    )


@app.route("/property-image/<int:image_id>")
def property_image_file(image_id):
    conn = get_db()

    image = conn.execute(
        """
        SELECT image_data, mime_type
        FROM property_images
        WHERE id = ?
        """,
        (image_id,),
    ).fetchone()

    conn.close()

    if not image or not image["image_data"]:
        abort(404)

    return send_file(
        BytesIO(bytes(image["image_data"])),
        mimetype=image["mime_type"] or "image/jpeg",
        max_age=86400,
    )


@app.template_filter("money")
def money(value):
    return f"£{value:,.0f}"

@app.template_filter("property_price")
def property_price(prop):
    try:
        if prop["price_on_application"]:
            return "POA"
    except (KeyError, IndexError, TypeError):
        pass

    return f"£{prop['price']:,.0f}"


@app.template_filter("datefmt")
def datefmt(value):
    if not value:
        return "Not specified"
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value

@app.route("/health")
def health():
    database_name = (
        "PostgreSQL"
        if USE_POSTGRES
        else "SQLite"
    )

    return {
        "status": "ok",
        "database": database_name,
    }


@app.route("/")
def index():
    conn = get_db()

    featured = conn.execute("""
        SELECT p.*, COUNT(f.id) AS favourite_count
        FROM properties p
        LEFT JOIN favourites f ON f.property_id = p.id
        GROUP BY p.id
        ORDER BY favourite_count DESC, p.created_at DESC
        LIMIT 4
    """).fetchall()

    recent = conn.execute("""
        SELECT *
        FROM properties
        ORDER BY created_at DESC
        LIMIT 6
    """).fetchall()

    conn.close()

    return render_template(
        "index.html",
        featured=featured,
        recent=recent,
        image_url=property_image,
    )

@app.route("/search")
def search():
    clauses = []
    params = []

    location = request.args.get("location", "").strip()
    property_type = request.args.get("property_type", "").strip()
    listing_type = request.args.get("listing_type", "").strip()
    min_price = request.args.get("min_price", "").strip()
    max_price = request.args.get("max_price", "").strip()
    min_size = request.args.get("min_size", "").strip()
    max_size = request.args.get("max_size", "").strip()
    parking = request.args.get("parking", "").strip()
    sort = request.args.get("sort", "newest")

    if location:
        clauses.append("(city LIKE ? OR postcode LIKE ? OR address LIKE ?)")
        search_term = f"%{location}%"
        params.extend([search_term, search_term, search_term])

    if property_type:
        clauses.append("property_type = ?")
        params.append(property_type)

    if listing_type:
        clauses.append("listing_type = ?")
        params.append(listing_type)

    try:
        if min_price:
            clauses.append("price_on_application = 0")
            clauses.append("price >= ?")
            params.append(float(min_price))
        if max_price:
            clauses.append("price_on_application = 0")
            clauses.append("price <= ?")
            params.append(float(max_price))
        if min_size:
            clauses.append("size_sqft >= ?")
            params.append(float(min_size))
        if max_size:
            clauses.append("size_sqft <= ?")
            params.append(float(max_size))
        if parking:
            clauses.append("parking >= ?")
            params.append(int(parking))
    except ValueError:
        flash("One of the numeric filters was invalid.", "warning")

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    sort_options = {
        "newest": "created_at DESC",
        "price_low": "price_on_application ASC, price ASC",
        "price_high": "price_on_application ASC, price DESC",
        "size_large": "size_sqft DESC",
    }

    order_by = sort_options.get(sort, "created_at DESC")

    conn = get_db()
    properties = conn.execute(
        f"SELECT * FROM properties {where} ORDER BY {order_by}",
        params,
    ).fetchall()
    conn.close()

    return render_template(
        "search.html",
        properties=properties,
        image_url=property_image,
        filters=request.args,
    )

@app.route("/property/<int:property_id>", methods=["GET", "POST"])
def property_detail(property_id):
    conn = get_db()

    prop = conn.execute("""
        SELECT p.*, u.name AS advertiser_name, u.email AS advertiser_email
        FROM properties p
        LEFT JOIN users u ON u.id = p.user_id
        WHERE p.id = ?
    """, (property_id,)).fetchone()

    if not prop:
        conn.close()
        abort(404)

    if request.method == "POST":
        if "user_id" not in session:
            conn.close()
            flash("Please log in before messaging the advertiser.", "warning")
            return redirect(url_for("login", next=request.path))

        message = request.form.get("message", "").strip()

        if message:
            viewer_id = session["user_id"]
            advertiser_id = prop["user_id"]

            if not advertiser_id:
                conn.close()
                flash("This listing does not currently have an advertiser account.", "warning")
                return redirect(url_for("property_detail", property_id=property_id))

            if viewer_id == advertiser_id:
                conn.close()
                flash("This is your own property listing.", "info")
                return redirect(url_for("property_detail", property_id=property_id))

            conversation = conn.execute(
                """
                SELECT id
                FROM conversations
                WHERE property_id = ?
                  AND seeker_id = ?
                  AND advertiser_id = ?
                """,
                (
                    property_id,
                    viewer_id,
                    advertiser_id,
                ),
            ).fetchone()

            now = datetime.now().isoformat()

            if conversation:
                conversation_id = conversation["id"]
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO conversations
                    (
                        property_id,
                        seeker_id,
                        advertiser_id,
                        created_at,
                        updated_at
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        property_id,
                        viewer_id,
                        advertiser_id,
                        now,
                        now,
                    ),
                )
                conversation_id = cursor.lastrowid

            conn.execute(
                """
                INSERT INTO chat_messages
                (
                    conversation_id,
                    sender_id,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    viewer_id,
                    message,
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    conversation_id,
                ),
            )

            conn.commit()
            conn.close()

            return redirect(
                url_for(
                    "chat_conversation",
                    conversation_id=conversation_id
                )
            )

    if session.get("user_id") != prop["user_id"]:
        conn.execute(
            "UPDATE properties SET views = views + 1 WHERE id = ?",
            (property_id,),
        )
        conn.commit()

        prop = conn.execute("""
            SELECT p.*, u.name AS advertiser_name, u.email AS advertiser_email
            FROM properties p
            LEFT JOIN users u ON u.id = p.user_id
            WHERE p.id = ?
        """, (property_id,)).fetchone()

    images = conn.execute(
        """SELECT *
           FROM property_images
           WHERE property_id = ?
           ORDER BY sort_order, id""",
        (property_id,),
    ).fetchall()

    favourite = False

    if "user_id" in session:
        favourite = conn.execute(
            """SELECT 1
               FROM favourites
               WHERE user_id = ? AND property_id = ?""",
            (session["user_id"], property_id),
        ).fetchone() is not None

    conn.close()

    return render_template(
        "property.html",
        property=prop,
        images=images,
        favourite=favourite,
        image_url=property_image,
        maps_url=maps_url_for_property(prop),
    )

@app.route("/favourite/<int:property_id>", methods=["POST"])
@login_required
def toggle_favourite(property_id):
    conn = get_db()

    existing = conn.execute(
        """SELECT id
           FROM favourites
           WHERE user_id = ? AND property_id = ?""",
        (session["user_id"], property_id),
    ).fetchone()

    if existing:
        conn.execute(
            "DELETE FROM favourites WHERE id = ?",
            (existing["id"],),
        )
        flash("Property removed from favourites.", "info")
    else:
        conn.execute(
            """INSERT INTO favourites
               (user_id, property_id, created_at)
               VALUES (?, ?, ?)""",
            (
                session["user_id"],
                property_id,
                datetime.now().isoformat(),
            ),
        )
        flash("Property saved to favourites.", "success")

    conn.commit()
    conn.close()

    return redirect(request.referrer or url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user_type = request.form.get("user_type", "seeker")

        if user_type not in {"seeker", "advertiser"}:
            user_type = "seeker"

        if not name or not email or not password:
            flash("Please complete all required fields.", "danger")
            return render_template("register.html")

        conn = get_db()

        try:
            conn.execute(
                """INSERT INTO users
                   (name, email, password_hash, user_type, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    name,
                    email,
                    generate_password_hash(password),
                    user_type,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        except (sqlite3.IntegrityError, psycopg.IntegrityError):
            try:
                conn.rollback()
            except Exception:
                pass

            conn.close()
            flash("An account with that email already exists.", "danger")
            return render_template("register.html")

        conn.close()

        flash("Account created. You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,),
        ).fetchone()
        conn.close()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))

        flash("Incorrect email or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    listings = conn.execute("""
        SELECT p.*,
               (
                   SELECT COUNT(*)
                   FROM favourites f
                   WHERE f.property_id = p.id
               ) AS saved_count
        FROM properties p
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
    """, (session["user_id"],)).fetchall()

    favourites = conn.execute("""
        SELECT p.*
        FROM favourites f
        JOIN properties p ON p.id = f.property_id
        WHERE f.user_id = ?
        ORDER BY f.created_at DESC
    """, (session["user_id"],)).fetchall()

    conversations = conn.execute(
        """
        SELECT
            c.*,
            p.title,
            p.property_type,
            seeker.name AS seeker_name,
            advertiser.name AS advertiser_name,
            (
                SELECT cm.message
                FROM chat_messages cm
                WHERE cm.conversation_id = c.id
                ORDER BY cm.created_at DESC, cm.id DESC
                LIMIT 1
            ) AS last_message,
            (
                SELECT cm.created_at
                FROM chat_messages cm
                WHERE cm.conversation_id = c.id
                ORDER BY cm.created_at DESC, cm.id DESC
                LIMIT 1
            ) AS last_message_at
        FROM conversations c
        JOIN properties p ON p.id = c.property_id
        JOIN users seeker ON seeker.id = c.seeker_id
        JOIN users advertiser ON advertiser.id = c.advertiser_id
        WHERE c.seeker_id = ?
           OR c.advertiser_id = ?
        ORDER BY c.updated_at DESC
        """,
        (
            session["user_id"],
            session["user_id"],
        ),
    ).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        listings=listings,
        favourites=favourites,
        conversations=conversations,
        image_url=property_image,
    )

@app.route("/chat/<int:conversation_id>", methods=["GET", "POST"])
@login_required
def chat_conversation(conversation_id):
    conn = get_db()

    conversation = conn.execute(
        """
        SELECT
            c.*,
            p.title,
            p.property_type,
            p.city,
            p.postcode,
            seeker.name AS seeker_name,
            advertiser.name AS advertiser_name
        FROM conversations c
        JOIN properties p ON p.id = c.property_id
        JOIN users seeker ON seeker.id = c.seeker_id
        JOIN users advertiser ON advertiser.id = c.advertiser_id
        WHERE c.id = ?
        """,
        (conversation_id,),
    ).fetchone()

    if not conversation:
        conn.close()
        abort(404)

    if session["user_id"] not in {
        conversation["seeker_id"],
        conversation["advertiser_id"],
    }:
        conn.close()
        abort(403)

    if request.method == "POST":
        message = request.form.get("message", "").strip()

        if message:
            now = datetime.now().isoformat()

            conn.execute(
                """
                INSERT INTO chat_messages
                (
                    conversation_id,
                    sender_id,
                    message,
                    created_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    conversation_id,
                    session["user_id"],
                    message,
                    now,
                ),
            )

            conn.execute(
                """
                UPDATE conversations
                SET updated_at = ?
                WHERE id = ?
                """,
                (
                    now,
                    conversation_id,
                ),
            )

            conn.commit()

        conn.close()

        return redirect(
            url_for(
                "chat_conversation",
                conversation_id=conversation_id
            )
        )

    chat_messages = conn.execute(
        """
        SELECT
            cm.*,
            u.name AS sender_name
        FROM chat_messages cm
        JOIN users u ON u.id = cm.sender_id
        WHERE cm.conversation_id = ?
        ORDER BY cm.created_at ASC, cm.id ASC
        """,
        (conversation_id,),
    ).fetchall()

    conn.close()

    other_name = (
        conversation["advertiser_name"]
        if session["user_id"] == conversation["seeker_id"]
        else conversation["seeker_name"]
    )

    return render_template(
        "chat.html",
        conversation=conversation,
        chat_messages=chat_messages,
        other_name=other_name,
    )


def get_property(property_id):
    conn = get_db()
    prop = conn.execute(
        "SELECT * FROM properties WHERE id = ?",
        (property_id,),
    ).fetchone()
    conn.close()
    return prop

def save_property(property_id=None):
    form = request.form

    required = [
        "title",
        "property_type",
        "address",
        "city",
        "postcode",
        "listing_type",
        "price_period",
        "size_sqft",
        "description",
    ]

    if any(not form.get(field, "").strip() for field in required):
        flash("Please complete all required fields.", "danger")
        return render_template(
            "advertise.html",
            property=get_property(property_id) if property_id else None,
        )

    price_on_application = (
        1 if form.get("price_on_application") == "1" else 0
    )

    try:
        if price_on_application:
            price = 0.0
        else:
            if not form.get("price", "").strip():
                raise ValueError
            price = float(form["price"])

        size_sqft = float(form["size_sqft"])
        parking = int(form.get("parking", 0) or 0)

    except ValueError:
        flash(
            "Enter a valid price, size and parking number, "
            "or choose POA for the price.",
            "danger"
        )
        return render_template(
            "advertise.html",
            property=get_property(property_id) if property_id else None,
        )

    values = (
        form["title"].strip(),
        form["property_type"],
        form["address"].strip(),
        form["city"].strip(),
        form["postcode"].strip(),
        form["listing_type"],
        price,
        price_on_application,
        form["price_period"],
        size_sqft,
        parking,
        form.get("parking_comment", "").strip(),
        form.get("phone", "").strip(),
        1 if form.get("show_phone") == "1" else 0,
        form["description"].strip(),
        form.get("features", "").strip(),
        form.get("availability_date") or None,
    )

    conn = get_db()

    if property_id is None:
        cursor = conn.execute(
            """INSERT INTO properties
            (user_id, title, property_type, address, city, postcode,
             listing_type, price, price_on_application, price_period,
             size_sqft, parking, parking_comment, phone, show_phone,
             description, features, availability_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session["user_id"],
                *values,
                datetime.now().isoformat(),
            ),
        )
        property_id = cursor.lastrowid
        flash("Your property has been advertised.", "success")
    else:
        owner = conn.execute(
            "SELECT user_id FROM properties WHERE id = ?",
            (property_id,),
        ).fetchone()

        if not owner or owner["user_id"] != session["user_id"]:
            conn.close()
            abort(403)

        conn.execute(
            """UPDATE properties
               SET title = ?,
                   property_type = ?,
                   address = ?,
                   city = ?,
                   postcode = ?,
                   listing_type = ?,
                   price = ?,
                   price_on_application = ?,
                   price_period = ?,
                   size_sqft = ?,
                   parking = ?,
                   parking_comment = ?,
                   phone = ?,
                   show_phone = ?,
                   description = ?,
                   features = ?,
                   availability_date = ?
               WHERE id = ?""",
            (*values, property_id),
        )

        flash("Your property has been updated.", "success")

    # -------------------------------------------------
    # PHOTO MANAGER
    # -------------------------------------------------

    deleted_ids = []

    for item in form.get("deleted_photo_ids", "").split(","):
        item = item.strip()

        if item.isdigit():
            deleted_ids.append(int(item))

    if deleted_ids:
        placeholders = ",".join("?" for _ in deleted_ids)

        rows_to_delete = conn.execute(
            f"""
            SELECT id, filename
            FROM property_images
            WHERE property_id = ?
            AND id IN ({placeholders})
            """,
            (property_id, *deleted_ids),
        ).fetchall()

        for row in rows_to_delete:
            if row["filename"] != "placeholder":
                try:
                    (UPLOAD_FOLDER / row["filename"]).unlink(
                        missing_ok=True
                    )
                except OSError:
                    pass

        conn.execute(
            f"""
            DELETE FROM property_images
            WHERE property_id = ?
            AND id IN ({placeholders})
            """,
            (property_id, *deleted_ids),
        )

    uploaded_files = request.files.getlist("photos")

    new_photo_ids = [
        item.strip()
        for item in form.get("new_photo_ids", "").split(",")
        if item.strip()
    ]

    new_files_by_id = {}

    for index, photo in enumerate(uploaded_files):
        if (
            photo
            and photo.filename
            and allowed_file(photo.filename)
        ):
            token = (
                new_photo_ids[index]
                if index < len(new_photo_ids)
                else f"fallback-{index}"
            )

            extension = photo.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{extension}"

            image_bytes = photo.read()
            mime_type = photo.mimetype or "image/jpeg"

            new_files_by_id[token] = {
                "filename": filename,
                "image_data": image_bytes,
                "mime_type": mime_type,
            }

    order_tokens = [
        token.strip()
        for token in form.get("photo_order", "").split(",")
        if token.strip()
    ]

    order_value = 0
    used_new_tokens = set()

    for token in order_tokens:
        if token.startswith("existing:"):
            image_id = token.split(":", 1)[1]

            if image_id.isdigit():
                conn.execute(
                    """
                    UPDATE property_images
                    SET sort_order = ?
                    WHERE id = ?
                    AND property_id = ?
                    """,
                    (
                        order_value,
                        int(image_id),
                        property_id,
                    ),
                )

                order_value += 1

        elif token.startswith("new:"):
            new_token = token.split(":", 1)[1]

            if (
                new_token in new_files_by_id
                and new_token not in used_new_tokens
            ):
                file_info = new_files_by_id[new_token]

                conn.execute(
                    """
                    INSERT INTO property_images
                    (
                        property_id,
                        filename,
                        sort_order,
                        image_data,
                        mime_type
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        property_id,
                        file_info["filename"],
                        order_value,
                        file_info["image_data"],
                        file_info["mime_type"],
                    ),
                )

                used_new_tokens.add(new_token)
                order_value += 1

    # Save any new images that were not present in the submitted order.
    for new_token, file_info in new_files_by_id.items():
        if new_token not in used_new_tokens:
            conn.execute(
                """
                INSERT INTO property_images
                (
                    property_id,
                    filename,
                    sort_order,
                    image_data,
                    mime_type
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    property_id,
                    file_info["filename"],
                    order_value,
                    file_info["image_data"],
                    file_info["mime_type"],
                ),
            )

            order_value += 1

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/advertise", methods=["GET", "POST"])
@login_required
def advertise():
    if request.method == "POST":
        return save_property()
    return render_template(
        "advertise.html",
        property=None,
        existing_images=[]
    )

@app.route("/edit/<int:property_id>", methods=["GET", "POST"])
@login_required
def edit_property(property_id):
    prop = get_property(property_id)

    if not prop or prop["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "POST":
        return save_property(property_id)

    conn = get_db()

    existing_images = conn.execute(
        """
        SELECT *
        FROM property_images
        WHERE property_id = ?
        ORDER BY sort_order, id
        """,
        (property_id,),
    ).fetchall()

    conn.close()

    return render_template(
        "advertise.html",
        property=prop,
        existing_images=existing_images
    )

@app.route("/delete/<int:property_id>", methods=["POST"])
@login_required
def delete_property(property_id):
    conn = get_db()

    prop = conn.execute(
        """SELECT *
           FROM properties
           WHERE id = ? AND user_id = ?""",
        (property_id, session["user_id"]),
    ).fetchone()

    if not prop:
        conn.close()
        abort(403)

    images = conn.execute(
        "SELECT filename FROM property_images WHERE property_id = ?",
        (property_id,),
    ).fetchall()

    for image in images:
        if image["filename"] != "placeholder":
            try:
                (UPLOAD_FOLDER / image["filename"]).unlink(missing_ok=True)
            except OSError:
                pass

    conn.execute(
        "DELETE FROM properties WHERE id = ?",
        (property_id,),
    )

    conn.commit()
    conn.close()

    flash("Listing deleted.", "info")
    return redirect(url_for("dashboard"))

# Initialise the database when Render/Gunicorn imports this module.
init_db()


if __name__ == "__main__":
    app.run(debug=True)
