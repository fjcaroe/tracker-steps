T82 — correcciones de provisión de gastos de embarque
===================================================

Alcance
-------

Se revisó el comentario humano y el documento adjunto del T82. Los destinos
solicitados son Desarrollo y Cerro El Plomo. La rama de producto es
``codex/ambientes-canonicos-reparacion``; el trabajo se hizo en un worktree propio.

Cambios
-------

* CLP y USD muestran el importe convertido antes de costear, usando las tasas
  nativas de la fecha y empresa. Las columnas permiten ingresar en cualquiera
  de esas monedas; la edición cambia la moneda e importe de origen y recalcula
  la otra columna y los totales. Se avisa expresamente si falta una tasa.
* Los importes aplicados al costear permanecen congelados: una tasa posterior
  no modifica los gastos costeados ni los contabilizados.
* Volver al estado anterior permite Validado → Creado y Costeado → Validado.
  Descarta únicamente el costeo pendiente y sus cuentas aplicadas; conserva
  gastos, importes de origen, identidad del documento y auditoría de estados.
  Una provisión contabilizada conserva su asiento y requiere el procedimiento
  contable de reversión; este botón no revierte ni elimina asientos.
* Cuentas analíticas muestra y permite seleccionar las relaciones existentes
  de temporada, especie y embarque. El valor elegido se guarda en el maestro
  original. No se crean maestros paralelos ni se infieren relaciones por nombre.
  El error identifica cuál de esas relaciones falta. Se mantienen los controles
  de empresa, cuenta activa y tres planes raíz distintos al costear.

Configuración existente
----------------------

En Desarrollo las cuentas de temporada y especie estaban vinculadas, pero
faltaba la cuenta del embarque. En Cerro faltaba la cuenta de temporada. La
existencia de una cuenta analítica no establece por sí sola esas relaciones.
El usuario confirmó la identidad de ambas cuentas. Se comprobaron primero las
relaciones en copias privadas, usando cuentas, gastos y tasas del destino.
En Desarrollo la relación ya estaba elegida al aplicar la comprobación; se
preservó la provisión que el usuario ya había contabilizado. En Cerro se
vinculó la cuenta confirmada al maestro original de temporada.

La provisión de Cerro usaba Miscellaneous Operations sin contracuenta, aunque
existía el diario específico Provisión gastos exportación con su cuenta de
pasivo configurada. Se corrigió únicamente la selección de diario usando
Volver al estado anterior, edición y Validar. Conserva identidad, gastos,
importes de origen y estado Validado. El retorno nativo normaliza a cero los
campos vacíos de valoración pendiente y actualiza la auditoría de escritura.
No se alteró el diario genérico ni se crearon cuentas, diarios o asientos.

Las provisiones validadas restantes pasaron el costeo en cada destino real.
Esos costeos de comprobación se revirtieron; no quedaron contabilizaciones
automáticas ni cambios en gastos o estados por las pruebas. Las herramientas
versionadas rechazan relaciones ya elegidas distintas de la solicitada,
empresas incorrectas y modificaciones inesperadas de documentos.

Paquete y verificación
---------------------

``step_export_shipment_provision``: ``18.0.1.0.2``.
Commit del paquete: ``9073b58148e8e6909580dd5f8965c5bab48e6900``.
SHA-256: ``929ad808ff38cdafbf99a2b3a3312d191e0e8839ee28789fda85d0a519e2d283``.

La primera ejecución detectó que el campo USD conservaba un valor de caché
después de ingresar CLP. Se corrigió invalidando las previsualizaciones al
terminar la inversa. Ese paquete fallido no se publicó; se generó el paquete
indicado y copias nuevas para repetir la validación.

Las pruebas cubren ingreso CLP/USD, previsualización independiente de las
relaciones analíticas, falta de tasa, regreso desde Validado y Costeado,
corrección y nuevo costeo, protección de importes y permisos, formulario Nuevo,
contabilización balanceada, tres planes analíticos y prevención de duplicados.
La verificación de destino ejecuta el flujo con un usuario de operación y
contabilidad y descarta las muestras.

La publicación exige comparación de los datos anteriores, paquete idéntico
al probado, ausencia de downgrade, respaldo, overlay privado y bloqueo
``/run/lock/steps-environments.lock``. Las evidencias, adjuntos y respaldos se
guardan fuera del repositorio; este documento no contiene credenciales.

Desarrollo: diez pruebas aprobadas y flujo de destino verificado; respaldo en
``/opt/steps_backups/management_development_20261014T174620Z``. La lectura de
las provisiones anteriores comprobó importes CLP/USD calculados, sin cambiar
sus estados, gastos ni relaciones pendientes.

Cerro El Plomo: diez pruebas aprobadas y flujo de destino verificado; respaldo
en ``/opt/steps_backups/management_cerro_20261014T175235Z``. Ambos destinos
sirven la versión indicada desde su overlay propio y mantienen el servicio HTTPS.
La confirmación del usuario completa las relaciones pendientes. El cierre del
ticket exige además las pruebas de configuración aplicada en ambos destinos.
Respaldos previos a la configuración:

* Desarrollo: ``/opt/steps_backups/provision_analytics_development_20261014T194515Z``.
* Cerro: ``/opt/steps_backups/provision_analytics_cerro_20261014T194712Z``.
