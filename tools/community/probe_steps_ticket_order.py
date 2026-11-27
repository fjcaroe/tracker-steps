"""Trace the original support user's ticket ordering and its page boundaries without changing any records."""
from unittest.mock import patch

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, Response
from werkzeug.datastructures import MultiDict
from probe_steps_support_thread import request_for


def run(env):
    assert env.cr.dbname in ("MANAGEMENT_QA_STEPS_CRM_20261126U42C", "COMMUNITY_STEPS_CRM_INTEGRATED_20261127U46A",
                             "COMMUNITY_STEPS_CRM_FISCAL_20261127U45F")
    env.cr.rollback()
    env.cr.execute("SET TRANSACTION READ ONLY")
    user = env["res.users"].browse(6)
    scope = env(user=user.id, su=False, context={"allowed_company_ids": [user.company_id.id], "lang": user.lang})
    model = scope["helpdesk.ticket"]
    visible = model.search([], order="id")
    assert len(visible) == 5 and user.share
    rank = {key: number for number, key in enumerate(visible.ids, 1)}
    groups = {key: model.browse(key).user_id.id or 0 for key in visible.ids}
    endpoint, = [r.endpoint for r in scope["ir.http"].routing_map().iter_rules() if r.rule == "/my/tickets"]
    original = type(model).search
    output = []
    try:
        for plan, options in (("default", {}), ("indexes", {"enable_seqscan": "off"}),
                              ("scan", {"enable_indexscan": "off", "enable_indexonlyscan": "off", "enable_bitmapscan": "off"})):
            for key in ("enable_seqscan", "enable_indexscan", "enable_indexonlyscan", "enable_bitmapscan"):
                env.cr.execute("SELECT set_config(%s,%s,true)", (key, options.get(key, "on")))
            for limit in (80, 2):
                combined = []
                all_queries = []
                for page in range(1, 2 if limit == 80 else 4):
                    queries = []
                    def capture(records, domain, *args, **kw):
                        found = original(records, domain, *args, **kw)
                        if kw.get("order") and kw.get("limit") is not None:
                            queries.append([kw.get("order"), kw.get("offset", 0), kw["limit"], list(found.ids)])
                        return found
                    with patch.object(type(model), "search", capture), patch.object(CustomerPortal, "_items_per_page", limit), request_for(scope, "/my/tickets"):
                        request.session.uid = user.id
                        request.httprequest.args = MultiDict([("sortby", "user_id")])
                        request.httprequest.headers = MultiDict()
                        request.render = lambda template, values=None, **kw: Response(template=template, qcontext=values or {})
                        response = endpoint(sortby="user_id", page=page)
                        assert response.status_code == 200
                    chosen = [row for row in queries if row[2] == limit]
                    assert chosen and len({tuple(row[3]) for row in chosen}) == 1, ("ticket-page-query", queries)
                    order, start, step, ids = chosen[0]
                    assert set(ids) <= rank.keys() and step == limit and start == (page - 1) * limit
                    combined.extend(ids)
                    all_queries.append([order, start, step, [rank[i] for i in ids]])
                output.append({"plan": plan, "limit": limit, "queries": all_queries,
                               "order": [rank[i] for i in combined], "complete_unique": sorted(combined) == sorted(rank),
                               "group_runs": [groups[i] for i in combined]})
        # Keep partner and staff identifiers out of the portable evidence.
        anonymized = {value: index for index, value in enumerate(dict.fromkeys(groups.values()), 1)}
        for line in output:
            line["group_runs"] = [anonymized[g] for g in line["group_runs"]]
        return {"steps": output, "by_ticket": [anonymized[groups[i]] for i in visible.ids]}
    finally:
        env.cr.rollback()
