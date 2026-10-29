# Analítica original y contabilización OCA

Aceptación de este bloque: [COMMUNITY_PROPIEDADES_NOMINA.md](COMMUNITY_PROPIEDADES_NOMINA.md),
pareja F y upgrade privado I; configuración original y conversión integral pendientes.

Este bloque conserva `hr.salary.rule.analytic_account_id` como propiedad JSONB
por empresa, nullable, `copy=False` y `ondelete=set null`, según metadata de la
referencia nativa. No cambia `account_debit`, `account_credit` ni la política
del diario. La extensión scalar de `hr.payslip.line.analytic_account_id` propia
de OCA permanece independiente: no se convierte su columna ni se reescriben
líneas históricas. La referencia nativa no contiene ese campo de línea.

## Proveedor y alcance funcional

Se auditó `payroll_account` OCA `18.0.1.0.6`, LGPL-3, del paquete aceptado D
de configuración original. Su `models/hr_payslip.py` tiene SHA-256
`0df0804e6f29610e1223011526c0caf8e05418b03aaad2475dd674900718a49d`.
Se mantiene su algoritmo real mediante `super`, incluida la prioridad
analítica contrato > regla, los asientos, impuestos, contrapartidas y redondeos.
Esa prioridad describe al proveedor OCA; no certifica equivalencia con todos
los casos del motor nativo.

Antes de contabilizar, el actor normal valida empresa, contratos, reglas,
campo analítico y cuenta efectiva. No se permite que `sudo`, una caché caliente
o una selección incompleta de líneas omita esas comprobaciones. La preparación
de débito y crédito verifica que `super` reciba y conserve la distribución
exacta del contrato o del slot de la regla en la empresa de la liquidación.
No cambia importes ni reconstruye distribuciones históricas.

Una propiedad SQL NULL sin default admite ausencia de distribución. Un slot
JSON explícitamente nulo también representa ausencia. La operación ORM Python
`False` limpia la relación mediante la normalización real del proveedor; un
booleano físico JSON no es un ID M2O válido y se rechaza antes de su lectura ORM.
Una propiedad poblada
sin slot de la empresa, un default implícito, un ID inválido, una cuenta oculta
o una cuenta de otra empresa bloquean el proceso antes de mutar la liquidación.
Las cuentas compartidas son válidas con permisos normales. La impresión y
lectura de liquidaciones cerradas no ejecutan estas guardas de procesamiento.

## Preparación física y cableado

`step_simpledigital_oca_base/analytic_storage.py` expone
`migrate_original_analytic_storage(cr)` para pre-init y pre-migración;
`prepare_original_analytic_storage(cr)` aplica exactamente la misma admisión.
Los hooks deben llamarlo antes de inicializar el campo JSON. El coordinador
cablea imports, versión, pre-init y la pre-migración de esa versión.

El helper no tiene bypass ni condiciona el producto al nombre de una base.
Exige el proveedor OCA real instalado, metadata y esquema compatibles y cero
Enterprise activo o pendiente, incluidos `to install`, `to upgrade` y `to remove`.
Los runners de ensayo mantienen por separado copia privada, respaldo y lease.
Este helper no autoriza quitar Enterprise en producción ni sustituye la
admisión integral de identidad y maestros previa a una conversión real.

La conversión scalar CE se realiza bajo bloqueo y savepoint. Valida todas las
filas antes del DDL. Conserva SQL NULL exactamente y sólo convierte un ID
scalar no nulo cuando la regla ya tiene una empresa explícita compatible con
la cuenta real. Una regla global con valor scalar aborta: no se elige dueño a
partir de la cuenta, estructura, usuario o empresa por defecto. Un JSON ya
existente se valida sin reescribirlo. Se retira únicamente el FK scalar real
`set null` hacia la cuenta analítica, que no es aplicable a un JSON; cualquier
otra restricción inesperada aborta. Se cambia la representación de la propiedad
del maestro ya existente; no se crean ni reasignan maestros/compañías, salarios, números, líneas, importes o
secuencias.

## Pruebas del bloque

`tests/test_original_analytic.py` incorpora nueve casos funcionales con roles,
contratos, reglas, cuentas y posting OCA reales, y cuatro casos de DDL PostgreSQL
sobre fixtures temporales eliminados por rollback. Cubren propiedad por empresa,
prioridad del contrato, cuentas compartidas, NULL/clear, defaults no aprobados,
ACL de fila/campo, intentos con sudo, líneas ocultas, rollback de asignaciones,
historia cerrada y migración ambigua/idempotente. Las secuencias de negocio
originales no se usan: liquidaciones y diarios son privados y sus números se
aportan explícitamente. La aceptación pertenece a la pareja exacta que ejecute
el coordinador; sintaxis o estos archivos por sí solos no acreditan conversión.
