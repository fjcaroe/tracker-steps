T88 Apertura contable y distribución analítica
============================================

Requerimiento ID 88 y respuestas humanas 9462/9463, con capturas 3353/3354.
Cerro El Plomo informa bloqueo de sus dos aperturas por distribución al 100 %.
La inspección de solo lectura encontró que la de resultados pasa la validación;
en la de activo-pasivo fallan quince líneas debido a planes obligatorios sin
reglas de aplicabilidad que distingan las cuentas de balance.

Se extiende el cálculo nativo de aplicabilidad de planes: cuando el tipo de
cuenta pertenece a activo, pasivo o patrimonio y el plan resultaría obligatorio,
se presenta como opcional. Se conservan planes no disponibles, requerimientos
explícitos de la API y las reglas de ingresos/gastos. No se deduce el tipo por
prefijos del código ni se modifican planes, distribuciones, importes o maestros.
No se crean modelos ni objetos Studio. El módulo se publica solamente en
Desarrollo y Cerro; no se altera el alcance instalado de otros destinos.

La prueba integral detectó además que bimoneda genera una línea de diferencia
de cambio sin distribución, aunque las líneas de resultados originales estén
completas. El ajuste generado hereda la distribución existente solo si todas
las distribuciones no vacías del asiento coinciden. No se elige una entre
distintas ni se modifica una distribución ya ingresada; se conserva la
validación nativa del 100 % también en esa línea de resultados.

Pruebas
-------

Tipos nativos de activo, pasivo y patrimonio; contabilización de un asiento
sintético sin analítica; obligación de resultados y rechazo de distribución
vacía o al 50 %; aceptación al 100 %; reglas opcionales/no disponibles y contexto
por empresa. En la copia privada de Cerro se prueba contabilizar las dos
aperturas reales y se revierte la transacción. En producción solo se valida
la analítica: los comprobantes del cliente permanecen en borrador.

Entrega verificada
------------------

Paquete inmutable del commit ``903001bd9e211cdfdf02a0cc707c942abb80560e``,
SHA256 ``66e15b9359f62cddb63b08ce2df1d0d89a83b10222126d4a6ee8e8f96cd9f845``,
módulo ``step_account_balance_analytic`` versión ``18.0.1.0.0``.
Las cuatro pruebas pasaron sin fallos en las copias nuevas
``MANAGEMENT_QA_DEVELOPMENT_t88_g_dev`` y ``MANAGEMENT_QA_CERRO_t88_g_cerro``.
Incluyen conservación de la clasificación nativa, empresa, reglas, rechazo
del 50 %, herencia única del ajuste bimoneda y rechazo de la ambigüedad.

La certificación de Cerro contabilizó las aperturas 13 y 9 y revirtió toda
la transacción. El primer chequeo posterior a las pruebas encontró caché
de planes de prueba revertidos; se corrigió el aislamiento del verificador
y se repitió la certificación contra el mismo paquete y copia preservada.
No se publicó ninguno de los paquetes preliminares.

Se publicó ese mismo paquete en Desarrollo y Cerro, usando exclusión
compartida, overlays privados y respaldos completos:

* ``/opt/steps_backups/management_development_20261015T230927Z``.
* ``/opt/steps_backups/management_cerro_20261015T231111Z``.

Ambos destinos devolvieron ``MANAGEMENT_VERIFY_OK`` con el commit indicado,
versión, formulario, menú y pruebas funcionales. Se revisaron visualmente
los formularios de contabilidad en ambos destinos y el selector analítico
de una cuenta de activo en Cerro, descartando su edición temporal.

La inspección final de solo lectura comparó las 22 líneas de resultados y
17 de activo-pasivo con la inspección inicial: mismos IDs, cuentas, saldos
y distribuciones, ambos documentos en borrador. El bloqueo de activo-pasivo
pasó de quince líneas a cero. No se contabilizaron documentos del cliente
en producción. Evidencias privadas y hashes en
``~/.codex/local-artifacts/t88-opening-20261015/visual-review.json``.

T88 cerrado en etapa resuelta con nota interna 9464, sin notificaciones.
