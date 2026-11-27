"""Compare the import assistant's row privacy under every original Cerro internal account."""
from odoo.exceptions import AccessError


def exercise(env):
    assert env.cr.dbname in ('MANAGEMENT_QA_CERRO_BOM_20261126U42N','COMMUNITY_CERRO_BOM_PACKING_20261127U46C',
                             'COMMUNITY_CERRO_BOM_PACKING_20261127U46A', 'COMMUNITY_CERRO_BOM_PACKING_20261127U46D')
    actors=env['res.users'].with_context(active_test=True).search([('share','=',False)])
    assert len(actors)==15
    row_id=-460228
    env.cr.execute("""INSERT INTO step_fruit_reception_import
                      (id,picking_id,filename,create_uid,create_date,write_uid,write_date)
                      VALUES (%s,228,'original-control',6,now(),6,now())""",(row_id,))
    rows={}
    for actor in actors:
        model=env['step.fruit.reception.import'].with_user(actor).with_context(allowed_company_ids=actor.company_ids.ids)
        item=model.browse(row_id)
        result={}
        for verb in ('read','write','unlink'):
            try:
                item.check_access(verb)
            except AccessError:
                result[verb]=False
            else:
                result[verb]=True
        try:
            result['found']=model.search([('id','=',row_id)]).ids==[row_id]
        except AccessError:
            result['found']=False
        try:
            result['open']=item.web_read({'filename':{}})[0]['filename']=='original-control'
        except AccessError:
            result['open']=False
        rows[str(actor.id)]=result
    assert rows['6']['open'] and rows['6']['write']
    env.cr.rollback()
    return rows


def model_access(env):
    assert env.cr.dbname in ('MANAGEMENT_QA_CERRO_BOM_20261126U42N','COMMUNITY_CERRO_BOM_PACKING_20261127U46D',
                             'COMMUNITY_CERRO_BOM_PACKING_20261127U46C','COMMUNITY_CERRO_BOM_PACKING_20261127U46A')
    models=('step.fruit.reception.import','step.fruit.package.line','step.packing.picking.tag.line',
            'step.harvest.container.transfer','step.harvest.container.transfer.line','step.scale.profile',
            'stock.picking','stock.move','stock.move.line','stock.quant','stock.quant.package','stock.lot',
            'product.product','product.template','product.packaging')
    users=env['res.users'].search([('share','=',False),('active','=',True)])
    assert len(users)==15
    result={}
    for user in users:
        rights=env['ir.model.access'].with_user(user).with_context(allowed_company_ids=user.company_ids.ids)
        result[str(user.id)]={model:[rights.check(model,mode,raise_exception=False)
                                     for mode in ('read','create','write','unlink')] for model in models}
    env.cr.rollback()
    return result
