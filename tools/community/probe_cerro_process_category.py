"""Compare all six original Cerro packing process types and their three options."""
import hashlib
import json
import re


def capture(env, test=False):
    assert re.fullmatch(r'(?:MANAGEMENT_QA|COMMUNITY)_CERRO_BOM_[A-Z0-9_]+', env.cr.dbname)
    refs = ['field_step_packing_process_type__step_category'] + [
        'selection__step_packing_process_type__step_category__' + value for value in ('selection', 'packing', 'correction')]
    ids = {name: env.ref('step_packing_operations.' + name).id for name in refs}
    env.cr.execute('SELECT id,name,company_id,step_category FROM step_packing_process_type ORDER BY id')
    rows = env.cr.fetchall()
    assert len(rows) == 6 and {r[-1] for r in rows} == {'selection', 'packing', 'correction'}
    result = {'ids': ids, 'rows': len(rows), 'values_sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
    if test:
        role = env['res.users'].browse(6)
        model = env['step.packing.process.type'].with_user(role).with_context(allowed_company_ids=role.company_ids.ids)
        records = model.search([])
        assert records and not model.env.su
        values = records.web_read({'step_category': {}})
        result['visible'] = len(values)
        existing = records[0]
        old = existing.step_category
        new = 'selection' if old == 'packing' else 'packing'
        existing.write({'step_category': new})
        assert existing.step_category == new
        existing.write({'step_category': old})
        try:
            with env.cr.savepoint():
                existing.write({'step_category': 'invalid-catalog-option'})
        except ValueError:
            pass
        else:
            raise AssertionError('An invalid process category was accepted')
    return result
