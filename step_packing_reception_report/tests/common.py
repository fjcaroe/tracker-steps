from odoo import Command


def receipt_fixture(env):
    company = env.company
    warehouse = env['stock.warehouse'].search([('company_id','=',company.id)], limit=1)
    kg = env.ref('uom.product_uom_kgm')
    producer = env['res.partner'].create({'name':'QA recibo productor', 'is_productor':True})
    driver = env['res.partner'].create({'name':'QA recibo chofer'})
    carrier = env['res.partner'].create({'name':'QA recibo transportista'})
    species = env['step.especie'].search([],limit=1)
    variety = env['step.variedad'].search([('especie_id','=',species.id)],limit=1)
    product = env['product.product'].create({'name':'QA recibo fruta', 'is_storable':True,
        'uom_id':kg.id,'uom_po_id':kg.id})
    box = env['product.packaging'].create({'name':'QA recibo caja','product_id':product.id,'qty':10})
    pallet = env['stock.package.type'].create({'name':'QA recibo pallet'})
    category = env['step.management.fruit.category'].create({'name':'QA recibo categoría','code':'QA-RECEIPT-CAT'})
    fruit_class = env['step.management.fruit.class'].create({'name':'QA recibo clase','code':'QA-RECEIPT-CLASS','category_id':category.id,'use_packing':True})
    picking = env['stock.picking'].create({'partner_id':producer.id,'picking_type_id':warehouse.in_type_id.id,
        'location_id':warehouse.in_type_id.default_location_src_id.id,'location_dest_id':warehouse.lot_stock_id.id,
        'step_fruit_reception_kind':'process','step_fruit_type':'conventional','fruit_guide_number':'QA-GUIA-141',
        'fruit_species_id':species.id,'fruit_variety_id':variety.id,'step_fruit_origin_class_id':fruit_class.id,
        'fruit_carrier_id':carrier.id,'fruit_truck_plate':'QA-141','step_fruit_driver_id':driver.id})
    move = env['stock.move'].create({'name':'QA recibo operación','picking_id':picking.id,'product_id':product.id,
        'product_uom':kg.id,'product_uom_qty':1200.50,'location_id':picking.location_id.id,
        'location_dest_id':picking.location_dest_id.id,'product_packaging_id':box.id,
        'step_fruit_pallet_type_id':pallet.id,'step_fruit_pallet_qty':3})
    move._action_confirm(merge=False)
    move.quantity=1200.50
    for i,net in enumerate((408.0,400.0,392.50)):
        env['step.packing.picking.tag.line'].create({'picking_id':picking.id,'product_id':product.id,
            'tag_number':'QA-141-%02d'%i,'sequence':i,'quantity':200,'packaging_id':box.id,
            'gross_kg':net+84,'tare_kg':84,'kilos':net})
    assert move.step_fruit_packaging_qty==600
    return picking
