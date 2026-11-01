# Receptor Coban para Cerro - 31/10/2026

Solicitud explícita del usuario: preparar y habilitar hoy el receptor para
Cerro El Plomo productivo; los cuatro IMEI, números SIM y manual llegarán aparte.

La primera entrega aisló receivers/coban sin modificar API ni frontend.
La ampliación de configuración descrita abajo integra ambos y conserva Teltonika
y los addons Odoo. Destino reservado: IP estática de odoo-new,
35.222.25.110, TCP 5001. No usar UDP ni 5027 para este receptor.
La apertura externa solo queda confirmada tras publicar y probar firewall.

## Alcance de protocolo

GPS103 ASCII con login `##,imei:...,A` / LOAD, heartbeat IMEI / ON,
posición F válida terminada en punto y coma, y variante decimal ALT terminada
en asterisco. Parser independiente contrastado con el proyecto Traccar:
https://github.com/traccar/traccar/blob/master/src/main/java/org/traccar/protocol/Gps103ProtocolDecoder.java

Las coordenadas F se convierten de grados/minutos y sus velocidades de nudos
a km/h; ALT utiliza grados decimales y km/h. Solo datos GPS válidos; LBS y
posiciones inválidas no fabrican puntos. El reloj del dispositivo debe usar UTC.
Una fecha futura o inválida queda rechazada, con captura privada solo para IMEI
permitidos. Un indicador de carga de batería no se convierte en corte de energía.

No se afirma compatibilidad física con una revisión 401C hasta recibir su manual
y una trama real. No se implementan variantes binarias, GT06, fotos, comandos
de configuración ni control de motor. La única respuesta de alarma es el acuse
de recibo SOS del protocolo, después de persistir el evento.

## Registro privado y encaminamiento

La autoridad vigente es el inventario GPS existente de Tracker, gestionado desde
Cerro / Steps Tracker / GPS y SIM. El receptor sincroniza cada cinco segundos
las compañías de Cerro mediante POST /v1/receiver/poll, con identidad ingestor
firmada de esa compañía. El navegador no puede usar esa ruta.

/var/lib/steps-coban/devices.json es una caché privada 0600, actualizada
atómicamente por el receptor. No editarla para dar de alta equipos. El archivo
anterior /etc/steps-coban/devices.json se conserva como referencia de la primera
entrega; ya no controla la recepción. El inventario permanece vacío hasta recibir
los IMEI reales.
Cada entrada tiene issuer CERRO_EL_PLOMO, company_id, mode y, para forward,
device_id UUID del inventario existente. Mode capture conserva hasta 200 tramas
privadas para validar la unidad sin crear posiciones en la aplicación. Mode
forward requiere además alta y asociación del vehículo en Tracker.

No incluir IMEI, teléfonos, tramas reales ni contraseñas en Git, pruebas públicas
o logs. El protocolo identifica por IMEI, sin autenticación criptográfica del
aparato; la lista restringe la recepción pero no convierte el protocolo en TLS.
La clave de puente de Cerro vive en archivo privado root:steps-coban 0640;
no se imprime ni se modifica la clave compartida original.

SQLite WAL/FULL conserva la cola antes del reenvío. SHA-256 del mensaje identifica
duplicados; recibos de la API completan la entrega, con reintentos y backoff.
La ruta de cada evento queda congelada; cambiar el mapa no mueve eventos a otra
compañía. La API existente valida nuevamente tenant y asignación para la fecha.
Retención de recibos hasta siete días / máximo 20.000, cola pendiente máxima 20.000, capturas 200,
tramas 4 KiB, buffers 16 KiB, 64 conexiones globales y 8 por IP, 120 mensajes/min
por conexión. Capturas/estado son privados y no se registran payloads en journal.

## Primera publicación de infraestructura (histórica)

