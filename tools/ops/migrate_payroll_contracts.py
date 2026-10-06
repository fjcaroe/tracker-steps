"""Map only explicit legacy amounts/codes, without triggering vacation writes.

The review flag stays set: APV, AFC, gratification and other payroll policies
need the administrator's review; they are never inferred from a wage or name.
"""
import json
from psycopg2 import sql

assert env.cr.dbname == EXPECTED_DATABASE
snapshots = env['step.payroll.legacy.snapshot'].sudo()
structure = env.ref('l10n_cl_simpledigital_payroll.structure_chile')
old_structures = env['hr.payroll.structure'].search([('step_legacy_payroll','=',True)])
old_types = old_structures.type_id.ids
simple = {
    'colacion':'colocation', 'movilizacion':'movility', 'viatico_santiago':'viatico_fijo',
    'carga_familiar':'family_simple_loads_count', 'carga_familiar_maternal':'family_maternal_loads_count',
    'carga_familiar_invalida':'family_invalid_loads_count', 'pension':'is_retired_elderly',
    'isapre_cotizacion_uf':'isapre_uf_valor', 'isapre_moneda':'isapre_calc_type',
}
for record in snapshots.search([('source_model','=','hr.contract')]):
    contract = env['hr.contract'].with_context(active_test=False).browse(record.source_id).exists()
    if not contract or contract.step_payroll_migration_mapped:
        continue
    payload = record.payload
    values = {new:payload[old] for old,new in simple.items() if old in payload and payload[old] is not None}
    if payload.get('structure_type_id') in old_types:
        values['structure_type_id'] = structure.type_id.id
    for field, old_model, ref_field in (('afp_option','hr.afp','afp_id'),('health_institution','hr.isapre','isapre_id')):
        master = snapshots.search([('source_model','=',old_model),('source_id','=',payload.get(ref_field) or 0)],limit=1)
        if master:
            code = str(master.payload.get('codigo_rem') or '').strip()
            allowed = env['hr.contract']._fields[field]._description_selection(env)
            matches = [key for key,label in allowed if key.split(' - ')[-1] == code]
            if len(matches)==1:
                values[field] = matches[0]
                if field=='afp_option' and values[field]!='00 - 100': values['pension_option']='afp'
    values['step_payroll_migration_mapped'] = True
    if values:
        statement=sql.SQL('UPDATE hr_contract SET {} WHERE id=%s').format(sql.SQL(',').join(sql.SQL('{}=%s').format(sql.Identifier(k)) for k in values))
        env.cr.execute(statement,[*values.values(),record.source_id])
env.cr.commit()
print('PAYROLL_CONTRACT_MAPPING_OK')
