import csv
import io
import os
from datetime import datetime, date, timedelta
from flask import render_template, request, Response, jsonify, send_file, current_app
from flask_login import login_required, current_user
from extensions import db
from models import Task, Project, TimeEntry, PomodoroSession, WorkLog, User
from . import reports_bp

@reports_bp.route('/reports/analytics')
@login_required
def analytics():
    total_tasks = Task.query.count()
    completed_tasks = Task.query.filter_by(status='completed').count()
    in_progress_tasks = Task.query.filter_by(status='in_progress').count()
    todo_tasks = Task.query.filter_by(status='todo').count()
    review_tasks = Task.query.filter_by(status='in_review').count()

    total_projects = Project.query.count()
    active_projects = Project.query.filter_by(status='active').count()

    # Total time logged
    all_time_entries = TimeEntry.query.all()
    total_minutes = sum(t.duration_minutes for t in all_time_entries)
    total_hours = round(total_minutes / 60.0, 1)

    total_pomodoro_sessions = PomodoroSession.query.filter_by(completed=True).count()

    return render_template(
        'reports/analytics.html',
        page_title='Productivity Analytics & Reports',
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        in_progress_tasks=in_progress_tasks,
        todo_tasks=todo_tasks,
        review_tasks=review_tasks,
        total_projects=total_projects,
        active_projects=active_projects,
        total_hours=total_hours,
        total_pomodoro_sessions=total_pomodoro_sessions
    )

@reports_bp.route('/reports/api/chart-data')
@login_required
def chart_data():
    """
    Returns JSON formatted data for Chart.js
    """
    # 1. Task status breakdown
    status_counts = {
        'Completed': Task.query.filter_by(status='completed').count(),
        'In Progress': Task.query.filter_by(status='in_progress').count(),
        'In Review': Task.query.filter_by(status='in_review').count(),
        'To Do': Task.query.filter_by(status='todo').count(),
    }

    # 2. Daily working hours for last 7 days
    today = date.today()
    days = [(today - timedelta(days=i)) for i in range(6, -1, -1)]
    day_labels = [d.strftime('%a (%d %b)') for d in days]
    hours_per_day = []

    for d in days:
        entries = TimeEntry.query.filter_by(date=d).all()
        day_minutes = sum(e.duration_minutes for e in entries)
        hours_per_day.append(round(day_minutes / 60.0, 1))

    # 3. Project progress data
    projects = Project.query.limit(6).all()
    project_labels = [p.name for p in projects]
    project_progress = [p.progress for p in projects]

    return jsonify({
        'taskStatus': {
            'labels': list(status_counts.keys()),
            'data': list(status_counts.values())
        },
        'weeklyHours': {
            'labels': day_labels,
            'data': hours_per_day
        },
        'projectProgress': {
            'labels': project_labels,
            'data': project_progress
        }
    })

@reports_bp.route('/reports/export-csv')
@login_required
def export_csv():
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['Task ID', 'Title', 'Project', 'Assignee', 'Priority', 'Status', 'Deadline', 'Created At'])
    tasks = Task.query.all()
    for t in tasks:
        writer.writerow([
            t.id,
            t.title,
            t.project.name if t.project else '',
            t.assignee.full_name if t.assignee else 'Unassigned',
            t.priority,
            t.status,
            t.deadline.strftime('%Y-%m-%d') if t.deadline else '',
            t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else ''
        ])

    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={"Content-Disposition": f"attachment;filename=productivity_tasks_{date.today()}.csv"}
    )

@reports_bp.route('/reports/download/pdf')
@login_required
def download_pdf():
    pdf_path = os.path.join(current_app.root_path, 'developer_productivity_tool_testing_report.pdf')
    if not os.path.exists(pdf_path):
        pdf_path = os.path.join(current_app.root_path, 'static', 'reports', 'developer_productivity_tool_testing_report.pdf')
    return send_file(
        pdf_path,
        mimetype='application/pdf',
        as_attachment=True,
        download_name='developer_productivity_tool_testing_report.pdf'
    )

@reports_bp.route('/reports/download/doc')
@login_required
def download_doc():
    doc_path = os.path.join(current_app.root_path, 'developer_productivity_tool_testing_report.doc')
    if not os.path.exists(doc_path):
        doc_path = os.path.join(current_app.root_path, 'static', 'reports', 'developer_productivity_tool_testing_report.doc')
    return send_file(
        doc_path,
        mimetype='application/msword',
        as_attachment=True,
        download_name='developer_productivity_tool_testing_report.doc'
    )

