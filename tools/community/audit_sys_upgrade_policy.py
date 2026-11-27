"""Compare policy seeds of the six modules with original aliases, rights, memberships and domains."""
import ast
import csv
import json

from lxml import etree

from restore_native_product_backup import query


def audit(db, core, modules, *, original_admin_seeds=False):
    def rows(sql):
        return json.loads(query(db, sql))
    aliases = rows("""SELECT json_object_agg(module||'.'||name,json_build_array(model,res_id,noupdate))
        FROM ir_model_data WHERE model IN ('ir.model','res.groups','ir.rule','ir.model.access','ir.module.category','ir.cron','hr.contract.type','res.country')""")
    access = rows("""SELECT json_object_agg(id,json_build_object('name',name,'model_id',model_id,'group_id',group_id,
        'perm_read',perm_read,'perm_write',perm_write,'perm_create',perm_create,'perm_unlink',perm_unlink))
        FROM ir_model_access""")
    groups = rows("""SELECT json_object_agg(id,json_build_object('name',name,'category_id',category_id,'comment',comment))
        FROM res_groups""")
    rules = rows("""SELECT json_object_agg(id,json_build_object('name',name,'model_id',model_id,'domain_force',domain_force,
        'global',NOT EXISTS (SELECT 1 FROM rule_group_rel g WHERE g.rule_group_id=r.id))) FROM ir_rule r""")
    stored_by_model = {"res.groups": groups, "ir.rule": rules}
    if original_admin_seeds:
        stored_by_model["hr.contract.type"] = rows("""SELECT json_object_agg(id,json_build_object(
            'name',name,'code',code,'country_id',country_id)) FROM hr_contract_type""")
        stored_by_model["ir.cron"] = rows("""SELECT json_object_agg(c.id,json_build_object('name',a.name,
            'model_id',a.model_id,'state',a.state,'code',a.code,'interval_type',c.interval_type,
            'interval_number',c.interval_number)) FROM ir_cron c JOIN ir_act_server a ON a.id=c.ir_actions_server_id""")
    memberships = {tuple(r) for r in rows("SELECT json_agg(json_build_array(gid,hid)) FROM res_groups_implied_rel")}
    result = {}
    for module in modules:
        base = core / "addons" / module
        manifest = ast.literal_eval((base / "__manifest__.py").read_text())

        def info(name):
            return aliases[name if "." in name else module + "." + name]

        records = {}
        for filename in manifest["data"]:
            path = base / filename
            if path.name == "ir.model.access.csv":
                with path.open(encoding="utf-8-sig", newline="") as raw:
                    for acl in csv.DictReader(raw):
                        declared = acl.pop("id")
                        model, pk, noupdate = info(declared)
                        assert model == "ir.model.access"
                        expected = {}
                        for key, new_value in acl.items():
                            if key.endswith((":id", "/id")):
                                expected[key[:-3]] = info(new_value)[1] if new_value else None
                            elif key.startswith("perm_"):
                                assert new_value in ("0", "1")
                                expected[key] = new_value == "1"
                            else:
                                expected[key] = new_value
                        mismatch = [key for key, val in expected.items() if access[str(pk)][key] != val]
                        records[model + "/" + str(pk)] = {"differences": mismatch, "noupdate": noupdate,
                                                          "declared_id": declared}
            elif path.suffix == ".xml":
                xml = etree.parse(str(path))
                for rec in xml.xpath("//record[@id and @model]"):
                    if rec.get("model") not in stored_by_model:
                        continue
                    if rec.xpath('ancestor-or-self::*[@noupdate="1"]'):
                        continue
                    model, pk, noupdate = info(rec.get("id"))
                    assert model == rec.get("model")
                    stored = stored_by_model[model][str(pk)]
                    mismatch = []
                    for field in rec.iterchildren("field"):
                        name = field.get("name")
                        if name == "implied_ids":
                            command, = ast.parse(field.attrib["eval"], mode="eval").body.elts
                            opcode, call = command.elts
                            assert opcode.value == 4 and call.func.id == "ref" and len(call.args) == 1
                            if (pk, info(call.args[0].value)[1]) not in memberships:
                                mismatch.append(name)
                            continue
                        old = stored[name]
                        if isinstance(old, dict):
                            old = old.get("en_US")
                        if field.get("ref"):
                            expected = info(field.attrib["ref"])[1]
                        elif field.get("eval"):
                            expected = ast.literal_eval(field.attrib["eval"])
                        else:
                            expected = (field.text or "").strip()
                            old = old.strip() if isinstance(old, str) else old
                            if type(old) is int:
                                expected = int(expected)
                        if old != expected:
                            mismatch.append(name)
                    records[model + "/" + str(pk)] = {"differences": mismatch, "noupdate": noupdate,
                                                      "declared_id": rec.get("id")}
        result[module] = records
    return result
