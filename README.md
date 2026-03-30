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
   pip install flask flask-sqlalchemy python-dotenv requests
   ```

## 2. Configuration (`secrets.env`)

The project uses environment variables stored in a file named `secrets.env`. This file contains the secret key for Flask, the database URL, and the API key required for the Pico to communicate with the server.

The file should look like this:
```env
SECRET_KEY=your_secret_key_here
DATABASE_URL=sqlite:///weather.db
API_KEY_PICO=your_api_key_here
```

## 3. Initialize the Database

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
