from .hooks import migrate_contractor_form
from . import models
from . import dashboard
from . import costing


def post_init_hook(env):
    migrate_contractor_form(env)
