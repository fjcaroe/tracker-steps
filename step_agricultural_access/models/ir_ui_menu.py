# -*- coding: utf-8 -*-
"""Consolida las apps que quedaron duplicadas entre Studio y su módulo.

Varias apps agrícolas se prototiparon en Studio y después se reescribieron
como módulos Python. Al instalar el módulo quedó un segundo menú raíz con el
mismo nombre e icono, de modo que el usuario ve la aplicación dos veces.

El menú de Studio no es una copia vacía: conserva maestros e informes que el
menú del módulo todavía no replica, así que **no se puede archivar sin más**.
Lo que hace esta rutina es fundir el árbol de Studio dentro del árbol del
módulo (sin borrar nada) y recién entonces archivar la raíz vacía.
"""

import logging
import unicodedata
from collections import defaultdict

from odoo import api, models

_logger = logging.getLogger(__name__)

#: Módulo que Odoo usa para todo lo creado con Studio.
STUDIO_MODULE = "studio_customization"

#: Prefijo de los módulos propios que deben quedarse con la app.
OWNER_PREFIXES = ("step_",)

#: Contexto que salta el filtro por grupos de `ir.ui.menu`.
FULL_LIST = {"ir.ui.menu.full_list": True}

#: URLs "de relleno" que Studio dejaba en menús contenedores.
PLACEHOLDER_URLS = ("/web", "/odoo", "/web#", "")

#: Sufijo para desambiguar una hoja de Studio que sobrevive junto a su gemela.
STUDIO_SUFFIX = " (Studio)"

#: Apps heredadas de Studio que hay que absorber aunque no compartan nombre
#: con la app del módulo. Clave y valor son nombres normalizados.
EXPLICIT_LEGACY_PAIRS = {
    "gestion y costos borrador": "gestion y costos",
}


