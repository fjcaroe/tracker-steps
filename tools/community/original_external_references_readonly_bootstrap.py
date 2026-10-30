"""Force real Odoo connection pools read-only before the first connection.

Odoo 18 explicitly sets each cursor's session from pool.readonly, overriding
PGOPTIONS. Only this isolated metadata process changes the pool policy; no
installed runtime or addon file is changed. An attempted startup write fails.
"""
from pathlib import Path
import runpy
import sys


def enforce_readonly_pools(sql_db):
    if sql_db._Pool is not None or sql_db._Pool_readonly is not None:
        raise ValueError('Refuse enabling read-only after a pool already exists')
    original = sql_db.ConnectionPool.__init__

    def initialize(self, maxconn=64, readonly=False):
        original(self, maxconn=maxconn, readonly=True)

    sql_db.ConnectionPool.__init__ = initialize
    probe = sql_db.ConnectionPool(maxconn=1, readonly=False)
    if not probe.readonly or probe._connections:
        raise ValueError('The real Odoo pool did not accept read-only before connecting')


def main():
    runtime, entry = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    if not runtime.is_dir() or not entry.is_file():
        raise ValueError('Existing official runtime and exact accepted entry required')
    arguments = sys.argv[3:]
    sys.path.insert(0, str(runtime))
    import odoo.sql_db
    enforce_readonly_pools(odoo.sql_db)
    # Preserve script-local imports of the accepted native preservation runner.
    sys.path.insert(0, str(entry.parent))
    sys.argv = [str(entry), *arguments]
    runpy.run_path(str(entry), run_name='__main__')


if __name__ == '__main__':
    main()
