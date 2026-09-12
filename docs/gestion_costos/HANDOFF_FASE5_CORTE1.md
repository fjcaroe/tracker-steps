# Handoff — Fase 5, corte 1 (Fito y fertilización)

**Addon:** `step_management_costs` · **De:** `18.0.10.0.0` → **A:** `18.0.11.0.0`
**Fecha:** 2026-09-03 · **Autor:** Claude · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Motor común de programas fitosanitarios y de fertilización: receta **por
hectárea** que se amplifica por las hectáreas de cada centro/cuartel, se
valoriza al aprobar y queda inmutable (con snapshot y hash). No se acopla a la
Orden de Producción (Fase 6). No incluye carga Excel de programa (corte
posterior) ni informes (Fase 7).

### Modelos

- **`step.management.crop.program`** — cabecera multiempresa: folio `PROG/…`,
  `program_type` (`phyto`/`fert`), temporada, especie/variedad, política de
  precio, moneda, `center_ids` (M2m), `line_ids` (receta), `application_ids`
  (expansión), totales, estado `draft/approved/superseded`, revisión y
  auditoría de aprobación (`approved_by_id`, `approved_at`,
  `approval_snapshot`, `approval_hash`, `revision`, `revision_of_id`,
  `superseded_by_id`, `reopen_reason`).
- **`step.management.crop.program.line`** — receta por hectárea: producto,
  `dose_per_ha`, UdM, precio manual, objetivo/plaga/nutriente, semana
  calendario (1–53), carencia (`phi_days`) y reingreso (`rei_hours`) para
  OT-BPA.
- **`step.management.crop.program.application`** — expansión por (línea ×
  centro): hectáreas y dosis (snapshot), `quantity = dose_per_ha × hectares`
  (**siempre × hectáreas**, corrige C2), precio unitario, fuente y fecha del
  precio, importe. `unique(line_id, center_id)`.

### Acciones

- `action_compute_applications()` (operador): expande receta × centros;
  idempotente; exige hectáreas > 0 en cada centro.
- `action_approve()` (aprobador): resuelve el precio unitario según la
  política, congela precio/fuente/fecha por aplicación, arma el snapshot JSON
  + `sha256`, pasa a `approved`. Si es una revisión, su origen pasa a
  `superseded`.
- `action_new_revision()` / `_do_reopen(reason)`: revisión correctiva; sólo
  una sucesora activa por origen; sin bypass por contexto RPC.
- `action_duplicate()`: copia independiente (misma receta, sin aplicaciones,
  `revision = 1`, sin origen) para otra temporada/centros.

### Valorización (D07 — pendiente de validación de Compras/Contabilidad)

`price_policy` por programa:

- `standard` (por defecto): `product.standard_price` de la empresa.
- `last_invoice`: precio unitario de la última línea de factura de compra
  publicada del producto en la empresa; si no hay, cae a `standard`.
- `manual`: `manual_price` de la línea de receta.

El precio se congela por aplicación al aprobar (`unit_price`, `price_source`,
`price_date`) y queda en el snapshot.

## 2. Seguridad

- ACL: `crop.program` — consulta lee; usuario crea/edita sin `unlink`;
  administrador full. `crop.program.line` y `crop.program.application` —
  usuario CRUD; administrador full. Gate de rol en `action_approve` /
  `_create_revision` (aprobador), válido también por RPC.
- Reglas globales por empresa para los tres modelos.
- `check_company=True` en `program_id`, `line_id`, `center_id`, `product_id`;
  `_check_company_auto` en los tres modelos; `@api.constrains` de coherencia
  de empresa para el M2m de centros.
- Constraint SQL `unique(line_id, center_id)` en la aplicación.
- Inmutabilidad tras aprobar: `write`/`unlink` de cabecera, receta y
  aplicaciones bloqueados (campos protegidos); la corrección es una revisión.

## 3. Interfaz

- Menú **Gestión y Costos > Planificación > Programas fitosanitarios** y
  **Programas de fertilización** (dos acciones con dominio y contexto por
  tipo).
