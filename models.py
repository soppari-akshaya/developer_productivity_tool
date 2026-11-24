from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    firebase_uid = db.Column(db.String(128), unique=True, nullable=True, index=True)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    full_name = db.Column(db.String(150), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='developer')  # 'admin', 'team_leader', 'developer'
    photo_url = db.Column(db.String(300), nullable=True)
    department = db.Column(db.String(100), nullable=True, default='Engineering')
    bio = db.Column(db.Text, nullable=True)
    phone_number = db.Column(db.String(30), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    # Relationships
    created_projects = db.relationship('Project', backref='creator', lazy=True, foreign_keys='Project.created_by_id')
    project_memberships = db.relationship('ProjectMember', backref='user', lazy=True, cascade='all, delete-orphan')
    assigned_tasks = db.relationship('Task', backref='assignee', lazy=True, foreign_keys='Task.assigned_to_id')
    created_tasks = db.relationship('Task', backref='author', lazy=True, foreign_keys='Task.created_by_id')
    comments = db.relationship('TaskComment', backref='user', lazy=True, cascade='all, delete-orphan')
    snippets = db.relationship('CodeSnippet', backref='user', lazy=True, cascade='all, delete-orphan')
    time_entries = db.relationship('TimeEntry', backref='user', lazy=True, cascade='all, delete-orphan')
    pomodoro_sessions = db.relationship('PomodoroSession', backref='user', lazy=True, cascade='all, delete-orphan')
    reported_issues = db.relationship('Issue', backref='reporter', lazy=True, foreign_keys='Issue.reported_by_id')
    assigned_issues = db.relationship('Issue', backref='assignee', lazy=True, foreign_keys='Issue.assigned_to_id')
    work_logs = db.relationship('WorkLog', backref='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy=True, cascade='all, delete-orphan')
    github_connection = db.relationship('GitHubConnection', backref='user', uselist=False, cascade='all, delete-orphan')
    active_timer = db.relationship('ActiveTimer', backref='user', uselist=False, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.email} ({self.role})>'

    @property
    def role_title(self):
        return self.role.replace('_', ' ').title()


class Project(db.Model):
    __tablename__ = 'projects'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    status = db.Column(db.String(30), default='active')    # 'planning', 'active', 'on_hold', 'completed'
    progress = db.Column(db.Integer, default=0)            # 0 to 100
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    members = db.relationship('ProjectMember', backref='project', lazy=True, cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='project', lazy=True, cascade='all, delete-orphan')
    issues = db.relationship('Issue', backref='project', lazy=True, cascade='all, delete-orphan')


class ProjectMember(db.Model):
    __tablename__ = 'project_members'

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role_in_project = db.Column(db.String(50), default='member')  # 'lead', 'developer', 'reviewer'
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('project_id', 'user_id', name='_project_user_uc'),)


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    deadline = db.Column(db.Date, nullable=True)
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    status = db.Column(db.String(30), default='todo')      # 'todo', 'in_progress', 'in_review', 'completed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    comments = db.relationship('TaskComment', backref='task', lazy=True, cascade='all, delete-orphan')
    time_entries = db.relationship('TimeEntry', backref='task', lazy=True)


class TaskComment(db.Model):
    __tablename__ = 'task_comments'

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CodeSnippet(db.Model):
    __tablename__ = 'code_snippets'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=True)
    language = db.Column(db.String(50), default='javascript')
    code = db.Column(db.Text, nullable=False)
    tags = db.Column(db.String(200), nullable=True)
    is_favorite = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TimeEntry(db.Model):
    __tablename__ = 'time_entries'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    duration_minutes = db.Column(db.Integer, nullable=False)
    duration_seconds = db.Column(db.Integer, nullable=True)
    start_time = db.Column(db.DateTime, nullable=True)
    end_time = db.Column(db.DateTime, nullable=True)
    description = db.Column(db.String(255), nullable=True)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    project = db.relationship('Project', backref=db.backref('time_entries', lazy=True))

    @property
    def display_start_time(self):
        if self.start_time:
            return self.start_time.strftime('%H:%M:%S')
        elif self.created_at and self.duration_minutes:
            est_start = self.created_at - timedelta(minutes=self.duration_minutes)
            return est_start.strftime('%H:%M:%S')
        return self.created_at.strftime('%H:%M:%S') if self.created_at else '--'

    @property
    def display_end_time(self):
        if self.end_time:
            return self.end_time.strftime('%H:%M:%S')
        return self.created_at.strftime('%H:%M:%S') if self.created_at else '--'

    @property
    def formatted_duration(self):
        secs = self.duration_seconds if self.duration_seconds is not None else ((self.duration_minutes or 0) * 60)
        hrs = secs // 3600
        mins = (secs % 3600) // 60
        s = secs % 60
        if hrs > 0:
            return f"{hrs:02d}h {mins:02d}m {s:02d}s"
        return f"{mins:02d}m {s:02d}s"


