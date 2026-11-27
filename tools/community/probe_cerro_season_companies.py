"""Read the original Cerro season form with its multi-company rule in all inventory-user contexts."""
import hashlib
import json
import re

from lxml import etree


def capture(env):
    if not re.fullmatch(r'MANAGEMENT_QA_CERRO_BOM_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Expected a private native Cerro trial')
    operator = env['res.users'].browse(6)
    original = env.ref('step_hr.view_temporada_form')
    extension = env.ref('step_agriculture_catalogs.view_temporada_form_companies')
    field = env['ir.model.fields'].browse(27057)
    rule = env['ir.rule'].browse(553)
    assert original.id == 4159 and extension.id == 4637 and extension.inherit_id == original
    assert (field.model, field.name, field.ttype, field.relation, field.store) == (
        'step.temporada', 'company_ids', 'many2many', 'res.company', True)
    assert rule.active and rule.model_id.model == field.model and not rule.groups
    assert rule.domain_force == "['|', ('company_ids', '=', False), ('company_ids', 'in', company_ids)]"
    original._check_xml()
    extension._check_xml()
    env.cr.execute("""SELECT s.id,coalesce(array_agg(rel.res_company_id ORDER BY rel.res_company_id)
                                 FILTER (WHERE rel.res_company_id IS NOT NULL), '{}')
                      FROM step_temporada s LEFT JOIN res_company_step_temporada_rel rel ON rel.step_temporada_id=s.id
                      GROUP BY s.id ORDER BY s.id""")
    native = dict(env.cr.fetchall())
    assert len(native) == 3
    partitions = {}
    for company in operator.company_ids:
        model = env[field.model].with_user(operator).with_context(allowed_company_ids=[company.id])
        assert not model.env.su
        form = model.get_views([(original.id,'form')], {'toolbar': True})['views']['form']
        assert form['id'] == original.id
        tree = etree.fromstring(form['arch'].encode())
        assert tree.xpath("//field[@name='company_ids'][@widget='many2many_tags']")
        records = model.search([],order='id')
        expected = [key for key, allowed in native.items() if not allowed or company.id in allowed]
        assert records.ids == expected
        values = records.read(['company_ids'])
        assert all(sorted(row['company_ids']) == native[row['id']] for row in values)
        partitions[str(company.id)] = len(records)
    return {'field': field.id, 'form': original.id, 'extension': extension.id, 'rule': rule.id,
            'seasons': len(native), 'partitions': partitions,
            'relations_sha256': hashlib.sha256(json.dumps(native,sort_keys=True).encode()).hexdigest()}
