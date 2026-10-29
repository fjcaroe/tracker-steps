# Beneficios salariales: contrato original y puerta pendiente

Auditoría de solo lectura desde `78e5cde8`, 29-10-2026. No se instala un
proveedor, cambia una dependencia ni se declara cerrada la brecha de
`hr.payroll.structure.type.salary_benefits_ids`.

## Contrato observado

En Cerro y SyS el campo original es un **One2many**, almacenado y editable,
no obligatorio, con comodelo `hr.contract.salary.benefit` e inverso
`structure_type_id`. El inverso es un Many2one obligatorio a
`hr.payroll.structure.type`, con eliminación **RESTRICT**. Sus XML IDs,
modelos, campos y PK son propios de cada base; no se pueden trasladar los
IDs numéricos de una empresa a la otra.

El comodelo contiene **46 campos, 36 almacenados**. Incluye tipos de beneficio,
valores, país, campos reales de contrato mediante `ir.model.fields`, relaciones
consigo mismo, documentos solicitados, resúmenes, actividades y Firma. Las
propiedades de visualización y los campos relacionados no acreditan las APIs
de cálculo, validación, configuración de ofertas ni sus permisos efectivos.

Se observaron cinco ACL sobre el modelo: sistema y responsable de contratos
tienen CRUD; usuarios internos, portal y público tienen lectura. No hay reglas
de registro sobre ese comodelo en estas capturas. Esta política pertenece al
catálogo original: **no autoriza dar acceso público a importes de contratos**,
asignar un rol gerente ni trasladar esas ACL a otro modelo.

El proveedor instalado es `hr_contract_salary` 18.0.2.0, **OEEL-1**,
con los puentes Enterprise de Nómina y ausencias. Se leyeron metadata SQL y
manifiestos de licencia; no se copiaron ni inspeccionaron cuerpos de fuentes
Enterprise. La relación SQL y la metadata no certifican métodos del registro.

## Datos y referencias

Ambas referencias conservan cero filas de beneficios, valores de beneficios,
ofertas y las tres relaciones M2M de beneficios. Esto reduce el alcance de
datos configurados, pero no elimina el contrato ni permite un modelo vacío.
La familia completa contiene **10 modelos, 14 tablas y 58 registros**:
tipos de beneficios, información personal configurable, motivos de rechazo y
resúmenes. Esos maestros, sus XML IDs, FK, permisos y datos se deben preservar.

El auditor también conserva los hashes de las vistas sin exportar su XML,
acciones, selecciones, columnas, restricciones, aliases de grupos y conteos de
uso de tipos por contratos y liquidaciones. No exporta salarios, empleados,
fórmulas ni documentos. Ninguna liquidación se carga por ORM o se recalcula.

## Motor libre real identificado

En el pin OCA ya utilizado por la migración,
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`, existe
[`payroll_contract_advantages` 18.0.1.0.0](https://github.com/OCA/payroll/blob/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e/payroll_contract_advantages/__manifest__.py),
LGPL-3, dependiente de `hr_contract` y del motor OCA `payroll`.

Es un motor concreto de ventajas por contrato: plantillas con código, límites
y valor predeterminado; registros de ventajas con importe; y una integración
con la evaluación real de reglas a través de `current_contract.advantages`.
Véanse su [documentación](https://github.com/OCA/payroll/blob/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e/payroll_contract_advantages/README.rst),
[modelo de contrato](https://github.com/OCA/payroll/blob/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e/payroll_contract_advantages/models/hr_contract.py)
y [API de liquidación](https://github.com/OCA/payroll/blob/4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e/payroll_contract_advantages/models/hr_payslip.py).

Su identidad es `hr.contract.advantage` / `hr.contract.advantage.template`,
con tablas y ACL diferentes. El catálogo nativo de beneficios utiliza otros
campos y relaciones; sus 46 campos no se convierten en esas plantillas por
renombrar un comodelo. Tampoco equivale al configurador de paquetes y ofertas
descrito en la [documentación oficial de Odoo](https://www.odoo.com/documentation/saas-18.1/applications/hr/payroll.html#salary-package-configurator).
No se ha probado ni certificado aquí la equivalencia funcional.

## Decisión y siguiente implementación

La brecha continúa **bloqueada por identidad y API**, con alternativa libre
real para evaluar. El siguiente ensayo debe instalar el addon OCA fijado en
Community privada, calcular una ventaja real mediante un actor normal y
probar límites, permisos, contabilización y lectura de historia cerrada.
Después se podrá diseñar un puente que conserve el catálogo original y sus
relaciones, con contrato explícito para funciones aún no soportadas.

No crear tablas paralelas para sustituir maestros, modelos vacíos ni aliases
que retargeteen registros. No cambiar dependencias, cargar datos originales
sobre demo ni retirar Enterprise antes de una adopción integral preservada.
La ausencia actual de beneficios no certifica las 71 reglas ni resuelve el 31.

## Evidencia y reproducción

Herramienta versionada: `tools/community/audit_payroll_salary_benefits.py`.
Cinco pruebas puras verifican la transacción de solo lectura, el rechazo de
otras bases y DML, el protocolo completo y la exposición limitada de datos.
No representan pruebas funcionales de un motor de beneficios.

Evidencia privada, sin fuentes OEEL ni importes:
`/opt/steps-validation/community-payroll-schema-20261029/`.
`benefits-cerro-v2.json`, `benefits-sys-v2.json` y `benefits-contract.json`
conservan el contrato y sus hashes; las capturas anteriores permanecen intactas.

El inventario exacto de `78e5cde8` queda en `products-inventory.json` y
`products-inventory-delta.json`, archivos 0600. Sin cambios respecto del
inventario final de Período: Cerro **381/140/100**, Steps **310/123/19** y
SyS **332/142/17** (instalados/Enterprise/propios). El repo mantiene **126**
manifiestos propios y **30** fuera de Cerro. `steps_transport` sigue como
fuente recuperada e inactiva. Las fuentes privadas y sus huellas quedan en
la evidencia privada; su presencia no acredita adopción ni retiro Enterprise.
