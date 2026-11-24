from app import create_app
from models import User
app = create_app()
with app.app_context():
    tls = User.query.filter_by(role='team_leader').all()
    for tl in tls:
        print(tl.id, tl.email, tl.full_name, 'is_active:', tl.is_active)
