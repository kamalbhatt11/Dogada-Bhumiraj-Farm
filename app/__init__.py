from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from pathlib import Path
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
login_manager.login_view = "admin.login"


def request_is_https():
    return request.is_secure or request.headers.get("X-Forwarded-Proto", "").lower() == "https"


def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if not app.config.get("SECRET_KEY"):
        raise RuntimeError("A strong SECRET_KEY environment variable is required in production.")
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_PROTECTION"] = "strong"
    # Render terminates HTTPS at its proxy. Trust one proxy hop for client IP/scheme.
    if app.config.get("IS_PRODUCTION"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1)
    csrf.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(self), camera=(), microphone=()")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; base-uri 'self'; object-src 'none'; "
            "frame-ancestors 'none'; form-action 'self'; "
            "img-src 'self' data: https:; font-src 'self' data: https://fonts.gstatic.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
            "script-src 'self' 'unsafe-inline' https://unpkg.com; "
            "connect-src 'self' https://router.project-osrm.org"
        )
        if request.path.startswith(("/owner/", "/dairy/")) or request.path in {"/data-rights"} or request.path.startswith("/order-success/"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        if request_is_https():
            response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        return response

    @app.errorhandler(500)
    def internal_server_error(error):
        app.logger.error("Unhandled server error", exc_info=(type(error), error, error.__traceback__))
        from flask import render_template
        return render_template("500.html"), 500

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    app.jinja_env.filters["fromjson"] = lambda v: __import__("json").loads(v)

    from .routes import main, admin
    from .dairy_routes import dairy
    app.register_blueprint(dairy)
    app.register_blueprint(main)
    app.register_blueprint(admin, url_prefix="/owner")

    with app.app_context():
        from .models import Product, Admin, Animal, Vaccination, LoginAttempt
        from . import dairy_models

        db.create_all()
        seed()

    return app


def seed():
    from .models import Product, Admin
    from werkzeug.security import generate_password_hash
    import os

    # Create products if database is empty
    if not Product.query.first():
        data = [
            ("Cow Milk", "cow-milk", 80, "liter", "Dairy", "Fresh local cow milk.", "🥛"),
            ("Buffalo Milk", "buffalo-milk", 90, "liter", "Dairy", "Rich and creamy buffalo milk.", "🥛"),
            ("Dahi", "dahi", 120, "kg", "Dairy", "Fresh traditional yogurt.", "🥣"),
            ("Mahi", "mahi", 70, "liter", "Dairy", "Refreshing traditional dairy drink.", "🥤"),
            ("Paneer", "paneer", 700, "kg", "Dairy", "Fresh paneer made from quality milk.", "🧀"),
            ("Ghee", "ghee", 1000, "kg", "Dairy", "Rich dairy ghee.", "🫙"),
            ("Cow", "cow", None, "on request", "Livestock",
             "Healthy cows. Ask about breed, age, availability and price.", "🐄"),
            ("Buffalo", "buffalo", None, "on request", "Livestock",
             "Buffalo available based on current stock.", "🐃"),
            ("Calf", "calf", None, "on request", "Livestock",
             "Calves available based on current stock.", "🐮")
        ]

        db.session.add_all([
            Product(
                name=a,
                slug=b,
                price=c,
                unit=d,
                category=e,
                description=f,
                icon=g
            )
            for a, b, c, d, e, f, g in data
        ])

        db.session.commit()

    # Always get the owner AFTER the database has been initialized
    owner = Admin.query.filter_by(username="owner").first()

    # Temporary password reset
    reset_password = os.environ.get("RESET_OWNER_PASSWORD")

    if reset_password and len(reset_password) >= 12:
        if owner:
            owner.password_hash = generate_password_hash(reset_password)
        else:
            owner = Admin(
                username="owner",
                password_hash=generate_password_hash(reset_password)
            )
            db.session.add(owner)

        db.session.commit()

    # Create owner on first deployment
    elif not owner:
        password = os.environ.get("INITIAL_OWNER_PASSWORD")

        if password and len(password) >= 12:
            owner = Admin(
                username="owner",
                password_hash=generate_password_hash(password)
            )
            db.session.add(owner)
            db.session.commit()