from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Task, TaskComment, Project, User, Notification
from . import tasks_bp

@tasks_bp.route('/tasks')
@login_required
def list_tasks():
    status_filter = request.args.get('status', 'all')
    priority_filter = request.args.get('priority', 'all')
    project_id = request.args.get('project_id')

    query = Task.query
    if current_user.role == 'developer':
        query = query.filter_by(assigned_to_id=current_user.id)
    
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if priority_filter != 'all':
        query = query.filter_by(priority=priority_filter)
    if project_id:
        query = query.filter_by(project_id=int(project_id))

    tasks = query.order_by(Task.deadline.asc().nullslast()).all()
    projects = Project.query.filter_by(status='active').all()
    developers = User.query.filter_by(role='developer', is_active=True).all()

    return render_template(
        'tasks/list.html',
        page_title='Task Management - Developer Productivity Tool',
        tasks=tasks,
        projects=projects,
        developers=developers,
        status_filter=status_filter,
        priority_filter=priority_filter,
        selected_project_id=project_id
    )

@tasks_bp.route('/tasks/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        project_id = request.form.get('project_id')
        assigned_to_id = request.form.get('assigned_to_id')
        deadline_str = request.form.get('deadline')
        priority = request.form.get('priority', 'medium')
        status = request.form.get('status', 'todo')

        if not title or not project_id:
            flash('Task title and associated project are required.', 'danger')
            return redirect(url_for('tasks.create'))

        deadline = datetime.strptime(deadline_str, '%Y-%m-%d').date() if deadline_str else None

        task = Task(
            title=title,
            description=description,
            project_id=int(project_id),
            assigned_to_id=int(assigned_to_id) if assigned_to_id else current_user.id,
            created_by_id=current_user.id,
            deadline=deadline,
            priority=priority,
            status=status
        )
        db.session.add(task)
        db.session.commit()

        # Send notification to assignee
        if task.assigned_to_id and task.assigned_to_id != current_user.id:
            notif = Notification(
                user_id=task.assigned_to_id,
                title='New Task Assigned',
                message=f'You were assigned task: {task.title}',
                link=url_for('tasks.detail', task_id=task.id)
            )
            db.session.add(notif)
            db.session.commit()

        flash(f'Task "{task.title}" created successfully!', 'success')
        return redirect(url_for('tasks.detail', task_id=task.id))

    projects = Project.query.filter_by(status='active').all()
    developers = User.query.filter_by(role='developer', is_active=True).all()
    return render_template('tasks/create.html', page_title='Create New Task', projects=projects, developers=developers)

@tasks_bp.route('/tasks/<int:task_id>')
@login_required
def detail(task_id):
    task = db.get_or_404(Task, task_id)
    comments = TaskComment.query.filter_by(task_id=task.id).order_by(TaskComment.created_at.asc()).all()
    developers = User.query.filter_by(role='developer', is_active=True).all()
    return render_template(
        'tasks/detail.html',
        page_title=f'{task.title} - Task Details',
        task=task,
        comments=comments,
        developers=developers
    )

@tasks_bp.route('/tasks/<int:task_id>/update-status', methods=['POST'])
@login_required
def update_status(task_id):
    task = db.get_or_404(Task, task_id)
    new_status = request.form.get('status')
    if new_status in ['todo', 'in_progress', 'in_review', 'completed']:
        task.status = new_status
        task.updated_at = datetime.utcnow()
        db.session.commit()
        flash(f'Status updated to {new_status.replace("_", " ").title()}.', 'success')
    return redirect(request.referrer or url_for('tasks.detail', task_id=task.id))

@tasks_bp.route('/tasks/<int:task_id>/comments', methods=['POST'])
@login_required
def add_comment(task_id):
    task = db.get_or_404(Task, task_id)
    comment_text = request.form.get('comment', '').strip()
    if comment_text:
        comment = TaskComment(
            task_id=task.id,
            user_id=current_user.id,
            comment=comment_text
        )
        db.session.add(comment)
        db.session.commit()
        flash('Comment posted.', 'success')
    return redirect(url_for('tasks.detail', task_id=task.id))

@tasks_bp.route('/tasks/<int:task_id>/delete', methods=['POST'])
@login_required
def delete(task_id):
    task = db.get_or_404(Task, task_id)
    if current_user.role not in ['admin', 'team_leader'] and task.created_by_id != current_user.id:
        flash('Permission denied to delete task.', 'danger')
        return redirect(url_for('tasks.list_tasks'))

    db.session.delete(task)
    db.session.commit()
    flash('Task deleted successfully.', 'info')
    return redirect(url_for('tasks.list_tasks'))

