# Limpieza de almacenamiento de Odoo — 23-11-2026

La intervención puntual en `odoo-new` retiró 180 bases privadas de
validaciones completadas y 168 respaldos de despliegue obsoletos.

| Volumen | Libre antes de la operación bajo bloqueo | Libre al terminar | Recuperado |
| --- | ---: | ---: | ---: |
| PostgreSQL, `SHOW data_directory` | 1,69 GiB | 34,64 GiB | 32,95 GiB |
| Raíz, incluye artefactos | 11,79 GiB | 32,66 GiB | 20,87 GiB |

Una limpieza separada retiró 288 MiB de journal archivado con más de 14 días.
Ese espacio ya estaba incluido en la medición inicial de raíz de la tabla.

El inventario previo encontró 927 bases, 646 con prefijo de validación
`MANAGEMENT_QA_`. El directorio `base` de PostgreSQL ocupaba unos 135 GiB
y el WAL unos 192 MiB. Las validaciones de tickets crean clones de cada
destino y de sus sucesivos ensayos. Los respaldos de despliegue guardan
además copias de volcado y filestore, con 29 GiB en `/opt/steps_backups`
antes de la limpieza.

El plan exigió un recibo de QA vinculado a una publicación del mismo commit,
un volcado del ambiente de origen decodificado por completo y ninguna sesión
activa en la copia. Se conservaron los 180 volcados de origen, y los
filestores, paquetes, logs y recibos de validación. Se usó
`/run/lock/steps-environments.lock`; el retiro de bases usó `dropdb` sin
terminar conexiones.

Para Desarrollo, Cerro y QA-Cerro se conservaron dos respaldos recientes por
ambiente. Se decodificaron ambos volcados de cada par y se verificaron por
SHA-1 todos los archivos referenciados en sus filestores. Permanecen los ocho
respaldos candidatos de SyS y Demo-SYS, cuyas alternativas carecían de
adjuntos referenciados. La búsqueda de esos adjuntos en los filestores
disponibles de ambos perfiles confirmó nueve huellas faltantes comunes.

Se verificó la ausencia de las 180 copias y 168 rutas retiradas, la presencia
de las seis bases canónicas del alcance y el estado activo de PostgreSQL y
los servicios Odoo registrados. Los volúmenes superan las reservas de 5 GiB
y 2 GiB para reanudar el ensayo Community.

Plan, recibo y verificación privados en
`~/.codex/local-artifacts/server-disk-cleanup-20261123` y evidencia remota
en `/opt/steps-validation/server-disk-cleanup-20261123`. SHA256 del recibo
`3a2fd28df781e4c7fcd3e89266f209fb1a30cdd86727055fd0302570ccf6d2ca`.
Herramienta versionada en `tools/ops/cleanup_managed_copies.py`.
