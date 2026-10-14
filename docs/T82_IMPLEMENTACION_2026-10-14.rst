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
Se pidió al usuario identificar las cuentas correctas; la selección queda
disponible en el formulario. No se modificaron esas relaciones sin identificar
su destino ni se costeó o contabilizó automáticamente ningún gasto del cliente.

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
El ticket queda en espera de identificar las relaciones analíticas pendientes;
las correcciones de código están publicadas y verificadas.
