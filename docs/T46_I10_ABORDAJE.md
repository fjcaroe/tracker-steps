# I10 — Subidas, bajadas y ausentes

La siguiente iteración del ticket T46 usa los servicios, rutas, vehículos,
conductores y nóminas de I9. La respuesta del usuario confirma Tracker como
origen y Odoo como consumidor. La instrucción posterior de probar primero en
Desarrollo sustituye el antiguo permiso de publicar directamente en producción.
Esta entrega no publica interfaces ni sustituye la API de Cerro o Steps.

## Operación

En **Hoy / Mi servicio**, el conductor elige su servicio y pulsa **Preparar
servicio en este teléfono** con señal. Esa acción autoriza una copia local de
la nómina por 24 horas, separada por URL de API y cuenta. La preparación permite
registrar subida, bajada y ausencia sin red. Buscar por nombre o RUT/ID, filtrar
por estado o leer un código selecciona la ficha; la acción se confirma con el
botón correspondiente. Ausente puede corregirse mediante una subida posterior.
Una persona que ya descendió no vuelve a abordar dentro del mismo servicio.

Se cuentan las personas realmente a bordo frente a la capacidad histórica del
servicio. La capacidad planificada por parada no sustituye la ocupación real.
Un asiento no puede reutilizarse hasta registrar el descenso anterior. Ausente
requiere confirmación. No se inventan eventos por leer un QR o buscar un nombre.

