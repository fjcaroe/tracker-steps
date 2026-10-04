# Recuperación de cambios locales — 03-10-2026

Se revisaron los archivos sin versionar de todos los worktrees registrados y
los cinco cambios pendientes del checkout principal. Se comparó el contenido
con objetos alcanzables desde ramas locales/remotas; los snapshots internos de
los agentes no se consideraron commits publicados.

## Código y documentación recuperados

| Destino | Contenido |
|---|---|
| `codex/cierre-cambios-locales` | Módulo `step_harvest_launcher`, herramientas de adjuntos/validación pública/DOCX, cinco documentos operativos y cambios locales de documentación y nombre de `step_hr` |
| `codex/web-tracker-redesign` | Validaciones de HTTP, aislamiento entre empresas y restricciones PostgreSQL, con README y retiro de supuestos antiguos |
| `ticket/35-exportaciones` | Generador del icono y procedimientos históricos de instalación/prueba de Productores y Exportaciones |
| `codex/t39-sii-tax-parser` | Procedimientos históricos de T39 e inspector del parser con archivo HTML y año explícitos |
| `codex/t41-packing-operations` | Consulta de estado de módulos Packing; el requerimiento completo ya estaba versionado y se conservó su copia vigente |
| `codex/home-commercial-20261001` | Check histórico de SEO de la portada de septiembre, documentado como histórico |

El inventario público de fuentes recuperadas está en
`recovery/2026-10-03-recuperados.json`. La ruta y el hash identifican el contenido
recuperado, aunque después se amplíe la herramienta. No se ejecutaron scripts
históricos de despliegue, contabilización, nómina o publicación de comentarios.
Las pruebas de atrasos de T47 ya cubren el caso del script local; no se duplicó
el experimento sobre trabajadores reales.

## Archivos que salieron del checkout

Se guardó una copia verificable de cada archivo original en
`C:/Users/tito4/.codex/local-recovery/20261003/`: cinco ZIP por checkout afectado,
`inventory.json`, `promotions.json`, `dispositions.json` y `cleanup-plan.json`.
Los hashes SHA-256 se verificaron contra el ZIP y el archivo local antes de
retirar cada original sin versionar. Los archivos recuperados permanecen en Git.

Las copias antiguas de módulos, previews y paquetes generados no sustituyeron
fuentes vigentes. Adjuntos, datos de clientes, resultados de nómina/contabilidad,
scripts específicos de operaciones ya hechas y fuentes descargadas de terceros
quedaron en el respaldo privado fuera del repositorio público. Su inventario
completo es privado porque también contiene nombres y referencias de casos.
No se ocultaron carpetas de código con reglas generales de ignore.

`.worktrees/` y `step_harvest_web/` son checkouts independientes, no código
pendiente del repositorio padre. Se verifican por separado; Harvest Web conserva
su propio remoto y ramas.

## Continuidad entre agentes

`AGENTS.md` y `CLAUDE.md` remiten a `WORKFLOW_GIT_COMPARTIDO.md`. La entrega
requiere commit, push y `python tools/git/verify_handoff.py --require-pushed`.
Con `--all-worktrees` revisa también otros checkouts y Harvest Web. La herramienta
es de solo lectura; las cuatro pruebas cubren cambios pendientes, commits sin
subir, falta de upstream y HEAD separado. Hacer fetch antes de comprobar el remoto.

Se distribuyen estas reglas a las ramas de los worktrees registrados. Las ramas
de distintos productos mantienen su identidad y no se fusionan entre sí por
el hecho de limpiar archivos locales. Steps Móvil conserva su base canónica
`codex/steps-movil` y Web Tracker `codex/web-tracker-redesign`.

Esta recuperación no requiere volver a ejecutar despliegues históricos. El
despliegue del ticket 46 ya está verificado en `/truck/`; estos commits de
recuperación no cambian su frontend ni su API.
