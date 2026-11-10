"""Company templates and review rows for the external reception wizard."""
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


RECEPTION_COLUMNS = [
    ('folio', 'Referencia de recepción'),
    ('guide', 'Número de guía'),
    ('tag', 'Número de tarja'),
    ('date', 'Fecha prevista'),
    ('species', 'Especie'),
    ('variety', 'Variedad'),
    ('producer', 'Productor o fundo'),
    ('packaging', 'Embalaje'),
    ('boxes', 'Cantidad de embalajes'),
    ('kilos', 'Peso neto kg'),
    ('kind', 'Tipo de recepción de fruta'),
    ('fruit_type', 'Tipo de fruta'),
    ('gassed', 'Fruta gasificada'),
    ('chilled', 'Fruta con frío'),
    ('palletized', 'Fruta palletizada'),
    ('classification', 'Clasificación'),
]


class ExternalReceptionTemplate(models.Model):
    _name = 'step.external.fruit.reception.template'
    _description = 'Plantilla de importación de recepciones de fruta'
    _check_company_auto = True
    _order = 'name, id'

    name = fields.Char(required=True)
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    picking_type_id = fields.Many2one('stock.picking.type', required=True, check_company=True)
    packing_id = fields.Many2one('res.partner', required=True, check_company=True)
    season_id = fields.Many2one('step.temporada', required=True)
    product_id = fields.Many2one('product.product', required=True, check_company=True)
    category_id = fields.Many2one('step.management.fruit.category', required=True)
    fruit_class_id = fields.Many2one('step.management.fruit.class', required=True)
    columns = fields.Json()
    alias_ids = fields.One2many('step.external.fruit.reception.template.alias', 'template_id')
    _sql_constraints = [
        ('reception_template_company_name', 'unique(company_id, name)', 'Ya existe una plantilla con ese nombre.'),
    ]


    def _remember_aliases(self, values):
        self.ensure_one()
        self.env.cr.execute('SELECT id FROM step_external_fruit_reception_template WHERE id=%s FOR UPDATE', [self.id])
        self.invalidate_recordset(['alias_ids'])
        existing = {(alias.kind, alias.source_key): alias for alias in self.alias_ids}
        alias_model = self.env['step.external.fruit.reception.template.alias']
        for item in values:
            alias = existing.get((item['kind'], item['source_key']))
            if alias:
                alias.write(item)
            else:
                alias_model.create(dict(item, template_id=self.id))


class ExternalReceptionTemplateAlias(models.Model):
    _name = 'step.external.fruit.reception.template.alias'
    _description = 'Equivalencia guardada de recepción de fruta'
    _check_company_auto = True

    template_id = fields.Many2one('step.external.fruit.reception.template', required=True, ondelete='cascade')
    company_id = fields.Many2one(related='template_id.company_id', store=True)
    source = fields.Char(required=True)
    source_key = fields.Char(required=True)
    kind = fields.Selection([('producer', 'Productor'), ('packaging', 'Embalaje de recepción'),
                             ('process_packaging', 'Embalaje de proceso'), ('process_caliber', 'Calibre de proceso')],
                            required=True)
    fundo_id = fields.Many2one('step.fundo', ondelete='restrict')
    packaging_id = fields.Many2one('product.packaging', check_company=True, ondelete='restrict')
    caliber_id = fields.Many2one('step.management.fruit.caliber', ondelete='restrict')
    _sql_constraints = [
        ('reception_template_alias_unique', 'unique(template_id, kind, source_key)', 'La equivalencia ya existe.'),
    ]

    @api.constrains('kind', 'fundo_id', 'packaging_id', 'caliber_id')
    def _check_target(self):
        fields_by_kind = {'producer': 'fundo_id', 'packaging': 'packaging_id',
                          'process_packaging': 'packaging_id', 'process_caliber': 'caliber_id'}
        for alias in self:
            targets = [field for field in ('fundo_id', 'packaging_id', 'caliber_id') if alias[field]]
            if targets != [fields_by_kind[alias.kind]]:
                raise ValidationError(_('Seleccione el maestro correspondiente al tipo de equivalencia.'))


class ExternalReceptionColumn(models.TransientModel):
    _name = 'step.external.fruit.reception.column'
    _description = 'Columna del Excel de recepciones'
    _order = 'position'

    wizard_id = fields.Many2one('step.external.fruit.reception.import', required=True, ondelete='cascade')
    position = fields.Integer(required=True)
    source = fields.Char(required=True)
    source_key = fields.Char(required=True)
    target = fields.Selection(RECEPTION_COLUMNS, string='Campo de Odoo')


class ExternalReceptionAlias(models.TransientModel):
    _name = 'step.external.fruit.reception.alias'
    _description = 'Equivalencia de nombres en el Excel de recepciones'
    _order = 'kind, source'

    wizard_id = fields.Many2one('step.external.fruit.reception.import', required=True, ondelete='cascade')
    product_id = fields.Many2one(related='wizard_id.product_id')
    source = fields.Char(required=True)
    kind = fields.Selection([('producer', 'Productor'), ('packaging', 'Embalaje')], required=True)
    fundo_id = fields.Many2one('step.fundo')
    packaging_id = fields.Many2one('product.packaging', domain="[('product_id', '=', product_id)]")