- Formulario con botones Calcular aplicaciones / Aprobar / Nueva revisión /
  Duplicar; pestañas Centros / Receta por hectárea / Aplicaciones /
  Aprobación (snapshot + hash). La receta oculta carencia y reingreso en
  programas de fertilización, y el precio manual salvo política «manual».

## 4. Migración

- Manifiesto `18.0.11.0.0`.
- `upgrades/18.0.11.0.0/post-migration.py` **idempotente**: sin backfill
  (modelos nuevos); registra el conteo preservado. Sin IDs numéricos, sin
  `commit()`.
- `data/management_sequences.xml`: secuencia `step.management.crop.program`
  (`PROG/%(year)s/`).

## 5. Pruebas

Pruebas nuevas: **15** (117 → **132** en la suite), en
`tests/test_fase5_programs.py` (`TestFase5Programs`):

- amplificación por hectáreas en fitosanitario **y** en fertilización (C2);
- expansión multi-centro e idempotencia;
- valorización con costo estándar y con precio manual;
- snapshot de aprobación + hash;
- inmutabilidad de cabecera / receta / aplicaciones tras aprobar;
- flujo de revisión + `superseded`;
- duplicado independiente (sin origen, sin aplicaciones, revisión 1);
- roles / RPC (operador calcula, no aprueba; consulta no crea; aprobador
  aprueba);
- centro de otra empresa rechazado;
- constraints de dosis negativa y semana fuera de 1–53;
- constraint SQL `unique(line_id, center_id)`;
- carencia/reingreso trasladados a la aplicación en fitosanitario;
- fertilización sin carencia/reingreso se aprueba sin problema.

### Verificación local

- `py_compile` de todos los `.py`: OK.
- Parseo de los 22 XML: OK.
- `git diff --check`: OK (sólo avisos LF/CRLF).

### Verificación Odoo real en `odoo-new` (sólo bases desechables)

| Escenario | Resultado |
|---|---|
| Upgrade de clon de `LAB_TAREAS` (`18.0.4.0.0` → `18.0.11.0.0`) | RC 0 · **0 failed, 0 error(s) of 132 tests** |
| Instalación limpia sin demo (`--without-demo=all`) | RC 0 · **0 failed, 0 error(s) of 132 tests** |

Migraciones `18.0.5.0.0`→`18.0.11.0.0` ejecutadas en el upgrade; la
`18.0.11.0.0/post-migration.py` registró «0 programa(s)… 0 aplicación(es)…»
sin error. Logs en `odoo-new`: `/tmp/mc_f5_upg_20260903_230148.log`,
`/tmp/mc_f5_clean_20260903_230148.log`.

Bases `MC_F5_UPG` / `MC_F5_CLEAN`, dump, `data-dir` temporal, tar y script
remoto eliminados al terminar; logs conservados en `/tmp/mc_f5_upg_*.log` y
`/tmp/mc_f5_clean_*.log`.

## 6. Decisiones y supuestos

- **C2 cerrada:** la cantidad de una aplicación siempre es `dosis/ha ×
  hectáreas`, también en fertilización.
- **D07 pendiente:** la política de precio y la fuente exacta (costo estándar,
  última factura, manual) quedan aisladas en `crop_program._resolve_unit_price`.
  El snapshot congela lo aplicado.
- Carencia y reingreso se guardan como **dato** (OT-BPA); su aplicación
  operativa (bloqueo de cosecha / reingreso) vive en operaciones, no aquí.
- La receta es por hectárea; el momento se registra como semana calendario
  (1–53) — la conversión a fechas concretas se hará al integrar con el plan
  semanal / la OP.

## 7. Límites y siguiente corte

- Sin carga Excel de programa ni duplicación masiva por lista de cuarteles.
- Sin cálculo de necesidades de stock (semana/mes/temporada) — Fase 6.
- Sin PDF ni informes (Fase 7).
- Worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
  `codex/gestion-costos`. Todo sin commit ni push. Sin despliegue ni escritura
  en `LAB_TAREAS`, `STEPS_DEMO` ni `STEPS_DEMO_SYS`.

Siguiente: Fase 6 — Orden de Producción semanal, necesidades de stock
(consolidando presupuesto + estimación + programas) e integración con OT;
o carga Excel de programa fito/ferti como corte menor.
