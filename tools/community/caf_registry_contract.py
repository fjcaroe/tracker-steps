"""Passive CAF metadata from an ALREADY loaded, private, read-only registry.

The caller owns Odoo startup and the transaction. This module never imports
Odoo, opens a database, browses records, calls provider methods/computes, reads
payloads/defaults, inspects source bodies or writes evidence. Pass the existing
shell ``env`` to inspect_registry() and save its JSON result privately.
"""
import inspect
import re
import types


MODEL = 'l10n_cl.dte.caf'
TABLE = 'l10n_cl_dte_caf'
PRIVATE_DATABASE = re.compile(r'(?:MANAGEMENT_QA_(?:CERRO|SYS)_[A-Za-z0-9_]+|COMMUNITY_[A-Za-z0-9_]+)')


class RegistryContractError(ValueError):
    """Code-only error; never echo records, field values, defaults or secrets."""


def _require(condition, code):
    if not condition:
        raise RegistryContractError(code)


def _method_name(value):
    if value is None or value is False:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, types.MethodType):
        value = value.__func__
    if isinstance(value, types.FunctionType):
        return value.__module__ + '.' + value.__qualname__
    # Do not repr arbitrary callable objects, inspect their attributes or call
    # them: their state could contain credentials or trigger provider code.
    return {'kind': type(value).__module__ + '.' + type(value).__qualname__}


def _signature(function):
    """Parameter names/kinds, using code metadata only, never defaults/body.

    inspect.signature() consults __defaults__/annotations. Avoid it: a default's
    repr or an annotation may contain a secret. We access no bytecode, constants,
    source text, annotations, defaults, local-variable tail or provider methods.
    """
    code = function.__code__
    names = code.co_varnames
    positional = code.co_argcount
    positional_only = code.co_posonlyargcount
    keyword_only = code.co_kwonlyargcount
    result = [{'name': names[index], 'kind': 'POSITIONAL_ONLY' if index < positional_only
               else 'POSITIONAL_OR_KEYWORD'} for index in range(positional)]
    offset = positional + keyword_only
    if code.co_flags & inspect.CO_VARARGS:
        result.append({'name': names[offset], 'kind': 'VAR_POSITIONAL'})
        offset += 1
    result.extend({'name': names[index], 'kind': 'KEYWORD_ONLY'}
                  for index in range(positional, positional + keyword_only))
    if code.co_flags & inspect.CO_VARKEYWORDS:
        result.append({'name': names[offset], 'kind': 'VAR_KEYWORD'})
    return result


def _method_metadata(name, value):
    kind = 'instance'
    if isinstance(value, staticmethod):
        kind, value = 'static', value.__func__
    elif isinstance(value, classmethod):
        kind, value = 'class', value.__func__
    if not isinstance(value, types.FunctionType):
        return None
    chain, seen = [], set()
    while isinstance(value, types.FunctionType) and id(value) not in seen and len(chain) < 8:
        seen.add(id(value))
        chain.append({'function': _method_name(value), 'parameters': _signature(value)})
        # Function __dict__ only: no descriptor execution or dynamic attribute
        # lookup on arbitrary wrappers. Do not access __defaults__ at all.
        value = value.__dict__.get('__wrapped__')
    return {'name': name, 'kind': kind, 'signatures': chain,
            'wrapper_chain_incomplete': value is not None}


def _providers(model):
    result = []
    for provider in model.__mro__:
        namespace = provider.__dict__
        declared_name, inherited = namespace.get('_name'), namespace.get('_inherit')
        belongs = declared_name == MODEL or inherited == MODEL or (
            isinstance(inherited, (tuple, list)) and MODEL in inherited)
        if not belongs:
            continue
        methods = []
        for name, value in sorted(namespace.items()):
            if name.startswith('__'):
                continue
            method = _method_metadata(name, value)
            if method is not None:
                methods.append(method)
        result.append({'python_module': provider.__module__, 'class': provider.__qualname__,
                       'odoo_module': namespace.get('_module'), 'methods': methods})
    return result


def inspect_registry(env):
    """Return metadata only; requires private DB, ready registry and READ ONLY.

    No ``env[model]`` or ORM search/read is used. The only SQL is SHOW of the
    already open transaction's read-only policy; a production name fails before
    even that query. A true binary policy proves the configured field metadata,
    not payload history, provider behavior, authority trust or folio allocation.
    """
    cursor, registry = env.cr, env.registry
    database = cursor.dbname
    _require(isinstance(database, str) and PRIVATE_DATABASE.fullmatch(database) is not None,
             'private-database-required')
    _require(registry.db_name == database, 'registry-database-mismatch')
    _require(registry.ready is True, 'registry-not-loaded')
    cursor.execute('SHOW transaction_read_only')
    _require(cursor.fetchone() == ('on',), 'read-only-transaction-required')
    model = registry.models.get(MODEL)
    _require(isinstance(model, type), 'caf-model-missing')
    _require(model._table == TABLE and model._auto is True and model._transient is False,
             'caf-model-identity-mismatch')
    fields = {}
    for name, field in sorted(model._fields.items()):
        related = field.related
        _require(related is None or related is False or isinstance(related, str) or (
            isinstance(related, (tuple, list)) and all(isinstance(part, str) for part in related)),
            'field-related-metadata-type')
        fields[name] = {
            'type': field.type, 'store': field.store, 'required': field.required,
            'readonly': field.readonly, 'related': list(related) if isinstance(related, (tuple, list)) else related,
            'groups': field.groups, 'compute': _method_name(field.compute),
        }
        if field.type == 'binary':
            fields[name]['attachment'] = field.attachment
    binary = fields.get('caf_file', {})
    policy = binary.get('type') == 'binary' and binary.get('attachment') is True and binary.get('store') is True
    return {'scope': 'loaded-registry-passive-metadata', 'database': database,
            'transaction_read_only': True, 'orm_records_accessed': False,
            'payloads_read': False, 'defaults_inspected': False,
            'provider_bodies_inspected': False, 'provider_methods_called': False,
            'model': {'name': MODEL, 'table': model._table,
                      'auto': model._auto, 'transient': model._transient},
            'fields': fields, 'providers': _providers(model),
            'binary_attachment_policy_proven': policy,
            'payload_storage_preservation_verified': False,
            'adoption_ready': False, 'folio_allocation_ready': False,
            'remaining_blockers': ['native-allocation-behavior-and-concurrency',
                                   'caf-payload-history-and-permissions-acceptance',
                                   'official-authority-trust-and-real-caf-acceptance']}
