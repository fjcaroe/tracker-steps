"""Force real Odoo connection pools read-only before the first connection.

Odoo 18 explicitly sets each cursor's session from pool.readonly, overriding
PGOPTIONS. Only this isolated metadata process changes the pool policy; no
installed runtime or addon file is changed. An attempted startup write fails.
"""
from pathlib import Path
import inspect
import runpy
import sys


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
    # Preserve script-local imports of the accepted native preservation runner.
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *arguments]
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
