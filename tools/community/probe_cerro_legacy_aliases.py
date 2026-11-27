"""Exercise Odoo's cleanup while the original, writable source XML identifiers retain their flags."""
import hashlib
import json
import re

from odoo.exceptions import ValidationError


class RollbackProbe(Exception):
    pass


def capture(env):
    if not re.fullmatch(r'COMMUNITY_(?:LIBRARY_CERRO|CERRO_BOM(?:_STRICT)?)_[A-Z0-9_]+', env.cr.dbname):
        raise ValueError('Expected private restored Cerro')
    data = env['ir.model.data']
    pairs = data._step_retained_aliases()
    fixed = {}
    for legacy, owner, names in pairs:
        names = list(names) if names is not None else None
        env.cr.execute("""SELECT src.id,src.name,src.model,src.res_id,src.noupdate,dst.id
            FROM ir_model_data src JOIN ir_model_data dst ON dst.name=src.name
              AND dst.model=src.model AND dst.res_id=src.res_id
            WHERE src.module=%s AND dst.module=%s AND (%s::text[] IS NULL OR src.name=ANY(%s))
            ORDER BY src.id""", [legacy, owner, names, names])
        rows = env.cr.fetchall()
        fixed[legacy + '/' + owner] = {'count': len(rows), 'original_writable': sum(not x[4] for x in rows),
                                      'sha256': hashlib.sha256(json.dumps(rows).encode()).hexdigest()}
    baseline = set(env.registry.loaded_xmlids)
    env.cr.execute("SELECT module||'.'||name FROM ir_model_data WHERE module='step_hr'")
    loaded = {r[0] for r in env.cr.fetchall()}
    def alias(module, name, record):
        return data.create({'module': module, 'name': name, 'model': record._name, 'res_id': record.id,
                            'noupdate': False})
    try:
        with env.cr.savepoint():
            params = env['ir.config_parameter']
            keep = params.create({'key': 'steps.cerro.alias_probe.keep', 'value': 'keep'})
            stale = params.create({'key': 'steps.cerro.alias_probe.stale', 'value': 'stale'})
            retained = alias('step_hr', 'steps_qa_verified_alias', keep)
            alias('step_agriculture_core', 'steps_qa_verified_alias', keep)
            removed = alias('step_hr', 'steps_qa_unclaimed_alias', stale)
            env.registry.loaded_xmlids.update(loaded)
            data._process_end(['step_hr'])
            assert retained.exists() and not retained.noupdate and keep.exists()
            assert not removed.exists() and not stale.exists()
            # A same-name alias pointing at another record is an error.
            other = params.create({'key': 'steps.cerro.alias_probe.other', 'value': 'other'})
            alias('step_hr', 'steps_qa_conflicting_alias', keep)
            alias('step_agriculture_core', 'steps_qa_conflicting_alias', other)
            env.registry.loaded_xmlids.update(loaded)
            try:
                with env.cr.savepoint():
                    data._process_end(['step_hr'])
            except ValidationError:
                pass
            else:
                raise AssertionError('The loader accepted a conflicting alias')
            raise RollbackProbe()
    except RollbackProbe:
        pass
    finally:
        env.registry.loaded_xmlids.clear()
        env.registry.loaded_xmlids.update(baseline)
    assert not env['ir.config_parameter'].search_count([('key', 'like', 'steps.cerro.alias_probe.%')])
    return {'pairs': fixed, 'same_target_preserved': True, 'stale_source_removed': True, 'conflict_rejected': True}
