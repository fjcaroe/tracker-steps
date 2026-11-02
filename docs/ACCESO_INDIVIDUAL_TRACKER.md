# Tracker por vehículo y control supervisado de arranque

La cuenta interna de Odoo es la identidad del usuario. El administrador asigna
vehículos nativos desde **Configuración de Tracker → Permisos por usuario →
Acceso Tracker**. Se reutilizan `fleet.vehicle`, `res.users` y el vínculo
explícito `step.tracker.asset.link`; no se resuelve una patente por coincidencia
de texto ni se crean maestros de vehículos o personas paralelos.

Los administradores mantienen la flota completa salvo restricción explícita.
Los otros perfiles de Tracker reciben únicamente los UUID de sus vehículos
asignados en la compañía seleccionada; una asignación vacía deniega todo.
El grupo **Tracker: operar vehículo asignado** permite atender incidentes y
armar/desarmar la vigilancia digital dentro de ese alcance. No da permisos de
administración de otras compañías, GPS/SIM ni de operación clásica/pasajeros.
Se conservan los permisos de otras aplicaciones que ya tenía la cuenta.

El puente firma el alcance por solicitud, sin entregar el JWT ni claves del
servidor al navegador. La API filtra listas, contadores, políticas e incidentes,
y rechaza IDs de posiciones, expedientes, órdenes y reportes de otro vehículo.
Las reglas nativas protegen Flota, vínculos e incidentes sincronizados; el
controlador de costos comprueba el mismo alcance antes de resolver el activo.
Las reglas de finanzas existentes continúan aplicándose sin `sudo` a importes.

## Experiencia del teléfono

Un usuario limitado entra en **Mi vehículo, Recorridos y Protección**. No ve
datasets, alta/sincronización de flota, inventario de otros GPS ni pasajeros.
El mapa muestra la última posición registrada y su antigüedad, sin inventar
velocidad cero ni convertir una posición de captura en recorrido. La protección
digital y el bloqueo físico del motor de arranque aparecen como funciones
separadas. El enlace con `?company=<id>` conserva la selección autorizada de Odoo.

La cuenta de prueba solicitada conserva el mismo alcance de Tracker, con los
controles físicos en simulación. La API también rechaza sus órdenes físicas,
aunque se manipule la pantalla. Su contraseña nueva se entrega en un archivo
privado fuera de Git. No se cambia la contraseña de la cuenta real ni se envían
invitaciones, correos o mensajes externos.

## Bloqueo físico del próximo arranque

Solo una instalación confirmada sobre el **circuito del motor de arranque**
puede habilitarse para la prueba supervisada. Esa confirmación se registra en
el inventario existente por la API de administración y no equivale a un ensayo
físico exitoso. Cambiar la asociación retira esa verificación.

La orden exige el permiso individual, alcance correcto, contraseña actual de
Odoo verificada en el servidor, patente escrita y presencia coordinada junto al
vehículo detenido con motor apagado. Para bloquear, API y receptor comprueban
GPS válido de menos de 60 segundos, velocidad de hasta 0,5 km/h y ACC apagado.
La restitución permite recuperar el arranque sin exigir una posición GPS nueva,
pero sigue requiriendo conexión TCP y autorización. No arranca el motor.

El protocolo envía exclusivamente las instrucciones GPS103 J/K descritas en
el [encoder oficial de Traccar](https://github.com/traccar/traccar/blob/master/src/main/java/org/traccar/protocol/Gps103ProtocolEncoder.java).
No hay comandos arbitrarios, `quickstop`, corte de un motor en marcha ni cola de
acciones para ejecutar al reconectar. El canal local usa un socket Unix y
`SO_PEERCRED`, restringido al UID del servicio API, sin abrir otro puerto de red.
Se comprueba nuevamente el dispositivo, emisor, compañía y modo de recepción.

La intención se conserva antes del envío y tiene plazo corto. La marca durable
del receptor precede a la escritura TCP. Repetir una intención, reiniciar un
proceso o perder la respuesta HTTP no la reenvía. Un resultado incierto requiere
revisión; no se repite automáticamente un bloqueo. Los estados de entrega son
independientes de la comprobación declarada por la persona en terreno. Una
escritura TCP nunca se presenta como una lectura eléctrica del relé.

## Publicación y comprobación

`manage_tracker_user_access.py` utiliza un checkout limpio, overlays privados,
copias frescas neutralizadas de Desarrollo, Cerro y QA-Cerro, y copia PostgreSQL
del GPS. Ensaya reglas, revocación, formulario, menú y verificación de contraseña.
Aplica dos veces la migración aditiva y compara las columnas originales para
comprobar conservación de datos. Las pruebas de API y del socket/TCP usan
fixtures aisladas; no envían órdenes a equipos reales.

Se publica el mismo paquete primero en Desarrollo y después en Cerro/QA-Cerro,
con respaldos, bloqueo compartido, comprobación de fuentes concurrentes y hashes
del frontend servido. Solo se cambian los archivos API declarados, conservando
el backend de otras aplicaciones. El receptor conserva su SQLite y configuración
con respaldo; no se alteran IP, puerto, SIM ni claves de los equipos. La copia
del cliente conserva capacitación y aislamiento y no recibe usuarios ni GPS
productivos. Comprobar la paridad de los dos addons afectados antes de entregar.

Las pruebas de teléfono usan la cuenta nueva y una sesión efímera de la cuenta
existente, sin cambiar su contraseña ni enviar comandos físicos. Las sesiones
de revisión se retiran al terminar.

Paquete preparado: `c7ce428f0f8369ed11b4226266bdd253366c7cc4`.
Recibos y respaldos privados: `/opt/steps-validation/tracker-user-access-20261102/`.
La certificación de software no afirma el resultado físico de la instalación;
este se registra durante la prueba de terreno con alimentación y señal reales.
