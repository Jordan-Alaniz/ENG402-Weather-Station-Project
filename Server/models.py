"""
Database Models and Forms

This module defines the SQLAlchemy models for weather data and users,
as well as the Flask-WTF login form.
"""

from db import db
from flask_login import UserMixin
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired
from datetime import datetime


class WeatherData(db.Model):
    """Stores weather sensor data: temperature, humidity, and pressure."""
    id = db.Column(db.Integer, primary_key=True)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    pressure = db.Column(db.Float)
    timestamp = db.Column(db.DateTime)


class User(UserMixin, db.Model):
    """User model for authentication, storing username and hashed password."""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # 2FA fields
    two_fa_enabled = db.Column(db.Boolean, default=False, nullable=False)
    two_fa_secret = db.Column(db.String(32), nullable=True)  # Base32 encoded TOTP secret
    
    # Relationships
    backup_codes = db.relationship('BackupCode', backref='user', lazy=True, cascade='all, delete-orphan')
    failed_attempts = db.relationship('FailedTOTPAttempt', backref='user', lazy=True, cascade='all, delete-orphan')


class BackupCode(db.Model):
    """Stores hashed backup codes for 2FA recovery"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    code_hash = db.Column(db.String(64), nullable=False)  # SHA-256 hash of the backup code
    used = db.Column(db.Boolean, default=False, nullable=False)
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class FailedTOTPAttempt(db.Model):
    """Tracks failed 2FA attempts for rate limiting"""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class LoginForm(FlaskForm):
    """Login form for user authentication."""
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')
