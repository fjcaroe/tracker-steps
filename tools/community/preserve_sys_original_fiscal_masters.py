"""Retain original Chilean masters whose economic projections matched the full official rehearsal."""
from collections import Counter
import csv
import hashlib
import json

from lxml import etree

from custody_sys_previred_filestore import digest
from restore_native_product_backup import query
from restore_sys_previred_pair import require


MODELS = {"account.account.tag": 47, "account.report": 1, "account.report.column": 1,
          "account.report.expression": 32, "account.report.line": 32, "l10n_latam.document.type": 58,
          "l10n_latam.identification.type": 3, "res.bank": 32}
XML = ("l10n_cl_chart_data.xml", "account_tax_report_data.xml", "account_tax_tags_data.xml",
       "l10n_latam_identification_type_data.xml")
CSVS = {"l10n_latam.document.type.csv": "l10n_latam.document.type", "res.bank.csv": "res.bank"}
TAG_REFS = {"tag_cl_purchase_mnt_iec", "tag_cl_specific_fuel_tax"}
SOURCE = "COMMUNITY_SYS_PREVIRED_COHORT_20261126U40J"
TRIAL = "COMMUNITY_SYS_PREVIRED_MODULES_20261127U41MQ"


def matched_fields(db):
    result = {}
    for model, touched in MODELS.items():
        table = model.replace(".", "_")
        value = "(to_jsonb(t)-'write_date')"
        if model == "account.account.tag":
            # These exact two rows originally had a single language. Check the extra locale separately.
            value = ("CASE WHEN t.id IN (23,114) THEN jsonb_set(to_jsonb(t)-'write_date','{name}',t.name-'es_CL') "
                     "ELSE to_jsonb(t)-'write_date' END")
        sql = f"""SELECT json_build_array(count(*),md5(string_agg(md5(({value})::text),'' ORDER BY id)),
              md5(string_agg(md5(to_jsonb(t)::text),'' ORDER BY id))) FROM public.{table} t"""
        source, rehearsal, fresh = [json.loads(query(name, sql)) for name in (SOURCE, TRIAL, db)]
        require(fresh == source and rehearsal[:2] == source[:2], "original-fiscal-master-drift-" + table)
        result[model] = {"rows": source[0], "economic_projection": source[1],
                         "original_rows": source[2], "edited_in_official_rehearsal": touched}
    lang = """SELECT json_agg(json_build_array(t.id,d.name,(t.name ? 'es_CL'),t.name ? 'en_US') ORDER BY t.id)
        FROM account_account_tag t JOIN ir_model_data d ON d.res_id=t.id AND d.model='account.account.tag'
        WHERE d.module='l10n_cl' AND d.name IN ('tag_cl_purchase_mnt_iec','tag_cl_specific_fuel_tax')"""
    old = [[23, "tag_cl_specific_fuel_tax", False, True], [114, "tag_cl_purchase_mnt_iec", False, True]]
    require(json.loads(query(SOURCE, lang)) == old and json.loads(query(db, lang)) == old and
            json.loads(query(TRIAL, lang)) == [[pk, key, True, True] for pk, key, missing, en in old],
            "unexpected-rehearsed-language-change")
    return result


def preserve(original, output, db, schema):
    signatures = matched_fields(db)
    declared = {}
    mf = (output / "__manifest__.py").read_text()
    output_files = {}
    for filename in XML:
        file = output / "data" / filename
        xml = etree.parse(str(file))
        require(xml.getroot().tag == "odoo" and not xml.xpath("//function | //delete | //record[not(@id)]"),
                "unrecognized-fiscal-seed-operation")
        for rec in xml.xpath("//record[@id]"):
            name = rec.get("id")
            require(name not in declared and rec.get("model") in MODELS, "unexpected-fiscal-record")
            declared[name] = rec.get("model")
        xml.getroot().set("noupdate", "1")
        for scope in xml.xpath("//data[@noupdate]"):
            scope.set("noupdate", "1")
        schema.assertValid(xml)
        xml.write(str(file), encoding="UTF-8", xml_declaration=True)
        output_files[filename] = digest(file)
    for filename, model in CSVS.items():
        incoming = original / "data" / filename
        source = "data/" + filename
        target = "data/sys_preserved_" + model.replace(".", "_") + ".xml"
        require(mf.count(source) == 1, "ambiguous-fiscal-csv")
        root = etree.Element("odoo", noupdate="1")
        with incoming.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                name = row.pop("id")
                require(name not in declared, "duplicate-original-fiscal-seed")
                declared[name] = model
                rec = etree.SubElement(root, "record", id=name, model=model)
                for key, val in row.items():
                    if key.endswith((":id", "/id")):
                        col = etree.SubElement(rec, "field", name=key[:-3])
                        if val:
                            col.set("ref", val)
                        else:
                            col.set("eval", "False")
                    elif key in ("l10n_cl_active", "active"):
                        require(val.lower() in ("true", "false", "1", "0", ""), "unrecognized-fiscal-boolean")
                        etree.SubElement(rec, "field", name=key, eval=str(val.lower() in ("1", "true")))
                    elif key == "sequence":
                        etree.SubElement(rec, "field", name=key, eval=str(int(val)) if val else "False")
                    else:
                        require(key in ("code", "name", "report_name", "internal_type", "doc_code_prefix",
                                        "l10n_cl_sbif_code"), "unrecognized-fiscal-csv-column")
                        etree.SubElement(rec, "field", name=key).text = val
        xml = etree.ElementTree(root)
        schema.assertValid(xml)
        xml.write(str(output / target), encoding="UTF-8", xml_declaration=True, pretty_print=True)
        mf = mf.replace(source, target)
        output_files[target] = digest(output / target)
    require(Counter(declared.values()) == MODELS, "wrong-declared-fiscal-master-count")
    aliases = json.loads(query(db, """SELECT json_object_agg(name,json_build_array(model,res_id,noupdate)) FROM ir_model_data
        WHERE module='l10n_cl'"""))
    for name, model in declared.items():
        key = name.removeprefix("l10n_cl.")
        require(key in aliases and aliases[key][0] == model, "original-fiscal-identity-missing-" + key)
    po = output / "i18n/es_419.po"
    blocks = po.read_text().split("\n\n")
    removed = {}
    retained = []
    for block in blocks:
        refs = [line[3:] for line in block.splitlines() if line.startswith("#: ")]
        keys = {r.removeprefix("model:account.account.tag,name:l10n_cl.") for r in refs} & TAG_REFS
        if keys:
            key, = keys
            require(refs == ["model:account.account.tag,name:l10n_cl." + key] and 'msgstr "' in block,
                    "unexpected-fiscal-translation-scope")
            removed[key] = hashlib.sha256(block.encode()).hexdigest()
        else:
            retained.append(block)
    require(removed.keys() == TAG_REFS, "original-fuel-tag-translations-not-accounted-for")
    po.write_text("\n\n".join(retained))
    (output / "__manifest__.py").write_text(mf)
    return {"master_projection": signatures, "original_xmlids": len(declared),
            "declared_models": dict(Counter(declared.values())), "preserved_absent_translations": removed,
            "files": output_files, "translation_catalog": digest(po)}
