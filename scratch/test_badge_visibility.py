import re
from app import create_app
from models import db, User, WorkLog

app = create_app()

def run_tests():
    with app.test_client() as client:
        # Test 1: Developer Login & Pages
        print("=== 1. Testing Developer Pages ===")
        # Get CSRF token
        login_page = client.get('/login').data.decode('utf-8')
        csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
        csrf_token = csrf_match.group(1) if csrf_match else ''
        
        login_res = client.post('/login', data={
            'email': 'dev@devproductivity.com',
            'password': 'Dev@12345',
            'csrf_token': csrf_token
        }, follow_redirects=True)
        # Submit a test work log for dev if none exists
        with app.app_context():
            dev_user = User.query.filter_by(email='dev@devproductivity.com').first()
            if not WorkLog.query.filter_by(user_id=dev_user.id).first():
                w = WorkLog(user_id=dev_user.id, work_performed="Fixed bug reports and updated navigation styles", hours_worked=7.5)
                db.session.add(w)
                db.session.commit()
                print("Created test work log with 7.5 hrs for dev")

        dev_urls = [
            ('/developer/dashboard', 'Developer Dashboard'),
            ('/developer/work-logs', 'Developer Work Logs'),
            ('/developer/timer', 'Developer Time Tracker'),
            ('/projects', 'Projects List'),
            ('/tasks', 'Tasks List'),
            ('/issues', 'Issues / Bug Reports'),
            ('/snippets', 'Code Snippets'),
        ]

        badge_regex = re.compile(r'<span[^>]*class="[^"]*badge[^"]*"[^>]*>(.*?)</span>', re.DOTALL | re.IGNORECASE)

        for url, name in dev_urls:
            res = client.get(url)
            assert res.status_code == 200, f"Failed to get {url}: {res.status_code}"
            html = res.data.decode('utf-8')
            matches = badge_regex.findall(html)
            clean_badges = [re.sub(r'<[^>]+>', '', m).strip() for m in matches]
            # filter out non-empty
            non_empty = [b for b in clean_badges if b]
            print(f"[{name}] ({url}) Found {len(matches)} badges, {len(non_empty)} with non-empty text.")
            
            # Special check for work logs
            if 'work-logs' in url:
                hours_badges = [b for b in clean_badges if 'hrs' in b]
                print(f"  -> Work log hours badges found: {hours_badges}")
                assert len(hours_badges) > 0, "No hours badge found in Work Logs!"

        # Logout
        client.get('/logout')

        # Test 2: Team Leader Login & Pages
        print("\n=== 2. Testing Team Leader Pages ===")
        login_page = client.get('/login').data.decode('utf-8')
        csrf_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', login_page)
        csrf_token = csrf_match.group(1) if csrf_match else ''
        
        login_res = client.post('/login', data={
            'email': 'leader@devproductivity.com',
            'password': 'Leader@12345',
            'csrf_token': csrf_token
        }, follow_redirects=True)
        assert login_res.status_code == 200, f"TL Login failed: {login_res.status_code}"
        print("Logged in as leader@devproductivity.com")

        tl_urls = [
            ('/team-leader/dashboard', 'Team Leader Dashboard'),
            ('/team-leader/reviews', 'Team Leader Daily Standup Reviews'),
            ('/team-leader/members', 'Team Leader Members Roster'),
            ('/projects', 'Projects List (TL)'),
            ('/tasks', 'Tasks List (TL)'),
            ('/issues', 'Issues List (TL)'),
        ]

        for url, name in tl_urls:
            res = client.get(url)
            assert res.status_code == 200, f"Failed to get {url}: {res.status_code}"
            html = res.data.decode('utf-8')
            matches = badge_regex.findall(html)
            clean_badges = [re.sub(r'<[^>]+>', '', m).strip() for m in matches]
            non_empty = [b for b in clean_badges if b]
            print(f"[{name}] ({url}) Found {len(matches)} badges, {len(non_empty)} with non-empty text.")
            if 'reviews' in url:
                hours_badges = [b for b in clean_badges if 'hrs' in b]
                print(f"  -> Standup review hours badges found: {hours_badges}")
                assert len(hours_badges) > 0, "No hours badge found in Reviews!"

    print("\nALL BADGE TESTS PASSED SUCCESSFULLY!")

if __name__ == '__main__':
    run_tests()
