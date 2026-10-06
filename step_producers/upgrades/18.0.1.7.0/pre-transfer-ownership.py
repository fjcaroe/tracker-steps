"""Relocate XML metadata while preserving every business record and table."""
import importlib.util
from odoo.tools import file_path


def migrate(cr, version):
    path = file_path('step_producers/migration_helpers.py')
    spec = importlib.util.spec_from_file_location('producer_ownership_migration', path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.transfer_ownership(cr)
