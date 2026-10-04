# Infraestructura Odoo en GCP — 23 de septiembre de 2026

Proyecto `stepsconsulting`, zona `us-central1-c`. Producción permanece en la VM
`odoo-new` (`n2d-standard-2`, 2 vCPU, 8 GiB RAM, IP `35.222.25.110`). Nginx,
las instancias Odoo 18, Tracker API y Teltonika siguen como servicios systemd.
PostgreSQL 12 sigue local en la misma VM.

## Almacenamiento

- Arranque: `odoo-new-disk`, 200 GiB `pd-standard`.
- Datos: `odoo-data-balanced-20260923`, 100 GiB `pd-balanced`, montado en
  `/srv/odoo-data` por UUID.
- PostgreSQL `/var/lib/postgresql/12/main` y nueve directorios `filestore`
  están montados por bind desde el disco de datos. Las entradas están en
  `/etc/fstab`, entre `BEGIN ODOO BALANCED DATA` y `END ODOO BALANCED DATA`.
- Las copias originales siguen ocultas bajo los puntos de montaje en el disco
  de arranque para permitir una reversión controlada. No restaurar solamente
  el disco de arranque: la base actual y los adjuntos están en el disco de datos.

La política `odoo-daily-backup` está asociada a ambos discos y retiene los
snapshots programados durante siete días. Snapshots manuales de punto de
control: `odoo-root-post-migration-20260923` y
`odoo-data-post-migration-20260923` (ambos `READY`). Para una recuperación,
crear los dos discos desde esos snapshots, adjuntarlos a una VM compatible,
verificar los UUID y los bind mounts de `/etc/fstab`, y arrancar PostgreSQL
antes de Odoo. Probar la restauración en una VM aislada antes de cambiar DNS.

## PostgreSQL y rendimiento

`/etc/postgresql/12/main/conf.d/odoo-performance.conf` establece 768 MiB de
`shared_buffers`, 4 GiB de `effective_cache_size`, `work_mem` de 4 MiB,
`pg_stat_statements`, `track_io_timing`, registro de consultas de más de un
segundo, esperas por bloqueo y autovacuum lento. La extensión
`pg_stat_statements` está creada en la base `postgres` y permite analizar
consultas de todas las bases. Los logs están en
`/var/log/postgresql/postgresql-12-main.log`.

La VM promedió 2,5% de CPU durante los 30 días previos al cambio; p95 5,3%.
Antes del cambio el disco de 200 GiB era HDD `pd-standard`, PostgreSQL tenía
128 MiB de `shared_buffers` y no había registro de consultas lentas. El
impacto real de latencia debe medirse con tráfico comparable durante varios días.

## Bases retiradas

Se eliminaron estas ocho bases junto con sus filestores:

- `CODEX_TEST_20260828_BIMONEDA`
- `CODEX_TEST_20260828_PREVIRED`
- `CODEX_TEST_BIM_FINAL_20260829`
- `CODEX_TEST_PREV_FINAL_20260829`
- `CODEX_TEST_PREV_FINAL2_20260829`
- `karo_step_hr_transition_test`
- `odoo18_test_db`
- `Prueba_Simple`

Cada una tiene `pg_dump -Fc` y paquete de filestore verificados por SHA-256 en
`gs://steps-backups-fer/retired-odoo-databases/retired_odoo_databases_20260923T133800Z/`.
También existe una copia local root-only en
`/opt/backups/retired_odoo_databases_20260923T133800Z`.

## Recursos antiguos retirados

La VM apagada `odoo-restore` y sus discos de 10 y 200 GiB, más el disco
regional sin uso `odoo18-luis-disk` de 200 GiB, se eliminaron después de
verificar tres snapshots finales en estado `READY`:

- `odoo-restore-boot-final-archive-20260923`
- `odoo-restore-data-final-archive-20260923`
- `odoo18-luis-final-archive-20260923`

Se retiraron 32 snapshots antiguos de series de máquinas ya desaparecidas.
Se conservó el más reciente de cada serie, además de `odoo-prod` y
`odoo-instance-snapshot` como puntos históricos.

## Crons y contenedores

SyS, demos, Cerro El Plomo y Everfruit no mostraron crons atrasados.
`LAB_TAREAS` tenía 13 tareas con más de una hora de atraso porque Odoo omite
los crons mientras hay módulos pendientes de instalar/actualizar/eliminar.
`steps_qa` conserva 71 crons vencidos desde agosto y no tiene un servicio
dedicado que los ejecute. No iniciar todos esos crons sin revisar primero su
función.

Docker Engine ya existía para `odoo19-pg`. Se instaló Docker Compose v5.5.1
con checksum verificado. La migración de un Odoo 18 personalizado a Compose
requiere una imagen reproducible con sus dependencias Enterprise y módulos
Steps, y una prueba aislada antes de reemplazar cualquier servicio systemd.

## Costos y siguientes decisiones

Los discos provisionados bajaron de 610 a 300 GiB: 200 GiB estándar más
100 GiB balanceados. A precios de lista aproximados en `us-central1`, el
costo fijo de discos pasa de USD 32,40 a USD 18/mes; el total del proyecto
dependerá de snapshots, tráfico y créditos. Evaluar un compromiso de un año
para la VM después de observar una semana de rendimiento y factura real; no
se compró un compromiso durante esta intervención.
