"""Exercise independently granted rights, retained read-only reports and forbidden direct tag mutations."""
from odoo.exceptions import AccessError, UserError

from probe_cerro_pack_report_rows import history_scope


def exercise(env):
    assert env.cr.dbname in ('COMMUNITY_CERRO_BOM_PACKING_20261127U46A', 'COMMUNITY_CERRO_BOM_PACKING_20261127U46D','COMMUNITY_CERRO_BOM_PACKING_20261127U46C')
    previous=history_scope(env)
    actor=env['res.users'].browse(6)
    model=env['stock.picking'].with_user(actor).with_context(allowed_company_ids=[31],lang='en_US')
    original=model.browse(228)
    tag=original.fruit_tag_line_ids.package_id
    assert tag.step_tag_state=='validated'
    forged=tag.with_context(_cerro_process_receipt=True)
    foreign=model.with_context(allowed_company_ids=[1]).browse(228)
    detail=forged.step_tag_line_ids[0]
    tests={
        'foreign_picking':lambda: foreign.check_access('write'),
        'tag_state':lambda: forged.write({'step_tag_state':'created'}),
        'tag_detail':lambda: detail.write({'quantity':detail.quantity+1}),
        'create_tag':lambda: forged.create({'name':'U46-FORGED','is_fruit_tag':True,'step_tag_kind':'C'}),
        'container':lambda: model.env['step.harvest.container.transfer'].with_context(_cerro_process_receipt=True).create({}),
    }
    denied=[]
    for name,operation in tests.items():
        try:
            with env.cr.savepoint():
                operation()
        except (AccessError,UserError):
            denied.append(name)
        else:
            raise AssertionError('Unexpected access to '+name)
    assert tag.step_tag_state=='validated'
    env.cr.rollback()
    return dict(orders=previous,denied=denied)
