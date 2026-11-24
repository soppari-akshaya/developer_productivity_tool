import time
from datetime import datetime, timedelta
from flask import request, jsonify, render_template, session, current_app
from flask_login import login_required, current_user
from extensions import db
from models import AIChatMessage
from . import ai_assistant_bp
from .services import GrokService

# In-memory simple rate limiting tracker: {user_id: [timestamps]}
_user_rate_limits = {}

def check_rate_limit(user_id, max_requests=30, window_seconds=60):
    """
    Prevents abuse and API token exhaustion.
    Max 30 requests per 60 seconds per user.
    """
    now = time.time()
    timestamps = _user_rate_limits.get(user_id, [])
    timestamps = [ts for ts in timestamps if now - ts < window_seconds]
    if len(timestamps) >= max_requests:
        _user_rate_limits[user_id] = timestamps
        return False
    timestamps.append(now)
    _user_rate_limits[user_id] = timestamps
    return True


@ai_assistant_bp.route('/ai/history', methods=['GET'])
@login_required
def get_history():
    """
    Returns the authenticated user's isolated chat history.
    """
    try:
        messages = AIChatMessage.query.filter_by(user_id=current_user.id)\
            .order_by(AIChatMessage.created_at.asc()).limit(50).all()
        return jsonify({
            'success': True,
            'messages': [m.to_dict() for m in messages]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f"Failed to retrieve chat history: {str(e)}"}), 500


