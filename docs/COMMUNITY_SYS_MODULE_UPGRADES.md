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
