"""Strict, offline proof of fractional numeric zero representation changes.

Only stock_package_type's five original rows are eligible. JSON text/NULL,
identities, nested objects, field order and every nonnumeric byte remain exact.
Numbers stay lexical tokens: no binary float, decimal rounding or tolerance.
"""
import hashlib
import json
import re


TABLE = 'stock_package_type'


class RepresentationError(ValueError):
    pass


class _Number(str):
    pass


def require(value, message):
    if not value:
        raise RepresentationError(message)


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def _constant(value):
    raise RepresentationError('nonfinite JSON number rejected')


DECODER = json.JSONDecoder(parse_int=_Number, parse_float=_Number,
    parse_constant=_constant, object_pairs_hook=_pairs)


def raw_hash(rows_json):
    """Keep PostgreSQL ORDER BY raw ordering; do not sort using Python locale."""
    require(isinstance(rows_json, list) and all(isinstance(row, str) for row in rows_json), 'expected ordered raw JSON strings')
    return hashlib.md5('\n'.join(rows_json).encode()).hexdigest()


def _numeric_literal(value):
    require(re.fullmatch(r'-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?', value), 'unexpected numeric JSON representation')
    return value.rstrip('0').rstrip('.') if '.' in value else value


def _row(raw):
    # Decode once with duplicate-key and exact numeric-token protection.
    value, end = DECODER.raw_decode(raw)
    require(isinstance(value, dict) and not raw[end:].strip(), 'expected one complete row object')
    require(isinstance(value.get('id'), _Number) and re.fullmatch(r'[1-9][0-9]*', value['id']), 'original ID must remain an integer token')
    # Replace only top-level numeric spans. All remaining bytes, including
    # whitespace, escapes and nested numeric scale, remain in this witness.
    index, last, parts = 1, 0, []
    require(raw.startswith('{'), 'expected PostgreSQL canonical row text')
    while True:
        while index < len(raw) and raw[index].isspace():
            index += 1
        if raw[index] == '}':
            break
        key, index = DECODER.raw_decode(raw, index)
        require(isinstance(key, str), 'expected object key')
        while raw[index].isspace():
            index += 1
        require(raw[index] == ':', 'expected object colon')
        index += 1
        while raw[index].isspace():
            index += 1
        start = index
        item, index = DECODER.raw_decode(raw, index)
        if isinstance(item, _Number):
            parts.extend((raw[last:start], _numeric_literal(item)))
            last = index
        while raw[index].isspace():
            index += 1
        require(raw[index] in ',}', 'expected object delimiter')
        if raw[index] == '}':
            break
        index += 1
    parts.append(raw[last:])
    return value, ''.join(parts)


def verify(before, upgraded, after, proof):
    """Bind five full raw rows to all three immutable fingerprint captures."""
    require(proof.get('schema') == 1 and proof.get('table') == TABLE, 'unapproved representation table')
    require(proof.get('read_only') is True and proof.get('database_writes') is False, 'representation audit must be read only')
    for snapshot in (before, upgraded, after):
        require(set(snapshot) == {'rows', 'hash', 'representation_hash'} and snapshot['rows'] == 5, 'unexpected five-row fingerprint contract')
    require(before['hash'] == upgraded['hash'] == after['hash'], 'numeric or business value fingerprint changed')
    require(upgraded == after, 'representation changed again during tests')
    first, last = proof['before_rows_json'], proof['after_rows_json']
    columns = proof['schema_columns']
    require(isinstance(columns, dict) and len(columns) == 19 and columns == proof['current_schema_columns'], 'original package schema types changed')
    require(proof['schema_definition'] == proof['current_schema_definition']
        and {name: kind for name, kind, not_null in proof['schema_definition']} == columns,
        'original package column order or nullability changed')
    require(len(first) == len(last) == 5, 'representation proof must include every original row')
    require(raw_hash(first) == before['representation_hash'], 'raw original rows do not match baseline fingerprint')
    require(raw_hash(last) == upgraded['representation_hash'] == after['representation_hash'], 'raw current rows do not match both final fingerprints')
    old, new = {}, {}
    for lines, target in ((first, old), (last, new)):
        for raw in lines:
            row, normalized = _row(raw)
            require(set(row) == set(columns), 'raw proof omitted original package columns')
            require(row['id'] not in target, 'duplicate original row ID')
            target[row['id']] = (row, normalized)
    require(old.keys() == new.keys(), 'original package type IDs changed')
    changes = []
    for ident in old:
        source, normalized_source = old[ident]
        current, normalized_current = new[ident]
        require(source.keys() == current.keys() and normalized_source == normalized_current,
            'a nonnumeric byte, nested value, text, NULL or business value changed')
        for field, value in source.items():
            other = current[field]
            if isinstance(value, _Number) or isinstance(other, _Number):
                require(isinstance(value, _Number) and isinstance(other, _Number), 'numeric field changed JSON type')
                if value != other:
                    require(field != 'id' and _numeric_literal(value) == _numeric_literal(other), 'number changed beyond fractional trailing zeros')
                    require(re.fullmatch(r'numeric(?:\([0-9]+(?:\s*,\s*[0-9]+)?\))?|double precision', columns[field]),
                        'integer or nonnumeric SQL storage changed representation')
                    changes.append({'id': int(ident), 'field': field, 'before_literal': str(value), 'after_literal': str(other)})
    require(changes and before['representation_hash'] != after['representation_hash'], 'no fractional-zero change established')
    return {'table': TABLE, 'rows': 5, 'all_original_ids_preserved': True, 'values_equal': True,
        'raw_representation_equal': False, 'normalized_value_hash': before['hash'],
        'before_representation_hash': before['representation_hash'],
        'after_upgrade_representation_hash': upgraded['representation_hash'],
        'after_representation_hash': after['representation_hash'],
        'other_fields_and_bytes_exact': True, 'fractional_numeric_zero_changes': sorted(changes, key=lambda row: (row['id'], row['field'])),
        'float_or_rounding_used': False, 'table_declared_byte_identical': False}
