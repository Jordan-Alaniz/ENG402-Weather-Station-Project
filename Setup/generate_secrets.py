"""
Secret Generation Utility

A helper script to generate a secure random 32-byte hex string
to be used as the Flask SECRET_KEY.
"""

import secrets

print(secrets.token_hex(32))