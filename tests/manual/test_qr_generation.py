#!/usr/bin/env python3
"""
Test script to debug QR code generation
"""

import sys
import os
from io import BytesIO
import base64
import pyotp
import qrcode

# Make the Server folder importable from the manual test folder.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'Server')))

# Test 1: Generate a secret
secret = pyotp.random_base32()
print(f"Generated Secret: {secret}")
print(f"Secret Length: {len(secret)}")
print(f"Is Valid Base32: {all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567=' for c in secret.upper())}")

# Test 2: Create TOTP and generate code
totp = pyotp.TOTP(secret)
current_code = totp.now()
print(f"\nGenerated TOTP Code: {current_code}")
print(f"Verify Code: {totp.verify(current_code)}")

# Test 3: Create provisioning URI
uri = totp.provisioning_uri(
    name="testuser",
    issuer_name="Weather Station"
)
print(f"\nProvisioning URI: {uri}")
print(f"URI Length: {len(uri)}")

# Test 4: Generate QR code
qr = qrcode.QRCode(
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
    box_size=10,
    border=4
)
qr.add_data(uri)
qr.make(fit=True)

print(f"\nQR Code Version: {qr.version}")
print(f"QR Code Modules: {len(qr.modules)}x{len(qr.modules[0])}")

# Test 5: Save QR code image to file
img = qr.make_image(fill_color="black", back_color="white")
qr_file_path = "test_qr_code.png"
img.save(qr_file_path)
print(f"\nQR Code saved to: {os.path.abspath(qr_file_path)}")
print(f"File size: {os.path.getsize(qr_file_path)} bytes")

# Test 6: Encode to base64
buffer = BytesIO()
img.save(buffer, format='PNG')
buffer.seek(0)
qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
print(f"\nBase64 QR Code Size: {len(qr_code_base64)} characters")
print(f"Base64 Preview (first 100 chars): {qr_code_base64[:100]}...")

# Test 7: Decode and verify base64
try:
    decoded = base64.b64decode(qr_code_base64)
    print(f"Base64 Decoded Size: {len(decoded)} bytes")
    print(f"Decoded matches saved file: {decoded == open(qr_file_path, 'rb').read()}")
except Exception as e:
    print(f"Error decoding base64: {e}")

print("\n✓ QR Code generation test completed successfully!")
print("\nYou can inspect the generated test_qr_code.png file to verify it's valid.")
print("Try scanning it with Google Authenticator to see if it works.")


