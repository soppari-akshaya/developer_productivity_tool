import os
import click
from datetime import datetime, date
from flask import Flask, render_template, redirect, url_for, request, send_from_directory, flash, session
from config import Config
from extensions import db, login_manager, csrf, normalize_role
from models import User, Project, ProjectMember, Task, CodeSnippet, Notification, ActivityLog
from integrations.firebase_auth import init_firebase_admin

# Import Blueprints
from auth import auth_bp
from admin import admin_bp
from team_leader import team_leader_bp
from developer import developer_bp
from projects import projects_bp
from tasks import tasks_bp
from snippets import snippets_bp
from issues import issues_bp
from reports import reports_bp

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Ensure instance and upload directories exist
    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'profile'), exist_ok=True)
    os.makedirs(os.path.join(app.root_path, 'secrets'), exist_ok=True)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Initialize Firebase Admin SDK
    init_firebase_admin(app)

    # User Loader for Flask-Login
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(team_leader_bp)
    app.register_blueprint(developer_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(tasks_bp)
    app.register_blueprint(snippets_bp)
    app.register_blueprint(issues_bp)
    app.register_blueprint(reports_bp)

    # Root redirect
    @app.route('/')
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            role = normalize_role(current_user.role)
            if role == 'admin':
                return redirect(url_for('admin.dashboard'))
            elif role == 'team_leader':
                return redirect(url_for('team_leader.dashboard'))
            else:
                return redirect(url_for('developer.dashboard'))
        return redirect(url_for('auth.login'))

    # Serve user uploaded files safely
    @app.route('/uploads/<path:filename>')
    def uploaded_file(filename):
        return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

    # Global Template Context Processor
    @app.context_processor
    def inject_global_vars():
        from flask_login import current_user
        unread_count = 0
        if current_user.is_authenticated:
            try:
                unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            except Exception:
                unread_count = 0

        # Public Firebase config injected securely to browser
        firebase_config = {
            'apiKey': app.config.get('FIREBASE_API_KEY', ''),
            'authDomain': app.config.get('FIREBASE_AUTH_DOMAIN', 'developer-productivity-t-73574.firebaseapp.com'),
            'projectId': app.config.get('FIREBASE_PROJECT_ID', 'developer-productivity-t-73574'),
            'storageBucket': app.config.get('FIREBASE_STORAGE_BUCKET', 'developer-productivity-t-73574.firebasestorage.app'),
            'messagingSenderId': app.config.get('FIREBASE_MESSAGING_SENDER_ID', ''),
            'appId': app.config.get('FIREBASE_APP_ID', ''),
            'measurementId': app.config.get('FIREBASE_MEASUREMENT_ID', '')
        }

        return {
            'firebase_config': firebase_config,
            'unread_notifications_count': unread_count,
            'current_year': datetime.utcnow().year
        }

    # Disable browser back caching on sensitive responses
    @app.after_request
    def set_cache_control_headers(response):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response

    # Custom Error Handlers
    from flask_wtf.csrf import CSRFError
    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        from flask_login import logout_user, current_user
        if request.path.endswith('/logout'):
            if current_user.is_authenticated:
                logout_user()
            session.clear()
            flash('You have been successfully logged out.', 'success')
            resp = redirect(url_for('auth.login'))
            resp.delete_cookie(app.config.get('SESSION_COOKIE_NAME', 'session'), path='/')
            resp.delete_cookie(app.config.get('REMEMBER_COOKIE_NAME', 'remember_token'), path='/')
            return resp
        flash('Session security validation failed. Please refresh the page and try again.', 'danger')
        return redirect(request.referrer or url_for('auth.login'))

    @app.errorhandler(403)
    def forbidden(e):
        return render_template('base.html', page_title='403 Forbidden', error_code=403, error_message='Access Denied. You do not have permission to access this resource.'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('base.html', page_title='404 Not Found', error_code=404, error_message='The page you requested could not be found.'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('base.html', page_title='500 Internal Server Error', error_code=500, error_message='An unexpected error occurred on the server.'), 500

    # Auto-seed database tables on first launch
    with app.app_context():
        db.create_all()
        seed_database()

    return app

def seed_database():
    """Seeds initial administrative accounts if database is empty."""
    if User.query.first():
        return

    # Seed Admin User
    admin = User(
        email='admin@devproductivity.com',
        full_name='System Administrator',
        role='admin',
        department='Engineering Leadership',
        bio='Platform administrator and architecture steward.',
        is_active=True
    )
    admin.set_password('Admin@12345')

    # Seed Team Leader User
    leader = User(
        email='leader@devproductivity.com',
        full_name='Sarah Jenkins',
        role='team_leader',
        department='Frontend & Core Architecture',
        bio='Engineering Team Lead overseeing development velocity.',
        is_active=True
    )
    leader.set_password('Leader@12345')

    # Seed Developer User
    dev = User(
        email='dev@devproductivity.com',
        full_name='Alex Rivera',
        role='developer',
        department='Full Stack Development',
        bio='Full stack software engineer.',
        is_active=True
    )
    dev.set_password('Dev@12345')

    db.session.add_all([admin, leader, dev])
    db.session.commit()

app = create_app()

@app.cli.command('create-admin')
@click.option('--name', prompt='Admin Full Name', default='System Administrator', help='Full name for the administrator')
@click.option('--email', prompt='Admin Email', help='Email address for the administrator')
@click.option('--password', prompt=True, hide_input=True, confirmation_prompt=True, help='Password for the administrator')
def create_admin_command(name, email, password):
    """Securely creates or provisions an administrator account in the SQLite database."""
    email_clean = email.strip().lower()
    if not email_clean:
        click.secho("Error: Email cannot be empty.", fg="red")
        return

    admin_count = User.query.filter(db.func.lower(User.role) == 'admin').count()
    if admin_count > 0:
        click.secho(f"Notice: {admin_count} Admin account(s) already exist in the database.", fg="yellow")
        if not click.confirm("Do you want to proceed and create another Administrator?", default=False):
            click.secho("Admin creation aborted.", fg="yellow")
            return

    existing = User.query.filter_by(email=email_clean).first()
    if existing:
        click.secho(f"User {email_clean} already exists with role '{existing.role}'. Elevating to Admin...", fg="yellow")
        existing.role = 'admin'
        existing.full_name = name.strip() or existing.full_name
        existing.set_password(password)
        db.session.commit()
        click.secho(f"Success: Account '{email_clean}' is now an Administrator!", fg="green")
        return

    new_admin = User(
        email=email_clean,
        full_name=name.strip() or 'Administrator',
        role='admin',
        is_active=True,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )
    new_admin.set_password(password)
    db.session.add(new_admin)
    db.session.commit()
    click.secho(f"Success: Created Administrator account for '{email_clean}'!", fg="green")

if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'create-admin':
        with app.app_context():
            name = input("Admin Full Name [System Administrator]: ").strip() or "System Administrator"
            email = input("Admin Email: ").strip().lower()
            import getpass
            password = getpass.getpass("Password: ")
            confirm = getpass.getpass("Confirm Password: ")
            if password != confirm:
                print("Error: Passwords do not match.")
                sys.exit(1)
            
            existing = User.query.filter_by(email=email).first()
            if existing:
                existing.role = 'admin'
                existing.full_name = name
                existing.set_password(password)
                db.session.commit()
                print(f"Success: Account '{email}' updated to Admin.")
            else:
                new_admin = User(
                    email=email,
                    full_name=name,
                    role='admin',
                    is_active=True,
                    created_at=datetime.utcnow(),
                    last_login=datetime.utcnow()
                )
                new_admin.set_password(password)
                db.session.add(new_admin)
                db.session.commit()
                print(f"Success: Created Administrator '{email}'.")
        sys.exit(0)

    import socket
    port = int(os.getenv('PORT', 5000))
    s = socket.socket()
    try:
        s.bind(('127.0.0.1', port))
        s.close()
    except OSError:
        port = 5001
    print(f" * Running Developer Productivity Tool on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=True)
