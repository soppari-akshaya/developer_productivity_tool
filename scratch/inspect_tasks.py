from app import create_app
from models import Task, User

app = create_app()
with app.app_context():
    for t in Task.query.all():
        creator = User.query.get(t.created_by_id)
        assignee = User.query.get(t.assigned_to_id)
        print(f"Task {t.id}: '{t.title}' | Created by: {t.created_by_id} ({creator.email if creator else None}) | Assigned to: {t.assigned_to_id} ({assignee.email if assignee else None})")
