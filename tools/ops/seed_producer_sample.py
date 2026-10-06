"""Coherent synthetic Productores walkthrough, for Desarrollo only.

Run through manage_producer_sample.py. No fiscal emission, emails, configuration
changes, Studio metadata edits or destructive reset. One transaction owns all
created records; a completion manifest makes reruns preserve manual demo edits.
"""
import json
from datetime import timedelta

from odoo import Command, fields

MARKER = 'steps.qa.productores.walkthrough.v1'
NAMESPACE = 'steps_qa_productores_walkthrough'
LABEL = 'PRUEBA - '


def business_fingerprints(env):
    """Retain every pre-existing business row, including write dates and money."""
    env.flush_all()
    env.cr.execute("""SELECT t.tablename, EXISTS(
        SELECT 1 FROM information_schema.columns c
        WHERE c.table_schema='public' AND c.table_name=t.tablename AND c.column_name='id')
        FROM pg_tables t WHERE t.schemaname='public' AND
        (t.tablename LIKE 'step_%' OR t.tablename LIKE 'account_%' OR
         t.tablename LIKE 'stock_%' OR t.tablename LIKE 'product_%' OR
         t.tablename LIKE 'mrp_%' OR t.tablename IN ('res_company','res_partner','ir_config_parameter'))
        ORDER BY t.tablename""")
    parts = []
    for table, has_id in env.cr.fetchall():
        # Names come from PostgreSQL, not user input.
        assert table.replace('_', '').isalnum()
        key = 'id::text' if has_id else 'md5(to_jsonb(t)::text)'
        parts.append("SELECT '%s',COALESCE(jsonb_object_agg(k,v),'{}'::jsonb) FROM "
                     "(SELECT %s k,md5(to_jsonb(t)::text)||':'||count(*)::text v FROM %s t "
                     "GROUP BY %s,to_jsonb(t)) q" % (table, key, table, key))
    env.cr.execute(' UNION ALL '.join(parts))
    return dict(env.cr.fetchall())


def assert_preserved(before, after):
    changed = {table for table, rows in before.items()
               if any(after.get(table, {}).get(key) != value for key, value in rows.items())}
    assert not changed, 'Pre-existing business rows changed: ' + ', '.join(sorted(changed))


def verify_manifest(env, manifest):
    assert manifest['company_id'] == env.company.id
    for key, item in manifest['records'].items():
        row = env[item['model']].browse(item['id']).exists()
        assert row, 'Sample record missing: ' + key
        if 'company_id' in row._fields and row.company_id:
            assert row.company_id == env.company, key
    return manifest


