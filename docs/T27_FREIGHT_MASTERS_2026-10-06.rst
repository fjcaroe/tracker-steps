T27: Tramos y Modalidad de frío
==============================

Se incorporaron las dos respuestas recientes del cliente y el documento
funcional respondido. Ambos errores eran reproducibles al abrir el historial
de los maestros: los modelos no implementaban ``mail.thread`` y las acciones
resolvían formularios Studio. El registro se guardaba, pero su pantalla fallaba
al solicitar ``_get_thread_with_access``. No era necesario crear otra tabla.

El paquete ``step_operations_ui 18.0.2.5.0`` conserva tablas, IDs y relaciones.
Implementa los dos maestros y sus campos anteriores en Python, añade historial
y actividades, usa ``x_name`` como nombre visible, y vincula listas, formularios
y búsquedas XML propios. Archiva únicamente las vistas Studio de estos dos
modelos. Los enlaces de las acciones anteriores siguen abriendo los maestros
migrados; no se cambian sus IDs.

Origen/destino y empresa se consolidan con las columnas anteriores. Los nombres
anteriores quedan como alias editables para mantener importaciones y relaciones.
La migración rechaza valores poblados diferentes antes de modificar datos;
no adivina empresas ni coincidencias por nombre. Fundo sigue siendo una relación
a ``step.fundo``. Código de frío, kilómetros y secuencia conservan sus columnas.
Los nombres técnicos ``x_studio_*`` no implican que el campo siga siendo manual:
se mantienen deliberadamente para preservar compatibilidad.

Base de entrega
---------------

La fuente canónica tenía una versión antigua del módulo. Se reconciliaron sus
archivos con el commit ``41ff3dc``: todos coincidían con el código efectivo de
Desarrollo 18.0.2.4.0. Se incorporó únicamente ese módulo, conservando las mejoras
de tarifas, costeo, contabilización y reportes de esa entrega.

La rama de trabajo es ``codex/t27-tramos-frio-20261006`` y se integra en
``codex/ambientes-canonicos-reparacion``. El paquete definitivo se construye
desde ``a3eea0133e9be5db6ad71c1d4e5c013ca4641381``; su SHA-256 es
``7ecb3abb09df56e81980709e9b1acdda025b2d4cb09613917b7a2fa12f7a7f5a``.

Validación y publicación
-----------------------

``tools/ops/build_management_release.py --kind freight`` empaqueta solo este
módulo desde blobs Git. ``manage_freight.py`` restaura una copia nueva de
Desarrollo con filestore privado, correo y cron desactivados, puerto local y
filtro de base exacto. Requiere pruebas satisfactorias del mismo paquete,
ausencia de cambios concurrentes, versiones y huellas de fuentes compartidas,
configuración y metadatos Studio sin cambios.

Los controles comparan todas las columnas originales de tablas de Fletes,
modalidades, asientos y líneas contables, además de mensajes, seguidores,
actividades y adjuntos de los documentos afectados. Únicamente se normalizan
los alias explícitos de Tramos; las ambigüedades bloquean la migración.

Las pruebas funcionales incluyen creación/edición con usuario interno,
historial, nombre visible, modalidad en tarifas, menús y vistas efectivas,
planificación, cálculos y contabilización. El primer ensayo detectó un correo
faltante del usuario de prueba; se corrigió la configuración de ese usuario
sin relajar la validación y se volvió a una copia nueva.

El publicador admite exclusivamente Desarrollo, exige el bloqueo compartido
``/run/lock/steps-environments.lock``, respalda base/configuración y usa un
overlay privado. Nunca reemplaza raíces compartidas. ``verify_freight.py``
comprueba versión, origen, menús, vistas y un flujo con rollback, sin conservar
registros de prueba. Los dumps, logs y capturas permanecen fuera de Git.

El paquete definitivo pasó 32 pruebas sin fallos ni errores en la copia nueva
``FREIGHT_QA_t27_1006c`` y se publicó en Desarrollo / ``LAB_TAREAS``. Se comprobaron
versión 18.0.2.5.0, ruta efectiva del overlay, menús, formularios, creación e
historial con usuario interno y rollback. La conservación de columnas, filas,
relaciones, importes e historial pasó tanto en la copia como en el destino.
El respaldo es ``/opt/steps_backups/freight_development_20261006T132558Z`` y la
evidencia del ensayo/publicación está en
``/opt/steps-validation/freight_development_t27_1006c``.

En el navegador se reprodujo primero el error del tramo del cliente y después
se abrió el mismo registro correctamente con origen, destino, kilómetros,
fundo y botones de historial operativos. Se abrió también la modalidad Mixto,
con su código conservado e historial operativo, sin modal de error. Los dos
modelos tienen metadatos ``base``, ningún campo manual y ninguna vista Studio
activa. Las capturas y ``evidence-final.tar.gz`` quedan en el directorio privado
``~/.codex/local-artifacts/ambientes-canonicos/t27-current/``.

El error previo conocido de carga de ``steps_api`` permanece fuera del alcance;
el publicador permite únicamente esa línea y rechaza cualquier otro error.

Alcance pendiente
----------------

Esta entrega responde a los dos fallos nuevos de T27. No declara terminada
la retirada completa de Studio: todavía deben revisarse Contabilizaciones,
automatización de folios, informe anterior y los otros bloques del inventario.
El ticket permanece abierto hasta la revisión funcional del cliente en
Desarrollo; no se publica este paquete en producción durante esta entrega.
La respuesta breve de revisión quedó publicada y comprobada como mensaje
9176 en T27, sin cambiar su etapa. Solicita recargar Odoo y crear ambos maestros
desde Fletes / Configuración, respondiendo OK o indicando cuál falla.
