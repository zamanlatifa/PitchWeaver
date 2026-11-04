import os
import sys
from datetime import timedelta

backend_dir = os.path.dirname(os.path.abspath(__file__))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

from flask import Flask, send_from_directory
from flask_jwt_extended import JWTManager
from models import db
from routes.auth import auth_bp, bcrypt
from routes.training import training_bp
from routes.dashboard import dashboard_bp


def create_app():
    app = Flask(__name__, static_folder=os.path.join(backend_dir, "..", "Frontend"))

    load_dotenv(env_path)
    db_url = os.getenv("DATABASE_URL")
    if db_url:
        # Neon/Heroku-style URLs start with postgres://, SQLAlchemy needs postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
    elif os.getenv("VERCEL"):
        # Vercel's filesystem is read-only except /tmp, which is wiped often.
        # This only lets the app boot; set DATABASE_URL for real persistence.
        db_url = "sqlite:////tmp/pitchweaver.db"
    else:
        db_url = f"sqlite:///{os.path.join(backend_dir, 'pitchweaver.db')}"
    app.config["SQLALCHEMY_DATABASE_URI"] = db_url
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {"pool_pre_ping": True}
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["JWT_SECRET_KEY"]           = os.getenv("JWT_SECRET_KEY", "change-me-before-production")
    app.config["JWT_TOKEN_LOCATION"]       = ["cookies"]
    app.config["JWT_COOKIE_CSRF_PROTECT"]  = False
    app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(days=7)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

    db.init_app(app)
    JWTManager(app)
    bcrypt.init_app(app)

    app.register_blueprint(auth_bp)
    app.register_blueprint(training_bp)
    app.register_blueprint(dashboard_bp)

    with app.app_context():
        db.create_all()

        from sqlalchemy import inspect, text
        cols = [c["name"] for c in inspect(db.engine).get_columns("users")]
        if "attempts_at_last_level_change" not in cols:
            db.session.execute(text(
                "ALTER TABLE users ADD COLUMN attempts_at_last_level_change INTEGER DEFAULT 0"
            ))
            db.session.commit()

    @app.route("/")
    def serve_index():
        return send_from_directory(app.static_folder, "index.html")

    @app.route("/login")
    def serve_login():
        return send_from_directory(app.static_folder, "login.html")

    @app.route("/about")
    def serve_about():
        return send_from_directory(app.static_folder, "about.html")

    @app.route("/<path:path>")
    def serve_static(path):
        return send_from_directory(app.static_folder, path)

    return app


app = create_app()

if __name__ == "__main__":
    print("PitchWeaver running at http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
