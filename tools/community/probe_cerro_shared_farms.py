"""Compare the original farm memberships, contact links, access rules and real user reads."""
import hashlib
import json
import re

from odoo import Command
from odoo.exceptions import AccessError, ValidationError

IDENTITIES = (
    'field_step_fundo__company_ids', 'field_step_fundo__step_contact_group_id',
    'field_res_partner__step_contact_group_id', 'field_res_users__step_contact_group_id',
    'model_inherit__step_fundo__step_shared_agriculture_master', 'model_step_shared_agriculture_master',
)


def capture(env):
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', env.cr.dbname)
    result = {}
    statements = {
        'farms': 'SELECT id, company_id, partner_id, fundo_code, csg_code, sector_id FROM step_fundo ORDER BY id',
        'memberships': 'SELECT master_id, company_id FROM step_fundo_company_rel ORDER BY 1,2',
        'contacts': 'SELECT id, step_contact_group_id FROM res_partner WHERE step_contact_group_id IS NOT NULL ORDER BY id',
        'security': """SELECT r.id,r.domain_force,r.perm_read,r.perm_write,r.perm_create,r.perm_unlink,
                         (SELECT array_agg(group_id ORDER BY group_id) FROM rule_group_rel WHERE rule_group_id=r.id)
                      FROM ir_rule r JOIN ir_model m ON m.id=r.model_id
                      WHERE m.model IN ('step.fundo','res.partner') ORDER BY r.id""",
        'acl': """SELECT a.id,group_id,active,perm_read,perm_write,perm_create,perm_unlink
                  FROM ir_model_access a JOIN ir_model m ON m.id=a.model_id
                  WHERE m.model IN ('step.fundo','res.partner') ORDER BY a.id""",
    }
    for name, sql in statements.items():
        env.cr.execute(sql)
        rows = env.cr.fetchall()
        result[name] = [len(rows), hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()]
    assert result['farms'][0] == 53 and result['memberships'][0] == 95 and result['contacts'][0] == 19
    result['legacy_ids'] = {name: env.ref('step_agriculture_multicompany.' + name).id for name in IDENTITIES}
    return result


def exercise(env):
    account = env['res.users'].browse(6)
    farms = env['step.fundo'].with_user(account).with_context(allowed_company_ids=account.company_ids.ids)
    farm = farms.search([], limit=1, order='id')
    assert farm and not farms.env.su
    farm.check_access('write')
    rows = farms.search_read([], ['company_id', 'company_ids', 'step_contact_group_id'], order='id')
    partitions = {}
    for company in account.company_ids:
        subset = farms.with_context(allowed_company_ids=[company.id])
        allowed = subset.search([], order='id')
        assert all(company in r.company_ids for r in allowed)
        forbidden = farm.sudo().search([('company_ids', 'not in', [company.id])], limit=1)
        if forbidden:
            assert not subset.search([('id', '=', forbidden.id)])
            try:
                forbidden.with_env(subset.env).read(['name'])
            except AccessError:
                pass
            else:
                raise AssertionError('Farm outside the permitted company can be read')
        partitions[company.id] = len(allowed)
    try:
        with env.cr.savepoint():
            farm.write({'company_ids': [Command.clear()]})
    except ValidationError:
        pass
    else:
        raise AssertionError('Clearing the owning company was permitted')
    env.cr.execute("""SELECT DISTINCT f.id,d.company_id FROM step_packing_production d
                      JOIN step_fundo f ON f.id=d.fruit_fundo_id
                      JOIN step_fundo_company_rel rel ON rel.master_id=f.id AND rel.company_id=d.company_id
                      WHERE d.company_id<>f.company_id ORDER BY 1,2""")
    documents = env.cr.fetchall()
    assert documents
    for farm_id, company_id in documents:
        used = farms.browse(farm_id)
        try:
            with env.cr.savepoint():
                used.write({'company_ids': [Command.unlink(company_id)]})
        except ValidationError:
            pass
        else:
            raise AssertionError('A farm company used by a historical packing order was removed')
    partner = farms.env['res.partner'].search([('step_contact_group_id', '!=', False), ('is_productor', '=', True)], limit=1)
    assert partner
    partner.check_access('write')
    try:
        with env.cr.savepoint():
            partner.step_contact_group_id = partner
    except ValidationError:
        pass
    else:
        raise AssertionError('A contact group cycle was permitted')
    result = {'uid': account.id, 'visible': len(rows), 'partitions': partitions, 'protected_packing_assignments': len(documents),
              'farm_reads_sha256': hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()}
    return result
