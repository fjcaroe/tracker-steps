# Handoff — Fase 7, corte 1 (Corte 1 post Fase 6: respuestas del cliente)

**Addon:** `step_management_costs` · **De:** `18.0.12.0.0` → **A:** `18.0.13.0.0`
**Fecha:** 2026-09-04 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Continuación tras `CONTINUACION_CLAUDE_RESPUESTAS_CLIENTE_2026-09-04.md`
(respuestas del cliente a `Preguntas_Cliente_Gestion_Costos_2026-09-04,
respuestas (1).docx` y `Formulario OP.pdf`). El documento del cliente define
7 frentes para su "Corte 1"; este handoff entrega **6**, todos dentro del
núcleo `step_management_costs`, sin dependencias agrícolas nuevas:

1. Documentación de decisiones confirmadas.
2. Vista previa antes de regenerar el plan semanal.
3. Política de precio de programas (D07) — confirmación sin cambio de código.
4. Programas por temporada + centro de costo, misma variedad.
5. Importación Excel de la receta de un programa (staging seguro).
6. Necesidades de stock cruzadas con inventario real.

**No incluye** el puente de maestros con Actividades (ítem 6 del documento
del cliente, addon nuevo `step_management_costs_agriculture`): al auditar
`step_hr` se encontró que `product.template.actividad_id` apunta hoy a
`account.analytic.account`, no al modelo `step.actividad` que la respuesta
del cliente da por hecho (ver `DECISION_LOG.md` D20). Queda documentado
como discrepancia real, no como decisión de diseño, y se aborda en la
siguiente entrega.

### Vista previa del plan semanal

`step.management.plan.action_generate_weekly_tasks()` ya no escribe
directamente: valida el estado del plan y abre
`step.management.plan.weekly.preview.wizard` (transitorio), que calcula
(sin escribir) cuántas tareas generadas se eliminarán, cuántas nuevas se
crearán y cuántas manuales se conservan, con el detalle línea a línea.
`action_confirm()` del wizard aplica los mismos comandos ya calculados. El
cálculo puro vive en `_build_weekly_task_commands()`
(`models/planning.py`); `_apply_weekly_task_commands()` hace la escritura.
Las tareas manuales nunca se tocan (ya era el caso; ahora además se
muestran en la vista previa).

### Política de precio de programas (D07)

Sin cambio de código: `price_policy` sigue con sus 3 opciones
(`standard` por defecto, `last_invoice`, `manual`), ya implementadas desde
Fase 5 con el precio congelado en el snapshot. Se documenta que la
política **oficial** de aprobación es `standard` y se agrega una prueba de
regresión que fija el comportamiento.

### Programas por temporada + centro de costo, misma variedad

`models/crop_program.py`: `center_ids` se renombra a "Centros de costo"
(el núcleo no tiene un segundo modelo "cuartel" — `plot` es un atributo
`Char` del centro, no hay jerarquía que reinterpretar). Nueva
`@api.constrains("center_ids")` que exige la misma `variety` entre los
centros elegidos (los centros sin variedad informada no generan conflicto
entre sí). Preflight de sólo lectura en
`upgrades/18.0.13.0.0/post-migration.py`: registra en el log los programas
existentes con centros de variedades mezcladas, sin bloquear el upgrade ni
corregir nada automáticamente.

### Importación Excel de programas

Nuevo `models/crop_program_import.py`
(`step.management.crop.program.import` + `.line`), mismo patrón de staging
seguro que `budget_import.py`: límite de filas/bytes, sin fórmulas,
cabeceras normalizadas (Producto, Dosis/Ha, UdM, Objetivo, Semana,
Carencia, Reingreso), vista previa con errores por fila, hash de archivo
para idempotencia, todo-o-nada salvo "importar sólo filas válidas". El
encabezado (tipo, temporada, especie/variedad, política de precio, centros)
se define en el registro de carga antes de validar; el Excel sólo aporta la
receta. **Aprobación segura:** el programa importado nace siempre en
**borrador**, nunca se aprueba automáticamente.

