"""Capture and restore the filestore objects referenced by a sealed SyS SQL pair."""

import argparse
import configparser
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tarfile
import tempfile

from restore_sys_previred_pair import LOCK, query, require, save


OBJECT = re.compile(r'([0-9a-f]{2})/([0-9a-f]{40})')


def digest(path, algorithm='sha256'):
    with path.open('rb') as stream:
        value = hashlib.new(algorithm)
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def attachments(database, read_query=query):
    prefix = (r'(?:(?:COMMUNITY|MANAGEMENT_QA)_SYS_PREVIRED_|MANAGEMENT_QA_(?:STEPS|CERRO)_CUSTODY_|'
              r'COMMUNITY_(?:PAYROLL_CERRO_REVIEW|CERRO_PAYROLL_RECOVERY|STEPS_CRM)_)')
    require(re.fullmatch(prefix + r'[A-Z0-9_]{1,32}', database), 'sys-store-private-database-required')
    return json.loads(read_query(database, """
        SELECT json_build_object(
            'database', current_database(),
            'rows', count(*),
            'objects', count(*) FILTER (WHERE store_fname IS NOT NULL),
            'rows_sha256', encode(sha256(convert_to(
                string_agg(encode(sha256(convert_to(to_jsonb(a)::text, 'UTF8')), 'hex'),
                           '' ORDER BY id), 'UTF8')), 'hex'),
            'references', json_agg(DISTINCT jsonb_build_array(store_fname, checksum, file_size))
                          FILTER (WHERE store_fname IS NOT NULL))
        FROM public.ir_attachment a
    """))


def object_catalog(references):
    catalog = {}
    for name, checksum, size in references:
        match = OBJECT.fullmatch(name)
        require(match and match[1] == match[2][:2] and match[2] == checksum,
                'sys-store-invalid-content-address')
        require(type(size) is int and size >= 0, 'sys-store-invalid-size')
        require(catalog.setdefault(name, size) == size, 'sys-store-conflicting-size')
    return catalog


def restore_objects(archive, target, catalog):
    pending = set(catalog)
    with tarfile.open(archive, 'r|') as source:
        for member in source:
            require(member.name in pending and member.isfile()
                    and member.size == catalog[member.name], 'sys-store-unexpected-archive-member')
            pending.remove(member.name)
            destination = target / member.name
            destination.parent.mkdir(exist_ok=True)
            with source.extractfile(member) as stored, destination.open('xb') as output:
                shutil.copyfileobj(stored, output)
            require(destination.stat().st_size == catalog[member.name]
                    and digest(destination, 'sha1') == destination.name, 'sys-store-restore-checksum')
    require(not pending, 'sys-store-incomplete-archive')


def capture(source, output, catalog, recovered=None):
    payload_bytes = sum(catalog.values())
    require(shutil.disk_usage(output).free >= 2 * 1024**3 + 2 * payload_bytes + 4096 * len(catalog),
            'sys-store-insufficient-reserve')
    paths = {}
    recovered_names = []
    for name, size in catalog.items():
        path = source / name
        if recovered is not None and not os.path.lexists(path):
            path = recovered / name
            recovered_names.append(name)
        require(path.is_file() and path.resolve() == path and path.stat().st_size == size,
                'sys-store-missing-or-invalid-source-object')
        paths[name] = path
    with tempfile.TemporaryDirectory(prefix='verification-', dir=output) as stage:
        archive = Path(stage) / 'filestore.tar'
        with tarfile.open(archive, 'x') as bundle:
            for name in sorted(catalog):
                bundle.add(paths[name], arcname=name, recursive=False)
        target = Path(stage) / 'restored'
        target.mkdir()
        restore_objects(archive, target, catalog)
        archive_sha = digest(archive)
        os.link(archive, output / archive.name)
    return {'archive_sha256': archive_sha, 'payload_bytes': payload_bytes,
            'verified_objects': len(catalog), 'recovered_objects': sorted(recovered_names)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pair', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--recovered', type=Path,
                        help='Private sibling directory of recovered content-addressed objects')
    args = parser.parse_args()
    os.umask(0o077)
    with open(LOCK, 'rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        backup = json.loads((args.pair / 'backup.json').read_bytes())
        require(backup['source'] == 'SyS' and backup['sha256'] == digest(args.pair / 'sys.dump'),
                'sys-store-sql-dump-mismatch')
        manifests = []
        suffixes = []
        for prefix, stage in (('MANAGEMENT_QA_SYS_PREVIRED_', 'reference-restored'),
                              ('COMMUNITY_SYS_PREVIRED_', 'candidate-restored')):
            receipt = json.loads((args.pair / (stage + '.json')).read_bytes())
            database = receipt['snapshot']['database']
            require(database.startswith(prefix) and receipt['stage'] == stage and receipt['preserved']
                    and receipt['backup_sha256'] == backup['sha256'], 'sys-store-pair-receipt-mismatch')
            manifest = attachments(database)
            require(manifest.pop('database') == database and manifest['objects'] > 0,
                    'sys-store-pair-attachments-required')
            manifest['references'] = object_catalog(manifest['references'])
            manifests.append(manifest)
            suffixes.append(database[len(prefix):])
        require(suffixes[0] == suffixes[1] and manifests[0] == manifests[1], 'sys-store-pair-drift')

        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read('/etc/odoo18-sys.conf')
        source = (Path(config['options']['data_dir']) / 'filestore' / 'SyS').resolve(strict=True)
        require(source.name == 'SyS' and source.parent.name == 'filestore',
                'sys-store-production-source-identity')
        require(args.output.is_absolute() and args.output.parent.resolve() == args.pair.resolve()
                and not args.output.resolve().is_relative_to(source),
                'sys-store-private-output-required')
        if args.recovered is not None:
            require(args.recovered.is_absolute() and args.recovered.resolve() == args.recovered
                    and args.recovered.parent == args.pair.resolve() and args.recovered.is_dir()
                    and not args.recovered.is_relative_to(source),
                    'sys-store-private-recovery-source-required')
        args.output.mkdir(mode=0o700)
        manifest = manifests[0]
        checked = capture(source, args.output, manifest.pop('references'), args.recovered)
        save(args.output, 'filestore-receipt.json', {
            **manifest, **checked, 'sql_backup_sha256': backup['sha256'],
            'source': 'SyS', 'same_attachment_rows_in_sql_pair': True,
            'verified_restore': True, 'upgrade_authorized': False,
        })
        print(json.dumps(checked, sort_keys=True))


if __name__ == '__main__':
    main()
