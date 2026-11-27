# Actualizaciones de seis módulos en la copia Community de SyS

La cohorte U41M se restauró a partir del respaldo Community U41R de U40J el 27 de noviembre de 2026 UTC. La instalación de origen registraba seis módulos con una versión anterior a la de sus fuentes. Esta prueba usa la versión instalada 18.0.1.5.0 de `step_payroll_oca_sys_history`. El ensayo del calendario 18.0.1.5.1 tiene su propia evidencia en [la comparación de exportaciones](COMMUNITY_SYS_PAYROLL_EXPORTS.md).

| Módulo | Versión SQL inicial | Versión del paquete | Migración específica en el intervalo |
| --- | --- | --- | --- |
| `l10n_cl_simpledigital_payroll` | 18.0.1.0.0 | 18.0.1.1.0 | Sin script de migración |
| `step_hr_previred` | 18.0.3.8.7 | 18.0.3.8.8 | Sin script de migración |
| `step_hr_previred_simpledigital` | 18.0.2.4.1 | 18.0.2.4.2 | Sin script de migración |
| `hr_timesheet` | 18.0.1.0 | 18.0.1.1 | `upgrades/1.1/pre-migrate.py` |
| `project_sms` | 18.0.1.0 | 18.0.1.1 | `upgrades/1.1/pre-migrate.py` |
| `l10n_latam_invoice_document` | 18.0.1.0 | 18.0.1.1 | `migrations/1.1/post-migration.py` |

El último script desactiva el bloqueo por hash en diarios de compras latinoamericanos que usan documentos y lo tienen activado. El origen contiene 33 diarios de compras con documentos. Ninguno cumple la tercera condición.

## Respaldo y permisos

| Elemento | Cantidad y control |
| --- | --- |
| SQL | 608.840 filas, SHA-256 `94db4529d4f3230a96f7df3d628d485878a978f67a826a5cf534037f237eb65e` |
| Adjuntos | 2.679 objetos, SHA-256 del archivo `3cdbab1b9d6095dbb2e321d93b12d2c209d279bb189c61670d93cf7bef19813b` |
| Entorno de ejecución | 190 proveedores y 22.235 archivos, SHA-256 `10d896c4b5eee9d350c429d3be856869683ee644ed3e1b9221903dda460164be` |
| Paquete de interfaz | SHA-256 `f9a7be026a550acf3e383f92414ed18161d6336d771184ee0936daeaf81d39e7` |
| Protección de originales | Los 40 triggers conservaron definición, función y estado al restaurar |
| Almacenamiento | Tablespace privado, 6.006.390.784 bytes disponibles en PostgreSQL y 33.611.968.512 en el volumen privado antes de crear U41M |

Se cotejaron los 32 registros de acceso de los seis módulos contra los identificadores originales. Coincidieron el modelo, el grupo, el nombre y las cuatro operaciones. También coincidieron los cinco grupos y las tres reglas que los archivos XML ofrecen actualizar, incluidos grupos implicados, dominios y ámbito global. Los originales conservaban su valor de `noupdate`.

La restauración y el instalador oficial comparten el mismo bloqueo de ambientes. Cada programa usa el socket PostgreSQL y un directorio de datos propio. El entorno aislado monta el ejecutable sellado para lectura. Los procesos no tienen conexión de red y se desactivan HTTP y cron. Los recibos privados contienen diferencias por tabla, estados de los módulos y resultados por función de usuario.


## Código original de las reglas de proyecto

El paquete oficial 1.1 de partes de horas cambia las dos reglas de los aprobadores. Añade al seguidor de la tarea entre los usuarios con acceso al proyecto privado. La migración de SMS retira los modelos de etapa de proyecto y etapa de tarea de la regla del encargado de plantillas e incorpora los de proyecto y tarea. Los tres dominios de SyS conservaban el comportamiento anterior.