class ActiveTimer(db.Model):
    __tablename__ = 'active_timers'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=True)
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'), nullable=True)
    description = db.Column(db.String(255), nullable=True)
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_started_at = db.Column(db.DateTime, nullable=True)
    accumulated_seconds = db.Column(db.Integer, default=0, nullable=False)
    status = db.Column(db.String(20), default='running', nullable=False)  # 'running', 'paused', 'stopped'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = db.relationship('Project', backref=db.backref('active_timers', lazy=True))
    task = db.relationship('Task', backref=db.backref('active_timers', lazy=True))

    def get_elapsed_seconds(self):
        if self.status == 'running' and self.last_started_at:
            delta = int((datetime.utcnow() - self.last_started_at).total_seconds())
            return self.accumulated_seconds + max(0, delta)
        return self.accumulated_seconds

    def to_dict(self):
        elapsed = self.get_elapsed_seconds()
        hrs = elapsed // 3600
        mins = (elapsed % 3600) // 60
        secs = elapsed % 60
        formatted = f"{hrs:02d}:{mins:02d}:{secs:02d}"

        return {
            'id': self.id,
            'user_id': self.user_id,
            'project_id': self.project_id,
            'project_name': self.project.name if self.project else None,
            'task_id': self.task_id,
            'task_title': self.task.title if self.task else None,
            'description': self.description or '',
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'last_started_at': self.last_started_at.isoformat() if self.last_started_at else None,
            'accumulated_seconds': self.accumulated_seconds,
            'elapsed_seconds': elapsed,
            'formatted_time': formatted,
            'status': self.status
        }


class PomodoroSession(db.Model):
    __tablename__ = 'pomodoro_sessions'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    duration_minutes = db.Column(db.Integer, default=25)
    session_type = db.Column(db.String(20), default='focus')  # 'focus', 'short_break', 'long_break'
    completed = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Issue(db.Model):
    __tablename__ = 'issues'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey('projects.id'), nullable=False)
    reported_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    severity = db.Column(db.String(20), default='major')   # 'minor', 'major', 'critical'
    priority = db.Column(db.String(20), default='medium')  # 'low', 'medium', 'high', 'critical'
    status = db.Column(db.String(30), default='open')      # 'open', 'in_progress', 'resolved', 'closed'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkLog(db.Model):
    __tablename__ = 'work_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=datetime.utcnow().date)
    completed_tasks = db.Column(db.Text, nullable=True)
    work_performed = db.Column(db.Text, nullable=False)
    challenges = db.Column(db.Text, nullable=True)
    pending_activities = db.Column(db.Text, nullable=True)
    hours_worked = db.Column(db.Float, default=8.0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(255), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class GitHubConnection(db.Model):
    __tablename__ = 'github_connections'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    github_username = db.Column(db.String(100), nullable=False)
    access_token = db.Column(db.String(255), nullable=True)
    avatar_url = db.Column(db.String(255), nullable=True)
    connected_at = db.Column(db.DateTime, default=datetime.utcnow)


class Announcement(db.Model):
    __tablename__ = 'announcements'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    target_role = db.Column(db.String(50), default='all')  # 'all', 'developer', 'team_leader'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='announcements', foreign_keys=[created_by_id])


class AIChatMessage(db.Model):
    __tablename__ = 'ai_chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user', 'assistant', 'system'
    content = db.Column(db.Text, nullable=False)
    message_type = db.Column(db.String(50), default='chat')  # 'chat', 'task', 'bug', 'summary', 'code'
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref=db.backref('ai_messages', lazy=True, cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'role': self.role,
            'content': self.content,
            'message_type': self.message_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


