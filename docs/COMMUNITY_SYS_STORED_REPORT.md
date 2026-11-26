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
