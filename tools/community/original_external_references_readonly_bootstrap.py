"""Force real Odoo connection pools read-only before the first connection.

Odoo 18 explicitly sets each cursor's session from pool.readonly, overriding
PGOPTIONS. Only this isolated metadata process changes the pool policy; no
installed runtime or addon file is changed. An attempted startup write fails.
"""
from pathlib import Path
import ast
import hashlib
import inspect
import runpy
import sys


SEQUENCE_METHOD_SHA256 = '6c41a6d4a995835a69a550420fbefb0987845008d8033035c96fea0670e5e000'
REGISTRY_SOURCE_SHA256 = frozenset((
    '20a64452e404254f6cc067f1e06753ac9f8723239d465ace96f797719beb1ffb',
    '9db45ba41656e998b4720003b20a53f3eb115459815755e65096c97dae86631f'))
CACHE_KEYS = ('default', 'assets', 'templates', 'routing', 'groups')
SEQUENCE_SELECT = '''SELECT base_registry_signaling.last_value,
base_cache_signaling_default.last_value, base_cache_signaling_assets.last_value,
base_cache_signaling_templates.last_value, base_cache_signaling_routing.last_value,
base_cache_signaling_groups.last_value FROM base_registry_signaling,
base_cache_signaling_default, base_cache_signaling_assets,
base_cache_signaling_templates, base_cache_signaling_routing,
base_cache_signaling_groups'''


def read_sequence_values(cr, keys):
    """Read existing signaling sequences on the real local primary, never nextval."""
    if cr.readonly is not True or tuple(keys) != CACHE_KEYS:
        raise ValueError('Exact real read-only cursor and original cache keys required')
    cr.execute('SHOW transaction_read_only')
    if cr.fetchone() != ('on',):
        raise ValueError('Signaling sequence connection is not read-only')
    cr.execute('SELECT pg_is_in_recovery()')
    if cr.fetchone() != (False,):
        raise ValueError('Read-only signaling inspection requires the local primary, not a replica')
    cr.execute(SEQUENCE_SELECT)
    values = cr.fetchone()
    if not values or len(values) != 6 or any(type(value) is not int for value in values):
        raise ValueError('All six original signaling sequences must already exist')
    return values[0], dict(zip(keys, values[1:]))


def install_readonly_sequence_reader(registry):
    """An isolated SELECT-only equivalent of the exact audited LGPL method.

    The original replica assertion assumes sequences cannot be read. A local
    primary in a read-only transaction can return their actual last_value.
    setup_signaling, signal_changes, nextval and all write paths stay intact.
    """
    raw = Path(registry.__file__).read_bytes()
    source_hash = hashlib.sha256(raw).hexdigest()
    if source_hash not in REGISTRY_SOURCE_SHA256 or tuple(registry._CACHES_BY_KEY) != CACHE_KEYS:
        raise ValueError('Unreviewed official registry source or signaling cache keys')
    source = raw.decode('utf-8')
    parsed = ast.parse(source)
    klass = next(node for node in parsed.body if isinstance(node, ast.ClassDef) and node.name == 'Registry')
    method = next(node for node in klass.body if isinstance(node, ast.FunctionDef) and node.name == 'get_sequences')
    segment = ast.get_source_segment(source, method)
    if (hashlib.sha256(segment.encode()).hexdigest() != SEQUENCE_METHOD_SHA256
            or tuple(inspect.signature(registry.Registry.get_sequences).parameters) != ('self', 'cr')):
        raise ValueError('The actual LGPL get_sequences contract differs')
    calls = []

    def get_sequences(self, cr):
        values = read_sequence_values(cr, registry._CACHES_BY_KEY)
        calls.append({'database': cr.dbname, 'transaction_read_only': 'on',
            'odoo_cursor_readonly': True, 'pg_is_in_recovery': False})
        return values

    registry.Registry.get_sequences = get_sequences
    registry._steps_readonly_sequence_reader_proof = {
        'original_registry_source_sha256': source_hash,
        'original_get_sequences_sha256': SEQUENCE_METHOD_SHA256,
        'select_only_sql_sha256': hashlib.sha256(SEQUENCE_SELECT.encode()).hexdigest(),
        'cache_keys': list(CACHE_KEYS), 'calls': calls,
        'cursor_readonly_unchanged': True, 'setup_signaling_unchanged': True,
        'signal_changes_unchanged': True, 'nextval_unchanged': True,
        'installed_sources_modified': False}


def enforce_readonly_pools(sql_db):
    if sql_db._Pool is not None or sql_db._Pool_readonly is not None:
        raise ValueError('Refuse enabling read-only after a pool already exists')
    original = sql_db.ConnectionPool.__init__
    parameters = tuple(inspect.signature(original).parameters.values())
    if (tuple(value.name for value in parameters) != ('self', 'maxconn', 'readonly')
            or parameters[1].default != 64 or parameters[2].default is not False):
        raise ValueError('Unreviewed official Odoo ConnectionPool constructor signature')

    def initialize(self, maxconn=64, readonly=False):
        original(self, maxconn=maxconn, readonly=True)

    sql_db.ConnectionPool.__init__ = initialize
    probe = sql_db.ConnectionPool(maxconn=1, readonly=False)
    if not probe.readonly or probe._connections:
        raise ValueError('The real Odoo pool did not accept read-only before connecting')


def observe_readonly_cursors(sql_db, database):
    """Record SHOW evidence before each real Odoo cursor can be used by callers."""
    original = sql_db.Cursor.__init__
    observations = []

    def initialize(self, *args, **kwargs):
        original(self, *args, **kwargs)
        if self.dbname not in (database, 'postgres'):
            raise ValueError('Refuse a cursor outside the explicit private database')
        self.execute('SHOW transaction_read_only')
        if self.fetchone() != ('on',) or self.readonly is not True:
            raise ValueError('A real registry connection did not start read-only')
        observations.append({'database': self.dbname, 'transaction_read_only': 'on', 'odoo_cursor_readonly': True})

    sql_db.Cursor.__init__ = initialize
    sql_db._steps_readonly_cursor_proof = observations


def main():
    runtime, entry = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if not runtime.is_dir() or not entry.is_file():
        raise ValueError('Existing official runtime and exact accepted entry required')
    database, arguments = sys.argv[3], sys.argv[4:]
    sys.path.insert(0, str(runtime))
    import odoo.sql_db
    enforce_readonly_pools(odoo.sql_db)
    observe_readonly_cursors(odoo.sql_db, database)
    import odoo.modules.registry
    install_readonly_sequence_reader(odoo.modules.registry)
    # Preserve script-local imports of the accepted native preservation runner.
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *arguments]
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
