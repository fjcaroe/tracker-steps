"""Temporary, exact-database Unix-socket permission for an isolated customer-QA clone.

Caller owns the shared environment lease. Never permits a production database,
changes credentials or widens the customer QA service's network firewall.
"""
from contextlib import contextmanager
from pathlib import Path
import os
import re


@contextmanager
def clone_database_access(query, database, stage):
    assert os.geteuid() == 0
    assert re.fullmatch(r'MANAGEMENT_QA_QA-CERRO_[a-z0-9_]{1,24}', database)
    assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % database), 'Fresh clone required'
    hba = Path(query('postgres', 'SHOW hba_file'))
    assert hba.name == 'pg_hba.conf' and str(hba).startswith('/etc/postgresql/')
    original = hba.read_text()
    marker = '# STEPS TEMPORARY CUSTOMER QA CLONE ' + database
    assert marker not in original
    block = marker + '\nlocal "' + database + '" cerroqa_odoo18 md5\n'
    backup = stage / 'clone_hba_before.conf'
    backup.write_text(original); backup.chmod(0o600)
    try:
        hba.write_text(block + original)
        assert not query('postgres', "SELECT error FROM pg_hba_file_rules WHERE error IS NOT NULL")
        assert query('postgres', 'SELECT pg_reload_conf()') == 't'
        yield
    finally:
        current = hba.read_text()
        assert block in current, 'Temporary clone rule unexpectedly modified'
        hba.write_text(current.replace(block, '', 1))
        assert not query('postgres', "SELECT error FROM pg_hba_file_rules WHERE error IS NOT NULL")
        assert query('postgres', 'SELECT pg_reload_conf()') == 't'
        print('CUSTOMER_QA_CLONE_ACCESS_REMOVED ' + database, flush=True)
