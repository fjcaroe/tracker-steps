{
    "name": "Steps - Historial tributario chileno",
    "version": "18.0.1.0.3",
    "author": "Steps",
    "license": "LGPL-3",
    "depends": ["l10n_cl", "step_document_library"],
    "external_dependencies": {"python": ["pdf417gen"]},
    "data": ["views/account_move.xml"],
    "pre_init_hook": "pre_init_hook",
    "installable": True,
}
