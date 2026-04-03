# Flask Weather Station Server - Step-by-Step Instructions

This project is a simple weather station server built using **Flask** and **SQLAlchemy**. It allows a weather station (e.g., a Raspberry Pi Pico) to send sensor data via a POST request to a SQLite database.

## 1. Setup Environment

First, make sure you have Python installed. You can check this by running `py --version` or `python --version` in your terminal.

1. **Create a virtual environment (optional but recommended):**
   ```bash
   py -m venv venv
   ```
2. **Activate the virtual environment:**
   - **Windows:** `venv\Scripts\activate`
   - **macOS/Linux:** `source venv/bin/activate`
3. **Install dependencies:**
   ```bash
   pip install flask flask-sqlalchemy python-dotenv requests flask-limiter flask-login flask-talisman flask-wtf bcrypt
   ```

## 2. Configuration (`secrets.env`)

The project uses environment variables stored in a file named `secrets.env`. This file contains the secret key for Flask, the database URL, and the API key required for the Pico to communicate with the server.

The file should look like this:
```env
FLASK_ENV=development
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///weather.db
API_KEY_PICO=your_api_key_here
```
*Note: Set `FLASK_ENV=production` in a real deployment to enable strict security headers and secure cookies.*

## 3. Security Measures

This application includes several built-in security features:
- **Content Security Policy (CSP):** Restricts where scripts and styles can be loaded from.
- **Rate Limiting:** Protects against brute-force and DoS attacks (via `Flask-Limiter`).
- **CSRF Protection:** Prevents cross-site request forgery (via `Flask-WTF`).
- **Secure Cookies:** Uses `HttpOnly`, `SameSite=Lax`, and `Secure` (in production) flags.
- **Password Hashing:** Passwords are securely hashed using `bcrypt`.
- **API Authentication:** Data ingestion is protected by a secret API key.
- **Input Validation:** All incoming data is strictly validated for type and range.

### Production Recommendations
When deploying to a public server:
1. **Use HTTPS:** Always serve the application over TLS/SSL.
2. **WSGI Server:** Use a production-grade server like `gunicorn` or `uwsgi` instead of the built-in Flask development server.
3. **Set `FLASK_ENV=production`:** This ensures that the `Secure` flag is set on cookies and HSTS is enforced.
4. **Firewall:** Restrict access to the database and internal ports.

## 4. Initialize the Database

Before running the server, you need to create the database tables. Run the provided script from the project root:

```bash
cd Server
py create_db.py
cd ..
```
*Note: This script initializes `weather.db` inside the `Server/instance/` folder.*

## 4. Run the Server

To start the Flask application:

```bash
cd Server
py Main.py
```
By default, the server will run on `http://127.0.0.1:5000`.

## 5. Test the API

You can test if the server is working by using the provided `test_api_client.py` script. 

1. Ensure the server is running (Step 4).
2. Open a new terminal.
3. Run the test script:
   ```bash
   py test_api_client.py
   ```
If successful, you should see a `200 OK` response.

## 6. Running Unit Tests

To run the full suite of unit tests for both the server and the client (Pico), use the provided `run_tests.py` script from the project root. This will execute tests in isolation to verify security features, data validation, and client behavior.

1. Ensure all dependencies are installed (Step 1).
2. Run the test suite:
   ```bash
   py run_tests.py
   ```
The test suite covers:
- **Server API Authentication:** Verifies `X-API-Key` protection.
- **Data Validation:** Ensures temperature, humidity, and pressure ranges are enforced.
- **User Authentication:** Tests login/logout and session protection.
- **Security Headers:** Confirms `Talisman` headers (CSP, HSTS, etc.) are present.
- **CSRF Protection:** Verifies that forms require a valid CSRF token.
- **Rate Limiting:** Ensures the `Flask-Limiter` extension is active.
- **Client Mocking:** Tests the Pico client's logic and error handling without needing a physical sensor or server.

## API Documentation

### POST `/api/weather`
Receives weather data from the Pico.

**Headers:**
- `X-API-Key`: Your `API_KEY_PICO` value.
- `Content-Type`: `application/json`

**Payload Example:**
```json
{
    "temperature": 72.5,
    "humidity": 45.0,
    "pressure": 1013.2,
    "timestamp": "2024-03-25T12:00:00"
}
```

**Response:**
- `200 OK` if successful.
- `401 Unauthorized` if the API key is missing or incorrect.
- `400 Bad Request` if data is missing or out of range.
