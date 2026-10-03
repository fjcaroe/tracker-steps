# Revisión de ramas y worktrees

Fecha: 2026-10-03T20:02-03:00.

## Ticket 46 — consolidado

Rama canónica: `codex/steps-movil`. Las ocho ramas históricas están integradas por historia,
incluyendo las dos variantes divergentes de I1. No queda un commit del ticket 46 fuera de la base canónica.
Se conservaron las referencias históricas para trazabilidad; no son destinos de despliegue.

La integración conserva I2, I4–I8, I12 parcial, I13 e I14/I15 parciales, mapa, rutas y confirmación de GPS.
Las variantes antiguas de I1 se adaptaron: no se retoma automáticamente una jornada por centro de costo
ni se borra una jornada porque no aparezca en una lista limitada. Consulta local por ID y revalidación al volver a primer plano.

Pendientes funcionales: I3/I16 requieren herramientas y cuentas para Android/iOS; I9–I11 diseño de pasajeros;
incidentes en Odoo, enlace de gastos con rendiciones y pruebas en teléfonos reales siguen pendientes según el plan.

## Inventario completo

Los conteos contra `develop` indican trabajo aún no incluido allí; no implican que falte respaldo o que deba desplegarse todo junto.
Las instrucciones vigentes mantienen producción del Web Tracker en `codex/web-tracker-redesign`.

