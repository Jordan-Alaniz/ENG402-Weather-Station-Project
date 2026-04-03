"""
Weather Station Client (e.g., Raspberry Pi Pico)

Simulates weather data collection and sends it periodically 
via HTTP POST to the central Flask server.
"""

import datetime
import os
import time

import requests
from dotenv import load_dotenv

import random

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
            "temperature": random.uniform(70, 80),
            "humidity": random.uniform(40, 60),
            "pressure": random.uniform(950, 1050),
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

        time.sleep(1)
        # Wait before sending the next update
        while int(time.time() % 60) != 59:
            time.sleep(1)


if __name__ == "__main__":
    main()