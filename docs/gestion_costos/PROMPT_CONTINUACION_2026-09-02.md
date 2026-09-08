# Prompt para continuar — Steps Gestión y Costos (nueva ventana de contexto)

Copia todo lo que sigue a un Claude Code nuevo.

---

Actúa como ingeniero senior de Odoo 18 y continúa la evolución del addon
`step_management_costs` ("Steps - Gestión y Costos"). Trabajo previo ya
entregado: Fase 0 + Fase 1 corte 1 + Fase 2 cortes 1 y 2. **No repitas ese
trabajo. No crees un segundo módulo. No renombres modelos/tablas/XML IDs. No
descartes datos.**

## Dónde está todo

- **Worktree de trabajo:** `C:\Users\tito4\Documents\Odoo-gestion-costos`
  (rama `codex/gestion-costos`, creada sobre `origin/codex/web-tracker-redesign`,
  commit base `9aa55c1`). **Trabaja SOLO aquí.**
- El checkout principal `C:\Users\tito4\Documents\Odoo`
  (rama `fix/previred-correcciones-2`) está sucio con trabajo ajeno — **no lo
  toques**. Tampoco `codex/web-tracker-redesign` ni el frontend Vite/React ni
  otros addons.
- **Sin commits.** Todo el trabajo previo está en el working tree sin
  commitear. El despliegue se hace por **tar sobre SSH**, no por git.
- **Nunca** `git push`, `merge`, `rebase`, ni modificar ramas remotas.

## Documentos de contexto (léelos antes de editar)

En `docs/gestion_costos/`:
- `MATRIZ_REQUISITOS.md`, `ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md`,
  `DECISION_LOG.md`, `DATA_MODEL.md` (Fase 0)
- `HANDOFF_FASE1_CORTE1.md`, `HANDOFF_FASE2_CORTE1.md`,
  `HANDOFF_FASE2_CORTE2.md`
- Plan maestro: `C:\Users\tito4\Documents\Odoo\docs\PLAN_DESARROLLO_GESTION_COSTOS_2026-09-02.md`
- Prompt inicial original: `C:\Users\tito4\Documents\Odoo\docs\PROMPT_INICIAL_CLAUDE_GESTION_COSTOS_2026-09-02.md`
- Paquete funcional fuente: `C:\Users\tito4\Downloads\1.6 Módulo Gestión y Costos\1.6 Módulo Gestión y Costos`
  (8 Word + 28 Excel). Para leer .docx/.xlsx usa
  `C:\Users\tito4\AppData\Local\Programs\Python\Python312\python.exe` con
  `python-docx` / `openpyxl` (ya instalados).

## Qué está IMPLEMENTADO y DESPLEGADO (versión actual `18.0.4.0.0`)

Recorrido: `18.0.1.1.0` → `18.0.2.0.0` (Fase 1 C1) → `18.0.3.0.0` (Fase 2 C1)
→ `18.0.4.0.0` (Fase 2 C2). Cada salto tiene su `upgrades/<versión>/` (C2 no
tiene script porque no cambió esquema persistente).

**Fase 1 C1 (`18.0.2.0.0`):** `_check_company_auto` + `check_company` en 10
modelos; 12 `ir.rule` de compañía **globales**; grupos nuevos
`group_management_readonly` y `group_management_approver` (cadena
readonly ⊂ user ⊂ approver ⊂ manager, se conservan los XML IDs
user/manager); aprobación con `approved_by_id/at`, `revision`,
`revision_of_id`/`superseded_by_id`, `reopen_reason`, `approval_snapshot`
(JSON) + `approval_hash` (sha256); `write()`/`unlink()` bloquean el aprobado;
asistente `step.management.budget.reopen.wizard`; `action_new_revision`;
distribución mensual no puede divergir del total (`_check_monthly_distribution`
con `float_compare`); `budget.center` con `unique(budget_id, center_id)` SQL;
gate de cuenta analítica por centro al aprobar (sin `required=True`);
`tests/test_management_costs.py` (22 casos).

