import re
from app import create_app
from models import db, User, Task, Project

app = create_app()

def run_verification():
    with app.test_client() as client:
        with app.app_context():
            user52 = User.query.filter_by(email='soppariakshaya@gmail.com').first()
            user57 = User.query.filter_by(email='harika@gmail.com').first()
            admin = User.query.filter_by(email='admin@devproductivity.com').first()
            all_db_tasks = [(t.id, t.title, t.project.name if t.project else 'None', t.assignee.full_name if t.assignee else 'None', t.priority, t.status) for t in Task.query.all()]
            assert len(all_db_tasks) == 4, f"Expected 4 DB tasks, found {len(all_db_tasks)}"

        print("==================================================")
        print("1. Verifying Task Management for Developer (User 52)")
        print("==================================================")
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user52.id)
            sess['_fresh'] = True

        res = client.get('/tasks')
        assert res.status_code == 200
        html = res.data.decode('utf-8')
        
        # Verify all 4 titles appear in the HTML
        for tid, title, pname, aname, priority, status in all_db_tasks:
            assert title in html, f"Task title '{title}' missing on /tasks"
            print(f"  [PASS] Found: '{title}' | Project: {pname} | Assignee: {aname} | Priority: {priority} | Status: {status}")

        # Check total rows
        rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html)
        print(f"Total task rows rendered: {len(rows)}")
        assert len(rows) == 4, f"Expected 4 rows, found {len(rows)}"

        print("\n2. Verifying Filters for Developer")
        # Status Filter: completed (should be 1 task)
        res_comp = client.get('/tasks?status=completed')
        html_comp = res_comp.data.decode('utf-8')
        comp_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html_comp)
        print(f"  Status=completed: found {len(comp_rows)} tasks: {comp_rows}")
        assert len(comp_rows) == 1 and comp_rows[0].strip() == all_db_tasks[0][1]

        # Status Filter: todo (should be 3 tasks)
        res_todo = client.get('/tasks?status=todo')
        html_todo = res_todo.data.decode('utf-8')
        todo_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html_todo)
        print(f"  Status=todo: found {len(todo_rows)} tasks: {todo_rows}")
        assert len(todo_rows) == 3

        # Priority Filter: medium (should be 2 tasks)
        res_med = client.get('/tasks?priority=medium')
        html_med = res_med.data.decode('utf-8')
        med_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html_med)
        print(f"  Priority=medium: found {len(med_rows)} tasks: {med_rows}")
        assert len(med_rows) == 2

        # Project Filter: project_id=1 (should be 4 tasks)
        res_proj = client.get('/tasks?project_id=1')
        html_proj = res_proj.data.decode('utf-8')
        proj_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html_proj)
        print(f"  Project_id=1: found {len(proj_rows)} tasks")
        assert len(proj_rows) == 4

        # Clear filters: /tasks
        res_clear = client.get('/tasks')
        html_clear = res_clear.data.decode('utf-8')
        clear_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', html_clear)
        print(f"  Cleared filters: found {len(clear_rows)} tasks")
        assert len(clear_rows) == 4

        print("\n3. Verifying Developer Dashboard")
        res_dash = client.get('/developer/dashboard')
        assert res_dash.status_code == 200
        html_dash = res_dash.data.decode('utf-8')
        dash_tasks = re.findall(r'<span class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</span>\s*<div class="text-muted"', html_dash)
        print(f"  Developer Dashboard tasks listed: {len(dash_tasks)}")
        assert len(dash_tasks) == 4, f"Expected 4 dashboard tasks, got {len(dash_tasks)}"

        print("\n4. Verifying Team Leader (User 57, Harika)")
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user57.id)
            sess['_fresh'] = True

        res_tl_tasks = client.get('/tasks')
        assert res_tl_tasks.status_code == 200
        tl_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', res_tl_tasks.data.decode('utf-8'))
        print(f"  Team Leader sees {len(tl_rows)} tasks on /tasks")
        assert len(tl_rows) == 4

        res_tl_dash = client.get('/team-leader/dashboard')
        assert res_tl_dash.status_code == 200
        print("  Team Leader Dashboard loaded successfully (200 OK)")

        print("\n5. Verifying Admin (User 1)")
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh'] = True

        res_admin_tasks = client.get('/tasks')
        assert res_admin_tasks.status_code == 200
        admin_rows = re.findall(r'<a href="/tasks/\d+"[^>]*class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</a>', res_admin_tasks.data.decode('utf-8'))
        print(f"  Admin sees {len(admin_rows)} tasks on /tasks")
        assert len(admin_rows) == 4

        print("\n==================================================")
        print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY! (4 OF 4)")
        print("==================================================")

if __name__ == '__main__':
    run_verification()
