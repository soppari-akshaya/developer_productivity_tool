from flask import Blueprint

snippets_bp = Blueprint('snippets', __name__, template_folder='../templates')

from . import routes

