# Recuperación del perfil SyS de Nómina para integrar Documentos

## Límite de preservación detectado al preparar la conversión fiscal

U43C acredita los recorridos funcionales descritos y conserva fielmente su propio estado en el respaldo de catorce piezas. La comparación posterior entre el esquema original de U42L y el esquema combinado encontró trece columnas que perdieron la obligatoriedad durante la instalación de Documentos. El uso de U43C como origen de una conversión integral queda suspendido. La preparación de U44FD detectó esta diferencia antes de aplicar su primera actualización fiscal.

Las once columnas afectadas de `res_company` son `account_tax_periodicity`, `account_tax_periodicity_reminder_day`, `currency_interval_unit`, `deferred_expense_amount_computation_method`, `deferred_revenue_amount_computation_method`, `generate_deferred_expense_entries_method`, `generate_deferred_revenue_entries_method`, `planning_employee_unavailabilities`, `planning_generation_interval`, `timesheet_mail_employee_interval` y `timesheet_mail_interval`. En `documents_document` se vieron afectadas `alias_id` y `document_token`.

Los dos snapshots conservan las 12.010 columnas de U42L, sus tipos y valores por defecto. Las 5.816 restricciones originales, las 1.996 relaciones con sus propietarios y permisos y las 858 definiciones de secuencias coinciden. U43C añadió 25 columnas, diez restricciones, seis relaciones y tres secuencias de los asistentes y campos documentales.

Una segunda limitación afecta al directorio de ejecución extraído del paquete. El proceso de recuperación lo creó con permisos 0700 de root y el usuario de Odoo no pudo atravesarlo en el montaje fiscal. El archivo del motor sí pasó su verificación byte a byte en la estación. La siguiente restauración debe comprobar el arranque como el usuario de servicio desde la extracción preparada con los permisos de lectura correspondientes.


El punto de partida de U43C es la copia privada U42L de SyS. Contiene 765 liquidaciones y 1.430 documentos. El respaldo congela las 1.138 tablas públicas, sus 608.867 filas y las 858 secuencias con sus valores. La segunda lectura de U42L coincidió con las tablas, el esquema y los contadores de la primera.

| Componente verificado fuera del servidor | Resultado |
| --- | --- |
| SQL | `0c4e970e29579c6de38d71397a987682e97ff9a90027baad8c9e9b77f84bf606` |
| Almacén de objetos referenciados | 2.679 objetos, `d694d99ca0e8670922caefc5eb98d47249cd09b675057824e09ad6b1dbd88b2a` |
| Árbol físico completo | 2.698 entradas, incluidos nueve objetos sueltos y diez marcas de recolección, `71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c` |
| Motor y módulos efectivos | 22.238 archivos y 190 proveedores, 189 LGPL-3 y uno AGPL-3, `46b1bc9d66abd42ab9c066eacc468a7553aee6a59b54c2c70b8393b4d9782a1a` |
| Paquete de Nómina | Siete módulos y 133 archivos iguales a los del motor congelado, `547c89989b796475cbb46075992f4008c10d23f7a50bbf450f0941192e81fc07` |
| Manifiesto local del respaldo | 11 componentes comprobados por tamaño y SHA-256, `370bf3255b9c82e1f028858fbaf89c1c0135706647a6072b65961b98ac878d40` |

La nómina usa `step_payroll_oca_sys_history` 18.0.1.6.1. La recuperación mantiene los valores de secuencia vigentes al tomar el respaldo. También conserva seis diferencias previas entre la versión registrada y el manifiesto efectivo.

| Módulo | Versión registrada | Manifiesto | Origen |
| --- | --- | --- | --- |
| hr_timesheet | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| l10n_latam_invoice_document | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| project_sms | 18.0.1.0 | 18.0.1.1 | Odoo Community |
| l10n_cl_simpledigital_payroll | 18.0.1.0.0 | 18.0.1.1.0 | Cohorte SyS |
| step_hr_previred | 18.0.3.8.7 | 18.0.3.8.8 | Cohorte SyS |
| step_hr_previred_simpledigital | 18.0.2.4.1 | 18.0.2.4.2 | Cohorte SyS |

## Nómina, Biblioteca y Portal en U43C

La copia privada incorporó el paquete documental `c8548015d864c1bac5b7b0a6d8eef588d2cfb4a29ed31132309f2b2e032c1b88`. El registro arrancó con los 190 proveedores de origen y los dos nuevos, `step_document_library` 18.0.1.0.5 y `step_document_library_portal` 18.0.1.0.3. La resolución efectiva de los 192 módulos confirmó 190 licencias LGPL-3 y dos AGPL-3. La primera adopción verificó 1.430 marcadores internos y 1.430 enlaces de portal sobre sus filas originales. La repetición escribió cero filas.

