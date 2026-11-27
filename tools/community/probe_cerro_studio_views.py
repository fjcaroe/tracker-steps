"""Qualify restored Cerro Studio views with their original fields, parents and ordinary users."""
import hashlib
import json
import re
from unittest.mock import patch

from lxml import etree

from odoo.exceptions import AccessError, UserError


def digest_arch(arch):
    if isinstance(arch, str):
        arch = arch.encode()
    node = etree.fromstring(arch, etree.XMLParser(resolve_entities=False, remove_blank_text=True))
    return hashlib.sha256(etree.tostring(node, method='c14n')).hexdigest()


def inventory(env):
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', env.cr.dbname)
    env.cr.execute("""SELECT d.name,d.id,v.id,v.model,v.type,v.name,v.inherit_id,v.priority,v.active,v.mode,
                     (SELECT array_agg(group_id ORDER BY group_id) FROM ir_ui_view_group_rel WHERE view_id=v.id),
                      d.noupdate,v.arch_db
                   FROM ir_model_data d JOIN ir_ui_view v ON v.id=d.res_id AND d.model='ir.ui.view'
                   WHERE d.module='studio_customization' AND v.active ORDER BY v.id,d.id""")
    result = {}
    for alias, xml_id, pk, model, kind, name, parent, priority, active, mode, groups, locked, arches in env.cr.fetchall():
        assert alias not in result and mode == 'extension'
        result[alias] = {'xml_id': xml_id, 'view_id': pk, 'model': model, 'kind': kind, 'name': name,
                         'parent': parent, 'priority': priority, 'active': active, 'mode': mode,
                         'groups': groups or [], 'noupdate': locked,
                         'source_arch': {k: digest_arch(a) for k,a in sorted(arches.items())}}
    assert len({r['view_id'] for r in result.values()}) == 23
    return result


def render(env, account, row):
    records = env[row['model']].with_user(account).with_context(allowed_company_ids=account.company_ids.ids,
                                                               lang='en_US')
    scoped = records.env
    assert not scoped.su
    records.check_access('read')
    sample = records.search([], limit=1)
    if sample:
        sample.read(['id'])
    views = scoped['ir.ui.view']
    actual = type(views).apply_inheritance_specs
    seen = set()

    def observed(view, *args, **kwargs):
        result = actual(view, *args, **kwargs)
        seen.update(view.ids)
        return result

    scoped.registry.clear_cache('default', 'templates')
    with patch.object(type(views), 'apply_inheritance_specs', observed):
        rendered = records.get_view(view_id=row['parent'], view_type=row['kind'])
    if row['view_id'] not in seen:
        raise ValueError('Original inherited view was not applied to the selected parent')
    menu_ids = scoped['ir.ui.menu']._visible_menu_ids()
    # Menu IDs returned by Odoo already reflect this user's groups and model
    # read access. Dialogs/embedded lists can be reached without a direct menu.
    scoped.cr.execute("""SELECT m.id,a.id FROM ir_ui_menu m JOIN ir_act_window a
                         ON m.action='ir.actions.act_window,'||a.id::text
                         WHERE m.id=ANY(%s) AND a.res_model=%s ORDER BY m.id""",
                      [list(menu_ids), row['model']])
    return {'uid': account.id, 'visible_menu_actions': scoped.cr.fetchall(),
            'read_existing_record': bool(sample), 'rendered_sha256': digest_arch(rendered['arch'])}


def capture(env, reference=None, adopted=None, selected=None):
    definitions = inventory(env)
    if reference:
        assert definitions == reference['definitions']
    wanted = set(definitions) if selected is None else set(selected)
    assert wanted and wanted <= definitions.keys()
    accounts = env['res.users'].search([('active', '=', True), ('share', '=', False), ('id', '!=', 1)])
    accounts = accounts.sorted(lambda user: (user.id != 6, user.id != 2, user.id))
    qualified = {}
    errors = {}
    for alias, row in definitions.items():
        if alias not in wanted:
            continue
        if adopted is not None:
            assert env.ref(adopted[alias]) == env.ref('studio_customization.' + alias)
        candidates = accounts
        if reference and alias in reference['qualified']:
            candidates = accounts.browse(reference['qualified'][alias]['uid'])
        for actor in candidates:
            try:
                with env.cr.savepoint():
                    evidence = render(env, actor, row)
            except (AccessError, UserError, ValueError, KeyError) as error:
                # Keep diagnostics private. No row values or user names enter the receipt.
                errors.setdefault(alias, {})[str(actor.id)] = type(error).__name__
                continue
            qualified[alias] = evidence
            break
    if reference:
        assert json.loads(json.dumps(qualified)) == reference['qualified']
    return {'definitions': definitions, 'qualified': qualified, 'errors': errors,
            'resolved_views': len(qualified), 'selected_views': len(wanted), 'active_views': len(definitions)}
