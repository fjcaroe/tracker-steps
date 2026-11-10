# Receptor Coban para Cerro - 31/10/2026

## Auditoría pasiva de reconexión — 09-11-2026

`tools/gps/observe_coban_link.py` observa de 30 a 600 segundos de TCP5001 en el
host receptor, filtrando por el GPS actualmente asignado al UUID de activo
indicado. No abre ni reinicia enlaces, no envía órdenes y no guarda capturas
crudas. Informa latidos, acuses ON/LOAD y tiempos, conexiones observadas, cierres,
retransmisiones y atraso entre captura GPS y recepción del paquete. Ignora los
otros equipos y descarta sus datos. Las únicas opciones de estado que puede
extraer son modo e intervalos de reporte; nunca muestra clave, IMEI, teléfonos,
coordenadas, APN ni el mensaje status completo. En modo de ahorro (2) no interpreta
la agenda de despertar como un intervalo en segundos.

Usar con PYTHONPATH al paquete de receptor inspeccionado, ejecución privilegiada
y salida privada fuera del checkout. `test_observe_coban_link.py` verifica
privacidad, aislamiento de otro dispositivo y separación del relleno de red.
El reporte es una muestra pasiva; un silencio o ausencia de status no prueba que
el GPS esté apagado. Una sola conexión observada tampoco prueba ausencia de
reconexiones antes de comenzar la captura.

Para revisar la unidad física, identificar antes la SIM por el vínculo activo
al vehículo. La consulta SMS documentada por el manual 401 es `check<clave>`
(sin espacios). El operador usa su teléfono autorizado y devuelve únicamente
los estados; nunca se pide publicar la clave ni el campo UP. Verificar revisión
y respuesta antes de cambiar el modo online/sleep o heartbeat: los manuales de
401 tienen sintaxis y valores predeterminados distintos. El timeout TCP de 600 s
es tolerancia del servidor, no un temporizador de reconexión del módem.

La cola SQLite protege lo que el servidor ya recibió. Posiciones con hora de
captura anterior que entran después, espaciadas por segundos, prueban recepción
tardía/reenvío; no certifican memoria no volátil, capacidad ni cobertura completa
de un intervalo. Validar memoria offline requiere especificación de la revisión
exacta y una prueba controlada conservando alimentación y recepción satelital,
comparando las muestras antes/durante/después de perder solo la conectividad.
No aplicar comandos save/load de modelos 303 al 401 por similitud de marca.

### Verificación del ajuste por SMS

Una medición pasiva de seis minutos observó latidos separados por 180,243 s,
con acuses del servidor en aproximadamente 10 ms. Después de que el operador
aplicara `heartbeat<clave> 60` desde su teléfono autorizado y recibiera la
confirmación del equipo, otra medición de cuatro minutos observó cuatro
latidos: tres intervalos de 60,250 a 60,498 s (mediana 60,300 s). Los cuatro
acuses tardaron entre 9,722 y 11,209 ms; las cuatro posiciones de esa muestra
llegaron con 1,453 a 1,560 s de atraso. Las capturas crudas no se guardaron.

La revisión fue 401A-L-260306-V2.04, informada por el propio equipo en la
consulta SMS. El operador ya había recibido confirmación de `online<clave>`;
no se repitió esa orden. La muestra posterior no incluyó un mensaje status,
por lo que no constituye una lectura independiente del modo configurado.

El protocolo del fabricante citado abajo describe reconexión tras dos latidos
sin respuesta. Reducir el intervalo de 180 a 60 s permite esperar detección
más rápida de ese fallo (aproximadamente dos minutos en lugar de seis), pero
esta prueba no provocó una interrupción ni midió una reconexión real. Tampoco
elimina la falta de cobertura móvil o satelital.

La revisión de mensajes ya recibidos encontró posiciones antiguas reenviadas
con hasta unos doce minutos y medio de atraso antes de llegar al receptor.
En los grupos revisados no hubo reintentos del API y el procesamiento posterior
tardó menos de tres segundos. Esto acredita recuperación parcial de
muestras retrasadas; no demuestra almacenamiento persistente del equipo ni
recuperación completa de todos los recorridos. Los recibos y mediciones por
activo quedan en archivos privados fuera del repositorio público.

## Continuidad y diagnóstico — 02-11-2026

El límite de inactividad TCP pasa de 180 a 600 segundos. El protocolo reciente
del fabricante documenta un heartbeat de tres minutos: el límite anterior
carecía de margen para la latencia. Un contador separado identifica los cierres
por inactividad; no se atribuyen todos los cierres a una falla de cobertura.

La captura privada de la revisión confirmó además heartbeats de 16 bytes:
IMEI y `;`. El separador quedaba como un mensaje vacío y cerraba la conexión
después de contestar ON; una posición agrupada en la misma lectura también
podía quedar sin procesar. El framer omite esos separadores, incluso si llegan
en otra lectura TCP. Las pruebas verifican heartbeat, posición y otro heartbeat
en una única escritura, con persistencia y conexión conservadas. Esta falla
explica reconexiones observadas, sin demostrar cuánto movimiento hubo en un
intervalo histórico que no tiene posiciones recibidas.

