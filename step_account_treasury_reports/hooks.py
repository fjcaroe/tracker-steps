"""Original launcher namespace backed by the actual Community report provider.

No Enterprise action/model is imitated or deleted. The provider admits only its
own target or the exact known former launcher, retaining the original menu row.
"""
from odoo.addons.step_account_treasury.report_ownership import preserve_menus
from odoo.addons.step_treasury_community_reports.hooks import (
    LAUNCHERS, post_init_reports as adopt_community_launchers,
)


def pre_init_reports(env):
    preserve_menus(env)


def post_init_reports(env):
    adopt_community_launchers(env)
