from datetime import datetime
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from extensions import db
from models import Issue, Project, User
from . import issues_bp

@issues_bp.route('/issues')
@login_required
def list_issues():
    status_filter = request.args.get('status', 'all')
    severity_filter = request.args.get('severity', 'all')

    query = Issue.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if severity_filter != 'all':
        query = query.filter_by(severity=severity_filter)

    issues = query.order_by(Issue.created_at.desc()).all()
    projects = Project.query.filter_by(status='active').all()
    developers = User.query.filter_by(role='developer', is_active=True).all()

    return render_template(
        'issues/list.html',
        page_title='Bug & Issue Tracker - Developer Productivity Tool',
        issues=issues,
        projects=projects,
        developers=developers,
        status_filter=status_filter,
        severity_filter=severity_filter
    )

@issues_bp.route('/issues/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        project_id = request.form.get('project_id')
        assigned_to_id = request.form.get('assigned_to_id')
        severity = request.form.get('severity', 'major')
        priority = request.form.get('priority', 'medium')

        if not title or not project_id:
            flash('Issue title and project are required.', 'danger')
            return redirect(url_for('issues.create'))

        issue = Issue(
            title=title,
            description=description,
            project_id=int(project_id),
            reported_by_id=current_user.id,
            assigned_to_id=int(assigned_to_id) if assigned_to_id else None,
            severity=severity,
            priority=priority,
            status='open'
        )
        db.session.add(issue)
        db.session.commit()
        flash(f'Issue #{issue.id} reported successfully.', 'success')
        return redirect(url_for('issues.list_issues'))

    projects = Project.query.filter_by(status='active').all()
    developers = User.query.filter_by(role='developer', is_active=True).all()
    return render_template('issues/create.html', page_title='Report a Bug / Issue', projects=projects, developers=developers)

@issues_bp.route('/issues/<int:issue_id>/update-status', methods=['POST'])
@login_required
def update_status(issue_id):
    issue = db.get_or_404(Issue, issue_id)
    new_status = request.form.get('status')
    if new_status in ['open', 'in_progress', 'resolved', 'closed']:
        issue.status = new_status
        issue.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Issue #{issue.id} marked as {new_status.replace("_", " ").title()}.', 'success')
    return redirect(request.referrer or url_for('issues.list_issues'))

