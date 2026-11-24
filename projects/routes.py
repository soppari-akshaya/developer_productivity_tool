from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from extensions import db
from models import Project, ProjectMember, Task, Issue, User
from . import projects_bp

def is_project_owner(user, project):
    """Check if the user is the original creator and owner of the project."""
    return project.created_by_id == user.id

def get_member_record(user, project):
    """Get the ProjectMember association record for this user and project."""
    return ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()

def can_view_project(user, project):
    """Check if the user has permission to view project details."""
    if user.role == 'admin':
        return True
    if is_project_owner(user, project):
        return True
    if get_member_record(user, project) is not None:
        return True
    return False

def can_edit_project(user, project):
    """Check if the user has permission to edit project details."""
    if user.role == 'admin':
        return True
    if is_project_owner(user, project):
        return True
    if user.role == 'team_leader':
        member = get_member_record(user, project)
        if member and member.role_in_project in ['lead', 'manager']:
            return True
    return False

def can_delete_project(user, project):
    """Check if the user has permission to delete a project."""
    if user.role == 'admin':
        return True
    if is_project_owner(user, project):
        return True
    if user.role == 'team_leader':
        member = get_member_record(user, project)
        if member and member.role_in_project in ['lead', 'manager']:
            return True
    return False

def can_manage_members(user, project):
    """Check if the user has permission to assign or remove members."""
    if user.role == 'admin':
        return True
    if is_project_owner(user, project):
        return True
    if user.role == 'team_leader':
        member = get_member_record(user, project)
        if member and member.role_in_project in ['lead', 'manager']:
            return True
    return False

@projects_bp.route('/projects')
@login_required
def list_projects():
    status_filter = request.args.get('status', 'all')
    search = request.args.get('q', '').strip()

    # Admin views all projects
    if current_user.role == 'admin':
        query = Project.query
    else:
        # Team Leaders view projects they manage/created or are members of.
        # Developers view projects they created or projects assigned to them.
        query = Project.query.filter(
            (Project.created_by_id == current_user.id) |
            (Project.members.any(user_id=current_user.id))
        )

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

    if not can_view_project(current_user, project):
        flash('You are not authorized to view this project.', 'danger')
        return redirect(url_for('projects.list_projects'))

    tasks = Task.query.filter_by(project_id=project.id).order_by(Task.deadline.asc()).all()
    issues = Issue.query.filter_by(project_id=project.id).order_by(Issue.created_at.desc()).all()

    # Fetch assignable candidates based on user role
    if current_user.role == 'admin':
        assignable_users = User.query.filter(
            User.role.in_(['team_leader', 'developer']),
            User.is_active == True
        ).order_by(User.full_name.asc()).all()
    else:
        assignable_users = User.query.filter_by(
            role='developer',
            is_active=True
        ).order_by(User.full_name.asc()).all()

    # Exclude members already assigned
    existing_user_ids = {m.user_id for m in project.members}
    available_candidates = [u for u in assignable_users if u.id not in existing_user_ids]

    can_edit = can_edit_project(current_user, project)
    can_del = can_delete_project(current_user, project)
    can_manage = can_manage_members(current_user, project)

    return render_template(
        'projects/detail.html',
        page_title=f'{project.name} - Project Details',
        project=project,
        tasks=tasks,
        issues=issues,
        available_candidates=available_candidates,
        can_edit=can_edit,
        can_delete=can_del,
        can_manage_members=can_manage
    )

