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
