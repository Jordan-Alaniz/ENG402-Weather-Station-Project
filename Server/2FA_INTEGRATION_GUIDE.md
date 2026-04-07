# Secure 2FA Integration Guide for Weather Station

## Overview
This guide shows you how to add enterprise-grade Two-Factor Authentication (TOTP) to your weather station Flask app. This implementation fixes all security issues in the tutorial code.

## Security Features Included
✅ Rate limiting (prevents brute force attacks)
✅ Account lockout after failed attempts  
✅ Backup codes for account recovery
✅ Constant-time comparison (prevents timing attacks)
✅ Secure secret storage in SQLite database
✅ No hardcoded secrets
✅ Integrates with your existing security (CSRF, Talisman, bcrypt)

---

## Step 1: Install Dependencies

```bash
pip install pyotp qrcode[pil] pillow
```

These are already partially installed (pyotp is in your imports), but make sure you have the full set.

---

## Step 2: Files Already Created

I've created these files in your `Server/` directory:
- `two_factor_auth.py` - Core 2FA logic (all security features)
- Updated `models.py` - Added 2FA database tables

---

## Step 3: Update Main.py

### 3A. Add imports at the top

Find this line in Main.py:
```python
from models import WeatherData, User, LoginForm
```

Change it to:
```python
from models import WeatherData, User, LoginForm, BackupCode, FailedTOTPAttempt
from two_factor_auth import TwoFactorAuth
```

Also make sure you have this import (should already be there):
```python
from flask import session  # Add 'session' if not already imported
```

### 3B. Replace the login() function

Find your current `login()` function (around line 186) and replace it with this:

```python
@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """
    Handles user login. Validates credentials against hashed passwords
    stored in the database using bcrypt. Redirects to 2FA if enabled.
    """
    logger.info(f"Login attempt from {get_remote_address()}")
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            pw_match = bcrypt.checkpw(form.password.data.encode('utf-8'), 
                                      user.password_hash.encode('utf-8') if isinstance(user.password_hash, str) else user.password_hash)
            if pw_match:
                # Check if 2FA is enabled
                if user.two_fa_enabled:
                    # Store user ID in session temporarily
                    session['pending_2fa_user_id'] = user.id
                    logger.info(f"User {form.username.data} requires 2FA")
                    return redirect(url_for('verify_2fa'))
                else:
                    # No 2FA, log in directly
                    login_user(user, remember=True)
                    logger.info(f"User {form.username.data} logged in")
                    return redirect(url_for('dashboard'))
            else:
                app.logger.warning(f"Login failed: Invalid password for user {form.username.data}")
        else:
            app.logger.warning(f"Login failed: User not found {form.username.data}")
        flash('Invalid username or password')
    return render_template('login.html', form=form)
```

### 3C. Add new 2FA routes

Add these routes AFTER the logout() function (around line 210):

