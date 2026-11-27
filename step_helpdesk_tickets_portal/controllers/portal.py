from datetime import timedelta
from itertools import groupby as group_rows
from operator import itemgetter

from odoo import _, fields, http
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.osv import expression


MODEL = "helpdesk.ticket"


class StepsSupportPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "ticket_count" in counters:
            tickets = request.env[MODEL]
            values["ticket_count"] = tickets.search_count([]) if tickets.has_access("read") else 0
        return values

    @http.route(["/my/tickets", "/my/tickets/page/<int:page>"], type="http", auth="user", website=True, methods=["GET"])
    def tickets(self, page=1, sortby="create_date desc", filterby="all", groupby="none", search=None,
                search_in="name", steps_priority="all", steps_stage="0", steps_status="all", steps_assignment="all",
                steps_period="all", date_begin=None, date_end=None, **kwargs):
        tickets = request.env[MODEL]
        if not tickets.has_access("read"):
            return request.redirect("/my")
        values = self._prepare_portal_layout_values()
        sortings = {
            "create_date desc": _("Más recientes"), "create_date asc": _("Más antiguos"),
            "write_date desc": _("Última actualización"), "id desc": _("Número"),
            "priority desc, write_date desc": _("Prioridad"), "name": _("Asunto"),
            "stage_id": _("Etapa"), "user_id": _("Responsable"),
        }
        search_fields = {"name": _("Asunto"), "partner_id": _("Contacto"), "stage_id": _("Etapa"),
                         "team_id": _("Equipo"), "user_id": _("Responsable")}
        groups = {"none": _("Sin agrupar"), "kanban_state": _("Estado"), **{k: v for k, v in search_fields.items() if k != "name"}}
        today = fields.Date.context_today(tickets)
        filters = {"all": (_("Todos"), []), "open": (_("Abiertos"), [("stage_id.fold", "=", False)]),
                   "closed": (_("Cerrados"), [("stage_id.fold", "=", True)]),
                   "assigned": (_("Asignados"), [("user_id", "!=", False)]), "unassigned": (_("Sin asignar"), [("user_id", "=", False)]),
                   "unread": (_("Sin leer"), [("message_needaction", "=", True)]),
                   "recent7": (_("Últimos siete días"), [("create_date", ">=", today - timedelta(days=7))])}
        # The stage directory contains only stages represented in the user's visible tickets.
        stages = tickets.search([]).mapped("stage_id")
        for stage_record in stages:
            filters["stage_%s" % stage_record.id] = (stage_record.display_name, [("stage_id", "=", stage_record.id)])
        sortby = sortby if sortby in sortings else "create_date desc"
        filterby = filterby if filterby in filters else "all"
        groupby = groupby if groupby in groups else "none"
        search_in = search_in if search_in in search_fields else "name"
        parts = [filters[filterby][1]]
        if search:
            parts.append([(search_in, "ilike", search)])
        if steps_priority in ("0", "1", "2", "3"):
            parts.append([("priority", "=", steps_priority)])
        if str(steps_stage) in {str(value) for value in stages.ids}:
            parts.append([("stage_id", "=", int(steps_stage))])
        if steps_status in ("open", "closed"):
            parts.append(filters[steps_status][1])
        if steps_assignment in ("assigned", "unassigned"):
            parts.append(filters[steps_assignment][1])
        if steps_period in ("7", "30", "90"):
            parts.append([("create_date", ">=", today - timedelta(days=int(steps_period)))])
        for value, op, days in ((date_begin, ">=", 0), (date_end, "<", 1)):
            if value:
                try:
                    date = fields.Date.to_date(value) + timedelta(days=days)
                except (TypeError, ValueError, OverflowError):
                    continue
                parts.append([("create_date", op, date)])
        domain = expression.AND(parts)
        url_args = {"sortby": sortby, "filterby": filterby, "groupby": groupby, "search": search, "search_in": search_in,
                    "steps_priority": steps_priority, "steps_stage": steps_stage, "steps_status": steps_status,
                    "steps_assignment": steps_assignment, "steps_period": steps_period, "date_begin": date_begin, "date_end": date_end}
        pager = portal_pager(url="/my/tickets", total=tickets.search_count(domain), page=page, step=self._items_per_page,
                             url_args={k: v for k, v in url_args.items() if v})
        order = sortby if groupby == "none" else groupby + ", " + sortby
        rows = tickets.search(domain, order=order, limit=self._items_per_page, offset=pager["offset"])
        request.session["steps_ticket_history"] = rows.ids
        if groupby == "none":
            grouped = [(False, rows)]
        else:
            grouped = [(key, tickets.browse([r.id for r in records])) for key, records in group_rows(rows, itemgetter(groupby))]
        values.update(url_args, tickets=rows, grouped_tickets=grouped, groups=groups, search_fields=search_fields,
                      filters=filters, sortings=sortings, stages=stages, pager=pager, page_name="steps_tickets")
        return request.render("step_helpdesk_tickets_portal.ticket_list", values)

    @http.route(["/my/ticket/<int:ticket_id>", "/my/ticket/<int:ticket_id>/<access_token>",
                 "/helpdesk/ticket/<int:ticket_id>", "/helpdesk/ticket/<int:ticket_id>/<access_token>"],
                type="http", auth="public", website=True, methods=["GET"])
    def ticket(self, ticket_id, access_token=None, **kwargs):
        try:
            record = self._document_check_access(MODEL, ticket_id, access_token)
        except (AccessError, MissingError):
            return request.redirect("/my")
        values = self._get_page_view_values(record, access_token, {"ticket": record, "page_name": "steps_ticket"},
                                            "steps_ticket_history", False, **kwargs)
        return request.render("step_helpdesk_tickets_portal.ticket_detail", values)
