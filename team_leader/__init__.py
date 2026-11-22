from flask import Blueprint

team_leader_bp = Blueprint('team_leader', __name__, template_folder='../templates')

from . import routes

