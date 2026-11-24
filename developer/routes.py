from datetime import datetime, date, timedelta
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_
from extensions import db, role_required
from models import Task, Project, ProjectMember, TimeEntry, ActiveTimer, PomodoroSession, WorkLog, CodeSnippet, Notification, ActivityLog, GitHubConnection
from integrations.github import GitHubService
from . import developer_bp

def get_user_today_working_time(user_id):
    """
    Calculate user's total working time for today in seconds, minutes, and formatted HH:MM:SS.
    Accurately sums completed sessions for today + currently active elapsed seconds (excluding pause duration).
    Does not double-count time.
    """
    today = date.today()
    today_entries = TimeEntry.query.filter_by(user_id=user_id, date=today).all()
    completed_seconds = 0
    for entry in today_entries:
        if entry.duration_seconds is not None:
            completed_seconds += entry.duration_seconds
        else:
            completed_seconds += (entry.duration_minutes or 0) * 60

    active_timer = ActiveTimer.query.filter_by(user_id=user_id).first()
    active_elapsed = 0
    if active_timer and active_timer.status in ('running', 'paused'):
        active_elapsed = active_timer.get_elapsed_seconds()

    total_seconds = completed_seconds + active_elapsed
    total_minutes = total_seconds // 60
    total_hours = round(total_seconds / 3600.0, 1)

    thrs = total_seconds // 3600
    tmins = (total_seconds % 3600) // 60
    tsecs = total_seconds % 60
    total_formatted = f"{thrs:02d}:{tmins:02d}:{tsecs:02d}"

    return {
        'completed_seconds': completed_seconds,
        'active_seconds': active_elapsed,
        'total_seconds': total_seconds,
        'total_minutes': total_minutes,
        'total_hours': total_hours,
        'total_formatted': total_formatted
    }

