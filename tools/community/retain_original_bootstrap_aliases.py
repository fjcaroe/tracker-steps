"""Retain exactly two proven original aliases before the real _process_end.

Private anchored-bootstrap helper, not an installed provider or a global data
retention policy. Its only mutation is to the real registry.loaded_xmlids set;
all database statements are SELECT. Call before _process_end on every admitted
bootstrap/update which defers these two original seed definitions.
"""
import hashlib
import json
from pathlib import Path
import re
import stat

import payroll_configuration_adoption_preflight as gate
from plan_original_payroll_bootstrap import original_aliases


EXPECTED = (
    {'id': 58549, 'module': 'l10n_cl_simpledigital_payroll', 'name': 'structure_type_chile',
     'model': 'hr.payroll.structure.type', 'res_id': 5, 'noupdate': False},
    {'id': 58550, 'module': 'l10n_cl_simpledigital_payroll', 'name': 'structure_chile',
     'model': 'hr.payroll.structure', 'res_id': 4, 'noupdate': False},
)
CAPSULE_SHA256 = '14b18ced97032ec27c306ed4c71c46f0c3d56e324d0eace4f0c8f2c86544e140'
SOURCE_MODULES = {'hr.payroll.structure': 'odoo.addons.payroll.models.',
                  'hr.payroll.structure.type': 'odoo.addons.hr_contract.models.'}
TABLES = {'hr.payroll.structure': 'hr_payroll_structure',
          'hr.payroll.structure.type': 'hr_payroll_structure_type'}


def _read_sealed(path, expected_sha256):
    path = Path(path).resolve()
    gate.require(path.is_relative_to(Path('/opt/steps-validation'))
        and stat.S_IMODE(path.stat().st_mode) == 0o600, 'private-sealed-bootstrap-input-required')
    raw = path.read_bytes()
    gate.require(hashlib.sha256(raw).hexdigest() == expected_sha256, 'bootstrap-source-file-hash-mismatch')
    return json.loads(raw)


def _contract(capsule, identity):
    aliases = original_aliases(capsule, identity)
    by_key = {(row['module'], row['name']): row for row in aliases}
    rows = gate.capsule_rows(capsule)
    result = []
    for expected in EXPECTED:
        gate.require(by_key.get((expected['module'], expected['name'])) == expected,
                     'two-original-false-alias-contract-drift')
        table = TABLES[expected['model']]
        raw_rows = capsule['tables'][table]['rows_json']
        raw = [raw for raw in raw_rows if json.loads(raw)['id'] == expected['res_id']]
        gate.require(len(raw) == 1 and expected['res_id'] in {row['id'] for row in rows[table]},
                     'original-retained-master-missing')
        models = [row for row in identity['ir_model'] if row['model'] == expected['model']]
        gate.require(len(models) == 1 and models[0]['state'] == 'base' and models[0]['transient'] is False,
                     'original-retained-model-metadata-not-proven')
        fields = [{'id': row['id'], 'model': row['model'], 'name': row['name'], 'state': row['state']}
                  for row in identity['ir_model_fields'] if row['model'] == expected['model']]
        gate.require(fields and len({row['id'] for row in fields}) == len(fields),
                     'original-retained-field-metadata-not-proven')
        result.append({'alias': expected, 'table': table, 'raw_json': raw[0],
            'model': {'id': models[0]['id'], 'model': expected['model'], 'state': models[0]['state']},
            'fields': fields})
    return result


def _require_oca_models(env):
    for name, source in SOURCE_MODULES.items():
        gate.require(name in env.registry, 'retained-master-model-not-registered')
        model = env[name]
        gate.require(model._name == name and model._table == TABLES[name]
            and model._auto is True and model._abstract is False and model._transient is False,
            'retained-master-is-not-a-real-persistent-provider-model')
        gate.require(any(cls.__module__.startswith(source) for cls in type(model).mro()),
                     'retained-master-provider-is-not-real-oca-or-official-contract')