@projects_bp.route('/projects/create', methods=['GET', 'POST'])
@login_required
def create():
    # All three roles (admin, team_leader, developer) are authorized to create projects
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

        # Add creator as project lead / owner
        lead_role = 'lead' if current_user.role in ['admin', 'team_leader'] else 'owner'
        member = ProjectMember(project_id=project.id, user_id=current_user.id, role_in_project=lead_role)
        db.session.add(member)

        # Allow project assignments to multiple Developers or Team Leaders on creation
        assigned_user_ids = request.form.getlist('assigned_developers')
        for uid_raw in assigned_user_ids:
            try:
                uid = int(uid_raw)
                if uid != current_user.id:
                    target_u = db.session.get(User, uid)
                    if target_u and target_u.is_active:
                        if current_user.role != 'admin' and target_u.role != 'developer':
                            continue
                        m_role = 'lead' if (target_u.role == 'team_leader' and current_user.role == 'admin') else 'developer'
                        db.session.add(ProjectMember(project_id=project.id, user_id=uid, role_in_project=m_role))
            except (ValueError, TypeError):
                continue

        db.session.commit()

        flash(f'Project "{project.name}" created successfully!', 'success')
        return redirect(url_for('projects.detail', project_id=project.id))

    # For GET: fetch available members that can be initially assigned
    if current_user.role == 'admin':
        assignable_users = User.query.filter(
            User.role.in_(['team_leader', 'developer']),
            User.is_active == True,
            User.id != current_user.id
        ).order_by(User.full_name.asc()).all()
    else:
        assignable_users = User.query.filter(
            User.role == 'developer',
            User.is_active == True,
            User.id != current_user.id
        ).order_by(User.full_name.asc()).all()

    return render_template(
        'projects/create.html',
        page_title='Create New Project',
        assignable_users=assignable_users
    )

@projects_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit(project_id):
    project = db.get_or_404(Project, project_id)
    if not can_edit_project(current_user, project):
        flash('Permission denied to modify this project.', 'danger')
        return redirect(url_for('projects.detail', project_id=project.id))

    if request.method == 'POST':
        project.name = request.form.get('name', project.name).strip()
        project.description = request.form.get('description', project.description).strip()
        project.priority = request.form.get('priority', project.priority)
        project.status = request.form.get('status', project.status)
        try:
            progress_val = int(request.form.get('progress', project.progress))
            project.progress = max(0, min(100, progress_val))
        except (ValueError, TypeError):
            pass

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
    if not can_delete_project(current_user, project):
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
    if not can_manage_members(current_user, project):
        flash('You are not authorized to assign members to this project.', 'danger')
        return redirect(url_for('projects.detail', project_id=project.id))

    user_id_raw = request.form.get('user_id')
    role_in_project = request.form.get('role_in_project', 'developer')

    if user_id_raw:
        try:
            user_id = int(user_id_raw)
            target_user = db.session.get(User, user_id)
            if not target_user or not target_user.is_active:
                flash('User not found or inactive.', 'danger')
                return redirect(url_for('projects.detail', project_id=project.id))

            # Non-admins can only assign Developers
            if current_user.role != 'admin' and target_user.role != 'developer':
                flash('You can only assign Developers to this project.', 'danger')
                return redirect(url_for('projects.detail', project_id=project.id))

            exists = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first()
            if not exists:
                if current_user.role == 'admin' and target_user.role == 'team_leader':
                    role_in_project = request.form.get('role_in_project', 'lead')
                new_m = ProjectMember(project_id=project.id, user_id=user_id, role_in_project=role_in_project)
                db.session.add(new_m)
                db.session.commit()
                flash(f'{target_user.full_name} added to project.', 'success')
            else:
                flash(f'{target_user.full_name} is already part of this project.', 'warning')
        except (ValueError, TypeError):
            flash('Invalid user ID provided.', 'danger')

    return redirect(url_for('projects.detail', project_id=project.id))

@projects_bp.route('/projects/<int:project_id>/members/<int:member_id>/remove', methods=['POST'])
@login_required
def remove_member(project_id, member_id):
    project = db.get_or_404(Project, project_id)
    if not can_manage_members(current_user, project):
        flash('You are not authorized to remove members from this project.', 'danger')
        return redirect(url_for('projects.detail', project_id=project.id))

    member = ProjectMember.query.filter_by(id=member_id, project_id=project.id).first_or_404()
    if member.user_id == project.created_by_id:
        flash('The project creator cannot be removed from project members.', 'warning')
        return redirect(url_for('projects.detail', project_id=project.id))

    user_name = member.user.full_name
    db.session.delete(member)
    db.session.commit()
    flash(f'{user_name} removed from the project.', 'info')
    return redirect(url_for('projects.detail', project_id=project.id))