@ai_assistant_bp.route('/ai/projects', methods=['GET'])
@login_required
def get_authorized_projects():
    """
    Returns list of projects the current user is authorized to access.
    """
    try:
        projects = GrokService.get_user_authorized_projects(current_user)
        return jsonify({
            'success': True,
            'projects': [
                {
                    'id': p.id,
                    'name': p.name,
                    'status': p.status,
                    'progress': p.progress
                } for p in projects
            ]
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_assistant_bp.route('/ai/chat', methods=['POST'])
@login_required
def send_chat_message():
    """
    General conversation with Developer Productivity Tool Assistant.
    """
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment before sending another message."}), 429

    data = request.get_json(silent=True) or {}
    user_text = (data.get('message') or '').strip()

    if not user_text:
        return jsonify({'success': False, 'error': "Message cannot be empty."}), 400
    if len(user_text) > 4000:
        return jsonify({'success': False, 'error': "Message exceeds maximum allowed length (4,000 characters)."}), 400

    # Persist user message
    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=user_text,
        message_type='chat'
    )
    db.session.add(user_msg)
    db.session.commit()

    # Load recent conversation history for context
    history_records = AIChatMessage.query.filter_by(user_id=current_user.id)\
        .order_by(AIChatMessage.created_at.desc()).limit(10).all()
    history = [m.to_dict() for m in reversed(history_records)]

    # Call AI Backend
    res = GrokService.chat(user_text, conversation_history=history, user=current_user)

    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='chat'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({
            'success': True,
            'reply': res['content'],
            'message_id': assistant_msg.id
        })
    else:
        return jsonify({
            'success': False,
            'error': res.get('error', 'The Assistant failed to respond.'),
            'is_config_error': res.get('is_config_error', False)
        }), 400 if res.get('is_config_error') else 500


# 1. Project Management: Create Project Guidance / Proposal
@ai_assistant_bp.route('/ai/create-project', methods=['POST'])
@login_required
def create_project_proposal():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    details = (data.get('details') or '').strip()

    if len(details) > 4000:
        return jsonify({'success': False, 'error': "Details exceed maximum length (4,000 characters)."}), 400

    user_text = f"Project Guidance & Review: {details[:120]}..." if details else "How do I create a project in the platform?"
    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=user_text,
        message_type='project'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.create_project_proposal(details if details else None)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='project'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 2. Project Management: Generate Project Report
@ai_assistant_bp.route('/ai/summarize-project', methods=['POST'])
@login_required
def summarize_project():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')

    if not project_id:
        return jsonify({'success': False, 'error': "Please select a project to generate a progress report for."}), 400

    metrics = GrokService.get_project_metrics_context(project_id, current_user)
    if not metrics:
        return jsonify({'success': False, 'error': "Project not found or you are not authorized to view its data."}), 403

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Generate Project Report: {metrics['name']}",
        message_type='summary'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.summarize_project(metrics)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='summary'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 3. Task Management: Create Task Guidance / Breakdown
@ai_assistant_bp.route('/ai/generate-task', methods=['POST'])
@login_required
def generate_task():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    requirement = (data.get('requirement') or '').strip()
    project_id = data.get('project_id')

    if len(requirement) > 4000:
        return jsonify({'success': False, 'error': "Requirement description exceeds maximum limit (4,000 characters)."}), 400

    project_context = None
    if project_id:
        project_context = GrokService.get_project_metrics_context(project_id, current_user)
        if not project_context:
            return jsonify({'success': False, 'error': "Specified project was not found or is unauthorized."}), 403

    user_text = f"Task Guidance & Review: {requirement[:120]}..." if requirement else "How do I create a task in the platform?"
    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=user_text,
        message_type='task'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.generate_task(requirement if requirement else None, project_context=project_context)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='task'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 4. Task Management: Generate Task Report
@ai_assistant_bp.route('/ai/task-report', methods=['POST'])
@login_required
def generate_task_report():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    project_id = data.get('project_id')

    task_data = GrokService.get_task_report_context(project_id, current_user)
    if not task_data:
        return jsonify({'success': False, 'error': "Could not retrieve task data or unauthorized."}), 403

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Generate Task Report: {task_data['scope']}",
        message_type='task'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.generate_task_report(task_data)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='task'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 5. Task Management: Break Project into Tasks
@ai_assistant_bp.route('/ai/break-project', methods=['POST'])
@login_required
def break_project():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    project_description = (data.get('description') or '').strip()

    if not project_description:
        return jsonify({'success': False, 'error': "Please enter a project description to break into tasks."}), 400
    if len(project_description) > 4000:
        return jsonify({'success': False, 'error': "Description exceeds maximum limit (4,000 characters)."}), 400

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Break Project into Tasks: {project_description[:120]}...",
        message_type='task'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.break_project_into_tasks(project_description)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='task'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 6. Bug Management: Create Bug Report
@ai_assistant_bp.route('/ai/generate-bug', methods=['POST'])
@login_required
def generate_bug():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    problem = (data.get('description') or '').strip()
    project_id = data.get('project_id')

    if not problem:
        return jsonify({'success': False, 'error': "Please describe the problem or bug behavior."}), 400
    if len(problem) > 4000:
        return jsonify({'success': False, 'error': "Description exceeds maximum limit (4,000 characters)."}), 400

    project_context = None
    if project_id:
        project = GrokService.get_authorized_project_by_id(project_id, current_user)
        if not project:
            return jsonify({'success': False, 'error': "Specified project was not found or is unauthorized."}), 403
        project_context = {'name': project.name}

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Create Bug Report: {problem}",
        message_type='bug'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.generate_bug_report(problem, project_context=project_context)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='bug'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 7. Bug Management: Analyze a Bug
@ai_assistant_bp.route('/ai/analyze-bug', methods=['POST'])
@login_required
def analyze_bug():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    bug_details = (data.get('details') or '').strip()

    if not bug_details:
        return jsonify({'success': False, 'error': "Please describe the bug symptoms or paste the error logs."}), 400
    if len(bug_details) > 4000:
        return jsonify({'success': False, 'error': "Details exceed maximum limit (4,000 characters)."}), 400

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Analyze Bug: {bug_details[:120]}...",
        message_type='bug'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.analyze_bug(bug_details)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='bug'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 8. Developer Assistance: Explain Code
@ai_assistant_bp.route('/ai/explain-code', methods=['POST'])
@login_required
def explain_code():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    code = (data.get('code') or '').strip()
    language = (data.get('language') or '').strip()
    question = (data.get('question') or '').strip()

    if not code:
        return jsonify({'success': False, 'error': "Please provide code to explain."}), 400
    if len(code) > 10000:
        return jsonify({'success': False, 'error': "Code snippet exceeds maximum limit (10,000 characters)."}), 400

    display_prompt = f"Explain {language or 'code'} snippet:\n```{language or ''}\n{code[:120]}...\n```"
    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=display_prompt,
        message_type='code'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.explain_code(code, language=language, question=question)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='code'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 9. Developer Assistance: Generate Code
@ai_assistant_bp.route('/ai/generate-code', methods=['POST'])
@login_required
def generate_code():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    requirements = (data.get('requirements') or '').strip()
    language = (data.get('language') or 'python').strip().lower()

    if not requirements:
        return jsonify({'success': False, 'error': "Please describe the code you want to generate."}), 400
    if len(requirements) > 4000:
        return jsonify({'success': False, 'error': "Requirements exceed maximum limit (4,000 characters)."}), 400

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Generate {language.upper()} code for: {requirements[:120]}...",
        message_type='code'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.generate_code(requirements, language=language)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='code'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 10. Daily Productivity: Generate Daily Work Report
@ai_assistant_bp.route('/ai/daily-summary', methods=['POST'])
@login_required
def daily_summary():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    data = request.get_json(silent=True) or {}
    work_done = (data.get('work_done') or '').strip()
    challenges = (data.get('challenges') or '').strip()
    next_steps = (data.get('next_steps') or '').strip()

    if not work_done:
        return jsonify({'success': False, 'error': "Please describe your completed work for today."}), 400
    if len(work_done) > 4000:
        return jsonify({'success': False, 'error': "Work description exceeds maximum limit (4,000 characters)."}), 400

    user_context = GrokService.get_user_today_summary(current_user)

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content=f"Generate Daily Work Report for: {work_done[:100]}...",
        message_type='summary'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.daily_work_summary(work_done, challenges=challenges, next_steps=next_steps, user_context=user_context)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='summary'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


# 11. Daily Productivity: Productivity Summary
@ai_assistant_bp.route('/ai/productivity-summary', methods=['POST'])
@login_required
def productivity_summary():
    if not check_rate_limit(current_user.id):
        return jsonify({'success': False, 'error': "Rate limit exceeded. Please wait a moment."}), 429

    user_context = GrokService.get_user_today_summary(current_user)

    user_msg = AIChatMessage(
        user_id=current_user.id,
        role='user',
        content="Generate Productivity Summary & Coaching Tips",
        message_type='summary'
    )
    db.session.add(user_msg)
    db.session.commit()

    res = GrokService.productivity_summary(current_user, user_context=user_context)
    if res['success']:
        assistant_msg = AIChatMessage(
            user_id=current_user.id,
            role='assistant',
            content=res['content'],
            message_type='summary'
        )
        db.session.add(assistant_msg)
        db.session.commit()
        return jsonify({'success': True, 'reply': res['content']})
    else:
        return jsonify({'success': False, 'error': res.get('error')}), 400 if res.get('is_config_error') else 500


@ai_assistant_bp.route('/ai/clear-history', methods=['POST'])
@login_required
def clear_history():
    """
    Deletes all chat messages belonging to the authenticated user.
    """
    try:
        AIChatMessage.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': "Conversation history cleared successfully."})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': f"Failed to clear history: {str(e)}"}), 500
