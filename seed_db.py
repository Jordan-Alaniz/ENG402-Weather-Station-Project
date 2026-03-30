"""
Database Seeding Utility

Creates an initial 'admin' user with a secure password if one 
does not already exist in the database.
"""

from flask_sqlalchemy import SQLAlchemy
import os
import bcrypt
from flask import Flask
from dotenv import load_dotenv

# Database initialization
db = SQLAlchemy()

# Model definition (copy of User model to avoid import issues)
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

load_dotenv('Server/secrets.env')

app = Flask(__name__)
# Adjusting path to match what Server/Main.py would use if run from project root or Server dir
# In Server/Main.py it's "sqlite:///weather.db" which creates instance/weather.db relative to Server/Main.py
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///weather.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

def create_admin():
    with app.app_context():
        db.create_all()
        user = User.query.filter_by(username='admin').first()
        password = '***REDACTED***'
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        if not user:
            admin = User(username='admin', password_hash=hashed_password.decode('utf-8'))
            db.session.add(admin)
            print(f"Admin user created with username 'admin' and password '{password}'")
        else:
            user.password_hash = hashed_password.decode('utf-8')
            print(f"Admin user password updated to '{password}'")
        db.session.commit()

if __name__ == '__main__':
    create_admin()
