from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path
from functools import wraps
from datetime import datetime
from urllib.parse import quote_plus
import uuid
import os

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "property_marketplace.db"
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

def get_db():
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
    columns = conn.execute(
        f"PRAGMA table_info({table_name})"
    ).fetchall()
    return any(column["name"] == column_name for column in columns)


def run_migrations(conn):
    # Add the new phone fields to an existing database without deleting listings.
    if not column_exists(conn, "properties", "phone"):
        conn.execute("ALTER TABLE properties ADD COLUMN phone TEXT")

    if not column_exists(conn, "properties", "show_phone"):
        conn.execute(
            "ALTER TABLE properties "
            "ADD COLUMN show_phone INTEGER NOT NULL DEFAULT 1"
        )

    conn.commit()

def init_db():
    conn = get_db()
    conn.executescript("""
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
        price_period TEXT NOT NULL,
        size_sqft REAL NOT NULL,
        parking INTEGER NOT NULL DEFAULT 0,
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
    """)

    run_migrations(conn)

    demo = conn.execute(
        "SELECT id FROM users WHERE email = ?",
        ("demo@example.com",)
    ).fetchone()

    if not demo:
        cursor = conn.execute(
            """INSERT INTO users
               (name, email, password_hash, user_type, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                "Demo Property Group",
                "demo@example.com",
                generate_password_hash("demo123"),
                "advertiser",
                datetime.now().isoformat(),
            ),
        )
        demo_id = cursor.lastrowid

        sample_properties = [
            (
                "Modern Office Building – Nottingham City Centre",
                "Office",
                "18 High Pavement",
                "Nottingham",
                "NG1 2JS",
                "Lease",
                3250,
                "per month",
                4200,
                12,
                "A bright, modern open-plan office building in Nottingham city centre. "
                "The property includes meeting rooms, kitchen facilities, secure access "
                "and excellent transport connections.",
                "Open-plan workspace, Meeting rooms, Reception, Kitchen, Secure entry, Lift access, Air conditioning",
                "2026-09-01",
            ),
            (
                "5,000 sq ft Warehouse – Derby",
                "Warehouse",
                "42 Pride Park Way",
                "Derby",
                "DE24 8HJ",
                "Lease",
                48000,
                "per year",
                5000,
                14,
                "A well-positioned warehouse with loading access, yard space and excellent "
                "road links. Suitable for storage, logistics or distribution.",
                "Loading doors, Secure yard, Offices, Staff room, LED lighting, Three-phase power",
                "2026-10-01",
            ),
            (
                "Retail Unit – Leicester High Street",
                "Retail",
                "107 High Street",
                "Leicester",
                "LE1 4FY",
                "Lease",
                29500,
                "per year",
                1850,
                2,
                "A prominent retail premises in a busy city-centre location with strong "
                "pedestrian traffic, large display windows and rear delivery access.",
                "Large frontage, Display windows, Storage, Staff WC, Rear delivery access",
                "2026-09-15",
            ),
            (
                "Industrial Workshop – Nottingham",
                "Workshop",
                "7 Colwick Industrial Estate",
                "Nottingham",
                "NG4 2BA",
                "Sale",
                395000,
                "total",
                6200,
                18,
                "A versatile industrial workshop and trade unit suitable for engineering, "
                "storage or light manufacturing, with office space and a secure yard.",
                "Workshop floor, Offices, Roller shutter, Parking, Secure yard, Three-phase power",
                "2026-11-01",
            ),
        ]

        for item in sample_properties:
            cursor = conn.execute(
                """INSERT INTO properties
                (user_id, title, property_type, address, city, postcode,
                 listing_type, price, price_period, size_sqft, parking,
                 description, features, availability_date, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (demo_id, *item, datetime.now().isoformat()),
            )
            conn.execute(
                "INSERT INTO property_images (property_id, filename) VALUES (?, ?)",
                (cursor.lastrowid, "placeholder"),
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
        """SELECT filename
           FROM property_images
           WHERE property_id = ?
           ORDER BY id
           LIMIT 1""",
        (property_id,),
    ).fetchone()
    conn.close()

    if image and image["filename"] != "placeholder":
        return url_for("static", filename=f"uploads/{image['filename']}")

    return "https://images.unsplash.com/photo-1497366811353-6870744d04b2?auto=format&fit=crop&w=1200&q=80"

@app.template_filter("money")
def money(value):
    return f"£{value:,.0f}"

@app.template_filter("datefmt")
def datefmt(value):
    if not value:
        return "Not specified"
    try:
        return datetime.fromisoformat(value).strftime("%d %b %Y")
    except ValueError:
        return value

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
            clauses.append("price >= ?")
            params.append(float(min_price))
        if max_price:
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
        "price_low": "price ASC",
        "price_high": "price DESC",
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
            flash("Please log in before sending an enquiry.", "warning")
            return redirect(url_for("login", next=request.path))

        message = request.form.get("message", "").strip()

        if message:
            user = current_user()
            conn.execute(
                """INSERT INTO messages
                   (property_id, sender_id, sender_name, sender_email, message, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    property_id,
                    user["id"],
                    user["name"],
                    user["email"],
                    message,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
            flash("Your enquiry has been sent.", "success")
            return redirect(url_for("property_detail", property_id=property_id))

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
           ORDER BY id""",
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
        except sqlite3.IntegrityError:
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

    messages = conn.execute("""
        SELECT m.*, p.title
        FROM messages m
        JOIN properties p ON p.id = m.property_id
        WHERE p.user_id = ?
        ORDER BY m.created_at DESC
        LIMIT 10
    """, (session["user_id"],)).fetchall()

    conn.close()

    return render_template(
        "dashboard.html",
        listings=listings,
        favourites=favourites,
        messages=messages,
        image_url=property_image,
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
        "price",
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

    try:
        price = float(form["price"])
        size_sqft = float(form["size_sqft"])
        parking = int(form.get("parking", 0) or 0)
    except ValueError:
        flash("Price, size and parking must contain valid numbers.", "danger")
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
        form["price_period"],
        size_sqft,
        parking,
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
             listing_type, price, price_period, size_sqft, parking,
             phone, show_phone, description, features,
             availability_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                   price_period = ?,
                   size_sqft = ?,
                   parking = ?,
                   phone = ?,
                   show_phone = ?,
                   description = ?,
                   features = ?,
                   availability_date = ?
               WHERE id = ?""",
            (*values, property_id),
        )

        flash("Your property has been updated.", "success")

    photos = request.files.getlist("photos")

    for photo in photos:
        if photo and photo.filename and allowed_file(photo.filename):
            extension = photo.filename.rsplit(".", 1)[1].lower()
            filename = f"{uuid.uuid4().hex}.{extension}"
            photo.save(UPLOAD_FOLDER / filename)

            conn.execute(
                """INSERT INTO property_images
                   (property_id, filename)
                   VALUES (?, ?)""",
                (property_id, filename),
            )

    conn.commit()
    conn.close()

    return redirect(url_for("dashboard"))

@app.route("/advertise", methods=["GET", "POST"])
@login_required
def advertise():
    if request.method == "POST":
        return save_property()
    return render_template("advertise.html", property=None)

@app.route("/edit/<int:property_id>", methods=["GET", "POST"])
@login_required
def edit_property(property_id):
    prop = get_property(property_id)

    if not prop or prop["user_id"] != session["user_id"]:
        abort(403)

    if request.method == "POST":
        return save_property(property_id)

    return render_template("advertise.html", property=prop)

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
