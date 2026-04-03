"""
Flask Weather Station Server - Main Application

This module handles the Flask app initialization, database configuration,
user authentication, and API endpoints for receiving weather data.
"""

import datetime
import os
from functools import wraps

import bcrypt
from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect, url_for, render_template, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_talisman import Talisman
from flask_wtf import CSRFProtect

from db import db
from models import WeatherData, User, LoginForm

import logging

#for 2FA
import pyotp
import pyqrcode
from io import BytesIO
import base64

# Initialize Flask app
app = Flask(__name__)

logging.basicConfig(level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('weather_station.log'),
        logging.StreamHandler()
    ])
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv('secrets.env')

# Configuration
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///weather.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config['SESSION_COOKIE_HTTPONLY'] = True  # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'  # CSRF protection
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(hours=1)

logger.info(f"FLASK_ENV: {os.environ.get('FLASK_ENV')}")

# Ensure the app is not running with a default secret key in production
if os.environ.get('FLASK_ENV') == 'production' and (not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "your_secret_key_here"):
    logger.error("SECRET_KEY must be set in production environment!")
    raise RuntimeError("SECRET_KEY must be set in production environment!")

# Extensions
db.init_app(app)
logger.info("Database initialized.")

csrf = CSRFProtect(app)
logger.info("CSRF protection enabled.")

Talisman(app,
         force_https=os.environ.get('FLASK_ENV') == 'production',
         strict_transport_security=True,
         content_security_policy={
             'default-src': "'self'",
             'script-src': "'self' 'unsafe-inline'",
             'style-src': "'self' 'unsafe-inline' https://fonts.googleapis.com",
             'font-src': "'self' https://fonts.gstatic.com",
             'img-src': "'self' data:",
         }
         )
logger.info("Talisman initialized.")

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per day", "5 per hour"]
)
logger.info("Rate limiting enabled.")

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
logger.info("Login manager initialized.")


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login user loader to retrieve a user from the database by ID."""
    logger.info(f"User {user_id} attempted to log in")
    return User.query.get(int(user_id))


# Helper decorators
def require_api_key(f):
    """
    Decorator to ensure the request contains a valid 'X-API-Key' header.
    Matches against the API_KEY_PICO environment variable.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == os.environ.get('API_KEY_PICO'):
            logger.info(f"API key check passed for {get_remote_address()}")
            return f(*args, **kwargs)
        app.logger.warning("Invalid API key. Request rejected.")
        return jsonify({'error': 'Invalid API key'}), 401

    return decorated


# Routes
@app.route('/')
@login_required
def main():
    """Redirect root access to the dashboard if authenticated."""
    return redirect(url_for('dashboard'))


@app.route('/api/weather', methods=['POST'])
@require_api_key
@limiter.limit("1 per minute") #65 per hour
@csrf.exempt
def receive_weather_data():
    """
    API endpoint for the weather station (e.g., Pico) to submit data.
    Validates input ranges and stores data in the SQLite database.
    """
    data = request.get_json()
    logger.info(f"Received weather data: {data}")
    # Check required fields
    required = ['temperature', 'humidity', 'pressure', 'timestamp']
    if not all(field in data for field in required):
        return jsonify({'error': 'Missing fields'}), 400

    # Validate types and ranges
    try:
        temp = float(data['temperature'])
        humidity = float(data['humidity'])
        pressure = float(data['pressure'])
        validated_timestamp = datetime.datetime.fromisoformat(data['timestamp'])

        if not (-50 <= temp <= 150):  # °F range
            logger.warning(f"Temp out of range: {temp}")
            return jsonify({'warning': 'Temp out of range'}), 400
        if not (0 <= humidity <= 100):
            logger.warning(f"Humidity out of range: {humidity}")
            return jsonify({'warning': 'Humidity out of range'}), 400
        if not (800 <= pressure <= 1200):  # hPa range
            logger.warning(f"Pressure out of range: {pressure}")
            return jsonify({'warning': 'Pressure out of range'}), 400
    except (ValueError, TypeError):
        logger.error("Invalid data types in request")
        return jsonify({'error': 'Invalid data types'}), 400

    # Data is validated, safe to use
    weather_entry = WeatherData(
        temperature=temp,
        humidity=humidity,
        pressure=pressure,
        timestamp=validated_timestamp
    )
    db.session.add(weather_entry)
    db.session.commit()
    logger.info(f"Weather data saved: {weather_entry}")

    return jsonify({'message': 'Data received successfully'}), 201


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """
    Handles user login. Validates credentials against hashed passwords
    stored in the database using bcrypt.
    """
    logger.info(f"Login attempt from {get_remote_address()}")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            pw_match = bcrypt.checkpw(form.password.data.encode('utf-8'), 
                                      user.password_hash.encode('utf-8') if isinstance(user.password_hash, str) else user.password_hash)
            if pw_match:
                login_user(user, remember=True)
                logger.info(f"User {form.username.data} logged in")
                return redirect(url_for('dashboard'))
            else:
                app.logger.warning(f"Login failed: Invalid password for user {form.username.data}")
        else:
            app.logger.warning(f"Login failed: User not found {form.username.data}")
        flash('Invalid username or password')
    return render_template('login.html', form=form)


