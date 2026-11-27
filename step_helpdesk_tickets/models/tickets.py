from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HelpdeskStage(models.Model):
    _name = "helpdesk.stage"
    _description = "Etapa de soporte"
    _auto = False
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer()
    fold = fields.Boolean(string="Etapa de cierre")
    team_ids = fields.Many2many("helpdesk.team", "team_stage_rel", "helpdesk_stage_id", "helpdesk_team_id",
                                string="Equipos", required=True)


class HelpdeskTag(models.Model):
    _name = "helpdesk.tag"
    _description = "Etiqueta de soporte"
    _auto = False
    _order = "name"

    name = fields.Char(required=True, translate=True)
    color = fields.Integer()


class HelpdeskTeam(models.Model):
    _name = "helpdesk.team"
    _inherit = ["mail.thread"]
    _description = "Equipo de soporte"
    _auto = False
    _order = "sequence,name"

    name = fields.Char(required=True, translate=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer()
    company_id = fields.Many2one("res.company", string="Compañía")
    member_ids = fields.Many2many("res.users", "helpdesk_team_res_users_rel", "helpdesk_team_id", "res_users_id",
                                  string="Miembros", required=True)
    stage_ids = fields.Many2many("helpdesk.stage", "team_stage_rel", "helpdesk_team_id", "helpdesk_stage_id",
                                 string="Etapas")
    privacy_visibility = fields.Selection([("invited_internal", "Personal invitado"),
            ("internal", "Personal interno"), ("portal", "Personal y portal")], string="Visibilidad")
    is_published = fields.Boolean()
    website_published = fields.Boolean(related="is_published")


class HelpdeskTicket(models.Model):
    _name = "helpdesk.ticket"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Ticket de soporte"
    _auto = False
    _order = "priority desc, id desc"

    name = fields.Char(string="Asunto", required=True)
    description = fields.Html(string="Descripción")
    active = fields.Boolean(default=True)
    ticket_ref = fields.Char(string="Número", readonly=True, copy=False)
    team_id = fields.Many2one("helpdesk.team", string="Equipo")
    team_privacy_visibility = fields.Selection(related="team_id.privacy_visibility")
    company_id = fields.Many2one("res.company", related="team_id.company_id", store=True)
    stage_id = fields.Many2one("helpdesk.stage", string="Etapa", ondelete="restrict", tracking=True)
    user_id = fields.Many2one("res.users", string="Responsable")
    partner_id = fields.Many2one("res.partner", string="Contacto")
    tag_ids = fields.Many2many("helpdesk.tag", "helpdesk_tag_helpdesk_ticket_rel", "helpdesk_ticket_id", "helpdesk_tag_id",
                               string="Etiquetas")
    priority = fields.Selection([("0", "Baja"), ("1", "Media"), ("2", "Alta"), ("3", "Urgente")],
                                string="Prioridad", default="0")
    kanban_state = fields.Selection([("normal", "En curso"), ("done", "Listo"), ("blocked", "Bloqueado")],
                                    required=True, default="normal")
    assign_date = fields.Datetime(string="Fecha de asignación", readonly=True)
    close_date = fields.Datetime(string="Fecha de cierre", readonly=True)
    date_last_stage_update = fields.Datetime(string="Último cambio de etapa", readonly=True)

    @api.onchange("team_id")
    def _onchange_team_stage(self):
        if self.team_id and self.stage_id not in self.team_id.stage_ids:
            self.stage_id = self.team_id.stage_ids.filtered("active").sorted(lambda stage: (stage.sequence, stage.id))[:1]

    @api.model_create_multi
    def create(self, vals_list):
        self.check_access("create")
        prepared = []
        for source in vals_list:
            values = dict(source)
            team = self.env["helpdesk.team"].browse(values.get("team_id"))
            if team:
                team.check_access("read")
                if not values.get("stage_id"):
                    values["stage_id"] = team.stage_ids.filtered("active").sorted(lambda stage: (stage.sequence, stage.id))[:1].id
            if not values.get("ticket_ref"):
                company = team.company_id or self.env.company
                values["ticket_ref"] = self.env["ir.sequence"].with_company(company).next_by_code("helpdesk.ticket")
                if not values["ticket_ref"]:
                    raise ValidationError(_("No hay una secuencia de tickets disponible para esta compañía."))
            if values.get("stage_id"):
                values.setdefault("date_last_stage_update", fields.Datetime.now())
            if values.get("user_id"):
                values.setdefault("assign_date", fields.Datetime.now())
            prepared.append(values)
        return super().create(prepared)

    def write(self, values):
        if "stage_id" not in values:
            return super().write(values)
        changed = self.filtered(lambda ticket: ticket.stage_id.id != values["stage_id"])
        if changed:
            now = fields.Datetime.now()
            stage = self.env["helpdesk.stage"].browse(values["stage_id"])
            super(HelpdeskTicket, changed).write(dict(values, date_last_stage_update=now,
                                                      close_date=now if stage.fold else False))
        other = self - changed
        return super(HelpdeskTicket, other).write(values) if other else True

    @api.model
    def _use_ticket_forms(self):
        for menu_name, action_name in (("my", "action_mine"), ("all", "action_all")):
            menu = self.env.ref("helpdesk.helpdesk_ticket_menu_" + menu_name)
            action = self.env.ref("step_helpdesk_tickets." + action_name)
            if menu.action != action:
                if menu.action._name != "ir.actions.act_window" or menu.action.res_model != self._name:
                    raise ValidationError(_("El menú de soporte apunta a una acción de otro modelo."))
                menu.write({"action": "ir.actions.act_window,%s" % action.id})
