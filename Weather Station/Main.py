import datetime
import os
import time

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('secrets.env')

# Configuration
API_URL = 'http://127.0.0.1:5000/api/weather'
API_KEY = os.getenv('API_KEY_PICO')


def main():
    if not API_KEY:
        print("API_KEY_PICO not found in secrets.env.")
        return

    while True:
        # Replace with real sensor data if available
        payload = {
            "temperature": 72.5,
            "humidity": 45.0,
            "pressure": 1013.2,
            "timestamp": datetime.datetime.now().isoformat()
        }

        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }

        print(f"Sending POST request to {API_URL}...")
        try:
            response = requests.post(API_URL, json=payload, headers=headers)

            print(f"Status Code: {response.status_code}")

            try:
                response_data = response.json()
                print(f"Response Body: {response_data}")
            except ValueError:
                print("Response is not valid JSON.")
                print(f"Raw Response Body: {response.text}")

            if not response.ok:
                print(f"Request failed: {response.text}")

        except requests.exceptions.ConnectionError:
            print("Error: Could not connect to the server. Make sure the Flask app is running.")
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")

        # Wait before sending the next update
        time.sleep(60)


if __name__ == "__main__":
    main()