La sincronización `status` de diciembre de 2023 se reconoce como contacto de
configuración sin coordenadas. No crea una posición, no renueva la fecha de la
última ubicación ni entra en capturas crudas (incluye credenciales del aparato).
Un mensaje `status` con formato de posición sigue pasando al decodificador GPS.
Referencia primaria del fabricante, secciones 2 y 5.13.1:
https://www.scribd.com/document/998077724/GpsTracker-Terminal-and-Monitoring-Center-Communication-Protocol-Alphabet-Edition-Edition-3rd-Version-20231227

`upgrade_coban_continuity.py` ensaya el mismo receptor con TCP y copia fresca
del API/base destino, conserva las posiciones previas y comprueba el control
de arranque en fixtures Linux. La publicación exige fuentes/configuración sin
cambios concurrentes, cola drenada y una ventana sin clientes TCP observados.
Usa bloqueo compartido, dump y copia consistente de SQLite, paquete inmutable
y retorno al enlace anterior ante fallo. No cambia API, Odoo, configuración
privada, permisos, IMEI, firmware ni puertos; los controles físicos conservan
sus propias comprobaciones de frescura. El reinicio breve se registra.

La cola durable del receptor ya guarda primero en SQLite WAL/FULL y reintenta
ante fallo de API. Esto protege mensajes recibidos por el servidor. Conservar
posiciones mientras el equipo está sin cobertura requiere memoria y reenvío
del propio hardware; el manual de la revisión 401 inspeccionada no documenta
una garantía de almacenamiento/recuperación de recorridos. No inferir esa
capacidad de otros modelos Coban ni reconstruir calles como datos observados.

Entrega verificada: receptor `1420b9faff9af9b4409f522473f6311799c728d8`.
El mismo paquete pasó 33 pruebas Linux y el flujo TCP/API en copia fresca del
destino antes de publicarse con respaldo y bloqueo. El receptor volvió a iniciar
el 03-11-2026 a las 01:07:32 UTC, en una ventana sin clientes TCP observados.
Se preservaron API, configuración privada, permisos e historial existente; no
se emitieron órdenes físicas. Recibos en `/opt/steps-validation/
coban-continuity-20261102/<commit>/`.

La observación pasiva posterior (01:08:34–01:12:04 UTC) comprobó la conexión del
equipo real en las 43 consultas, incluyendo su siguiente heartbeat y contactos
posteriores. El contador de heartbeats aumentó en dos sin nuevos rechazos ni
mensajes de configuración por reconexión. La evidencia privada de diagnóstico
incluye `heartbeat-after-framer-fix.json`. Esto verifica el defecto
corregido; no demuestra la causa completa de un intervalo histórico sin muestras.
Elevar solamente el timeout no había eliminado las reconexiones observadas.

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


## Auditoría solicitada de QA, web y móvil — 31/10/2026

El usuario recordó una versión más completa en Demo o Desarrollo. La auditoría de
fuentes efectivas, módulos instalados, menús, modelos/campos y archivos HTTPS
confirmó una omisión real en la entrega de configuración GPS: el paquete e4a1cb7b
partió del frontend canónico que todavía no incorporaba la unificación anterior
cc919212 ni el panel de costos. Conservó API y móvil, pero dejó fuera la pestaña
Operación, su acceso con sesión Odoo y los enlaces de costos por vehículo en
Desarrollo y Cerro. Demo conservaba esa web más completa. La revisión anterior
no detectó esa pérdida; se corrigió sin trasladar datos de Demo a producción.

Se recuperaron desde la rama móvil consolidada App, ClassicApp, AuthContext,
AssetCostsPanel, detalle de activo y navegación. FleetWorkspace combina de forma
explícita Operación/costos con la configuración y diagnóstico Coban; se conserva
su refresco cada cinco segundos, control de concurrencia y aprobación de recepción.
Los archivos frontend completos quedaron iguales entre las ramas canónicas Web
Tracker y Steps Móvil (integración móvil 7de79d02), para evitar nuevas pérdidas al
cambiar de rama. No se vuelve a desplegar una copia parcial de una de ellas.

Comparación comprobada antes de corregir:

| Parte | Desarrollo | Demo | Cerro productivo |
| --- | --- | --- | --- |
| Web unificada / Operación y costos | Omitida por e4a1cb7b | Presente | Omitida por e4a1cb7b |
| Configuración y diagnóstico Coban nuevos | Paquete con controles limitados a Cerro | Inventario anterior | Habilitada |
| App de terreno /truck/ | Tracker 1.3.0 | Mismo JS/CSS 1.3.0 | Mismo JS/CSS 1.3.0 |
| Módulos Tracker Odoo principales | Misma versión y código | Misma versión y código | Misma versión y código |
| Portal de app unificada /steps_app/v1 | Instalado, health 200 | No instalado, 404 | No instalado, 404 |

