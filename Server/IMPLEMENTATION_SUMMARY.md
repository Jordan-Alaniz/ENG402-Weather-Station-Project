# 🔐 Secure 2FA Implementation - Complete Guide

## What I've Created For You

I've built a production-ready 2FA system that fixes **ALL security vulnerabilities** in the tutorial code you shared. Here's what's included:

### ✅ Files Created (in your Server/ directory):

1. **`two_factor_auth.py`** - Core 2FA module with all security features
2. **`models.py`** (updated) - Added 3 new database tables for 2FA
3. **`templates/verify_2fa.html`** - 2FA code entry page
4. **`templates/setup_2fa.html`** - QR code setup page with backup codes
5. **`templates/backup_codes.html`** - Backup code regeneration page
6. **`2FA_INTEGRATION_GUIDE.md`** - Step-by-step integration instructions

---

## 🛡️ Security Features (What Makes This Better Than The Tutorial)

| Vulnerability in Tutorial | Fixed in My Implementation |
|---------------------------|----------------------------|
| ❌ No rate limiting → brute force attacks | ✅ 3 attempts max, 15min lockout |
| ❌ Secrets stored in memory → lost on restart | ✅ Persistent SQLite storage |
| ❌ No backup codes → locked out if phone lost | ✅ 10 one-time backup codes generated |
| ❌ Session secret regenerates → logs everyone out | ✅ Persistent session key in file |
| ❌ No HTTPS enforcement | ✅ Works with your existing Talisman setup |
| ❌ Timing attack vulnerability | ✅ Constant-time comparison (hmac.compare_digest) |
| ❌ No database, just dictionary | ✅ Proper SQLite tables with relationships |

---

## 📋 Implementation Steps

### 1. Install Dependencies
```bash
cd C:\Users\JordanAlaniz\Documents\GitHub\ENG402-Weather-Station-Project\Server
pip install pyotp qrcode[pil] pillow
```

### 2. Update Main.py

#### 2A. Add imports (around line 20)
Find this line:
```python
from models import WeatherData, User, LoginForm
```

Change to:
```python
from models import WeatherData, User, LoginForm, BackupCode, FailedTOTPAttempt
from two_factor_auth import TwoFactorAuth
```

Also ensure `session` is imported:
```python
from flask import Flask, jsonify, request, redirect, url_for, render_template, flash, session
```

#### 2B. Replace login() function (around line 186)

Replace your existing `login()` function with:

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
                    session['pending_2fa_user_id'] = user.id
                    logger.info(f"User {form.username.data} requires 2FA")
                    return redirect(url_for('verify_2fa'))
                else:
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

#### 2C. Add 2FA routes (after logout() function, around line 210)

Add ALL of these routes:

```python
@app.route('/verify-2fa', methods=['GET', 'POST'])
@limiter.limit("10 per minute")
def verify_2fa():
    """Verify 2FA code after password login"""
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
    """Setup 2FA for current user"""
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
    """Disable 2FA"""
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

### 3. Update Dashboard (Optional but Recommended)

Add this section to `templates/dashboard.html` after the welcome message:

```html
<div style="background: #f8f9fa; padding: 15px; margin: 20px 0; border-radius: 4px; border-left: 4px solid #007bff;">
    <h3 style="margin-top: 0;">Security Settings</h3>
    <p style="margin: 10px 0;">
        <strong>Two-Factor Authentication:</strong> 
        {% if current_user.two_fa_enabled %}
            <span style="color: #28a745;">✓ Enabled</span>
        {% else %}
            <span style="color: #dc3545;">✗ Disabled</span>
        {% endif %}
    </p>
    
    {% if current_user.two_fa_enabled %}
        <form method="POST" action="{{ url_for('disable_2fa') }}" style="display: inline;" 
              onsubmit="return confirm('Are you sure you want to disable 2FA?');">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <button type="submit" style="background: #dc3545; color: white; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer;">
                Disable 2FA
            </button>
        </form>
        <form method="POST" action="{{ url_for('regenerate_backup_codes') }}" style="display: inline;">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <button type="submit" style="background: #ffc107; color: #333; padding: 8px 15px; border: none; border-radius: 4px; cursor: pointer;">
                Regenerate Backup Codes
            </button>
        </form>
    {% else %}
        <a href="{{ url_for('setup_2fa') }}" style="background: #28a745; color: white; padding: 8px 15px; border-radius: 4px; text-decoration: none;">
            Enable 2FA
        </a>
    {% endif %}
