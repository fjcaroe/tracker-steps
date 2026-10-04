# Recuperación de cambios locales — 03-10-2026

Se revisaron los archivos sin versionar de todos los worktrees registrados y
los cinco cambios pendientes del checkout principal. Se comparó el contenido
con objetos alcanzables desde ramas locales/remotas; los snapshots internos de
los agentes no se consideraron commits publicados.

## Código y documentación recuperados

| Destino | Contenido |
|---|---|
| `codex/cierre-cambios-locales` | Módulo `step_harvest_launcher`, herramientas de adjuntos/validación pública/DOCX, cinco documentos operativos y cambios locales de documentación y nombre de `step_hr` |
| `codex/helpdesk-layout-canonical` | Fuentes de inspección/corrección histórica de comentarios, sin ejecutar escrituras |
| `codex/t38-producers-completion` y `codex/t40-inventory-packing` | Procedimientos de pruebas QA recuperados de carpetas ignoradas |
| `codex/web-tracker-redesign` | Generador del manual con salidas fuera del checkout; validaciones de HTTP, aislamiento entre empresas y restricciones PostgreSQL, con README y retiro de supuestos antiguos |
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
`C:/Users/tito4/.codex/local-recovery/20261003/`: nueve ZIP para archivos visibles y ocultos por reglas de ignore,
`inventory.json`, `promotions.json`, `dispositions.json` y `cleanup-plan.json`.
Los hashes SHA-256 se verificaron contra el ZIP y el archivo local antes de
retirar cada original sin versionar. Los archivos recuperados permanecen en Git.

Se verificaron 1.445 archivos originales y se retiraron 1.426 archivos sin
versionar después de conservar o recuperar las fuentes útiles. El inventario
clasifica 244 copias de contenido ya alcanzable desde ramas, 929 archivos de
datos/resultados/adjuntos, 236 experimentos o herramientas históricas privadas,
31 fuentes recuperadas y cinco archivos modificados ya seguidos por Git. Las
herramientas parametrizadas de adjuntos y del parser se añadieron como derivados
de los experimentos recuperados.

Las copias antiguas de módulos, previews y paquetes generados no sustituyeron
fuentes vigentes. Adjuntos, datos de clientes, resultados de nómina/contabilidad,
scripts específicos de operaciones ya hechas y fuentes descargadas de terceros
quedaron en el respaldo privado fuera del repositorio público. Su inventario
completo es privado porque también contiene nombres y referencias de casos.
La inspección adicional de carpetas ignoradas recuperó 11 fuentes y archivó
325 archivos más (1.770 originales revisados; 1.751 originales retirados). Las
dependencias regenerables de node_modules/venv no se trataron como código propio.
El comprobador detecta fuentes ignoradas en carpetas temporales. No se añadieron
reglas generales para ocultar código.

`.worktrees/` y `step_harvest_web/` son checkouts independientes, no código
pendiente del repositorio padre. Se verifican por separado; Harvest Web conserva
su propio remoto y ramas.

## Continuidad entre agentes

`AGENTS.md` y `CLAUDE.md` remiten a `WORKFLOW_GIT_COMPARTIDO.md`. La entrega
requiere commit, push y `python tools/git/verify_handoff.py --require-pushed`.
Con `--all-worktrees` revisa también otros checkouts y Harvest Web. La herramienta
es de solo lectura; las cinco pruebas cubren cambios pendientes, commits sin
subir, falta de upstream, HEAD separado y código oculto por ignore. Hacer fetch antes de comprobar el remoto.

Se distribuyen estas reglas a las ramas de los worktrees registrados. Las ramas
de distintos productos mantienen su identidad y no se fusionan entre sí por
el hecho de limpiar archivos locales. Steps Móvil conserva su base canónica
`codex/steps-movil` y Web Tracker `codex/web-tracker-redesign`.

Esta recuperación no requiere volver a ejecutar despliegues históricos. El
despliegue del ticket 46 ya está verificado en `/truck/`; estos commits de
recuperación no cambian su frontend ni su API.

Validación de la recuperación: análisis de sintaxis de Python/shell y XML,
cinco pruebas aisladas del comprobador y siete casos de redirección de Harvest
con dobles de Odoo, sin acceso al servidor. Los ocho nombres históricos de
ramas T46 se avanzan por fast-forward a la base consolidada: no quedan builds
alternativos detrás de esos nombres. Las reglas compartidas se distribuyen
a las ramas de los 20 worktrees registrados durante la revisión; el checkout
temporal de T47 se retira después de publicar su cierre.

## Verificación final

- 28 ramas publicadas sin force-push; 19 worktrees restantes y el repositorio
  independiente Harvest Web sin cambios pendientes ni commits por subir.
- Las ocho ramas `ticket/46-*`, `codex/t46-movil-consolidado` y
  `codex/steps-movil` apuntan a `74290aae` después de integrar las reglas de cierre.
- Cinco pruebas del comprobador aprobadas. Se verificó sintaxis de 105 fuentes
  Python/shell de herramientas en los worktrees y XML del módulo recuperado.
- Siete casos de redirección/configuración de Harvest aprobados con dobles de
  Odoo. El controlador recuperado coincide por SHA-256 con los instalados en
  Desarrollo, Demo y Cerro el Plomo:
  `0763b536a47060446b68aaf3006fbed130c151d4240c36efc8fd154eb62d37ff`.
- `/truck/` conserva `assets/index-zbpnCxRX.js`, SHA-256
  `5968cae2b74f118af1d63b379fb14e53161e179b712eff000db46de286890717`.
  No hay cambios en `mobile/` ni `backend/` respecto del commit desplegado de T46.
  `tracker-steps-api.service` y nginx están activos; `/health` responde `ok`.

El checkout principal queda en `codex/cierre-cambios-locales`. Para continuar
Móvil, usar `C:/Users/tito4/Documents/Odoo-tracker-costos` sobre
`codex/steps-movil`; para Tracker, usar el worktree de
`codex/web-tracker-redesign`. La elección de rama es por producto, según las
instrucciones compartidas, aunque otro agente haya dejado un checkout abierto.