Los módulos step_tracker_portal (18.0.1.3.0, hash 78fd01449536...),
step_tracker_odoo (18.0.1.0.0, d8e088eecefa...) y step_hr (18.0.1.4.0,
fee46b0d8c20...) coinciden entre esos tres ambientes. Cerro y Desarrollo también
comparten step_tracker_usage, step_expense_tracker y step_management_costs_tracker.
No se encontraron modelos/campos Studio ni vistas Coban que hubieran quedado en
Demo sin pasar a Cerro. step.mobilization.gps.point corresponde al otro flujo de
movilización y está presente en los tres; no constituye un receptor Coban perdido.
La documentación de septiembre dejaba pendiente el receptor físico compatible;
la recepción GPS103 se implementó en la entrega reciente, no en un receptor de QA
que falte copiar. Esto no certifica una variante física sin su manual y sus tramas.

La app /truck/ de los tres usa index-BpVsqkbJ.js, SHA-256
d1a63335b27ded530f623c5e08f98dee21adf41e49f00300153b9044f5d549f5,
y la misma API compartida. Ofrece jornadas, cola offline, checklist, incidentes,
gastos, rutas y Supervisor, más Mi servicio de I9. No falta una versión de esa app
en Cerro. El servidor antiguo steps-truck-backend (9000/Redis) está en reinicio,
pero la app actual apunta a la API Tracker (8000); no se reutiliza ni se interviene
ese servicio legado como parte de esta corrección.

El portal adicional de Desarrollo (step_mobile_portal y sus módulos de catálogo)
aporta identidad, invitaciones, accesos y selección de módulos de la app unificada.
Es un piloto distinto del build tracker publicado en /truck/. No se promueve como
si fuera un parche Coban. Asimismo, el Supervisor móvil consulta sesiones/jornadas
y sus últimas posiciones; Coban alimenta gps_positions y la flota /v1 de la web.
La conexión del mapa móvil a esa flota independiente todavía requiere desarrollo.
No era una integración funcional de QA perdida en Cerro. Siguen pendientes también
las conexiones móviles de incidentes/gastos y servicios de pasajeros con sus
consumidores Odoo señaladas en el plan móvil; Android/iOS requieren validación física.

Corrección publicada: be359b822293a52adb72cb55ca9f4584e68009fe, mismo build en
Desarrollo y Cerro. JS de entrada index-DnpJrwX9.js, SHA-256
6409d9d4e42ee771eebb1e55a6e02490eda55a2682a242fe5b52e05fda0c7b4e.
Se verificaron todos los recursos, no solo el index. Prueba de navegador con
fixtures: alta GPS/SIM, asociación, captura/activación/deshabilitación, formulario
de costos, acceso con sesión a Operación, sus diez menús y regreso a Coban.
El mismo paquete pasó además en una copia fresca de tracker_steps: TCP Coban,
cola, reinicio, consulta de flota, aislamiento y sesión clásica con todos los
catálogos que consume Operación. Una sesión real del administrador existente de
Cerro abrió Registro de operación y regresó a Configuración GPS sin crear GPS,
vehículos ni jornadas ficticias. Se verificó el formulario nativo y el módulo
Odoo instalado; la sesión temporal de revisión se elimina al terminar.

El publicador tools/ops/deploy_tracker_frontend.py toma el bloqueo compartido,
conserva copias de configuración nginx y referencias a los directorios inmutables,
y compara la API efectiva antes de publicar. No migra bases, no reinicia la API
ni reemplaza el receptor. La auditoría antes/después confirmó idénticos hashes
para API, receptor, móvil, Demo y web histórica de Steps. QA-Cerro mantiene sus
módulos idénticos a Cerro y su aislamiento; sus rutas web_tracker/truck no se
publican hacia servicios de producción.

Evidencia privada: /opt/steps-validation/tracker-parity-20261031/
be359b822293a52adb72cb55ca9f4584e68009fe/ (qa.json, development.json,
production.json, private/functional.log y dump comprobado de la copia).
Respaldo de configuración Cerro: private/backup-cerro-20261101T020732Z.
Auditoría reproducible: tools/ops/audit_tracker_parity.py; guarda su salida fuera
del checkout. Evidencia local antes/después y capturas de navegador en
~/.codex/local-artifacts/tracker-qa-audit-20261031/.

Para comprobar conjuntamente la versión GPS y la web posterior, el verificador
admite dos checkouts: verify_gps_commissioning.py <fuente-receptor-e4a1cb7b>
<fuente-frontend-be359b82>. La separación es deliberada: restaurar el frontend
no instala de nuevo un receptor ni cambia su caché, claves o datos.
