"""Retira la navegación paralela que creó la versión 18.0.1.0.0.

La 1.0.0 publicó un submenú propio «Previred Steps» con tres entradas dentro
de Nómina › Reportes. Eso dejaba dos flujos Previred visibles a la vez: el del
motor y el de Steps. A partir de la 2.0.0 hay **un solo flujo**: cada bridge
repunta el menú que el motor ya publicaba hacia el asistente nuevo.

La migración es idempotente: si los menús ya no existen, no hace nada. No
borra el modelo ni ningún lote generado.
"""

import logging

_logger = logging.getLogger(__name__)

#: XML IDs publicados por la 18.0.1.0.0 que ya no deben existir.
OBSOLETE_MENUS = (
    "step_hr_previred.menu_previred_export",
    "step_hr_previred.menu_previred_batch",
    "step_hr_previred.menu_previred_profile",
    "step_hr_previred.menu_previred_root",
)


#: Perfiles que sembró el core en la 1.0.0 y que ahora pertenecen a su
#: bridge. Se **adopta** el registro existente en vez de crear uno nuevo: así
#: los lotes ya generados conservan su perfil y no se viola la restricción de
#: unicidad (motor, versión, formato).
ADOPTED_PROFILES = (
    ("step_hr_previred", "profile_l10n_cl_hr_v84",
     "step_hr_previred_blueminds", "profile_blueminds_v84"),
    ("step_hr_previred", "profile_simpledigital_v84",
     "step_hr_previred_simpledigital", "profile_simpledigital_v84"),
)


def _adopt_profiles(cr):
    """Traspasa el XML ID de los perfiles del core a su bridge.

    Corre **antes** de que el bridge cargue su archivo de datos, así que el
    bridge encuentra el registro y lo actualiza en lugar de insertarlo.
    Idempotente: si ya fue traspasado, o si el destino ya existe, no hace nada.
    """
    for old_module, old_name, new_module, new_name in ADOPTED_PROFILES:
        cr.execute(
            "SELECT id, res_id FROM ir_model_data "
            "WHERE module = %s AND name = %s AND model = %s",
            (old_module, old_name, "step.previred.profile"))
        row = cr.fetchone()
        if not row:
            continue
        cr.execute(
            "SELECT id FROM ir_model_data "
            "WHERE module = %s AND name = %s AND model = %s",
            (new_module, new_name, "step.previred.profile"))
        if cr.fetchone():
            # El bridge ya tiene el suyo: el del core sobra.
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (row[0],))
            _logger.info("Previred: descartado el XML ID duplicado %s.%s.",
                         old_module, old_name)
            continue
        # Un perfil cuyo bridge no está instalado y que nunca generó nada no
        # sirve para el histórico y sólo confunde en la lista: se retira. Si
        # tiene lotes, se conserva siempre, porque son su trazabilidad.
        cr.execute("SELECT COUNT(*) FROM step_previred_batch "
                   "WHERE profile_id = %s", (row[1],))
        has_batches = cr.fetchone()[0] > 0
        cr.execute("SELECT state FROM ir_module_module WHERE name = %s",
                   (new_module,))
        bridge = cr.fetchone()
        bridge_installed = bool(bridge and bridge[0] == "installed")

        if not has_batches and not bridge_installed:
            cr.execute("DELETE FROM ir_model_data WHERE id = %s", (row[0],))
            cr.execute("DELETE FROM step_previred_profile WHERE id = %s",
                       (row[1],))
            _logger.info(
                "Previred: retirado el perfil %s.%s; su motor no está "
                "instalado en esta base y no generó ningún lote.",
                old_module, old_name)
            continue

        cr.execute(
            "UPDATE ir_model_data SET module = %s, name = %s, noupdate = TRUE "
            "WHERE id = %s", (new_module, new_name, row[0]))
        _logger.info(
            "Previred: perfil %s.%s adoptado por %s.%s (registro %s "
            "conservado con sus lotes).",
            old_module, old_name, new_module, new_name, row[1])


def _remove_parallel_menus(env):
    removed = 0
    for xmlid in OBSOLETE_MENUS:
        menu = env.ref(xmlid, raise_if_not_found=False)
        if not menu:
            continue
        menu.unlink()
        removed += 1
    if removed:
        _logger.info(
            "Previred: retirados %d menús de la navegación paralela de la "
            "1.0.0; el flujo visible lo aporta ahora el bridge del motor.",
            removed)


def migrate(cr, version):
    if not version:
        return
    from odoo import api, SUPERUSER_ID
    env = api.Environment(cr, SUPERUSER_ID, {})
    _remove_parallel_menus(env)
    _adopt_profiles(cr)
