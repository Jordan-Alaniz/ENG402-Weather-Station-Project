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
from flask import Flask, jsonify, request, redirect, url_for, render_template, flash, session
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_talisman import Talisman
from flask_wtf import CSRFProtect

import db
from models import WeatherData, User, LoginForm, BackupCode, FailedTOTPAttempt
from two_factor_auth import TwoFactorAuth

import logging

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
db.db.init_app(app)
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
    # Fixed: Use db.session.get instead of deprecated User.query.get
    return db.db.session.get(User, int(user_id))


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
    db.db.session.add(weather_entry)
    db.db.session.commit()
    logger.info(f"Weather data saved: {weather_entry}")

    return jsonify({'message': 'Data received successfully'}), 201


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """
    Handles user login. Validates credentials against hashed passwords
    stored in the database using bcrypt. Redirects to 2FA if enabled.
    """
    logger.info(f"Login attempt from {get_remote_address()}")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            pw_match = bcrypt.checkpw(form.password.data.encode('utf-8'), 
                                      user.password_hash.encode('utf-8') if isinstance(user.password_hash, str) else user.password_hash)
            if pw_match:
                # Fixed: Check two_fa_enabled (not two_factor_auth_enabled)
                if user.two_fa_enabled:
                    session['pending_2fa_user_id'] = user.id
                    logger.info(f"User {form.username.data} requires 2FA")
                    return redirect(url_for('verify_2fa'))
                else:
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


@app.route('/verify-2fa', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_2fa():
    """Verify 2FA code after password login"""
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        flash('Session expired. Please log in again.')
        return redirect(url_for('login'))

    # Fixed: Use db.session.get instead of deprecated User.query.get
    user = db.db.session.get(User, user_id)
    if not user or not user.two_fa_enabled:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        if not code:
            flash('Please enter a code')
            return render_template('verify_2fa.html')

        success, message, locked_out = TwoFactorAuth.verify_totp(user, code, allow_backup=True)

        if success:
            session.pop('pending_2fa_user_id', None)
            login_user(user, remember=True)
            logger.info(f"User {user.username} verified 2FA and logged in")
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed 2FA attempt for user {user.username}: {message}")
            if locked_out:
                session.pop('pending_2fa_user_id', None)
                flash(message, 'error')
                return redirect(url_for('login'))
            else:
                flash(message, 'error')

    return render_template('verify_2fa.html', username=user.username)


@app.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per minute")
def setup_2fa():
    """Setup 2FA for current user"""
    if current_user.two_fa_enabled:
        flash('2FA is already enabled', 'info')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        code = request.form.get('code')
        if code:
            success, message, _ = TwoFactorAuth.verify_totp(current_user, code, allow_backup=False)
            if success:
                current_user.two_fa_enabled = True
                db.db.session.commit()
                logger.info(f"User {current_user.username} enabled 2FA")
                flash('2FA has been successfully enabled!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash(f'Verification failed: {message}', 'error')
                qr_data = TwoFactorAuth.generate_qr_code(current_user)
                backup_codes = session.get('backup_codes_to_show', [])
                return render_template('setup_2fa.html',
                                       qr_code=qr_data['qr_code_base64'],
                                       secret=qr_data['secret'],
                                       backup_codes=backup_codes)
        else:
            setup_data = TwoFactorAuth.enable_2fa(current_user)
            session['backup_codes_to_show'] = setup_data['backup_codes']
            return render_template('setup_2fa.html',
                                   qr_code=setup_data['qr_data']['qr_code_base64'],
                                   secret=setup_data['qr_data']['secret'],
                                   backup_codes=setup_data['backup_codes'])

    if not current_user.two_fa_secret:
        setup_data = TwoFactorAuth.enable_2fa(current_user)
        session['backup_codes_to_show'] = setup_data['backup_codes']
        return render_template('setup_2fa.html',
                               qr_code=setup_data['qr_data']['qr_code_base64'],
                               secret=setup_data['qr_data']['secret'],
                               backup_codes=setup_data['backup_codes'])
    else:
        qr_data = TwoFactorAuth.generate_qr_code(current_user)
        backup_codes = session.get('backup_codes_to_show', [])
        return render_template('setup_2fa.html',
                               qr_code=qr_data['qr_code_base64'],
                               secret=qr_data['secret'],
                               backup_codes=backup_codes)


@app.route('/disable-2fa', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def disable_2fa():
    """Disable 2FA"""
    if not current_user.two_fa_enabled:
        flash('2FA is not enabled', 'info')
        return redirect(url_for('dashboard'))

    TwoFactorAuth.disable_2fa(current_user)
    logger.info(f"User {current_user.username} disabled 2FA")
    flash('2FA has been disabled', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/regenerate-backup-codes', methods=['POST'])
@login_required
@limiter.limit("3 per hour")
def regenerate_backup_codes():
    """Regenerate backup codes"""
    if not current_user.two_fa_enabled:
        flash('2FA is not enabled', 'error')
        return redirect(url_for('dashboard'))

    new_codes = TwoFactorAuth.generate_backup_codes(current_user)
    logger.info(f"User {current_user.username} regenerated backup codes")
    return render_template('backup_codes.html', backup_codes=new_codes)


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
    # Ensure database tables are created before starting
    # Must be inside app.run() or the app context will be lost
    with app.app_context():
        db.db.create_all()
        logger.info("Database tables created/verified.")
    app.run(debug=False)
