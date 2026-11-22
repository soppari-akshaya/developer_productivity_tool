from flask import Blueprint

issues_bp = Blueprint('issues', __name__, template_folder='../templates')

from . import routes

