from zoneinfo import ZoneInfo

from odoo import fields, models

DEFAULT_TIMEZONE = 'America/Santiago'


class ResCompany(models.Model):
    _inherit = 'res.company'

    # Las credenciales de servicio de Tracker las leía cualquier usuario interno (res.company es
    # legible por todos). Solo el administrador las necesita; el resto de los procesos corre con sudo.
    step_tracker_username = fields.Char(groups='base.group_system')
    step_tracker_password = fields.Char(groups='base.group_system')

    def _step_operation_zone(self):
        """Zona horaria de la operación: la del contacto de la compañía; si falta, la del usuario y,
        por último, la de Chile continental."""
        self.ensure_one()
        name = self.sudo().partner_id.tz or self.env.user.tz or DEFAULT_TIMEZONE
        try:
            return ZoneInfo(name)
        except Exception:  # zona desconocida en este servidor
            return ZoneInfo(DEFAULT_TIMEZONE)
