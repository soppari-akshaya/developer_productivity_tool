import os
from datetime import datetime, date
from flask import current_app
from extensions import db, normalize_role
from models import Project, ProjectMember, Task, TimeEntry, WorkLog, Issue, User

# Try importing OpenAI client
try:
    from openai import OpenAI, APIError, APITimeoutError, AuthenticationError, RateLimitError, APIConnectionError
except ImportError:
    OpenAI = None
    APIError = APITimeoutError = AuthenticationError = RateLimitError = APIConnectionError = Exception


class GrokService:
    """
    Service wrapper for the AI Assistant (powered internally by xAI API via OpenAI Python SDK).
    Strictly follows role-based read-only context retrieval and security constraints.
    Does not display 'Grok' in any user-facing text.
    """

    @classmethod
    def get_api_key(cls):
        """
        Securely retrieves XAI_API_KEY from environment or app config.
        Never hardcoded, never exposed to client.
        """
        key = None
        if current_app:
            key = current_app.config.get('XAI_API_KEY')
        if not key:
            key = os.getenv('XAI_API_KEY')
        if key:
            key = str(key).strip().strip('"\'')
        return key or ''

    @classmethod
    def get_client(cls):
        """
        Instantiates OpenAI client pointed to xAI base URL.
        """
        if OpenAI is None:
            raise RuntimeError("The 'openai' Python package is not installed. Run 'pip install openai' to enable the AI Assistant.")

        api_key = cls.get_api_key()
        if not api_key:
            raise ValueError("xAI API key is not configured. Please set the XAI_API_KEY environment variable in your .env file to enable the AI Assistant.")

        base_url = None
        if current_app:
            base_url = current_app.config.get('XAI_BASE_URL')
        if not base_url:
            base_url = os.getenv('XAI_BASE_URL', 'https://api.x.ai/v1')
        base_url = str(base_url).strip().strip('"\'')

        return OpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=30.0
        )

    @classmethod
    def get_model(cls):
        model = None
        if current_app:
            model = current_app.config.get('XAI_MODEL')
        if not model:
            model = os.getenv('XAI_MODEL', 'grok-4.7')
        return str(model).strip().strip('"\'') or 'grok-4.7'

    @classmethod
    def call_grok(cls, messages, temperature=0.6, max_tokens=1500):
        """
        Executes a completion request against the AI backend.
        Handles API errors, timeouts, and rate limits gracefully.
        """
        try:
            client = cls.get_client()
            model = cls.get_model()

            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens
            )

            if response and response.choices and len(response.choices) > 0:
                reply_text = response.choices[0].message.content or ''
                return {'success': True, 'content': reply_text.strip()}
            else:
                return {'success': False, 'error': "The AI Assistant returned an empty response. Please try again."}

        except ValueError as ve:
            # Missing API key configuration
            return {'success': False, 'error': str(ve), 'is_config_error': True}
        except RuntimeError as re:
            return {'success': False, 'error': str(re), 'is_config_error': True}
        except AuthenticationError:
            return {'success': False, 'error': "Authentication failed. The provided XAI_API_KEY is invalid or expired. Please check your credentials.", 'is_auth_error': True}
        except APITimeoutError:
            return {'success': False, 'error': "The request to the AI Assistant timed out (30s). Please try again with a more concise prompt.", 'is_timeout': True}
        except RateLimitError:
            return {'success': False, 'error': "API rate limit reached. Please wait a moment before sending another request.", 'is_rate_limit': True}
        except APIConnectionError:
            return {'success': False, 'error': "Unable to establish connection to the AI backend. Please check your internet connectivity.", 'is_network_error': True}
        except Exception as e:
            # Clean generic errors without leaking sensitive tokens
            err_msg = str(e)
            api_key = cls.get_api_key()
            if api_key and api_key in err_msg:
                err_msg = err_msg.replace(api_key, "[REDACTED_API_KEY]")
            return {'success': False, 'error': f"AI Assistant service error: {err_msg}"}

    # -------------------------------------------------------------
    # Role-Based Authorized Context Helpers (Strictly Read-Only)
    # -------------------------------------------------------------

    @staticmethod
    def get_user_authorized_projects(user):
        """
        Returns list of projects the user is authorized to view based on RBAC:
        - Admin: All projects
        - Team Leader: Projects created by user OR projects where user is assigned
        - Developer: Projects where user is a team member OR assigned tasks
        """
        if not user or not user.is_authenticated:
            return []

        user_role = normalize_role(user.role)

        if user_role == 'admin':
            projects = Project.query.order_by(Project.created_at.desc()).all()
        elif user_role == 'team_leader':
            member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=user.id).all()]
            projects = Project.query.filter(
                (Project.created_by_id == user.id) | (Project.id.in_(member_pids))
            ).order_by(Project.created_at.desc()).all()
        else:
            member_pids = [m.project_id for m in ProjectMember.query.filter_by(user_id=user.id).all()]
            task_pids = [t.project_id for t in Task.query.filter_by(assigned_to_id=user.id).all()]
            allowed_ids = list(set(member_pids + task_pids))
            if not allowed_ids:
                return []
            projects = Project.query.filter(Project.id.in_(allowed_ids)).order_by(Project.created_at.desc()).all()

        return projects

    @staticmethod
    def get_authorized_project_by_id(project_id, user):
        """
        Returns Project instance only if the user is authorized to view it.
        Prevents parameter tampering across user boundaries.
        """
        if not project_id or not user or not user.is_authenticated:
            return None

        project = db.session.get(Project, project_id)
        if not project:
            return None

        user_role = normalize_role(user.role)
        if user_role == 'admin':
            return project

        if user_role == 'team_leader':
            if project.created_by_id == user.id:
                return project
            is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()
            if is_member:
                return project
            return None

        # Developer
        is_member = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()
        has_task = Task.query.filter_by(project_id=project.id, assigned_to_id=user.id).first()
        if is_member or has_task:
            return project
        return None

    @classmethod
    def get_project_metrics_context(cls, project_id, user):
        """
        Calculates verified real metrics for an authorized project.
        Never invents statistics.
        """
        project = cls.get_authorized_project_by_id(project_id, user)
        if not project:
            return None

        total_tasks = Task.query.filter_by(project_id=project.id).count()
        completed_tasks = Task.query.filter_by(project_id=project.id, status='completed').count()
        in_progress_tasks = Task.query.filter_by(project_id=project.id, status='in_progress').count()
        todo_tasks = Task.query.filter_by(project_id=project.id, status='todo').count()
        in_review_tasks = Task.query.filter_by(project_id=project.id, status='in_review').count()

        # Potential delays
        today = date.today()
        delayed_tasks = Task.query.filter(
            Task.project_id == project.id,
            Task.deadline < today,
            Task.status != 'completed'
        ).all()

        delayed_titles = [t.title for t in delayed_tasks[:5]]

        # Team contributions if available
        team_members = ProjectMember.query.filter_by(project_id=project.id).all()
        contributions = []
        for m in team_members:
            u = db.session.get(User, m.user_id)
            if u:
                assigned_cnt = Task.query.filter_by(project_id=project.id, assigned_to_id=u.id).count()
                done_cnt = Task.query.filter_by(project_id=project.id, assigned_to_id=u.id, status='completed').count()
                contributions.append(f"{u.full_name} ({m.role_in_project}): {done_cnt}/{assigned_cnt} tasks completed")

        return {
            'id': project.id,
            'name': project.name,
            'description': project.description or 'No description provided.',
            'status': project.status,
            'progress': project.progress,
            'priority': project.priority,
            'start_date': project.start_date.strftime('%Y-%m-%d') if project.start_date else 'N/A',
            'end_date': project.end_date.strftime('%Y-%m-%d') if project.end_date else 'N/A',
            'total_tasks': total_tasks,
            'completed_tasks': completed_tasks,
            'in_progress_tasks': in_progress_tasks,
            'todo_tasks': todo_tasks,
            'in_review_tasks': in_review_tasks,
            'pending_tasks': todo_tasks + in_progress_tasks + in_review_tasks,
            'delayed_count': len(delayed_tasks),
            'delayed_samples': delayed_titles,
            'contributions': contributions
        }

    @classmethod
    def get_task_report_context(cls, project_id, user):
        """
        Retrieves real task distribution by status, priority, and assignee for authorized scope.
        """
        if not user or not user.is_authenticated:
            return None

        today = date.today()
        if project_id:
            project = cls.get_authorized_project_by_id(project_id, user)
            if not project:
                return None
            task_query = Task.query.filter_by(project_id=project.id)
            scope_name = project.name
        else:
            user_role = normalize_role(user.role)
            if user_role == 'admin':
                task_query = Task.query
                scope_name = "All Platform Projects"
            elif user_role == 'team_leader':
                pids = [p.id for p in cls.get_user_authorized_projects(user)]
                task_query = Task.query.filter(Task.project_id.in_(pids)) if pids else Task.query.filter_by(id=-1)
                scope_name = "Managed Team Projects"
            else:
                task_query = Task.query.filter_by(assigned_to_id=user.id)
                scope_name = f"{user.full_name}'s Assigned Tasks"

        tasks = task_query.all()
        total = len(tasks)
        completed = sum(1 for t in tasks if t.status == 'completed')
        in_progress = sum(1 for t in tasks if t.status == 'in_progress')
        todo = sum(1 for t in tasks if t.status == 'todo')
        in_review = sum(1 for t in tasks if t.status == 'in_review')
        overdue = sum(1 for t in tasks if t.status != 'completed' and t.deadline and t.deadline < today)

        # Priorities
        critical = sum(1 for t in tasks if t.priority == 'critical')
        high = sum(1 for t in tasks if t.priority == 'high')
        medium = sum(1 for t in tasks if t.priority == 'medium')
        low = sum(1 for t in tasks if t.priority == 'low')

        # Assignee breakdown
        assignee_map = {}
        for t in tasks:
            name = t.assignee.full_name if t.assignee else 'Unassigned'
            assignee_map[name] = assignee_map.get(name, 0) + 1

        return {
            'scope': scope_name,
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'todo': todo,
            'in_review': in_review,
            'overdue': overdue,
            'critical': critical,
            'high': high,
            'medium': medium,
            'low': low,
            'assignees': assignee_map
        }

    @classmethod
    def get_user_today_summary(cls, user):
        """
        Extracts verified user productivity data for the logged-in user only.
        """
        if not user or not user.is_authenticated:
            return {}

        today = date.today()
        entries = TimeEntry.query.filter_by(user_id=user.id, date=today).all()
        total_seconds = sum((e.duration_seconds if e.duration_seconds is not None else ((e.duration_minutes or 0) * 60)) for e in entries)
        total_hours = round(total_seconds / 3600.0, 1)

        completed_tasks = Task.query.filter_by(assigned_to_id=user.id, status='completed').all()
        task_names = [t.title for t in completed_tasks[:5]]

        log = WorkLog.query.filter_by(user_id=user.id, date=today).first()
        work_performed = log.work_performed if log else ''
        challenges = log.challenges if log else ''
        pending = log.pending_activities if log else ''

        return {
            'today_hours': total_hours,
            'completed_tasks': task_names,
            'logged_work': work_performed,
            'challenges': challenges,
            'pending': pending
        }

    # -------------------------------------------------------------
    # Specialized AI Capabilities (11 Predefined Features)
    # -------------------------------------------------------------

    @classmethod
    def chat(cls, user_message, conversation_history=None, user=None):
        """
        General AI Chat with Developer Productivity Tool Assistant.
        """
        system_prompt = (
            "You are the Developer Productivity Tool Assistant, an intelligent AI-powered productivity companion "
            "integrated into the Developer Productivity Tool. "
            "You help software engineers, team leads, and project managers manage projects, create tasks, generate reports, "
            "track bugs, analyze code, and improve engineering productivity. "
            "Be concise, highly practical, technically precise, and use clean markdown formatting with code blocks when helpful. "
            "Never claim you executed code, modified the database, or saved records, because all actions in the platform require user review and confirmation."
        )

        messages = [{"role": "system", "content": system_prompt}]

        if conversation_history:
            for msg in conversation_history[-8:]:
                if msg.get('role') in ('user', 'assistant'):
                    messages.append({"role": msg['role'], "content": msg['content']})

        messages.append({"role": "user", "content": user_message})
        return cls.call_grok(messages, temperature=0.7)

    PROJECT_CREATION_GUIDANCE = (
        "### 📋 How to Create a Project: Comprehensive Guide\n\n"
        "> **Note:** The AI Assistant serves as your productivity guide and does **not** automatically create or save projects in the database. "
        "Please prepare your project details below and submit them directly via the **Project Management** module.\n\n"
        "---\n\n"
        "### 1. 🔑 Important Project Details to Prepare\n"
        "Before creating your project, ensure you have prepared these key elements:\n\n"
        "1. **Project Name:** A concise, recognizable title (e.g., *Customer Analytics & Real-Time Reporting Dashboard*).\n"
        "2. **Project Description:** A clear overview explaining the purpose, business context, and problem the project solves.\n"
        "3. **Objectives:** 2–4 measurable business or engineering goals (e.g., *Reduce query latency by 40%, unify telemetry data*).\n"
        "4. **Technology Stack:** Languages, frameworks, and databases to be utilized (e.g., *Python/Flask, PostgreSQL, Redis, Bootstrap 5*).\n"
        "5. **Start Date and Deadline:** Realistic kickoff date and milestone/release target dates.\n"
        "6. **Team Members:** The project lead/owner, developers, and QA engineers allocated to the initiative.\n"
        "7. **Project Requirements:** Functional and non-functional requirements (security, authentication, scalability, API specifications).\n"
        "8. **Expected Deliverables:** Concrete outputs (e.g., *RESTful APIs, interactive dashboard, unit & integration test suite, API documentation*).\n\n"
        "---\n\n"
        "### 2. 💡 Example of a Well-Defined Project\n\n"
        "- **Project Name:** Automated API Gateway & Rate Limiting Service\n"
        "- **Project Description:** A centralized edge gateway service that authenticates incoming client requests, manages API token quotas, and routes traffic to backend microservices.\n"
        "- **Objectives:**\n"
        "  - Standardize authentication across all client applications.\n"
        "  - Prevent API abuse with distributed sliding-window rate limiting.\n"
        "  - Provide unified request logging and latency telemetry.\n"
        "- **Technology Stack:** Python (Flask), Redis, PostgreSQL, Docker, Nginx.\n"
        "- **Start Date and Deadline:** 2026-12-01 to 2027-02-15\n"
        "- **Team Members:** Lead Architect, 2 Backend Developers, 1 QA Engineer.\n"
        "- **Project Requirements:**\n"
        "  - Token-based API authentication with HMAC-SHA256.\n"
        "  - Per-minute and per-hour throttling tiers.\n"
        "  - Response headers indicating quota remaining (`X-RateLimit-Remaining`).\n"
        "  - Sub-15ms overhead per proxied request.\n"
        "- **Expected Deliverables:**\n"
        "  - API Gateway service and reverse proxy routing engine.\n"
        "  - Admin management interface for API keys and rate limits.\n"
        "  - Automated test suite with 90%+ branch coverage.\n"
        "  - Deployment runbook and OpenAPI 3.0 documentation.\n\n"
        "---\n\n"
        "### 3. 🛠️ Steps to Create the Project Manually in the App\n\n"
        "Follow these steps in the Developer Productivity Tool:\n\n"
        "1. **Navigate to Projects:** Click **Projects** in the left sidebar navigation menu.\n"
        "2. **Open Creation Form:** Click the **+ Create Project** button in the top-right corner (or visit `/projects/create`).\n"
        "3. **Fill in Required Information:**\n"
        "   - Enter your **Project Name** and **Description**.\n"
        "   - Set the **Start Date** and **End Date**.\n"
        "   - Choose the initial **Priority** (*Low, Medium, High, Critical*) and **Status** (*Planning, Active*).\n"
        "   - Select the assigned **Team Members / Developers** from the list.\n"
        "4. **Save the Project:** Click **Create Project** to save your project to the database.\n"
        "5. **Begin Tracking:** Your project will appear in your Projects dashboard, where you can now assign tasks, track sprint progress, and monitor team activity."
    )

    TASK_CREATION_GUIDANCE = (
        "### 📋 How to Create a Task: Comprehensive Guide\n\n"
        "> **Note:** The AI Assistant serves as your productivity guide and does **not** automatically create or save tasks in the database. "
        "Please prepare your task details below and submit them directly via the **Task Management** module.\n\n"
        "---\n\n"
        "### 1. 🔑 Important Task Details to Prepare\n"
        "Before creating a task, gather the following necessary details:\n\n"
        "1. **Task Title:** A specific, action-oriented title describing the exact unit of work (e.g., *Implement Redis Caching Layer for Dashboard Metrics*).\n"
        "2. **Task Description:** A clear breakdown of the problem, implementation instructions, and technical context.\n"
        "3. **Related Project:** The active project to which this task belongs.\n"
        "4. **Assigned Developer:** The specific team member responsible for executing the task.\n"
        "5. **Priority:** Urgency level (*Low, Medium, High, Critical*) based on project milestones and blockers.\n"
        "6. **Start Date and Due Date:** Target kickoff date and completion deadline.\n"
        "7. **Status:** The initial workflow state (*To Do / Todo, In Progress, Review*).\n"
        "8. **Expected Outcome:** Clear acceptance criteria and definition of done (e.g., *Unit tests pass, cache hit ratio > 80%, API latency under 50ms*).\n\n"
        "---\n\n"
        "### 2. 💡 Example of a Well-Defined Task\n\n"
        "- **Task Title:** Implement OAuth 2.0 GitHub Login Integration\n"
        "- **Task Description:** Integrate GitHub OAuth 2.0 authentication flow to allow developers to sign in using their GitHub credentials alongside standard email/password login.\n"
        "- **Related Project:** Developer Productivity Platform\n"
        "- **Assigned Developer:** Backend Developer (e.g., Dev Alex)\n"
        "- **Priority:** High\n"
        "- **Start Date and Due Date:** 2026-12-01 to 2026-12-04\n"
        "- **Status:** To Do\n"
        "- **Expected Outcome / Acceptance Criteria:**\n"
        "  - [ ] User can click 'Sign in with GitHub' on the login page.\n"
        "  - [ ] GitHub callback exchanges authorization code for user access token securely.\n"
        "  - [ ] Existing users with matching email are linked; new accounts are created with developer role.\n"
        "  - [ ] Session is initialized and user is redirected to developer dashboard.\n"
        "  - [ ] Error states (denied permissions, network failures) display user-friendly flash messages.\n\n"
        "---\n\n"
        "### 3. 🛠️ Steps to Create the Task Manually in the App\n\n"
        "Follow these steps in the Developer Productivity Tool:\n\n"
        "1. **Navigate to Task Management:** Click **Task Management** (or **My Tasks** / **Sprint Tasks**) in the left sidebar navigation menu.\n"
        "2. **Open Creation Form:** Click the **+ New Task** button (or visit `/tasks/create`).\n"
        "3. **Fill in Task Information:**\n"
        "   - Enter your **Task Title** and detailed **Description**.\n"
        "   - Select the **Associated Project** from the dropdown menu.\n"
        "   - Choose the **Assigned Developer** responsible for the task.\n"
        "   - Select the **Priority** (*Low, Medium, High, Critical*) and initial **Status** (*To Do, In Progress*).\n"
        "   - Set the **Deadline / Due Date**.\n"
        "4. **Save the Task:** Click **Create Task** to persist it in the database.\n"
        "5. **Collaborate:** The assigned developer will automatically receive a notification and the task will appear in the Task Board and Gantt/Sprint charts."
    )

    # 1. Project Management: Create Project Proposal / Guidance
    @classmethod
    def create_project_proposal(cls, details=None):
        """
        Provides guidance and information on how to create a project in the Project Management module.
        Does NOT create or insert any project into the database.
        If details are provided, reviews the draft, checks the 8 required elements, suggests improvements,
        and provides manual creation steps.
        """
        if not details or not details.strip():
            return {'success': True, 'content': cls.PROJECT_CREATION_GUIDANCE}

        system_prompt = (
            "You are a Senior Project & Program Manager guide in the Developer Productivity Tool.\n"
            "IMPORTANT: The AI Assistant does NOT create, save, or insert projects into the database.\n"
            "Your role is strictly to provide guidance, review the user's project draft, and help them prepare for manual creation.\n\n"
            "Evaluate their project input against the 8 required project details:\n"
            "1. Project name\n"
            "2. Project description\n"
            "3. Objectives\n"
            "4. Technology stack\n"
            "5. Start date and deadline\n"
            "6. Team members\n"
            "7. Project requirements\n"
            "8. Expected deliverables\n\n"
            "Point out any missing or vague information, suggest improvements, and structure their project clearly.\n"
            "Always conclude with the manual steps to create the project using the Project Management module:\n"
            "1. Navigate to Projects in the sidebar navigation (/projects).\n"
            "2. Click '+ Create Project' (/projects/create).\n"
            "3. Fill in the Project Name, Description, Start & End Dates, Priority, Status, and assign Team Members.\n"
            "4. Click 'Create Project' to save it to the database."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Please review this draft project and provide guidance:\n{details}"}
        ]
        return cls.call_grok(messages, temperature=0.5, max_tokens=1300)

    # 2. Project Management: Generate Project Report
    @classmethod
    def summarize_project(cls, metrics):
        """
        Generates comprehensive Project Progress Report using verified real database metrics.
        Never invents statistics.
        """
        system_prompt = (
            "You are an executive Technical Program Manager. "
            "Analyze the provided real verified project metrics and produce a comprehensive Project Progress Report. "
            "CRITICAL: Do NOT invent statistics, task counts, or percentages. Use ONLY the numbers provided in the data. "
            "Format the report as follows:\n\n"
            "### 📊 Project Progress Report: {Project Name}\n\n"
            "**Current Status:** {Status} | **Progress:** {Progress}% | **Priority:** {Priority}\n"
            "**Timeline:** {Start Date} to {End Date}\n\n"
            "#### 📈 Task Execution Overview\n"
            "- **Total Tasks:** {Total}\n"
            "- **Completed:** {Completed}\n"
            "- **In Progress:** {In Progress}\n"
            "- **In Review:** {In Review}\n"
            "- **Pending / To Do:** {Pending}\n\n"
            "#### 👥 Team Contributions & Staffing\n"
            "<Summarize the team contribution details provided in the data>\n\n"
            "#### ⚠️ Risk & Delay Analysis\n"
            "<Highlight potential delays based on the provided overdue task counts and timeline, or state on schedule if 0 delays>\n\n"
            "#### 🎯 Strategic Recommendations & Next Actions\n"
            "1. ...\n2. ...\n3. ..."
        )

        data_content = (
            f"Project Data (Verified from Database):\n"
            f"- Project Name: {metrics['name']}\n"
            f"- Description: {metrics['description']}\n"
            f"- Current Status: {metrics['status']}\n"
            f"- Progress: {metrics['progress']}%\n"
            f"- Priority: {metrics['priority']}\n"
            f"- Start Date: {metrics['start_date']} | End Date: {metrics['end_date']}\n"
            f"- Total Tasks: {metrics['total_tasks']}\n"
            f"- Completed Tasks: {metrics['completed_tasks']}\n"
            f"- In Progress Tasks: {metrics['in_progress_tasks']}\n"
            f"- In Review Tasks: {metrics['in_review_tasks']}\n"
            f"- To Do Tasks: {metrics['todo_tasks']}\n"
            f"- Pending Tasks Total: {metrics['pending_tasks']}\n"
            f"- Overdue / Delayed Tasks Count: {metrics['delayed_count']}\n"
        )
        if metrics.get('delayed_samples'):
            data_content += f"- Overdue Task Examples: {', '.join(metrics['delayed_samples'])}\n"
        if metrics.get('contributions'):
            data_content += "- Team Contributions:\n  " + "\n  ".join(metrics['contributions']) + "\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the Project Progress Report from these verified database metrics:\n\n{data_content}"}
        ]
        return cls.call_grok(messages, temperature=0.3, max_tokens=1300)

    # 3. Task Management: Create a Task Guidance / Breakdown
    @classmethod
    def generate_task(cls, requirement=None, project_context=None):
        """
        Provides guidance and information on how to create a task in the Task Management module.
        Does NOT create or insert any task into the database.
        If requirement is provided, reviews the requirement, structures it according to the 8 required task fields,
        suggests acceptance criteria and improvements, and provides manual creation steps.
        """
        if not requirement or not requirement.strip():
            return {'success': True, 'content': cls.TASK_CREATION_GUIDANCE}

        system_prompt = (
            "You are an expert Agile Scrum Master and Software Lead guide in the Developer Productivity Tool.\n"
            "IMPORTANT: The AI Assistant does NOT create, save, or insert tasks into the database.\n"
            "Your role is strictly to provide guidance, review the user's task requirement, and help them prepare for manual creation.\n\n"
            "Structure and evaluate their input against the 8 required task details:\n"
            "1. Task title (action-oriented)\n"
            "2. Task description (clear objective and scope)\n"
            "3. Related project\n"
            "4. Assigned developer (role or specific assignee)\n"
            "5. Priority (Low, Medium, High, Critical with rationale)\n"
            "6. Start date and due date (estimated timeframe)\n"
            "7. Status (To Do, In Progress, Review)\n"
            "8. Expected outcome / Acceptance criteria (checklist of verifiable conditions)\n\n"
            "Always conclude with the manual steps to create the task using the Task Management module:\n"
            "1. Navigate to Task Management in the sidebar navigation (/tasks).\n"
            "2. Click '+ New Task' (/tasks/create).\n"
            "3. Fill in the Task Title, Description, Associated Project, Assigned Developer, Priority, Status, and Due Date.\n"
            "4. Click 'Create Task' to save it to the database."
        )

        user_content = f"Please review this task requirement and provide guidance:\n{requirement}"
        if project_context:
            user_content += f"\n\nTarget Project: {project_context.get('name')} (Status: {project_context.get('status')})"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        return cls.call_grok(messages, temperature=0.5, max_tokens=1300)

    # 4. Task Management: Generate Task Report
    @classmethod
    def generate_task_report(cls, task_data):
        """
        Summarizes completed, pending, overdue, and in-progress tasks, including distribution by priority and assignee.
        """
        system_prompt = (
            "You are a Sprint Operations Lead. "
            "Analyze the provided verified sprint task statistics and produce a clear, structured Task Summary Report. "
            "CRITICAL: Do NOT invent statistics. Use ONLY the verified data provided.\n\n"
            "Format:\n"
            "### 📋 Sprint Task Summary Report: {Scope}\n\n"
            "#### 📊 Task Status Breakdown\n"
            "- **Total Tasks:** {Total}\n"
            "- **Completed:** {Completed} ({Completion Rate}%)\n"
            "- **In Progress:** {In Progress}\n"
            "- **In Review:** {In Review}\n"
            "- **Pending / To Do:** {To Do}\n"
            "- **Overdue Tasks:** {Overdue}\n\n"
            "#### ⚡ Priority Distribution\n"
            "- **Critical:** {Critical} | **High:** {High} | **Medium:** {Medium} | **Low:** {Low}\n\n"
            "#### 👤 Assignee Workload Distribution\n"
            "<List distribution across assignees based on data>\n\n"
            "#### ⚠️ Bottlenecks & Sprint Focus Recommendations\n"
            "1. ...\n2. ...\n3. ..."
        )

        rate = round((task_data['completed'] / task_data['total'] * 100), 1) if task_data['total'] > 0 else 0
        assignee_str = "\n".join([f"- {name}: {cnt} tasks" for name, cnt in task_data['assignees'].items()]) if task_data['assignees'] else "No assignees assigned."

        content = (
            f"Scope: {task_data['scope']}\n"
            f"Total Tasks: {task_data['total']}\n"
            f"Completed: {task_data['completed']} ({rate}%)\n"
            f"In Progress: {task_data['in_progress']}\n"
            f"In Review: {task_data['in_review']}\n"
            f"To Do: {task_data['todo']}\n"
            f"Overdue: {task_data['overdue']}\n"
            f"Critical Priority: {task_data['critical']}\n"
            f"High Priority: {task_data['high']}\n"
            f"Medium Priority: {task_data['medium']}\n"
            f"Low Priority: {task_data['low']}\n"
            f"Assignee Counts:\n{assignee_str}\n"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the Task Summary Report from these verified numbers:\n\n{content}"}
        ]
        return cls.call_grok(messages, temperature=0.3, max_tokens=1200)

    # 5. Task Management: Break Project into Tasks
    @classmethod
    def break_project_into_tasks(cls, project_description):
        """
        Takes project description and breaks it into a structured list of tasks and subtasks required to complete it.
        """
        system_prompt = (
            "You are a Technical Lead and Scrum Master. "
            "Analyze the project description and break it down into a structured Work Breakdown Structure (WBS) with realistic tasks and subtasks.\n\n"
            "Format:\n"
            "### 🏗️ Project Work Breakdown\n\n"
            "#### 🔹 Phase 1: Planning & Architecture\n"
            "1. **Task Title** (Priority: High | Est: 2 days)\n"
            "   - Description: ...\n"
            "   - Subtasks:\n"
            "     - [ ] ...\n"
            "     - [ ] ...\n\n"
            "#### 🔹 Phase 2: Core Development & Implementation\n"
            "2. **Task Title** (Priority: High | Est: 3 days)\n"
            "   - Description: ...\n"
            "   - Subtasks:\n"
            "     - [ ] ...\n"
            "     - [ ] ...\n\n"
            "#### 🔹 Phase 3: Testing, Quality Assurance & Deployment\n"
            "3. **Task Title** (Priority: Medium | Est: 2 days)\n"
            "   - Description: ...\n"
            "   - Subtasks:\n"
            "     - [ ] ...\n\n"
            "⚠️ Review these proposed tasks. You can adopt and create any of these items in the Task Management module."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Break down this project into tasks:\n\n{project_description}"}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1400)

    # 6. Bug Management: Create a Bug Report
    @classmethod
    def generate_bug_report(cls, problem_description, project_context=None):
        """
        Prepares professional bug reports with title, description, steps to reproduce, expected, actual, severity, priority, suggested solution.
        """
        system_prompt = (
            "You are a Senior QA Engineer. Help the user prepare a professional bug report from their description.\n\n"
            "Format:\n"
            "### 🐛 Bug Title\n<Clear symptom and component area>\n\n"
            "### 📝 Description\n<Detailed summary of the failure and environment impact>\n\n"
            "### 🔄 Steps to Reproduce\n1. Navigate to ...\n2. Perform action ...\n3. Observe ...\n\n"
            "### 🎯 Expected Result\n<What should happen under normal operation>\n\n"
            "### ❌ Actual Result\n<What actually occurs, including error messages>\n\n"
            "### 🚨 Severity & Priority\n- **Severity:** <Minor | Major | Critical>\n- **Priority:** <Low | Medium | High | Critical>\n\n"
            "### 💡 Suggested Solution & Root Cause Direction\n<Hypothesis or code fix guidance>\n\n"
            "⚠️ Please review this bug report before filing it in the Bug Tracker."
        )

        user_content = f"Problem Description:\n{problem_description}"
        if project_context:
            user_content += f"\n\nProject: {project_context.get('name')}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1200)

    # 7. Bug Management: Analyze a Bug
    @classmethod
    def analyze_bug(cls, bug_details):
        """
        Explains possible cause of a reported bug, suggests debugging steps and solutions.
        Does NOT claim fixed without verification.
        """
        system_prompt = (
            "You are an expert Debugging Specialist and Systems Architect. "
            "Analyze the reported bug, error logs, or symptoms provided by the user. "
            "CRITICAL: Do NOT claim that the bug has been fixed without verification.\n\n"
            "Format:\n"
            "### 🔍 Bug Diagnostic Analysis\n\n"
            "#### 💡 Likely Root Causes\n"
            "1. **Hypothesis 1:** ...\n"
            "2. **Hypothesis 2:** ...\n\n"
            "#### 🛠️ Recommended Debugging & Verification Steps\n"
            "- [ ] Step 1: Check logs / stack trace at ...\n"
            "- [ ] Step 2: Reproduce with minimal test case ...\n"
            "- [ ] Step 3: Inspect database state / network payload ...\n\n"
            "#### 🩹 Potential Fix Strategies & Code Solutions\n"
            "```python\n# Suggested fix pattern for review and testing\n```\n\n"
            "#### ⚠️ Verification Checklist (Ensure fix before closing)\n"
            "- [ ] Run automated regression test suite\n"
            "- [ ] Verify in staging environment"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this bug:\n\n{bug_details}"}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1300)

    # 8. Developer Assistance: Explain Code
    @classmethod
    def explain_code(cls, code, language=None, question=None):
        """
        Explains code in simple language: purpose, functions, logic, important sections, bugs, improvements.
        Strictly does NOT execute code.
        """
        system_prompt = (
            "You are a Principal Software Architect and code reviewer. "
            "Analyze the provided code thoroughly. DO NOT execute the code. "
            "Explain it in clear, simple language with the following structure:\n\n"
            "### 💡 Purpose & Overview\n<High-level summary of what this code does>\n\n"
            "### 🔍 Detailed Logic & Important Sections\n<Walk through the functions, control flow, and core algorithms step-by-step>\n\n"
            "### ⚠️ Possible Errors & Edge Cases\n<Identify null pointer risks, exception handling gaps, off-by-one errors, or concurrency concerns>\n\n"
            "### ⚡ Improvement Suggestions & Best Practices\n<Recommend idiomatic conventions, performance tweaks, or readability improvements>\n\n"
            "### 🚀 Optimized Alternative Version\n```<language>\n<Clean, refactored code with explanatory comments>\n```"
        )

        user_content = f"Language: {language or 'Auto-detect'}\n\n```\n{code}\n```"
        if question:
            user_content += f"\n\nUser Question: {question}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1600)

    # 9. Developer Assistance: Generate Code
    @classmethod
    def generate_code(cls, requirements, language="python"):
        """
        Generates sample code in Python, Java, JavaScript, HTML, CSS, or SQL with explanation in readable code block.
        """
        system_prompt = (
            "You are a Senior Polyglot Software Engineer. "
            "Generate production-grade, well-commented sample code based on the user's requirements. "
            "Supported languages include Python, Java, JavaScript, HTML, CSS, and SQL. "
            "Format:\n\n"
            "### 💻 Generated Code: {Language}\n\n"
            "```{language}\n// Complete, robust, clean implementation with inline comments\n```\n\n"
            "### 🔍 How It Works\n<Step-by-step explanation of the core functions, data structures, and algorithms>\n\n"
            "### 🧪 How to Test & Run It\n<Brief usage example and verification steps>\n\n"
            "### 💡 Edge Cases & Production Considerations\n<Brief recommendations for scaling, error handling, or security>"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Language: {language}\n\nRequirements:\n{requirements}"}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1600)

    # 10. Daily Productivity: Generate Daily Work Report
    @classmethod
    def daily_work_summary(cls, user_entered_work, challenges=None, next_steps=None, user_context=None):
        """
        Summarizes user's daily work using actual daily work logs and tracked time.
        Does NOT invent activities or hours.
        """
        system_prompt = (
            "You are an Engineering Productivity Lead. "
            "Format the user's completed work, challenges, and next steps into a clean, professional Daily Work Report. "
            "CRITICAL: Do NOT invent completed work or fictitious hours. Rely strictly on the information provided.\n\n"
            "Format:\n"
            "### 📝 Daily Work Report\n\n"
            "#### ✅ Completed Activities\n- ...\n\n"
            "#### 🔄 In Progress & Ongoing Work\n- ...\n\n"
            "#### 🚧 Challenges & Blockers Encountered\n- ...\n\n"
            "#### 🎯 Next Steps (Tomorrow's Priority)\n- ...\n\n"
            "#### ⏱️ Verified Working Time & Metrics\n<Reference actual tracked hours and system records if provided, otherwise note as reported by user>"
        )

        user_content = f"User Reported Work:\n{user_entered_work}\n"
        if challenges:
            user_content += f"\nChallenges Encountered:\n{challenges}\n"
        if next_steps:
            user_content += f"\nPlanned Next Steps:\n{next_steps}\n"
        if user_context and user_context.get('today_hours'):
            user_content += f"\nActual Time Tracker Hours Today: {user_context['today_hours']} hours\n"
            if user_context.get('completed_tasks'):
                user_content += f"Tasks Marked Completed Today: {', '.join(user_context['completed_tasks'])}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1100)

    # 11. Daily Productivity: Productivity Summary
    @classmethod
    def productivity_summary(cls, user, user_context=None):
        """
        Summarizes available task completion and time-tracking info with actionable suggestions to improve productivity.
        """
        system_prompt = (
            "You are an Agile Productivity Coach. "
            "Analyze the user's verified task completion and time-tracking metrics to provide an empowering Productivity Summary. "
            "CRITICAL: Do NOT invent statistics. Use only verified authorized user data.\n\n"
            "Format:\n"
            "### 🚀 Developer Productivity Summary\n\n"
            "#### ⏱️ Time Allocation & Focus\n"
            "- **Tracked Hours Today:** {Hours} hrs\n"
            "- **Completed Tasks:** {Completed Count}\n\n"
            "#### 🎯 Sprint Velocity & Momentum\n"
            "<Evaluate progress towards sprint deliverables based on actual numbers>\n\n"
            "#### 💡 Actionable Productivity Tips\n"
            "1. **Focus Optimization:** ...\n"
            "2. **Task Prioritization:** ...\n"
            "3. **Flow State Suggestion:** ..."
        )

        context_str = f"User: {user.full_name} ({user.role})\n"
        if user_context:
            context_str += f"- Today's Tracked Hours: {user_context.get('today_hours', 0)} hrs\n"
            if user_context.get('completed_tasks'):
                context_str += f"- Completed Tasks Today: {', '.join(user_context['completed_tasks'])}\n"
            if user_context.get('logged_work'):
                context_str += f"- Work Log Summary: {user_context['logged_work']}\n"

        # Additional task metrics
        assigned_tasks = Task.query.filter_by(assigned_to_id=user.id).all()
        total_assigned = len(assigned_tasks)
        done_assigned = sum(1 for t in assigned_tasks if t.status == 'completed')
        in_progress_assigned = sum(1 for t in assigned_tasks if t.status == 'in_progress')
        context_str += f"- Total Assigned Sprint Tasks: {total_assigned}\n"
        context_str += f"- Overall Completed: {done_assigned} | In Progress: {in_progress_assigned}\n"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Generate the Productivity Summary based on this verified data:\n\n{context_str}"}
        ]
        return cls.call_grok(messages, temperature=0.4, max_tokens=1100)
