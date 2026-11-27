# Notas de crédito de clientes en Steps Community

El operador de contabilidad abrió el formulario de cada una de las 20 facturas de venta contabilizadas de la copia nativa de Steps. En las 20 preparó una nota de crédito ordinaria y otra por corrección de texto. El otro usuario original pudo abrir las mismas facturas. Su formulario conservó el botón de nota de crédito oculto en las 20. El ensayo adicional con los dos textos de corrección vacíos reprodujo el comportamiento del asistente original.

La copia de 166 módulos conservaba la vista original del asistente, pero carecía de los cuatro campos chilenos que la vista utilizaba al abrirse. El proveedor `step_cl_credit_note_draft` registra esos campos en el modelo original `account.move.reversal` y utiliza la relación histórica de referencias de la factura. La versión 18.0.1.0.1, con licencia LGPL-3, tiene cinco archivos y la huella de paquete `5e8270b4a8bd25a91bc2bfaf4dd1db40be9be44a8bb1122449a46eaa7a03e552`.

La primera versión de ensayo preparaba correctamente el importe cero de las correcciones de texto, pero en seis facturas tomaba una cuenta del historial del cliente. La versión 18.0.1.0.1 utiliza la cuenta predeterminada del diario para esa línea. Las 20 notas ordinarias conservaron sus importes, impuestos y la referencia de código 3 a la factura de origen. Las 20 correcciones de texto conservaron el importe cero, la cuenta y la referencia de código 2. Los 40 borradores conservaron el tipo 61, la factura tipo 33 de origen, los enlaces desde el asistente y el documento, la moneda, el diario, el cliente y los apuntes. El formulario dejó el folio sin asignar.

En la derivada de ensayos U46D, los 60 contrastes de los dos usuarios y el caso de los textos vacíos coincidieron con la referencia nativa. Tras revertir cada borrador, se conservaron las 1.115 tablas y los 15.183 objetos SQL. U46D se creó a partir de U46C, cuya recuperación del respaldo de 166 módulos se documenta en [Mesa de Ayuda](COMMUNITY_STEPS_SOPORTE.md). La prueba cubre la preparación del borrador. La contabilización y el envío de una nota de crédito al SII siguen pendientes de validación.

| Evidencia | SHA-256 |
|---|---|
| Asistente y facturas originales, 60 contrastes y textos vacíos | `ef434372dc52a52df01aea2191e27d89f9c9500fd23583f8e6e04a869b2420ec` |
| Actualización del proveedor en U46D | `f628ad3db5aef236fd239bcd49d258a51766c003d5dadbde415465525969ea02` |
| Contraste funcional en U46D | `fc2022b9a842a6bd8e98d0eb6b279e7502b73745afd89a61ee159493833b36a4` |
