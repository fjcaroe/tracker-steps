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

El primer proveedor propio recuperó el estado de 23 DTE, los 25 archivos
tributarios vinculados, 22 timbres guardados y la referencia de una nota de
crédito sobre sus registros de origen. Tras la instalación y una actualización
se validaron los 86 asientos y sus 211 líneas, los permisos de siete contextos
y 17 aperturas de formulario. Las etiquetas coincidieron en español e inglés.
Seis campos del formulario original siguen pendientes. En la primera prueba
de impresión, los 21 documentos contabilizados fallaron para los dos usuarios
por faltar el campo que controla la visibilidad de la firma.

La revisión 18.0.1.0.1 conservó las cuatro columnas de auditoría de las
referencias y recuperó la configuración de firma y de resolución de la empresa.
Las dos empresas de la muestra tenían la firma desactivada. En la prueba de
168 configuraciones en memoria, el original falló en ocho casos al activar la
firma en facturas o notas de crédito contabilizadas; carecía del campo de
imagen de la firma. La revisión conservó disponible esa área para el caso
habilitado y permitió imprimirla en blanco. Los 160 casos que el original
pudo calcular coincidieron. La comparación fiscal de los documentos detectó
que la plantilla de origen necesitaba también la oficina regional del SII.

La revisión 18.0.1.0.2 restableció las 71 oficinas regionales originales y
la acción Documentos de la factura. Con siete contextos coincidieron el
indicador y el acceso a cada lista de documentos vinculados. Se abrieron los
21 comprobantes para dos operadores. Los textos completos coincidieron en
40 de 42 lecturas. La única factura diferente mostraba dos abonos en distinto
orden. En diez facturas con varios abonos el sistema nativo presentaba las
conciliaciones por su identificador original. La impresión en PDF reveló otra
diferencia: el gráfico del timbre ocupaba más espacio. La imagen generada con
escala 1 y margen 15 coincidió píxel a píxel con los 21 timbres nativos.

La revisión 18.0.1.0.3 recuperó el orden de las conciliaciones y el tamaño
del timbre. El texto completo de los 21 comprobantes coincide para ambos
operadores. Se imprimieron cuatro PDF con la acción original: dos facturas y
dos notas de crédito. Coinciden sus cuatro páginas, los 210 tramos de texto,
156 trazos y todos los píxeles en color a 96 y 144 ppp. El mismo control
contable conservó las 211 líneas y sus 86 asientos. Quedan cinco campos del
formulario original, vinculados con cesiones de crédito y préstamos, sin datos
en la muestra. El paquete probado tiene la huella
`8c7cf3cc764d92740db4549b395ddc27b126ab71596c9e2c7744a830f559cf2f`.

En el circuito de pagos, el menú de clientes mostró 34 cobros y el de
proveedores mostró 11 pagos al aplicar sus filtros iniciales. Las 42
conciliaciones parciales y 25 completas conservaron las mismas relaciones y
permisos en siete combinaciones de usuario y empresa. El programa propio
`step_payment_in_process` conserva el comportamiento del diario al registrar
un cobro manual desde la factura. Si el método carece de cuenta de cobros
pendientes, el cobro queda en proceso y la factura en pago. El operador puede
validar ese pago; la factura sigue en pago mientras no exista conciliación.
Con el método y la cuenta usados en los cobros históricos, el asiento quedó
publicado, la factura pagada y el cobro conciliado. Los dos ensayos se hicieron
en copias aisladas y se revirtieron. Coincidieron los importes, estados y
relaciones al repetirlos contra el original. La revisión de tres archivos tiene
la huella `5428545ab11150a070894e1286480597925c2150856c5ba0344499a2b0c97db2`.

También se ensayó el pago de una factura de proveedor pendiente. El operador
abrió la factura y usó el asistente de pago saliente. Con el diario sin cuenta
transitoria quedó en proceso y la factura en pago. Validarlo mantuvo la
factura pendiente de conciliación. Con el diario de los pagos históricos, el
asiento se publicó, las líneas por pagar se conciliaron y la factura quedó
pagada. Se repitieron las dos operaciones en el original y en la copia de
166 módulos. Coincidieron los estados, importes, cuentas y contrapartidas. Los
ensayos revirtieron los movimientos de prueba. El recibo de comparación tiene
la huella `bdbdee89b5498bd52334b2330f2a6bd1df8c9447c16c805ade9c2b42c3658c7d`.

## Respaldo integrado de 166 módulos

La copia de Steps reunió el cobro manual con ventas, Documentos, facturas
chilenas y Mesa de Ayuda. Se repitió la instalación de los dos módulos de
soporte sobre la copia contable y se cotejaron los 15.183 objetos SQL.
El vendedor pudo confirmar un pedido y abrir la factura en borrador. Los
dos operadores contables volvieron a abrir los 21 comprobantes. Coincidieron
los cuatro PDF fiscales y los cuatro de ventas en color a 96 y 144 ppp.
La primera ejecución de impresión fiscal falló en la comparación histórica.
La repetición verificó todas sus tablas de control antes y después de imprimir.
El cotejo independiente de las 1.115 tablas frente al respaldo previo a la
instalación identificó las mismas once tablas de configuración que ya habían
cambiado al instalar los módulos.

Se comprobaron los permisos de 98 documentos en 686 casos, 162 accesos a
enlaces históricos, los hilos de soporte internos y las dos descargas de la
cuenta de portal. Los cinco tickets conservaron el mismo orden en el listado
completo y en páginas de dos. El control conjunto de ventas, Documentos y
contabilidad conserva 22 recibos y tiene la huella
`c9bbfa39897f7a38735b6a6e383fbb4097e860a4b44c61becb5c04dcd623e63e`.

El respaldo reúne 163.602 filas, 807 contadores y 1.748 archivos. Se copiaron
y verificaron fuera del servidor sus ocho piezas y el índice. El índice
tiene la huella `183a72362efaa1fc6f9d44e946b9f7219efb0760a2b80caabb6cad611cf4c021`.
La copia requiere el respaldo anterior de 165, sus dos antecesores y el
suplemento de impresión documentado en [Mesa de Ayuda](COMMUNITY_STEPS_SOPORTE.md).