def normalize_label(text):
    """Compara nombres de menú ignorando tildes, mayúsculas y espacios."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", str(text))
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(stripped.lower().split())


class IrUiMenu(models.Model):
    _inherit = "ir.ui.menu"

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    @api.model
    def _label_variants(self, menus):
        """Todas las traducciones normalizadas del nombre de cada menú.

        Los menús se comparan por nombre, y ese nombre es traducible: el
        usuario ve `es_CL` mientras una migración corre en `en_US`. Comparar en
        un solo idioma emparejaba ramas equivocadas, así que se juntan todas
        las variantes y basta con que una coincida.
        """
        variants = defaultdict(set)
        if not menus:
            return variants
        langs = set(self.env["res.lang"].sudo().search([("active", "=", True)]).mapped("code"))
        langs.add("en_US")
        for lang in sorted(langs):
            for menu in menus.with_context(lang=lang):
                label = normalize_label(menu.name)
                if label:
                    variants[menu.id].add(label)
        return variants

    @api.model
    def _menu_owner_modules(self, menus):
        """Módulo propietario de cada menú, según `ir.model.data`."""
        if not menus:
            return {}
        rows = self.env["ir.model.data"].sudo().search_read(
            [("model", "=", "ir.ui.menu"), ("res_id", "in", menus.ids)],
            ["res_id", "module"],
        )
        return {row["res_id"]: row["module"] for row in rows}

    def _active_children(self):
        """Hijos activos sin filtrar por grupos."""
        self.ensure_one()
        return self.env["ir.ui.menu"].sudo().with_context(**FULL_LIST).search(
            [("parent_id", "=", self.id)], order="sequence, id")

    def _action_target_model(self):
        """Modelo al que apunta el menú, o False si no abre nada relevante."""
        self.ensure_one()
        action = self.action
        if not action:
            return False
        return getattr(action, "res_model", False) or False

    def _action_signature(self):
        """Destino real de un menú: modelo + dominio + contexto de su acción."""
        self.ensure_one()
        action = self.action
        if not action or action._name != "ir.actions.act_window":
            return False
        model = getattr(action, "res_model", "") or ""
        if not model:
            return False
        # Las vistas forman parte del destino: un informe en pivot no es lo
        # mismo que una lista aunque compartan modelo y dominio.
        return (model,
                (getattr(action, "domain", "") or "").strip(),
                (getattr(action, "context", "") or "").strip(),
                (getattr(action, "view_mode", "") or "").strip(),
                tuple(getattr(action, "view_ids", self.env["ir.actions.act_window.view"]).ids),
                (getattr(action, "view_id", False) or self.env["ir.ui.view"]).id)

    def _is_placeholder(self):
        """Menú contenedor: sin acción, o con una acción de relleno de Studio."""
        self.ensure_one()
        action = self.action
        if not action:
            return True
        if action._name == "ir.actions.act_url":
            return (action.url or "").rstrip("/") in [u.rstrip("/") for u in PLACEHOLDER_URLS]
        return False

    # ------------------------------------------------------------------
    # Fusión
    # ------------------------------------------------------------------
    def _merge_menu_into(self, target, report):
        """Vuelca los hijos de `self` (Studio) dentro de `target` (módulo)."""
        self.ensure_one()
        target.ensure_one()
        source_children = self._active_children()
        target_children = target._active_children()
        variants = self._label_variants(source_children | target_children)
        for child in source_children:
            child_labels = variants.get(child.id, set())
            twins = target._active_children().filtered(
                lambda menu: bool(child_labels & variants.get(menu.id, set())))
            twin = twins[:1]
            if not twin:
                report.setdefault("_padres_afectados", set()).add(self.id)
                child.write({"parent_id": target.id})
                report["movidos"].append("%s -> %s" % (child.name, target.name))
                continue

            grandchildren = child._active_children()
            if grandchildren:
                child._merge_menu_into(twin, report)
                grandchildren = child._active_children()

            if grandchildren:
                # Quedó contenido propio: se conserva como rama aparte.
                child.write({"parent_id": target.id, "name": child.name + STUDIO_SUFFIX})
                report["movidos"].append("%s%s -> %s" % (child.name, STUDIO_SUFFIX, target.name))
                continue

            same_target = (
                child._action_target_model()
                and child._action_target_model() == twin._action_target_model()
            )
            if child._is_placeholder() or same_target:
                report.setdefault("_padres_afectados", set()).add(self.id)
                child.write({"active": False})
                report["archivados_redundantes"].append("%s (en %s)" % (child.name, target.name))
            else:
                # Abre algo distinto: se conserva, renombrado para no confundir.
                child.write({"parent_id": target.id, "name": child.name + STUDIO_SUFFIX})
                report["movidos"].append("%s%s -> %s" % (child.name, STUDIO_SUFFIX, target.name))
        return True

    def _dedupe_app_leaves(self, report):
        """Quita entradas repetidas dentro de una misma app tras la fusión.

        Al mover una rama completa de Studio pueden quedar dos entradas que
        abren lo mismo en distintos niveles (por ejemplo "Puntos de control"
        suelto y dentro de "Calidad"). Se archiva sólo cuando coinciden **el
        modelo y el nombre**: si el nombre difiere puede tratarse de otra
        vista o de otro informe, y en ese caso no se toca.
        """
        self.ensure_one()
        Menu = self.env["ir.ui.menu"].sudo().with_context(**FULL_LIST)
        descendants = Menu.search([("id", "child_of", self.id), ("id", "!=", self.id)])
        owners = self._menu_owner_modules(descendants)
        variants = self._label_variants(descendants)

        seen = {}
        # Los menús del módulo mandan: se registran primero.
        ordered = descendants.filtered(lambda m: owners.get(m.id) != STUDIO_MODULE)
        ordered |= descendants
        for menu in ordered:
            model = menu._action_target_model()
            if not model:
                continue
            for label in variants.get(menu.id, set()):
                key = (model, label)
                keeper = seen.get(key)
                if keeper is None:
                    seen[key] = menu
                    continue
                if keeper == menu or not menu.active:
                    continue
                report.setdefault("_padres_afectados", set()).add(menu.parent_id.id)
                menu.write({"active": False})
                report["archivados_redundantes"].append(
                    "%s (repetido en %s)" % (menu.name, self.name))
                break

        # Segunda pasada: dos entradas pueden abrir exactamente lo mismo con
        # nombres distintos ("Orden de flete" y "Órdenes de flete"). Sólo se
        # archiva la heredada de Studio y sólo si el destino real coincide:
        # mismo modelo, mismo dominio y mismo contexto.
        by_target = {}
        for menu in ordered:
            if not menu.active:
                continue
            target = menu._action_signature()
            if not target:
                continue
            keeper = by_target.get(target)
            if keeper is None:
                by_target[target] = menu
                continue
            # Sólo se retira una entrada heredada de Studio cuando la que
            # sobrevive pertenece al módulo: dos entradas Studio entre sí no
            # son asunto de esta rutina.
            if keeper == menu or owners.get(menu.id) != STUDIO_MODULE:
                continue
            if owners.get(keeper.id) == STUDIO_MODULE:
                continue
            report.setdefault("_padres_afectados", set()).add(menu.parent_id.id)
            menu.write({"active": False})
            report["archivados_redundantes"].append(
                "%s (mismo destino que '%s' en %s)" % (menu.name, keeper.name, self.name))
        return True

    @api.model
    def _consolidate_duplicated_apps(self):
        """Funde cada app raíz de Studio dentro de la app del módulo homónimo.

        Idempotente: una vez archivada la raíz de Studio deja de encontrarse y
        las siguientes pasadas no hacen nada.
        """
        report = {
            "pares": [],
            "movidos": [],
            "archivados_redundantes": [],
            "raices_archivadas": [],
        }
        Menu = self.env["ir.ui.menu"].sudo().with_context(**FULL_LIST)
        roots = Menu.search([("parent_id", "=", False)])
        owners = self._menu_owner_modules(roots)

        variants = self._label_variants(roots)
        studio_roots = roots.filtered(lambda m: owners.get(m.id) == STUDIO_MODULE)
        module_roots = roots.filtered(
            lambda m: (owners.get(m.id) or "").startswith(OWNER_PREFIXES))

        for studio in studio_roots:
            labels = variants.get(studio.id, set())
            module = module_roots.filtered(
                lambda m: bool(labels & variants.get(m.id, set())))
            if not module:
                # App heredada con otro nombre: se resuelve por la tabla explícita.
                targets = {EXPLICIT_LEGACY_PAIRS[label]
                           for label in labels if label in EXPLICIT_LEGACY_PAIRS}
                if targets:
                    module = module_roots.filtered(
                        lambda m: bool(targets & variants.get(m.id, set())))
            if not module:
                continue
            # Con más de un candidato no se adivina: se informa y se deja.
            if len(module) > 1:
                _logger.warning(
                    "Menús duplicados ambiguos para %s: studio=%s módulo=%s; no se toca.",
                    sorted(labels), studio.id, module.ids)
                continue
            report["pares"].append("%s: Studio #%s -> %s #%s" % (
                module.name, studio.id, module.name, module.id))
            studio._merge_menu_into(module, report)
            module._dedupe_app_leaves(report)
            if not studio._active_children():
                studio.write({"active": False})
                report["raices_archivadas"].append("%s (#%s)" % (studio.name, studio.id))

        # Las apps ya fusionadas en releases anteriores también se revisan: en
        # Fletes convivían entradas heredadas que abren exactamente lo mismo que
        # las nuevas con otro nombre.
        for module_root in module_roots:
            if not module_root.active:
                continue
            descendants = Menu.search([
                ("id", "child_of", module_root.id), ("id", "!=", module_root.id)])
            if not descendants:
                continue
            owners_here = self._menu_owner_modules(descendants)
            if STUDIO_MODULE not in owners_here.values():
                continue
            module_root._dedupe_app_leaves(report)

        # Contenedores que ESTA pasada dejó sin hijos activos.
        emptied_parents = report.pop("_padres_afectados", set())
        for menu in Menu.browse(sorted(emptied_parents)).exists():
            if not menu.active or menu.action or not menu.parent_id:
                continue
            if Menu.search_count([("parent_id", "=", menu.id)]):
                continue
            menu.write({"active": False})
            report["archivados_redundantes"].append(
                "%s (#%s, contenedor vacío)" % (menu.name, menu.id))

        self.env.registry.clear_cache()
        _logger.info(
            "Consolidación de apps duplicadas | pares=%s | menús movidos=%s | "
            "redundantes archivados=%s | raíces archivadas=%s",
            report["pares"], len(report["movidos"]),
            len(report["archivados_redundantes"]), report["raices_archivadas"],
        )
        return report
