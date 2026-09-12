# Ticket 27 — T27 Mejoras módulo Fletes

Módulo: `step_operations_ui` (18.0.2.0.3 → 18.0.2.1.0) · Rama: `ticket/27-fletes-mejoras` · Base: `fix/previred-correcciones-2`.

## Origen

El ticket trae el documento de diseño "2.6 Fletes mejoras e integración con
Inventario" (docx) y el anexo "Formulario de registro de flete" (xlsx). El
documento propone: reordenar el menú de Fletes, crear "Planificar fletes",
reemplazar "Registro de fletes" por un formulario mucho más completo con dos
orígenes (manual y automático desde Guías de Despacho), agregar configuración
contable de fletes y exponer "Rastreo" como consola de la app móvil de
transporte.

Es, en conjunto, un documento de rediseño multi-pieza: varias partes dependen
de un módulo que todavía no existe (**Guías de Despacho**, ticket 25, sólo
analizado) o de decidir reglas contables sin valores confirmados. Por
instrucción explícita del usuario en el chat de esta sesión ("ejecuta el 27
hasta terminarlo"), se implementó la porción autocontenida que sí cabe en el
módulo `step_operations_ui` ya existente, sin inventar arquitectura nueva ni
tocar contabilización real.

## Qué se implementó

1. **Reordenamiento del menú de Fletes**, según el orden pedido en el
   documento: Inicio (ya existía) → Operaciones (Planificar fletes, Registro
   de fletes, Rastreo) → Contabilización (se mantiene, no estaba en la lista
   del documento pero es una funcionalidad ya en uso; quitarla no fue pedido
   explícitamente) → Informe y análisis (antes "Análisis") → Maestros (antes
   "Configuración": Tarifas, Tramos, Transportistas) → Configuraciones
   (nuevo: Servicios de fletes, Camiones, Modalidad de frío, Tipo de
   despacho).
2. **"Planificar fletes" (nuevo)**: modelo `x_planificacion_de_flete` +
   líneas `x_planificacion_de_flete_linea`, con los campos exactos que pide
   el documento (producto marcado "Es flete" = `is_flete` en
   `product.template`, ya existente en `step_hr`; unidad del producto;
   cantidad; precio; total = cantidad × precio). Restricción
   (`@api.constrains`) que impide guardar una línea con un producto que no
   esté marcado `is_flete`, no sólo por dominio de vista (que se puede
   saltar por RPC).
3. **"Registro de fletes"**: se renombró la acción/menú de "Órdenes de
   flete" a "Registro de fletes" (coincide con el nombre pedido). **No** se
   rediseñó el formulario en profundidad: los campos nuevos que pide el
   documento (RUT, Chofer, Patentes, Cliente/destinatario, Razón del
   traslado, Tipo despacho, líneas con tramo desde/hasta, Kms, servicio de
   flete, distribución analítica) y el origen automático desde Guías de
   Despacho **no están implementados** — dependen de un módulo (Guías de
   Despacho) que no existe en ningún worktree Steps todavía.
4. **"Tipo de despacho" (nuevo)**: modelo `x_tipo_despacho` con regla
   `paga_flete` (No/Opcional/Sí) y datos semilla exactamente como en el
   anexo (Retira cliente=No, Despacho a cliente=Opcional, Despacho a
   tercero=Opcional). Vista y menú bajo Configuraciones. No está todavía
   enlazado como campo del Registro de fletes (ver punto 3).
5. **"Modalidad de frío"**: el modelo ya existía (sin vistas ni menú desde
   su creación); se agregaron lista, formulario y menú.
6. **"Camiones"**: la acción ya existía (apunta a `fleet.vehicle`) pero no
   estaba enlazada a ningún menú; se agregó el `<menuitem>` bajo
   Configuraciones. Se agregó `fleet` como dependencia explícita del
   manifiesto (el módulo ya usaba `fleet.vehicle` en `x_orden_de_flete` sin
   declarar la dependencia).
7. **"Servicios de fletes"**: acción de solo lectura/edición sobre
   `product.template` filtrada por `is_flete = True`, bajo Configuraciones.

## Qué NO se implementó (pendiente, y por qué)

- **Origen automático desde Guías de Despacho** en el Registro de fletes:
  bloqueado por el ticket 25 (Guías de Despacho), que sigue en fase de
  análisis — no hay módulo del que leer.
- **Rediseño completo del formulario "Registro de fletes"** (RUT, Chofer,
  Patentes, Cliente/destinatario, Razón del traslado, líneas con
  tramo/kms/servicio/distribución analítica): requiere decidir si esos
  campos van sobre el modelo actual `x_orden_de_flete` o un modelo nuevo, y
  el documento no da suficiente detalle de tipos/validaciones para todos
  ellos. Se dejó fuera para no inventar el diseño por cuenta propia.
- **Configuración contable de fletes** (diario contable + tipo de
  documento, reglas Debe/Haber): toca contabilización real y el documento
  no da las cuentas/diarios concretos a usar — implementarlo a ciegas
  arriesga generar asientos incorrectos. Se dejó fuera; el modelo actual de
  contabilización (`x_contabilizacion_de_f`) no se tocó.
- **"Rastreo" como consola de la app móvil de transporte**: la
  funcionalidad de rastreo GPS real vive en el proyecto `tracker-steps` /
  Web Tracker, un repositorio y stack completamente distinto (Vite/React),
  no en un módulo Odoo. El menú "Rastreo" y el modelo
  `x_rastreo_camiones` ya existían antes de este ticket y no se
  modificaron; integrar con la consola real de la app móvil está fuera del
  alcance de un módulo Odoo y de esta sesión.

## Pruebas

`step_operations_ui/tests/test_freight_plan.py` (4 casos): total de línea =
cantidad × precio; total de planificación = suma de líneas; rechazo de un
producto no marcado `is_flete`; el total se recalcula al eliminar una línea.

`step_operations_ui/tests/test_freight_dispatch_type.py` (2 casos): los tres
tipos de despacho semilla quedan con la regla `paga_flete` esperada; el valor
por defecto de un tipo nuevo es "No".

No se ejecutaron contra un Odoo real en esta sesión — sólo
`python -m compileall` (sin errores) y parseo de los XML modificados/nuevos
(sin errores).
