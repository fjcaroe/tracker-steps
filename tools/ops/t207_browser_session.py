"""Create/remove a private native session for T207/T208 read-only browser review."""
import json
import os
from pathlib import Path
from odoo import http
from native_business_profile import scoped_business_environment

hosts = {'LAB_TAREAS': 'desarrollo.stepsapp.cl', 'CERRO_EL_PLOMO': 'cerroelplomo.stepsapp.cl',
         'QA-CERROELPLOMO': 'qa-cerroelplomo.stepsapp.cl'}
assert env.cr.dbname in hosts
proof = Path(os.environ['T207_BROWSER_PROOF'])
assert proof.parent == Path('/tmp') and proof.name.startswith('t207-browser-')
if os.environ.get('T207_CLEANUP') == '1':
    data = json.loads(proof.read_text())
    session = http.root.session_store.get(data['session_id'])
    assert session.get('db') == env.cr.dbname
    http.root.session_store.delete(session)
    proof.unlink()
    print('T207_BROWSER_SESSION_REMOVED')
else:
    assert not proof.exists()
    business = scoped_business_environment(env)
    requested_company = int(os.environ.get('T207_COMPANY_ID') or 0)
    if requested_company:
        company = env['res.company'].search([('id', '=', requested_company), ('id', 'child_of', business.company.id)])
        assert len(company) == 1, 'Review must remain inside the destination business'
        business = scoped_business_environment(env, company=company)
    user = business.user
    session = http.root.session_store.new()
    session.update({'db': env.cr.dbname, 'uid': user.id, 'login': user.login,
        'context': dict(user.with_user(user).context_get(), allowed_company_ids=business.company.ids),
        'session_token': user._compute_session_token(session.sid)})
    actions = {name: business.ref(xmlid).id for name, xmlid in {
        'guides':'step_dispatch_guide.action_dispatch_guides',
        'receipts':'step_inventory_packing.action_steps_fruit_process_reception',
        'report':'step_producer_fruit_reports.action_process',
        'interplant':'step_packing_interplant.receipts'}.items()}
    data = {'session_id': session.sid, 'company_id': business.company.id,
        'host': hosts[env.cr.dbname], 'actions': actions}
    if os.environ.get('T209_WAREHOUSE_CASE'):
        from odoo.addons.step_export_branch_consolidation.models import branch_companies
        branches = branch_companies(business,business.company) - business.company
        requested = int(os.environ.get('T209_DESTINATION_ID') or 0)
        if requested:
            branches = branches.filtered(lambda c:c.id == requested)
        cases = []
        for destination in branches:
            warehouses = business['stock.warehouse'].with_company(destination).search([('company_id','=',destination.id)])
            if warehouses:
                cases.append((destination,warehouses))
        kind = business['step.freight.dispatch.type'].search([('step_recipient_kind','=','interplant')],limit=1)
        assert kind or env.cr.dbname == 'LAB_TAREAS'
        if not cases:
            assert env.cr.dbname == 'LAB_TAREAS', 'Customer destination must already exist'
            data['warehouse_case'] = {'no_destination':True,'guide_id':False,'type':kind.display_name if kind else False,
                'source_name':business.company.display_name,'warehouses':[]}
        else:
            destination, warehouses = cases[0]
            guide = business['step.dispatch.guide'].search([('name','=',os.environ.get('T209_GUIDE_NAME','')),
                ('company_id','=',business.company.id),('state','=','draft')],limit=1)
            if guide:
                assert guide.step_destination_company_id == destination
            data['warehouse_case'] = {'guide_id':guide.id, 'type':kind.display_name,
                'partner':destination.partner_id.display_name,'source_name':business.company.display_name,
                'destination':destination.id,'warehouses':warehouses.mapped('display_name')}
    http.root.session_store.save(session)
    proof.write_text(json.dumps(data))
    proof.chmod(0o600)
    print('T207_BROWSER_SESSION_READY')
env.cr.rollback()
