"""Preserve existing ownership before company_id becomes a compatibility value."""
from odoo import Command
from .models.catalogs import CATALOGS, _INSTALL_SCOPE


def post_init_hook(env):
    # During installation the computed company_id can already have recomputed.
    # Ownership is captured by _auto_init before schema setup (see below).
    for model in CATALOGS:
        table = env[model]._table
        env.cr.execute('SELECT to_regclass(%s)', ('steps_catalog_scope_' + table,))
        if not env.cr.fetchone()[0]:
            continue
        env.cr.execute('SELECT id,company_id FROM steps_catalog_scope_' + table)
        for record_id, company_id in env.cr.fetchall():
            record = env[model].browse(record_id).exists()
            if record:
                record.with_context(_install_scope=_INSTALL_SCOPE).write({'company_ids': [Command.set([company_id] if company_id else [])]})
        env.cr.execute('DROP TABLE steps_catalog_scope_' + table)
    for model in CATALOGS:
        env[model].search([])._check_catalog_scope()