```python
@app.route('/verify-2fa', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_2fa():
    """
    Verify the 2FA code after successful password login.
    Accepts both TOTP codes and backup codes.
    """
    user_id = session.get('pending_2fa_user_id')
    if not user_id:
        flash('Session expired. Please log in again.')
        return redirect(url_for('login'))
    
    user = User.query.get(user_id)
    if not user or not user.two_fa_enabled:
        session.pop('pending_2fa_user_id', None)
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        
        if not code:
            flash('Please enter a code')
            return render_template('verify_2fa.html')
        
        success, message, locked_out = TwoFactorAuth.verify_totp(user, code, allow_backup=True)
        
        if success:
            session.pop('pending_2fa_user_id', None)
            login_user(user, remember=True)
            logger.info(f"User {user.username} verified 2FA and logged in")
            flash('Successfully logged in!', 'success')
            return redirect(url_for('dashboard'))
        else:
            logger.warning(f"Failed 2FA attempt for user {user.username}: {message}")
            if locked_out:
                session.pop('pending_2fa_user_id', None)
                flash(message, 'error')
                return redirect(url_for('login'))
            else:
                flash(message, 'error')
    
    return render_template('verify_2fa.html', username=user.username)


@app.route('/setup-2fa', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per minute")
def setup_2fa():
    """Setup 2FA for the current user"""
    if current_user.two_fa_enabled:
        flash('2FA is already enabled', 'info')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        code = request.form.get('code')
        
        if code:
            success, message, _ = TwoFactorAuth.verify_totp(current_user, code, allow_backup=False)
            
            if success:
                current_user.two_fa_enabled = True
                db.session.commit()
                logger.info(f"User {current_user.username} enabled 2FA")
                flash('2FA has been successfully enabled!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash(f'Verification failed: {message}', 'error')
                qr_data = TwoFactorAuth.generate_qr_code(current_user)
                backup_codes = session.get('backup_codes_to_show', [])
                return render_template('setup_2fa.html', 
                                     qr_code=qr_data['qr_code_base64'],
                                     secret=qr_data['secret'],
                                     backup_codes=backup_codes)
        else:
            setup_data = TwoFactorAuth.enable_2fa(current_user)
            session['backup_codes_to_show'] = setup_data['backup_codes']
            
            return render_template('setup_2fa.html',
                                 qr_code=setup_data['qr_data']['qr_code_base64'],
                                 secret=setup_data['qr_data']['secret'],
                                 backup_codes=setup_data['backup_codes'])
    
    if not current_user.two_fa_secret:
        setup_data = TwoFactorAuth.enable_2fa(current_user)
        session['backup_codes_to_show'] = setup_data['backup_codes']
        
        return render_template('setup_2fa.html',
                             qr_code=setup_data['qr_data']['qr_code_base64'],
                             secret=setup_data['qr_data']['secret'],
                             backup_codes=setup_data['backup_codes'])
    else:
        qr_data = TwoFactorAuth.generate_qr_code(current_user)
        backup_codes = session.get('backup_codes_to_show', [])
        return render_template('setup_2fa.html',
                             qr_code=qr_data['qr_code_base64'],
                             secret=qr_data['secret'],
                             backup_codes=backup_codes)


@app.route('/disable-2fa', methods=['POST'])
@login_required
@limiter.limit("5 per minute")
def disable_2fa():
    """Disable 2FA for the current user"""
    if not current_user.two_fa_enabled:
        flash('2FA is not enabled', 'info')
        return redirect(url_for('dashboard'))
    
    TwoFactorAuth.disable_2fa(current_user)
    logger.info(f"User {current_user.username} disabled 2FA")
    flash('2FA has been disabled', 'warning')
    return redirect(url_for('dashboard'))


@app.route('/regenerate-backup-codes', methods=['POST'])
@login_required
@limiter.limit("3 per hour")
def regenerate_backup_codes():
    """Regenerate backup codes"""
    if not current_user.two_fa_enabled:
        flash('2FA is not enabled', 'error')
        return redirect(url_for('dashboard'))
    
    new_codes = TwoFactorAuth.generate_backup_codes(current_user)
    logger.info(f"User {current_user.username} regenerated backup codes")
    
    return render_template('backup_codes.html', backup_codes=new_codes)
```

---

## Step 4: Update database

Run this in your Server directory:

```bash
python
>>> from Main import app, db
>>> with app.app_context():
...     db.create_all()
>>> exit()
```

This creates the new 2FA tables (BackupCode, FailedTOTPAttempt).

---

## Step 5: Create HTML templates

I'll create these templates next to match your dashboard style.

---

## How It Works

### Normal Login (No 2FA):
1. User enters username/password
2. Logs in directly

### Login with 2FA Enabled:
1. User enters username/password
2. Redirected to `/verify-2fa`
3. User enters 6-digit code from Google Authenticator
4. Logged in if code is correct

### Setting Up 2FA:
1. User logs in normally
2. Clicks "Enable 2FA" on dashboard
3. Scans QR code with Google Authenticator app
4. Saves backup codes (shown once!)
5. Enters test code to verify it works
6. 2FA is now active

### Security Features:
- **Rate Limiting**: Max 3 failed 2FA attempts in 15 minutes
- **Lockout**: Account locked for 15 minutes after 3 failures
- **Backup Codes**: 10 one-time use codes in case phone is lost
- **Constant-Time Comparison**: Prevents timing attack vulnerabilities
- **Secure Storage**: All secrets stored encrypted in database

---

## Next Steps

1. Update Main.py as shown above
2. Run database migration
3. I'll create the HTML templates
4. Test it out!

Would you like me to create the HTML templates now?
