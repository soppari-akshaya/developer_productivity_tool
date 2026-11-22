import os
import uuid
from datetime import datetime
import secrets
from urllib.parse import urlencode, urlparse
import requests
from werkzeug.utils import secure_filename
from flask import render_template, request, jsonify, redirect, url_for, session, flash, current_app
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db, csrf
from models import User, GitHubConnection
from integrations.firebase_auth import verify_firebase_token
from . import auth_bp
from .services import get_dashboard_url_for_role, create_user_profile, log_activity

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(get_dashboard_url_for_role(current_user.role))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember_me = 'remember_me' in request.form or request.form.get('remember-me') == 'on'

        if not email or not password:
            flash('Please enter both email and password.', 'danger')
            return render_template('login.html', page_title='Sign In - Developer Productivity Tool')

        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an Administrator.', 'danger')
                return render_template('login.html', page_title='Sign In - Developer Productivity Tool')

            user.last_login = datetime.utcnow()
            db.session.commit()
            login_user(user, remember=remember_me)
            log_activity(user.id, 'User Login', f'Signed in via email/password ({user.role})', request.remote_addr)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(get_dashboard_url_for_role(user.role))
        else:
            flash('Invalid email address or password. Please try again.', 'danger')
            return render_template('login.html', page_title='Sign In - Developer Productivity Tool', email=email)

    return render_template('login.html', page_title='Sign In - Developer Productivity Tool')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(get_dashboard_url_for_role(current_user.role))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        role = request.form.get('role', 'developer').strip().lower()

        if not full_name or not email or not password or not confirm_password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool')

        # Admin account security: do not allow public registration as Admin
        if role in ['admin', 'administrator', 'superadmin', 'root']:
            flash('Admin registration is restricted. Administrator accounts must be created through secure initial setup or by an existing Admin.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, email=email, role='developer')

        # Backend role validation: allow only Developer or Team Leader
        if role not in ['developer', 'team_leader']:
            flash('Invalid role selected. Please choose Developer or Team Leader.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, email=email, role='developer')

        permitted_role = role

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, email=email, role=permitted_role)

        if password != confirm_password:
            flash('Passwords do not match. Please retype your password.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, email=email, role=permitted_role)

        existing = User.query.filter_by(email=email).first()
        if existing:
            flash('An account with this email address already exists. Please sign in instead.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, role=permitted_role)

        new_user = User(
            firebase_uid=None,
            email=email,
            full_name=full_name,
            role=permitted_role,
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        new_user.set_password(password)

        try:
            db.session.add(new_user)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Registration database error: {e}")
            flash('A database error occurred while registering your account. Please try again.', 'danger')
            return render_template('register.html', page_title='Create Account - Developer Productivity Tool', full_name=full_name, email=email, role=permitted_role)

        login_user(new_user, remember=True)
        log_activity(new_user.id, 'User Registration', f'Created account with role {permitted_role}', request.remote_addr)
        flash('Account registered successfully! Welcome to your workspace.', 'success')
        return redirect(get_dashboard_url_for_role(new_user.role))

    return render_template('register.html', page_title='Create Account - Developer Productivity Tool')

@auth_bp.route('/forgot-password', methods=['GET'])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(get_dashboard_url_for_role(current_user.role))
    return render_template('forgot_password.html', page_title='Reset Password - Developer Productivity Tool')

@auth_bp.route('/auth/onboarding', methods=['GET'])
def onboarding():
    # Role selection for first-time OAuth users
    pending = session.get('pending_oauth_user')
    if not pending:
        if current_user.is_authenticated:
            return redirect(get_dashboard_url_for_role(current_user.role))
        flash('No pending authentication found. Please sign in.', 'info')
        return redirect(url_for('auth.login'))

    return render_template(
        'onboarding.html',
        page_title='Complete Onboarding - Developer Productivity Tool',
        pending_user=pending
    )

@auth_bp.route('/auth/verify-token', methods=['POST'])
@csrf.exempt
def verify_token():
    """
    Receives the Firebase ID token from the frontend.
    Verifies it on backend using Firebase Admin SDK.
    Establishes secure Flask session and redirects according to role.
    """
    data = request.get_json() or {}
    id_token = data.get('idToken')
    remember_me = data.get('rememberMe', True)
    client_role = data.get('role')  # Sent during registration
    client_name = data.get('fullName')

    if not id_token:
        return jsonify({'status': 'error', 'message': 'Missing Firebase ID token.'}), 400

    try:
        token_data = verify_firebase_token(id_token)
    except Exception as e:
        current_app.logger.error(f"Token verification failed: {e}")
        return jsonify({'status': 'error', 'message': f'Authentication verification error: {str(e)}'}), 401

    firebase_uid = token_data.get('uid')
    email = token_data.get('email', '').strip().lower()
    name = client_name or token_data.get('name') or email.split('@')[0].capitalize()
    picture = token_data.get('picture', '')

    if not firebase_uid:
        return jsonify({'status': 'error', 'message': 'Invalid token claims: missing UID.'}), 400

    # 1. Lookup user in SQLite
    user = User.query.filter_by(firebase_uid=firebase_uid).first()

    # 2. Lookup by email if UID changed or linking
    if not user and email:
        user = User.query.filter_by(email=email).first()
        if user:
            user.firebase_uid = firebase_uid
            db.session.commit()

    # 3. Existing User -> Log in and redirect to their saved role dashboard
    if user:
        if not user.is_active:
            return jsonify({'status': 'error', 'message': 'Your account has been deactivated. Please contact an Administrator.'}), 403

        user.last_login = datetime.utcnow()
        if picture and not user.photo_url:
            user.photo_url = picture
        db.session.commit()

        login_user(user, remember=remember_me)
        log_activity(user.id, 'User Login', f'Signed in via Firebase ({user.role})', request.remote_addr)

        dashboard_url = get_dashboard_url_for_role(user.role)
        return jsonify({
            'status': 'success',
            'role': user.role,
            'redirect': dashboard_url,
            'userName': user.full_name
        }), 200

    # 4. New Registration with designated role (From registration form)
    if client_role in ['developer', 'team_leader']:
        new_user = create_user_profile(
            firebase_uid=firebase_uid,
            email=email,
            full_name=name,
            role=client_role,
            photo_url=picture
        )
        login_user(new_user, remember=remember_me)
        log_activity(new_user.id, 'User Registration', f'Created account with role {client_role}', request.remote_addr)

        return jsonify({
            'status': 'success',
            'role': new_user.role,
            'redirect': get_dashboard_url_for_role(new_user.role),
            'userName': new_user.full_name
        }), 200

    # 5. First-time OAuth user without a role -> route to Onboarding step
    session['pending_oauth_user'] = {
        'firebase_uid': firebase_uid,
        'email': email,
        'full_name': name,
        'picture': picture,
        'remember_me': remember_me
    }

    return jsonify({
        'status': 'onboarding_required',
        'redirect': url_for('auth.onboarding')
    }), 200

@auth_bp.route('/auth/complete-onboarding', methods=['POST'])
@csrf.exempt
def complete_onboarding():
    pending = session.get('pending_oauth_user')
    if not pending:
        return jsonify({'status': 'error', 'message': 'Session expired. Please sign in again.'}), 400

    data = request.get_json() or {}
    chosen_role = data.get('role', 'developer')
    full_name = data.get('fullName', pending.get('full_name', 'Developer'))

    if chosen_role not in ['developer', 'team_leader']:
        chosen_role = 'developer'

    new_user = create_user_profile(
        firebase_uid=pending.get('firebase_uid'),
        email=pending['email'],
        full_name=full_name,
        role=chosen_role,
        photo_url=pending.get('picture', '')
    )

    # If user registered via GitHub OAuth, store GitHubConnection
    if pending.get('provider') == 'github' and pending.get('github_username'):
        new_conn = GitHubConnection(
            user_id=new_user.id,
            github_username=pending['github_username'],
            access_token=pending.get('access_token'),
            avatar_url=pending.get('picture', '')
        )
        db.session.add(new_conn)
        db.session.commit()

    login_user(new_user, remember=pending.get('remember_me', True))
    log_activity(new_user.id, 'OAuth Onboarding Completed', f'Assigned role {chosen_role}', request.remote_addr)

    session.pop('pending_oauth_user', None)

    return jsonify({
        'status': 'success',
        'role': new_user.role,
        'redirect': get_dashboard_url_for_role(new_user.role)
    }), 200

# =========================================================================
# Direct GitHub OAuth Flow (Secure Server-Side Exchange)
# =========================================================================

@auth_bp.route('/auth/github/login', methods=['GET'])
def github_login():
    """
    Initiates GitHub OAuth Authorization Flow.
    Redirects user to GitHub with client_id, scope, and CSRF state token.
    """
    if current_user.is_authenticated:
        return redirect(get_dashboard_url_for_role(current_user.role))

    client_id = (current_app.config.get('GITHUB_CLIENT_ID') or '').strip().strip('"\'')
    client_secret = (current_app.config.get('GITHUB_CLIENT_SECRET') or '').strip().strip('"\'')
    callback_url = (current_app.config.get('GITHUB_CALLBACK_URL') or '').strip().strip('"\'')

    if not client_id or not client_secret:
        flash(
            'GitHub OAuth is not configured: GITHUB_CLIENT_ID or GITHUB_CLIENT_SECRET is missing. Please set them in your .env file.',
            'warning'
        )
        return redirect(url_for('auth.login'))

    if not callback_url:
        flash(
            'GitHub OAuth is not configured: GITHUB_CALLBACK_URL is missing. Please set GITHUB_CALLBACK_URL in your .env file.',
            'warning'
        )
        return redirect(url_for('auth.login'))

    # Ensure browser host matches configured callback URL host so OAuth state session cookies persist
    parsed_cb = urlparse(callback_url)
    cb_hostname = parsed_cb.hostname or ''
    current_hostname = request.host.split(':')[0]
    if cb_hostname and current_hostname.lower() != cb_hostname.lower():
        # Redirect to the same hostname as the configured callback URL
        aligned_url = f"{parsed_cb.scheme}://{parsed_cb.netloc}{request.full_path}"
        return redirect(aligned_url)

    state = secrets.token_urlsafe(32)
    session['github_oauth_state'] = state

    # Capture optional role if initiated from register page
    role = request.args.get('role')
    if role in ['developer', 'team_leader']:
        session['oauth_register_role'] = role

    params = {
        'client_id': client_id,
        'redirect_uri': callback_url,
        'scope': 'user:email read:user',
        'state': state
    }
    github_auth_url = f"https://github.com/login/oauth/authorize?{urlencode(params)}"
    return redirect(github_auth_url)


@auth_bp.route('/auth/github/callback', methods=['GET'])
def github_callback():
    """
    Handles GitHub OAuth Callback.
    Exchanges code for access token, retrieves user profile, links or creates SQLite user.
    """
    if current_user.is_authenticated:
        return redirect(get_dashboard_url_for_role(current_user.role))

    # 1. Check for error returned by GitHub (e.g. user cancelled)
    error = request.args.get('error')
    if error:
        error_desc = request.args.get('error_description', 'Authorization was denied or cancelled.')
        flash(f'GitHub sign-in was cancelled: {error_desc}', 'warning')
        return redirect(url_for('auth.login'))

    # 2. Validate state token
    returned_state = request.args.get('state')
    saved_state = session.pop('github_oauth_state', None)
    if not returned_state or not saved_state or returned_state != saved_state:
        flash('Invalid OAuth state. Please try again.', 'danger')
        return redirect(url_for('auth.login'))

    # 3. Check authorization code
    code = request.args.get('code')
    if not code:
        flash('Missing authorization code from GitHub.', 'danger')
        return redirect(url_for('auth.login'))

    client_id = (current_app.config.get('GITHUB_CLIENT_ID') or '').strip().strip('"\'')
    client_secret = (current_app.config.get('GITHUB_CLIENT_SECRET') or '').strip().strip('"\'')
    callback_url = (current_app.config.get('GITHUB_CALLBACK_URL') or '').strip().strip('"\'')

    if not callback_url:
        flash('GitHub OAuth is not configured: GITHUB_CALLBACK_URL is missing.', 'danger')
        return redirect(url_for('auth.login'))

    try:
        # 4. Exchange code for access token
        token_res = requests.post(
            'https://github.com/login/oauth/access_token',
            headers={'Accept': 'application/json'},
            data={
                'client_id': client_id,
                'client_secret': client_secret,
                'code': code,
                'redirect_uri': callback_url
            },
            timeout=10
        )
        token_data = token_res.json()
        access_token = token_data.get('access_token')

        if not access_token:
            err_msg = token_data.get('error_description') or token_data.get('error') or 'Failed to obtain access token from GitHub.'
            flash(f'GitHub authentication failed: {err_msg}', 'danger')
            return redirect(url_for('auth.login'))

        # 5. Fetch GitHub profile
        gh_headers = {
            'Authorization': f'Bearer {access_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'DeveloperProductivityTool'
        }
        user_res = requests.get('https://api.github.com/user', headers=gh_headers, timeout=10)
        if user_res.status_code != 200:
            flash('Failed to retrieve GitHub user profile. Please try again.', 'danger')
            return redirect(url_for('auth.login'))

        gh_profile = user_res.json()
        github_username = gh_profile.get('login')
        full_name = gh_profile.get('name') or github_username
        email = (gh_profile.get('email') or '').strip().lower()
        avatar_url = gh_profile.get('avatar_url') or ''

        # 6. If email is not public, fetch verified emails from GitHub
        if not email:
            emails_res = requests.get('https://api.github.com/user/emails', headers=gh_headers, timeout=10)
            if emails_res.status_code == 200:
                emails_data = emails_res.json()
                for em in emails_data:
                    if em.get('primary') and em.get('verified'):
                        email = em.get('email', '').strip().lower()
                        break
                if not email:
                    for em in emails_data:
                        if em.get('verified'):
                            email = em.get('email', '').strip().lower()
                            break

        if not email:
            email = f"{github_username.lower()}@users.noreply.github.com"

        # 7. Check if user already exists in SQLite (by GitHubConnection or by Email)
        gh_conn = GitHubConnection.query.filter_by(github_username=github_username).first()
        user = gh_conn.user if gh_conn else None

        if not user and email:
            user = User.query.filter_by(email=email).first()

        # 8. Existing User -> Link/Update GitHub connection & Log In (Preserves existing role!)
        if user:
            if not user.is_active:
                flash('Your account has been deactivated. Please contact an Administrator.', 'danger')
                return redirect(url_for('auth.login'))

            if not user.github_connection:
                new_conn = GitHubConnection(
                    user_id=user.id,
                    github_username=github_username,
                    access_token=access_token,
                    avatar_url=avatar_url
                )
                db.session.add(new_conn)
            else:
                user.github_connection.access_token = access_token
                user.github_connection.avatar_url = avatar_url
                user.github_connection.connected_at = datetime.utcnow()

            if avatar_url and not user.photo_url:
                user.photo_url = avatar_url
            user.last_login = datetime.utcnow()
            db.session.commit()

            # Preserve role!
            login_user(user, remember=True)
            log_activity(user.id, 'User Login', f'Signed in via GitHub OAuth ({user.role})', request.remote_addr)
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(get_dashboard_url_for_role(user.role))

        # 9. New User -> Check if role was designated on registration page
        chosen_role = session.pop('oauth_register_role', None)
        if chosen_role in ['developer', 'team_leader']:
            new_user = create_user_profile(
                email=email,
                full_name=full_name,
                role=chosen_role,
                photo_url=avatar_url
            )
            new_conn = GitHubConnection(
                user_id=new_user.id,
                github_username=github_username,
                access_token=access_token,
                avatar_url=avatar_url
            )
            db.session.add(new_conn)
            db.session.commit()

            login_user(new_user, remember=True)
            log_activity(new_user.id, 'User Registration', f'Created account via GitHub OAuth with role {chosen_role}', request.remote_addr)
            flash(f'Account created successfully! Welcome, {new_user.full_name}.', 'success')
            return redirect(get_dashboard_url_for_role(new_user.role))

        # 10. New OAuth user without role -> route to Onboarding
        session['pending_oauth_user'] = {
            'provider': 'github',
            'github_username': github_username,
            'access_token': access_token,
            'email': email,
            'full_name': full_name,
            'picture': avatar_url,
            'remember_me': True
        }
        return redirect(url_for('auth.onboarding'))

    except requests.RequestException as req_err:
        current_app.logger.error(f"GitHub OAuth network error: {req_err}")
        flash('Network error connecting to GitHub. Please check your internet connection.', 'danger')
        return redirect(url_for('auth.login'))
    except Exception as e:
        current_app.logger.error(f"GitHub OAuth error: {e}")
        flash(f'GitHub authentication error: {str(e)}', 'danger')
        return redirect(url_for('auth.login'))

# =========================================================================
# Logout Route (Strict POST & Session Teardown)
# =========================================================================

@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    """
    Clears the authenticated user session using Flask-Login and session.clear().
    Redirects to the login page with a success message.
    Sets anti-cache headers preventing back navigation access to protected pages.
    """
    if current_user.is_authenticated:
        log_activity(current_user.id, 'User Logout', 'Signed out from session', request.remote_addr)
        logout_user()
    session.clear()
    flash('You have been successfully logged out.', 'success')
    response = redirect(url_for('auth.login'))
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.delete_cookie(current_app.config.get('SESSION_COOKIE_NAME', 'session'), path='/')
    response.delete_cookie(current_app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'), path='/')
    return response

# =========================================================================
# Initial Admin Setup (One-Time Creation)
# =========================================================================

@auth_bp.route('/setup-admin', methods=['GET', 'POST'])
def setup_admin():
    """
    Secure setup route to initialize the primary administrator account.
    If an admin already exists in the SQLite database, this route safely denies
    access and redirects back to the login page.
    """
    admin_exists = User.query.filter(db.func.lower(User.role) == 'admin').first() is not None
    if admin_exists:
        flash('An administrator account already exists. Please sign in.', 'info')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not email or not password or not confirm_password:
            flash('Please fill in all required fields.', 'danger')
            return render_template('setup_admin.html', page_title='Initial Admin Setup - Developer Productivity Tool')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return render_template('setup_admin.html', page_title='Initial Admin Setup - Developer Productivity Tool', full_name=full_name, email=email)

        if password != confirm_password:
            flash('Passwords do not match. Please retype your password.', 'danger')
            return render_template('setup_admin.html', page_title='Initial Admin Setup - Developer Productivity Tool', full_name=full_name, email=email)

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            # Promote existing user to admin
            existing_user.role = 'admin'
            existing_user.full_name = full_name
            existing_user.set_password(password)
            db.session.commit()
            log_activity(existing_user.id, 'Admin Account Initialized', f'Promoted {email} to Administrator via initial setup', request.remote_addr)
            flash('Admin account provisioned successfully! You may now sign in.', 'success')
            return redirect(url_for('auth.login'))

        admin = User(
            email=email,
            full_name=full_name,
            role='admin',
            department='Platform Administration',
            bio='System Administrator and platform steward.',
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()

        log_activity(admin.id, 'Admin Account Created', f'Initial administrator account created ({email})', request.remote_addr)
        flash('Initial administrator account created successfully! Please sign in with your credentials.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('setup_admin.html', page_title='Initial Admin Setup - Developer Productivity Tool')

# =========================================================================
# User Profile Management (Admin, Team Leader, Developer)
# =========================================================================

ALLOWED_PHOTO_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
MAX_PHOTO_SIZE = 5 * 1024 * 1024  # 5MB limit

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_PHOTO_EXTENSIONS

@auth_bp.route('/profile', methods=['GET'])
@login_required
def profile():
    """Renders profile overview and settings for the authenticated user."""
    return render_template('profile.html', page_title='My Profile - Developer Productivity Tool', user=current_user)

@auth_bp.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    """Updates user information (Name, Email, Phone Number, Department, Bio). Roles cannot be self-modified."""
    full_name = request.form.get('full_name', '').strip()
    email = request.form.get('email', '').strip().lower()
    phone_number = request.form.get('phone_number', '').strip()
    department = request.form.get('department', '').strip()
    bio = request.form.get('bio', '').strip()

    if not full_name:
        flash('Full name cannot be empty.', 'danger')
        return redirect(url_for('auth.profile'))

    if not email:
        flash('Email address cannot be empty.', 'danger')
        return redirect(url_for('auth.profile'))

    # Check email uniqueness against other accounts
    existing = User.query.filter(User.email == email, User.id != current_user.id).first()
    if existing:
        flash('That email address is already in use by another account.', 'danger')
        return redirect(url_for('auth.profile'))

    current_user.full_name = full_name
    current_user.email = email
    current_user.phone_number = phone_number
    current_user.department = department
    current_user.bio = bio

    db.session.commit()
    log_activity(current_user.id, 'Profile Updated', 'User updated personal profile information', request.remote_addr)
    flash('Your profile has been updated successfully.', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/profile/photo', methods=['POST'])
@login_required
def upload_photo():
    """Uploads and updates user profile picture with format and size validation."""
    if 'photo' not in request.files:
        flash('No file selected for upload.', 'danger')
        return redirect(url_for('auth.profile'))

    file = request.files['photo']
    if not file or file.filename == '':
        flash('No photo selected.', 'danger')
        return redirect(url_for('auth.profile'))

    if not allowed_file(file.filename):
        flash('Invalid image format. Allowed formats: PNG, JPG, JPEG, WEBP.', 'danger')
        return redirect(url_for('auth.profile'))

    # Check file size (<= 5MB)
    file.seek(0, os.SEEK_END)
    size = file.tell()
    file.seek(0)
    if size > MAX_PHOTO_SIZE:
        flash('Image file is too large. Maximum allowed size is 5MB.', 'danger')
        return redirect(url_for('auth.profile'))

    ext = file.filename.rsplit('.', 1)[1].lower()
    unique_filename = f"{uuid.uuid4().hex}.{ext}"
    profile_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'profile')
    os.makedirs(profile_dir, exist_ok=True)

    dest_path = os.path.join(profile_dir, unique_filename)
    file.save(dest_path)

    current_user.photo_url = f"/uploads/profile/{unique_filename}"
    db.session.commit()

    log_activity(current_user.id, 'Avatar Updated', 'User uploaded a new profile picture', request.remote_addr)
    flash('Profile photo updated successfully!', 'success')
    return redirect(url_for('auth.profile'))

@auth_bp.route('/profile/remove-photo', methods=['POST'])
@login_required
def remove_photo():
    """Removes the current user's profile picture and resets to default avatar."""
    current_user.photo_url = None
    db.session.commit()
    log_activity(current_user.id, 'Avatar Removed', 'User reset profile picture to default initials', request.remote_addr)
    flash('Profile photo removed. Default initials avatar will be displayed.', 'info')
    return redirect(url_for('auth.profile'))