Las dos implementaciones originales corresponden exactamente a la revisión pública `52864b102af6eb4bdedc7910e9cbb6841903a2a3` de Odoo 18. Se cotejaron los objetos Git y sus modos, incluidos todos los archivos de traducción. Ambos manifiestos declaran versión 1.0 y licencia LGPL-3. [Partes de horas de Odoo](https://github.com/odoo/odoo/tree/52864b102af6eb4bdedc7910e9cbb6841903a2a3/addons/hr_timesheet) y [SMS de proyecto de Odoo](https://github.com/odoo/odoo/tree/52864b102af6eb4bdedc7910e9cbb6841903a2a3/addons/project_sms).

| Proveedor | Archivos | Árbol Git idéntico al de SyS |
| --- | ---: | --- |
| `hr_timesheet` | 142 | `7b9b6adbee716a8ff805efbb10659084c1fb8377` |
| `project_sms` | 58 | `e2a37f7d07d09c4dc3009eae9fa8ca6d94eac45c` |

Dos descargas independientes de las fuentes públicas produjeron un archivo de 4.270.080 bytes con SHA-256 `e1ab99abe55ac7693afe6c48f3ee51aa4ac27208b483472a6e8ae20f0be6233b`. El empaquetador reconstruye los árboles y valida cada archivo contra el objeto de Git correspondiente. [Empaquetador](../tools/community/package_sys_original_policy_providers.py).

Los dos scripts 1.1 se ejecutaron sobre tablas temporales con los tres dominios originales. Después se consultaron ambos predicados, con cada operador y cada empresa activa que tenía asignada. En las 52 combinaciones por regla coincidieron los registros consultables. El ensayo respetó las demás reglas y permisos efectivos de cada usuario.

| Regla original | Casos sintéticos | Acceso adicional de 1.1 | Acceso retirado de 1.1 |
| --- | ---: | --- | --- |
| Aprobador de partes de horas | 8 | El seguidor de la tarea en un proyecto privado cuyo proyecto no sigue | Ninguno |
| Aprobador de análisis de horas | 8 | El mismo caso de seguidor de la tarea | Ninguno |
| Encargado de plantillas SMS | 5 | Plantillas de tareas y proyectos | Plantillas de las dos clases de etapa |

## Ensayos con la distribución sin adaptar

U41M ejecutó el actualizador oficial con la distribución sellada y las protecciones que ya existían en PostgreSQL. Los paquetes de Simple Digital y Previred principal intentaron escribir sobre grupos originales. Las dos migraciones de proyecto intentaron modificar dominios originales. La integración Previred pasó de 2.4.1 a 2.4.2 y el cargador relajó 11 restricciones `NOT NULL` originales en `res_company`. La verificación comparó estas restricciones además de las filas.

U41MP repitió las seis operaciones con el cargador protegido de la instalación original. Llegaron a su destino Previred 3.8.8 y la integración 2.4.2. El proveedor Simple Digital llegó a 1.1.0 antes de que su dependiente `step_payroll_engine_transition` fallara al reimportar un permiso existente. Las dos filas de tipos de contrato y las cuatro tareas programadas con sus acciones delegadas solo cambiaron de fecha de edición. Los seis intentos se conservaron por separado. Los 2.679 objetos de adjuntos, las 1.697 filas de PDF de liquidaciones y todas las restricciones `NOT NULL` originales se conservaron en U41MP.

El instalador LATAM intentó volver a aplicar el localizador `//img/../..` sobre la plantilla estándar personalizada de SyS. La vista 204 de SyS tiene un encabezado sin imagen y la herencia 1215 ya se ajusta a él. Sus arquitecturas, padres y referencias externas coincidieron en el original nativo y en U40J. El bloque estándar distribuido por Odoo coincide en 1.0 y 1.1, con SHA-256 XML canónico `3d70253f3d94a0bd6ab09c0e3ba14fa910e7efc902bb17dbea9e49a1c48c4a39`. El cambio de la distribución 1.1 afecta al pie del diseño de ondas.

El script fiscal original se ejecutó en el proceso de Odoo sobre la copia y sobre 18 combinaciones en una tabla temporal. Afectó cero diarios en la copia y solo al caso sintético de compra con documentos y bloqueo activado. Ambas transacciones se revirtieron.

## Comparación de maestros y carga de código

U41MQ arrancó desde la misma restauración con las dos versiones públicas 1.0 y 41 declaraciones de datos cotejadas contra los registros de SyS. Completó las tres actualizaciones de nómina. El actualizador fiscal ejecutó su migración y alcanzó 1.1. Una dependencia posterior, `step_account_monthly_books`, intentó reimportar dos permisos originales y el paso completo terminó con error. Los dos actores abrieron los seis formularios tanto antes como después del ensayo.

El cotejo por identidad y por columna detectó 206 filas originales modificadas por la recarga de datos chilenos. En 204 filas solo cambió la fecha de escritura. Otras dos etiquetas de impuestos recibieron además un texto `es_CL` que el origen no tenía. Los demás valores y vínculos originales coincidieron. El perfil de conservación se obtuvo de las declaraciones de datos ya distribuidas por Odoo. Cada registro tiene una referencia externa original y la misma identidad. El catálogo del perfil excluye las dos traducciones adicionales de esas etiquetas.

| Maestro fiscal | Filas cotejadas |
| --- | ---: |
| Etiquetas de cuenta | 47 |
| Informe fiscal y columna | 2 |
| Líneas y expresiones de informe | 64 |
| Tipos de documentos | 58 |
| Tipos de identificación | 3 |
| Bancos | 32 |

Veinte de las 47 etiquetas se declaran en `l10n_cl_chart_data.xml`. Las otras 27 pertenecen a `account_tax_tags_data.xml`. El perfil exige que las declaraciones de los seis archivos cubran exactamente las 206 identidades. Las filas completas de las ocho tablas se comparan con la fuente restaurada, incluidas las no mencionadas por el proveedor. [Verificación de los maestros fiscales](../tools/community/preserve_sys_original_fiscal_masters.py).

El ejecutable `odoo-bin` del respaldo incorpora su carpeta `runtime/addons` antes de procesar las rutas configuradas. Los módulos seleccionados se montan además en esa ruta dentro del entorno privado para que el instalador y el arranque normal usen el mismo código probado. La prueba en frío compara el archivo importado, los manifiestos de los módulos y las fuentes de los 190 proveedores activos. [Ejecutor](../tools/community/rehearse_sys_module_upgrades.py) y [comprobación desde Odoo](../tools/community/probe_sys_retained_provider_release.py).

## Referencias históricas de facturación

La plantilla de factura chilena de SyS solicita la relación `account.move.l10n_cl_reference_ids`. El registro de modelos Community de J podía abrir los formularios de documentos, pero fallaba al imprimir con esa plantilla. El origen conserva la relación 8296 y el modelo 639, con cinco referencias de notas de crédito de compra y una de venta. Cada fila apunta a un documento contabilizado distinto mediante la clave `move_id`. En el origen ninguna factura tiene un timbre SII guardado en esa columna.

El adaptador de Steps declara la relación sobre la tabla original, las referencias al tipo de documento, los códigos de referencia y las columnas que usa el pie de la factura. La preparación del paquete coteja los once campos, el modelo, los tres códigos, la clave inversa y las seis filas con la copia nativa. Conserva la lectura para el grupo interno y los permisos de facturación para sus operadores. Los ensayos se limitan a documentos ya contabilizados y a la representación en imagen de un texto sintético. [Adaptador histórico](../tools/community/sys_chilean_invoice_history.py) y [cotejo de estructura y permisos](../tools/community/build_sys_invoice_history.py).

En MV, los cuatro actualizadores oficiales terminaron con las versiones esperadas y se conservaron todas las restricciones obligatorias. Tres tipos de identificación mantenían un ámbito interior explícito de actualización en el XML del proveedor. La única diferencia de sus filas era la fecha de escritura. La construcción de MW aplica el atributo de conservación a ese ámbito interior y parte otra vez del respaldo U41R.

La plantilla también consulta dos campos calculados de firma. Ninguna de las 29 empresas del origen tenía habilitada el área de firma. Había 124 firmantes registrados en 8.129 movimientos, además de una imagen de firma personal existente. El comparador solo publica conteos y huellas. La copia nativa se consultó como usuario de facturación en sus empresas activas. En los 6.972 documentos que podía leer se respetó la configuración guardada. En 180 combinaciones sintéticas se midieron estado, tipo de movimiento, configuración de empresa y presencia de una imagen artificial. Las 72 combinaciones adicionales de boletas de entrada y salida nunca habilitaron la firma. [Comparador de firma](../tools/community/probe_sys_invoice_signing.py).

El origen emplea la plantilla de factura chilena también para las cinco notas de crédito de compra. En las seis notas se cotejaron las referencias originales y los motivos que el operador puede leer. La referencia nativa de los doce artículos impresos en HTML tiene SHA-256 `f377c74132a77b46b34b4f49f97539b49419b436da84f27267aa7c2436fdd008`. [Captura en el motor original](../tools/community/probe_native_sys_invoice_text.py).

La política de borrado en la línea de asiento de SyS es `CASCADE` sobre su cuenta y la de los impuestos referenciados por el modelo de conciliación es `RESTRICT`. Los campos originales son 6077 y 5963. El proveedor chileno expresa ambas políticas en los campos ORM. La actualización fiscal normal recompuso esas claves foráneas en MW. El cotejo posterior contra el respaldo íntegro dio cero diferencias de columnas, restricciones, propietarios, permisos SQL, definiciones de secuencias y tablas comerciales cubiertas.

La prueba de ambas políticas construyó dos relaciones temporales con las acciones leídas del catálogo PostgreSQL de MW. El borrado de una cuenta eliminó el apunte artificial y el borrado de un impuesto todavía referenciado produjo la excepción original. Los dos ensayos terminaron con una reversión. El recibo tiene SHA-256 `917f6b4f48dbb80447c2027a62bb04a192fea3c59a1aa2a1c0663a8175c04182`.

El perfil financiero en esta prueba contenía 187 archivos, con SHA-256 del TAR `716e338839142e3bfe02b038333fb742b09ca5fd6f4bd91753739a7a0bf1b61c`. El cotejo posterior contó 54.385 identificadores externos originales, 40 controles de escritura, 2.679 archivos y 1.697 registros de PDF de nómina. Cambiaron once tablas del registro de Odoo y los valores de once secuencias de administración o asistentes de prueba. Las definiciones de las secuencias y las filas comerciales conservaron sus huellas. El recibo del almacenamiento tiene SHA-256 `adc1152c4397d67b0765b3a57ecba605fe7d199dfad60eed4f448a12c666c39d`.

El cotejo del artículo de las seis notas encontró ocho precios unitarios cuyos dos ceros decimales desaparecían tras la actualización. Los ocho importes seguían teniendo el mismo valor numérico. La plantilla chilena 1281 del origen mostraba dos decimales en el precio unitario y conservaba la posición del bloque de descuento. La edición del proveedor libre recupera las dos expresiones. La actualización ordinaria restauró íntegra la plantilla en español de Chile e inglés. Su huella en SQL volvió a `8fc9e221a7d0138e7bb479054774576f7426a2710323357a81c13356285ea92a`.

El perfil corregido de 187 archivos tiene SHA-256 `ca9180cdd5d3be9b5e69073d83171760cef34b22b07ae0a7cb38940cbd63ce37`. Con él, MW reprodujo las doce huellas de texto completo de las seis notas para los dos operadores, las 252 combinaciones de firma y la presentación de los 6.972 documentos accesibles al operador de facturación. Las 190 versiones del registro coincidieron con los proveedores efectivamente cargados. El recibo de estos controles tiene SHA-256 `08aa40062fd28ee705caae6d1edfb07f93a15208edf484f7ac94d9d2d701d806`.

Los dos operadores imprimieron en MW una factura contabilizada y una nota de crédito por persona mediante la acción original. Se generaron cuatro PDF de una página. El lector de PDF encontró todas las palabras del artículo en cada caso y las referencias del documento original en ambas impresiones de la nota. Los cuatro archivos se cotejaron por SHA-256 y se rasterizaron por segunda vez fuera del servidor. El recibo de impresión es `8d18f38dae5a9da6e442f3df08102d54cad36e92cc1bece8f6fd80b83565db0e` y el de rasterización `49c5abf7fe1f5e6fdb0e13bf9a04837d2286f7ab8bfdd6b36663af6a1d269af7`. [Verificador independiente](../tools/community/verify_sys_invoice_pdfs.py).

Con el paquete definitivo, los 24 pares de operador y empresa conservaron los archivos y diagnósticos del estado de nómina de origen de MW (18.0.1.5.0), con recibo `922b74a15a3e85e949114ddb8130f9529c3be4a09145bb2ba576ef51764121ee`. El postflight final después de la impresión tiene SHA-256 `bc47ad575e6f7ddc1a2ddd65dbe70d14cc3a1b5016566872e1a56d58c0696bb0`. Los ensayos de nómina 18.0.1.6.1 y del conjunto con Biblioteca corresponden a derivadas independientes.

### Ensayo conjunto de nómina 18.0.1.6.1 y facturación

MF partió del respaldo sellado de L, con 608.867 filas en 1.138 tablas y 190 proveedores efectivos. Se restauraron los 2.679 objetos referenciados, nueve objetos sueltos y diez marcas del filestore. La huella del árbol completo de 2.698 archivos fue `71c9add47cf4265ee31555f42c02c8a819b8683154e53858490b22c6c11f8d1c`. El paquete financiero reconstruido sobre esta copia coincidió con los 187 archivos de MW.

Las cuatro actualizaciones oficiales se completaron, los dos módulos que contienen las políticas originales conservaron su versión 18.0.1.0 y las 190 versiones activas coincidieron con el registro. Los 24 pares de Previred y Libro de Remuneraciones, con sus pantallas y diagnósticos, coincidieron íntegramente con el motor nativo para las 12 empresas. El recibo tiene SHA-256 `658f035c21f60012a63da9aca4e566ad009501ad57e6d709ac78d19fee5cf41a`.

Los doce artículos de las notas coinciden con las impresiones HTML nativas. Cada operador imprimió también una factura y una nota de crédito. Los cuatro PDF de una página coincidieron en texto completo con los impresos en MW y se rasterizaron fuera del servidor. Los recibos tienen SHA-256 `50501360d63b269978d2c6ea8c62698680081bd7db6c9712eff4e802c2e74ba6` (impresión) y `9d71fb06e0115ed8c1b7abb3146eeab5dd9bfd1a3892396e7a810b3d9624e8a5` (rasterización). Después de los recorridos siguieron intactos los 54.409 identificadores de origen, los 1.697 registros de PDF de nómina, las columnas, claves foráneas, propietarios y permisos SQL y las filas de negocio cubiertas. El recibo tiene SHA-256 `2b064674c4835cf696c3ba8f6bec0917d37682f4a7e2ef96de360220e50e89d1`.

El motor original imprimió las mismas cuatro páginas por la acción de factura, con recibo `1916ca300a4bbd0d3be792ac016a2a558af5a11eb54341bab90396854c5e13f2`. Entre el original y cada versión Community coincidieron documento, empresa, operador, permisos, texto íntegro del PDF, tamaño A4, los 141 tramos de texto con su tipografía y coordenadas, y los 140 trazados con su geometría. El tema original usa los colores de texto `#111827` y `#5f636f`; el de Community usa `#212529` y `#6c757d`. Al rasterizar en gris, esta diferencia afecta entre el 1,71 % y el 2,74 % de los píxeles según el documento. El recibo de geometría de MF tiene SHA-256 `13fb8919fb52a6708cf1ef470443eb36574b15f4b1ee83a40c66cb5bfbcff7e6`.

La relectura posterior a las impresiones volvió a cotejar los 2.698 archivos y marcas de origen de MF con la misma huella íntegra. La compilación de los estilos incorporó un objeto CSS de contenido y tres marcas de recolección. De las 5.441 filas de adjuntos que tenía el origen, 5.439 conservaron todos sus valores. El servidor reemplazó dos registros de estilos compilados de `/web/assets/` por dos nuevos. El recibo de conservación posterior a todos los recorridos tiene SHA-256 `9d8223d5cdad3520b8c0ef81d1547aae54167d26ba7f79ebfe72ac34c7de4c75`.

### Catálogo completo y directorio de empleados de SyS

La revisión de FG amplió el cotejo a todas las vistas SQL, índices y derechos de propiedad. Entre L y MF se conservaron las 12.010 columnas de tabla, las 5.816 restricciones, los 2.484 índices y los tres diseños de facturación. En MF, la actualización de RR. HH. regeneró la vista SQL `hr_employee_public` desde los campos activos y omitió tres columnas históricas de su proyección. En la copia C, la instalación documental relajó 13 restricciones de obligatoriedad que sí existían en L. Once pertenecían a `res_company` y dos a los documentos. FD restauró el mismo estado de C y se detuvo antes de procesar actualizaciones.

La nueva derivada FG se restauró directamente de L, con las 608.867 filas de origen y las 2.698 entradas físicas de su almacén. La comparación por filas identificó las dos cuentas sintéticas de Portal, sus dos contactos, dos relaciones de empresa y seis pertenencias a grupos. La huella del recibo de restauración fue `a3e1dd3e3d928865ffa95790898d373c8b98ca773280e7be3c7dcd208fce53d4`.

El perfil de RR. HH. de FG proviene de los 217 archivos del proveedor libre. El nuevo proveedor conserva la definición íntegra de `hr_employee_public` tras cotejarla con las seis identidades de campos de origen de `hr.employee` y `hr.employee.public`. Los campos históricos son `last_appraisal_id`, `ongoing_appraisal_count` y `timesheet_manager_id`. Las tres columnas leen los valores originales de `hr_employee`. La revisión verifica el propietario de la vista, sus permisos, las 31 columnas proyectadas y que los campos activos que requiere Odoo sigan presentes. El archivo TAR de 218 miembros tiene SHA-256 `91c782849b652422c4324a9c8cf7dc9cf50323b1569515127e95a8dc20af7feb`. [Constructor del perfil](../tools/community/build_sys_employee_view_profile.py) y [conservación de la vista original](../tools/community/sys_original_employee_view.py).

Cada actualización se contrasta con la misma referencia de L, de huella `4f8f84fdd9dc34ca7cb903540aa67db88554653999bbe2adf20a7c7b4a959e27`. Incluye todas las columnas y restricciones, 2.484 índices con sus permisos, el propietario y los permisos de 1.996 relaciones, la definición de 858 secuencias, sus 741 vínculos de propiedad, las 26 vistas SQL y los tres diseños SQL de facturación. El control comprueba también las 21 columnas obligatorias cuya definición puede intentar relajar el instalador. [Cotejo del catálogo](../tools/community/guard_sys_original_catalogue.py) y [ejecutor de ambas fases financieras](../tools/community/rehearse_sys_fiscal_documents.py).

FG completó las cuatro actualizaciones financieras y de nómina. En los ocho puntos antes y después de cada módulo permanecieron idénticas todas las propiedades originales comparadas. El postflight financiero, de SHA-256 `26aa1f882ca7788cb6d9aa663e80a94c290afc0f83a1086d146d4ad5de5785c6`, volvió a verificar 54.409 identificadores externos, 40 protecciones de escritura y 1.697 registros de PDF de nómina. La relectura de los 2.698 archivos devolvió la misma huella física de L. Las acciones de eliminación de las dos claves foráneas se ejercitaron con filas temporales.

La lectura del directorio de empleados se ejecutó con los dos operadores reales en sus 52 combinaciones de empresa y usuario, con el acceso propio de cada uno. En los 52 casos coincidieron el número y la huella de las filas visibles entre el entorno nativo y FG. Los formularios financieros y el directorio dieron el mismo recibo antes y después de las actualizaciones, de SHA-256 `30c200fa90707142f9d2f980505e888b9ac9be6bd36eee11370a25f097144451`. La referencia nativa es `4241069cd6248766568b7c7282b556a5efb2b3f9e5576b2397277607cb85f9f9` y la comparación es `f99554b60333b1d525da9163bb80917f7824299831d4c726c65ce52d7313008f`. [Prueba de lectura por operador](../tools/community/probe_sys_employee_directory.py).
