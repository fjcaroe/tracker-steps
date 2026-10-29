"""Metadata-only payload for an already loaded private Odoo registry.

The caller must supply a read-only transaction. Never starts Odoo, imports an
Enterprise source file, reads a batch/payment record, executes a compute or
validates/reconciles a payment. These runtime field attributes are not in SQL.
"""
import inspect
import re


MODEL = 'account.batch.payment'
METHODS = ('create', 'write', 'unlink', 'validate_batch_button', 'export_batch_payments',
           'action_open_batch', 'action_export_bancoestado_xlsx', 'action_export_security_xls')


def inspect_registry(env):
    database = env.cr.dbname
    if not re.fullmatch(r'(?:COMMUNITY_[A-Za-z0-9_]+|MANAGEMENT_QA_(?:CERRO|SYS|STEPS)_[A-Za-z0-9_]+)', database):
        raise ValueError('Only private validation registries are allowed')
    env.cr.execute('SHOW transaction_read_only')
    if env.cr.fetchone()[0] != 'on':
        raise ValueError('Use a read-only transaction before inspecting the registry')
    if MODEL not in env.registry:
        return {'database': database, 'read_only': True, 'model_present': False,
                'functional_provider_certified': False, 'business_records_read': False}
    model = env[MODEL]
    fields = {}
    for name, field in model._fields.items():
        if name.startswith(('message_', 'activity_')):
            continue
        compute = getattr(field, 'compute', None)
        if callable(compute):
            compute = 'callable:' + getattr(compute, '__qualname__', type(compute).__name__)
        related = getattr(field, 'related', None)
        fields[name] = {'type': field.type, 'store': bool(field.store),
                       'required': bool(field.required), 'readonly': bool(field.readonly),
                       'comodel_name': getattr(field, 'comodel_name', None),
                       'inverse_name': getattr(field, 'inverse_name', None),
                       'related': list(related) if isinstance(related, tuple) else related,
                       'currency_field': getattr(field, 'currency_field', None),
                       'attachment': getattr(field, 'attachment', None),
                       'compute_method_name': compute, 'owner_module': getattr(field, '_module', None)}
    methods = {}
    for name in METHODS:
        method = getattr(model, name, None)
        if callable(method):
            methods[name] = {'parameters': [{'name': item.name, 'kind': str(item.kind)}
                                           for item in inspect.signature(method).parameters.values()],
                             'module': getattr(method, '__module__', None)}
    related_providers = {}
    for name in ('account.batch.error.wizard', 'account.batch.payment.rejection',
                 'bank.rec.widget', 'bank.rec.widget.line'):
        if name not in env.registry:
            related_providers[name] = {'present': False}
            continue
        provider = env[name]
        related_providers[name] = {'present': True, 'table': provider._table,
                                  'auto': provider._auto, 'transient': provider._transient,
                                  'batch_relations': sorted(field_name for field_name, field in provider._fields.items()
                                      if getattr(field, 'comodel_name', None) == MODEL)}
    return {'database': database, 'read_only': True, 'model_present': True,
            'model_name': model._name, 'table': model._table, 'auto': model._auto, 'transient': model._transient,
            'fields': fields, 'method_signatures': methods, 'related_providers': related_providers,
            'business_records_read': False,
            'computes_executed': False, 'source_bodies_exported': False,
            'functional_provider_certified': False}