def retain_original_aliases(env, *, capsule_path, capsule_sha256,
                            original_identity_path, original_identity_sha256):
    """Called by the coordinator's admitted addon before real cleanup.

    Source bytes and all PG identities/values are checked before changing the
    loaded set. Labels/required/type metadata may legitimately differ during
    handover; original PK/model/name/state must remain exact. No sudo write,
    artificial owner alias, field coercion or noupdate modification is made.
    """
    gate.require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+', env.cr.dbname),
                 'private-native-anchor-required')
    gate.require(type(env.registry.loaded_xmlids) is set, 'real-official-loaded-xmlids-set-required')
    gate.require(capsule_sha256 == CAPSULE_SHA256, 'unreviewed-original-capsule-version')
    capsule = _read_sealed(capsule_path, capsule_sha256)
    identity = _read_sealed(original_identity_path, original_identity_sha256)
    contract = _contract(capsule, identity)
    _require_oca_models(env)
    cr = env.cr
    cr.execute("SELECT name FROM ir_module_module WHERE state='to remove' OR "
        "(state IN ('installed','to install','to upgrade') AND (license='OEEL-1' "
        "OR name IN ('hr_payroll','hr_payroll_account'))) ORDER BY name")
    gate.require(not cr.fetchall(), 'native-enterprise-or-uninstall-state-forbidden')
    proofs = []
    for item in contract:
        alias = item['alias']
        cr.execute('SELECT id,module,name,model,res_id,noupdate FROM ir_model_data '
            'WHERE id=%s OR (module=%s AND name=%s) ORDER BY id',
            [alias['id'], alias['module'], alias['name']])
        actual = [dict(zip(('id', 'module', 'name', 'model', 'res_id', 'noupdate'), row))
                  for row in cr.fetchall()]
        gate.require(actual == [alias], 'retained-alias-pk-binding-or-noupdate-drift')
        cr.execute('SELECT id,model,state FROM ir_model WHERE id=%s OR model=%s ORDER BY id',
                   [item['model']['id'], item['model']['model']])
        gate.require(cr.fetchall() == [tuple(item['model'][name] for name in ('id', 'model', 'state'))],
                     'retained-model-pk-or-state-drift')
        cr.execute('SELECT id,model,name,state FROM ir_model_fields WHERE id=ANY(%s) ORDER BY id',
                   [[row['id'] for row in item['fields']]])
        expected = sorted((row['id'], row['model'], row['name'], row['state']) for row in item['fields'])
        gate.require(cr.fetchall() == expected, 'retained-field-pk-model-name-or-state-drift')
        # Parse original numeric JSON in PostgreSQL, not through Python float.
        # Compare only source columns: nullable new CE columns are not defaults
        # authorizing a rewrite of any original value, NULL or audit field.
        cr.execute('SELECT projection.payload=source.payload,md5(projection.payload::text),'
            'md5(source.payload::text) FROM ' + gate.identifier(item['table']) + ' t '
            'CROSS JOIN (SELECT %s::jsonb AS payload) source CROSS JOIN LATERAL '
            '(SELECT jsonb_object_agg(k,to_jsonb(t)->k) AS payload '
            'FROM jsonb_object_keys(source.payload) k) projection WHERE t.id=%s',
            [item['raw_json'], alias['res_id']])
        values = cr.fetchall()
        gate.require(len(values) == 1 and values[0][0] is True
            and values[0][1] == values[0][2], 'retained-original-master-values-or-null-drift')
        proofs.append({'xmlid': alias['module'] + '.' + alias['name'],
            'metadata_id': alias['id'], 'model': alias['model'], 'res_id': alias['res_id'],
            'noupdate': False, 'noupdate_exact': True, 'original_values_md5': values[0][1]})
    # No partial retention: only after both records and every field identity pass.
    additions = {row['xmlid'] for row in proofs}
    before = set(env.registry.loaded_xmlids)
    env.registry.loaded_xmlids.update(additions)
    gate.require(env.registry.loaded_xmlids == before | additions, 'unexpected-loaded-xmlids-mutation')
    return {'schema': 1, 'private_anchor': env.cr.dbname, 'aliases': proofs,
        'exact_two_aliases_retained': True, 'sql_writes': False, 'noupdate_written': False,
        'source_capsule_sha256': capsule_sha256, 'original_identity_sha256': original_identity_sha256,
        'retention_is_not_adoption': True, 'all_other_namespaces_or_aliases_retained': False}
