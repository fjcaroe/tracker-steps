"""Reuse the four agricultural masters; no new season/species/variety tables."""
from odoo import api, Command, fields, models, _
from odoo.exceptions import ValidationError
from odoo.models import to_company_ids
from odoo.tools.misc import unquote

CATALOGS = ('step.temporada', 'step.especie', 'step.variedad', 'step.grupo.variedad')
_INSTALL_SCOPE = object()


class CatalogCompanyMixin(models.AbstractModel):
    _name = 'step.agriculture.catalog.company.mixin'
    _description = 'Empresas habilitadas para un maestro agrícola'

    company_ids = fields.Many2many(
        'res.company', string='Empresas', default=lambda self: self.env.company,
        help='Vacío: compartido con todas las empresas de esta base. Seleccione una o varias para restringirlo.',
    )

    def _auto_init(self):
        relation = self._fields['company_ids'].relation
        self.env.cr.execute('SELECT to_regclass(%s),to_regclass(%s)', (self._table, relation))
        table_exists, relation_exists = self.env.cr.fetchone()
        if table_exists and not relation_exists:
            self.env.cr.execute('CREATE TEMP TABLE steps_catalog_scope_' + self._table +
                                ' ON COMMIT DROP AS SELECT id,company_id FROM ' + self._table)
        return super()._auto_init()

    @api.depends('company_ids')
    def _compute_legacy_company(self):
        for record in self:
            record.company_id = record.company_ids if len(record.company_ids) == 1 else False

    @api.model
    def _check_company_domain(self, companies):
        ids = companies if isinstance(companies, unquote) else to_company_ids(companies)
        return ['|', ('company_ids', '=', False), ('company_ids', 'in', ids)]

    @api.model_create_multi
    def create(self, values_list):
        prepared = []
        for values in values_list:
            values = dict(values)
            if 'company_id' in values:
                company = values.pop('company_id')
                values.setdefault('company_ids', [Command.set([company] if company else [])])
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        values = dict(values)
        if 'company_id' in values:
            company = values.pop('company_id')
            values.setdefault('company_ids', [Command.set([company] if company else [])])
        result = super().write(values)
        if 'company_ids' in values and self.env.context.get('_install_scope') is not _INSTALL_SCOPE:
            for model, field in (('step.variedad', 'especie_id'), ('step.variedad', 'grupo_variedad_id'), ('step.grupo.variedad', 'especie_id')):
                if self._name == self.env[model]._fields[field].comodel_name:
                    self.env[model].sudo().search([(field, 'in', self.ids)])._check_catalog_scope()
        return result

    @api.constrains('company_ids')
    def _check_catalog_scope(self):
        if self.env.context.get('_install_scope') is _INSTALL_SCOPE:
            return
        for record in self:
            for field in ('especie_id', 'grupo_variedad_id'):
                if field not in record._fields:
                    continue
                parent = record[field]
                if parent.company_ids and (not record.company_ids or record.company_ids - parent.company_ids):
                    raise ValidationError(_('Las empresas de la variedad o grupo deben estar incluidas en las de su especie y grupo.'))


class Season(models.Model):
    _name = 'step.temporada'
    _inherit = ['step.temporada', 'step.agriculture.catalog.company.mixin']
    company_id = fields.Many2one(required=False, compute='_compute_legacy_company', store=True, readonly=True)


class Species(models.Model):
    _name = 'step.especie'
    _inherit = ['step.especie', 'step.agriculture.catalog.company.mixin']
    company_id = fields.Many2one(required=False, compute='_compute_legacy_company', store=True, readonly=True)


class Variety(models.Model):
    _name = 'step.variedad'
    _inherit = ['step.variedad', 'step.agriculture.catalog.company.mixin']
    company_id = fields.Many2one(required=False, compute='_compute_legacy_company', store=True, readonly=True)

    @api.constrains('especie_id', 'grupo_variedad_id')
    def _check_variety_relations(self):
        self._check_catalog_scope()


class VarietyGroup(models.Model):
    _name = 'step.grupo.variedad'
    _inherit = ['step.grupo.variedad', 'step.agriculture.catalog.company.mixin']
    company_id = fields.Many2one(required=False, compute='_compute_legacy_company', store=True, readonly=True)

    @api.constrains('especie_id')
    def _check_species_relation(self):
        self._check_catalog_scope()
