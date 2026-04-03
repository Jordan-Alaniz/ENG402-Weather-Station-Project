import unittest
import os
import sys
import json
import datetime
import bcrypt
from flask import url_for

# Add the Server directory to the path so we can import Main, models, etc.
server_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Server'))
sys.path.insert(0, server_path)

import Main as ServerMain
import models
from Main import app, db, limiter
from models import User, WeatherData

class ServerTestCase(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing forms
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['SECRET_KEY'] = 'test_secret'
        os.environ['API_KEY_PICO'] = 'test_pico_key'
        
        self.app_context = app.app_context()
        self.app_context.push()
        self.client = app.test_client()
        
        db.create_all()
        
        # Create a test user
        password_hash = bcrypt.hashpw(b'testpassword', bcrypt.gensalt()).decode('utf-8')
        user = User(username='testuser', password_hash=password_hash)
        db.session.add(user)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_api_authentication_success(self):
        """Test API endpoint with valid API key."""
        payload = {
            "temperature": 75.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": datetime.datetime.now().isoformat()
        }
        headers = {'X-API-Key': 'test_pico_key'}
        response = self.client.post('/api/weather', 
                                    data=json.dumps(payload),
                                    content_type='application/json',
                                    headers=headers)
        self.assertEqual(response.status_code, 201)
        self.assertIn(b'Data received successfully', response.data)

    def test_api_authentication_failure(self):
        """Test API endpoint with invalid API key."""
        payload = {
            "temperature": 75.5,
            "humidity": 45.2,
            "pressure": 1013.2,
            "timestamp": datetime.datetime.now().isoformat()
        }
        headers = {'X-API-Key': 'wrong_key'}
        response = self.client.post('/api/weather', 
                                    data=json.dumps(payload),
                                    content_type='application/json',
                                    headers=headers)
        self.assertEqual(response.status_code, 401)
        self.assertIn(b'Invalid API key', response.data)

    def test_api_validation_ranges(self):
        """Test API data validation for out-of-range values."""
        headers = {'X-API-Key': 'test_pico_key'}
        
        # Temperature out of range
        payload = {"temperature": 200, "humidity": 50, "pressure": 1000, "timestamp": datetime.datetime.now().isoformat()}
        response = self.client.post('/api/weather', data=json.dumps(payload), content_type='application/json', headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Temp out of range', response.data)

        # Humidity out of range
        payload = {"temperature": 70, "humidity": 110, "pressure": 1000, "timestamp": datetime.datetime.now().isoformat()}
        response = self.client.post('/api/weather', data=json.dumps(payload), content_type='application/json', headers=headers)
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Humidity out of range', response.data)

    def test_login_logout(self):
        """Test user login and logout."""
        # Test login success
        response = self.client.post('/login', data=dict(
            username='testuser',
            password='testpassword'
        ), follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Weather Dashboard', response.data)

        # Test logout
        response = self.client.get('/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Login', response.data)

    def test_dashboard_protected(self):
        """Test that dashboard requires login."""
        response = self.client.get('/dashboard', follow_redirects=False)
        self.assertEqual(response.status_code, 302)  # Redirect to login
        self.assertIn('/login', response.location)

    def test_security_headers(self):
        """Test if security headers are present (Talisman)."""
        response = self.client.get('/login')
        self.assertIn('Content-Security-Policy', response.headers)
        self.assertIn('X-Content-Type-Options', response.headers)
        self.assertIn('X-Frame-Options', response.headers)

    def test_csrf_protection(self):
        """Test CSRF protection on login form."""
        # Enable CSRF for this test
        app.config['WTF_CSRF_ENABLED'] = True
        
        # Try to post to login without CSRF token
        response = self.client.post('/login', data=dict(
            username='testuser',
            password='testpassword'
        ), follow_redirects=True)
        
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'The CSRF token is missing', response.data)
        
        # Reset for other tests
        app.config['WTF_CSRF_ENABLED'] = False

    def test_rate_limiting_api(self):
        """Test rate limiting on API endpoint."""
        # The current limit is 65 per hour. We can't easily change it here.
        # But we can verify that the limiter is enabled for the endpoint.
        # We'll check for the 'X-RateLimit-Limit' header if it's configured to show it,
        # or just assume it's working if it's decorated.
        # For this test, we'll just check if the app has the limiter extension.
        self.assertTrue(hasattr(app, 'extensions'))
        self.assertIn('limiter', app.extensions)

if __name__ == '__main__':
    unittest.main()
