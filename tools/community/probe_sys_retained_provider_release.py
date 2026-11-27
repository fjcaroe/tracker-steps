"""Check loaded upstream origins and exercise the customized Latin American invoice report as original operators."""
import ast
import importlib
from pathlib import Path

from lxml import etree, html
from odoo.modules.module import adapt_version, get_manifest, get_module_path


def run(shell, root):
    shell.cr.rollback()
    shell.cr.execute("SET TRANSACTION READ ONLY")
    versions = {}
    for name in ("hr_timesheet", "project_sms"):
        path = (root / "pinned" / name).resolve()
        assert Path(get_module_path(name)).samefile(path)
        assert Path(importlib.import_module("odoo.addons." + name).__file__).samefile(path / "__init__.py")
        manifest = ast.literal_eval((path / "__manifest__.py").read_text())
        mod, = shell["ir.module.module"].search([("name", "=", name), ("state", "=", "installed")])
        assert mod.latest_version == "18.0.1.0" and manifest["version"] == "1.0" and manifest["license"] == "LGPL-3"
        versions[name] = mod.latest_version
    installed = shell["ir.module.module"].search([("state", "=", "installed")])
    assert len(installed) == 190 and not installed.filtered(lambda item: item.license == "OEEL-1")
    differences = {item.name: [item.latest_version, adapt_version(get_manifest(item.name)["version"])]
                   for item in installed if item.latest_version != adapt_version(get_manifest(item.name)["version"])}
    assert not differences and all(Path(get_module_path(item.name)).resolve().is_relative_to(root) for item in installed)
    profile = root / ("tested-profile" if (root / "tested-profile-proof.json").is_file() else "profile")
    overlays = []
    for module in sorted(profile.iterdir()):
        actual = Path(get_module_path(module.name))
        assert actual.samefile(module) and (actual / "__manifest__.py").samefile(module / "__manifest__.py")
        overlays.append(module.name)
    shell.cr.execute("""SELECT id,encode(sha256(convert_to(arch_db::text,'UTF8')),'hex') FROM ir_ui_view
                        WHERE id IN (1215,204) ORDER BY id""")
    assert shell.cr.fetchall() == [
        (204, "7348f33beabc72cdf09cf504c5cff83847e324953fec3bd73ff0c8e966a79111"),
        (1215, "0e6741df23c3e3cd2f1d68068f960fb2034fd503f324be1cb2118c9443242edf")]
    actors = shell["res.users"].sudo().search([("active", "=", True), ("share", "=", False), ("id", ">", 1)])
    assert len(actors) == 2
    result = []
    for actor in actors:
        for company in actor.company_ids.filtered("active"):
            scope = shell(user=actor.id, su=False, context={"allowed_company_ids": [company.id], "lang": "es_CL"})
            assert not scope.su
            move = scope["account.move"].search([("company_id", "=", company.id), ("state", "=", "posted"),
                ("move_type", "=", "out_invoice"), ("l10n_latam_document_type_id", "!=", False)], order="id", limit=1)
            if not move:
                continue
            move.check_access("read")
            standard = scope.ref("l10n_latam_invoice_document.external_layout_standard")
            wave = scope.ref("l10n_latam_invoice_document.external_layout_wave")
            assert standard.id == 1215 and standard.inherit_id.id == 204
            assert etree.fromstring(standard.get_combined_arch().encode()).tag
            wave_tree = etree.fromstring(wave.get_combined_arch().encode())
            footers = wave_tree.xpath('//*[contains(@t-if,"custom_footer") and contains(@t-attf-class,"o_footer_content")]')
            assert any("mx-5" in (f.get("t-attf-class") or "") and "position-absolute" not in f.get("t-attf-class")
                       for f in footers)
            rendered, fmt = scope["ir.actions.report"]._render_qweb_html("account.account_invoices", move.ids)
            content = rendered if isinstance(rendered, bytes) else str(rendered).encode()
            visible = " ".join(html.fromstring(content).text_content().split())
            identifiers = [str(value) for value in (move.name, move.l10n_latam_document_number) if value]
            assert fmt == "html" and any(token in visible for token in identifiers)
            result.append({"original_company": company.id, "html_bytes": len(content),
                           "document_number_visible": True, "wave_footer_nodes": len(footers)})
            break
    assert len(result) == 2
    shell.cr.rollback()
    return {"active_source_versions": versions, "all_installed_checked": len(installed), "version_differences": differences,
            "loaded_profile": overlays, "native_standard_layout": True, "operator_invoice_renders": result}
