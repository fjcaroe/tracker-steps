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
Las dependencias efectivas de `amount` e `is_paid` son explícitas en los campos:
días, sueldo contractual, tipo usado, estructura de la liquidación y su relación
de tipos no pagados. Se excluye el antiguo camino global
`work_entry_type_id.unpaid_structure_ids`, que agenda días de B al editar sólo A.
No basta un decorador nuevo: Odoo combina decoradores heredados; el parámetro
real `depends` tiene precedencia y las pruebas verifican la lista efectiva del
registro. No se usa `modified()` manual ni se escribe un importe para simular
invalidación correcta. Un día real de borrador B debe conservar su fila completa
cuando A modifica su propia relación, con flush ejecutado por el actor A.

El lector privado de política obtiene por SQL todos los pares directamente
afectados, incluidos registros archivados, y exige permiso normal sobre sus
extremos y campos. Una escritura/copia/eliminación de estructura inspecciona sus
tipos; la operación equivalente de un tipo inspecciona todas sus estructuras.
No expande vecinos de vecinos: procesar A con un tipo global compartido no
requiere leer valores de una estructura B que la operación no modifica.
No permite que una restricción de registro o campo transforme una relación
efectivamente afectada oculta en un supuesto día pagado. Los cómputos almacenados restablecen
el entorno del UID original sin elevarlo, pues Odoo usa `compute_sudo=True`.
El setup valida sólo el país explícito de la estructura. Un país desconocido
queda almacenable y pendiente, incluso si OCA asignó una compañía por defecto:
ese default no prueba propiedad nativa. El contexto desconocido sólo se resuelve
al procesar con la compañía real de la liquidación; nunca se crea propietario.
Así se conserva el par demo F con dueño predeterminado US/tipo CL, pero su
procesamiento sigue bloqueado. No se presenta ese bootstrap como configuración
chilena original adoptada ni certificada.

En escrituras de ambos sentidos se comprueba antes la visibilidad completa de
los pares afectados, y después su alcance restante dentro de un savepoint. La validación previa no
exige que una relación antigua inválida ya esté corregida: permite quitar un
extremo visible incorrecto. Copia y eliminación también requieren visibilidad
de sus pares directamente afectados. Las copias conservan los extremos archivados aun con el contexto
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
borradores e IDs; workflow cerrado/asiento exacto; lados propietarios con pares ocultos; ACL de
campo incluso bajo cómputo privilegiado; y país/global/corrección de par legado.
Dos casos compartidos de referencia nativa prueban sólo contrato físico,
inverso ORM/SQL y pares archivados: no se infiere su fórmula ni se copia OEEL.

Siguen abiertos los maestros/reglas originales, restantes metadatos, seguridad
por rol, SyS, certificación contable/Previred/libro, DTE/CAF/SII y conversión
integral restaurable con cero Enterprise. Producción y QA-Cerro quedan intactos.
Calendar, Boolean bancario, 210233 y correlativos mantienen sus restricciones.
El 31 de octubre continúa en riesgo alto; este bloque no resuelve el vencimiento.
