"""
Secure Two-Factor Authentication Module for Weather Station

This module implements TOTP-based 2FA with enterprise-grade security:
- Rate limiting on verification attempts
- Backup codes for account recovery
- Constant-time comparison to prevent timing attacks
- Secure secret storage in database
- Account lockout after too many failed attempts

Dependencies:
pip install pyotp qrcode[pil] pillow

Usage:
    from two_factor_auth import TwoFactorAuth
    
    # Generate QR code for setup
    qr_data = TwoFactorAuth.generate_qr_code(user)
    
    # Verify TOTP code
    is_valid = TwoFactorAuth.verify_totp(user, code_from_user)
    
    # Generate backup codes
    codes = TwoFactorAuth.generate_backup_codes(user)
"""

import pyotp
import qrcode
from io import BytesIO
import base64
import secrets
import hmac
from datetime import datetime, timedelta

import Server.db
from Server.models import User, BackupCode, FailedTOTPAttempt


class TwoFactorAuth:
    """Handles all 2FA operations securely"""
    
    # Security constants
    MAX_TOTP_ATTEMPTS = 3  # Max failed attempts before temporary lockout
    LOCKOUT_MINUTES = 15    # How long to lock out after too many failures
    BACKUP_CODE_COUNT = 10  # Number of backup codes to generate
    TOTP_VALID_WINDOW = 1   # Allow 1 step before/after (30 seconds tolerance)
    
    @staticmethod
    def generate_secret():
        """Generate a new TOTP secret (Base32 encoded)"""
        return pyotp.random_base32()
    
    @staticmethod
    def generate_qr_code(user, app_name="Weather Station"):
        """
        Generate QR code for Google Authenticator setup.
        
        Args:
            user: User object with two_fa_secret populated
            app_name: Name to display in authenticator app
            
        Returns:
            dict with 'qr_code_base64' and 'secret'
        """
        if not user.two_fa_secret:
            raise ValueError("User must have two_fa_secret set before generating QR code")
        
        # Create provisioning URI
        totp = pyotp.TOTP(user.two_fa_secret)
        provisioning_uri = totp.provisioning_uri(
            name=user.username,
            issuer_name=app_name
        )
        
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        qr_code_base64 = base64.b64encode(buffer.getvalue()).decode()
        
        return {
            'qr_code_base64': qr_code_base64,
            'secret': user.two_fa_secret
        }
    
    @staticmethod
    def verify_totp(user, code, allow_backup=True):
        """
        Verify a TOTP code or backup code.
        
        Uses constant-time comparison to prevent timing attacks.
        Implements rate limiting to prevent brute force.
        
        Args:
            user: User object
            code: 6-digit TOTP code or backup code from user
            allow_backup: Whether to accept backup codes
            
        Returns:
            tuple: (success: bool, message: str, locked_out: bool)
        """
        # Check if user is locked out
        if TwoFactorAuth._is_locked_out(user):
            remaining = TwoFactorAuth._get_lockout_remaining(user)
            return False, f"Too many failed attempts. Try again in {remaining} minutes.", True
        
        # Clean the code (remove spaces/dashes)
        code = code.replace(' ', '').replace('-', '').strip()
        
        # Try TOTP first
        if len(code) == 6 and code.isdigit():
            totp = pyotp.TOTP(user.two_fa_secret)
            # Use constant-time comparison
            if totp.verify(code, valid_window=TwoFactorAuth.TOTP_VALID_WINDOW):
                # Success - clear failed attempts
                TwoFactorAuth._clear_failed_attempts(user)
                return True, "Code verified successfully", False
        
        # Try backup codes if allowed and code format matches
        if allow_backup and len(code) in [12, 14]:  # Format: XXXX-XXXX-XXXX or XXXXXXXXXXXXXXXX
            if TwoFactorAuth._verify_backup_code(user, code):
                TwoFactorAuth._clear_failed_attempts(user)
                return True, "Backup code verified successfully", False
        
        # Record failed attempt
        TwoFactorAuth._record_failed_attempt(user)
        
        # Check if this failure caused a lockout
        if TwoFactorAuth._is_locked_out(user):
            return False, f"Too many failed attempts. Account locked for {TwoFactorAuth.LOCKOUT_MINUTES} minutes.", True
        
        attempts_left = TwoFactorAuth.MAX_TOTP_ATTEMPTS - TwoFactorAuth._count_recent_attempts(user)
        return False, f"Invalid code. {attempts_left} attempts remaining.", False
    
    @staticmethod
    def _verify_backup_code(user, code):
        """
        Verify and consume a backup code.
        Uses constant-time comparison for security.
        """
        # Normalize the code
        code = code.replace('-', '').upper()
        
        # Get all unused backup codes for this user
        backup_codes = BackupCode.query.filter_by(
            user_id=user.id,
            used=False
        ).all()
        
        for bc in backup_codes:
            # Constant-time comparison
            if hmac.compare_digest(bc.code_hash, TwoFactorAuth._hash_code(code)):
                # Mark as used
                bc.used = True
                bc.used_at = datetime.utcnow()
                db.session.commit()
                return True
        
        return False
    
    @staticmethod
    def generate_backup_codes(user):
        """
        Generate new backup codes for a user.
        Deletes any existing unused codes.
        
        Returns:
            list of backup code strings (save these to show user)
        """
        # Delete old unused backup codes
        BackupCode.query.filter_by(user_id=user.id, used=False).delete()
        
        codes = []
        for _ in range(TwoFactorAuth.BACKUP_CODE_COUNT):
            # Generate random 12-digit code (format: XXXX-XXXX-XXXX)
            code = ''.join(secrets.choice('0123456789ABCDEF') for _ in range(12))
            formatted_code = f"{code[0:4]}-{code[4:8]}-{code[8:12]}"
            
            # Store hashed version
            backup_code = BackupCode(
                user_id=user.id,
                code_hash=TwoFactorAuth._hash_code(code),
                used=False
            )
            db.session.add(backup_code)
            codes.append(formatted_code)
        
        db.session.commit()
        return codes
    
    @staticmethod
    def _hash_code(code):
        """Hash a backup code for storage"""
        import hashlib
        return hashlib.sha256(code.encode()).hexdigest()
    
    @staticmethod
    def _record_failed_attempt(user):
        """Record a failed TOTP attempt"""
        attempt = FailedTOTPAttempt(
            user_id=user.id,
            timestamp=datetime.utcnow()
        )
        db.session.add(attempt)
        db.session.commit()
    
    @staticmethod
    def _clear_failed_attempts(user):
        """Clear all failed attempts for a user"""
        FailedTOTPAttempt.query.filter_by(user_id=user.id).delete()
        db.session.commit()
    
    @staticmethod
    def _count_recent_attempts(user):
        """Count failed attempts in the last LOCKOUT_MINUTES"""
        cutoff = datetime.utcnow() - timedelta(minutes=TwoFactorAuth.LOCKOUT_MINUTES)
        return FailedTOTPAttempt.query.filter(
            FailedTOTPAttempt.user_id == user.id,
            FailedTOTPAttempt.timestamp > cutoff
        ).count()
    
    @staticmethod
    def _is_locked_out(user):
        """Check if user is currently locked out"""
        return TwoFactorAuth._count_recent_attempts(user) >= TwoFactorAuth.MAX_TOTP_ATTEMPTS
    
    @staticmethod
    def _get_lockout_remaining(user):
        """Get minutes remaining on lockout"""
        oldest_attempt = FailedTOTPAttempt.query.filter_by(
            user_id=user.id
        ).order_by(FailedTOTPAttempt.timestamp.asc()).first()
        
        if not oldest_attempt:
            return 0
        
        elapsed = (datetime.utcnow() - oldest_attempt.timestamp).total_seconds() / 60
        remaining = max(0, TwoFactorAuth.LOCKOUT_MINUTES - elapsed)
        return int(remaining) + 1
    
    @staticmethod
    def enable_2fa(user):
        """
        Enable 2FA for a user (generates secret and backup codes).
        
        Returns:
            dict with 'qr_data' and 'backup_codes'
        """
        # Generate new secret
        user.two_fa_secret = TwoFactorAuth.generate_secret()
        user.two_fa_enabled = False  # Will be enabled after verification
        db.session.commit()
        
        # Generate QR code
        qr_data = TwoFactorAuth.generate_qr_code(user)
        
        # Generate backup codes
        backup_codes = TwoFactorAuth.generate_backup_codes(user)
        
        return {
            'qr_data': qr_data,
            'backup_codes': backup_codes
        }
    
    @staticmethod
    def disable_2fa(user):
        """Disable 2FA for a user and clean up related data"""
        user.two_fa_enabled = False
        user.two_fa_secret = None
        
        # Delete backup codes and failed attempts
        BackupCode.query.filter_by(user_id=user.id).delete()
        FailedTOTPAttempt.query.filter_by(user_id=user.id).delete()
        
        db.session.commit()
