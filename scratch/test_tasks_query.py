from app import create_app
from models import User, Task, Project

app = create_app()

def test_current_behavior():
    with app.test_client() as client:
        # Check as Developer User 52 (soppariakshaya@gmail.com)
        user52 = None
        with app.app_context():
            user52 = User.query.filter_by(email='soppariakshaya@gmail.com').first()
            user57 = User.query.filter_by(email='harika@gmail.com').first()
            admin = User.query.filter_by(email='admin@devproductivity.com').first()

        print("Testing with User 52 (soppariakshaya@gmail.com, role=developer):")
        # Simulating login session for user 52
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user52.id)
            sess['_fresh'] = True

        res = client.get('/tasks')
        html = res.data.decode('utf-8')
        import re
        task_rows = re.findall(r'<a href="/tasks/\d+"[^>]*>(.*?)</a>', html)
        # Filter only titles from table
        print(f"User 52 sees {len(task_rows)} tasks on /tasks:")
        for t in task_rows:
            print("  -", t.strip())

        res_dash = client.get('/developer/dashboard')
        html_dash = res_dash.data.decode('utf-8')
        dash_tasks = re.findall(r'<span class="fw-semibold[^"]*"[^>]*>\s*(.*?)\s*</span>\s*<div class="text-muted"', html_dash)
        print(f"User 52 sees {len(dash_tasks)} tasks on /developer/dashboard:")
        for t in dash_tasks:
            print("  -", t.strip())

        # Testing with User 57 (harika@gmail.com, role=team_leader)
        print("\nTesting with User 57 (harika@gmail.com, role=team_leader):")
        with client.session_transaction() as sess:
            sess['_user_id'] = str(user57.id)
            sess['_fresh'] = True

        res_tl = client.get('/tasks')
        html_tl = res_tl.data.decode('utf-8')
        tl_tasks = re.findall(r'<a href="/tasks/\d+"[^>]*>(.*?)</a>', html_tl)
        print(f"User 57 sees {len(tl_tasks)} tasks on /tasks:")
        for t in tl_tasks:
            print("  -", t.strip())

        res_tl_dash = client.get('/team-leader/dashboard')
        print(f"TL Dashboard status: {res_tl_dash.status_code}")

if __name__ == '__main__':
    test_current_behavior()
