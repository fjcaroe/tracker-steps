# Handoff — Fase 2, corte 4

**Addon:** `step_management_costs` · **De:** `18.0.5.0.0` → **A:** `18.0.6.0.0`
**Fecha:** 2026-09-03 · **Autor:** Codex · **Estado:** implementado y verificado, sin despliegue

## 1. Resultado de la revisión

La suite anterior estaba verde, pero el análisis del código encontró cuatro
defectos P0 no cubiertos:

1. `action_reopen` devolvía el mismo aprobado a borrador y permitía sobrescribir
   la evidencia original al aprobar otra vez.
2. Los contextos `mc_reopen` y `mc_supersede` eran enviables por RPC y podían
   saltarse el congelamiento de cabecera/detalle.
3. El presupuesto general no admitía ingresar valores directos sin
   cantidad/tarifa, ni tenía una acción UI que lo llevara a `calculated`.
4. Dos centros con la misma cuenta analítica producían atribución silenciosa al
   último centro del diccionario.

También se corrigieron conciliación monetaria, moneda de presupuesto, signo de
cantidades en notas de crédito, duplicados mensuales e integridad del staging.

## 2. Cambios implementados

### Revisión e inmutabilidad

- “Crear corrección” genera una nueva revisión `draft` con centros, líneas y
  meses copiados; el aprobado original no cambia.
- El motivo queda en la revisión; el chatter del original registra la copia.
- Sólo puede existir una sucesora activa por origen; una alternativa cancelada
  permite crear el siguiente número de revisión.
- Una revisión sólo reemplaza un origen que aún esté `approved` o `closed`.
- Se eliminaron los bypass de congelamiento basados en contexto.
- Se congelaron también `budget_version` y notas del aprobado.

### Presupuesto general y conciliación

- `budget.line.calculation_mode`: `quantity` o `direct`.
- `direct_amount` en línea y mes.
- `monthly_amount` y conciliación obligatoria de montos.
- En modo cantidad se concilian cantidad y monto; en modo directo se concilia
  el monto y la cantidad es opcional.
- El modo directo sólo es válido en presupuesto general.
- Nueva acción `action_prepare_general` y botón “Validar presupuesto”.
- Una línea no puede usar un centro ausente de la pestaña Centros.
- Constraint SQL `unique(budget_line_id, month)`; la pre-migración aborta con
  IDs accionables si detecta duplicados heredados.
- El snapshot incluye modo, monto directo, monto mensual, fecha de conversión y
  monto convertido por mes.

### Real analítico

- Se bloquea aprobación/comparación si dos centros del presupuesto comparten
  cuenta analítica.
- `balance` se convierte desde moneda de compañía a moneda del presupuesto a la
  fecha del apunte.
- Las cantidades de notas de crédito/reversas reciben el mismo signo económico
  que el monto.
- El fallback producto→categoría ignora grupos de otra empresa.
- El rango del asistente valida `Desde <= Hasta`.

### Importación segura

- `.xlsm` se rechaza; sólo `.xlsx`.
- Límite de archivo de 10 MB y Base64 validado.
- Filas repetidas de la misma clave/mes se agregan antes de crear el mes.
- Cantidad cero con monto agrícola se rechaza y dirige al modo directo general.
- El operador sólo lee líneas de staging; creación, borrado y marca `imported`
  se realizan dentro del servicio controlado del lote.

## 3. Migración

- Manifiesto: `18.0.6.0.0`.
- `upgrades/18.0.6.0.0/pre-migration.py`: preflight de meses duplicados, sin
  corrección silenciosa.
- `post-migration.py`: inicializa `calculation_mode='quantity'` de forma
  defensiva y recomputa montos/distribuciones almacenados.
- En el clon ejecutado: 14 líneas y 14 meses recalculados; sin errores.

## 4. Pruebas

Verificación local:

- `py_compile`: OK.
- Parseo de todos los XML: OK.
- `git diff --check`: OK.

Verificación Odoo real en `odoo-new`, usando únicamente bases desechables:

| Escenario | Resultado |
|---|---|
| Upgrade de clon `LAB_TAREAS` a `18.0.6.0.0` | RC 0 · **0 failed, 0 errors of 57 tests** |
| Instalación limpia sin demo | RC 0 · **0 failed, 0 errors of 57 tests** |

Se agregaron pruebas para monto directo, conciliación monetaria, restricción de
mes, copia de revisión general, bloqueo del contexto forjable, segunda sucesora,
cuenta analítica compartida, centro fuera de asignaciones, staging no editable,
`.xlsm`, agregación de filas duplicadas y signo de cantidad de NC.

Las bases `MC_F2C4_UPG` y `MC_F2C4_CLEAN` fueron eliminadas. También se retiró
el dump temporal que el primer cleanup no pudo borrar por propiedad de
`postgres`. Los logs de evidencia permanecen en
`/tmp/mc_f2c4_*_20260903_014503.log`.

## 5. Estado y límites

- Worktree: `C:\Users\tito4\Documents\Odoo-gestion-costos`.
- Rama: `codex/gestion-costos`.
- Todo permanece sin commit y sin push.
- No hubo despliegue ni escritura en `LAB_TAREAS`, `STEPS_DEMO` o
  `STEPS_DEMO_SYS`.
- Demo-SyS permanece fuera de alcance por decisión previa.
- Los supuestos contables A1–A5 siguen pendientes de validación humana.

## 6. Siguiente corte recomendado

Cerrar Fase 2 con una de estas dos rutas, en orden de seguridad:

1. reportes persistentes de desviación (`_auto=False`) sólo después de aprobar
   A1–A5; o
2. presupuesto de maquinaria, definiendo horas cero como error de datos y
   separando combustible, lubricantes, repuestos, mantención, arriendo y
   depreciación.

Si la validación contable no está disponible, el siguiente corte independiente
es Fase 3A: maestros de curva y validación 100% para semanas, calibres y clases,
sin calcular aún la estimación final.
