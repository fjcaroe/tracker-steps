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

## Integración con Rendiciones

U50E partió de los 166 módulos recuperados, la corrección de la vista de Rendiciones y el proveedor de documentos de gastos. El módulo de notas de crédito se instaló como el número 168 y se actualizó con el mismo paquete. Las cinco identidades históricas del asistente, los 15.183 objetos SQL y los 1.748 archivos físicos coincidieron antes y después de cada paso. La instalación conservó 1.110 tablas completas y cambió cinco de metadatos. La actualización conservó 1.112 tablas y cambió tres de metadatos.

El operador y el usuario de consulta reprodujeron los 60 resultados del sistema original. Los 41 borradores se revirtieron y las 1.115 tablas mantuvieron su contenido. Avanzaron cinco contadores de prueba. Los recibos de instalación, actualización y prueba tienen las huellas `bf597de671ea26b0a21be3e4d4df4cdf29cc534fc1f7c29caa0c03908c3fd000`, `ce6864dcbc36790693d51f6cab75b50671349932febef6c711d85ac4675a1f92` y `faccf32d19f335636b04811c059152f85445d0a0d144ecbc0b2be75815060222`.

Los dos operadores consultaron también los 243 tickets y sus 418 adjuntos en U50E. El invitado volvió a ver cinco tickets, tres mensajes y dos descargas. Se mantuvieron las denegaciones del portal, los enlaces vigentes y revocados, y los límites de las páginas de dos tickets. El control original tiene la huella `b70f02af8ef320ae106f27fb74c4fa26db878733de21a7e673eb79250b2884c8` y el de U50E `6129bb233dc0de833f6cc665df42e6d506de456eaa128a6df5cb8439917a6f92`.
