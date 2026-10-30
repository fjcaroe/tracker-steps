"""Admission around the real LGPL contract-advantage engine, not native aliases."""
from math import isfinite

from odoo import api, models, _
from odoo.exceptions import UserError, ValidationError
from odoo.addons.step_payroll_contracts.history import assert_mutable


ADVANTAGE_FIELDS = ['contract_id', 'advantage_template_id', 'amount']
TEMPLATE_FIELDS = ['code', 'lower_bound', 'upper_bound']
CONTRACT_FIELDS = ['company_id', 'employee_id', 'advantages_ids']


def _read(records, names):
    records.check_access('read')
    records.check_field_access_rights('read', names)
    return records


def _links(records, values=None):
    """Check old and proposed real references using the caller's normal UID."""
    records = records.sudo(False)
    values = values or {}
    contracts = records.env['hr.contract']
    templates = records.env['hr.contract.advantage.template']
    if records:
        _read(records, ADVANTAGE_FIELDS)
        contracts |= records.contract_id
        templates |= records.advantage_template_id
    if values.get('contract_id'):
        contracts |= contracts.browse(values['contract_id'])
    if values.get('advantage_template_id'):
        templates |= templates.browse(values['advantage_template_id'])
    _read(contracts, CONTRACT_FIELDS)
    _read(templates, TEMPLATE_FIELDS)
    if contracts.exists() != contracts or templates.exists() != templates:
        raise UserError(_('Select existing original contract advantage references.'))
    if any(contract.company_id not in records.env.companies for contract in contracts):
        raise UserError(_('Contract advantages require an authorized original company.'))
    return records


class AdvantageTemplate(models.Model):
    _inherit = 'hr.contract.advantage.template'

    @api.model_create_multi
    def create(self, values_list):
        normal = self.sudo(False)
        normal.check_access('create')
        for values in values_list:
            normal.check_field_access_rights('write', list(values))
        return super(AdvantageTemplate, normal).create(values_list)

    def write(self, values):
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        return super(AdvantageTemplate, normal).write(values)

    def unlink(self):
        normal = self.sudo(False)
        normal.check_access('unlink')
        rows = normal.env['hr.contract.advantage'].with_context(active_test=False)
        _read(rows, ['advantage_template_id'])
        rows.flush_model(['advantage_template_id'])
        normal.env.cr.execute('SELECT id FROM hr_contract_advantage WHERE advantage_template_id=ANY(%s)', (normal.ids,))
        used = rows.browse([row[0] for row in normal.env.cr.fetchall()])
        _read(used, ['advantage_template_id'])
        if used:
            raise UserError(_('An actual contract advantage still uses this template; preserve its original reference.'))
        return super(AdvantageTemplate, normal).unlink()

    def read(self, fields=None, load='_classic_read'):
        normal = self.sudo(False)
        normal.check_access('read')
        normal.check_field_access_rights('read', fields)
        return super(AdvantageTemplate, normal).read(fields=fields, load=load)

    def copy_data(self, default=None):
        normal = self.sudo(False)
        _read(normal, [name for name, field in normal._fields.items() if field.copy and field.store])
        return super(AdvantageTemplate, normal).copy_data(default=default)

    def copy(self, default=None):
        normal = self.sudo(False)
        _read(normal, [name for name, field in normal._fields.items() if field.copy and field.store])
        return super(AdvantageTemplate, normal).copy(default=default)


class Advantage(models.Model):
    _inherit = 'hr.contract.advantage'

    @api.model_create_multi
    def create(self, values_list):
        normal = self.sudo(False)
        normal.check_access('create')
        for values in values_list:
            normal.check_field_access_rights('write', list(values))
            _links(normal, values)
            if not values.get('contract_id') or not values.get('advantage_template_id'):
                raise UserError(_('Select an actual contract and advantage template before creating its value.'))
        with normal.env.cr.savepoint():
            return super(Advantage, normal).create(values_list)

    def write(self, values):
        normal = self.sudo(False)
        normal.check_access('write')
        normal.check_field_access_rights('write', list(values))
        _links(normal, values)
        if any(name in values and not values[name] for name in ('contract_id', 'advantage_template_id')):
            raise UserError(_('An existing contract advantage must retain its real references.'))
        with normal.env.cr.savepoint():
            return super(Advantage, normal).write(values)

    def unlink(self):
        normal = self.sudo(False)
        normal.check_access('unlink')
        _links(normal)
        return super(Advantage, normal).unlink()

    def read(self, fields=None, load='_classic_read'):
        normal = self.sudo(False)
        normal.check_access('read')
        normal.check_field_access_rights('read', fields)
        return super(Advantage, normal).read(fields=fields, load=load)

    def copy_data(self, default=None):
        normal = self.sudo(False)
        _links(normal)
        _read(normal, [name for name, field in normal._fields.items() if field.copy and field.store])
        return super(Advantage, normal).copy_data(default=default)

    def copy(self, default=None):
        normal = self.sudo(False)
        _links(normal, default)
        _read(normal, [name for name, field in normal._fields.items() if field.copy and field.store])
        return super(Advantage, normal).copy(default=default)

    @api.constrains('amount', 'advantage_template_id', 'contract_id')
    def _step_check_advantage_limits(self):
        normal = _links(self)
        for row in normal:
            if not row.contract_id or not row.advantage_template_id:
                raise ValidationError(_('Contract advantages require their actual contract and template.'))
            lower, upper = row.advantage_template_id.lower_bound, row.advantage_template_id.upper_bound
            if not all(isfinite(value) for value in (row.amount, lower, upper)) or lower > upper:
                raise ValidationError(_('Contract advantage amounts and ordered limits must be finite.'))
            # Preserve OCA's explicit zero exemption; a zero is not missing.
            if row.amount and not lower <= row.amount <= upper:
                raise ValidationError(_('The contract advantage amount is outside its real template limits.'))