def seed(env):
    assert env.cr.dbname == 'LAB_TAREAS' or env.cr.dbname.startswith('MANAGEMENT_QA_DEVELOPMENT_'), 'QA only'
    env = env(context=dict(env.context, tracking_disable=True, mail_create_nosubscribe=True,
                          mail_create_nolog=True, mail_notrack=True))
    old = env['ir.config_parameter'].sudo().get_param(MARKER)
    if old:
        return verify_manifest(env, json.loads(old))
    assert env.company.step_fruit_inventory_enabled, 'Agricultural receptions must already be enabled'
    assert env.company.dispatch_dte_provider == 'third_party', 'Internal guide mode must already be configured'
    assert env.company.step_producer_advance_account_id and env.company.step_producer_advance_product_id
    company, today = env.company, fields.Date.today()
    monday = today - timedelta(days=today.weekday())
    end = monday + timedelta(days=27)
    usd, kg, unit = env.ref('base.USD'), env.ref('uom.product_uom_kgm'), env.ref('uom.product_uom_unit')
    variety = env['step.variedad'].search([('name', '=', 'Santina'), ('especie_id.name', '=', 'Cerezas')])
    assert len(variety) == 1, 'Use an unambiguous existing Santina/Cerezas master'
    species, group = variety.especie_id, variety.grupo_variedad_id
    warehouse = env.ref('stock.warehouse0')
    assert warehouse.company_id == company
    records = {}

    def remember(key, row):
        assert key not in records
        records[key] = {'model': row._name, 'id': row.id}
        env['ir.model.data'].create({'module': NAMESPACE, 'name': key,
                                    'model': row._name, 'res_id': row.id, 'noupdate': True})
        return row

    def create(key, model, values):
        assert not env.ref(NAMESPACE + '.' + key, raise_if_not_found=False), 'Partial sample must be audited'
        return remember(key, env[model].create(values))

    season = create('season', 'step.temporada', {'name': LABEL + 'Temporada demostración %s/%s' % (today.year, today.year + 1)})
    producers, farms = [], []
    for key, name, city in [('valle', 'Agrícola Valle Claro', 'Talca'), ('sur', 'Huertos del Sur', 'Curicó')]:
        producer = create('producer_' + key, 'res.partner', {
            'name': LABEL + name, 'is_company': True, 'is_productor': True,
            'company_id': company.id, 'country_id': env.ref('base.cl').id,
            'city': city, 'comment': 'Datos ficticios para recorrer Productores en Desarrollo. Sin RUT ni datos de contacto reales.'})
        farm = create('farm_' + key, 'step.fundo', {
            'name': LABEL + ('Fundo Los Cerezos' if key == 'valle' else 'Fundo Santa Rosa'),
            'partner_id': producer.id, 'company_id': company.id, 'city': city,
            'fundo_code': 'PRUEBA-' + key.upper(), 'hec_total': 20, 'hec_plant': 15})
        producers.append(producer); farms.append(farm)
    packing = create('packing', 'res.partner', {'name': LABEL + 'Planta Central', 'is_company': True,
                                              'company_id': company.id, 'step_export_packing': True,
                                              'step_export_packing_type': 'third_party'})
    receiver = create('receiver', 'res.partner', {'name': LABEL + 'Importadora de fruta', 'is_company': True,
                                                'company_id': company.id, 'country_id': env.ref('base.us').id})
    driver = create('driver', 'res.partner', {'name': LABEL + 'Chofer demostración', 'company_id': company.id})
    category = create('product_category', 'product.category', {'name': LABEL + 'Productos demostración',
                                                              'property_valuation': 'manual_periodic'})

    def product(key, name, uom, weight, fruit=True):
        return create(key, 'product.product', {'name': LABEL + name, 'default_code': 'PRUEBA-' + key.upper(),
            'company_id': company.id, 'categ_id': category.id, 'is_storable': True,
            'type': 'consu', 'weight': weight, 'uom_id': uom.id, 'uom_po_id': uom.id,
            'tracking': 'none', 'is_fruta': fruit, 'grupo_labor': 'pack',
            'step_export_enabled': fruit, 'step_export_species_id': species.id if fruit else False,
            'taxes_id': [Command.clear()], 'supplier_taxes_id': [Command.clear()]})

    raw = product('raw', 'Cereza Santina a proceso (kg)', kg, 1)
    finished = product('finished', 'Cereza Santina caja 5 kg', unit, 5)
    carton = product('carton', 'Caja de embalaje', unit, 0.2, False)
    pallet = create('pallet_type', 'stock.package.type', {'name': LABEL + 'Pallet 80 cajas', 'step_export_boxes_per_pallet': 80})
    packaging = create('packaging', 'product.packaging', {'name': LABEL + 'Caja 5 kg', 'company_id': company.id, 'product_id': finished.id,
                                                          'qty': 1, 'step_export_kg_per_box': 5})
    bom = create('bom', 'mrp.bom', {'product_tmpl_id': finished.product_tmpl_id.id, 'product_id': finished.id,
        'company_id': company.id, 'product_qty': 1, 'product_uom_id': unit.id, 'step_export_fruit': True,
        'bom_line_ids': [Command.create({'product_id': carton.id, 'product_qty': 1, 'product_uom_id': unit.id})]})
    expense = company.step_export_purchase_account_id
    assert expense and company in expense.company_ids
    accounts = env['account.account'].search([('company_ids', 'in', company.ids), ('deprecated', '=', False),
                                             ('account_type', '=', 'liability_current')], order='code,id')
    provision = accounts.filtered(lambda row: '210331' in row.code)[:1]
    assert provision, 'Existing contract provision account is required'
    journals = env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'general')], order='id')
    journal = journals.filtered(lambda row: not row.l10n_latam_use_documents and
        (not company.step_producer_advance_account_id.allowed_journal_ids or
         row in company.step_producer_advance_account_id.allowed_journal_ids) and
        (not provision.allowed_journal_ids or row in provision.allowed_journal_ids))[:1]
    assert journal, 'Reuse an approved non-fiscal contract journal without changing allowed journals'
    fixed = create('fixed_cost', 'step.export.grower.discount', {'name': LABEL + 'Embalaje y operación',
                'company_id': company.id, 'code': 'QA-EMB', 'account_id': expense.id})
    margin = create('margin_cost', 'step.export.grower.discount', {'name': LABEL + 'Gestión comercial',
                'company_id': company.id, 'code': 'QA-GEST', 'account_id': expense.id})
    rates = []
    for index, producer in enumerate(producers):
        rates.append(create('rate_' + str(index), 'step.export.grower.rate', {
            'name': LABEL + 'Tarifa ' + producer.name.removeprefix(LABEL), 'date': today,
            'company_id': company.id, 'producer_id': producer.id, 'season_id': season.id, 'species_id': species.id,
            'rate_type': 'usd_kg', 'rate_value': 4.5, 'expense_account_id': expense.id,
            'notes': '<p>Tarifa ficticia: gasto fijo por kg y gestión comercial del 8 % del FOB.</p>',
            'preliq_line_ids': [Command.create({'item_id': fixed.id, 'value_type': 'usd_kg', 'value': 1.2 - index * 0.3}),
                               Command.create({'item_id': margin.id, 'value_type': 'fob_fraction', 'value': 0.08})]}))
    create('price_list', 'step.producer.preliq.price', {'name': LABEL + 'Precios FOB cerezas',
        'company_id': company.id, 'season_id': season.id, 'species_id': species.id,
        'valid_from': monday, 'valid_to': end + timedelta(days=60), 'currency_id': usd.id,
        'line_ids': [Command.create({'variety_id': variety.id, 'product_id': p.id,
                                    'uom_id': kg.id, 'price': 6.5}) for p in (raw, finished)]})
    estimates, contracts = [], []
    for index, (producer, farm, quantity, kind, fruit) in enumerate(zip(producers, farms, (8000, 4000), ('process', 'packed'), (raw, finished))):
        estimate = create('estimate_' + str(index), 'step.export.estimate', {
            'name': LABEL + 'Cosecha ' + producer.name.removeprefix(LABEL), 'date': today,
            'company_id': company.id, 'producer_id': producer.id, 'fundo_id': farm.id,
            'packing_partner_id': packing.id, 'season_id': season.id, 'delivery_start': monday, 'delivery_end': end,
            'notes': '<p>Ejemplo de %s kg exportables repartidos en cuatro semanas.</p>' % quantity,
            'estimate_line_ids': [Command.create({'delivery_kind': kind, 'species_id': species.id,
                'variety_group_id': group.id, 'variety_id': variety.id, 'product_id': fruit.id,
                'export_kg': quantity, 'export_percentage': 0.8 if kind == 'process' else 1,
                'kg_per_box': 5, 'boxes_per_package': 80, 'packaging_id': packaging.id if kind == 'packed' else False,
                'package_type_id': pallet.id, 'week_line_ids': [Command.create({
                    'week_start': monday + timedelta(days=7 * n), 'export_kg': quantity / 4}) for n in range(4)]})]})
        estimate.action_validate_estimate(); estimate.action_activate_estimate(); estimates.append(estimate)
        contract = create('contract_' + str(index), 'step.producer.purchase.contract', {
            'name': 'PRUEBA/CTR/%02d' % (index + 1), 'company_id': company.id, 'partner_id': producer.id,
            'date_start': monday, 'date_end': end, 'currency_id': usd.id, 'operation_type': 'Anticipo demostración',
            'reference': LABEL + 'Recorrido Productores', 'journal_id': journal.id,
            'provision_account_id': provision.id, 'accounting_date': today,
            'notes': '<p>Contrato ficticio de QA. Dos cuotas de anticipo, sin emisión tributaria.</p>',
            'product_line_ids': [Command.create({'product_id': fruit.id, 'species_id': species.id,
                'variety_id': variety.id, 'quantity': quantity, 'uom_id': kg.id, 'price_unit': 0.25})]})
        for n in range(2):
            env['step.producer.purchase.contract.installment'].create({'contract_id': contract.id,
                'product_line_id': contract.product_line_ids.id, 'sequence': 10 * (n + 1),
                'quantity': quantity / 2, 'date_due': monday + timedelta(days=7 + n * 14),
                'validation_criteria': 'Cuota de anticipo ficticia para demostración'})
        contract.action_confirm(); contracts.append(contract)
    contracts[0].action_account()
    remember('advance_entry', contracts[0].accounting_move_id)
    revision = env['step.export.estimate'].browse(estimates[0].action_new_estimate_version()['res_id'])
    revision.name = LABEL + 'Cosecha Valle Claro / nueva versión editable'
    remember('estimate_revision', revision)

    def receive(key, producer, farm, fruit, quantities, kind):
        tags = env['stock.quant.package']
        for n, amount in enumerate(quantities):
            tag = create(key + '_tag_' + str(n), 'stock.quant.package', {
                'name': 'PRUEBA/' + key.upper() + '/%02d' % (n + 1), 'is_fruit_tag': True,
                'step_tag_kind': 'C' if kind == 'process' else 'E', 'package_type_id': pallet.id,
                'step_packing_result': 'export' if kind == 'packed' else False})
            tags |= tag
        picking = create(key, 'stock.picking', {'origin': LABEL + key, 'partner_id': producer.id,
            'company_id': company.id, 'picking_type_id': warehouse.in_type_id.id,
            'location_id': env.ref('stock.stock_location_suppliers').id, 'location_dest_id': warehouse.lot_stock_id.id,
            'fruit_fundo_id': farm.id, 'fruit_species_id': species.id, 'fruit_variety_id': variety.id,
            'fruit_season_id': season.id, 'step_fruit_reception_kind': kind,
            'step_fruit_gross_kg': sum(quantities), 'fruit_guide_number': 'PRUEBA-' + key.upper(),
            'fruit_tag_line_ids': [Command.create({'tag_number': tag.name, 'package_id': tag.id,
                'product_id': fruit.id, 'quantity': amount if fruit == raw else amount / 5,
                'kilos': amount, 'box_count': amount / 5, 'uom_id': fruit.uom_id.id})
                for tag, amount in zip(tags, quantities)]})
        picking.action_prepare_fruit_stock(); picking.with_context(skip_backorder=True).button_validate()
        assert picking.state == 'done' and all(tag.step_tag_state == 'validated' for tag in tags)
        return picking, tags

    _, raw_tags = receive('reception_process', producers[0], farms[0], raw, (1000, 2000), 'process')
    _, packed_tags = receive('reception_packed', producers[1], farms[1], finished, (1000,), 'packed')
    supply = create('material_reception', 'stock.picking', {'origin': LABEL + 'Materiales de embalaje',
        'company_id': company.id, 'picking_type_id': warehouse.in_type_id.id,
        'location_id': env.ref('stock.stock_location_suppliers').id, 'location_dest_id': warehouse.lot_stock_id.id,
        'move_ids': [Command.create({'name': LABEL + 'Cajas de embalaje', 'product_id': carton.id,
            'product_uom': unit.id, 'product_uom_qty': 1000,
            'location_id': env.ref('stock.stock_location_suppliers').id, 'location_dest_id': warehouse.lot_stock_id.id})]})
    supply.action_confirm(); supply.action_assign(); supply.move_ids.quantity = 1000
    supply.with_context(skip_backorder=True).button_validate(); assert supply.state == 'done'
    order = create('packing_order', 'step.packing.order', {'name': 'PRUEBA/OP/01', 'company_id': company.id,
        'week_start': monday, 'week_end': monday + timedelta(days=6), 'packing_partner_id': packing.id,
        'instruction': '<p>Demostración: 80 % de fruta exportable y 20 % de merma. Cajas de 5 kg.</p>',
        'line_ids': [Command.create({'product_id': finished.id, 'species_id': species.id,
            'variety_id': variety.id, 'boxes': 480, 'kilos': 2400, 'bom_id': bom.id})]})
    order.action_refresh_materials(); order.action_validate()
    outputs = env['stock.quant.package']
    for n in range(2):
        outputs |= create('packed_output_' + str(n), 'stock.quant.package', {
            'name': 'PRUEBA/EMBALADA/%02d' % (n + 1), 'is_fruit_tag': True, 'step_tag_kind': 'E',
            'step_packing_result': 'export', 'step_producer_id': producers[0].id, 'fundo_id': farms[0].id,
            'step_export_season_id': season.id, 'especie_id': species.id, 'variedad_id': variety.id,
            'package_type_id': pallet.id, 'step_tag_line_ids': [Command.create({'producer_id': producers[0].id,
                'product_id': finished.id, 'quantity': 80, 'boxes': 80, 'kilos': 400})]})
    ot = create('packing_closed', 'step.packing.production', {'name': 'PRUEBA/OT/01', 'company_id': company.id,
        'step_packing_order_id': order.id, 'product_id': finished.id, 'product_qty': 160,
        'product_uom_id': unit.id, 'bom_id': bom.id, 'fruit_fundo_id': farms[0].id,
        'fruit_species_id': species.id, 'step_packing_input_tag_ids': [Command.set(raw_tags[:1].ids)],
        'step_packing_output_tag_ids': [Command.set(outputs.ids)]})
    ot.action_step_packing_validate(); ot.action_prepare_materials(); ot.action_approve_materials(); ot.action_step_packing_close()
    assert ot.state == 'closed' and ot.step_packing_export_kg == 800 and ot.step_packing_loss_kg == 200
    waiting_output = create('packing_pending_output', 'stock.quant.package', {
        'name': 'PRUEBA/EMBALADA/PENDIENTE', 'is_fruit_tag': True, 'step_tag_kind': 'E', 'step_packing_result': 'export',
        'step_producer_id': producers[0].id, 'especie_id': species.id, 'variedad_id': variety.id,
        'step_export_season_id': season.id, 'step_tag_line_ids': [Command.create({'producer_id': producers[0].id,
            'product_id': finished.id, 'quantity': 320, 'boxes': 320, 'kilos': 1600})]})
    pending = create('packing_pending', 'step.packing.production', {'name': 'PRUEBA/OT/02', 'company_id': company.id,
        'step_packing_order_id': order.id, 'product_id': finished.id, 'product_qty': 320,
        'product_uom_id': unit.id, 'bom_id': bom.id, 'fruit_fundo_id': farms[0].id,
        'fruit_species_id': species.id, 'step_packing_input_tag_ids': [Command.set(raw_tags[1:].ids)],
        'step_packing_output_tag_ids': [Command.set(waiting_output.ids)]})
    pending.action_step_packing_validate(); pending.action_prepare_materials(); pending.action_approve_materials()
    income = env['account.account'].search([('company_ids', 'in', company.ids), ('deprecated', '=', False), ('allowed_journal_ids', '=', False),
                                          ('account_type', '=', 'income')], order='code,id', limit=1)
    assert income
    sales_journal = create('sales_journal', 'account.journal', {'name': LABEL + 'Ventas internas QA (sin DTE)',
        'code': 'QAVEN', 'company_id': company.id, 'type': 'sale', 'currency_id': usd.id,
        'default_account_id': income.id, 'l10n_latam_use_documents': False})
    program = create('sales_program', 'step.export.sales.program', {'name': LABEL + 'Programa de ventas cerezas',
        'company_id': company.id, 'partner_id': receiver.id, 'season_id': season.id, 'species_id': species.id,
        'product_id': finished.id, 'packaging_id': packaging.id, 'package_type_id': pallet.id,
        'date_start': monday, 'date_end': end, 'currency_id': usd.id, 'rate_to_usd': 1,
        'pallets_per_container': 1, 'boxes_per_pallet': 80, 'kg_per_box': 5,
        'line_ids': [Command.create({'week_start': monday, 'container_qty': 1, 'price_per_kg': 6.5})]})
    program.action_validate(); program.action_activate()
    reason = env['step.dispatch.transfer.reason'].search([('code', '=', '1')])
    if not reason:
        reason = env['step.dispatch.transfer.reason'].search([], limit=1)
    assert len(reason) == 1
    guide = create('dispatch_guide', 'step.dispatch.guide', {'company_id': company.id,
        'external_folio': 'PRUEBA-SIN-VALOR-01', 'partner_id': receiver.id, 'driver_partner_id': driver.id,
        'origin_address': 'Planta ficticia de demostración', 'destination_address': 'Destino ficticio de QA',
        'truck_plate': 'QA0000', 'transfer_reason_id': reason.id,
        'reference': LABEL + 'Sin documento tributario ni transmisión externa',
        'line_ids': [Command.create({'product_id': finished.id, 'description': LABEL + 'Fruta de demostración',
            'product_uom_id': unit.id, 'quantity': 80, 'quantity_kg': 400, 'price_unit': 0})]})
    guide.action_confirm()
    shipment = create('shipment', 'step.export.export', {'name': LABEL + 'Embarque cerezas', 'company_id': company.id,
        'sales_program_id': program.id, 'date': today, 'departure_date': today,
        'destination_country_id': receiver.country_id.id, 'tag_ids': [Command.set(outputs[:1].ids)],
        'dispatch_guide_ids': [Command.set(guide.ids)], 'dus_folio': 'PRUEBA-SIN-VALOR-DUS',
        'bl_folio': 'PRUEBA-SIN-VALOR-BL', 'ivv_folio': 'PRUEBA-SIN-VALOR-IVV',
        'line_ids': [Command.create({'product_id': finished.id, 'variety_id': variety.id,
            'pallet_qty': 1, 'boxes_per_pallet': 80, 'kg_per_box': 5})]})
    shipment.action_validate_shipment(); shipment.action_dispatch(); shipment.action_ship()
    dispatch = create('stock_dispatch', 'stock.picking', {'company_id': company.id, 'origin': LABEL + 'Embarque demostración',
        'partner_id': receiver.id, 'picking_type_id': warehouse.out_type_id.id,
        'location_id': warehouse.lot_stock_id.id, 'location_dest_id': env.ref('stock.stock_location_customers').id,
        'move_ids': [Command.create({'name': LABEL + 'Despacho caja 5 kg', 'product_id': finished.id,
            'product_uom': unit.id, 'product_uom_qty': 80, 'location_id': warehouse.lot_stock_id.id,
            'location_dest_id': env.ref('stock.stock_location_customers').id})]})
    dispatch.action_confirm()
    env['stock.move.line'].create({'picking_id': dispatch.id, 'move_id': dispatch.move_ids.id,
        'product_id': finished.id, 'product_uom_id': unit.id, 'quantity': 80,
        'package_id': outputs[0].id, 'location_id': warehouse.lot_stock_id.id,
        'location_dest_id': env.ref('stock.stock_location_customers').id})
    dispatch.with_context(skip_backorder=True).button_validate(); assert dispatch.state == 'done'
    shipment.picking_ids = [Command.set(dispatch.ids)]
    invoice = create('internal_invoice', 'account.move', {'move_type': 'out_invoice', 'company_id': company.id,
        'journal_id': sales_journal.id, 'partner_id': receiver.id, 'currency_id': usd.id,
        'invoice_date': today, 'date': today, 'ref': LABEL + 'Simulación QA sin emisión fiscal',
        'step_export_shipment_id': shipment.id, 'invoice_line_ids': [Command.create({'product_id': finished.id,
            'name': LABEL + '80 cajas de 5 kg, ejemplo sin valor tributario', 'quantity': 80,
            'price_unit': 32.5, 'account_id': income.id, 'tax_ids': [Command.clear()]})]})
    invoice.action_post(); shipment.action_invoice()
    receiver_settlement = create('receiver_settlement', 'step.export.receiver.settlement', {
        'name': 'PRUEBA/REC/01', 'company_id': company.id, 'receiver_id': receiver.id,
        'sales_program_id': program.id, 'date': today, 'currency_id': usd.id, 'rate_to_usd': 1,
        'receiver_reference': LABEL + 'Liquidación ficticia', 'line_ids': [Command.create({
            'shipment_id': shipment.id, 'invoice_id': invoice.id, 'sales_amount': 2600,
            'expenses_usd': 300, 'commission_rate': 0.05})]})
    receiver_settlement.action_validate()
    liquidated = receiver_settlement.producer_settlement_ids
    assert len(liquidated) == 1 and liquidated.producer_id == producers[0]
    liquidated.name = 'PRUEBA/LIQ/01'
    liquidated.discount_line_ids = [Command.create({'item_id': fixed.id, 'amount_usd': 120})]
    liquidated.fob_transfer_percent = 90
    liquidated.action_validate(); remember('producer_settlement_validated', liquidated)
    assert receiver_settlement.total_fob_usd == 2170 and liquidated.net_usd == 1833
    draft = create('producer_settlement_draft', 'step.export.producer.settlement', {
        'name': 'PRUEBA/LIQ/02', 'company_id': company.id, 'date': today, 'producer_id': producers[1].id,
        'season_id': season.id, 'species_id': species.id, 'rate_id': rates[1].id,
        'line_ids': [Command.create({'tag_id': packed_tags.id, 'kg_qty': 1000, 'allocated_fob_usd': 6500})],
        'discount_line_ids': [Command.create({'item_id': fixed.id, 'amount_usd': 250})]})
    for index, producer in enumerate(producers):
        preliq = create('preliquidation_' + str(index), 'step.producer.preliquidation', {
            'name': LABEL + 'Preliquidación ' + producer.name.removeprefix(LABEL), 'company_id': company.id,
            'producer_id': producer.id, 'season_id': season.id, 'species_id': species.id,
            'date': today, 'contract_ids': [Command.set(contracts[index].ids)]})
        preliq.action_generate(); assert preliq.line_ids and preliq.estimated_return_usd > 0
    env.invalidate_all()
    assert estimates[0].estimate_line_ids.step_received_kg == 3000
    assert estimates[1].estimate_line_ids.step_received_kg == 1000
    assert outputs[0].step_tag_state == 'liquidated' and outputs[1].step_tag_state == 'validated'
    manifest = {'version': 1, 'company_id': company.id, 'created_on': str(today), 'records': records,
        'summary': {'productores': 2, 'fundos': 2, 'estimaciones': 3, 'contratos': 2, 'tarifas': 2,
                    'recepciones_fruta': 2, 'ot_packing': 2, 'preliquidaciones': 2,
                    'liquidaciones_productor': 2, 'embarques_liquidados': 1},
        'expected': {'export_kg': 12000, 'received_process_kg': 3000, 'received_packed_kg': 1000,
                     'packing_export_kg': 800, 'packing_loss_kg': 200,
                     'receiver_fob_usd': 2170, 'producer_net_usd': 1833}}
    env['ir.config_parameter'].sudo().set_param(MARKER, json.dumps(manifest))
    return verify_manifest(env, manifest)
