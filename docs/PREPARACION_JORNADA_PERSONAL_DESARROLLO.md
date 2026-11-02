# Jornada personal preparada en Desarrollo — 02-11-2026

El usuario confirmó retirar sus máquinas antiguas de prueba, conservar únicamente
el vehículo personal con GPS y preparar los datos para probar la aplicación.
Confirmó cuatro pasajeros sin conductor y autorizó un servicio con cuatro
personas claramente ficticias. Los identificadores, nómina, RUT, patente,
coordenadas, sesiones, planes y respaldos se conservan exclusivamente en evidencia
privada; no forman parte del repositorio público.

## Resultado

- 18 vehículos antiguos de la compañía de Desarrollo archivados en Flota,
  conservando registros, lecturas y relaciones históricas.
- 19 proyecciones antiguas retiradas del mapa, comprobando que no tenían
  posiciones, asociaciones de GPS ni incidentes. Los eventos de auditoría
  existentes se conservan. La ficha real, asignación, aprobación, receptor,
  SIM e historial GPS siguen en su dominio original.
- Un vehículo disponible para jornadas, enlazado a la ficha nativa existente;
  cuatro asientos de pasajeros y cinco asientos totales en Flota. El centro
  Interno existente se reutiliza mediante referencias explícitas, incluidas
  las relaciones analíticas de la ficha. Se configura Conducción en la actividad
  Operaciones existente. No se inventa una labor de cosecha para conducir el auto.
- El conductor se resuelve desde `hr.employee.user_id`, no por coincidencia de
  nombre. Se corrigió la proyección legada con RUT diferente, sin cambiar el
  trabajador nativo ni el conductor del catálogo productivo.
- Un servicio de prueba de la cuenta piloto, con dos paradas sin coordenadas
  inventadas y cuatro nombres/documentos explícitamente ficticios. La creación
  es idempotente y no registra abordajes ni viajes reales por adelantado.

Tracker móvil 1.6.2 precarga los valores cuando hay un único vehículo. Para
vehículos configurados por distancia (`kmpl`), no pide horómetro; el estanque
es opcional y una lectura ausente se guarda como NULL, no como cero. Tampoco se
inventa consumo sin ambas lecturas. El odómetro físico permanece en su ficha
nativa y no se confunde con horas o distancia calculada por GPS. Las máquinas
por hora conservan sus campos obligatorios. La recuperación desde otro teléfono
también conserva lecturas desconocidas como NULL.

## Separación de la operación de Desarrollo

El catálogo clásico carecía de ámbito por ambiente. Dar de alta el auto en su
base compartida lo habría mostrado también en otros frontends. Por eso se
instaló `tracker_steps_development` únicamente con el esquema vigente y las filas
necesarias del piloto: cuenta existente con el mismo ID, vehículo, conductor,
actividad, labor y centro. No se copiaron vehículos GPS, posiciones, otros
clientes o empresas. Se conservó la identidad JWT del acceso Odoo; las claves
no se rotaron ni se publicaron. No es una segunda ficha nativa: las proyecciones
mantienen los IDs externos y las relaciones a los maestros de Flota y Empleados.

`steps-tracker-dev-api` permanece en loopback 8012, expuesto solo por HTTPS
`desarrollo.stepsapp.cl/tracker-dev-api/`. Su configuración privada añade
`/etc/steps-tracker-development.env` y sus adjuntos viven en
`/opt/steps-tracker-development/media`. La API y el receptor productivos no se
reemplazaron ni reiniciaron. El catálogo productivo volvió a su estado previo,
sin el vehículo personal de jornadas. El GPS físico sigue llegando a
`tracker_steps` por el receptor existente; mapa, configuración y recorridos
usan el puente Odoo y su tenant autorizado, no la base clásica nueva.

Esta preparación habilita la cuenta piloto existente. Un nuevo usuario requiere
aprovisionar su identidad en la base de Desarrollo; no se copian automáticamente
cuentas de otras empresas. No se promete con esta preparación el consumidor
automático de pasajeros hacia Odoo, builds de tiendas o funciones aún pendientes
en T46.

## Repetibilidad y conservación

`tools/ops/manage_personal_journey.py` prueba el plan explícito sobre copias
frescas de Tracker y Odoo, verifica apertura/cierre y guarda copias previas bajo
bloqueo compartido. `prepare_personal_journey_data.py` rechaza cambios de
inventario, uso real de un activo antiguo y un catálogo clásico concurrente.
`prepare_personal_journey_native.py` archiva por IDs y conserva los odómetros;
reutiliza los espejos y maestros existentes, sin Studio.

`isolate_personal_journey.py` prueba una base aislada antes de instalar la misma
estructura para Desarrollo. Restaura extensiones PostgreSQL como administrador,
usa el rol privado existente y no copia datos del dominio GPS. El cambio de la
API de Desarrollo se valida antes de confirmar el retiro de sus filas temporales
del catálogo compartido. Ante fallo restaura configuración y conserva respaldos.
`align_personal_driver.py` valida la relación nativa usuario/trabajador y rechaza
reconciliar silenciosamente un conductor con jornadas previas.

`prepare_personal_passenger_trial.py` solo permite Desarrollo o una copia privada.
La ruta carece de trazado porque no existe un recorrido real programado. El
usuario puede probar la nómina mediante búsqueda, código o los QR del HTML
privado generado por `create_passenger_trial_cards.py`.

Verificación: 187 pruebas móviles, TypeScript, apertura/cierre por API en copia,
flujo móvil de la app servida contra la copia, consulta real con la cuenta
existente, un vehículo en el formulario y un GPS en el mapa, ficha nativa y los
cuatro pasajeros autorizados. La revisión no inició jornadas reales. Cerro
conserva cuatro registros GPS, Desarrollo uno y el odómetro físico se conserva.
Las copias, servidores de revisión, tokens y sesiones temporales se retiraron.

Frontend certificado: `35c2b1fda8ad037af600577410e3cf2bda847595`, mismo código
móvil que el build anterior del ensayo (los commits siguientes corrigen y
documentan herramientas). Evidencia privada:
`/opt/steps-validation/personal-journey-20261102/`,
`/opt/steps-validation/personal-journey-isolation-20261102/` y
`~/.codex/local-artifacts/personal-journey-20261102/`.
