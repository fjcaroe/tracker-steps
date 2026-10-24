from datetime import timedelta
from operator import itemgetter

from odoo import fields, http
from odoo.addons.helpdesk.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.http import request
from odoo.osv.expression import AND
from odoo.tools import groupby as groupbyelem


class StepsCustomerPortal(CustomerPortal):
    """Keep the standard portal access rules while improving ticket navigation."""

    def _comment_activity(self, ticket_ids):
        if not ticket_ids:
            return {}
        comment_subtype = request.env.ref("mail.mt_comment")
        request.env.cr.execute(
            """
            SELECT res_id, MAX(id) AS latest_id,
                   MAX(id) FILTER (WHERE author_id IS DISTINCT FROM %s) AS incoming_id
              FROM mail_message
             WHERE model = 'helpdesk.ticket'
               AND res_id IN %s
               AND message_type = 'comment'
               AND subtype_id = %s
             GROUP BY res_id
            """,
            (request.env.user.partner_id.id, tuple(ticket_ids), comment_subtype.id),
        )
        return {
            row[0]: {"latest_id": row[1], "incoming_id": row[2]}
            for row in request.env.cr.fetchall()
        }

    def _seen_message_ids(self, ticket_ids):
        records = request.env["step.helpdesk.portal.seen"].sudo().search([
            ("user_id", "=", request.env.user.id),
            ("ticket_id", "in", ticket_ids),
        ])
        return {record.ticket_id.id: record.last_seen_message_id.id or 0 for record in records}

    def _prepare_my_tickets_values(self, page=1, date_begin=None, date_end=None,
                                   sortby=None, filterby="all", search=None,
                                   groupby="none", search_in="name"):
        values = self._prepare_portal_layout_values()
        Ticket = request.env["helpdesk.ticket"]
        visible_domain = self._prepare_helpdesk_tickets_domain()
        domain = visible_domain
        # Keep these independent of Odoo's single-choice searchbar filter so
        # visitors can combine them without changing the standard portal UI.
        args = request.httprequest.args
        selections = {
            "status": {"all", "open", "closed"},
            "period": {"all", "7", "30", "90"},
            "assignment": {"all", "assigned", "unassigned"},
        }
        selected = {
            key: args.get(f"steps_{key}", "all")
            for key in selections
        }
        selected = {
            key: value if value in selections[key] else "all"
            for key, value in selected.items()
        }
        sortings = {
            "create_date desc": {"label": "Creación: recientes"},
            "create_date asc": {"label": "Creación: antiguos"},
            "write_date desc": {"label": "Última modificación"},
            "priority desc, write_date desc": {"label": "Prioridad"},
            "id desc": {"label": "Referencia"},
            "name": {"label": "Asunto"},
            "user_id": {"label": "Asignado a"},
            "stage_id": {"label": "Etapa"},
        }
        filters = {
            "all": {"label": "Todos", "domain": []},
            "unread": {"label": "Con respuestas sin revisar", "domain": []},
            "open": {"label": "Abiertos", "domain": [("close_date", "=", False)]},
            "closed": {"label": "Cerrados", "domain": [("close_date", "!=", False)]},
            "recent7": {
                "label": "Modificados en 7 días",
                "domain": [("write_date", ">=", fields.Datetime.now() - timedelta(days=7))],
            },
            "assigned": {"label": "Asignados", "domain": [("user_id", "!=", False)]},
            "unassigned": {"label": "Sin asignar", "domain": [("user_id", "=", False)]},
        }
        # Stages come only from tickets this account may read.
        visible_stages = Ticket.search(domain).mapped("stage_id").sorted(lambda stage: (stage.sequence, stage.id))
        for stage in visible_stages:
            filters[f"stage_{stage.id}"] = {
                "label": f"Etapa: {stage.name}",
                "domain": [("stage_id", "=", stage.id)],
            }

        stage_ids = {stage.id for stage in visible_stages}
        try:
            selected_stage = int(args.get("steps_stage", "0"))
        except (TypeError, ValueError):
            selected_stage = 0
        if selected_stage not in stage_ids:
            selected_stage = 0
        priority_options = Ticket.fields_get(["priority"])["priority"]["selection"]
        priority_values = {value for value, _label in priority_options}
        selected_priority = args.get("steps_priority", "all")
        if selected_priority not in priority_values:
            selected_priority = "all"

        if sortby not in sortings:
            sortby = "create_date desc"
        if filterby not in filters:
            filterby = "all"
        inputs = dict(sorted(self._ticket_get_searchbar_inputs().items(), key=lambda item: item[1]["sequence"]))
        groupings = dict(sorted(self._ticket_get_searchbar_groupby().items(), key=lambda item: item[1]["sequence"]))
        if groupby not in groupings:
            groupby = "none"

        domain = AND([domain, filters[filterby]["domain"]])
        if selected["status"] != "all":
            domain = AND([domain, [("close_date", "=", False) if selected["status"] == "open" else ("close_date", "!=", False)]])
        if selected_stage:
            domain = AND([domain, [("stage_id", "=", selected_stage)]])
        if selected["period"] != "all":
            since = fields.Datetime.now() - timedelta(days=int(selected["period"]))
            domain = AND([domain, [("create_date", ">=", since)]])
        if selected_priority != "all":
            domain = AND([domain, [("priority", "=", selected_priority)]])
        if selected["assignment"] != "all":
            domain = AND([domain, [("user_id", "!=", False) if selected["assignment"] == "assigned" else ("user_id", "=", False)]])
        if date_begin and date_end:
            domain = AND([domain, [("create_date", ">", date_begin), ("create_date", "<=", date_end)]])
        if search and search_in:
            domain = AND([domain, self._ticket_get_search_domain(search_in, search)])

        if filterby == "unread":
            candidate_ids = Ticket.search(domain).ids
            activity = self._comment_activity(candidate_ids)
            seen = self._seen_message_ids(candidate_ids)
            unread_ids = [
                ticket_id for ticket_id, item in activity.items()
                if item["incoming_id"] and item["incoming_id"] > seen.get(ticket_id, 0)
            ]
            domain = AND([domain, [("id", "in", unread_ids)]])

        result_count = Ticket.search_count(domain)
        pager = portal_pager(
            url="/my/tickets",
            url_args={"date_begin": date_begin, "date_end": date_end, "sortby": sortby,
                      "search_in": search_in, "search": search, "groupby": groupby, "filterby": filterby,
                      "steps_status": selected["status"], "steps_stage": selected_stage,
                      "steps_period": selected["period"], "steps_priority": selected_priority,
                      "steps_assignment": selected["assignment"]},
            total=result_count, page=page, step=self._items_per_page,
        )
        order = f"{groupby}, {sortby}" if groupby != "none" else sortby
        tickets = Ticket.search(domain, order=order, limit=self._items_per_page, offset=pager["offset"])
        request.session["my_tickets_history"] = tickets.ids[:100]
        if not tickets:
            grouped_tickets = []
        elif groupby != "none":
            grouped_tickets = [Ticket.concat(*group) for _, group in groupbyelem(tickets, itemgetter(groupby))]
        else:
            grouped_tickets = [tickets]

        activity = self._comment_activity(tickets.ids)
        seen = self._seen_message_ids(tickets.ids)
        last_messages = request.env["mail.message"].sudo().browse(
            [item["latest_id"] for item in activity.values()]
        )
        message_by_id = {message.id: message for message in last_messages}
        unread_ids = {
            ticket_id for ticket_id, item in activity.items()
            if item["incoming_id"] and item["incoming_id"] > seen.get(ticket_id, 0)
        }
        values.update({
            "date": date_begin,
            "steps_date_begin": date_begin,
            "steps_date_end": date_end,
            "grouped_tickets": grouped_tickets,
            "page_name": "ticket",
            "default_url": "/my/tickets",
            "pager": pager,
            "searchbar_sortings": sortings,
            "searchbar_filters": filters,
            "searchbar_inputs": inputs,
            "searchbar_groupby": groupings,
            "sortby": sortby,
            "groupby": groupby,
            "search_in": search_in,
            "search": search,
            "filterby": filterby,
            "steps_ticket_last_messages": {
                ticket_id: message_by_id[item["latest_id"]]
                for ticket_id, item in activity.items()
            },
            "steps_ticket_unread_ids": unread_ids,
            "steps_filter": selected,
            "steps_stage": selected_stage,
            "steps_priority": selected_priority,
            "steps_stages": visible_stages,
            "steps_priority_options": priority_options,
            "steps_total_count": Ticket.search_count(visible_domain),
            "steps_open_count": Ticket.search_count(AND([visible_domain, [("close_date", "=", False)]])),
            "steps_closed_count": Ticket.search_count(AND([visible_domain, [("close_date", "!=", False)]])),
            "steps_result_count": result_count,
        })
        return values

    @http.route([
        "/helpdesk/ticket/<int:ticket_id>",
        "/helpdesk/ticket/<int:ticket_id>/<access_token>",
        "/my/ticket/<int:ticket_id>",
        "/my/ticket/<int:ticket_id>/<access_token>",
    ], type="http", auth="public", website=True)
    def tickets_followup(self, ticket_id=None, access_token=None, **kw):
        response = super().tickets_followup(ticket_id, access_token, **kw)
        if request.env.user._is_public() or response.status_code != 200:
            return response
        try:
            self._document_check_access("helpdesk.ticket", ticket_id, access_token)
        except (AccessError, MissingError):
            return response
        activity = self._comment_activity([ticket_id])
        latest_id = activity.get(ticket_id, {}).get("latest_id")
        Seen = request.env["step.helpdesk.portal.seen"].sudo()
        record = Seen.search([
            ("user_id", "=", request.env.user.id),
            ("ticket_id", "=", ticket_id),
        ], limit=1)
        values = {"last_seen_at": fields.Datetime.now(), "last_seen_message_id": latest_id or False}
        if record:
            record.write(values)
        else:
            Seen.create({"user_id": request.env.user.id, "ticket_id": ticket_id, **values})
        return response
