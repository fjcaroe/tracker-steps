"""Verify exported admission-upgrade evidence using files and versioned code only.

No Odoo process, SQL, external request or evidence-file code is executed here.
The dump/filestore may be intentionally absent from the privacy-preserving
export: their decode/preservation remains an attestation of the sealed runner.
"""
import ast
from decimal import Decimal
import hashlib
import importlib.util
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys


RUNNER = 'tools/community/validate_payroll_admission_upgrade.py'
DEPENDENCY = 'tools/community/validate_payroll_properties_upgrade.py'
PIN = 'tools/community/simpledigital_runtime_source.json'
BUILDER = 'tools/community/build_simpledigital_candidate.py'
TRUE_FLAGS = ('actual_upgrade', 'normal_actor', 'real_oca_engine', 'historical_read_unchanged',
    'synthetic_fixture_only', 'synthetic_paid_marker', 'current_wage_changed_after_closure',
    'original_required_admission_normal_actor', 'original_unpaid_inverse_preserved',
    'frozen_compute_preserved', 'closed_compute_refused', 'source_unchanged',
    'source_filestore_unchanged', 'backup_decoded', 'runtime_network_isolated', 'postgres_unix_socket')
FALSE_FLAGS = ('closed_payroll_recomputed', 'payment_workflow_certified', 'customer_payroll_certified',
    'engine_conversion', 'writes_to_source', 'module_states_rewritten', 'full_community_conversion')


def _sha(blob):
    return hashlib.sha256(blob).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        assert key not in result, 'Duplicate JSON key in private evidence'
        result[key] = value
    return result


def _json(blob):
    def reject_constant(value):
        raise ValueError('Non-finite JSON evidence value')
    def finite_float(value):
        parsed = float(value)
        assert math.isfinite(parsed), 'Non-finite JSON evidence value'
        return parsed
    return json.loads(blob, object_pairs_hook=_unique_object, parse_constant=reject_constant, parse_float=finite_float)


def _blob(folder, name):
    path = folder / name
    assert path.is_file() and not path.is_symlink(), 'Missing or linked evidence file: ' + name
    return path.read_bytes()


def _load(folder, name):
    return _json(_blob(folder, name))


def _hash(value):
    assert isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'Invalid evidence hash'
    return value


def _packet(packet):
    assert isinstance(packet, dict) and packet, 'Empty source packet'
    grouped = {}
    for name, value in packet.items():
        path = PurePosixPath(name)
        assert isinstance(name, str) and not path.is_absolute() and len(path.parts) >= 2
        assert '\\' not in name and '..' not in path.parts and str(path) == name, 'Unsafe source packet name'
        assert re.fullmatch('[A-Za-z0-9_]+', path.parts[0])
        grouped.setdefault(path.parts[0], {})['/'.join(path.parts[1:])] = _hash(value)
    return grouped


def _load_versioned_helper(folder, git_source, proof):
    repo = Path(__file__).resolve().parents[2]
    executed = {'upgrade-probe.py': RUNNER, Path(DEPENDENCY).name: DEPENDENCY}
    seals = _load(folder, 'probe-dependencies.json')
    assert set(seals) == set(executed), 'Unexpected probe dependency set'
    assert proof['probe_dependencies_sha256'] == _sha(_blob(folder, 'probe-dependencies.json'))
    for name, source_name in executed.items():
        blob = _blob(folder, name)
        assert _sha(blob) == seals[name], 'Executed probe/dependency hash mismatch'
        trusted = git_source[source_name]
        assert isinstance(trusted, bytes)
        assert blob.replace(b'\r\n', b'\n') == trusted.replace(b'\r\n', b'\n'), 'Executed probe/dependency differs from Git'
        local = repo / source_name
        assert local.is_file() and not local.is_symlink()
        assert local.read_bytes().replace(b'\r\n', b'\n') == trusted.replace(b'\r\n', b'\n'), 'Local static helper differs from Git'
    assert proof['tool_sha256'] == seals['upgrade-probe.py']
    assert proof['helper_sha256'] == seals[Path(DEPENDENCY).name]
    # Import the already checked repository file, never the exported probe.
    spec = importlib.util.spec_from_file_location('_verified_payroll_admission', repo / RUNNER)
    helper = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        spec.loader.exec_module(helper)
    finally:
        sys.dont_write_bytecode = previous
    return helper


