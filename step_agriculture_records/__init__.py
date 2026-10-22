from . import models


def pre_init_hook(env):
    from .migrate_schema import MODELS, exists, table_name
    for old, new in MODELS.items():
        assert exists(env.cr, table_name(new)) and not exists(env.cr, table_name(old)), (
            'Prepare the versioned in-place migration before installing the native agricultural addon', old)


def post_init_hook(env):
    from .migrate_schema import finalize
    finalize(env.cr)
