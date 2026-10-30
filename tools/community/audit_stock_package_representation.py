"""Reconstruct five stock package rows from a private dump, using SELECT only.

No restore, DDL, COPY execution, ORM, float conversion or business writes.
COPY text escaping: https://www.postgresql.org/docs/15/sql-copy.html
Only reviewed column/type identifiers become SQL; values become hex literals.
Raw rows leave PostgreSQL solely for a new private proof, never stdout.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


TABLE = 'stock_package_type'
NATIVE_ROOT_PREFIXES = ('community-original-bootstrap-', 'community-original-contracts-',
                        'community-multifront-')
COLUMNS = (
    ('id', 'integer', True), ('sequence', 'integer', False),
    ('company_id', 'integer', False), ('create_uid', 'integer', False),
    ('write_uid', 'integer', False), ('name', 'character varying', True),
    ('barcode', 'character varying', False),
    ('create_date', 'timestamp without time zone', False),
    ('write_date', 'timestamp without time zone', False),
    ('height', 'double precision', False), ('width', 'double precision', False),
    ('packaging_length', 'double precision', False), ('base_weight', 'numeric', False),
    ('max_weight', 'double precision', False),
    ('step_export_boxes_per_pallet', 'numeric', False),
    ('step_export_pallets_20', 'numeric', False),
    ('step_export_pallets_40', 'numeric', False),
    ('fruit_package_group', 'character varying', False),
    ('pallets_per_aircraft', 'numeric', False),
)
NUMBER = re.compile(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?\Z')
NORMALIZER = "(SELECT jsonb_object_agg(key,CASE WHEN jsonb_typeof(value)='number' " \
    "THEN to_jsonb((CASE WHEN strpos(value#>>'{}','.')>0 THEN " \
    "rtrim(rtrim(value#>>'{}','0'),'.') ELSE value#>>'{}' END)::numeric) " \
    "ELSE value END) FROM jsonb_each(to_jsonb(t)))"


def require(value, message):
    if not value:
        raise ValueError(message)


def native_root_allowed(root):
    path = PurePosixPath(str(root))
    return (path.is_absolute() and '..' not in path.parts
        and path.is_relative_to(PurePosixPath('/opt/steps-validation'))
        and path.name.startswith(NATIVE_ROOT_PREFIXES))


def validate_native_acceptance(root, accepted, *, expected_multifront_installed=None, operational_extensions=False, quality_extension=False, critical_extension=False, critical_generation='R3'):
    require(native_root_allowed(root), 'Private accepted source root required')
    require(accepted.get('mode') == 'cerro-reference' and accepted.get('writes_to_source') is False,
            'Accepted native reference required')
    if PurePosixPath(str(root)).name.startswith('community-multifront-'):
        require(not quality_extension or operational_extensions, 'Quality requires the operational extension profile')
        require(type(critical_extension) is bool and (not critical_extension or quality_extension), 'Critical requires Quality acceptance')
        from audit_multifront_installation import critical_tests, check_generation
        check_generation(accepted, critical_extension, critical_generation)
        expected_tests = critical_tests(critical_extension, critical_generation)['cerro-reference'] if critical_extension else 441 if quality_extension else 437 if operational_extensions else 391
        require(accepted.get('critical_extension', False) is critical_extension, 'Exact critical acceptance flag required')
        require(accepted.get('multifront') is True and accepted.get('focused_development_pass') is False
                and accepted.get('expected_test_count') == expected_tests
                and bool(accepted.get('operational_extensions', False)) == operational_extensions,
                'Full exact multifront native acceptance profile required')
        require(bool(accepted.get('quality_extension',False)) == quality_extension, 'Exact Quality acceptance flag required')
        # The coordinator pins the independently measured installed graph.
        # Do not guess393, accept a range or learn the pin from this same file.
        require(type(expected_multifront_installed) is int and expected_multifront_installed > 140,
                'Exact measured multifront installed count must be supplied')
        require(accepted.get('counts') == {'installed': expected_multifront_installed, 'enterprise': 140},
                'Measured multifront module graph differs')
    else:
        require(critical_generation == 'R3' and not critical_extension and not quality_extension and not operational_extensions and expected_multifront_installed is None and accepted.get('multifront', False) is False
                and accepted.get('focused_development_pass', False) is False and accepted.get('expected_test_count') == 294
                and accepted.get('counts') == {'installed': 391, 'enterprise': 140},
                'Original native294/installed391 witness required')


def sha(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def capture(command, *, statement=None):
    result = subprocess.run(command, input=statement, text=True, capture_output=True)
    require(result.returncode == 0, 'Private extraction/query failed; raw diagnostics withheld')
    return result.stdout


def schema_columns(schema):
    blocks = re.findall(r'^CREATE TABLE public\.stock_package_type \(\n(.*?)\n\);', schema, re.M | re.S)
    require(len(blocks) == 1, 'Exactly one reviewed table definition is required')
    columns = []
    for line in blocks[0].splitlines():
        if line.lstrip().startswith('CONSTRAINT '):
            require(re.fullmatch(r'\s*CONSTRAINT [a-z_]+ CHECK \(.+\),?', line), 'Unrecognized constraint metadata')
            continue  # Metadata only; its expression is never executed.
        match = re.fullmatch(r'\s*([a-z_][a-z_0-9]*) (integer|numeric|double precision|character varying|timestamp without time zone)( NOT NULL)?,?', line)
        require(match is not None, 'Unreviewed column type/default/definition')
        columns.append((match[1], match[2], bool(match[3])))
    require(tuple(columns) == COLUMNS, 'Source column/type/order/nullability drift')
    return columns


def copy_value(value):
    if value == r'\N':
        return None
    # Decode escapes at byte level so UTF-8 octal/hex escapes cannot become
    # mojibake. COPY TO emits ordinary C escapes, not arbitrary SQL expressions.
    data, result, index = value.encode('utf-8'), bytearray(), 0
    escapes = {ord('b'): 8, ord('f'): 12, ord('n'): 10, ord('r'): 13,
               ord('t'): 9, ord('v'): 11, ord('\\'): 92}
    while index < len(data):
        item = data[index]
        index += 1
        if item != 92:
            result.append(item)
            continue
        require(index < len(data), 'Truncated COPY escape')
        item = data[index]
        index += 1
        if item in escapes:
            result.append(escapes[item])
        elif 48 <= item <= 55:
            digits = bytes([item])
            while index < len(data) and len(digits) < 3 and 48 <= data[index] <= 55:
                digits += bytes([data[index]])
                index += 1
            require(int(digits, 8) <= 255, 'Invalid COPY octal byte')
            result.append(int(digits, 8))
        elif item == ord('x'):
            digits = b''
            while index < len(data) and len(digits) < 2 and chr(data[index]) in '0123456789abcdefABCDEF':
                digits += bytes([data[index]])
                index += 1
            require(bool(digits), 'Invalid COPY hexadecimal byte')
            result.append(int(digits, 16))
        else:
            raise ValueError('Unrecognized COPY escape')
    require(0 not in result, 'NUL COPY data refused')
    try:
        return result.decode('utf-8')
    except UnicodeError:
        raise ValueError('Invalid UTF-8 COPY value') from None


def copy_rows(data):
    matches = re.findall(r'^COPY public\.stock_package_type \(([^\n]+)\) FROM stdin;\n(.*?)^\\\.\n', data, re.M | re.S)
    require(len(matches) == 1, 'Exactly one reviewed COPY block is required')
    names, body = matches[0]
    require(names.split(', ') == [row[0] for row in COLUMNS], 'COPY column identity/order drift')
    raw = body.splitlines()
    require(len(raw) == 5, 'Exactly five source package rows are required')
    rows = []
    for line in raw:
        cells = line.split('\t')
        require(len(cells) == len(COLUMNS), 'COPY field count drift')
        values = [copy_value(cell) for cell in cells]
        for value, (_, kind, notnull) in zip(values, COLUMNS):
            require(value is not None or not notnull, 'Required source value is NULL')
            if value is None:
                continue
            if kind == 'integer':
                require(re.fullmatch(r'-?[0-9]+', value), 'Invalid integer text')
            elif kind in ('numeric', 'double precision'):
                require(NUMBER.fullmatch(value), 'Non-finite/invalid numeric text')
            elif kind == 'timestamp without time zone':
                require(re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?', value), 'Unreviewed timestamp text')
        rows.append(values)
    require(len({row[0] for row in rows}) == 5, 'Duplicate source package IDs')
    return rows


def typed_values(rows):
    require(len(rows) == 5 and all(len(row) == len(COLUMNS) for row in rows), 'Five complete typed rows required')
    values = []
    for row in rows:
        values.append('(' + ','.join(
            ('NULL' if value is None else "convert_from(decode('%s','hex'),'UTF8')" % value.encode('utf-8').hex())
            + '::' + column[1] for value, column in zip(row, COLUMNS)) + ')')
    return 'WITH t (' + ','.join('"' + column[0] + '"' for column in COLUMNS) + ') AS (VALUES ' + ','.join(values) + ') '


def normalizer(path):
    module = ast.parse(Path(path).read_text(encoding='utf-8-sig'))
    assignments = [node.value for function in module.body if isinstance(function, ast.FunctionDef) and function.name == 'snapshot'
        for node in ast.walk(function) if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == 'normalized' for target in node.targets)]
    require(len(assignments) == 1, 'Unique versioned snapshot normalizer required')
    value = ast.literal_eval(assignments[0])
    require(value == NORMALIZER, 'Unreviewed snapshot normalizer')
    return value


def aggregate_sql(label, relation, normalized):
    return "SELECT json_build_object('section','%s','rows',count(*),'rows_json',json_agg(raw::text ORDER BY raw::text),'raw_md5',md5(coalesce(string_agg(raw::text,E'\\n' ORDER BY raw::text),'')),'normalized_md5',md5(coalesce(string_agg(n::text,E'\\n' ORDER BY n::text),''))) FROM (SELECT to_jsonb(t) raw,%s n FROM %s) rows;" % (label, normalized, relation)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--output-directory', type=Path, required=True)
    parser.add_argument('--expected-multifront-installed', type=int,
        help='Exact independently measured installed graph, mandatory only for multifront roots')
    parser.add_argument('--operational-extensions', action='store_true', help='Require the exact full native437 operational package')
    parser.add_argument('--quality-extension',action='store_true',help='Require the exact full native441 Quality package')
    parser.add_argument('--critical-extension',action='store_true')
    parser.add_argument('--critical-generation',choices=('R3','S'),default='R3')
    args = parser.parse_args()
    require(os.geteuid() == 0, 'Local peer inspection requires root')
    root, output = args.native_root.resolve(), args.output_directory.resolve()
    require(native_root_allowed(root), 'Private accepted source root required')
    require(output.is_relative_to(Path('/opt/steps-validation')) and not output.is_relative_to(root) and not output.exists(), 'New private output outside accepted root required')
    native = root / 'cerro-reference'
    accepted = json.loads((native / 'passed.json').read_text())
    database = accepted['database']
    require(re.fullmatch(r'MANAGEMENT_QA_CERRO_PAYROLL_API_[A-Za-z0-9_]+', database), 'Private reference database required')
    validate_native_acceptance(root, accepted, expected_multifront_installed=args.expected_multifront_installed,
        operational_extensions=args.operational_extensions,quality_extension=args.quality_extension,critical_extension=args.critical_extension,critical_generation=args.critical_generation)
    dump = native / 'source.dump'
    require(dump.is_file() and not dump.is_symlink(), 'Original private dump required')
    original_stat = dump.stat()
    dump_sha = sha(dump)
    options = ['pg_restore', '--table=' + TABLE, '--no-owner', '--no-acl', '--no-comments', '--file=-']
    schema = capture([*options, '--schema-only', str(dump)])
    data = capture([*options, '--data-only', str(dump)])
    columns, rows = schema_columns(schema), copy_rows(data)
    source_tool = root / 'addons/tools/community/validate_community_reports.py'
    normalized = normalizer(source_tool)
    statement = "BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY; SET LOCAL search_path=pg_catalog;\n"
    statement += "SELECT json_build_object('section','metadata','read_only',current_setting('transaction_read_only'),'database',current_database(),'server_encoding',current_setting('server_encoding'),'lc_collate',current_setting('lc_collate'),'extra_float_digits',current_setting('extra_float_digits'),'columns',(SELECT json_agg(json_build_array(attname,format_type(atttypid,atttypmod),attnotnull) ORDER BY attnum) FROM pg_attribute WHERE attrelid='public.stock_package_type'::regclass AND attnum>0 AND NOT attisdropped));\n"
    statement += typed_values(rows) + aggregate_sql('before', 't', normalized) + '\n'
    statement += aggregate_sql('after', 'public.stock_package_type t', normalized) + '\nROLLBACK;'
    environment = {key: value for key, value in os.environ.items() if not key.startswith('PG')}
    environment.update(PGHOST='/var/run/postgresql', PGOPTIONS='-c default_transaction_read_only=on', PGPASSFILE='/opt/steps-validation/no-such-readonly-passfile')
    result = subprocess.run(['sudo', '-u', 'postgres', 'env', *[key + '=' + value for key, value in environment.items() if key.startswith('PG')],
        'psql', '-XAtq', '-v', 'ON_ERROR_STOP=1', '-d', database], input=statement, text=True, capture_output=True, env=environment)
    require(result.returncode == 0, 'Readonly reconstruction failed; raw diagnostics withheld')
    sections = [json.loads(line) for line in result.stdout.splitlines() if line]
    require(len(sections) == 3 and [row['section'] for row in sections] == ['metadata', 'before', 'after'], 'Incomplete readonly reconstruction')
    metadata, before, after = sections
    require(metadata['read_only'] == 'on' and metadata['database'] == database and metadata['server_encoding'] == 'UTF8', 'Readonly UTF8 local database required')
    require(metadata['columns'] == [list(row) for row in columns], 'Current physical schema drift')
    snapshots = [json.loads((native / (name + '.json')).read_text())[TABLE] for name in ('business-before', 'business-after-upgrade', 'business-after')]
    require(before['rows'] == after['rows'] == 5, 'Exactly five reconstructed/current rows required')
    require(before['raw_md5'] == snapshots[0]['representation_hash'], 'Reconstruction does not match original raw snapshot')
    require(after['raw_md5'] == snapshots[1]['representation_hash'] == snapshots[2]['representation_hash'], 'Current raw snapshot differs from upgrade/test witness')
    require(before['normalized_md5'] == after['normalized_md5'] == snapshots[0]['hash'] == snapshots[1]['hash'] == snapshots[2]['hash'], 'Normalized snapshot drift')
    require((dump.stat().st_size, dump.stat().st_mtime_ns) == (original_stat.st_size, original_stat.st_mtime_ns), 'Source dump changed during extraction')
    proof = {'schema': 1, 'table': TABLE, 'read_only': True, 'database_writes': False,
        'orm_loaded': False, 'dump_ddl_or_copy_executed': False, 'float_or_rounding_used': False,
        'database': database, 'source_dump_sha256': dump_sha, 'tool_sha256': sha(__file__),
        'native_acceptance_sha256': sha(native / 'passed.json'),
        'expected_multifront_installed': args.expected_multifront_installed,
        'operational_extensions': args.operational_extensions,
        'quality_extension':args.quality_extension,
        'critical_extension':args.critical_extension,
        'source_dump_path': str(dump), 'source_dump_bytes': original_stat.st_size,
        'schema_columns': {name: kind for name, kind, _ in columns},
        'current_schema_columns': {name: kind for name, kind, _ in metadata['columns']},
        'schema_definition': [list(row) for row in columns], 'current_schema_definition': metadata['columns'],
        'schema_extract_sha256': hashlib.sha256(schema.encode()).hexdigest(),
        'copy_extract_sha256': hashlib.sha256(data.encode()).hexdigest(),
        'snapshot_normalizer_tool_sha256': sha(source_tool),
        'normalizer_sha256': hashlib.sha256(normalized.encode()).hexdigest(),
        'snapshot_files_sha256': {name: sha(native / (name + '.json')) for name in ('business-before', 'business-after-upgrade', 'business-after')},
        'metadata': metadata, 'before_rows_json': before['rows_json'], 'after_rows_json': after['rows_json'],
        'before_raw_md5': before['raw_md5'], 'after_raw_md5': after['raw_md5'],
        'before_normalized_md5': before['normalized_md5'], 'after_normalized_md5': after['normalized_md5']}
    if args.critical_generation == 'S':
        proof['critical_generation'] = 'S'
    from payroll_representation_contract import verify
    proof['comparison'] = verify(*snapshots, proof)
    output.mkdir(mode=0o700)
    for name, raw in (('business-representation-proof.json', json.dumps(proof, indent=2).encode()),
                      ('auditor.py', Path(__file__).read_bytes())):
        with os.fdopen(os.open(output / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as stream:
            stream.write(raw)
    print(json.dumps({'proof': str(output / 'business-representation-proof.json'), 'sha256': sha(output / 'business-representation-proof.json'),
        'rows': 5, 'before_raw_md5': before['raw_md5'], 'after_raw_md5': after['raw_md5'], 'database_writes': False}))


if __name__ == '__main__':
    main()