@developer_bp.route('/developer/dashboard')
@login_required
@role_required('developer', 'team_leader', 'admin')
def dashboard():
    today = date.today()
    user_project_ids = [p.id for p in Project.query.filter(
        (Project.created_by_id == current_user.id) |
        (Project.members.any(user_id=current_user.id))
    ).all()]

    conditions = [
        Task.assigned_to_id == current_user.id,
        Task.created_by_id == current_user.id
    ]
    if user_project_ids:
        conditions.append(Task.project_id.in_(user_project_ids))

    my_tasks = Task.query.filter(or_(*conditions)).all()

    total_assigned_tasks = len(my_tasks)
    pending_tasks = len([t for t in my_tasks if t.status == 'todo'])
    in_progress_tasks = len([t for t in my_tasks if t.status == 'in_progress'])
    completed_tasks = len([t for t in my_tasks if t.status == 'completed'])

    # Active projects user is involved in
    my_project_ids = [t.project_id for t in my_tasks if t.project_id]
    active_projects = Project.query.filter(Project.id.in_(my_project_ids), Project.status == 'active').all() if my_project_ids else []

    # Today's working hours (completed + active running sessions, excluding pauses)
    today_work = get_user_today_working_time(current_user.id)
    today_hours = today_work['total_hours']
    today_hours_display = f"{today_hours} hrs" if today_work['total_seconds'] > 0 else "0 hrs"
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()

    # Productivity percentage
    productivity_pct = round((completed_tasks / total_assigned_tasks * 100), 1) if total_assigned_tasks > 0 else 0

    upcoming_deadlines = Task.query.filter(
        or_(*conditions),
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
        today_hours_display=today_hours_display,
        today_work=today_work,
        active_timer=active_timer.to_dict() if active_timer else None,
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

@developer_bp.route('/api/editor/execute', methods=['POST'])
@login_required
def api_editor_execute():
    from flask import current_app
    from .code_runner import execute_python_code, execute_javascript_code, execute_sql_code
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    language = (data.get('language') or '').lower().strip()
    code = data.get('code', '')

    if not language:
        return jsonify({'status': 'error', 'output': 'No language specified.'}), 400

    if len(code) > 100_000:
        return jsonify({'status': 'error', 'output': 'Code payload exceeds maximum size limit (100KB).'}), 400

    if language == 'python':
        result = execute_python_code(code, timeout=5)
        return jsonify(result)
    elif language == 'javascript':
        result = execute_javascript_code(code, timeout=5)
        return jsonify(result)
    elif language == 'sql':
        result = execute_sql_code(current_user.id, code, current_app.instance_path, timeout=5)
        return jsonify(result)
    elif language in ('html', 'css'):
        return jsonify({
            'status': 'success',
            'output': f'{language.upper()} code ready for preview.',
            'execution_time': 0,
            'is_preview': True
        })
    else:
        return jsonify({
            'status': 'error',
            'output': f'Unsupported execution language: {language}. Supported: JavaScript, Python, HTML, CSS, SQL.'
        }), 400

@developer_bp.route('/api/editor/reset-sql', methods=['POST'])
@login_required
def api_editor_reset_sql():
    from flask import current_app
    from .code_runner import reset_user_sql_db
    success = reset_user_sql_db(current_user.id, current_app.instance_path)
    return jsonify({
        'status': 'success' if success else 'error',
        'message': 'Scratch SQL database reset successfully.' if success else 'Failed to reset scratch database.'
    })

@developer_bp.route('/developer/timer')
@login_required
def timer():
    projects = Project.query.filter_by(status='active').order_by(Project.name.asc()).all()
    # Provide all tasks under active projects so users can select tasks associated with their project
    tasks = Task.query.join(Project).filter(Project.status == 'active').order_by(Task.title.asc()).all()
    today_entries = TimeEntry.query.filter_by(user_id=current_user.id, date=date.today()).order_by(TimeEntry.created_at.desc()).all()
    all_time_entries = TimeEntry.query.filter_by(user_id=current_user.id).order_by(TimeEntry.date.desc(), TimeEntry.created_at.desc()).limit(50).all()
    today_work = get_user_today_working_time(current_user.id)
    today_hours_display = f"{today_work['total_hours']} hrs" if today_work['total_seconds'] > 0 else "0 hrs"
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()

    return render_template(
        'developer/timer.html',
        page_title='Time Tracker',
        projects=projects,
        tasks=tasks,
        today_entries=today_entries,
        all_time_entries=all_time_entries,
        today_work=today_work,
        today_hours_display=today_hours_display,
        active_timer=active_timer.to_dict() if active_timer else None
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

    now = datetime.utcnow()
    start_t = now - timedelta(minutes=duration_minutes)
    entry = TimeEntry(
        user_id=current_user.id,
        project_id=int(project_id) if project_id else None,
        task_id=int(task_id) if task_id else None,
        duration_minutes=duration_minutes,
        duration_seconds=duration_minutes * 60,
        start_time=start_t,
        end_time=now,
        description=description,
        date=date.today()
    )
    db.session.add(entry)
    
    # Clean up any active timer for this user if one existed
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    if active_timer:
        db.session.delete(active_timer)
        
    db.session.commit()
    flash('Time entry successfully recorded!', 'success')
    return redirect(url_for('developer.timer'))

# ==========================================
# REST API Endpoints for Global Time Tracker
# ==========================================

@developer_bp.route('/api/timer/current', methods=['GET'])
@login_required
def api_timer_current():
    """
    Returns current active timer state, elapsed seconds, and today's total working time.
    """
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    today_work = get_user_today_working_time(current_user.id)

    if not active_timer:
        return jsonify({
            'active': False,
            'status': 'idle',
            'timer': None,
            'today_total_seconds': today_work['total_seconds'],
            'today_total_minutes': today_work['total_minutes'],
            'today_total_hours': today_work['total_hours'],
            'today_total_formatted': today_work['total_formatted']
        })

    return jsonify({
        'active': True,
        'status': active_timer.status,
        'timer': active_timer.to_dict(),
        'today_total_seconds': today_work['total_seconds'],
        'today_total_minutes': today_work['total_minutes'],
        'today_total_hours': today_work['total_hours'],
        'today_total_formatted': today_work['total_formatted']
    })

@developer_bp.route('/api/timer/start', methods=['POST'])
@login_required
def api_timer_start():
    """
    Start new timer session. Server-side timestamps prevent drift.
    """
    data = request.get_json(silent=True) or request.form.to_dict() or {}
    project_id = data.get('project_id')
    task_id = data.get('task_id')
    description = (data.get('description') or '').strip()
    switch = data.get('switch', False)

    try:
        project_id = int(project_id) if project_id is not None and str(project_id).strip() not in ('', 'null', 'None') else None
    except (ValueError, TypeError):
        project_id = None

    try:
        task_id = int(task_id) if task_id is not None and str(task_id).strip() not in ('', 'null', 'None') else None
    except (ValueError, TypeError):
        task_id = None

    # Check for existing timer for this user
    existing_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    if existing_timer and existing_timer.status in ('running', 'paused'):
        if switch:
            prev_seconds = existing_timer.get_elapsed_seconds()
            if prev_seconds > 0:
                now_prev = datetime.utcnow()
                start_prev = existing_timer.start_time if existing_timer.start_time else (now_prev - timedelta(seconds=prev_seconds))
                entry = TimeEntry(
                    user_id=current_user.id,
                    project_id=existing_timer.project_id,
                    task_id=existing_timer.task_id,
                    duration_minutes=max(1, int(round(prev_seconds / 60.0))),
                    duration_seconds=prev_seconds,
                    start_time=start_prev,
                    end_time=now_prev,
                    description=existing_timer.description or 'Work Session',
                    date=date.today()
                )
                db.session.add(entry)
            db.session.delete(existing_timer)
            db.session.flush()
        else:
            return jsonify({
                'status': 'error',
                'message': 'A timer is already active. Please pause or stop it before starting a new one.',
                'timer': existing_timer.to_dict()
            }), 400
    elif existing_timer:
        db.session.delete(existing_timer)
        db.session.flush()

    # Validate project
    if project_id:
        project = db.session.get(Project, project_id)
        if not project:
            return jsonify({'status': 'error', 'message': 'Selected project was not found.'}), 400

    # Validate task
    if task_id:
        task = db.session.get(Task, task_id)
        if not task:
            return jsonify({'status': 'error', 'message': 'Selected task was not found.'}), 400
        if not project_id and task.project_id:
            project_id = task.project_id

    now = datetime.utcnow()
    timer_obj = ActiveTimer(
        user_id=current_user.id,
        project_id=project_id,
        task_id=task_id,
        description=description,
        start_time=now,
        last_started_at=now,
        accumulated_seconds=0,
        status='running',
        created_at=now,
        updated_at=now
    )
    db.session.add(timer_obj)
    db.session.commit()

    today_work = get_user_today_working_time(current_user.id)
    return jsonify({
        'status': 'success',
        'message': 'Timer started.',
        'timer': timer_obj.to_dict(),
        'today_total_seconds': today_work['total_seconds'],
        'today_total_minutes': today_work['total_minutes'],
        'today_total_hours': today_work['total_hours'],
        'today_total_formatted': today_work['total_formatted']
    }), 201

@developer_bp.route('/api/timer/pause', methods=['POST'])
@login_required
def api_timer_pause():
    """
    Pause the active timer. Accumulate elapsed seconds and clear last_started_at.
    """
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    if not active_timer:
        return jsonify({'status': 'error', 'message': 'No active timer found.'}), 404
    if active_timer.status == 'paused':
        return jsonify({'status': 'error', 'message': 'Timer is already paused.'}), 400

    now = datetime.utcnow()
    if active_timer.status == 'running' and active_timer.last_started_at:
        delta = int((now - active_timer.last_started_at).total_seconds())
        active_timer.accumulated_seconds += max(0, delta)

    active_timer.last_started_at = None
    active_timer.status = 'paused'
    active_timer.updated_at = now
    db.session.commit()

    today_work = get_user_today_working_time(current_user.id)
    return jsonify({
        'status': 'success',
        'message': 'Timer paused.',
        'timer': active_timer.to_dict(),
        'today_total_seconds': today_work['total_seconds'],
        'today_total_minutes': today_work['total_minutes'],
        'today_total_hours': today_work['total_hours'],
        'today_total_formatted': today_work['total_formatted']
    })

@developer_bp.route('/api/timer/resume', methods=['POST'])
@login_required
def api_timer_resume():
    """
    Resume a paused timer.
    """
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    if not active_timer:
        return jsonify({'status': 'error', 'message': 'No active timer found.'}), 404
    if active_timer.status == 'running':
        return jsonify({'status': 'error', 'message': 'Timer is already running.'}), 400

    now = datetime.utcnow()
    active_timer.last_started_at = now
    active_timer.status = 'running'
    active_timer.updated_at = now
    db.session.commit()

    today_work = get_user_today_working_time(current_user.id)
    return jsonify({
        'status': 'success',
        'message': 'Timer resumed.',
        'timer': active_timer.to_dict(),
        'today_total_seconds': today_work['total_seconds'],
        'today_total_minutes': today_work['total_minutes'],
        'today_total_hours': today_work['total_hours'],
        'today_total_formatted': today_work['total_formatted']
    })

@developer_bp.route('/api/timer/stop', methods=['POST'])
@login_required
def api_timer_stop():
    """
    Stop active timer and record completed duration to TimeEntry in SQLite.
    """
    active_timer = ActiveTimer.query.filter_by(user_id=current_user.id).first()
    if not active_timer:
        return jsonify({'status': 'error', 'message': 'No active timer found.'}), 404

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    req_project_id = data.get('project_id')
    req_task_id = data.get('task_id')
    req_description = data.get('description')

    try:
        req_project_id = int(req_project_id) if req_project_id is not None and str(req_project_id).strip() not in ('', 'null', 'None') else None
    except (ValueError, TypeError):
        req_project_id = None

    try:
        req_task_id = int(req_task_id) if req_task_id is not None and str(req_task_id).strip() not in ('', 'null', 'None') else None
    except (ValueError, TypeError):
        req_task_id = None

    now = datetime.utcnow()
    if active_timer.status == 'running' and active_timer.last_started_at:
        delta = int((now - active_timer.last_started_at).total_seconds())
        total_seconds = active_timer.accumulated_seconds + max(0, delta)
    else:
        total_seconds = active_timer.accumulated_seconds

    final_project_id = req_project_id if req_project_id is not None else active_timer.project_id
    final_task_id = req_task_id if req_task_id is not None else active_timer.task_id
    final_desc = req_description if req_description is not None and str(req_description).strip() != '' else (active_timer.description or 'Work Session')

    duration_minutes = 0
    entry_id = None
    if total_seconds > 0:
        duration_minutes = max(1, int(round(total_seconds / 60.0)))
        start_t = active_timer.start_time if active_timer.start_time else (now - timedelta(seconds=total_seconds))
        entry = TimeEntry(
            user_id=current_user.id,
            project_id=final_project_id,
            task_id=final_task_id,
            duration_minutes=duration_minutes,
            duration_seconds=total_seconds,
            start_time=start_t,
            end_time=now,
            description=final_desc,
            date=date.today(),
            created_at=now
        )
        db.session.add(entry)
        db.session.flush()
        entry_id = entry.id

    db.session.delete(active_timer)
    db.session.commit()

    today_work = get_user_today_working_time(current_user.id)
    return jsonify({
        'status': 'success',
        'message': f'Timer stopped and {duration_minutes} min recorded.' if duration_minutes > 0 else 'Timer stopped.',
        'entry_id': entry_id,
        'total_seconds': total_seconds,
        'duration_minutes': duration_minutes,
        'today_total_seconds': today_work['total_seconds'],
        'today_total_minutes': today_work['total_minutes'],
        'today_total_hours': today_work['total_hours'],
        'today_total_formatted': today_work['total_formatted']
    })

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

