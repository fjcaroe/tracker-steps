# Efecto del botón original de netos negativos de SyS

La revisión .6.3 incorpora la aplicación de la deducción y documenta la segunda ruta del operador, que genera una actividad al abrir la liquidación en verificación. [Resultados y recuperación de la operación en Community](COMMUNITY_SYS_ARRASTRE_NETOS.md)

El botón **Reporte** conlleva una operación de nómina. Los dos operadores originales lo encontraron oculto en los tres recibos cerrados que tenían la marca de neto pendiente. Al crear un borrador para el mes siguiente de cada caso, el botón apareció con un importe distinto de cero.

Se ejecutó el método nativo seis veces en la copia completa U40RP, con un borrador nuevo por operador y caso. La copia conserva los 336 módulos nativos y su respaldo SQL tiene SHA-256 `acfa47a2642725b22d92a0f53c40ccafc2c43205097db87dacbc987f6071de2b`. Cada ensayo revirtió sus escrituras sobre las tablas y restricciones originales.

| Efecto observado | Resultado para los dos operadores |
| --- | --- |
| Importe mostrado | Coincidió con la suma de los netos de los recibos marcados del empleado. Un contexto dio una suma positiva y dos dieron una suma negativa. |
| Entrada de nómina | En los seis casos se creó una sola entrada `DEDUCTION` en el borrador por el valor absoluto de esa suma. Se conservó el maestro original. |
| Marcas pendientes | Se retiró la marca de todos los recibos marcados del trabajador. Los tres contextos despejaron respectivamente una, dos y dos. En la simulación retrospectiva del segundo contexto, una de las dos pertenecía a un período que empezaba a partir del inicio del borrador. |
| Recálculo | El recibo pasó a verificación y el botón dejó de mostrarse. No se creó asiento. Las entradas manuales existentes conservaron su valor. |
| Seguimiento | No se crearon ni retiraron actividades. Para dos de los tres contextos, el recálculo actualizó la fecha o el usuario de modificación de cuatro y siete ausencias, respectivamente. Sus campos de negocio siguieron iguales. |

Tras revertir las seis operaciones se cotejaron los datos completos de once tablas de nómina, ausencias, contabilidad, actividades, mensajes, usuarios y grupos. Los comprobantes y los documentos contables originales mantuvieron sus importes. En U40RP avanzaron cinco secuencias de prueba por los identificadores de recibos, líneas, entradas, días y números de nómina. La ejecución inicial sobre U40N también detectó un avance de contador durante el ensayo preparatorio. No se rebobinó ningún contador.

La entrega Community .6.2 permite consultar las actividades históricas y conserva las marcas. La equivalencia con esta operación económica requiere que el operador pueda aplicarla explícitamente en un borrador y que se comprueben la deducción, el recálculo y el retiro de las marcas. La huella del ensayo nativo completo es `884d70220d1739029061dbb4d9381e89fa0dd35347d6b6482b4edb3e036b7d35`. La huella de la inspección nativa en modo de sólo lectura es `7d434bf6f6dcae480789a943ce6473a940fa2b64f35544e6dd2d69f8dd4431e5`. [Prueba nativa](../tools/community/probe_sys_negative_net.py)
