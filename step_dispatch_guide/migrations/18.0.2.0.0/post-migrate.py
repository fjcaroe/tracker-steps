"""18.0.2.0.0: el chofer pasa a ser un contacto (diseño, nota 1 del Anexo 1).

Por cada guía que usaba el maestro anterior step.dispatch.driver se busca un
contacto con el mismo RUT o se crea uno marcado como chofer. Los transportistas
ya usados en guías quedan marcados como "Transporte de carga" para que sigan
apareciendo al elegirlos.
"""
import logging

from odoo import SUPERUSER_ID, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"].with_context(active_test=False)
    guides = env["step.dispatch.guide"].search([("driver_id", "!=", False), ("driver_partner_id", "=", False)])
    for driver in guides.driver_id:
        partner = Partner.search([("vat", "=", driver.vat)], limit=1) if driver.vat else Partner
        if not partner:
            vals = {"name": driver.name, "phone": driver.phone, "step_chofer": True,
                    "company_id": driver.company_id.id}
            try:
                with cr.savepoint():
                    partner = Partner.create(dict(vals, vat=driver.vat))
            except ValidationError:
                partner = Partner.create(dict(vals, comment=f"RUT registrado en la guía: {driver.vat}"))
        partner.step_chofer = True
        guides.filtered(lambda g: g.driver_id == driver).driver_partner_id = partner
        _logger.info("Guías: chofer %s migrado al contacto %s", driver.name, partner.id)
    carriers = env["step.dispatch.guide"].search([]).carrier_id.filtered(lambda p: not p.step_carga)
    carriers.write({"step_carga": True})
    _logger.info("Guías: %s transportistas marcados como transporte de carga", len(carriers))
