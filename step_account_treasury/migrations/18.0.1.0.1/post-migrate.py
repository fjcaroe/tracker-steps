# -*- coding: utf-8 -*-
"""Cierra de forma idempotente la migración del prototipo Studio."""

from odoo import SUPERUSER_ID, api
from odoo.addons.step_account_treasury.hooks import (
    archive_studio_menus,
    grant_initial_groups,
    migrate_studio_treasury,
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = migrate_studio_treasury(env)
    archive_studio_menus(env, report)
    grant_initial_groups(env)
