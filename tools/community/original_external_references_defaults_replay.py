"""Replay the pinned typed-defaults archive using only sources exported from Git.

Filesystem/JSON/static replay only. Never extracts or executes archive Python,
opens SQL, starts Odoo, evaluates the anchored writer policy or alters evidence.
"""
import argparse
from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tarfile
import tempfile


REVISION = '42d2e0ef'
ARCHIVE_SHA256 = 'ef1ab1979b6131428c2b9d85bc1a5c44314e4abcdbf377c5ae0189b7ab19579c'
SOURCES = (
    'original_external_references.py', 'original_external_references_dump.py',
    'original_external_references_registry.py', 'original_external_references_related.py',
    'original_external_references_defaults.py', 'original_external_references_anchored.py',
    'payroll_configuration_adoption_preflight.py', 'audit_stock_package_representation.py',
)
COPIES = ('community-H', 'community-D', 'native-D')
EXPECTED_COUNTS = {'community-H': (30, 24, 6, 45, 113, 97, 16),
    'community-D': (30, 24, 6, 45, 113, 97, 16), 'native-D': (58, 46, 12, 68, 24, 0, 24)}


def require(value, code):
    if not value:
        raise ValueError(code)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def file_inventory():
    names = {'typed-defaults/source/' + name for name in SOURCES}
    names |= {f'{folder}/{name}.json' for folder in ('references', 'registries') for name in COPIES}
    names |= {'typed-defaults/evidence/' + name + '.json' for name in COPIES}
    names |= {'typed-defaults/evidence/summary.json', 'typed-defaults/source-files.json'}
    return names


def validate_inventory(files, manifest):
    require(manifest.get('schema') == 1 and manifest.get('git_commit') == REVISION
        and manifest.get('database_writes') is False and manifest.get('writer_authorized') is False
        and manifest.get('global_guard_counts_unchanged') is True
        and manifest.get('anchored_policy_live_handover_evaluated') is False, 'manifest-policy-differs')
    expected = file_inventory()
    require(len(expected) == 19 and set(files) == expected | {'export-manifest.json'}
        and set(manifest.get('files', {})) == expected, 'exact19-file-inventory-required')
    require(all(sha(files[name]) == manifest['files'][name] for name in expected), 'manifest-file-sha256-differs')


def read_archive(path):
    raw_sha = sha(Path(path).read_bytes())
    require(raw_sha == ARCHIVE_SHA256, 'pinned-archive-sha256-differs')
    files = {}
    with tarfile.open(path, 'r:gz') as archive:
        for member in archive.getmembers():
            if member.isdir():
                continue
            name = PurePosixPath(member.name)
            require(member.isfile() and not member.issym() and not member.islnk()
                and not name.is_absolute() and '..' not in name.parts
                and str(name) == member.name and member.name not in files
                and 0 <= member.size <= 32 * 1024**2, 'unsafe-or-duplicate-archive-member')
            files[member.name] = archive.extractfile(member).read()
    require(sum(map(len, files.values())) <= 64 * 1024**2, 'archive-expanded-size-not-admitted')
    manifest = json.loads(files['export-manifest.json'])
    validate_inventory(files, manifest)
    return files, manifest


def replay_copy(name, files, module):
    reference_raw, registry_raw, report_raw = (files[path] for path in (
        'references/' + name + '.json', 'registries/' + name + '.json',
        'typed-defaults/evidence/' + name + '.json'))
    reference, registry, report = map(json.loads, (reference_raw, registry_raw, report_raw))
    require(report['read_only'] is True and report['database_writes'] is False and report['orm_loaded'] is False
        and report['conditions_or_code_evaluated'] is False and report['writer_authorized'] is False
        and report['inherited_guards_unchanged'] is True and report['two_snapshots_exact'] is True,
        'readonly-report-policy-differs')
    require(report['source_reference_sha256'] == sha(reference_raw) and report['registry_sha256'] == sha(registry_raw)
        and reference['registry_proof_sha256'] == sha(registry_raw)
        and report['tool_sha256'] == sha(files['typed-defaults/source/original_external_references_defaults.py']),
        'reference-registry-tool-links-differ')
    binding = module.contract(reference, registry)
    require(binding == report['physical_contract'], 'physical-default-binding-replay-differs')
    observation = report['observations']
    require(observation['transaction'] == [{'mode': 'on'}], 'readonly-snapshot-receipt-required')
    classified = module.classify(observation['defaults'], reference, registry)
    require(classified == report['classified_defaults'], 'classification-replay-differs')
    endpoints, contracts = module.endpoint_plan(observation['defaults'], classified, registry)
    queries = dict(module.queries(binding), **endpoints)
    require(queries == report['queries'] and set(queries) == set(observation) and len(queries) == 12,
        'exact-query-and-observation-plan-differs')
    identities = []
    for contract in contracts:
        rows = observation[contract['observation']]
        require(set(contract['ids']) == {row['id'] for row in rows} and len(rows) == len(contract['ids']),
            'default-endpoint-missing-or-ambiguous')
        identities.append(dict(contract, rows=rows,
            aliases=observation.get(contract.get('alias_observation'), [])))
    require(identities == report['endpoint_identities'], 'endpoint-identity-replay-differs')
    summary = {'defaults': len(classified), 'states': dict(Counter(row['status'] for row in classified)),
        'typed_targets': sum(len(row['targets']) for row in classified),
        'adoption_target_hits': sum(len(row['adoption_target_hits']) for row in classified),
        'all_defaults_classified': all(row['status'] == 'typed' for row in classified),
        'typed_endpoint_records_and_aliases_captured': sum(len(row['rows']) for row in identities),
        'writer_authorized': False}
    partition = module.guard_partition(reference)
    require(summary == report['summary'] and report['inherited_guard_count'] == len(reference['blockers'])
        and partition == report['inherited_guard_partition'], 'summary-or-inherited-guards-replay-differs')
    counts = (summary['defaults'], summary['states']['typed'], summary['states']['unresolved'],
        summary['typed_endpoint_records_and_aliases_captured'], report['inherited_guard_count'],
        len(partition['identity_target_deltas_requiring_explicit_plan']),
        len(partition['unresolved_binding_or_semantic_guards']))
    require(counts == EXPECTED_COUNTS[name] and summary['adoption_target_hits'] == 0,
        'expected-real-counts-differ')
    return {'summary': summary, 'inherited_guard_count': counts[4],
        'partition': {'identity_target_deltas': counts[5], 'unresolved_binding_or_semantic': counts[6]},
        'queries_per_complete_snapshot': len(queries), 'replay_exact': True,
        'runtime_two_snapshots_exact_receipt': True,
        'two_raw_snapshots_independently_replayed': False}


