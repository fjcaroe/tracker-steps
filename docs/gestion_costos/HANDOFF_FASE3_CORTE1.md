# Handoff — Fase 3, corte 1

**Addon:** `step_management_costs` · **De:** `18.0.6.0.0` → **A:** `18.0.7.0.0`
**Fecha:** 2026-09-03 · **Autor:** Codex · **Estado:** implementado y verificado, sin despliegue

## 1. Alcance

Se implementó el núcleo independiente de Estimaciones definido en
`1.6.4 Estimaciones de Cosecha.docx` y `Anexo 1.6.4.1`:

- unidades de estimación con factor de conversión a kilogramos;
- categorías y clases de fruta, incluyendo marcas Cosecha/Packing;
- grupos de calibre y calibres;
- curvas de semanas calendario, grupos de calibre y clases de fruta;
- validación exacta del 100 %, sin calcular todavía el documento de estimación.

La fórmula contradictoria del Word no se incorporó en este corte. Para el
siguiente se mantiene D05: `Total UE × factor kg`, sin volver a multiplicar por
rendimiento.

## 2. Integridad, seguridad y auditoría

- Todos los modelos tienen compañía y reglas globales multiempresa.
- Las relaciones usan `check_company=True` y `_check_company_auto`.
- Semanas limitadas a 1–53.
- Cada línea contiene exactamente una dimensión compatible con el tipo de curva.
- Porcentaje individual `(0, 100]`; total exacto 100 % para validar.
- `unique(curve_id, dimension_key)` evita dimensiones repetidas a nivel SQL.
- Sólo un administrador mantiene y valida maestros; los demás perfiles leen.
- Curvas validadas y sus líneas quedan congeladas; sólo la acción administrativa
  “Volver a borrador” permite corregirlas.
- Se registra usuario y fecha de validación en chatter.

## 3. Interfaz y migración

- Nuevo menú `Estimaciones > Curvas de estimación`.
- Maestros nuevos bajo `Maestros`: unidades, categorías, clases, grupos de
  calibre y calibres.
- Vista de curva adapta columnas según tipo y muestra total/estado.
- Upgrade `18.0.7.0.0/post-migration.py`; las tablas nuevas se crean por ORM y
  la migración registra la cantidad de curvas existentes.

## 4. Pruebas

Pruebas nuevas: 9, en `tests/test_fase3_curves.py`.

| Escenario real en `odoo-new` | Resultado |
|---|---|
| Upgrade de clon desechable de `LAB_TAREAS` | RC 0 · **0 failed, 0 errors of 66 tests** |
| Instalación limpia sin demo | RC 0 · **0 failed, 0 errors of 66 tests** |

También pasaron `py_compile`, parseo de 17 XML y `git diff --check`.
Las bases `MC_F3C1_UPG` y `MC_F3C1_CLEAN`, el dump, los addons temporales y el
script remoto fueron eliminados. Logs conservados:

- `/tmp/mc_f3c1_upg_20260903_020759.log`
- `/tmp/mc_f3c1_clean_20260903_020759.log`

Los mensajes `steps_api` ausente y `grupo_labor` NOT NULL son ruido histórico
del clon; el upgrade continuó y finalizó correctamente.

## 5. Estado y siguiente corte

- Worktree: `C:\Users\tito4\Documents\Odoo-gestion-costos`.
- Rama: `codex/gestion-costos`.
- Cambios sin commit ni push.
- Sin despliegue ni escritura en `LAB_TAREAS`, `STEPS_DEMO` o
  `STEPS_DEMO_SYS`; Demo-SyS continúa fuera de alcance.

Siguiente: Fase 3, corte 2, documento de estimación por centro/cuartel,
versiones, método Planta/Hectárea/Kilo, selección de tres curvas validadas y
generación reproducible de distribuciones. La importación Excel y los informes
quedan para cortes posteriores.
