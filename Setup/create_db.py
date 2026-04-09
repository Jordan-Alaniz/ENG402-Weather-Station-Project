"""
Database Creation Utility

Run this script directly to initialize the SQLite database and create 
the necessary tables for weather data and users.
"""

from flask import Flask
from Server.db import db
import Server.models

from dotenv import load_dotenv
import os

load_dotenv('../Server/secrets.env')

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()