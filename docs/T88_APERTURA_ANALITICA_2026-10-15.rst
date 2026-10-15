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

Estado: pruebas y publicación pendientes.
