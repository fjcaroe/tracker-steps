from .hooks import migrate_contractor_form


def post_init_hook(env):
    migrate_contractor_form(env)