**Fase 2 C1 (`18.0.3.0.0`):** `budget.group.flow_type` (`cost`/`income`)
propagado a líneas; `operational.budget.total_amount` = sólo costo, +
`total_income` + `margin`; `product.template`/`product.category`
`management_budget_group_id` + `_get_management_budget_group()` (producto →
subcategoría → categoría); **importador Anexo 1.6.2.1**:
`step.management.budget.import` + `.import.line` (`models/budget_import.py`),
menú "Presupuesto → Carga desde Excel", parseo openpyxl (límite 5000 filas,
corte por filas vacías, rechaza fórmulas), resolución de maestros por clave
única de empresa, vista previa con error por fila, **todo-o-nada** +
`import_valid_only`, idempotencia por `file_hash`; `operational.budget.
template_id` ahora OPCIONAL, `origin_type` (`template`/`import`/`manual`);
`tests/test_fase2_import.py` (9 casos).

**Fase 2 C2 (`18.0.4.0.0`):** `models/analytic_actuals.py` (hereda
`step.management.operational.budget`): `_read_analytic_actuals(date_from,
date_to)` lee **sólo `account.move.line` con `parent_state='posted'`**
imputados por `analytic_distribution` (robusto a multi-plan; NO usa
`account.analytic.line` porque los centros usan el plan "Centro de costos"
= `x_plan3_id`); naturaleza por `account_type` (`expense*`/`income*`); NC y
reversa con su signo; grupo por producto/categoría, sin grupo → "Sin
clasificar". Asistente `step.management.budget.variance.wizard` +
`.variance.line` (`wizard/budget_variance.py` + `_views.xml`), botón
"Comparar con real" en el presupuesto (aprobado/cerrado/reemplazado):
Budget / Actual / Var$ / **Var% recalculado desde totales** por
centro×grupo×mes×naturaleza, con "Ver asientos" (drill-down al
`account.move.line`). Sin migración de esquema (modelos transient).
`tests/test_fase2_variance.py` (5 casos, usa `AccountTestInvoicingCommon`).

**Pruebas:** `tests/` = **36/36 verde** en upgrade y clean install (última
corrida). El paquete se importa desde `tests/__init__.py`.

**Estado de servidores (GCP, instancia `odoo-new`):**
| Ambiente | DB | Servicio | Puerto | Versión |
|---|---|---|---|---|
| Desarrollo | `LAB_TAREAS` | `odoo18-dev.service` | 8075 | `18.0.4.0.0` |
| Demo | `STEPS_DEMO` | `odoo18-demo.service` | 8080 | `18.0.4.0.0` |
| Demo-SyS | `STEPS_DEMO_SYS` | `odoo18-demo-sys.service` | 8090 (localhost) | **NO instalado — decisión del usuario, no instalar** |

## Cómo verificar y desplegar (procedimiento ya probado)

**Acceso:** `gcloud compute ssh odoo-new --zone us-central1-c --command="..."`
(proyecto `stepsconsulting`, ya autenticado). El `--command` con comillas
anidadas y `$(...)` **se rompe con plink en Windows**: escribe scripts, haz
`gcloud compute scp` y ejecútalos por nombre.

**Construir el artefacto** (desde el worktree, sin commitear):
```bash
git add -A step_management_costs && TREE=$(git write-tree) && \
git archive --format=tar --prefix=step_management_costs/ "$TREE":step_management_costs \
  -o /c/Users/tito4/AppData/Local/Temp/claude/mc_deploy.tar && git reset -q
gcloud compute scp /c/Users/tito4/AppData/Local/Temp/claude/mc_deploy.tar odoo-new:/tmp/mc_deploy.tar --zone us-central1-c
```