def _verify_package(package, baseline_packet, consumer_packet, current_packet, git_source, helper):
    assert len(package) == 95 and {'payroll', 'payroll_account'} <= package.keys(), 'Accepted F installed set is incomplete'
    baseline, consumers, current = _packet(baseline_packet), _packet(consumer_packet), _packet(current_packet)
    assert set(consumers) <= set(package) and set(consumer_packet) <= set(baseline_packet), 'Unapproved consumer derivation'
    checked = 0
    for module, phases in package.items():
        assert re.fullmatch('[A-Za-z0-9_]+', module) and set(phases) == {'legacy', 'candidate'}
        for phase in phases.values():
            assert '__manifest__.py' in phase, 'Installed addon manifest missing'
            _packet({module + '/' + name: value for name, value in phase.items()})
        if module in baseline:
            expected = dict(baseline[module])
            expected.update(consumers.get(module, {}))
            assert phases['legacy'] == expected, 'Accepted F legacy addon differs: ' + module
            checked += 1
        if module in helper.VERSIONS:
            assert phases['candidate'] == current[module], 'Current candidate addon differs: ' + module
            tracked = {name[len(module) + 1:]: _sha(blob) for name, blob in git_source.items()
                if name.startswith(module + '/')}
            assert tracked == current[module], 'Current addon packet differs from Git: ' + module
            manifest = ast.literal_eval(git_source[module + '/__manifest__.py'].decode('utf-8-sig'))
            assert manifest['version'] == helper.VERSIONS[module][1] and manifest['license'] == 'LGPL-3'
        else:
            assert phases['candidate'] == phases['legacy'], 'Unrelated addon changed: ' + module
    assert set(helper.VERSIONS) <= package.keys() and checked > len(helper.VERSIONS)
    return checked


def _verify_fixture(seed, marker, proof):
    assert seed['actor'] > 1 and seed['normal_actor'] is True and seed['real_oca_engine'] is True
    assert seed['synthetic_fixture_only'] is True and seed['synthetic_paid_marker'] is True
    assert seed['payment_workflow_certified'] is False and seed['confirmation_uses_existing_oca_draft_option'] is True
    assert seed['current_wage_changed_after_closure'] is True
    assert marker['synthetic_fixture_only'] is True and marker['database'] == proof['database']
    assert marker['state'] == 'done' and marker['step_history_locked'] is True
    assert marker['paid'] is None or marker['paid'] is False
    assert marker['original_not_paid_predicate_matches'] is (marker['paid'] is False)
    assert marker['null_aware_predicate_matches'] is True
    assert proof['synthetic_paid_marker_original_sql_value'] is seed['synthetic_paid_marker_original_sql_value'] is marker['paid']
    before = seed['raw_rows']
    slip = next(row for row in before['hr_payslip'] if row['id'] == seed['slip'])
    assert (marker['id'], marker['employee_id'], marker['contract_id'], marker['company_id']) == (
        seed['slip'], slip['employee_id'], seed['contract'], seed['company'])
    assert slip['state'] == 'done' and slip['paid'] is True and slip['step_history_locked'] is True
    assert slip['contract_id'] == seed['contract'] and slip['company_id'] == seed['company'] and slip['move_id'] == seed['move']
    assert all(slip[name] == value for name, value in seed['draft_amounts'].items())
    contract = next(row for row in before['hr_contract'] if row['id'] == seed['contract'])
    assert contract['wage'] == 1200000, 'Changed current-wage witness is missing'
    days = {row['id']: row for row in before['hr_payslip_worked_days']}
    for ident, values in ((seed['day'], seed['draft_day_values']), (seed['unpaid_day'], seed['unpaid_day_values'])):
        assert days[ident]['payslip_id'] == seed['slip'] and all(days[ident][name] == value for name, value in values.items())
    assert days[seed['day']]['is_paid'] is True and days[seed['day']]['amount'] > 0
    assert days[seed['unpaid_day']]['is_paid'] is False and days[seed['unpaid_day']]['amount'] == 0
    assert days[seed['unpaid_day']]['work_entry_type_id'] == seed['unpaid_type']
    relation = before['relations']['hr_payroll_structure_hr_work_entry_type_rel']
    assert {'hr_payroll_structure_id': seed['structure'], 'hr_work_entry_type_id': seed['unpaid_type']} in relation
    moves = [row for row in before['account_move'] if row['id'] == seed['move']]
    assert len(moves) == 1 and moves[0]['state'] == 'posted'
    entries = [row for row in before['account_move_line'] if row['move_id'] == seed['move']]
    assert len(entries) >= 2 and sum(Decimal(str(row['debit'])) for row in entries) > 0
    assert abs(sum(Decimal(str(row['debit'])) - Decimal(str(row['credit'])) for row in entries)) < Decimal('.00001')
    lines = [row for row in before['hr_payslip_line'] if row['slip_id'] == seed['slip']]
    primary = [row for row in lines if row['salary_rule_id'] == seed['rule']]
    assert primary and all(type(row['note']) is str and row['note'] and row['analytic_account_id'] == seed['analytic'] for row in primary)
    assert {'BASIC', 'GROSS', 'NET'} <= {row['code'] for row in lines}
    rule = next(row for row in before['hr_salary_rule'] if row['id'] == seed['rule'])
    assert isinstance(rule['note'], dict) and rule['note'].get('en_US')
    assert rule['analytic_account_id'] == {str(seed['company']): seed['analytic']}
    assert type(rule['analytic_account_id'][str(seed['company'])]) is int


