"""Physical field bindings from a private registry ALREADY loaded by caller.

No registry startup, record access, computes/defaults/selection calls, source
bodies, writes or adoption. The coordinator binds this payload to an accepted
packet and proves SQL table/counter preservation around its execution.
"""
import hashlib
from pathlib import Path
import re


TYPES = frozenset(('many2one', 'one2many', 'many2many', 'reference',
    'many2one_reference', 'json', 'properties', 'properties_definition'))


def require(value, code):
    if not value:
        raise ValueError(code)


def _name(value):
    return value if isinstance(value, str) else None


def inspect_registry(env, *, source_packet_sha256, acceptance_sha256):
    database = env.cr.dbname
    require(re.fullmatch(r'(?:COMMUNITY_PAYROLL_API_|MANAGEMENT_QA_CERRO_PAYROLL_API_)[A-Za-z0-9_]+', database), 'private-reference-registry-required')
    require(all(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value)
        for value in (source_packet_sha256, acceptance_sha256)), 'sealed-accepted-source-required')
    env.cr.execute('SHOW transaction_read_only')
    require(env.cr.fetchone() == ('on',), 'readonly-registry-transaction-required')
    models = []
    for model_name, model in sorted(env.registry.models.items()):
        # Registry classes and Field objects only. Never env[model].search,
        # getattr(record, field_name), callable selections or source inspection.
        table = _name(getattr(model, '_table', None))
        inherits = getattr(model, '_inherits', {})
        require(isinstance(inherits, dict) and all(isinstance(k, str) and isinstance(v, str)
            for k, v in inherits.items()), 'registry-inherits-shape')
        fields = []
        for field_name, field in sorted(model._fields.items()):
            kind = getattr(field, 'type', None)
            if kind not in TYPES and not getattr(field, 'company_dependent', False):
                continue
            row = {'name': field_name, 'type': kind,
                'store': bool(getattr(field, 'store', False)),
                'company_dependent': bool(getattr(field, 'company_dependent', False)),
                'comodel': _name(getattr(field, 'comodel_name', None)),
                'related': (getattr(field, 'related').split('.') if isinstance(getattr(field, 'related', None), str)
                    else list(getattr(field, 'related', ()) or ())),
                'relation_table': _name(getattr(field, 'relation', None)) if kind == 'many2many' else None,
                'column1': _name(getattr(field, 'column1', None)) if kind == 'many2many' else None,
                'column2': _name(getattr(field, 'column2', None)) if kind == 'many2many' else None,
                'inverse_name': _name(getattr(field, 'inverse_name', None)),
                'model_field': _name(getattr(field, 'model_field', None)),
                'selection_models': None, 'selection_callable': False}
            if kind == 'reference':
                selection = getattr(field, 'selection', None)
                if isinstance(selection, (tuple, list)):
                    require(all(isinstance(item, (tuple, list)) and len(item) == 2
                        and isinstance(item[0], str) for item in selection), 'registry-reference-selection-shape')
                    row['selection_models'] = [item[0] for item in selection]
                else:
                    row['selection_callable'] = callable(selection) or isinstance(selection, str)
            fields.append(row)
        models.append({'model': model_name, 'table': table,
            'auto': bool(getattr(model, '_auto', False)), 'abstract': bool(getattr(model, '_abstract', False)),
            'transient': bool(getattr(model, '_transient', False)), 'inherits': dict(inherits), 'fields': fields})
    return {'schema': 1, 'database': database, 'read_only': True, 'orm_loaded_by_payload': False,
        'orm_records_accessed': False, 'source_bodies_read': False, 'callables_executed': False,
        'database_writes': False, 'source_packet_sha256': source_packet_sha256,
        'acceptance_sha256': acceptance_sha256, 'models': models,
        'tool_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'adoption_authorized': False}