El código es el UUID de la línea de nómina, solo o con prefijo
`steps:passenger:`; no es el RUT ni una URL arbitraria. El lector usa cámara
trasera, BarcodeDetector cuando existe y jsQR incluido en el paquete para QR
en otros navegadores. También admite código manual y lectores tipo teclado.
No necesita descargar un decodificador al perder señal. La cámara se libera al
cerrar, leer, fallar o vencer 30 segundos. Las fuentes de implementación son
[Chrome](https://developer.chrome.com/docs/capabilities/shape-detection) y
[jsQR](https://github.com/cozmo/jsQR). No se certifica cámara física o APK/IPA
por una prueba de navegador automatizada.

La ubicación es opcional y se solicita mediante una casilla explícita. Solo se
adjunta una lectura del teléfono de menos de 30 segundos con su precisión. Sin
permiso o lectura se guarda hora y ubicación desconocida. No se sustituye por
la coordenada del vehículo. No se requiere iniciar una jornada.

## Persistencia, permisos y conflictos

IndexedDB confirma la transacción antes de mostrar un registro guardado. Sus
transacciones serializan escrituras de varias pestañas. La cola incluye UUID
de servicio/pasajero/evento, acción, versión prevista, hora y coordenadas
opcionales; no nombres ni documentos. No se descarta al fallar la red o cerrar
sesión. El usuario se advierte si tiene pendientes antes de salir. La copia
personal se retira al salir, expirar o recibir 401/403/404. Los eventos conservan
su dueño y no se atribuyen a otra cuenta. Sin señal no se puede conocer una
revocación posterior: el permiso offline vence a las 24 horas.

La app debe estar autenticada y preparada antes de perder red. Mantenerla
abierta durante el viaje; el arranque completo sin red todavía está limitado
por la autenticación anterior del Tracker. Cambiar entre Hoy y Perfil conserva
la cola. Reconectar, volver a primer plano, consultar cada 30 segundos o pulsar
Sincronizar reintenta en orden. No borrar los datos del navegador con pendientes.

`GET /mobile/services/{uuid}/manifest` entrega estados, ocupación, versión y
recibos. `POST /mobile/services/{uuid}/events` recibe un evento inmutable con
UUID, pasajero, acción, versión prevista y hora UTC con zona. Solo admite al
conductor asignado o administrador con acceso vigente al centro del vehículo.
El servicio se bloquea durante la escritura; cada secuencia tiene restricción
única. Repetir UUID y contenido devuelve el recibo, sin duplicar. Otro contenido,
una ruta cancelada, capacidad/asiento ocupados o una versión antigua obtienen
409. La hora debe estar en los últimos siete días, con cinco minutos de margen
futuro. Datos inválidos o un pasajero ajeno no generan filas.

Dos dispositivos pueden requerir revisión explícita. **Revisar pendientes con el
servidor** presenta los nombres/acciones pendientes y la ocupación confirmada.
Tras confirmar, retira solo eventos cuyo recibo ya existe y valida los restantes
contra los estados/capacidad actuales antes de actualizar versiones. Una
contradicción conserva toda la cola y pide revisión del supervisor. No se
fuerza una versión ni se descartan silenciosamente eventos.

`mobile_passenger_events` es una bitácora dependiente de los servicios y líneas
existentes, no un maestro paralelo. Conserva actor, orden, hora registrada y
hora recibida. La migración solo añade esta tabla e índices. La respuesta I9
se conserva; el nuevo manifiesto amplía el contrato de sincronización a versión
2 e incluye eventos/estados en su hash. El consumidor automático Odoo sigue
pendiente y esta iteración no declara instalada esa sincronización.

## Publicación solo en Desarrollo

`tools/ops/deploy_mobile_boarding.py` implementa `qa`, `development`, `verify`.
Parte de checkout limpio de la rama canónica Steps Móvil, commit exacto y build
de `tools/ops/build_mobile_google.py <checkout> /tracker-dev-api`. No usa el
publicador histórico que reemplaza `/truck/` compartido ni la API productiva.

La API independiente `steps-tracker-dev-api`, en loopback 8012, atiende únicamente
el alias HTTPS de Desarrollo `/tracker-dev-api/`. Usa el mismo entorno privado,
JWT y base `tracker_steps`, sin crear otra copia de maestros o cambiar claves.
La separación es de **proceso y publicación de código**, no una base aislada:
los datos clásicos existentes siguen compartidos y los servicios conservan sus
permisos por conductor/centro. La tabla aditiva también está en esa base.
Todas las filas sintéticas de validación viven exclusivamente en copias privadas.
El receptor físico sigue usando la API productiva 8000 y no se reinicia.

Se prueba migración repetida y conservación de columnas/filas antiguas en una
copia fresca, servicio offline completo, reintentos y aislamiento. La publicación
adquiere `/run/lock/steps-environments.lock`, respalda base y alias, rechaza cambios
concurrentes y otro proceso en 8012, publica el mismo paquete y comprueba todos
los hashes servidos. Rechaza reemplazar una API Development anterior sin revisión.
Conserva los alias web, Cerro, Steps compartido y los procesos/API productivos.
El rollback restaura el alias y detiene la API nueva; conserva la tabla aditiva.
Una futura promoción a Cerro exige autorización y nueva certificación del destino.

Validación UI repetible: `tools/qa/tracker/serve_passenger_copy.py` y
`passenger-boarding.cjs`. La app servida en Desarrollo realiza las llamadas del
ensayo hacia una API de copia privada por túnel; nunca hacia producción. Se
comprueban cinco eventos de un viaje sin red, ausencia, ocupación, persistencia
al cambiar de sección, filtros, código, coincidencia final y cero geolocalización
sin permiso. Después se verifica el menú real con la cuenta existente, sin crear
servicios o pasajeros ficticios en el destino vivo. T46 permanece abierto.

## Entrega verificada — 02-11-2026

Publicado Tracker 1.6.1 solo en Desarrollo, paquete `2abb2e0678cad981ca15ba90d91ec2c37cbe8275`. Nota interna 9952, T46 en curso y sin notificaciones externas. 183 pruebas app en Windows/Linux, 83 API en Windows/Linux; migración repetida y originales conservados en copia fresca. Navegador sobre la app servida con API PostgreSQL privada: cinco eventos offline, confirmación única, filtros, código, cero geolocalización implícita y Perfil con cinco pendientes antes de reconectar. Cuenta real existente: Hoy, Perfil 1.6.1 y mapa de PKFX47, sin eventos de pasajeros. Cero servicios/eventos sintéticos vivos; las copias, tokens y sesiones temporales se retiraron.

API Development y receptor/productiva conservados por hash; Cerro mantiene cuatro GPS y Desarrollo uno. La API dedicada efectiva se conserva en su primera ruta inmutable porque el código posterior de la API es idéntico al paquete; la última publicación modifica solo el frontend. El publicador únicamente reutiliza una API existente con código y unidad exactamente iguales. Una actualización de ese código requiere revisión explícita del mecanismo de reemplazo y otra certificación; nunca se pisa por una publicación de UI.

Evidencia privada remota: `/opt/steps-validation/mobile-boarding-20261102/2abb2e0678cad981ca15ba90d91ec2c37cbe8275/`. Respaldo: `/opt/steps-validation/mobile-boarding-20261102/2abb2e0678cad981ca15ba90d91ec2c37cbe8275/backup-20261102T124221Z`. Evidencia local: `~/.codex/local-artifacts/t46-boarding-20261102/`. El primer intento restauró Desarrollo al recibir el índice anterior durante la recarga de nginx; el verificador espera ahora a los nuevos workers. También se corrigieron timestamps del harness y selectores de revisión antes de repetir el flujo completo. Ninguno de esos ensayos envió filas ficticias al sistema vivo.
