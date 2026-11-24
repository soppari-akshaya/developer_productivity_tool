from flask import Blueprint

ai_assistant_bp = Blueprint(
    'ai_assistant',
    __name__,
    template_folder='templates',
    static_folder='../static'
)

from . import routes
