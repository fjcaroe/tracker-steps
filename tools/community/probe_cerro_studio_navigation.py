"""Find visible Cerro menu actions that actually apply each selected Studio view."""
from unittest.mock import patch

from odoo.tools.safe_eval import safe_eval

from probe_cerro_studio_views import inventory


def capture(env):
    rows = inventory(env)
    actor = env['res.users'].browse(6)
    scoped = env['ir.ui.menu'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids, lang='en_US').env
    menus = list(scoped['ir.ui.menu']._visible_menu_ids())
    scoped.cr.execute("""SELECT m.id,a.id,a.res_model
                         FROM ir_ui_menu m JOIN ir_act_window a ON m.action='ir.actions.act_window,'||a.id::text
                         WHERE m.id=ANY(%s) AND a.res_model=ANY(%s) ORDER BY a.id,m.id""",
                      [menus, sorted({row['model'] for row in rows.values()})])
    actions = {}
    for menu, action, model in scoped.cr.fetchall():
        actions.setdefault((action, model), []).append(menu)
    wanted = {row['view_id']: (row['model'], row['kind']) for row in rows.values()}
    by_view = {pk: [] for pk in wanted}
    unresolved = {}
    for (action_id, model_name), menu_ids in actions.items():
        if all(by_view[pk] for pk, (name, _kind) in wanted.items() if name == model_name):
            continue
        action = scoped['ir.actions.act_window'].browse(action_id)
        try:
            with scoped.cr.savepoint():
                act = action.read(['views', 'context'])[0]
                ctx = dict(scoped.context)
                if act['context']:
                    ctx.update(safe_eval(act['context'], {
                        'uid': actor.id, 'user': actor, 'context': ctx,
                        'active_id': False, 'active_ids': [], 'active_model': False,
                        'allowed_company_ids': actor.company_ids.ids,
                    }))
                model = scoped[model_name].with_context(ctx)
                for requested, kind in act['views']:
                    if not any(pair == (model_name, kind) and not by_view[pk] for pk, pair in wanted.items()):
                        continue
                    seen = set()
                    cls = type(model.env['ir.ui.view'])
                    apply = cls.apply_inheritance_specs

                    def collect(view, *args, **kwargs):
                        result = apply(view, *args, **kwargs)
                        seen.update(view.ids)
                        return result

                    scoped.registry.clear_cache('default', 'templates')
                    with patch.object(cls, 'apply_inheritance_specs', collect):
                        model.get_views([(requested or False, kind)], options={'action_id': action_id})
                    for pk in seen & wanted.keys():
                        if wanted[pk] == (model_name, kind):
                            by_view[pk].append({'menus': menu_ids, 'action': action_id, 'kind': kind})
        except Exception as exc:
            unresolved[action_id] = {'type': type(exc).__name__, 'detail': str(exc)[:280]}
    return {'uid': actor.id, 'direct_menu_routes': by_view, 'errors': unresolved}
