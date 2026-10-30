"""Read ir_model_data COPY metadata from a private dump; execute no dump SQL."""
import re
import subprocess

from audit_stock_package_representation import copy_value


FIELDS = ('id', 'module', 'name', 'model', 'res_id', 'noupdate')


def require(value, code):
    if not value:
        raise ValueError(code)


def xmlids_from_copy(body):
    lines = body.splitlines()
    headers = [(index, re.fullmatch(r'COPY public\.ir_model_data \(([^)]+)\) FROM stdin;', line))
        for index, line in enumerate(lines) if line.startswith('COPY ')]
    require(len(headers) == 1 and headers[0][1] is not None, 'exact-ir-model-data-copy-required')
    start, header = headers[0]
    columns = header[1].split(', ')
    require(len(set(columns)) == len(columns) and set(FIELDS) <= set(columns)
        and all(re.fullmatch('[a-z_][a-z0-9_]*', name) for name in columns), 'unreviewed-xmlid-copy-columns')
    result, ended = [], False
    for line in lines[start + 1:]:
        if line == r'\.':
            ended = True
            break
        values = line.split('\t')
        require(len(values) == len(columns), 'xmlid-copy-row-column-count')
        raw = {name: copy_value(values[columns.index(name)]) for name in FIELDS}
        require(raw['id'] is not None and re.fullmatch('[1-9][0-9]*', raw['id'])
            and raw['res_id'] is not None and re.fullmatch('-?[0-9]+', raw['res_id'])
            and raw['noupdate'] in ('t', 'f', None), 'xmlid-copy-key-or-boolean-format')
        raw.update(id=int(raw['id']), res_id=int(raw['res_id']),
            noupdate=None if raw['noupdate'] is None else raw['noupdate'] == 't')
        result.append(raw)
    require(ended and result and len({row['id'] for row in result}) == len(result), 'xmlid-copy-missing-end-or-duplicate-id')
    return result


def prove_original_identity(backup, identity_before):
    result = subprocess.run(['pg_restore', '--data-only', '--schema=public', '--table=ir_model_data',
        '--file=-', str(backup)], capture_output=True, text=True)
    require(result.returncode == 0, 'private-xmlid-metadata-extraction-failed-diagnostics-withheld')
    source = xmlids_from_copy(result.stdout)
    expected = identity_before['original_xmlids']
    before = {row['id']: {name: row[name] for name in FIELDS} for row in expected}
    require(len(before) == len(expected) and {row['id']: row for row in source} == before,
        'entire-original-xmlid-snapshot-differs-from-own-backup')
    return {'original_xmlids': len(source), 'all_six_identity_fields_exact_to_backup': True,
        'dump_ddl_dml_or_copy_executed': False, 'only_ir_model_data_metadata_extracted': True}