tools/ops/deploy_coban.py valida SHA-256 y commit del paquete, toma el bloqueo
/run/lock/steps-environments.lock y ensaya el mismo código en el entorno privado
de validación: copia fresca del destino tracker_steps, dump decodificado, tests
unitarios y flujo TCP real hacia la API actual sobre esa copia. Se comprueban
consulta de flota, reinicio durable, deduplicación y rechazo entre compañías.
Se comparan datos GPS reales y fuentes de API antes/después; no se cambian.

La publicación instala un servicio no privilegiado steps-coban, código bajo
/opt/steps-coban/releases/<commit>, enlace current, configuración y datos privados.
No sobrescribe raíces existentes. Crea únicamente una regla GCP TCP 5001 con
tag steps-coban-cerro para esa VM. Conserva el resto de tags y reglas. El respaldo
de configuración previa queda en /opt/steps-validation/coban-receiver-20261031/.
No hay migración ni reinicio de Odoo, API, nginx o Teltonika.

## Al recibir los cuatro equipos

1. Seleccionar la sociedad correcta en Odoo y abrir Steps Tracker / GPS y SIM.
2. Agregar el IMEI de la etiqueta, SIM Entel y fechas/responsable de conectividad.
3. Asociar el vehículo real y pulsar Probar recepción, indicando el motivo.
4. Cotejar manual y configurar físicamente servidor TCP, APN y SMS de administración.
5. Revisar contacto, ubicación y hora recientes. Activar seguimiento requiere
   una posición recibida después de la asociación y durante los últimos cinco
   minutos, receptor disponible y confirmación explícita de revisión física.
6. Comprobar posiciones nuevas en Cerro, reconexión tras corte normal y SMS de
   administración. No aprobar seguimiento ni despachar como listo antes de ello.

El mapa se relee por mensaje, sin reiniciar el receptor. Ninguna entrada o
vehículo ficticio se crea en producción para probar este servicio.

## Primera publicación verificada (histórica)

Paquete del commit 115d80e719837d11faa20a64028f60e55ec8c0f1, SHA-256
f44a056f4fc1aecb45d559854d057a36f52fd54e0c8b0c8b716e57280eddf71c.
22 tests aprobados en Windows y Linux, más flujo TCP -> cola reiniciada -> API
actual sobre copia PostgreSQL -> consulta de flota. Una entrega cruzada a otra
compañía recibió 403. Las huellas de datos GPS y fuentes de API de producción
permanecieron intactas. El primer ensayo se detuvo al intentar cargar .env de
producción: se aisló una copia exacta del código API sin copiar secretos y se
repitió con otra copia fresca. No se cambiaron permisos ni credenciales existentes.

Servicio steps-coban activo y habilitado al arranque. Regla GCP dedicada
steps-coban-cerro-tcp5001, únicamente TCP 5001 y tag de esa VM. IP reservada
ip-odoo-static, 35.222.25.110. Prueba desde un equipo externo: conexión TCP
correcta y cierre al presentar un identificador no permitido. Reinicio del
servicio probado, con contadores persistidos. Teltonika, API y Odoo Cerro activos.

Respaldo /opt/steps-validation/coban-receiver-20261031/backup-20261101T003929Z
(nombre UTC; publicación el 31/10 en America/Santiago). Evidencia privada
en el mismo directorio de validación y ~/.codex/local-artifacts/coban-receiver-20261031/.
Se actualizó el instructivo imprimible con destino TCP confirmado.

Estado de entrega: infraestructura habilitada, inventario permitido vacío a la
espera de los cuatro IMEI y datos de SIM. No se declara aprobada ninguna unidad
física ni se registra un vehículo ficticio. A continuación corresponde configurar
capture, cotejar manual/trama y asociar los GPS a sus vehículos antes de forward.


## Configuración desde Tracker publicada el 31/10/2026

Paquete instalado e4a1cb7bcff552e874ba20b016be8be5cebfe548, desde la rama
canónica Web Tracker. API y receptor se verifican por hash de cada archivo Python;
index y todos los recursos HTTPS coinciden con el build revisado en Desarrollo.
Las ramas canónicas Web Tracker y Steps Móvil conservan el mismo backend completo:
la integración móvil 7d017a8f incluye esta ampliación sin retirar servicios de
pasajeros, sesiones, operaciones offline ni los controles de acceso ya instalados.

