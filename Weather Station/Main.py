"""
Weather Station Client (e.g., Raspberry Pi Pico)

Simulates weather data collection and sends it periodically 
via HTTP POST to the central Flask server.
"""

import os
import time

import requests
#from dotenv import load_dotenv
import sens
import secrets

import wifi

# Load environment variables

# Configuration
API_URL = 'http://192.168.0.235:8080/api/weather'
API_KEY = secrets.API_KEY_PICO

wifi.connect()

def main():
    if not API_KEY:
        print("API_KEY_PICO not found in secrets.env.")
        return

    while True:
        values = sens.sens()
        payload = {
            "temperature": float(values[0]),
            "humidity": float(values[1]),
            "pressure": float(values[2]),
            "timestamp": values[3]
        }

        headers = {
            'X-API-Key': API_KEY,
            'Content-Type': 'application/json'
        }
        print(payload)

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

            if response.status_code>=400:
                print(f"Request failed: {response.text}")

        except OSError as e:
            print(f"Error: Could not connect to the server. Make sure the Flask app is running. {e}")
        except Exception as e:
            print(f"Request error: {e}")

        time.sleep(1)
        # Wait before sending the next update
        while int(time.time() % 60) != 59:
            time.sleep(1)


if __name__ == "__main__":
    main()

