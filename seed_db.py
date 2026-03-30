"""
Database Seeding Utility

Creates an initial admin user if one does not already exist.
Password is read from environment variables or prompted securely.
"""

from flask_sqlalchemy import SQLAlchemy
import os
import bcrypt
from flask import Flask
from dotenv import load_dotenv
import getpass

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

# Optional: load local env file if present (but do NOT commit it)
load_dotenv("Server/secrets.env")

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///weather.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

def _get_admin_credentials():
    username = os.getenv("ADMIN_USERNAME", "admin")

    password = os.getenv("ADMIN_PASSWORD")
    if not password:
        password = getpass.getpass("Enter admin password (input hidden): ").strip()

    if not password:
        raise ValueError("Admin password is empty. Set ADMIN_PASSWORD or enter a password when prompted.")

    return username, password

def create_admin(allow_password_update: bool = False):
    with app.app_context():
        db.create_all()

        username, password = _get_admin_credentials()
        user = User.query.filter_by(username=username).first()

        hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

        if not user:
            db.session.add(User(username=username, password_hash=hashed_password))
            print(f"Admin user created: username='{username}'")
        else:
            if allow_password_update:
                user.password_hash = hashed_password
                print(f"Admin user password updated: username='{username}'")
            else:
                print(f"Admin user already exists: username='{username}' (no changes made)")

        db.session.commit()

if __name__ == "__main__":
    allow_update = os.getenv("ALLOW_ADMIN_PASSWORD_UPDATE", "false").lower() in ("1", "true", "yes", "y")
    create_admin(allow_password_update=allow_update)