@app.route('/logout')
@login_required
def logout():
    """Logs out the current user and redirects to the login page."""
    logout_user()
    logger.info(f"User logged out")
    return redirect(url_for('login'))


@app.route('/dashboard')
@limiter.limit("100 per minute")
@login_required
def dashboard():
    """
    Renders the main weather dashboard with the latest 10 data records
    for the table and the graph.
    """
    weather_data = WeatherData.query.order_by(WeatherData.timestamp.desc()).limit(10).all()
    # Reverse to show chronological order on the graph
    weather_data_chrono = weather_data[::-1]
    labels = [entry.timestamp.strftime('%H:%M') for entry in weather_data_chrono]
    temperature = [entry.temperature for entry in weather_data_chrono]
    humidity = [entry.humidity for entry in weather_data_chrono]
    pressure = [entry.pressure for entry in weather_data_chrono]
    logger.info(f"Dashboard rendered for user {current_user.username}")
    return render_template('dashboard.html', weather_data=weather_data, labels=labels, temperature=temperature, humidity=humidity, pressure=pressure)
    

@app.route('/api/recent_weather')
@login_required
@limiter.limit("100 per minute")
def get_recent_weather():
    """
    Returns the latest 10 weather records in JSON format.
    Used for AJAX polling on the dashboard page.
    """
    # Return the same data as the dashboard, but in JSON format for updates
    weather_data = WeatherData.query.order_by(WeatherData.timestamp.desc()).limit(10).all()
    weather_data_chrono = weather_data[::-1]
    
    data = {
        'labels': [entry.timestamp.strftime('%H:%M') for entry in weather_data_chrono],
        'temperature': [entry.temperature for entry in weather_data_chrono],
        'humidity': [entry.humidity for entry in weather_data_chrono],
        'pressure': [entry.pressure for entry in weather_data_chrono],
        'table_data': [
            {
                'timestamp': entry.timestamp.strftime('%Y-%m-%d %H:%M'),
                'temperature': f"{entry.temperature:.1f}",
                'humidity': f"{entry.humidity:.1f}",
                'pressure': f"{entry.pressure:.1f}"
            } for entry in weather_data
        ]
    }
    logger.info(f"Recent weather data requested: {data}")
    return jsonify(data)


@app.errorhandler(404)
def not_found(error):
    """Custom error handler for 404 Page Not Found errors."""
    logger.warning(f"404 Not Found: {request.url}")
    return render_template('404.html'), 404


@app.errorhandler(429)
def ratelimit_handler(error):
    """Custom error handler for 429 Too Many Requests (rate limiting)."""
    logger.warning(f"Rate limit exceeded: {get_remote_address()}")
    return "Too many requests. Please try again later.", 429


if __name__ == '__main__':
    with app.app_context():
        # Ensure database tables are created before starting
        db.create_all()
    app.run(debug=False)

