import os, re, secrets, sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash, session, abort
from werkzeug.utils import secure_filename
from twilio.rest import Client

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = BASE_DIR / "news.db"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
ADMIN_PHONE = os.getenv("ADMIN_PHONE", "+919454102368")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "change-this-before-deploying")
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "false").lower() == "true",
)

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'मुख्य समाचार',
                summary TEXT NOT NULL DEFAULT '',
                body TEXT NOT NULL,
                image TEXT,
                created_at TEXT NOT NULL
            )
        """)

init_db()

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def twilio_client():
    sid = os.getenv("TWILIO_ACCOUNT_SID")
    token = os.getenv("TWILIO_AUTH_TOKEN")
    if not sid or not token:
        raise RuntimeError("TWILIO_ACCOUNT_SID और TWILIO_AUTH_TOKEN सेट नहीं हैं।")
    return Client(sid, token)

def verify_sid():
    sid = os.getenv("TWILIO_VERIFY_SERVICE_SID")
    if not sid:
        raise RuntimeError("TWILIO_VERIFY_SERVICE_SID सेट नहीं है।")
    return sid

def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route("/")
def index():
    q = request.args.get("q", "").strip()
    with db() as conn:
        if q:
            rows = conn.execute(
                "SELECT * FROM news WHERE title LIKE ? OR summary LIKE ? OR body LIKE ? ORDER BY id DESC",
                (f"%{q}%", f"%{q}%", f"%{q}%")
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    return render_template("index.html", news=rows, q=q)

@app.route("/news/<int:news_id>")
def article(news_id):
    with db() as conn:
        item = conn.execute("SELECT * FROM news WHERE id=?", (news_id,)).fetchone()
    if not item:
        abort(404)
    return render_template("article.html", item=item)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        phone = re.sub(r"\s+", "", request.form.get("phone", ""))
        if phone != ADMIN_PHONE:
            flash("यह नंबर अधिकृत नहीं है। केवल अधिकृत एडमिन लॉगिन कर सकता है।", "danger")
            return redirect(url_for("login"))
        try:
            twilio_client().verify.v2.services(verify_sid()).verifications.create(
                to=ADMIN_PHONE, channel="sms"
            )
            session["pending_admin"] = True
            flash("OTP भेज दिया गया है।", "success")
            return redirect(url_for("verify_otp"))
        except Exception as exc:
            app.logger.exception("OTP send failed")
            flash("OTP नहीं भेजा जा सका। Twilio की सेटिंग जाँचें।", "danger")
            return redirect(url_for("login"))
    return render_template("login.html")

@app.route("/verify-otp", methods=["GET", "POST"])
def verify_otp():
    if not session.get("pending_admin"):
        return redirect(url_for("login"))
    if request.method == "POST":
        code = request.form.get("code", "").strip()
        try:
            result = twilio_client().verify.v2.services(verify_sid()).verification_checks.create(
                to=ADMIN_PHONE, code=code
            )
            if result.status == "approved":
                session.clear()
                session["is_admin"] = True
                session["csrf_token"] = secrets.token_urlsafe(24)
                return redirect(url_for("dashboard"))
            flash("गलत या समाप्त OTP। दोबारा प्रयास करें।", "danger")
        except Exception:
            app.logger.exception("OTP check failed")
            flash("OTP सत्यापन विफल हुआ।", "danger")
    return render_template("verify.html")

@app.route("/logout", methods=["POST"])
@admin_required
def logout():
    session.clear()
    flash("आप लॉगआउट हो गए हैं।", "info")
    return redirect(url_for("index"))

def check_csrf():
    if request.form.get("csrf_token") != session.get("csrf_token"):
        abort(400, "Invalid request token")

@app.route("/admin")
@admin_required
def dashboard():
    with db() as conn:
        rows = conn.execute("SELECT * FROM news ORDER BY id DESC").fetchall()
    return render_template("dashboard.html", news=rows)

@app.route("/admin/news/new", methods=["GET", "POST"])
@admin_required
def new_news():
    if request.method == "POST":
        check_csrf()
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()
        summary = request.form.get("summary", "").strip()
        category = request.form.get("category", "मुख्य समाचार").strip() or "मुख्य समाचार"
        if not title or not body:
            flash("शीर्षक और समाचार विवरण आवश्यक हैं।", "danger")
            return render_template("news_form.html", item=None)
        image_name = None
        upload = request.files.get("image")
        if upload and upload.filename:
            if not allowed_file(upload.filename):
                flash("केवल JPG, PNG या WEBP इमेज अपलोड करें।", "danger")
                return render_template("news_form.html", item=None)
            image_name = f"{secrets.token_hex(8)}_{secure_filename(upload.filename)}"
            upload.save(UPLOAD_DIR / image_name)
        with db() as conn:
            conn.execute(
                "INSERT INTO news(title,category,summary,body,image,created_at) VALUES(?,?,?,?,?,?)",
                (title, category, summary, body, image_name, datetime.now().strftime("%d-%m-%Y %H:%M"))
            )
        flash("समाचार सफलतापूर्वक प्रकाशित हुआ।", "success")
        return redirect(url_for("dashboard"))
    return render_template("news_form.html", item=None)

@app.route("/admin/news/<int:news_id>/delete", methods=["POST"])
@admin_required
def delete_news(news_id):
    check_csrf()
    with db() as conn:
        row = conn.execute("SELECT image FROM news WHERE id=?", (news_id,)).fetchone()
        conn.execute("DELETE FROM news WHERE id=?", (news_id,))
    if row and row["image"]:
        try:
            (UPLOAD_DIR / row["image"]).unlink(missing_ok=True)
        except OSError:
            pass
    flash("समाचार हटाया गया।", "info")
    return redirect(url_for("dashboard"))

@app.errorhandler(413)
def too_large(_):
    return "इमेज 5 MB से छोटी होनी चाहिए।", 413

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=False)
