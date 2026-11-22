from functools import wraps
from flask import abort, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please sign in to access this workspace.'
login_manager.login_message_category = 'warning'

def normalize_role(role) -> str:
    """
    Standardize role values across uppercase, lowercase, spaces, and hyphens.
    Returns: 'admin', 'team_leader', or 'developer'
    """
    if not role:
        return 'developer'
    r = str(role).strip().lower().replace(' ', '_').replace('-', '_')
    if r in ('admin', 'administrator'):
        return 'admin'
    if r in ('team_leader', 'teamleader', 'leader', 'team_lead'):
        return 'team_leader'
    return 'developer'

def role_required(*roles):
    """
    Decorator to restrict route access to specific roles.
    Supported roles: 'admin', 'team_leader', 'developer'
    """
    normalized_allowed = [normalize_role(r) for r in roles]
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return login_manager.unauthorized()
            
            user_role = normalize_role(current_user.role)
            if user_role not in normalized_allowed:
                flash(f'Access denied. Your role ({user_role.replace("_", " ").title()}) does not have permission to view that resource.', 'danger')
                if user_role == 'admin':
                    return redirect(url_for('admin.dashboard'))
                elif user_role == 'team_leader':
                    return redirect(url_for('team_leader.dashboard'))
                else:
                    return redirect(url_for('developer.dashboard'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

