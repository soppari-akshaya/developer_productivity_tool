from datetime import datetime, date
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db, role_required
from models import User, Project, ProjectMember, Task, WorkLog, Issue
from . import team_leader_bp

@team_leader_bp.route('/team-leader/dashboard')
@login_required
@role_required('team_leader', 'admin')
def dashboard():
    today = date.today()
    
    # Projects created by or associated with this team leader
    managed_projects = Project.query.filter(
        (Project.created_by_id == current_user.id) |
        (Project.members.any(user_id=current_user.id))
    ).all()
    project_ids = [p.id for p in managed_projects]

    active_projects_count = Project.query.filter(Project.id.in_(project_ids), Project.status == 'active').count() if project_ids else 0

    # Team members
    team_members = User.query.filter(
        User.role == 'developer',
        User.is_active == True
    ).all()
    total_team_members = len(team_members)

    # Tasks within managed projects
    tasks_query = Task.query.filter(Task.project_id.in_(project_ids)) if project_ids else Task.query.filter_by(id=-1)
    total_tasks = tasks_query.count()
    completed_tasks = tasks_query.filter_by(status='completed').count()
    pending_tasks = total_tasks - completed_tasks
    overdue_tasks = tasks_query.filter(Task.status != 'completed', Task.deadline < today).count()

    team_productivity = round((completed_tasks / total_tasks * 100), 1) if total_tasks > 0 else 0

    recent_work_logs = WorkLog.query.order_by(WorkLog.created_at.desc()).limit(5).all()
    recent_tasks = tasks_query.order_by(Task.updated_at.desc()).limit(6).all() if project_ids else []
    recent_issues = Issue.query.filter(Issue.project_id.in_(project_ids)).order_by(Issue.created_at.desc()).limit(5).all() if project_ids else []

    return render_template(
        'team_leader/dashboard.html',
        page_title='Team Leader Dashboard - Developer Productivity Tool',
        total_team_members=total_team_members,
        active_projects_count=active_projects_count,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks,
        overdue_tasks=overdue_tasks,
        team_productivity=team_productivity,
        managed_projects=managed_projects,
        team_members=team_members,
        recent_work_logs=recent_work_logs,
        recent_tasks=recent_tasks,
        recent_issues=recent_issues
    )

@team_leader_bp.route('/team-leader/members')
@login_required
@role_required('team_leader', 'admin')
def members():
    developers = User.query.filter_by(role='developer').all()
    return render_template(
        'team_leader/members.html',
        page_title='Team Members - Developer Productivity Tool',
        developers=developers
    )

@team_leader_bp.route('/team-leader/reviews')
@login_required
@role_required('team_leader', 'admin')
def reviews():
    work_logs = WorkLog.query.order_by(WorkLog.date.desc()).all()
    return render_template(
        'team_leader/reviews.html',
        page_title='Work Log Reviews - Developer Productivity Tool',
        work_logs=work_logs
    )

@team_leader_bp.route('/team-leader/reports')
@login_required
@role_required('team_leader', 'admin')
def reports():
    managed_projects = Project.query.filter_by(created_by_id=current_user.id).all()
    return render_template(
        'team_leader/reports.html',
        page_title='Team Productivity Reports',
        projects=managed_projects
    )

