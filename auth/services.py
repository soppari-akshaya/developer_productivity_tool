from datetime import datetime
from flask import url_for
from extensions import db, normalize_role
from models import User, ActivityLog

def get_dashboard_url_for_role(role: str) -> str:
    norm = normalize_role(role)
    if norm == 'admin':
        return url_for('admin.dashboard')
    elif norm == 'team_leader':
        return url_for('team_leader.dashboard')
    elif norm == 'developer':
        return url_for('developer.dashboard')
    return url_for('developer.dashboard')

def create_user_profile(firebase_uid: str = None, email: str = '', full_name: str = '', role: str = 'developer', photo_url: str = None) -> User:
    # Strict validation: admin accounts cannot be self-registered
    sanitized_role = 'developer'
    if role == 'team_leader':
        sanitized_role = 'team_leader'
    elif role == 'admin':
        # Fall back to developer if unauthorized self-assignment attempted
        sanitized_role = 'developer'

    user = User(
        firebase_uid=firebase_uid,
        email=email.strip().lower(),
        full_name=full_name.strip() or 'Developer',
        role=sanitized_role,
        photo_url=photo_url or '',
        is_active=True,
        created_at=datetime.utcnow(),
        last_login=datetime.utcnow()
    )
    db.session.add(user)
    db.session.commit()
    return user

def log_activity(user_id: int, action: str, details: str = None, ip_address: str = None):
    try:
        log = ActivityLog(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=ip_address
        )
        db.session.add(log)
        db.session.commit()
    except Exception as e:
        db.session.rollback()

