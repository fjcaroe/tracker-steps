"""Cold-start checks for the original salesperson on the restored Steps CRM cohort."""
from hashlib import sha1

from odoo.exceptions import AccessError


def steps_restore_access(env, core):
    from odoo.modules.module import get_manifest, get_module_path
    import sys
    from hashlib import sha256
    from pathlib import Path

    summary = run(env, inspect_only=True)
    assert summary['phase'] == 'inspected'
    assert (summary['menu'], summary['server_action'], summary['action'], summary['view']) == (340,488,505,1484)
    assert summary['full_form']['values'] == 'c16475d9351129e493c871c226f50e3f85bf3eb324db4c44fc3a226505e64b26'
    assert (summary['full_form']['records'], summary['full_form']['fields']) == (9,72)
    env.cr.execute('SET TRANSACTION READ ONLY')
    installed = env['ir.module.module'].search([('state','=','installed')])
    manifests = {}
    for module in installed:
        path = Path(get_module_path(module.name)).resolve(strict=True)
        imported = Path(sys.modules['odoo.addons.'+module.name].__file__).resolve(strict=True).parent
        assert imported == path and path.is_relative_to(core)
        info = get_manifest(module.name)
        assert info['version'] == module.latest_version and info['license'] == module.license
        assert module.license in {'LGPL-3','GPL-3','AGPL-3'}
        manifests[module.name] = sha256((path/'__manifest__.py').read_bytes()).hexdigest()
    assert len(manifests) == 157
    assert digest(manifests) == '0146e9a78d75ed0b33c943505cc3c1a3026f7fd15d2a5ec0c6198087465cd210'
    actor = env['res.users'].browse(7)
    attachments = env['ir.attachment'].with_user(actor).with_context(allowed_company_ids=[1], bin_size=False)
    assert not attachments.env.su and not actor.has_group('base.group_system')
    leads = attachments.env['crm.lead'].with_context(active_test=False).search([])
    sample = attachments.search([('res_model','=','crm.lead'),('res_id','in',leads.ids),
                                 ('store_fname','!=',False),('file_size','>',0),('file_size','<',2_000_000)],
                                order='id', limit=12)
    assert len(sample) == 12
    denied = []
    for obj in sample:
        obj.check_access('read')
        raw = obj.raw
        assert len(raw) == obj.file_size and sha1(raw).hexdigest() == obj.checksum
        public = obj.with_user(env.ref('base.public_user'))
        assert not public.env.su
        try:
            public.check_access('read')
        except AccessError:
            denied.append(obj.id)
    assert denied == sample.ids
    results = {'crm':{'visible': len(leads), 'own':9, 'fields':72, 'menu':340,
                      'values':summary['full_form']['values'], 'attachments':12, 'public_denied':12,
                      'proof_of_loaded_providers':digest(manifests)}}
    if not env['ir.ui.view'].browse(1444).active:
        from odoo.tests import Form
        scope = attachments.env
        leads = scope['crm.lead'].search([('user_id','=',actor.id),('partner_id','!=',False),
                                         ('order_ids','=',False)], order='id', limit=1)
        assert leads
        action = leads.action_sale_quotations_new()
        model = scope['sale.order'].with_context(**action['context'])
        form_view = next((ident for ident, kind in action['views'] if kind == 'form'), False)
        form = Form(model, view=form_view or None)
        assert form.partner_id == leads.partner_id and form.opportunity_id == leads
        assert model.search_count([]) == 4
        results['sale_quotation'] = {'form_initialized':True, 'action':action['id'], 'historical_orders':4}
    return actor, results
