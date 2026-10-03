# Ticket 46 — consolidación y despliegue

Fecha: 03-10-2026, aproximadamente 20:04 America/Santiago.

## Resultado

Publicado en https://stepsapp.cl/truck/ desde `codex/steps-movil`.
Entrega ejecutada: `fd1d870367871b91b8198837a0de4779fd4c232d`.
Versión de app: `1.2.1`. JS servido: `index-zbpnCxRX.js`.
SHA-256 del JS público y del archivo construido:
`5968cae2b74f118af1d63b379fb14e53161e179b712eff000db46de286890717`.

Las ocho ramas `ticket/46-*` están incluidas en la historia canónica.
Se integraron por merge las variantes divergentes de I1, adaptando su comportamiento
a la base que conserva I2–I15 parciales, mapa, rutas y confirmación de jornada.
Las referencias antiguas se conservan como historia; no tienen commits exclusivos
fuera de `codex/steps-movil` y no deben desplegarse individualmente.

## Correcciones

- Restaurado el inicio idempotente con UUID del cliente en la API (I2), perdido por el despliegue antiguo.
- `/sessions/my` entrega el vínculo al parte y distancia; se recuperan horómetro y combustible del parte real.
- Al volver a primer plano se sincroniza y se consulta la jornada local por ID, sin asumir cierre por no aparecer en una lista limitada.
- Retomar exige selección y confirmación. No inicia automáticamente el GPS de una jornada compartida por centro de costo.
- No se borran puntos pendientes al detectar un cierre remoto; se reenvían aunque la jornada ya no esté activa en pantalla.
- Los registros agregados durante una petición de sincronización sobreviven a su resultado.
- Cierre y valores finales se guardan en cola antes de enviarse: un fallo después del cierre no pierde el parte final.
- Corregido el acumulador de kilómetros, que leía repetidamente una referencia antigua.
- Runbook y `mobile/AGENTS.md` apuntan a la rama canónica; el despliegue exige commit exacto, detecta diferencias no revisadas del servidor y dispone de rollback de fuentes/frontend.

## Validación

- Vitest: 34/34, incluidos concurrencia de cola y recuperación tras fallo del parte final.
- Pytest: 52/52 en entorno Python local aislado. Incluye recuperación del vínculo al parte y reintento idempotente después de cerrar.
- TypeScript y Vite: compilación correcta local y en el servidor.
- Navegador con API sintética: Retomar, recargar y mantener puerta de confirmación; Hoy con jornada/tareas; Supervisor. Ancho 375 px sin desbordamiento horizontal.
- PostgreSQL: respaldo restaurado a una base temporal; acceso ORM correcto a sesiones, partes y seis modelos móviles. Copia de ensayo eliminada.
- Producción: API y nginx activos, health correcto, OpenAPI con rutas/incidentes/refresh/sessions; nginx válido y JS público idéntico por SHA-256.
- Delta de API confirmado antes de publicar: solo `app/routers/sessions.py`.

Los dos primeros ensayos se detuvieron antes de cambiar producción por permisos
del directorio temporal y registro incompleto de modelos en el arnés, respectivamente.
Ambos se corrigieron en el runbook y el ensayo final pasó.

No se probaron GPS real, pantalla apagada ni Android/iOS en un teléfono físico.
I3/I9–I11/I16 y las integraciones parciales de Odoo siguen pendientes según el plan.

## Respaldos de la entrega publicada

- Base y API: `/opt/fernando_odoo18/backups/movil-consolidado-20261003T230318Z`.
- Frontend: `/var/www/steps-truck-frontend.pre-movil-20261003T230318Z`.
- Fuentes revisadas del servidor: `/tmp/steps-movil-release-QbLv27Sp`.

No se alteraron `/web_tracker/`, addons Odoo ni secretos.

## Revisión del resto del repositorio

Ver `docs/REVISION_RAMAS_2026-10-03.md`: inventario de todas las ramas y worktrees,
su respaldo en origin, PR abiertos y siguientes grupos a consolidar.
En el directorio principal permanecen cinco archivos versionados modificados y
845 no versionados; otros worktrees también conservan archivos temporales/documentos.
No se incluyeron a ciegas en el repositorio público ni se eliminaron.
