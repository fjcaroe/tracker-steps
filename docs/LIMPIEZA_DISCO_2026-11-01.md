# Limpieza de disco del servidor Odoo — 01-11-2026 UTC

Solicitud explícita: eliminar backups y temporales por falta de espacio.
El trabajo comenzó el 31-10-2026 por la noche, hora de Chile.

## Alcance y selección

Servidor canónico: odoo-new, stepsconsulting/us-central1-c.
Se leyó el registro local de ambientes y la política canónica antes de intervenir.
El disco raíz de 200 GiB estaba al 100%, con aproximadamente 186 MiB libres.
El disco de datos independiente de 150 GiB conservaba 36 GiB disponibles.

- Journal: limpieza nativa de archivos archivados con vacuum-size=500M;
  liberó 2,9 GiB. No se cambió la configuración de retención.
- Backups: solo directorios management de development, sys, cerro y qa-cerro
  fechados antes de 20261018, conservando al menos los dos más nuevos por grupo.
  Steps tenía un único backup management y se conservó.
- Temporales de validación: solo subdirectorios data/filestore de ejecuciones
  management sin referencias activas y con más de 14 días de antigüedad.
  Se conservaron dumps fuente, código, logs y evidencias.
- /tmp: solo archivos regulares de paquetes tar/tgz/zip/gz de más de 7 días,
  sin referencias de procesos. No se hizo una limpieza recursiva general.
- Se conservaron los backups de los ambientes legados, las bases PostgreSQL,
  los filestores operativos y los datos de capacitación de QA-Cerro.

La selección inicial comprendió 66 backups, 161 filestores temporales y
289 archivos de paquetes. La aplicación vuelve a comprobar referencias activas,
rutas absolutas, ausencia de enlaces y antigüedad de descendientes, bajo
/run/lock/steps-environments.lock. Los procesos du/find de la propia auditoría
son lectores y se excluyeron de la detección de uso activo.

Antes de borrar se decodificaron por completo con pg_restore -f /dev/null
los nueve dumps retenidos de los cinco grupos. No equivale a un ensayo de
restauración funcional; no se modificó ni publicó ningún módulo Odoo.

## Evidencia

Los scripts de tools/ops/oneoff conservan la operación de esta fecha.
El aplicador archivado incorpora una bandera explícita para impedir una
repetición accidental; no es una política de retención recurrente.
Los manifiestos detallados quedan en el servidor bajo
/var/tmp/steps-cleanup-20261101-{plan,result}.json.
No contienen contraseñas. Se conserva una copia local fuera del checkout.

## Resultado final

Se eliminaron los 516 candidatos, sin omisiones: 66 backups de despliegues,
161 filestores de pruebas y 289 paquetes temporales. La fase de archivos
recuperó 26.212.106.240 bytes (24,41 GiB), además de los 2,9 GiB del journal.
El contador disponible al concluir fue 29.563.654.144 bytes (27,53 GiB).
df -h muestra la raíz en 167G usados / 28G libres, 86%; antes estaba al 100%.
El disco de datos conserva 105G usados / 36G libres, 75%.

Los nueve servicios Odoo registrados y postgresql@12-main permanecen activos.
Las páginas /web/login de Steps, SyS, Cerro, Desarrollo y QA-Cerro responden
HTTP 200. Estas comprobaciones son de disponibilidad; no se desplegaron
cambios funcionales ni se modificaron registros de negocio.

La acumulación de copias de validación y respaldos por despliegue sigue siendo
una fuente de crecimiento. Esta intervención es puntual y no instala cron,
timer ni borrado recurrente. La antigüedad por sí sola no autoriza borrar
overlays activos, bases de datos ni respaldos legados.

Verificación del archivo de scripts: py_compile correcto; el aplicador
archivado rechaza su ejecución sin la bandera de esta operación.
El du agregado del inventario se detuvo para reducir lecturas concurrentes;
la medición final corresponde al espacio libre real del filesystem.
