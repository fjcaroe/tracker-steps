# I11 — Avance del transporte y cierre del manifiesto

En **Hoy → Mi servicio → Paradas y avance del servicio**, el conductor asignado
registra la llegada y después la salida de cada parada en orden. Puede anotar
un desvío o una novedad con cada registro. La estimación de las paradas
pendientes ajusta el horario programado según el último registro. La fecha
efectiva la guarda el servidor. Los nuevos registros requieren conexión y los
abordajes ya preparados conservan su sincronización sin señal.

En **Supervisor → Avance de servicios de pasajeros**, el perfil administrador
consulta desde la web la ruta, las horas y los retrasos. La vista activa
actualiza su consulta cada diez segundos y omite la nómina de pasajeros.

Después de la última parada, el conductor sincroniza la nómina, registra
las ausencias y los descensos pendientes y firma con su nombre. El cierre
guarda el usuario autenticado, el texto de firma, la fecha, un resumen de
novedades y el hash de la nómina confirmada. El sistema serializa el cierre
junto a los registros de pasajeros para impedir cambios posteriores.

El paquete utiliza exclusivamente `tracker_steps_development`. El publicador
`tools/ops/deploy_mobile_progress.py` incorpora los cambios de pasajeros
sobre la API vigente de Desarrollo, con el mismo código de Analítica y la
misma configuración de servicio, y certifica el resultado en una copia.
La publicación mantiene intactos Cerro, la API compartida y el receptor GPS.
