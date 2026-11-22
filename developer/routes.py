from datetime import datetime, date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db, role_required
from models import Task, Project, TimeEntry, PomodoroSession, WorkLog, CodeSnippet, Notification, ActivityLog, GitHubConnection
from integrations.github import GitHubService
from . import developer_bp

@developer_bp.route('/developer/dashboard')
@login_required
@role_required('developer', 'team_leader', 'admin')
def dashboard():
    today = date.today()
    my_tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()

    total_assigned_tasks = len(my_tasks)
    pending_tasks = len([t for t in my_tasks if t.status == 'todo'])
    in_progress_tasks = len([t for t in my_tasks if t.status == 'in_progress'])
    completed_tasks = len([t for t in my_tasks if t.status == 'completed'])

    # Active projects user is involved in
    my_project_ids = [t.project_id for t in my_tasks if t.project_id]
    active_projects = Project.query.filter(Project.id.in_(my_project_ids), Project.status == 'active').all() if my_project_ids else []

    # Today's logged working hours
    today_time_entries = TimeEntry.query.filter_by(user_id=current_user.id, date=today).all()
    today_minutes = sum(t.duration_minutes for t in today_time_entries)
    today_hours = round(today_minutes / 60.0, 1)

    # Productivity percentage
    productivity_pct = round((completed_tasks / total_assigned_tasks * 100), 1) if total_assigned_tasks > 0 else 0

    upcoming_deadlines = Task.query.filter(
        Task.assigned_to_id == current_user.id,
        Task.status != 'completed',
        Task.deadline >= today
    ).order_by(Task.deadline.asc()).limit(5).all()

    recent_snippets = CodeSnippet.query.filter_by(user_id=current_user.id).order_by(CodeSnippet.updated_at.desc()).limit(3).all()
    recent_notifications = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(5).all()

    return render_template(
        'developer/dashboard.html',
        page_title='Developer Workspace - Developer Productivity Tool',
        total_assigned_tasks=total_assigned_tasks,
        pending_tasks=pending_tasks,
        in_progress_tasks=in_progress_tasks,
        completed_tasks=completed_tasks,
        active_projects_count=len(active_projects),
        today_hours=today_hours,
        productivity_pct=productivity_pct,
        my_tasks=my_tasks[:6],
        active_projects=active_projects[:4],
        upcoming_deadlines=upcoming_deadlines,
        recent_snippets=recent_snippets,
        recent_notifications=recent_notifications
    )

@developer_bp.route('/developer/editor')
@login_required
def editor():
    return render_template('developer/editor.html', page_title='Online Code Editor - CodeMirror')

@developer_bp.route('/developer/timer')
@login_required
def timer():
    projects = Project.query.filter_by(status='active').all()
    tasks = Task.query.filter_by(assigned_to_id=current_user.id).all()
    today_entries = TimeEntry.query.filter_by(user_id=current_user.id, date=date.today()).order_by(TimeEntry.created_at.desc()).all()
    all_time_entries = TimeEntry.query.filter_by(user_id=current_user.id).order_by(TimeEntry.date.desc()).limit(20).all()
    return render_template(
        'developer/timer.html',
        page_title='Time Tracker',
        projects=projects,
        tasks=tasks,
        today_entries=today_entries,
        all_time_entries=all_time_entries
    )

@developer_bp.route('/developer/timer/save', methods=['POST'])
@login_required
def save_timer():
    duration_minutes = int(request.form.get('duration_minutes', 0))
    project_id = request.form.get('project_id')
    task_id = request.form.get('task_id')
    description = request.form.get('description', '')

    if duration_minutes <= 0:
        flash('Timer duration must be greater than 0 minutes.', 'warning')
        return redirect(url_for('developer.timer'))

    entry = TimeEntry(
        user_id=current_user.id,
        project_id=int(project_id) if project_id else None,
        task_id=int(task_id) if task_id else None,
        duration_minutes=duration_minutes,
        description=description,
        date=date.today()
    )
    db.session.add(entry)
    db.session.commit()
    flash('Time entry successfully recorded!', 'success')
    return redirect(url_for('developer.timer'))

@developer_bp.route('/developer/pomodoro')
@login_required
def pomodoro():
    sessions = PomodoroSession.query.filter_by(user_id=current_user.id).order_by(PomodoroSession.created_at.desc()).limit(15).all()
    today_sessions = PomodoroSession.query.filter(
        PomodoroSession.user_id == current_user.id,
        PomodoroSession.created_at >= datetime.utcnow().date()
    ).count()
    return render_template(
        'developer/pomodoro.html',
        page_title='Pomodoro Deep Work Timer',
        sessions=sessions,
        today_sessions=today_sessions
    )