### Necesidades de stock cruzadas con inventario real

`models/stock_requirement.py`: nueva dependencia del manifiesto `stock`.
Cabecera gana `warehouse_id` (vacío = todos los almacenes de la empresa,
nunca una ubicación implícita) y `availability_metric`
(`on_hand`=`qty_available`, `free`=existencia−reservado,
`forecasted`=`virtual_available` — cada métrica con su propio significado,
nunca mezcladas) y `computed_at`. Línea gana `available_quantity` y
`shortage_quantity = max(0, total − disponible)`. La lectura de
disponibilidad usa `sudo()` porque `qty_available`/`virtual_available`
pueden depender internamente de otros modelos instalados (p. ej. `mrp.bom`
para kits fantasma) a los que un usuario de Gestión y Costos no tiene por
qué tener acceso — es una lectura agregada de sólo consulta.

## 2. Seguridad

- ACL nuevas: `plan.weekly.preview.wizard` (+`.line`) para
  `group_management_user`/`group_management_manager`;
  `crop.program.import` (+`.line`) con el mismo patrón de
  `budget_import`/`budget_import_line` (readonly/user/manager).
- Reglas globales por empresa nuevas para `crop.program.import` y su línea.
- `check_company=True` en `stock_requirement.warehouse_id`;
  `_check_company_auto` en los modelos nuevos; `@api.constrains` de
  coherencia de empresa y de variedad para `crop_program_import.center_ids`.
- Sin cambios de rol: `action_generate_weekly_tasks`/wizard usan los mismos
  gates existentes (el plan sigue exigiendo `group_management_user` para
  escribir).

## 3. Interfaz

- Botón "Generar tareas semanales" del plan ahora abre la vista previa
  (`target=new`) en vez de escribir directo.
- Menú **Gestión y Costos > Planificación > Carga de programas desde
  Excel**.
- Formulario de necesidades de stock: almacén, métrica de disponibilidad,
  columnas Disponible/Faltante (con `decoration-danger` si hay faltante) y
  fecha de cálculo.

## 4. Migración

- Manifiesto `18.0.13.0.0`; nueva dependencia `stock`.
- `upgrades/18.0.13.0.0/post-migration.py` **idempotente**: preflight de
  sólo lectura (programas con variedades mezcladas) + log de conteo de
  necesidades de stock preservadas. Sin backfill de esquema (los campos
  nuevos son opcionales o el ORM los completa con su default al agregar la
  columna). Sin IDs numéricos, sin `commit()`.
- `data/management_sequences.xml`: secuencia
  `step.management.crop.program.import` (`IMPPROG/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **17**, en `tests/test_fase7_corte1.py`
(`TestFase7Corte1`) — total local **161** pruebas (antes 144).
`test_fase4_planning.py` se actualizó (sin agregar métodos) para pasar por
el flujo de vista previa en vez de escribir directo:

- vista previa no escribe hasta confirmar; el conteo de tareas a eliminar/
  crear/conservar coincide con lo aplicado; nunca toca tareas manuales;
  falla temprano si no hay presupuesto aprobado;
- política de precio: default `standard`, congela `product.standard_price`;
- centros con variedades distintas → `ValidationError`; misma variedad u
  todas vacías → OK;
- importador Excel de programas: fila válida crea receta; producto
  inexistente/dosis negativa/semana fuera de rango → error por fila; mismo
  archivo reimportado → idempotente; "sólo filas válidas" importa el
  subconjunto correcto; el programa importado siempre nace en borrador;
- necesidades de stock: `on_hand` lee existencia real; `free` resta
  reservado; `shortage_quantity = max(0, total−disponible)`; `computed_at`
  se fija y se actualiza en cada cálculo; métrica/almacén por defecto
  explícitos (no ambiguos).

### Verificación local

- `py_compile` de todos los `.py` nuevos/tocados: OK.
- Parseo de los 25 XML del addon: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF preexistentes en archivos no
  tocados por este corte).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

Se detectó y corrigió un bug real durante la verificación: la primera
corrida contra el clon de `LAB_TAREAS` (que tiene `mrp` instalado) falló
`TestFase6Stock.test_roles` con `AccessError` sobre `mrp.bom`, porque
`qty_available`/`virtual_available` pueden disparar internamente una
búsqueda de kit fantasma que exige acceso a Manufactura — el usuario de
prueba (`group_management_user`) no lo tiene. Se corrigió leyendo la
disponibilidad con `sudo()` (lectura agregada de sólo consulta) antes de
declarar la verificación completa.

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.13.0.0`) | RC 0 · **0 failed, 0 error(s)** (`odoo.tests.stats`: 174 tests, 208.18s, 60395 queries) |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s)** (`odoo.tests.stats`: 174 tests, 44.38s, 26499 queries) |

