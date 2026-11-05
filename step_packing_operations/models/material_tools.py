"""Shared native stock allocation and transfer for Packing operations."""
from collections import defaultdict
from odoo import _
from odoo.exceptions import UserError, ValidationError
from odoo.tools.float_utils import float_compare


def create_stock_transfer(record, warehouse, source, dest, lines):
    """lines: list of (product, qty, source_package_or_False, result_package_or_False)."""
    record.ensure_one()
    grouped = {}
    for line in lines:
        product, qty, src_pkg, dst_pkg = line[:4]
        grouped.setdefault(product, 0.0)
        grouped[product] += qty
    picking = record.env["stock.picking"].create({
        "picking_type_id": warehouse.int_type_id.id,
        "company_id": record.company_id.id,
        "origin": record.name,
        "location_id": source.id,
        "location_dest_id": dest.id,
        "move_ids": [(0, 0, {
            "name": product.display_name, "product_id": product.id,
            "product_uom_qty": qty, "product_uom": product.uom_id.id,
            "location_id": source.id, "location_dest_id": dest.id,
            **record._packing_move_extra_values(product, qty, source, dest, lines),
        }) for product, qty in grouped.items()],
    })
    picking.action_confirm()
    # Remove any generic allocation before assigning the exact packages.
    picking.do_unreserve()
    for line in lines:
        product, qty, src_pkg, dst_pkg = line[:4]
        lot, owner = line[4:] if len(line) == 6 else (False, False)
        move = picking.move_ids.filtered(lambda row: row.product_id == product)
        if len(move) != 1:
            raise ValidationError(_("No se encontró un movimiento único para %s.") % product.display_name)
        record.env["stock.move.line"].create({
            "move_id": move.id, "picking_id": picking.id,
            "product_id": product.id, "product_uom_id": product.uom_id.id,
            "quantity": qty, "location_id": source.id, "location_dest_id": dest.id,
            "package_id": src_pkg.id if src_pkg else False,
            "result_package_id": dst_pkg.id if dst_pkg else False,
            "lot_id": lot.id if lot else False,
            "owner_id": owner.id if owner else False,
        })
    picking.button_validate()
    if picking.state != "done":
        raise UserError(_("No se pudo completar el movimiento de Packing en Inventario."))
    return picking


def allocate_stock(record, source, lines, allow_shortage=False):
    if record._name == 'step.packing.production':
        fruit_products = (record.raw_product_id | record.step_packing_input_tag_ids.step_tag_line_ids.product_id
                          | record.step_packing_output_tag_ids.step_tag_line_ids.product_id)
    else:
        fruit_products = record.line_ids.product_id
    if source.usage == 'internal':
        allocated = defaultdict(float)
        exact = []
        for line in lines:
            product, qty, package, result = line[:4]
            domain = [('product_id', '=', product.id), ('location_id', '=', source.id),
                      ('package_id', '=', package.id if package else False), ('quantity', '>', 0),
                      ('company_id', '=', record.company_id.id)]
            if len(line) == 6:
                domain += [('lot_id', '=', line[4].id if line[4] else False),
                           ('owner_id', '=', line[5].id if line[5] else False)]
            elif not package:
                domain.append(('owner_id', '=', False))
            quants = record.env['stock.quant'].search(domain, order='in_date, id')
            if quants:
                record.env.cr.execute('SELECT id FROM stock_quant WHERE id IN %s ORDER BY id FOR UPDATE', [tuple(sorted(quants.ids))])
                quants.invalidate_recordset()
            remaining = qty
            for quant in quants:
                take = min(remaining, max(0, quant.quantity - quant.reserved_quantity - allocated[quant.id]))
                if take <= 0:
                    continue
                allocated[quant.id] += take
                exact.append((product, take, package, result, quant.lot_id, quant.owner_id))
                remaining -= take
                if float_compare(remaining, 0, precision_rounding=product.uom_id.rounding) <= 0:
                    break
            if float_compare(remaining, 0, precision_rounding=product.uom_id.rounding) > 0:
                if allow_shortage and not package and not result and product not in fruit_products:
                    if product.with_company(record.company_id).standard_price <= 0:
                        raise UserError(_('Ingrese un costo mayor a cero para consumir sin stock: %s.') % product.display_name)
                    if not product.is_storable or product.tracking != 'none':
                        raise UserError(_('El consumo sin stock requiere un material inventariable sin seguimiento por lote o serie: %s.') % product.display_name)
                    exact.append((product, remaining, False, False, False, False))
                    continue
                raise UserError(_('Stock libre insuficiente de %(product)s en %(location)s. '
                                  'Cantidad requerida: %(required)s %(unit)s; faltante: %(missing)s. '
                                  'Revise el stock de esta ubicación y sus reservas.') % {
                                      'product': product.display_name, 'location': source.display_name,
                                      'required': qty, 'missing': remaining, 'unit': product.uom_id.display_name})
        lines = exact
    return lines


def material_recipe(tag, detail, company, order=None):
    product, quantity = detail.product_id, detail.quantity
    if order:
        raw = order.raw_product_id | order.step_packing_input_tag_ids.step_tag_line_ids.product_id
        if product in raw:
            product = ((tag.step_packaging_id.product_id - raw) or (order.product_id - raw) or
                       (order.step_packing_output_tag_ids.filtered(
                           lambda row: row.step_tag_kind == 'E' and row.step_packing_result == 'export'
                       ).step_tag_line_ids.product_id - raw))
            if len(product) != 1 or detail.boxes <= 0:
                raise UserError(_('Identifique el producto terminado y las cajas de la tarja %s.') % tag.name)
            quantity = detail.boxes
    bom = (order.bom_id if order and order.bom_id.product_tmpl_id == product.product_tmpl_id
           and (not order.bom_id.product_id or order.bom_id.product_id == product)
           else tag.env['mrp.bom']._bom_find(product, company_id=company.id).get(product))
    if not bom:
        raise UserError(_('Configure una lista de materiales para %s.') % product.display_name)
    return bom, product, quantity


def component_quantities(bom, product, quantity, pallet_share, include_boxes=True, include_pallet=True):
    factor = product.uom_id._compute_quantity(quantity, bom.product_uom_id) / bom.product_qty
    for component in bom.bom_line_ids:
        if component._skip_bom_line(product):
            continue
        quantity = ((component.product_qty * factor if include_boxes else 0) +
                    (component.step_export_qty_per_pallet * pallet_share if include_pallet else 0))
        quantity = component.product_uom_id._compute_quantity(quantity, component.product_id.uom_id)
        if quantity < 0:
            raise ValidationError(_('La matriz de materiales no admite consumos negativos.'))
        if quantity:
            yield component.product_id, quantity
