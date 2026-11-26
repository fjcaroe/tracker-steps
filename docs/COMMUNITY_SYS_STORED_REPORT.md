# Impresión de las liquidaciones cerradas de SyS

El 26 de noviembre de 2026 se verificaron las cinco liquidaciones cerradas de
octubre de la empresa seleccionada por la referencia nativa. En la copia
Community de SyS, el operador original abrió la acción original 1431 e
imprimió cada documento. La comprobación partió de las líneas históricas y
comparó los archivos con sus respectivos importes almacenados.

| Comprobación en U40R | Resultado |
| --- | --- |
| Liquidaciones impresas y páginas legibles | 5 de 5, una página por documento |
| Líneas visibles, incluida la tabla de otros conceptos | 61 de 61 identificadores e importes entre 86 líneas históricas |
| Líquido en HTML y en el texto extraído de cada PDF | 5 de 5 coincidencias con el NET original |
| Ocho archivos previos adjuntos a las mismas liquidaciones | 8 de 8 SHA-256 intactos |
| Acción, liquidaciones, entradas, días, líneas, reglas, contratos y adjuntos anteriores | Huellas anteriores y posteriores idénticas |

Dos PDF archivados contenían un líquido anterior diferente del NET almacenado.
Se conservaron ambos byte a byte. El nuevo PDF de cada liquidación mostró el
importe que tenía su línea NET al comenzar el ensayo.

Se probaron el lector de líneas en `aa2c1bed`, la plantilla de Cerro en
`4d6e8288` y la ruta de impresión en `84aa050a`. En SyS el diseño estándar
presenta la empresa en el cuerpo. La ruta mantiene el encabezado oficial vacío
cuando cada artículo contiene la empresa autorizada y su tabla de nómina.
Los cinco casos de regresión de la tipografía y estructura de cabeceras pasaron.
Los archivos generados y sus importes quedan en custodia privada.
El recibo independiente de verificación de PDF tiene SHA-256
`5227d394e521728055342377a42b5e49c6be6d85414e7af108229b3b3d3b23b6`.

La primera actualización general de Simple Digital en U40R intentó volver a
escribir el grupo histórico de empleados. La protección de SyS detuvo esa
operación. Se instaló la ruta de impresión por separado y se mantuvo la
protección. La actualización general del proveedor chileno continúa pendiente.

## Repetición desde una restauración limpia

En U40R2 se partió nuevamente del respaldo de la cohorte U40E
(`1acacf8f8754826d85e95730f4e65b9f031b84ef6fff34a943eea6b6c7438457`).
Se instaló el puente de informes por su entrada oficial y se cargó únicamente
la plantilla Steps mediante el cargador XML de Odoo. Se verificaron su
arquitectura anterior, la fuente y sus identificadores originales. La segunda
llamada reconoció la arquitectura aceptada y no escribió. La base conserva
registrada la versión previa 18.0.1.7.2 del módulo base; el lector Python
probado en esta derivada procede del paquete 18.0.1.7.3.

Se imprimieron nuevamente cinco PDF de una página. Los 61 identificadores, los
61 importes visibles y los cinco líquidos coincidieron. Los ocho adjuntos
archivados y las filas originales de los grupos de usuarios conservaron sus
huellas. El recibo independiente de esta repetición tiene SHA-256
`c9c3d3256567e5b11f8593f5051f2ba78c5da6d9aefb83094c97d17a64bc0421`.
