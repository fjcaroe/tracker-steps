from odoo import models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def _step_matches_shared_stock_farm(self, farm, company):
        if not self or not farm or not company:
            return False
        producer = self.sudo()
        master = farm.sudo()
        # The contact keeps its owning branch. Only the fruit of this expressly
        # assigned farm can use it as an inventory owner in the receiving branch.
        if (not producer.is_productor or not producer.company_id
                or producer.company_id.root_id != company.sudo().root_id
                or master.partner_id != producer or company not in master.company_ids):
            return False
        return self.env.su or (
            company in self.env.companies and farm.has_access('read') and self.has_access('read'))


def _check_stock_company(records, fnames, field, matches, native_check):
    # Odoo expands either company field to the whole set of relational fields.
    names = records._fields if fnames is None or {'company_id', 'company_ids'}.intersection(fnames) else fnames
    if field not in names:
        return native_check(records, fnames)
    permitted = records.filtered(matches)
    if permitted:
        native_check(permitted, [name for name in names if name not in (field, 'company_id', 'company_ids')])
    return native_check(records - permitted, fnames)


class Picking(models.Model):
    _inherit = 'stock.picking'

    def _check_company(self, fnames=None):
        return _check_stock_company(self, fnames, 'partner_id',
            lambda picking: picking.step_fruit_reception_kind == 'process'
                and picking.picking_type_code == 'incoming'
                and picking.partner_id._step_matches_shared_stock_farm(picking.fruit_fundo_id, picking.company_id),
            lambda records, names: super(Picking, records)._check_company(names))


def _owner_matches_package(record, package):
    receipt = package.step_process_reception_id
    return (receipt and receipt.step_fruit_reception_kind == 'process'
            and receipt.company_id == record.company_id and package.fundo_id == receipt.fruit_fundo_id
            and record.owner_id._step_matches_shared_stock_farm(package.fundo_id, record.company_id))


class MoveLine(models.Model):
    _inherit = 'stock.move.line'

    def _check_company(self, fnames=None):
        return _check_stock_company(self, fnames, 'owner_id',
            lambda line: any(_owner_matches_package(line, package)
                for package in line.package_id | line.result_package_id),
            lambda records, names: super(MoveLine, records)._check_company(names))


class Quant(models.Model):
    _inherit = 'stock.quant'

    def _check_company(self, fnames=None):
        return _check_stock_company(self, fnames, 'owner_id',
            lambda quant: _owner_matches_package(quant, quant.package_id),
            lambda records, names: super(Quant, records)._check_company(names))
