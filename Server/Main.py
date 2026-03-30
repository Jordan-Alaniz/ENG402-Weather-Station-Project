import datetime
import os
from functools import wraps

import bcrypt
from dotenv import load_dotenv
from flask import Flask, jsonify, request, redirect, url_for, render_template, flash
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager, login_user, logout_user, login_required
from flask_talisman import Talisman
from flask_wtf import CSRFProtect

from db import db
from models import WeatherData, User, LoginForm

# Initialize Flask app
app = Flask(__name__)

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

# Ensure the app is not running with a default secret key in production
if os.environ.get('FLASK_ENV') == 'production' and (not app.config["SECRET_KEY"] or app.config["SECRET_KEY"] == "your_secret_key_here"):
    raise RuntimeError("SECRET_KEY must be set in production environment!")

# Extensions
db.init_app(app)
csrf = CSRFProtect(app)
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

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per day", "5 per hour"]
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# Helper decorators
def require_api_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if api_key and api_key == os.environ.get('API_KEY_PICO'):
            return f(*args, **kwargs)
        app.logger.warning("Invalid API key. Request rejected.")
        return jsonify({'error': 'Invalid API key'}), 401

    return decorated


# Routes
@app.route('/')
@login_required
def main():
    return redirect(url_for('dashboard'))


@app.route('/api/weather', methods=['POST'])
@limiter.limit("65 per hour")
@csrf.exempt
@require_api_key
def receive_weather_data():
    data = request.get_json()

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
            return jsonify({'error': 'Temp out of range'}), 400
        if not (0 <= humidity <= 100):
            return jsonify({'error': 'Humidity out of range'}), 400
        if not (800 <= pressure <= 1200):  # hPa range
            return jsonify({'error': 'Pressure out of range'}), 400
    except (ValueError, TypeError):
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

    return jsonify({'message': 'Data received successfully'}), 201


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            pw_match = bcrypt.checkpw(form.password.data.encode('utf-8'), 
                                      user.password_hash.encode('utf-8') if isinstance(user.password_hash, str) else user.password_hash)
            if pw_match:
                login_user(user, remember=True)
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
    logout_user()
    return redirect(url_for('login'))


@app.route('/dashboard')
@limiter.limit("100 per minute")
@login_required
def dashboard():
    weather_data = WeatherData.query.order_by(WeatherData.timestamp.desc()).limit(10).all()
    # Reverse to show chronological order on the graph
    weather_data_chrono = weather_data[::-1]
    labels = [entry.timestamp.strftime('%H:%M') for entry in weather_data_chrono]
    temperature = [entry.temperature for entry in weather_data_chrono]
    humidity = [entry.humidity for entry in weather_data_chrono]
    pressure = [entry.pressure for entry in weather_data_chrono]
    return render_template('dashboard.html', weather_data=weather_data, labels=labels, temperature=temperature, humidity=humidity, pressure=pressure)


@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404


@app.errorhandler(429)
def ratelimit_handler(error):
    return "Too many requests. Please try again later.", 429


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=False)

