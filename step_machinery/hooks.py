# -*- coding: utf-8 -*-
"""Deja el catálogo canónico de conceptos de maquinaria tras instalar."""

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def post_init_canonical_catalog(env):
    if not isinstance(env, api.Environment):  # compatibilidad con firmas antiguas
        env = api.Environment(env, SUPERUSER_ID, {})
    env["type.service.machinery"]._ensure_canonical_catalog()
