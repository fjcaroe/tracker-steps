"""Read native freight concepts and existing instruction sections without writes."""
import json
try:
    module=env['ir.module.module'].search([('name','=','step_export_shipping_design')])
    print('SHIPPING_VERSION',module.latest_version,module.state)
    concepts=env['step.export.exterior.expense.concept'].search([])
    print('CONCEPTS',json.dumps([{'id':c.id,'name':c.name,'company':c.company_id.id} for c in concepts],ensure_ascii=False))
    for shipment in env['step.export.export'].search([],order='id desc',limit=10):
        print('SHIPMENT',json.dumps({'id':shipment.id,'company':shipment.company_id.id,'state':shipment.state,
            'documents':[(d.kind,d.originals,d.copies,d.instructions,d.status) for d in shipment.documentation_ids],
            'freights':[(f.concept_id.id,f.payment) for f in shipment.freight_ids]},ensure_ascii=False))
finally:
    env.cr.rollback()
