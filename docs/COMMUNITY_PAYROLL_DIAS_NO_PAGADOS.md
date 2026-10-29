# Relación original de días no pagados

Bloque preparado junto a la obligatoriedad original desde `c12c1f6e`.
**Aceptación del paquete exacto pendiente del coordinador.**

`hr.payroll.structure.unpaid_work_entry_type_ids` y
`hr.work.entry.type.unpaid_structure_ids` comparten la tabla existente
`hr_payroll_structure_hr_work_entry_type_rel`. Se conservan las columnas
`hr_payroll_structure_id` y `hr_work_entry_type_id` en sentidos inversos, campos
almacenados/editables y `copy=True`. No hay una tabla paralela, DDL de backfill,
reasignación de IDs ni importación de pares originales. La referencia nativa F
tiene dos pares y CE uno; adoptar los pares originales sigue requiriendo cerrar
identidad y referencias de la configuración fuente.

## Política efectiva y permisos

La estructura permite administrar la misma relación que ya usa la fórmula real
de Simple Digital–OCA: un día mensual pagado usa `wage/30 * number_of_days`, y una
relación de tipo/estructura no pagada produce importe cero e `is_paid=False`.
No se introduce otra fórmula ni una escritura manual de importes almacenados.
La invalidación inversa M2M y la cola de cómputo ORM deben demostrar el cambio en
borradores durante la aceptación; no se declara probado por leer el código.

El lector privado de política obtiene IDs completos del componente M2M por SQL,
incluidos registros archivados, y exige permiso normal sobre todos los extremos
y campos. No permite que una restricción de registro o campo transforme una
relación oculta en un supuesto día pagado. Los cómputos almacenados restablecen
el entorno del UID original sin elevarlo, pues Odoo usa `compute_sudo=True`.
La pertenencia de país se valida con el país explícito de la estructura o de su
compañía real. Para una estructura global sin país, el contexto sólo se resuelve
al procesar con la compañía real de la liquidación; nunca se crea propietario.

En escrituras de ambos sentidos se comprueba antes la visibilidad completa,
y después el alcance restante dentro de un savepoint. La validación previa no
exige que una relación antigua inválida ya esté corregida: permite quitar un
extremo visible incorrecto. Copia y eliminación también requieren visibilidad
del componente. Las copias conservan los extremos archivados aun con el contexto
de lectura predeterminado, sin cambiar el resto de la política estándar de copia.

La guarda de cálculo/contabilización inspecciona también los IDs completos de
días almacenados. Un día que necesita cálculo de pago debe tener su estructura
explícita; no se usa la ausencia de estructura como supuesto pagado. No se
asignan maestros automáticamente.

## Histórico cerrado

`_compute_payment` añade controles a borradores y delega la fórmula al proveedor
existente. Las filas protegidas pasan a su restauración de caché desde SQL sin
revalidar una política actual que pudo cambiar u ocultarse. No se recalculan
pagadas/validadas al leer, ni se alteran sus importes o `is_paid`.

La prueba privada cierra mediante el workflow real OCA y genera un asiento
publicado. Después cambia sueldo, relación no pagada, archivo y visibilidad del
tipo. Exige igualdad completa de cabecera, días, líneas salariales, asiento y
apuntes originales de ese caso sintético. No marca una liquidación comercial
como pagada ni interpreta esa prueba como certificación de la nómina de SyS.

## Wiring y pruebas previstas

El coordinador debe importar `models/original_unpaid.py` en StepBase, los dos
wrappers de pruebas y actualizar versión/conteos. No hace falta una migración
que toque pares existentes: la nueva relación es el inverso del campo existente.

Siete casos CE reales cubren metadata/inverso/pares; archivo/copia; recálculo de
borradores e IDs; workflow cerrado/asiento exacto; componentes ocultos; ACL de
campo incluso bajo cómputo privilegiado; y país/global/corrección de par legado.
Dos casos compartidos de referencia nativa prueban sólo contrato físico,
inverso ORM/SQL y pares archivados: no se infiere su fórmula ni se copia OEEL.

Siguen abiertos los maestros/reglas originales, restantes metadatos, seguridad
por rol, SyS, certificación contable/Previred/libro, DTE/CAF/SII y conversión
integral restaurable con cero Enterprise. Producción y QA-Cerro quedan intactos.
Calendar, Boolean bancario, 210233 y correlativos mantienen sus restricciones.
El 31 de octubre continúa en riesgo alto; este bloque no resuelve el vencimiento.
