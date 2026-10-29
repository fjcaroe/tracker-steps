"""Original type APIs backed by the actual OCA structure/type relationship."""
from odoo import api, fields, models


class _StructureCounter(fields.Integer):
    # The pinned official Environment.cache_key consults field.context for
    # active_test. Integer has no such attribute; keep the mapping local to
    # this field, without changing Odoo's default Integer or registry factory.
    context = {}


class Structure(models.Model):
    _inherit = "hr.payroll.structure"

    schedule_pay = fields.Selection(related="type_id.default_schedule_pay", readonly=True, compute_sudo=False)


class StructureType(models.Model):
    _inherit = "hr.payroll.structure.type"

    struct_ids = fields.One2many("hr.payroll.structure", "type_id", string="Structures")
    struct_type_count = _StructureCounter(compute="_step_compute_structure_count", compute_sudo=False)

    @api.depends("struct_ids", "struct_ids.active")
    @api.depends_context("uid", "company", "allowed_company_ids", "active_test")
    def _step_compute_structure_count(self):
        # The real inverse relation applies normal company/country/record ACL.
        # No SQL shadow relation, sudo aggregate or historical payroll read.
        for kind in self:
            kind.struct_type_count = len(kind.struct_ids)
