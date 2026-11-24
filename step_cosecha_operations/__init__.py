from .hooks import migrate_contractor_form
from . import models
from . import dashboard


def post_init_hook(env):
    migrate_contractor_form(env)
