"""Verify the migrated company with the existing Desarrollo API profile."""
import json
from pathlib import Path
from urllib.request import Request, urlopen
import xmlrpc.client

URL = "https://desarrollo.stepsapp.cl"
DB = "LAB_TAREAS"


def main():
    access = json.loads((Path.home() / ".odoo" / "desarrollo_api.json").read_text(encoding="utf-8-sig"))
    assert access["db"] == DB
    credential = access["api_key"]
    uid = xmlrpc.client.ServerProxy(URL + "/xmlrpc/2/common").authenticate(DB, access["username"], credential, {})
    assert uid

    def read(model, method, args=(), **kwargs):
        payload = {
            "jsonrpc": "2.0", "method": "call", "id": 1,
            "params": {"service": "object", "method": "execute_kw",
                       "args": [DB, uid, credential, model, method, list(args), kwargs]},
        }
        request = Request(URL + "/jsonrpc", data=json.dumps(payload).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request, timeout=30) as response:
            data = json.load(response)
        if "error" in data:
            raise RuntimeError(data["error"]["data"]["message"])
        return data["result"]

    company, = read("res.company", "search_read", [[("name", "=ilike", "EcoPlantas")]], fields=["name"])
    cid = company["id"]
    ctx = {"allowed_company_ids": [cid]}
    user, = read("res.users", "read", [[uid]], fields=["company_id", "company_ids"])
    assert cid in user["company_ids"]
    dashboard = read("res.company", "get_steps_greenhouse_dashboard", context=ctx)
    assert dashboard["planned"] == 100 and dashboard["operations"] == 2 and dashboard["tasks"] == 4
    assert dashboard["shared_costs"]
    assert dashboard["subpage_metrics"]["batch"][0]["value"] == 100
    for key in ("receipt", "batch", "inspection", "dispatch", "maintenance", "project"):
        entry = dashboard[key]
        record, = read(entry["model"], "read", [[entry["id"]]], fields=["company_id"], context=ctx)
        assert record["company_id"][0] == cid
        view = read(entry["model"], "get_view", view_type="form", context=ctx)
        assert view["arch"]
    costs, = read("step.nursery.cost.run", "search_read", [[("company_id", "=", cid)]],
                  fields=["state", "cost_total", "line_ids"], context=ctx)
    assert costs["state"] == "draft" and costs["cost_total"] == 200000 and len(costs["line_ids"]) == 4
    menu = read("ir.ui.menu", "search_read", [[("name", "=", "Invernadero")]], fields=["action"], context=ctx)
    assert any(row["action"] for row in menu)
    other = user["company_id"][0]
    if other != cid:
        try:
            read("res.company", "get_steps_greenhouse_dashboard", context={"allowed_company_ids": [other]})
        except RuntimeError as error:
            assert "Seleccione EcoPlantas" in str(error)
        else:
            raise AssertionError("Invernadero loaded for a different company")
    print(json.dumps({"company": cid, "reviewer": uid, "forms": 6, "cost_total": costs["cost_total"],
                      "route": f"{URL}/odoo/invernadero?cids={cid}"}))


if __name__ == "__main__":
    main()