class Payslip(models.Model):
    _inherit = 'hr.payslip'

    def _step_check_contract_advantages(self):
        normal = self.sudo(False)
        names = ['state', 'employee_id', 'company_id', 'contract_id', 'date_from', 'date_to']
        names += [name for name in ('paid', 'step_history_locked') if name in normal._fields]
        _read(normal, names)
        assert_mutable(normal)
        result = {}
        for slip in normal:
            contracts = _read(slip._get_employee_contracts(), CONTRACT_FIELDS)
            if not contracts or any(type(ident) is not int for ident in contracts.ids):
                raise UserError(_('Select the actual saved contracts before reading advantage values.'))
            if any(contract.company_id != slip.company_id for contract in contracts):
                raise UserError(_('Contract advantages must use the payslip original company.'))
            rows = normal.env['hr.contract.advantage'].with_context(active_test=False)
            _read(rows, ADVANTAGE_FIELDS)
            rows.flush_model(ADVANTAGE_FIELDS)
            normal.env.cr.execute('SELECT id,contract_id,advantage_template_id,amount '
                'FROM hr_contract_advantage WHERE contract_id=ANY(%s) ORDER BY id', (contracts.ids,))
            physical = normal.env.cr.fetchall()
            complete = rows.browse([row[0] for row in physical])
            _read(complete, ADVANTAGE_FIELDS)
            templates = _read(complete.advantage_template_id, TEMPLATE_FIELDS)
            templates.flush_recordset(TEMPLATE_FIELDS)
            normal.env.cr.execute('SELECT id,code,lower_bound,upper_bound FROM hr_contract_advantage_template '
                'WHERE id=ANY(%s) ORDER BY id', (templates.ids,))
            original_templates = {row[0]: row[1:] for row in normal.env.cr.fetchall()}
            seen = set()
            for ident, contract_id, template_id, amount in physical:
                original = original_templates.get(template_id)
                if amount is None or original is None or any(value is None for value in original):
                    raise UserError(_('Original contract advantage values or limits are missing; no zero will be invented.'))
                code, lower, upper = original
                if not code or not code.strip() or (contract_id, code) in seen:
                    raise UserError(_('Contract advantage codes must be present and unambiguous per actual contract.'))
                seen.add((contract_id, code))
                if not all(isfinite(value) for value in (amount, lower, upper)) or lower > upper:
                    raise UserError(_('Original contract advantage amounts and ordered limits must be finite.'))
                if amount and not lower <= amount <= upper:
                    raise UserError(_('Original contract advantage amount is outside its actual template limits.'))
            result[slip.id] = contracts
        return result

    def get_current_contract_dict(self, contract, contracts):
        normal = self.sudo(False)
        normal.ensure_one()
        selected = normal._step_check_contract_advantages()[normal.id]
        requested = _read(contracts.with_env(normal.env), CONTRACT_FIELDS)
        chosen = _read(contract.with_env(normal.env), CONTRACT_FIELDS)
        if set(requested.ids) != set(selected.ids) or len(chosen) != 1 or chosen not in requested:
            raise UserError(_('Use only the payslip actual selected contracts for advantage calculation.'))
        # The actual OCA module creates its BrowsableObject. No replacement
        # dictionary, fabricated advantage, alias or salary model is supplied.
        return super(Payslip, normal).get_current_contract_dict(chosen, requested)

    def compute_sheet(self):
        normal = self.sudo(False)
        normal._step_check_contract_advantages()
        with normal.env.cr.savepoint():
            return super(Payslip, normal).compute_sheet()

    def action_payslip_done(self):
        normal = self.sudo(False)
        normal._step_check_contract_advantages()
        with normal.env.cr.savepoint():
            return super(Payslip, normal).action_payslip_done()


class Contract(models.Model):
    _inherit = 'hr.contract'

    def unlink(self):
        normal = self.sudo(False)
        normal.check_access('unlink')
        _read(normal, CONTRACT_FIELDS)
        rows = normal.env['hr.contract.advantage'].with_context(active_test=False)
        _read(rows, ['contract_id'])
        rows.flush_model(['contract_id'])
        normal.env.cr.execute('SELECT id FROM hr_contract_advantage WHERE contract_id=ANY(%s)', (normal.ids,))
        used = rows.browse([row[0] for row in normal.env.cr.fetchall()])
        _read(used, ['contract_id'])
        if used:
            raise UserError(_('An actual contract advantage still uses this contract; preserve its original reference.'))
        return super(Contract, normal).unlink()