Migración `18.0.13.0.0/post-migration.py` ejecutada en el upgrade; registró
"sin programas con centros de variedades mezcladas" y "0 consolidación(es)
de necesidades de stock preservadas" sin error.

**Nota de infraestructura (para la siguiente entrega):** el clon de
`LAB_TAREAS` necesita el árbol completo de addons agrícolas para cargar sus
módulos ya instalados (`step_hr`, `step_machinery`, etc.). Se referenció
`/opt/dev_odoo18/odoo_agriculture` **de sólo lectura**, con el addon de esta
entrega copiado primero en el `addons_path` para que tome precedencia sobre
la copia allí presente; nunca se escribió en ese árbol (coherente con la
nota de memoria "el árbol de addons de Desarrollo lo lee Producción"). El
proceso real corre con `/usr/bin/python3.10` + `PYTHONPATH=/opt/odoo18`
(no el venv de `/opt/odoo18/venv`, que no tiene los paquetes que usan los
módulos agrícolas, p. ej. `matplotlib`).

Bases `MC_F7_UPG`/`MC_F7_CLEAN`, dump de `LAB_TAREAS`, directorio temporal
de addons/`data_dir` y `odoo.conf` desechables eliminados al terminar; no
quedaron bases ni archivos temporales en `odoo-new`. `LAB_TAREAS` no se
tocó (sólo se leyó vía `pg_dump`, nunca se escribió).

## 6. Decisiones y supuestos

- Ver `DECISION_LOG.md` §"Corte 1 post Fase 6" para el detalle completo:
  D04/D07/D08 confirmados y cerrados donde correspondía; D19 (necesidades
  de stock vs. inventario, nuevo) y D20 (discrepancia real del maestro
  Actividad en `step_hr`, nuevo) documentados.
- La disponibilidad de inventario es una **foto** al momento de "Calcular"
  (`computed_at`); no se recalcula en vivo al ver el documento.
- El programa importado desde Excel siempre nace en borrador: "aprobación
  segura" se interpreta como "nunca automática", no como un flujo de
  aprobación adicional distinto al que ya existe.

## 7. Límites y siguiente corte

- Sin Orden de Producción, sin PDF, sin integración OT (Corte 2/3 del
  documento del cliente).
- Sin puente de maestros con Actividades (`step_management_costs_agriculture`)
  — discrepancia real documentada en D20; requiere decidir cómo tratar el
  campo `product.template.actividad_id` antes de construirlo.
- Fórmula de estimación (D05) y precedencia de rendimiento estándar
  centro→variedad→grupo no formaban parte de los 7 frentes de este corte;
  siguen fuera de alcance.
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni
  escritura en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`. No se tocó
  Demo-SyS ni las sesiones de Claude que trabajan en Previred/Tesorería en
  el otro worktree.

Siguiente: puente de maestros con Actividades (D20) — requiere decidir con
el cliente/equipo de `step_hr` cómo tratar `product.template.actividad_id`;
o Corte 2 del documento del cliente (Orden de Producción semanal + PDF).