Las dos cuentas temporales de Portal se crearon en la nueva restauración antes de instalar la última protección de membresías del respaldo. Se comprobaron las 40 protecciones, las siete cuentas originales, 438 membresías, 538 reglas, 1.718 permisos de modelo y 5.441 adjuntos originales. También coincidieron las 3.955 filas originales de acceso documental, las 2.021 filas de correo y el contenido de los 1.430 documentos históricos.

Para la prueba se escogió uno de los 1.240 PDF privados que comparten la misma identidad de adjunto entre Biblioteca y Nómina. El gerente original abrió la liquidación en su compañía, recorrió la carpeta desde el menú histórico, abrió el formulario de Biblioteca y usó el enlace que entrega el editor. El PDF tuvo 27.369 bytes en ambas aplicaciones. La otra compañía y el acceso público directo al adjunto quedaron denegados.

La compañía del destinatario del ensayo y la del documento estaban asignadas al gerente. El selector de destinatarios respetó esas compañías al otorgar y retirar la lectura. Las dos cuentas de Portal iniciaron sesión por el controlador de autenticación de Odoo en una red privada del proceso. La clave del enlace y el contenido del documento permanecieron dentro de la prueba.

| Estado del permiso sobre el archivo original | Destinatario | Otra cuenta Portal | Anónimo |
| --- | ---: | ---: | ---: |
| Restringido | 404 | 404 | 404 |
| Lectura concedida | 200, mismo PDF | 404 | 404 |
| Lectura revocada | 404 | 404 | 404 |

La suma SHA-256 del PDF entregado al destinatario coincidió con la lectura del gerente y con el adjunto original verificado en el respaldo. Todo el recorrido documental se revirtió al terminar.

Los nueve ensayos de Nómina reprodujeron los nueve resultados de U42L en maestros, libro, reglas, alcance contable, días trabajados, confirmación, diferencias de horas rechazadas, lote y empresas. El libro reprodujo la huella `38d10fe52f0b1d41084e86658d33cd2fdbd44d783eeb8bdaf6005992e65f5009`. El lote de cinco borradores se confirmó sobre transacciones reversibles. Esta comparación mide el comportamiento calificado de U42L.

Las 87 tablas originales de historia laboral, liquidaciones y contabilidad comprobadas conservaron sus datos. Antes y después de los flujos, las 1.141 tablas de la copia coincidieron fila por fila, junto con el esquema, propietarios y permisos. Doce secuencias avanzaron en los ensayos y sus nuevos contadores quedaron registrados.

El recibo funcional `combined-product-proof.json` tiene SHA-256 `3cd1f2666053fb81a088d4b7ac230ba3aa2ad804731e8080780bd3a2a2e9efb1`. La copia U43C queda como control independiente para los ensayos fiscales de una derivada posterior.

## Instantánea entregada al ensayo fiscal

Una vez cerrados los ejercicios se capturó una segunda instantánea de U43C. Reúne sus 1.141 tablas con 609.045 filas, las 861 secuencias, los 2.698 archivos físicos y el motor autónomo de los 192 módulos. Las 22.238 rutas del motor de Nómina conservaron sus bytes y permisos. Las otras veinte rutas coinciden con los dos proveedores de la entrega documental. En esta instantánea se conservan los contadores posteriores a las pruebas.

| Verificación de la instantánea combinada | SHA-256 |
| --- | --- |
| Base de datos | `3e8dbc09924d1314b98a77851248f8a1d96b084672ada561c998668dd9c46fb6` |
| Archivo del motor con los 192 proveedores | `5a3348da8fb1caa58e30023c9a27d834bdd4087ede82f7ac928bbae8e4c723c7` |
| Archivo de objetos referenciados | `396013497147e9ee4adf89f0d65fa7dc86d35093138a0c7f26c85cb55970a438` |
| Árbol completo del almacén, idéntico al de U42L | `71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c` |
| Recibo del respaldo usado por la derivada, `backup.json` | `b581a15a5551742d183720ae1faae7b480537b3622d7c990e7d2973d5bb9caa6` |
| Recibo del almacén usado por la derivada, `filestore-physical.json` | `5547203ba39b959743c3a496d7490d031288c649b83058c3bb821ad467aaff53` |
| Manifiesto de los 14 componentes en la estación | `838e4f1fb89c265dd71df3fc27066989e8f7c3d35677531f6704b7f79f17e231` |

El verificador portable volvió a leer los 22.258 archivos del motor, las 2.698 entradas del almacén, los 133 archivos del paquete de Nómina y los veinte del paquete de Documentos. Las huellas de ambos recibos se suministraron por separado al restaurador de U44FD.
