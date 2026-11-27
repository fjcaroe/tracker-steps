# Histórico contable de Steps

La referencia de Steps contiene 86 asientos, 84 contabilizados y dos anulados,
con 211 apuntes. Incluye veinte facturas de cliente contabilizadas, una nota
de crédito de cliente contabilizada y una factura de cliente anulada.

El ensayo recorrió siete combinaciones de usuario y empresa en las copias
nativa, de ventas y Documentos, y de ventas con Mesa de Ayuda. Coincidieron
las filas accesibles, los importes, los impuestos, las conciliaciones y las
relaciones contables que exponían ambos sistemas. Un operador interno tenía
86 asientos y 211 apuntes disponibles. El vendedor tenía 22 y 66. La cuenta
de portal tenía siete y 21. La compañía sin movimientos devolvió cero y
el visitante mantuvo denegada la consulta.

Se abrieron 17 formularios de asientos, facturas y notas de crédito con sus
acciones de menú. En las dos copias Community faltaban el tipo de documento
tributario, su número y el estado del DTE. Los valores seguían en el origen
y los enlaces fiscales originales tenían 27 tipos de documento informados,
23 estados, 25 archivos DTE y 22 timbres. También había una referencia
entre documentos.

En U45F se restauró el respaldo de ventas y Documentos U44R. Se reactivaron
los 25 archivos LGPL de la versión original del módulo de documentos
latinoamericanos y los 51 de la localización chilena, con las dependencias
instaladas en Steps. Se recuperaron el tipo y el número con sus valores
originales para los mismos usuarios en los 17 formularios. El arranque
conservó las 1.114 tablas ajenas al registro de módulos y las definiciones
y contadores SQL del respaldo.

Las comparaciones se reproducen con `probe_steps_accounting_history.py`
y `verify_steps_accounting_history.py`. Los recibos privados U45C y U45F0
contienen las huellas por campo de cada contexto.
