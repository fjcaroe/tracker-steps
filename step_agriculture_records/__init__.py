from . import models


def pre_init_hook(env):
    from .migrate_schema import MODELS, exists, table_name
    for old, new in MODELS.items():
        assert not exists(env.cr, table_name(old)), (
            'Prepare the versioned in-place migration before installing the native agricultural addon', old)


def post_init_hook(env):
    from .migrate_schema import finalize
    from .schema import SEQUENCES, MODELS
    for old, code in SEQUENCES.items():
        sequence = env['ir.sequence'].search([('code', '=', code)])
        if not sequence:
            # Fresh native documents get a fresh standard sequence. Existing
            # client sequence settings and counters are never overwritten.
            sequence = env['ir.sequence'].create({'name': env[MODELS[old]]._description,
                'code': code, 'prefix': MODELS[old].split('.')[-1].upper() + '/%(year)s/',
                'padding': 5, 'company_id': False})
    finalize(env.cr)
