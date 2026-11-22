from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import Project, ProjectMember, Task, Issue, User
from . import projects_bp

@projects_bp.route('/projects')
@login_required
def list_projects():
    status_filter = request.args.get('status', 'all')
    search = request.args.get('q', '').strip()

    query = Project.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if search:
        query = query.filter(Project.name.ilike(f'%{search}%'))

    projects = query.order_by(Project.created_at.desc()).all()
    return render_template(
        'projects/list.html',
        page_title='Projects - Developer Productivity Tool',
        projects=projects,
        status_filter=status_filter,
        search=search
    )

@projects_bp.route('/projects/<int:project_id>')
@login_required
def detail(project_id):
    project = db.get_or_404(Project, project_id)
    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.deadline.asc()).all()
    issues = Issue.query.filter_by(project_id=project.id).order_by(Issue.created_at.desc()).all()
    all_developers = User.query.filter_by(role='developer', is_active=True).all()
    return render_template(
        'projects/detail.html',
        page_title=f'{project.name} - Project Details',
        project=project,
        tasks=tasks,
        issues=issues,
        all_developers=all_developers
    )

@projects_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create():
    # Only Admin and Team Leader can create projects
    if current_user.role not in ['admin', 'team_leader']:
        flash('Only Team Leaders and Admins are authorized to create projects.', 'danger')
        return redirect(url_for('projects.list_projects'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        description = request.form.get('description', '').strip()
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        priority = request.form.get('priority', 'medium')
        status = request.form.get('status', 'active')

        if not name:
            flash('Project name is required.', 'danger')
            return redirect(url_for('projects.create'))

        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else None
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else None

        project = Project(
            name=name,
            description=description,
            start_date=start_date,
            end_date=end_date,
            priority=priority,
            status=status,
            progress=0,
            created_by_id=current_user.id
        )
        db.session.add(project)
        db.session.commit()

        # Add creator as project lead
        member = ProjectMember(project_id=project.id, user_id=current_user.id, role_in_project='lead')
        db.session.add(member)
        db.session.commit()

        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('projects.detail', project_id=project.id))

    return render_template('projects/create.html', page_title='Create New Project')

@projects_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    project = db.get_or_404(Project, project_id)
    if current_user.role not in ['admin', 'team_leader'] and project.created_by_id != current_user.id:
        flash('Permission denied to modify this project.', 'danger')
        return redirect(url_for('projects.detail', project_id=project.id))

    if request.method == 'POST':
        project.name = request.form.get('name', project.name).strip()
        project.description = request.form.get('description', project.description).strip()
        project.priority = request.form.get('priority', project.priority)
        project.status = request.form.get('status', project.status)
        project.progress = int(request.form.get('progress', project.progress))

        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        if start_date_str:
            project.start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        if end_date_str:
            project.end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        db.session.commit()
        flash('Project updated successfully.', 'success')
        return redirect(url_for('projects.detail', project_id=project.id))

    return render_template('projects/edit.html', page_title=f'Edit {project.name}', project=project)

@projects_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
def delete(project_id):
    project = db.get_or_404(Project, project_id)
    if current_user.role != 'admin' and project.created_by_id != current_user.id:
        flash('Permission denied to delete this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

    name = project.name
    db.session.delete(project)
    db.session.commit()
    flash(f'Project "{name}" has been deleted.', 'info')
    return redirect(url_for('projects.list_projects'))

@projects_bp.route('/projects/<int:project_id>/members/add', methods=['POST'])
@login_required
def add_member(project_id):
    project = db.get_or_404(Project, project_id)
    user_id = request.form.get('user_id')
    role_in_project = request.form.get('role_in_project', 'developer')

    if user_id:
        exists = ProjectMember.query.filter_by(project_id=project.id, user_id=int(user_id)).first()
        if not exists:
            new_m = ProjectMember(project_id=project.id, user_id=int(user_id), role_in_project=role_in_project)
            db.session.add(new_m)
            db.session.commit()
            flash('Team member added to project.', 'success')
        else:
            flash('Member is already part of this project.', 'warning')

    return redirect(url_for('projects.detail', project_id=project.id))