def replay(archive, repo):
    files, manifest = read_archive(archive)
    repo = Path(repo).resolve()
    trusted = {name: subprocess.check_output(['git', '-C', str(repo), 'show',
        REVISION + ':tools/community/' + name]) for name in SOURCES}
    require(all(raw == files['typed-defaults/source/' + name] for name, raw in trusted.items()),
        'archive-source-is-not-exact-trusted-git-source')
    listed = json.loads(files['typed-defaults/source-files.json'])
    require(listed['git_commit'] == REVISION and listed['base'] == 'a983b501'
        and listed['files'] == {name: sha(raw) for name, raw in trusted.items()}, 'source-file-receipt-differs')
    # The archive is never placed on sys.path. Only git-show bytes enter this
    # new directory. Existing imports are refused to prevent an ambient module
    # from shadowing that trust boundary.
    names = [name[:-3] for name in SOURCES]
    require(not any(name in sys.modules for name in names), 'fresh-replay-process-required')
    previous_bytecode = sys.dont_write_bytecode
    with tempfile.TemporaryDirectory(prefix='trusted-typed-defaults-') as temporary:
        for name, raw in trusted.items():
            Path(temporary, name).write_bytes(raw)
        sys.path.insert(0, temporary)
        sys.dont_write_bytecode = True
        try:
            module = importlib.import_module('original_external_references_defaults')
            # No source helper may accidentally turn replay into a live query.
            def no_database(*args, **kwargs):
                raise ValueError('database-operation-forbidden-in-offline-replay')
            module.refs.run_snapshot = no_database
            results = {name: replay_copy(name, files, module) for name in COPIES}
        finally:
            sys.path.remove(temporary)
            sys.dont_write_bytecode = previous_bytecode
            for name in names:
                sys.modules.pop(name, None)
    source_summary = json.loads(files['typed-defaults/evidence/summary.json'])
    require(source_summary['schema'] == 1 and source_summary['git_commit'] == REVISION
        and source_summary['database_writes'] is False and set(source_summary['databases']) == set(COPIES),
        'aggregate-summary-schema-differs')
    for name, result in results.items():
        expected = dict(result['summary'], inherited_guards_unchanged=True,
            inherited_guard_count=result['inherited_guard_count'],
            identity_target_deltas=result['partition']['identity_target_deltas'],
            unresolved_binding_guards=result['partition']['unresolved_binding_or_semantic'],
            proof_sha256=sha(files['typed-defaults/evidence/' + name + '.json']))
        require(source_summary['databases'][name] == expected, 'aggregate-summary-replay-differs')
    return {'schema': 1, 'git_commit': REVISION, 'archive_sha256': ARCHIVE_SHA256,
        'manifest_sha256': sha(files['export-manifest.json']), 'manifest_files_exact': len(manifest['files']),
        'all_actual_archive_files_exact': len(files), 'git_sources_exact': len(trusted),
        'database_access': False, 'artifact_code_executed': False,
        'anchored_policy_live_handover_evaluated': False, 'results': results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'repo', 'output'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(args.output.is_absolute() and args.output.parent.is_dir() and not args.output.exists(),
        'new-private-replay-output-required')
    result = replay(args.archive, args.repo)
    with os.fdopen(os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'w') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print('TYPED_DEFAULTS_OFFLINE_REPLAY_OK', result['manifest_files_exact'], result['git_sources_exact'])


if __name__ == '__main__':
    main()