| Rama | HEAD | Local/origin (delante/detrás) | Commits fuera de develop | PR abierto |
|---|---|---|---:|---|
| `codex/gestion-costos` | `5169875` | 0/0 | 0 | — |
| `codex/helpdesk-layout-canonical` | `e56ef13` | 0/0 | 11 | [#5](https://github.com/fjcaroe/tracker-steps/pull/5) → `develop` |
| `codex/home-commercial-20261001` | `8eedd77` | 0/0 | 21 | — |
| `codex/homepage-prod-seo-20260911` | `2fdd2f2` | 0/0 | 5 | — |
| `codex/steps-movil` | `f2727dd` | 0/0 | 39 | — |
| `codex/steps-task` | `d3e63cd` | 0/0 | 9 | — |
| `codex/t22-t30-integraciones` | `722a56e` | 0/0 | 4 | — |
| `codex/t27-studio-migration` | `719300f` | 0/0 | 6 | — |
| `codex/t30-productores-revision` | `9397ae5` | 0/0 | 28 | [#8](https://github.com/fjcaroe/tracker-steps/pull/8) → `ticket/35-exportaciones` |
| `codex/t38-producers-completion` | `a63dfaf` | 0/0 | 46 | [#11](https://github.com/fjcaroe/tracker-steps/pull/11) → `ticket/35-exportaciones` |
| `codex/t39-sii-tax-parser` | `d90f928` | 0/0 | 2 | [#9](https://github.com/fjcaroe/tracker-steps/pull/9) → `develop` |
| `codex/t40-inventory-packing` | `e908ef8` | 0/0 | 31 | [#10](https://github.com/fjcaroe/tracker-steps/pull/10) → `ticket/35-exportaciones` |
| `codex/t41-packing-operations` | `d53fab8` | 0/0 | 43 | [#12](https://github.com/fjcaroe/tracker-steps/pull/12) → `codex/t40-inventory-packing` |
| `codex/t42-homepage-apps` | `9534453` | 0/0 | 16 | — |
| `codex/t46-movil-consolidado` | `f2727dd` | 0/0 | 39 | — |
| `codex/tracker-costos-integracion` | `c043a99` | 0/0 | 19 | [#14](https://github.com/fjcaroe/tracker-steps/pull/14) → `codex/web-tracker-redesign` |
| `codex/tracker-unificado` | `4f7f90c` | 0/0 | 21 | — |
| `codex/web-tracker-redesign` | `358072d` | 0/0 | 13 | — |
| `develop` | `7c78302` | 0/0 | 0 | — |
| `docs/helpdesk-notas-ia-2026-09` | `0f63984` | 0/0 | 1 | — |
| `ticket/22-inventario-tarja-fruta` | `f06c473` | 0/0 | 5 | — |
| `ticket/23-bpa-inventario-consumo` | `6b2c3ae` | 0/0 | 6 | [#2](https://github.com/fjcaroe/tracker-steps/pull/2) → `develop` |
| `ticket/24-maquinaria-inventario-consumo` | `9341509` | 0/0 | 5 | [#3](https://github.com/fjcaroe/tracker-steps/pull/3) → `develop` |
| `ticket/25-dispatch-guide` | `2d13f75` | 0/0 | 2 | — |
| `ticket/25-dispatch-guide-completo` | `65352bd` | 0/0 | 8 | [#7](https://github.com/fjcaroe/tracker-steps/pull/7) → `ticket/25-dispatch-guide` |
| `ticket/27-analytic-precision` | `ed0987e` | 0/0 | 7 | — |
| `ticket/27-fletes-mejoras` | `fa7c501` | 0/0 | 3 | — |
| `ticket/28-bancoestado` | `8a17879` | 0/0 | 1 | — |
| `ticket/28-bancoestado-aprobacion` | `52789ba` | 0/0 | 2 | — |
| `ticket/30-compras-contrato-anticipo` | `c755427` | 0/0 | 4 | — |
| `ticket/34-aserradero-step-sawmill` | `de856bf` | 0/0 | 2 | — |
| `ticket/35-exportaciones` | `1897186` | 0/0 | 24 | [#4](https://github.com/fjcaroe/tracker-steps/pull/4) → `develop` |
| `ticket/43-gastos-rendiciones` | `2c6da14` | 0/0 | 2 | — |
| `ticket/44-contract-paid-days` | `521126a` | 0/0 | 1 | [#13](https://github.com/fjcaroe/tracker-steps/pull/13) → `develop` |
| `ticket/46-movil-i1-jornada-no-se-pierde` | `5335d8f` | 0/0 | 24 | — |
| `ticket/46-movil-i12-pausas` | `84437ab` | 0/0 | 29 | — |
| `ticket/46-movil-i2-jornada-sin-senal` | `267b3f7` | 0/0 | 26 | — |
| `ticket/46-movil-i4-i15` | `5c01e8f` | 0/0 | 28 | — |
| `ticket/46-movil-jornada-no-se-pierde` | `54ce5dc` | 0/0 | 25 | — |
| `ticket/46-movil-jornada-persistente` | `2439f12` | 0/0 | 24 | — |
| `ticket/46-movil-mejoras` | `e40c0fa` | 0/0 | 30 | — |
| `ticket/46-movil-restaurar-build` | `b5ae3e3` | 0/0 | 31 | — |
| `ticket/47-descuento-atrasos` | `d8c02f1` | 0/0 | 2 | — |

## Comprobación de integración del ticket 46

| Rama histórica | Commits fuera de la canónica |
|---|---:|
| `ticket/46-movil-i1-jornada-no-se-pierde` | 0 |
| `ticket/46-movil-i12-pausas` | 0 |
| `ticket/46-movil-i2-jornada-sin-senal` | 0 |
| `ticket/46-movil-i4-i15` | 0 |
| `ticket/46-movil-jornada-no-se-pierde` | 0 |
| `ticket/46-movil-jornada-persistente` | 0 |
| `ticket/46-movil-mejoras` | 0 |
| `ticket/46-movil-restaurar-build` | 0 |

## Cambios locales fuera de Git

Se revisaron todos los worktrees registrados. No se añadieron masivamente archivos temporales, documentos ni respaldos al repositorio público.

| Worktree / rama | Archivos versionados modificados | Archivos no versionados |
|---|---:|---:|
| `ticket/34-aserradero-step-sawmill` (Documents/Odoo) | 5 | 845 |

Cambios versionados en `ticket/34-aserradero-step-sawmill`: `LAUDE.md`, `docs/CLAUDE_SEPARACION_MODULO_MOVILIZACION.md`, `docs/DEPLOY_WEB_TRACKER.md`, `docs/PROMPT_CLAUDE_TESORERIA_CONTABILIDAD_2026-08-29.md`, `step_hr/__manifest__.py`.


No versionados en `ticket/34-aserradero-step-sawmill`: `tmp` (532), `docs` (216), `output` (44), `"tmp` (26), `.codex-tmp` (14), `step_harvest_launcher` (8), `.worktrees` (2), `AGENTS.md` (1), `step_harvest_web` (1), `t39_deploy.tgz` (1).

| `codex/helpdesk-layout-canonical` (helpdesk-layout/Odoo) | 0 | 0 |
| `codex/t46-movil-consolidado` (t46-movil-consolidado/Odoo) | 0 | 0 |
| `codex/t27-studio-migration` (ticket27-studio-migration/Odoo) | 0 | 0 |
| `codex/t30-productores-revision` (ticket30-productores/Odoo) | 0 | 0 |
| `ticket/35-exportaciones` (ticket35-productores/Odoo) | 0 | 9 |

No versionados en `ticket/35-exportaciones`: `.codex-tmp` (9).

| `codex/t38-producers-completion` (ticket38-producers/Odoo) | 0 | 0 |
| `codex/t39-sii-tax-parser` (ticket39-sii-tax/Odoo) | 0 | 10 |

No versionados en `codex/t39-sii-tax-parser`: `tmp` (7), `"tmp` (3).

| `codex/t40-inventory-packing` (ticket40-fruit-inventory/Odoo) | 0 | 0 |
| `codex/t41-packing-operations` (ticket41-packing/Odoo) | 0 | 0 |
| `codex/t42-homepage-apps` (ticket42-homepage/Odoo) | 0 | 0 |
| `codex/web-tracker-redesign` (tracker-layout-protection/Odoo) | 0 | 0 |
| `codex/home-commercial-20261001` (.worktrees/home-commercial) | 0 | 2 |

No versionados en `codex/home-commercial-20261001`: `commercial-preview.css` (1), `commercial-preview.html` (1).

| `ticket/44-contract-paid-days` (.worktrees/ticket44) | 0 | 0 |
| `codex/gestion-costos` (Documents/Odoo-gestion-costos) | 0 | 575 |

No versionados en `codex/gestion-costos`: `tmp` (548), `docs` (25), `AGENTS.md` (1), `"tmp` (1).

| `codex/steps-task` (Documents/Odoo-steps-task) | 0 | 0 |
| `ticket/25-dispatch-guide-completo` (Documents/Odoo-t25) | 0 | 0 |
| `ticket/43-gastos-rendiciones` (Documents/Odoo-t43) | 0 | 0 |
| `codex/steps-movil` (Documents/Odoo-tracker-costos) | 0 | 0 |

## Siguientes consolidaciones por producto

- Productores / inventario / packing: T35 como base de T30/T38/T40 y T41 sobre T40; revisar los PR #4, #8, #10, #11 y #12 como conjunto.
- Nómina: T44 y T47 son cambios independientes pendientes de integrar con sus pruebas de remuneraciones.
- Fletes: variantes T27 de Studio, mejoras y precisión analítica requieren revisión conjunta.
- Tesorería: T28 aprobación está encima de T28 BancoEstado; consolidar esa cadena.
- Tracker y costos: las ramas de costos, unificación y Web Tracker tienen destinos distintos; revisar PR #14 sin alterar la rama productiva del Web Tracker.
- Otras entregas: T22–T25, T34, T39, T42, T43, homepage y soporte conservan sus ramas/PR según la tabla.

No se fusionaron módulos ajenos al ticket 46 ni se descartaron los archivos locales pendientes. Esta revisión registra exactamente lo pendiente; su integración funcional requiere pruebas y destinos por módulo.