La ficha existente gps_device_registrations conserva los maestros y añade modo
(disabled/capture/forward), diagnóstico y comienzo de la prueba. No se crean
maestros paralelos. El alta inicia deshabilitada. Una prueba nueva descarta la
aprobación previa; cambiar de vehículo retira la aprobación y exige una posición
posterior a la nueva asociación. Las escrituras usan versión y bloqueo, con motivo
en auditoría. Un heartbeat no modifica la versión del formulario abierto.
Deshabilitar bloquea también la ingesta en la API aunque el receptor todavía tenga
una caché anterior. Una caída de API conserva la caché y la cola, sin mover eventos
entre compañías o dispositivos. No se aprueba ni controla el corte de motor.

Publicador: tools/ops/deploy_gps_commissioning.py, acciones qa, development y
production. Exige checkout fresco, baseline instalado conocido, Git limpio, build
con configuración privada del servidor, copia fresca de tracker_steps y el mismo
paquete. Aplica la migración aditiva dos veces y compara las huellas de todas las
columnas preexistentes de todas las tablas. El ensayo usa API real en la copia,
configuración por API, captura, diagnóstico, aprobación, socket TCP, cola durable,
deduplicación, consulta de flota y rechazo de otra compañía. 23 pruebas Linux del
receptor, 72 de API en Windows y prueba de navegador de registro/SIM/asociación/
activación/deshabilitación en 390 y 1440 px. La prueba publicada de Desarrollo usa
fixtures interceptadas, sin crear maestros de demostración en el ambiente real.

La publicación toma /run/lock/steps-environments.lock, conserva dump decodificable,
código API, configuración, enlace y SQLite del receptor. Rechaza cambios ajenos.
Los frontends de Desarrollo y Cerro usan snippets y directorios privados bajo
/var/www/steps-tracker-releases/<commit>. Se conserva el portal compartido legado,
Demo y el frontend móvil /truck. No se modifica ningún addon Odoo ni las bases
Odoo; QA-Cerro conserva sus datos y aislamiento y no se conecta al receptor de
producción. Las comprobaciones nativas validaron el menú GPS y SIM, su acción settings y
el módulo step_tracker_portal instalado 18.0.1.3.0 en Desarrollo y Cerro. Se abrió
el formulario real con un usuario administrador existente y la sociedad Cerro
correcta, en computador y móvil, sin guardar dispositivos ficticios. La API
rechazó un alta inválida y la ruta privada del receptor permanece bloqueada para
el proxy del navegador. Las sesiones temporales de revisión se retiran al terminar.

La primera promoción se revirtió por una condición incorrecta que buscaba la
palabra passenger en las rutas OpenAPI: la ruta real es /mobile/services.
Se corrigió y se repitieron ensayo en copia fresca y revisión de Desarrollo con
el paquete final. No se revirtió la base sobre datos nuevos; la migración aditiva
preservó todos los registros. El intento final verificó servicios, heartbeat de
las compañías Cerro, paquete instalado y recursos servidos antes de entregar.

Evidencia privada: /opt/steps-validation/gps-commissioning-20261031/
e4a1cb7bcff552e874ba20b016be8be5cebfe548/ (qa.json, development.json,
production.json, private/flow.log y private/receiver-unit.log).
Respaldo final: private/backup-production-20261101T005849Z.
Verificador de solo lectura: tools/ops/verify_gps_commissioning.py <checkout-del-paquete>.
Devuelve únicamente estados agregados y hashes, nunca IMEI, teléfonos o claves.

Estado al publicar: receptor disponible, cero identidades habilitadas. Pendientes
los cuatro IMEI, números SIM, asociación a vehículos y fotos del manual para
comprobar variante física, comandos SMS y prueba real de cada equipo antes de
entregarlo para instalación. La preparación de la aplicación no certifica aparatos
que aún no han transmitido.
