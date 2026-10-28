"""Admit existing snapshots before field setup; retain closure after reopening."""
from odoo.addons.step_payroll_contracts.history import assert_history_snapshots, protected_sql, columns, assert_community_engine


def pre_init_hook(env):
    assert_community_engine(env.cr)
    assert_history_snapshots(env.cr)


def mark_existing_history(cr):
    cr.execute('UPDATE hr_payslip s SET step_history_locked=true WHERE NOT coalesce(step_history_locked,false) AND '+protected_sql(columns(cr,'hr_payslip')))


def post_init_hook(env):
    mark_existing_history(env.cr)
