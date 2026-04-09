"""
API Test Client

A simple script to test the /api/weather POST endpoint with sample data.
Ensures the server is up and rejecting invalid API keys.
"""

import requests
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', 'Server', 'secrets.env'))

# Configuration
API_URL = 'http://127.0.0.1:5000/api/weather'
API_KEY = os.getenv('API_KEY_PICO')

def test_api():
    if not API_KEY:
        print("API_KEY_PICO not found in secrets.env.")
        return

    payload = {
        "temperature": 72.5,
        "humidity": 45.0,
        "pressure": 1013.2,
        "timestamp": "2024-03-25T12:00:00"
    }

    headers = {
        'X-API-Key': API_KEY,
        'Content-Type': 'application/json'
    }

    print(f"Sending POST request to {API_URL}...")
    try:
        response = requests.post(API_URL, json=payload, headers=headers)

        print(f"Status Code: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'unknown')}")

        # Try to decode JSON only if the response appears to be JSON
        try:
            response_data = response.json()
            print(f"Response Body: {response_data}")
        except ValueError:
            print("Response is not valid JSON.")
            print(f"Raw Response Body: {response.text}")

        # Helpful status-based message
        if not response.ok:
            print("Request failed. Check the API route, API key, and server logs.")

    except requests.exceptions.ConnectionError:
        print("Error: Could not connect to the server. Make sure the Flask app is running at http://127.0.0.1:5000.")
    except requests.exceptions.RequestException as e:
        print(f"Request error: {e}")

if __name__ == "__main__":
    test_api()