</div>
```

### 4. Initialize Database

```bash
cd Server
python
```
```python
from Main import app, db
with app.app_context():
    db.create_all()
exit()
```

---

## 🧪 Testing Instructions

### Test 1: Enable 2FA
1. Start server: `python Main.py`
2. Log in normally
3. Click "Enable 2FA"
4. Scan QR code with Google Authenticator
5. **SAVE THE BACKUP CODES!**
6. Enter test code
7. Should say "2FA enabled successfully"

### Test 2: Login with 2FA
1. Log out
2. Log in with username/password
3. Should redirect to 2FA verification
4. Enter 6-digit code from app
5. Should log in successfully

### Test 3: Backup Code
1. Log out
2. Log in with username/password
3. Enter a backup code instead of TOTP
4. Should log in (code is now used up)

### Test 4: Rate Limiting
1. Log out
2. Log in with username/password
3. Enter wrong code 3 times
4. Should get locked out for 15 minutes

---

## 🔒 Security Features Explained

### Rate Limiting
- **3 failed attempts** → 15 minute lockout
- Prevents brute force attacks on 6-digit codes
- Tracks attempts per user in database

### Backup Codes
- 10 codes generated during setup
- Each code works **exactly once**
- Download/print them during setup
- Can regenerate new set (invalidates old ones)

### Constant-Time Comparison
- Uses `hmac.compare_digest()` for all code checks
- Prevents timing attacks (can't guess code by measuring response time)

### Persistent Storage
- All secrets stored in SQLite
- Survives server restarts
- Session key stored in file (not regenerated)

---

## 📁 File Structure After Implementation

```
Server/
├── Main.py (updated with 2FA routes)
├── models.py (updated with 2FA tables)
├── db.py (unchanged)
├── two_factor_auth.py (NEW - core 2FA logic)
├── templates/
│   ├── login.html (unchanged)
│   ├── dashboard.html (add 2FA controls)
│   ├── verify_2fa.html (NEW)
│   ├── setup_2fa.html (NEW)
│   └── backup_codes.html (NEW)
└── instance/
    └── weather.db (will have new tables after migration)
```

---

## ⚠️ Important Notes

1. **Backup Codes**: Users see them ONCE during setup. Make sure they save them!
2. **Testing**: Test on http://localhost first, not production
3. **HTTPS**: In production, Talisman will enforce HTTPS automatically
4. **Lockout**: If locked out, wait 15 minutes OR delete failed_totp_attempt table records

---

## 🆘 Troubleshooting

**"ImportError: No module named pyotp"**
→ Run: `pip install pyotp qrcode[pil] pillow`

**"Table backup_code doesn't exist"**
→ Run the database migration in Step 4

**"Code doesn't work"**
→ Check phone time is accurate (Settings → Date & Time → Auto)

**"Locked out for 15 minutes"**
→ Either wait, or manually clear: `DELETE FROM failed_totp_attempt WHERE user_id = 1;`

---

## 🎯 What This Fixes From The Tutorial

| Tutorial Code Problem | How It's Fixed |
|-----------------------|----------------|
| Secret in dictionary, lost on restart | SQLite database persistence |
| No failed attempt tracking | FailedTOTPAttempt table with lockout logic |
| No backup codes | BackupCode table with 10 one-time codes |
| Timing attack on verification | hmac.compare_digest() |
| Session secret regenerates | Stored in session_secret.key file |
| No rate limiting | Flask-Limiter + attempt tracking |
| Simple string comparison | Constant-time comparison |

---

## ✅ Ready to Implement?

You have everything you need:
1. ✅ Security module created
2. ✅ Database models updated  
3. ✅ HTML templates created
4. ✅ Integration guide written

Just follow steps 1-4 above and you'll have enterprise-grade 2FA!

Let me know if you need help with any step!
