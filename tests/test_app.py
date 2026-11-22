import os
import unittest
import json
import tempfile
from app import create_app
from config import Config
from extensions import db
from models import User, Project, Task, CodeSnippet, WorkLog

class DeveloperProductivityToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.test_db_fd, cls.test_db_path = tempfile.mkstemp(suffix='.db')
        os.close(cls.test_db_fd)
        norm_test_path = cls.test_db_path.replace('\\', '/')

        class TestConfig(Config):
            TESTING = True
            WTF_CSRF_ENABLED = False
            SQLALCHEMY_DATABASE_URI = f'sqlite:///{norm_test_path}'

        cls.app = create_app(TestConfig)
        with cls.app.app_context():
            db.create_all()
            # Seed clean test users
            admin = User(email='admin@testdomain.com', full_name='System Admin', role='admin', is_active=True)
            admin.set_password('Admin@12345')
            leader = User(email='leader@testdomain.com', full_name='Sprint Leader', role='team_leader', is_active=True)
            leader.set_password('Leader@12345')
            dev = User(email='dev@testdomain.com', full_name='Senior Developer', role='developer', is_active=True)
            dev.set_password('Dev@12345')
            db.session.add_all([admin, leader, dev])
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
        self.ctx.pop()

    def test_01_public_routes_and_ui_elements(self):
        """Test public login, register, forgot-password pages render properly with required UI specs"""
        r_login = self.client.get('/login')
        self.assertEqual(r_login.status_code, 200)
        login_html = r_login.data.decode('utf-8')
        
        # Split-screen structure
        self.assertIn('auth-split-left', login_html)
        self.assertIn('auth-split-right', login_html)
        
        # Application info and features
        self.assertIn('Developer Productivity Tool', login_html)
        self.assertIn('Your Development Workflow', login_html)
        self.assertIn('Project & Task Management', login_html)
        self.assertIn('Code Snippet Manager', login_html)
        self.assertIn('Built for developers. Designed for productivity.', login_html)
        
        # Requirement: Remove dark/light theme toggle from login page
        self.assertNotIn('theme-toggle-btn', login_html)
        
        # Requirement: Remove code/configuration preview box from left section
        self.assertNotIn('auth-code-terminal', login_html)
        self.assertNotIn('workspace.config.py', login_html)
        
        # Requirement: Form fields are empty without demo credentials
        self.assertIn('id="email"', login_html)
        self.assertIn('id="password"', login_html)
        self.assertNotIn('value="admin@devproductivity.com"', login_html)
        self.assertNotIn('value="password123"', login_html)
        
        # Requirement: Eye icon for password visibility
        self.assertIn('id="toggle-password-btn"', login_html)
        
        # Requirement: Button labels Continue with Google / GitHub
        self.assertIn('Continue with Google', login_html)
        self.assertIn('Continue with GitHub', login_html)

        # Register page check
        r_reg = self.client.get('/register')
        self.assertEqual(r_reg.status_code, 200)
        reg_html = r_reg.data.decode('utf-8')
        self.assertIn('Create an Account', reg_html)
        self.assertIn('Account Role', reg_html)
        self.assertNotIn('theme-toggle-btn', reg_html)
        self.assertIn('id="toggle-password-btn"', reg_html)
        self.assertIn('id="toggle-confirm-password-btn"', reg_html)
        # Roles developer and team_leader allowed, admin disallowed
        self.assertIn('value="developer"', reg_html)
        self.assertIn('value="team_leader"', reg_html)
        self.assertNotIn('value="admin"', reg_html)
        self.assertIn('Admin registration is restricted', reg_html)

        r_forgot = self.client.get('/forgot-password')
        self.assertEqual(r_forgot.status_code, 200)
        self.assertIn(b'Reset Password', r_forgot.data)

    def test_02_new_developer_registration_and_redirect(self):
        """Test developer registration creates SQLite record and redirects to developer dashboard"""
        import time
        uid = f"mock_dev_{int(time.time() * 1000)}"
        payload = {
            'idToken': uid,
            'fullName': f'Test Developer {uid}',
            'role': 'developer',
            'rememberMe': True
        }
        res = self.client.post('/auth/verify-token',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['role'], 'developer')
        self.assertIn('/developer/dashboard', data['redirect'])

        # Verify saved in SQLite
        user = User.query.filter_by(firebase_uid=uid).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'developer')

    def test_03_new_team_leader_registration_and_redirect(self):
        """Test team leader registration creates SQLite record and redirects to team leader dashboard"""
        import time
        uid = f"mock_tl_{int(time.time() * 1000)}"
        payload = {
            'idToken': uid,
            'fullName': f'Test Team Leader {uid}',
            'role': 'team_leader',
            'rememberMe': True
        }
        res = self.client.post('/auth/verify-token',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['role'], 'team_leader')
        self.assertIn('/team-leader/dashboard', data['redirect'])

        # Verify saved in SQLite
        user = User.query.filter_by(firebase_uid=uid).first()
        self.assertIsNotNone(user)
        self.assertEqual(user.role, 'team_leader')

    def test_04_admin_self_registration_forbidden(self):
        """Test users cannot self-register as Admin"""
        payload = {
            'idToken': 'mock_hack_token_789',
            'fullName': 'Hacker Wannabe',
            'role': 'admin',
            'rememberMe': True
        }
        res = self.client.post('/auth/verify-token',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data.get('status'), 'onboarding_required')

    def test_05_subsequent_login_preserves_role_and_session(self):
        """Test user registration followed by subsequent login retrieves saved role and does not overwrite"""
        import time
        uid = f"mock_user_subsequent_{int(time.time() * 1000)}"
        
        reg_payload = {
            'idToken': uid,
            'fullName': 'Subsequent Test TL',
            'role': 'team_leader',
            'rememberMe': True
        }
        reg_res = self.client.post('/auth/verify-token',
                                   data=json.dumps(reg_payload),
                                   content_type='application/json')
        self.assertEqual(reg_res.status_code, 200)
        reg_data = reg_res.get_json()
        self.assertEqual(reg_data['role'], 'team_leader')

        login_payload = {
            'idToken': uid,
            'rememberMe': True
        }
        login_res = self.client.post('/auth/verify-token',
                                     data=json.dumps(login_payload),
                                     content_type='application/json')
        self.assertEqual(login_res.status_code, 200)
        login_data = login_res.get_json()
        self.assertEqual(login_data['status'], 'success')
        self.assertEqual(login_data['role'], 'team_leader')

        u = User.query.filter_by(firebase_uid=uid).first()
        self.assertEqual(u.role, 'team_leader')

    def test_06_unauthorized_dashboard_access_blocked(self):
        """Test developers cannot access Admin dashboard"""
        dev = User.query.filter_by(role='developer').first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(dev.id)
            sess['_fresh'] = True

        res = self.client.get('/admin/dashboard', follow_redirects=False)
        self.assertIn(res.status_code, [302, 403])
        if res.status_code == 302:
            self.assertIn('/developer/dashboard', res.headers['Location'])

    def test_07_admin_access_allowed(self):
        """Test Admin can access Admin Dashboard"""
        admin = User.query.filter_by(role='admin').first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        res = self.client.get('/admin/dashboard')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Admin Dashboard', res.data)

    def test_08_first_time_oauth_onboarding_flow(self):
        """Test OAuth sign in without existing user routes to onboarding"""
        import time
        uniq_id = f"mock_oauth_{int(time.time() * 1000)}"
        payload = {
            'idToken': uniq_id,
            'rememberMe': True
        }
        res = self.client.post('/auth/verify-token',
                               data=json.dumps(payload),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'onboarding_required')
        self.assertIn('/auth/onboarding', data['redirect'])

        onboard_payload = {
            'fullName': 'New OAuth Engineer',
            'role': 'developer'
        }
        onboard_res = self.client.post('/auth/complete-onboarding',
                                       data=json.dumps(onboard_payload),
                                       content_type='application/json')
        self.assertEqual(onboard_res.status_code, 200)
        data2 = onboard_res.get_json()
        self.assertEqual(data2['status'], 'success')
        self.assertEqual(data2['role'], 'developer')
        self.assertIn('/developer/dashboard', data2['redirect'])

    def test_09_project_crud(self):
        """Test project creation and retrieval"""
        admin = User.query.filter_by(role='admin').first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        res = self.client.post('/projects/create', data={
            'name': 'Isolated Test Project',
            'description': 'Integration testing project in isolated DB',
            'priority': 'high',
            'status': 'active'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Isolated Test Project', res.data)

    def test_10_task_crud(self):
        """Test task creation and retrieval"""
        dev = User.query.filter_by(role='developer').first()
        proj = Project.query.first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(dev.id)
            sess['_fresh'] = True

        res = self.client.post('/tasks/create', data={
            'title': 'Isolated Test Task Item',
            'project_id': proj.id,
            'priority': 'critical',
            'status': 'todo'
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Isolated Test Task Item', res.data)

    def test_11_logout_post(self):
        """Test POST logout clears session, flashes message, sets anti-cache headers, and redirects to login"""
        dev = User.query.filter_by(role='developer').first()
        with self.client.session_transaction() as sess:
            sess['_user_id'] = str(dev.id)
            sess['_fresh'] = True

        res = self.client.post('/logout', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers['Location'])
        # Verify anti-cache headers
        self.assertIn('no-store', res.headers.get('Cache-Control', ''))
        self.assertIn('no-cache', res.headers.get('Cache-Control', ''))

        # Follow redirect and verify success message
        r_after = self.client.get(res.headers['Location'])
        self.assertEqual(r_after.status_code, 200)
        self.assertIn(b'successfully logged out', r_after.data)

    def test_12_native_email_password_login(self):
        """Test native Flask & SQLite email/password login and wrong credential rejection"""
        # 1. Test wrong credentials first
        res_fail = self.client.post('/login', data={
            'email': 'admin@testdomain.com',
            'password': 'WrongPassword999'
        }, follow_redirects=True)
        self.assertEqual(res_fail.status_code, 200)
        self.assertIn(b'Invalid email address or password', res_fail.data)

        # 2. Test correct credentials
        res_ok = self.client.post('/login', data={
            'email': 'admin@testdomain.com',
            'password': 'Admin@12345'
        }, follow_redirects=False)
        self.assertEqual(res_ok.status_code, 302)
        self.assertIn('/admin/dashboard', res_ok.headers['Location'])

        # 3. Clean up session via logout
        self.client.post('/logout')

    def test_13_native_registration_flow(self):
        """Test native Flask & SQLite registration with validation and password confirmation"""
        # Mismatched password
        res_mismatch = self.client.post('/register', data={
            'full_name': 'New Dev',
            'email': 'newdev@testdomain.com',
            'role': 'developer',
            'password': 'Password@123',
            'confirm_password': 'DifferentPassword@123'
        }, follow_redirects=True)
        self.assertIn(b'Passwords do not match', res_mismatch.data)

        # Successful registration
        res_ok = self.client.post('/register', data={
            'full_name': 'New Dev',
            'email': 'newdev@testdomain.com',
            'role': 'developer',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        }, follow_redirects=False)
        self.assertEqual(res_ok.status_code, 302)
        self.assertIn('/developer/dashboard', res_ok.headers['Location'])

        # Log out so we can attempt registering the duplicate email
        self.client.post('/logout')

        # Duplicate email check
        res_dup = self.client.post('/register', data={
            'full_name': 'Duplicate User',
            'email': 'newdev@testdomain.com',
            'role': 'developer',
            'password': 'Password@123',
            'confirm_password': 'Password@123'
        }, follow_redirects=True)
        self.assertIn(b'already exists', res_dup.data)

    def test_14_google_login_existing_user_preserves_role(self):
        """Test Google login preserves existing role in SQLite and routes to appropriate dashboard"""
        leader = User.query.filter_by(role='team_leader').first()
        leader.firebase_uid = 'mock_google_tl_uid'
        db.session.commit()

        res = self.client.post('/auth/verify-token',
                               data=json.dumps({'idToken': 'mock_google_tl_uid'}),
                               content_type='application/json')
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data['status'], 'success')
        self.assertEqual(data['role'], 'team_leader')
        self.assertIn('/team-leader/dashboard', data['redirect'])

        # Verify role was not changed in DB
        u = User.query.filter_by(firebase_uid='mock_google_tl_uid').first()
        self.assertEqual(u.role, 'team_leader')

    def test_15_google_login_invalid_token(self):
        """Test missing or invalid Google ID token returns 400/401 error message"""
        res_empty = self.client.post('/auth/verify-token',
                                     data=json.dumps({'idToken': ''}),
                                     content_type='application/json')
        self.assertEqual(res_empty.status_code, 400)
        self.assertIn('Missing Firebase ID token', res_empty.get_json()['message'])

    def test_16_github_oauth_missing_config_warning(self):
        """Test GitHub login without configured client_id/secret shows informative warning"""
        orig_id = self.app.config.get('GITHUB_CLIENT_ID')
        self.app.config['GITHUB_CLIENT_ID'] = ''
        try:
            res = self.client.get('/auth/github/login', follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn(b'GitHub OAuth is not configured', res.data)
        finally:
            self.app.config['GITHUB_CLIENT_ID'] = orig_id

    def test_17_github_oauth_redirect_and_state(self):
        """Test GitHub login redirects to GitHub authorization with state parameter"""
        self.app.config['GITHUB_CLIENT_ID'] = 'test_gh_client_id'
        self.app.config['GITHUB_CLIENT_SECRET'] = 'test_gh_secret'
        res = self.client.get('/auth/github/login', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        loc = res.headers.get('Location', '')
        self.assertIn('github.com/login/oauth/authorize', loc)
        self.assertIn('client_id=test_gh_client_id', loc)
        self.assertIn('state=', loc)

    def test_18_github_oauth_cancelled_callback(self):
        """Test user cancelling GitHub login displays clean warning and returns to login"""
        res = self.client.get('/auth/github/callback?error=access_denied&error_description=The+user+has+denied+your+application+access.', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'GitHub sign-in was cancelled', res.data)

    def test_19_github_oauth_invalid_state_rejected(self):
        """Test invalid or mismatched OAuth state token is rejected"""
        res = self.client.get('/auth/github/callback?code=fakecode&state=invalid_state', follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Invalid OAuth state', res.data)

    def test_20_github_oauth_successful_flow(self):
        """Test successful GitHub OAuth creates user, links connection, preserves role, and logs in"""
        from unittest.mock import patch

        self.app.config['GITHUB_CLIENT_ID'] = 'test_id'
        self.app.config['GITHUB_CLIENT_SECRET'] = 'test_secret'

        with self.client.session_transaction() as sess:
            sess['github_oauth_state'] = 'valid_state_123'
            sess['oauth_register_role'] = 'developer'

        mock_token_res = unittest.mock.MagicMock()
        mock_token_res.json.return_value = {'access_token': 'gh_test_token_abc'}

        mock_profile_res = unittest.mock.MagicMock()
        mock_profile_res.status_code = 200
        mock_profile_res.json.return_value = {
            'login': 'octocat_dev',
            'name': 'Octo Developer',
            'email': 'octocat@testdomain.com',
            'avatar_url': 'https://github.com/images/error/octocat_happy.gif'
        }

        with patch('requests.post', return_value=mock_token_res), \
             patch('requests.get', return_value=mock_profile_res):
            res = self.client.get('/auth/github/callback?code=mock_code_123&state=valid_state_123', follow_redirects=False)
            self.assertEqual(res.status_code, 302)
            self.assertIn('/developer/dashboard', res.headers.get('Location', ''))

            # Verify user exists in SQLite with role developer
            u = User.query.filter_by(email='octocat@testdomain.com').first()
            self.assertIsNotNone(u)
            self.assertEqual(u.role, 'developer')
            self.assertIsNotNone(u.github_connection)
            self.assertEqual(u.github_connection.github_username, 'octocat_dev')

    def test_21_logout_for_all_roles(self):
        """Test logout for Admin, Team Leader, and Developer accounts clears session and blocks back navigation"""
        test_accounts = [
            ('admin@testdomain.com', 'Admin@12345', '/admin/dashboard'),
            ('leader@testdomain.com', 'Leader@12345', '/team-leader/dashboard'),
            ('dev@testdomain.com', 'Dev@12345', '/developer/dashboard')
        ]

        for email, pwd, dash_url in test_accounts:
            client = self.app.test_client()

            # Sign in
            r_login = client.post('/login', data={'email': email, 'password': pwd}, follow_redirects=False)
            self.assertEqual(r_login.status_code, 302)

            # Confirm dashboard accessible
            r_dash = client.get(dash_url)
            self.assertEqual(r_dash.status_code, 200)

            # Logout via POST
            r_logout = client.post('/logout', follow_redirects=False)
            self.assertEqual(r_logout.status_code, 302)
            self.assertIn('/login', r_logout.headers.get('Location', ''))
            self.assertIn('no-store', r_logout.headers.get('Cache-Control', ''))

            # Verify login page has success message
            r_after = client.get(r_logout.headers.get('Location'))
            self.assertEqual(r_after.status_code, 200)
            self.assertIn(b'successfully logged out', r_after.data)

            # Re-accessing protected dashboard must fail and redirect to login
            r_reaccess = client.get(dash_url, follow_redirects=False)
            self.assertIn(r_reaccess.status_code, [302, 401])
            self.assertIn('/login', r_reaccess.headers.get('Location', ''))

    def test_22_admin_dashboard_access_and_role_normalization(self):
        """Test admin can directly access /admin/dashboard without getting redirected to developer dashboard"""
        client = self.app.test_client()
        # Sign in as admin
        client.post('/login', data={'email': 'admin@testdomain.com', 'password': 'Admin@12345'})
        r_admin = client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(r_admin.status_code, 200)
        self.assertIn(b'Admin Dashboard', r_admin.data)
        client.post('/logout')

        # Developer trying to access admin dashboard is redirected to developer dashboard
        client.post('/login', data={'email': 'dev@testdomain.com', 'password': 'Dev@12345'})
        r_dev_try_admin = client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(r_dev_try_admin.status_code, 302)
        self.assertIn('/developer/dashboard', r_dev_try_admin.headers.get('Location', ''))
        client.post('/logout')

    def test_23_setup_admin_route_and_guard(self):
        """Test /setup-admin is guarded when an admin already exists in the database"""
        client = self.app.test_client()
        # Since an admin already exists (seeded in setUpClass), /setup-admin redirects to login
        res = client.get('/setup-admin', follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/login', res.headers.get('Location', ''))

    def test_24_profile_view_and_update(self):
        """Test profile page viewing, updating personal details (including phone number), and immutable role"""
        client = self.app.test_client()
        client.post('/login', data={'email': 'dev@testdomain.com', 'password': 'Dev@12345'})

        # Profile GET
        r_prof = client.get('/profile')
        self.assertEqual(r_prof.status_code, 200)
        self.assertIn(b'Account Profile', r_prof.data)
        self.assertIn(b'Personal & Contact Information', r_prof.data)

        # Profile POST update
        r_edit = client.post('/profile/edit', data={
            'full_name': 'Senior Developer Pro',
            'email': 'dev@testdomain.com',
            'phone_number': '+1-800-555-0199',
            'department': 'Platform Infrastructure',
            'bio': 'Passionate about distributed systems.'
        }, follow_redirects=True)
        self.assertEqual(r_edit.status_code, 200)
        self.assertIn(b'profile has been updated successfully', r_edit.data)

        # Verify database record updated
        u = User.query.filter_by(email='dev@testdomain.com').first()
        self.assertEqual(u.full_name, 'Senior Developer Pro')
        self.assertEqual(u.phone_number, '+1-800-555-0199')
        self.assertEqual(u.department, 'Platform Infrastructure')
        self.assertEqual(u.role, 'developer')  # Role untouched!

    def test_25_profile_photo_upload_and_removal(self):
        """Test uploading profile picture and subsequent removal"""
        import io
        client = self.app.test_client()
        client.post('/login', data={'email': 'dev@testdomain.com', 'password': 'Dev@12345'})

        # Upload dummy PNG
        fake_png = io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4')
        r_upload = client.post('/profile/photo', data={
            'photo': (fake_png, 'avatar.png')
        }, content_type='multipart/form-data', follow_redirects=True)
        self.assertEqual(r_upload.status_code, 200)
        self.assertIn(b'Profile photo updated successfully', r_upload.data)

        u = User.query.filter_by(email='dev@testdomain.com').first()
        self.assertTrue(u.photo_url.startswith('/uploads/profile/'))

        # Remove photo
        r_remove = client.post('/profile/remove-photo', follow_redirects=True)
        self.assertEqual(r_remove.status_code, 200)
        self.assertIn(b'Profile photo removed', r_remove.data)

        db.session.refresh(u)
        self.assertIsNone(u.photo_url)

    def test_26_email_password_registration_with_null_firebase_uid(self):
        """Test registering a new Developer via email/password saves firebase_uid as NULL and allows login/logout"""
        client = self.app.test_client()
        # Register new developer via POST /register
        res = client.post('/register', data={
            'full_name': 'Email Dev User',
            'email': 'emaildev@testdomain.com',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'role': 'developer'
        }, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/developer/dashboard', res.headers.get('Location', ''))

        # Verify saved in SQLite database with firebase_uid is NULL
        new_u = User.query.filter_by(email='emaildev@testdomain.com').first()
        self.assertIsNotNone(new_u)
        self.assertIsNone(new_u.firebase_uid)
        self.assertEqual(new_u.role, 'developer')
        self.assertTrue(new_u.check_password('Password@123'))

        # Verify login with the new account works
        client.post('/logout')
        res_login = client.post('/login', data={
            'email': 'emaildev@testdomain.com',
            'password': 'Password@123'
        }, follow_redirects=False)
        self.assertEqual(res_login.status_code, 302)
        self.assertIn('/developer/dashboard', res_login.headers.get('Location', ''))

        # Verify logout works
        res_logout = client.post('/logout', follow_redirects=False)
        self.assertEqual(res_logout.status_code, 302)
        self.assertIn('/login', res_logout.headers.get('Location', ''))

    def test_27_public_registration_team_leader_and_admin_security(self):
        """Test public registration allows Team Leader with correct DB storage/redirect, but strictly blocks Admin"""
        client = self.app.test_client()

        # 1. Register as Team Leader publicly
        res_tl = client.post('/register', data={
            'full_name': 'Team Lead Public',
            'email': 'tl_public@testdomain.com',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'role': 'team_leader'
        }, follow_redirects=False)
        self.assertEqual(res_tl.status_code, 302)
        self.assertIn('/team-leader/dashboard', res_tl.headers.get('Location', ''))

        # Confirm account created with role 'team_leader' in SQLite
        u_tl = User.query.filter_by(email='tl_public@testdomain.com').first()
        self.assertIsNotNone(u_tl)
        self.assertEqual(u_tl.role, 'team_leader')
        client.post('/logout')

        # Log in with the newly registered Team Leader -> must redirect to /team-leader/dashboard
        res_tl_login = client.post('/login', data={
            'email': 'tl_public@testdomain.com',
            'password': 'Password@123'
        }, follow_redirects=False)
        self.assertEqual(res_tl_login.status_code, 302)
        self.assertIn('/team-leader/dashboard', res_tl_login.headers.get('Location', ''))
        client.post('/logout')

        # 2. Attempt public registration as Admin -> must be rejected
        res_admin = client.post('/register', data={
            'full_name': 'Sneaky Admin',
            'email': 'sneaky_admin@testdomain.com',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'role': 'admin'
        }, follow_redirects=True)
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b'Admin registration is restricted', res_admin.data)
        self.assertIsNone(User.query.filter_by(email='sneaky_admin@testdomain.com').first())

        # 3. Attempt arbitrary/invalid role -> must be rejected
        res_invalid = client.post('/register', data={
            'full_name': 'Hacker Wannabe',
            'email': 'hacker@testdomain.com',
            'password': 'Password@123',
            'confirm_password': 'Password@123',
            'role': 'superuser'
        }, follow_redirects=True)
        self.assertEqual(res_invalid.status_code, 200)
        self.assertIn(b'Invalid role selected', res_invalid.data)
        self.assertIsNone(User.query.filter_by(email='hacker@testdomain.com').first())

    def test_28_admin_create_team_leader_and_login_redirect(self):
        """Test Admin can provision Team Leader, duplicate email is rejected, non-admins are blocked, and TL redirects to TL dashboard"""
        client = self.app.test_client()

        # 1. Non-admin (developer) attempt to access create-team-leader must be blocked
        client.post('/login', data={'email': 'dev@testdomain.com', 'password': 'Dev@12345'})
        res_dev_block = client.get('/admin/create-team-leader', follow_redirects=False)
        self.assertEqual(res_dev_block.status_code, 302)
        self.assertIn('/developer/dashboard', res_dev_block.headers.get('Location', ''))

        # Developer trying to POST must also be blocked
        res_dev_post_block = client.post('/admin/create-team-leader', data={
            'full_name': 'Hacked TL',
            'email': 'hacked_tl@testdomain.com',
            'password': 'Password@123',
            'department': 'Hacking'
        }, follow_redirects=False)
        self.assertEqual(res_dev_post_block.status_code, 302)
        self.assertIn('/developer/dashboard', res_dev_post_block.headers.get('Location', ''))
        self.assertIsNone(User.query.filter_by(email='hacked_tl@testdomain.com').first())
        client.post('/logout')

        # 2. Admin creates a new Team Leader
        client.post('/login', data={'email': 'admin@testdomain.com', 'password': 'Admin@12345'})
        res_create = client.post('/admin/create-team-leader', data={
            'full_name': 'Marcus Vance',
            'email': 'marcus_tl@testdomain.com',
            'password': 'LeaderPassword@123',
            'department': 'Backend & Distributed Systems'
        }, follow_redirects=True)
        self.assertEqual(res_create.status_code, 200)
        self.assertIn(b'created successfully', res_create.data)

        # Verify created in SQLite database with team_leader role and Werkzeug hash
        new_tl = User.query.filter_by(email='marcus_tl@testdomain.com').first()
        self.assertIsNotNone(new_tl)
        self.assertEqual(new_tl.role, 'team_leader')
        self.assertEqual(new_tl.department, 'Backend & Distributed Systems')
        self.assertTrue(new_tl.check_password('LeaderPassword@123'))
        self.assertIsNone(new_tl.firebase_uid)

        # 3. Duplicate email check
        res_dup = client.post('/admin/create-team-leader', data={
            'full_name': 'Duplicate Person',
            'email': 'marcus_tl@testdomain.com',
            'password': 'AnotherPassword@123',
            'department': 'Engineering'
        }, follow_redirects=True)
        self.assertEqual(res_dup.status_code, 200)
        self.assertIn(b'already exists', res_dup.data)
        client.post('/logout')

        # 4. New Team Leader logs in via standard login page
        res_login = client.post('/login', data={
            'email': 'marcus_tl@testdomain.com',
            'password': 'LeaderPassword@123'
        }, follow_redirects=False)

        # Must automatically redirect to Team Leader Dashboard
        self.assertEqual(res_login.status_code, 302)
        self.assertIn('/team-leader/dashboard', res_login.headers.get('Location', ''))

        # Verify dashboard page loads for the new Team Leader
        res_dash = client.get(res_login.headers.get('Location'))
        self.assertEqual(res_dash.status_code, 200)
        self.assertIn(b'Leader Dashboard', res_dash.data)
        client.post('/logout')

    def test_29_cross_role_dashboard_protection_and_redirection(self):
        """Test strict role-based dashboard redirection and access controls preventing cross-role URL tampering"""
        client = self.app.test_client()

        # 1. Developer cannot access Admin or Team Leader dashboards
        client.post('/login', data={'email': 'dev@testdomain.com', 'password': 'Dev@12345'})
        r_dev_to_admin = client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(r_dev_to_admin.status_code, 302)
        self.assertIn('/developer/dashboard', r_dev_to_admin.headers.get('Location', ''))

        r_dev_to_tl = client.get('/team-leader/dashboard', follow_redirects=False)
        self.assertEqual(r_dev_to_tl.status_code, 302)
        self.assertIn('/developer/dashboard', r_dev_to_tl.headers.get('Location', ''))

        r_dev_own = client.get('/developer/dashboard')
        self.assertEqual(r_dev_own.status_code, 200)
        client.post('/logout')

        # 2. Team Leader cannot access Admin dashboard, but can access Team Leader dashboard
        client.post('/login', data={'email': 'tl_public@testdomain.com', 'password': 'Password@123'})
        r_tl_to_admin = client.get('/admin/dashboard', follow_redirects=False)
        self.assertEqual(r_tl_to_admin.status_code, 302)
        self.assertIn('/team-leader/dashboard', r_tl_to_admin.headers.get('Location', ''))

        r_tl_own = client.get('/team-leader/dashboard')
        self.assertEqual(r_tl_own.status_code, 200)
        client.post('/logout')

        # 3. Admin can access Admin dashboard
        client.post('/login', data={'email': 'admin@testdomain.com', 'password': 'Admin@12345'})
        r_admin_own = client.get('/admin/dashboard')
        self.assertEqual(r_admin_own.status_code, 200)
        self.assertIn(b'Admin Dashboard', r_admin_own.data)
        client.post('/logout')

if __name__ == '__main__':
    unittest.main()