@developer_bp.route('/developer/pomodoro/complete', methods=['POST'])
@login_required
def complete_pomodoro():
    data = request.get_json() or {}
    session_type = data.get('session_type', 'focus')
    duration = int(data.get('duration', 25))

    pomo = PomodoroSession(
        user_id=current_user.id,
        duration_minutes=duration,
        session_type=session_type,
        completed=True
    )
    db.session.add(pomo)
    db.session.commit()
    return jsonify({'status': 'success', 'message': 'Pomodoro session recorded.'})

@developer_bp.route('/developer/work-logs', methods=['GET', 'POST'])
@login_required
def work_logs():
    if request.method == 'POST':
        work_performed = request.form.get('work_performed', '').strip()
        completed_tasks = request.form.get('completed_tasks', '').strip()
        challenges = request.form.get('challenges', '').strip()
        pending_activities = request.form.get('pending_activities', '').strip()
        hours_worked = float(request.form.get('hours_worked', 8.0))

        if not work_performed:
            flash('Work performed summary is required.', 'danger')
            return redirect(url_for('developer.work_logs'))

        log = WorkLog(
            user_id=current_user.id,
            date=date.today(),
            completed_tasks=completed_tasks,
            work_performed=work_performed,
            challenges=challenges,
            pending_activities=pending_activities,
            hours_worked=hours_worked
        )
        db.session.add(log)
        db.session.commit()
        flash('Daily work log submitted successfully!', 'success')
        return redirect(url_for('developer.work_logs'))

    logs = WorkLog.query.filter_by(user_id=current_user.id).order_by(WorkLog.date.desc()).all()
    return render_template('developer/work_logs.html', page_title='Daily Work Logs', logs=logs)

@developer_bp.route('/developer/profile')
@login_required
def profile():
    return render_template('developer/profile.html', page_title='Developer Profile')

@developer_bp.route('/developer/github', methods=['GET'])
@login_required
def github_view():
    conn = GitHubConnection.query.filter_by(user_id=current_user.id).first()
    repos = []
    error_msg = None

    if conn:
        if conn.access_token:
            repos = GitHubService.get_user_repositories(conn.access_token, limit=15)
        elif conn.github_username:
            repos = GitHubService.get_public_user_repos(conn.github_username, limit=15)

        if not repos:
            error_msg = "No repositories found or GitHub rate limit reached. Please check your username or token."

    return render_template(
        'developer/github.html',
        page_title='GitHub Integration',
        connection=conn,
        repos=repos,
        error_msg=error_msg
    )

@developer_bp.route('/developer/github/connect', methods=['POST'])
@login_required
def github_connect():
    username = request.form.get('github_username', '').strip()
    token = request.form.get('access_token', '').strip()

    if not username and not token:
        flash('Please enter a GitHub username or Personal Access Token.', 'warning')
        return redirect(url_for('developer.github_view'))

    conn = GitHubConnection.query.filter_by(user_id=current_user.id).first()
    if not conn:
        conn = GitHubConnection(user_id=current_user.id, github_username=username or 'User')
        db.session.add(conn)

    if username:
        conn.github_username = username
    if token:
        conn.access_token = token
        profile = GitHubService.get_user_profile(token)
        if profile and 'login' in profile:
            conn.github_username = profile['login']
            conn.avatar_url = profile.get('avatar_url', '')

    db.session.commit()
    flash(f'GitHub account @{conn.github_username} connected successfully.', 'success')
    return redirect(url_for('developer.github_view'))

@developer_bp.route('/developer/github/disconnect', methods=['POST'])
@login_required
def github_disconnect():
    conn = GitHubConnection.query.filter_by(user_id=current_user.id).first()
    if conn:
        db.session.delete(conn)
        db.session.commit()
        flash('GitHub connection removed.', 'info')
    return redirect(url_for('developer.github_view'))

@developer_bp.route('/developer/github/repo/<owner>/<repo>', methods=['GET'])
@login_required
def github_repo_details(owner, repo):
    conn = GitHubConnection.query.filter_by(user_id=current_user.id).first()
    token = conn.access_token if conn else None

    repo_data = GitHubService.get_repo_details(owner, repo, token)
    commits = GitHubService.get_repo_commits(owner, repo, token, limit=10)
    prs = GitHubService.get_repo_pull_requests(owner, repo, token, limit=10)

    return render_template(
        'developer/github_repo.html',
        page_title=f'{owner}/{repo} - GitHub Repository',
        owner=owner,
        repo_name=repo,
        repo=repo_data,
        commits=commits,
        pull_requests=prs
    )

