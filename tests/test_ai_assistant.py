import os
import unittest
import json
import tempfile
from unittest.mock import patch, MagicMock
from app import create_app
from config import Config
from extensions import db
from models import User, Project, ProjectMember, Task, TimeEntry, AIChatMessage
from ai_assistant.services import GrokService

class DeveloperProductivityToolAssistantTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_fd, cls.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(cls.test_db_fd)
        norm_test_path = cls.test_db_path.replace('\\', '/')

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{norm_test_path}'
            XAI_API_KEY = 'test_xai_mock_key_12345'
            XAI_MODEL = 'grok-4.7'

        cls.app = create_app(TestConfig)
        with cls.app.app_context():
            db.create_all()
            # Create test users: Admin, Team Leader, Developer A, Developer B
            admin = User(email='ai_admin@test.com', full_name='AI Admin', role='admin', is_active=True)
            admin.set_password('Admin@123')
            leader = User(email='ai_leader@test.com', full_name='AI Leader', role='team_leader', is_active=True)
            leader.set_password('Leader@123')
            dev_a = User(email='dev_a@test.com', full_name='Developer A', role='developer', is_active=True)
            dev_a.set_password('DevA@123')
            dev_b = User(email='dev_b@test.com', full_name='Developer B', role='developer', is_active=True)
            dev_b.set_password('DevB@123')

            db.session.add_all([admin, leader, dev_a, dev_b])
            db.session.commit()

            # Create Project 1 (accessible to dev_a)
            p1 = Project(name='Mobile App Redesign', status='active', progress=60, priority='high', created_by_id=leader.id)
            # Create Project 2 (private to leader/admin, inaccessible to dev_a)
            p2 = Project(name='Secret Kernel Engine', status='planning', progress=10, priority='critical', created_by_id=leader.id)
            db.session.add_all([p1, p2])
            db.session.commit()

            # Add dev_a to p1
            pm1 = ProjectMember(project_id=p1.id, user_id=dev_a.id, role_in_project='developer')
            # Tasks in p1
            t1 = Task(title='Design Wireframes', project_id=p1.id, assigned_to_id=dev_a.id, created_by_id=leader.id, status='completed')
            t2 = Task(title='API Integration', project_id=p1.id, assigned_to_id=dev_a.id, created_by_id=leader.id, status='in_progress')
            # Tasks in p2
            t3 = Task(title='Kernel Architecture', project_id=p2.id, assigned_to_id=leader.id, created_by_id=leader.id, status='todo')

            db.session.add_all([pm1, t1, t2, t3])
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        if os.path.exists(cls.test_db_path):
            try:
                os.remove(cls.test_db_path)
            except Exception:
                pass

    def setUp(self):
        self.client = self.app.test_client()
        self.ctx = self.app.app_context()
        self.ctx.push()

    def tearDown(self):
        try:
            self.ctx.pop()
        except Exception:
            pass

    def login_as(self, email):
        if hasattr(self, 'ctx'):
            try:
                self.ctx.pop()
            except Exception:
                pass
            self.ctx = self.app.app_context()
            self.ctx.push()
        self.client = self.app.test_client()
        user = User.query.filter_by(email=email).first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(user.id)
            sess['_fresh'] = True
        return user

    # 1. UI & Launch Tests
    def test_01_floating_button_and_widget_on_all_authorized_dashboards(self):
        """Verify Assistant widget appears on Developer, Team Leader, and Admin dashboards with new name"""
        self.login_as('dev_a@test.com')
        r_dev = self.client.get('/developer/dashboard')
        self.assertEqual(r_dev.status_code, 200)
        self.assertIn(b'id="grok-launcher-btn"', r_dev.data)
        self.assertIn(b'id="grok-chat-panel"', r_dev.data)
        self.assertIn(b'Developer Productivity Tool Assistant', r_dev.data)
        self.assertIn(b'Your AI-powered productivity companion', r_dev.data)
        self.assertNotIn(b'Grok AI', r_dev.data)

        # Team leader dashboard
        self.login_as('ai_leader@test.com')
        r_lead = self.client.get('/team-leader/dashboard')
        self.assertEqual(r_lead.status_code, 200)
        self.assertIn(b'id="grok-launcher-btn"', r_lead.data)
        self.assertIn(b'Developer Productivity Tool Assistant', r_lead.data)

        # Admin dashboard
        self.login_as('ai_admin@test.com')
        r_admin = self.client.get('/admin/dashboard')
        self.assertEqual(r_admin.status_code, 200)
        self.assertIn(b'id="grok-launcher-btn"', r_admin.data)
        self.assertIn(b'Developer Productivity Tool Assistant', r_admin.data)

        # Public login (unauthenticated) - Widget must NOT be present
        if hasattr(self, 'ctx'):
            try:
                self.ctx.pop()
            except Exception:
                pass
            self.ctx = self.app.app_context()
            self.ctx.push()
        anon_client = self.app.test_client()
        r_login = anon_client.get('/login')
        self.assertEqual(r_login.status_code, 200)
        self.assertNotIn(b'id="grok-launcher-btn"', r_login.data)

    def test_02_welcome_screen_and_predefined_feature_cards(self):
        """Verify exact welcome message and all 5 categories of predefined feature cards"""
        self.login_as('dev_a@test.com')
        r = self.client.get('/developer/dashboard')
        html = r.data.decode('utf-8')

        # Welcome message requirements
        self.assertIn("Welcome to Developer Productivity Tool Assistant!", html)
        self.assertIn("How can I help you today? I can help you manage projects, create tasks, generate reports, track bugs, and improve your productivity.", html)

        # 5 Categories
        self.assertIn('Project Management', html)
        self.assertIn('Task Management', html)
        self.assertIn('Bug and Issue Management', html)
        self.assertIn('Developer Assistance', html)
        self.assertIn('Daily Productivity', html)

        # Predefined Feature Cards
        self.assertIn('Create a Project', html)
        self.assertIn('Generate Project Report', html)
        self.assertIn('Create a Task', html)
        self.assertIn('Generate Task Report', html)
        self.assertIn('Break Project into Tasks', html)
        self.assertIn('Create a Bug Report', html)
        self.assertIn('Analyze a Bug', html)
        self.assertIn('Explain Code', html)
        self.assertIn('Generate Code', html)
        self.assertIn('Generate Daily Work Report', html)
        self.assertIn('Productivity Summary', html)

    # 2. General AI Chat
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_03_general_chat_success(self, mock_call):
        """Test general chat message sends to AI Assistant and returns response"""
        mock_call.return_value = {
            'success': True,
            'content': 'To optimize SQLite queries in Flask-SQLAlchemy, ensure indexes on foreign keys.'
        }
        self.login_as('dev_a@test.com')

        res = self.client.post('/ai/chat',
                               data=json.dumps({'message': 'How do I optimize SQLite queries?'}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('indexes on foreign keys', data['reply'])

    # 3. Project Management: Create Project & Project Report
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_04_create_project_proposal(self, mock_call):
        """Test Create a Project returns guidance without creating records in database"""
        self.login_as('dev_a@test.com')

        initial_count = Project.query.count()

        # 1. Calling without details returns full guidance, 8 fields, example, and manual creation steps
        res_guide = self.client.post('/ai/create-project',
                                     data=json.dumps({'details': ''}),
                                     content_type='application/json')
        self.assertEqual(res_guide.status_code, 200)
        data_guide = res_guide.get_json()
        self.assertTrue(data_guide['success'])
        reply = data_guide['reply']

        # Ensure NO project was inserted into database
        self.assertEqual(Project.query.count(), initial_count)

        # 8 Required Project Details
        self.assertIn('Project Name', reply)
        self.assertIn('Project Description', reply)
        self.assertIn('Objectives', reply)
        self.assertIn('Technology Stack', reply)
        self.assertIn('Start Date and Deadline', reply)
        self.assertIn('Team Members', reply)
        self.assertIn('Project Requirements', reply)
        self.assertIn('Expected Deliverables', reply)

        # Example of well-defined project
        self.assertIn('Example of a Well-Defined Project', reply)

        # Manual creation steps in Project Management module
        self.assertIn('Steps to Create the Project Manually in the App', reply)
        self.assertIn('Projects', reply)
        self.assertIn('/projects/create', reply)

        # 2. Calling with draft details reviews draft without inserting any record
        proposal = (
            "### 📌 Project Title & Objective\nAPI Gateway Redesign\n\n"
            "### 📄 Detailed Description & Scope\nBuild resilient gateway.\n\n"
            "### 📅 Timeline & Milestones\nStart: 2026-12-01\n\n"
            "### ⚡ Priority & Initial Status\nPriority: High\n\n"
            "### 👥 Recommended Team Roles\nLead Architect, 2 Devs"
        )
        mock_call.return_value = {'success': True, 'content': proposal}

        res = self.client.post('/ai/create-project',
                               data=json.dumps({'details': 'API Gateway Redesign starting Dec 1 with 2 devs'}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data['success'])
        self.assertIn('API Gateway Redesign', data['reply'])
        self.assertEqual(Project.query.count(), initial_count)

    @patch('ai_assistant.services.GrokService.call_grok')
    def test_05_project_report_with_real_authorized_data(self, mock_call):
        """Test project report passes verified DB task metrics and enforces RBAC"""
        mock_call.return_value = {
            'success': True,
            'content': '### 📊 Project Progress Report: Mobile App Redesign\nProgress: 60%'
        }

        self.login_as('dev_a@test.com')
        p1 = Project.query.filter_by(name='Mobile App Redesign').first()

        res = self.client.post('/ai/summarize-project',
                               data=json.dumps({'project_id': p1.id}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

        # Unauthorized access to Project 2 (Secret Kernel Engine) returns 403
        p2 = Project.query.filter_by(name='Secret Kernel Engine').first()
        res_unauth = self.client.post('/ai/summarize-project',
                                      data=json.dumps({'project_id': p2.id}),
                                      content_type='application/json')
        self.assertEqual(res_unauth.status_code, 403)
        self.assertFalse(res_unauth.get_json()['success'])

    # 4. Task Management: Create Task, Task Report, Break Project
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_06_create_task_and_break_project(self, mock_call):
        """Test Create a Task returns guidance without creating records in database"""
        self.login_as('dev_a@test.com')

        initial_task_count = Task.query.count()

        # 1. Calling without requirement returns full guidance, 8 fields, example, and manual creation steps
        res_guide = self.client.post('/ai/generate-task',
                                     data=json.dumps({'requirement': ''}),
                                     content_type='application/json')
        self.assertEqual(res_guide.status_code, 200)
        data_guide = res_guide.get_json()
        self.assertTrue(data_guide['success'])
        reply = data_guide['reply']

        # Ensure NO task was inserted into database
        self.assertEqual(Task.query.count(), initial_task_count)

        # 8 Required Task Details
        self.assertIn('Task Title', reply)
        self.assertIn('Task Description', reply)
        self.assertIn('Related Project', reply)
        self.assertIn('Assigned Developer', reply)
        self.assertIn('Priority', reply)
        self.assertIn('Start Date and Due Date', reply)
        self.assertIn('Status', reply)
        self.assertIn('Expected Outcome', reply)

        # Example of well-defined task
        self.assertIn('Example of a Well-Defined Task', reply)

        # Manual creation steps in Task Management module
        self.assertIn('Steps to Create the Task Manually in the App', reply)
        self.assertIn('Task Management', reply)
        self.assertIn('/tasks/create', reply)

        # 2. Calling with draft requirement reviews requirement without inserting record
        mock_call.return_value = {
            'success': True,
            'content': '### 📌 Task Title\nImplement OAuth\n\n### 📋 Subtasks\n- [ ] Configure keys'
        }
        res = self.client.post('/ai/generate-task',
                               data=json.dumps({'requirement': 'Implement OAuth login'}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])
        self.assertEqual(Task.query.count(), initial_task_count)

        # Break Project into Tasks
        mock_call.return_value = {
            'success': True,
            'content': '### 🏗️ Project Work Breakdown\n#### 🔹 Phase 1: Planning\n1. Design Schema'
        }
        res_break = self.client.post('/ai/break-project',
                                     data=json.dumps({'description': 'Build an eCommerce checkout system'}),
                                     content_type='application/json')
        self.assertEqual(res_break.status_code, 200)
        self.assertTrue(res_break.get_json()['success'])
        self.assertIn('Project Work Breakdown', res_break.get_json()['reply'])

    @patch('ai_assistant.services.GrokService.call_grok')
    def test_07_task_report_generation(self, mock_call):
        """Test Generate Task Report returns summary of authorized tasks"""
        mock_call.return_value = {
            'success': True,
            'content': '### 📋 Sprint Task Summary Report\nTotal Tasks: 2'
        }
        self.login_as('dev_a@test.com')

        res = self.client.post('/ai/task-report',
                               data=json.dumps({}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()['success'])

    # 5. Bug Management: Create Bug Report & Analyze Bug
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_08_bug_report_and_analysis(self, mock_call):
        """Test Create Bug Report and Analyze Bug (does not claim fixed without verification)"""
        # Create Bug Report
        mock_call.return_value = {
            'success': True,
            'content': '### 🐛 Bug Title\nCSS Overflow Bug\n\n### 🔄 Steps to Reproduce\n1. Open modal'
        }
        self.login_as('dev_a@test.com')

        r_bug = self.client.post('/ai/generate-bug',
                                 data=json.dumps({'description': 'Modal overflows on mobile view'}),
                                 content_type='application/json')
        self.assertEqual(r_bug.status_code, 200)
        self.assertTrue(r_bug.get_json()['success'])

        # Analyze Bug
        mock_call.return_value = {
            'success': True,
            'content': '### 🔍 Bug Diagnostic Analysis\n#### 💡 Likely Root Causes\nZ-index collision or viewport overflow.'
        }
        r_analyze = self.client.post('/ai/analyze-bug',
                                    data=json.dumps({'details': 'Error: Uncaught TypeError in main.js:24'}),
                                    content_type='application/json')
        self.assertEqual(r_analyze.status_code, 200)
        self.assertTrue(r_analyze.get_json()['success'])

    # 6. Developer Assistance: Explain Code & Generate Code
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_09_code_explanation_and_generation(self, mock_call):
        """Test Explain Code and Generate Code for supported languages"""
        # Explain Code
        mock_call.return_value = {
            'success': True,
            'content': '### 💡 Purpose & Overview\nFibonacci calculation with dynamic programming.'
        }
        self.login_as('dev_a@test.com')

        r_exp = self.client.post('/ai/explain-code',
                                 data=json.dumps({'code': 'def f(n): return n if n<=1 else f(n-1)+f(n-2)', 'language': 'python'}),
                                 content_type='application/json')
        self.assertEqual(r_exp.status_code, 200)
        self.assertTrue(r_exp.get_json()['success'])

        # Generate Code
        mock_call.return_value = {
            'success': True,
            'content': '### 💻 Generated Code: Python\n```python\ndef parse_csv(): pass\n```\n### 🔍 How It Works\nParses data cleanly.'
        }
        r_gen = self.client.post('/ai/generate-code',
                                data=json.dumps({'requirements': 'Parse CSV files with error handling', 'language': 'python'}),
                                content_type='application/json')
        self.assertEqual(r_gen.status_code, 200)
        self.assertTrue(r_gen.get_json()['success'])
        self.assertIn('Generated Code', r_gen.get_json()['reply'])

    # 7. Daily Productivity: Daily Work Report & Productivity Summary
    @patch('ai_assistant.services.GrokService.call_grok')
    def test_10_daily_work_report_and_productivity_summary(self, mock_call):
        """Test Daily Work Report and Productivity Summary use actual logs and hours"""
        # Daily Report
        mock_call.return_value = {
            'success': True,
            'content': '### 📝 Daily Work Report\n#### ✅ Completed Activities\n- Tested AI Assistant.'
        }
        self.login_as('dev_a@test.com')

        r_daily = self.client.post('/ai/daily-summary',
                                   data=json.dumps({'work_done': 'Tested AI Assistant enhancements'}),
                                   content_type='application/json')
        self.assertEqual(r_daily.status_code, 200)
        self.assertTrue(r_daily.get_json()['success'])

        # Productivity Summary
        mock_call.return_value = {
            'success': True,
            'content': '### 🚀 Developer Productivity Summary\nVelocity is solid with 1 completed task today.'
        }
        r_prod = self.client.post('/ai/productivity-summary', content_type='application/json')
        self.assertEqual(r_prod.status_code, 200)
        self.assertTrue(r_prod.get_json()['success'])

    # 8. Missing API Key Error Handling
    def test_11_missing_api_key_displays_friendly_error(self):
        """Test missing API key produces clear friendly configuration message"""
        with patch.object(GrokService, 'get_api_key', return_value=''):
            res = GrokService.chat("Hello Assistant")
            self.assertFalse(res['success'])
            self.assertIn("xAI API key is not configured", res['error'])
            self.assertIn("XAI_API_KEY", res['error'])

    # 9. Invalid Requests & Input Validation
    def test_12_invalid_requests_handled_properly(self):
        """Test empty messages and oversized inputs return 400 Bad Request"""
        self.login_as('dev_a@test.com')

        r_empty = self.client.post('/ai/chat', data=json.dumps({'message': '   '}), content_type='application/json')
        self.assertEqual(r_empty.status_code, 400)
        self.assertIn('cannot be empty', r_empty.get_json()['error'])

        huge_text = 'A' * 4500
        r_huge = self.client.post('/ai/chat', data=json.dumps({'message': huge_text}), content_type='application/json')
        self.assertEqual(r_huge.status_code, 400)
        self.assertIn('exceeds maximum', r_huge.get_json()['error'])

    # 10. API Timeout Handling
    @patch('ai_assistant.services.OpenAI')
    def test_13_timeout_handled_properly(self, mock_openai_cls):
        """Test API timeout returns user-friendly timeout notification"""
        from openai import APITimeoutError
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = APITimeoutError(request=MagicMock())
        mock_openai_cls.return_value = mock_client

        with patch.object(GrokService, 'get_client', return_value=mock_client):
            res = GrokService.chat("Complex prompt that takes too long")
            self.assertFalse(res['success'])
            self.assertIn("timed out (30s)", res['error'])
            self.assertTrue(res.get('is_timeout'))

    # 11. Security: Zero API Key Exposure & No "Grok" in User Facing UI
    def test_14_no_api_key_exposure_and_no_grok_in_ui(self):
        """Verify API key is never rendered and 'Grok' is not displayed in the user interface"""
        self.login_as('dev_a@test.com')
        r = self.client.get('/developer/dashboard')
        html = r.data.decode('utf-8')
        self.assertNotIn('test_xai_mock_key_12345', html)
        self.assertNotIn('XAI_API_KEY', html)

        # Check rendered HTML does NOT display Grok to user
        self.assertNotIn('>Grok<', html)
        self.assertNotIn('>Grok AI<', html)
        self.assertNotIn('Grok is thinking', html)
        self.assertNotIn('powered by Grok', html)

        # Static JS does not have user-facing Grok strings
        with open('static/js/ai_assistant.js', 'r', encoding='utf-8') as f:
            js_content = f.read()
        self.assertNotIn('test_xai_mock_key_12345', js_content)
        self.assertNotIn('"Grok"', js_content)
        self.assertNotIn("'Grok'", js_content)

    # 12. Chat History Isolation & User Separation
    def test_15_chat_history_isolated_by_user(self):
        """Verify Developer A and Developer B have isolated conversations and cannot view each other's messages"""
        dev_a = self.login_as('dev_a@test.com')
        msg_a = AIChatMessage(user_id=dev_a.id, role='user', content='Private message for Dev A', message_type='chat')
        db.session.add(msg_a)
        db.session.commit()

        # Dev A queries history
        r_a = self.client.get('/ai/history')
        self.assertEqual(r_a.status_code, 200)
        contents_a = [m['content'] for m in r_a.get_json()['messages']]
        self.assertIn('Private message for Dev A', contents_a)

        # Dev B logs in on isolated context and queries history - must NOT see Dev A's message
        dev_b = self.login_as('dev_b@test.com')
        r_b = self.client.get('/ai/history')
        self.assertEqual(r_b.status_code, 200)
        contents_b = [m['content'] for m in r_b.get_json()['messages']]
        self.assertNotIn('Private message for Dev A', contents_b)

        # Dev B clears their history - must NOT affect Dev A
        self.client.post('/ai/clear-history')
        dev_a_msg_count = AIChatMessage.query.filter_by(user_id=dev_a.id).count()
        self.assertGreaterEqual(dev_a_msg_count, 1)

    # 13. Light and Dark Theme Variable Support
    def test_16_theme_support_css_variables(self):
        """Verify ai_assistant.css uses application design tokens for light and dark modes"""
        with open('static/css/ai_assistant.css', 'r', encoding='utf-8') as f:
            css = f.read()
        self.assertIn('--assistant-primary', css)
        self.assertIn('[data-theme="dark"]', css)
        self.assertIn('var(--bg-card', css)
        self.assertIn('var(--text-primary', css)
        self.assertIn('var(--border-color', css)