def verify_admission_evidence(folder, git_source, current_packet):
    """Return a bounded proof; reject provenance/value drift without any writes."""
    folder = Path(folder).resolve()
    proof = _load(folder, 'passed.json')
    helper = _load_versioned_helper(folder, git_source, proof)
    helper.configure_profile(proof.get('upgrade_profile', 'admission'))
    assert re.fullmatch(helper.DATABASE_PATTERN, proof['database']) and proof['source_database'] == helper.SOURCE_DB
    assert proof['original_versions'] == {name: values[0] for name, values in helper.VERSIONS.items()}
    assert proof['target_versions'] == {name: values[1] for name, values in helper.VERSIONS.items()}
    assert proof['official_community_revision'] == helper.OFFICIAL_PIN and proof['oca_revision'] == helper.OCA_PIN
    assert all(proof[name] is True for name in TRUE_FLAGS) and all(proof[name] is False for name in FALSE_FLAGS)
    verified = _load(folder, 'verified.json')
    assert all(helper.digest(proof[name]) == helper.digest(value) for name, value in verified.items()), 'Passed proof differs from runtime verification'
    for name, key in (('seed.json', 'seed_sha256'), ('rows-after.json', 'rows_after_sha256'),
        ('xml-config-upgrade-audit.json', 'xml_config_upgrade_audit_sha256')):
        assert _sha(_blob(folder, name)) == proof[key], 'Changed raw evidence: ' + name
    seed, after = _load(folder, 'seed.json'), _load(folder, 'rows-after.json')
    marker_bytes = _blob(folder, 'synthetic-paid-marker-before.json')
    assert _sha(marker_bytes) == proof['synthetic_paid_marker_witness_sha256'] == seed['synthetic_paid_marker_witness_sha256']
    _verify_fixture(seed, _json(marker_bytes), proof)
    audit = _load(folder, 'xml-config-upgrade-audit.json')
    assert audit['database'] == proof['database']
    log_bytes = _blob(folder, 'upgrade.log')
    assert _sha(log_bytes) == audit['upgrade_log_sha256']
    assert audit['reload_log_lines'] == [line for line in log_bytes.decode().splitlines()
        if 'odoo.modules.loading: loading l10n_cl_simpledigital_payroll/' + helper.CONFIG_XML in line]
    for name in ('upgrade.log', 'upgrade-bootstrap.log', 'legacy-seed-bootstrap.log', 'upgraded-verify-bootstrap.log'):
        text = _blob(folder, name).decode(errors='replace')
        assert 'Traceback (most recent call last)' not in text and not re.search(r' (ERROR|CRITICAL) ', text), 'Failed private upgrade log'
    pin_bytes = _blob(folder, 'xml-config-source-pin.json')
    assert _sha(pin_bytes) == audit['source_pin_manifest_sha256']
    assert pin_bytes.replace(b'\r\n', b'\n') == git_source[PIN].replace(b'\r\n', b'\n')
    pin = _json(pin_bytes)
    assert pin['license'] == 'AGPL-3' and len(pin['files']) == 52 and helper.digest(pin['files']) == helper.PROVIDER_SOURCE_FILES_SHA256
    derivations = []
    for phase in ('legacy', 'candidate'):
        content = _blob(folder, phase + '-provider-derivation.json')
        assert _sha(content) == audit[phase + '_provider_derivation_sha256'] == helper.PROVIDER_DERIVATION_SHA256
        derived = _json(content)
        assert derived['license'] == 'AGPL-3' and derived['source_files'] == pin['files']
        assert derived['builder_sha256'] == audit[phase + '_builder_sha256'] == _sha(git_source[BUILDER]) == helper.PROVIDER_BUILDER_SHA256
        assert helper.CONFIG_XML in derived['transformed_files'] and derived['identity_conversion_accepted'] is False
        derivations.append(content)
    assert derivations[0] == derivations[1]
    for phase in ('before', 'after'):
        content = _blob(folder, 'upgrade-sql-clock-' + phase + '.json')
        assert _sha(content) == audit['sql_clock_' + phase + '_sha256'] and _json(content)['utc'] == audit['sql_utc_' + phase]
    check = helper.verify_rows(seed['raw_rows'], after, audit)
    assert all(helper.digest(proof[name]) == helper.digest(value) for name, value in check.items())
    assert check['expected_write_date_changes'] == 2 and check['all_original_raw_fields_exact'] is False
    source_before = _load(folder, 'source-before.json')
    assert helper.digest(source_before) == helper.digest(_load(folder, 'source-after.json')) == proof['source_snapshot_sha256']
    assert 'sequence_values' in source_before and set(helper.RAW_TABLES) <= source_before.keys()
    assert {'ir_model', 'ir_model_fields', 'ir_model_data', 'ir_module_module'} <= source_before.keys()
    for table, value in source_before.items():
        if table == 'sequence_values':
            assert all(re.fullmatch(r'-?\d+:(true|false)', item) for item in value.values())
        else:
            assert type(value['rows']) is int and value['rows'] >= 0
            _hash(value['sha256'])
    filestore = _load(folder, 'source-filestore.json')
    assert isinstance(filestore, dict)
    for name, value in filestore.items():
        path = PurePosixPath(name)
        assert not path.is_absolute() and '..' not in path.parts and '\\' not in name
        _hash(value)
    baseline_bytes = _blob(folder, 'source-acceptance.json')
    assert _sha(baseline_bytes) == proof['source_acceptance_sha256']
    baseline = _json(baseline_bytes)
    assert baseline['mode'] == 'community' and baseline['database'] == helper.SOURCE_DB
    assert baseline['counts'] == {'installed': 95, 'enterprise': 0}
    assert baseline['official_community_revision'] == helper.OFFICIAL_PIN and baseline['oca_revision'] == helper.OCA_PIN
    baseline_packet_bytes = _blob(folder, 'source-packet.json')
    assert _sha(baseline_packet_bytes) == baseline['source_files_sha256']
    consumers = _load(folder, 'source-consumer-packet.json')
    assert helper.digest(consumers) == proof['source_consumer_files_sha256']
    package_bytes = _blob(folder, 'package-files.json')
    package = _json(package_bytes)
    assert helper.digest(package) == proof['package_files_sha256'] and _sha(package_bytes) == audit['package_files_sha256']
    legacy_checked = _verify_package(package, _json(baseline_packet_bytes), consumers, current_packet, git_source, helper)
    for phase in ('legacy', 'candidate'):
        provider = package['l10n_cl_simpledigital_payroll'][phase]
        assert set(provider) == set(pin['files']) and provider[helper.CONFIG_XML] == helper.DERIVED_CONFIG_XML_SHA256
    _hash(proof['backup_sha256'])
    decoded = _blob(folder, 'decode.log').decode(errors='replace')
    assert 'pg_restore: error:' not in decoded and 'errors ignored on restore' not in decoded
    # The frozen runner checked the decoder exit code; an exported hash is not
    # a second decoding of a backup omitted from this evidence folder.
    backup_checked = (folder / 'source.dump').exists()
    if backup_checked:
        path = folder / 'source.dump'
        assert path.is_file() and not path.is_symlink()
        with path.open('rb') as stream:
            hasher = hashlib.sha256()
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                hasher.update(chunk)
        assert hasher.hexdigest() == proof['backup_sha256']
    keys = ('original_versions', 'target_versions', 'raw_rows_compared', 'raw_rows_preserved',
        'all_original_raw_fields_exact', 'expected_write_date_changes', 'expected_write_date_change_records',
        'write_date_exception_justification', 'model_ids_preserved', 'field_ids_preserved',
        'historical_read_unchanged', 'source_unchanged', 'source_filestore_unchanged',
        'synthetic_paid_marker', 'payment_workflow_certified', 'customer_payroll_certified',
        'full_community_conversion', 'runtime_network_isolated', 'postgres_unix_socket',
        'rule_json_properties_preserved_exactly', 'original_required_admission_normal_actor',
        'original_unpaid_inverse_preserved', 'frozen_compute_preserved', 'closed_compute_refused',
        'structure_type_name_not_null', 'rule_category_ondelete', 'line_category_ondelete')
    return dict({key: proof[key] for key in keys}, source_installed_modules=95, source_enterprise_modules=0,
        legacy_owned_addons_checked=legacy_checked, current_addons_checked=2, backup_decoded=True,
        backup_archive_hash_checked=backup_checked, backup_redecoded_offline=False,
        source_filestore_manifest_entries=len(filestore), filesystem_only=True)
