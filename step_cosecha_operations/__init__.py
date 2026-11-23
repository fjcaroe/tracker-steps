from .hooks import migrate_contractor_form
from . import models


def post_init_hook(env):
    migrate_contractor_form(env)