**Verificar en bases DESECHABLES** (nunca en las compartidas): clona
`LAB_TAREAS` con `pg_dump | pg_restore` a `MC_*`, corre
`odoo-bin -c /etc/dev_odoo18.conf -d MC_* --addons-path=/tmp/mc_test_addons,...
-u step_management_costs --test-enable --test-tags=/step_management_costs
--stop-after-init --no-http --http-port 8991 --gevent-port 8992`. Repite con
`-i` en base nueva. Exige `RC=0` y `0 failed, 0 error`. Elimina las `MC_*` al
terminar. Hay scripts de ejemplo en
`C:\Users\tito4\AppData\Local\Temp\claude\...\scratchpad\` de la sesión
anterior (`mc_verify_*.sh`, `mc_status.sh`) — puede que ya no existan; recréalos.

**Desplegar** (script en `odoo-new:/tmp/mc_deploy_env.sh`, arg `dev` o `demo`):
toma backup fresco (`/opt/backups/mc_deploy_<env>_<TS>/` = dump `-Fc` +
`module.pre.tgz`), para el servicio, `-u step_management_costs
--stop-after-init` **exigiendo exit 0**, reinicia, verifica HTTP; **rollback
automático (drop+pg_restore+restaurar código+start) si falla**. Trampas ya
resueltas en el script:
- Dev corre el upgrade como OS user `odoo` (conf world-readable);
  **Demo como `demo_odoo18`** (`/etc/demo_odoo18.conf` es `-rw-r-----`
  root:demo_odoo18, NO legible por `odoo`). El script tiene `RUNUSER` por env.
- El deploy copia `/tmp/mc_new/step_management_costs` (extrae el tar antes).

**Ruido conocido e inofensivo** al hacer `-u` (Odoo continúa):
- `ERROR odoo.schema: product_template: unable to set NOT NULL on column
  'grupo_labor'` y `step_cosecha_registry.product_uom_id` — preexistente de
  `step_hr`/`step_cosecha` (NULLs históricos); ahora también sale bajo este
  módulo porque hereda `product.template`.
- `ERROR ... Some modules are not loaded ... ['steps_api']` — huérfano
  preexistente en las bases, ajeno a este addon.

## Qué sigue (elige y confirma alcance con el usuario)

Por orden del plan (§7.1: la primera vertical "presupuesto aprobado → real
contable → desviación" ya está funcionalmente cerrada):

1. **Terminar Fase 2**: presupuesto **general** (centros no agrícolas,
   formulario libre sin plantilla) y **maquinaria** (modelo de tarifa
   gastos/horas — el anexo 1.6.2.5 tiene un `#DIV/0!`, ver DECISION_LOG C6);
   promover la comparación de desviación de asistente a **vista SQL
   `_auto=False`** con `company_id`/ACL/regla global y prueba de dos
   compañías (plan §5.4, para volumen).
2. **Fase 3 — Estimaciones**: curvas de semanas/calibres/clases, estimación
   por cuartel, versiones, importación Excel. Ojo D05 (el texto duplica el
   rendimiento; usar conversión a kg).
3. **Fase 4 — Plan semanal y cosecha**: tareas semanales derivadas del
   presupuesto vigente, plan de cosecha, `period_service` (ISO-8601, W53,
   semanas que cruzan mes prorrateadas — D04).
4. **Fase 5 — Fito y fertilización**; **Fase 6 — OP, stock, integraciones**;
   **Fase 7 — Informes y endurecimiento** (catálogo D18).
5. Puentes opcionales (`step_management_costs_account_budget`, `_agriculture`,
   `_bpa`, `_machinery`, `_operations`) — ninguno creado aún.

## Reglas duras

- Trabaja SOLO en el worktree `codex/gestion-costos`. Sin commit salvo que el
  usuario lo pida; sin push/merge/rebase.
- **No instales nada en Demo-SyS** (decisión del usuario).
- Verifica SIEMPRE en base desechable antes de desplegar; el despliegue a
  Desarrollo/Demo lo ha venido autorizando el usuario corte a corte — pídelo.
- No conviertas campos a `required=True` sin auditar y migrar datos
  existentes. Migraciones idempotentes, sin IDs numéricos, sin `commit()`.
- Decisiones D01/D15 (Contabilidad: cuentas de resultado en alcance, NC/
  reversa/multimoneda, si "ingresos" entra, enriquecimiento OP/OT) siguen
  **pendientes de validación humana**. Los supuestos actuales están
  documentados en `models/analytic_actuals.py` (A1–A5); no inventes
  respuestas, documenta.
- No presentes verificaciones estáticas como prueba Odoo ejecutada. Si algo
  no se pudo correr, dilo con los comandos exactos pendientes.
- No dupliques contabilidad, monedas, productos, UdM ni cuentas analíticas.

Empieza leyendo los documentos de `docs/gestion_costos/` y el estado del
worktree (`git -C C:\Users\tito4\Documents\Odoo-gestion-costos status`),
propón el siguiente corte pequeño con su matriz requisito→cambio→prueba, y
pide confirmación de alcance antes de implementar.
