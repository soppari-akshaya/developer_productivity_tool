from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db, role_required
from models import User, Project, Task, ActivityLog, Issue, WorkLog
from . import admin_bp

@admin_bp.route('/admin/dashboard')
@login_required
@role_required('admin')
def dashboard():
    total_users = User.query.count()
    total_developers = User.query.filter_by(role='developer').count()
    total_team_leaders = User.query.filter_by(role='team_leader').count()
    total_admins = User.query.filter_by(role='admin').count()
    active_users = User.query.filter_by(is_active=True).count()
    inactive_users = User.query.filter_by(is_active=False).count()

    total_projects = Project.query.count()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()

    recent_activities = ActivityLog.query.order_by(ActivityLog.created_at.desc()).limit(8).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(6).all()

    return render_template(
        'admin/dashboard.html',
        page_title='Admin Dashboard - Developer Productivity Tool',
        total_users=total_users,
        total_developers=total_developers,
        total_team_leaders=total_team_leaders,
        total_admins=total_admins,
        active_users=active_users,
        inactive_users=inactive_users,
        total_projects=total_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        recent_activities=recent_activities,
        recent_users=recent_users
    )

@admin_bp.route('/admin/create-team-leader', methods=['GET', 'POST'])
@login_required
@role_required('admin')
def create_team_leader():
    """
    Administrative provisioning endpoint to create Team Leader accounts.
    Only authenticated Admin users can access this route.
    """
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        department = request.form.get('department', '').strip() or 'Engineering'

        if not full_name or not email or not password:
            flash('Please provide Full Name, Email, and Password for the Team Leader.', 'danger')
            return redirect(request.referrer or url_for('admin.dashboard'))

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'danger')
            return redirect(request.referrer or url_for('admin.dashboard'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash(f'An account with email {email} already exists (Current role: {existing_user.role_title}).', 'danger')
            return redirect(request.referrer or url_for('admin.dashboard'))

        new_tl = User(
            firebase_uid=None,
            email=email,
            full_name=full_name,
            role='team_leader',
            department=department,
            is_active=True,
            created_at=datetime.utcnow(),
            last_login=datetime.utcnow()
        )
        new_tl.set_password(password)

        try:
            db.session.add(new_tl)
            db.session.commit()

            from auth.services import log_activity
            log_activity(
                current_user.id,
                'Team Leader Created',
                f'Admin created Team Leader account for {email} ({full_name}) in {department}',
                request.remote_addr
            )
            flash(f'Team Leader account for {full_name} ({email}) created successfully!', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Database error creating Team Leader: {str(e)}', 'danger')

        return redirect(url_for('admin.dashboard'))

    return render_template(
        'admin/create_team_leader.html',
        page_title='Create Team Leader - Admin Dashboard'
    )

@admin_bp.route('/admin/users')
@login_required
@role_required('admin')
def users():
    role_filter = request.args.get('role', 'all')
    search_query = request.args.get('q', '').strip()

    query = User.query
    if role_filter != 'all':
        query = query.filter_by(role=role_filter)
    if search_query:
        query = query.filter((User.full_name.ilike(f'%{search_query}%')) | (User.email.ilike(f'%{search_query}%')))

    users_list = query.order_by(User.created_at.desc()).all()
    return render_template(
        'admin/users.html',
        page_title='Manage Users - Developer Productivity Tool',
        users_list=users_list,
        role_filter=role_filter,
        search_query=search_query
    )

@admin_bp.route('/admin/users/<int:user_id>/update-role', methods=['POST'])
@login_required
@role_required('admin')
def update_user_role(user_id):
    user = db.get_or_404(User, user_id)
    new_role = request.form.get('role')

    if new_role not in ['admin', 'team_leader', 'developer']:
        flash('Invalid role selected.', 'danger')
        return redirect(url_for('admin.users'))

    if user.id == current_user.id and new_role != 'admin':
        flash('You cannot remove your own admin privileges.', 'warning')
        return redirect(url_for('admin.users'))

    old_role = user.role
    user.role = new_role
    db.session.commit()

    flash(f"Updated role for {user.full_name} from {old_role.title()} to {new_role.title()}.", 'success')
    return redirect(url_for('admin.users'))

@admin_bp.route('/admin/users/<int:user_id>/toggle-status', methods=['POST'])
@login_required
@role_required('admin')
def toggle_user_status(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == current_user.id:
        flash('You cannot deactivate your own account.', 'warning')
        return redirect(url_for('admin.users'))

    user.is_active = not user.is_active
    db.session.commit()
    status_str = "activated" if user.is_active else "deactivated"
    flash(f"Account for {user.full_name} has been {status_str}.", 'info')
    return redirect(url_for('admin.users'))

@admin_bp.route('/admin/projects')
@login_required
@role_required('admin')
def projects():
    all_projects = Project.query.order_by(Project.created_at.desc()).all()
    return render_template(
        'admin/projects.html',
        page_title='All Projects - Admin Overview',
        projects=all_projects
    )

@admin_bp.route('/admin/reports')
@login_required
@role_required('admin')
def reports():
    total_projects = Project.query.count()
    completed_projects = Project.query.filter_by(status='completed').count()
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()
    total_issues = Issue.query.count()
    resolved_issues = Issue.query.filter_by(status='resolved').count()
    total_work_logs = WorkLog.query.count()

    return render_template(
        'admin/reports.html',
        page_title='System Reports - Admin Overview',
        total_projects=total_projects,
        completed_projects=completed_projects,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        total_issues=total_issues,
        resolved_issues=resolved_issues,
        total_work_logs=total_work_logs
    )

