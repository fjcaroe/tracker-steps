# Cosecha, planificación y registros Community

## Contrato operacional

Cosecha 18.0.1.8.0 depende de `step_labor_operations_core` y de módulos
oficiales Community. Conserva sus diez modelos de Cosecha/historial, tablas,
campos, acciones, maestros, ACL y reglas. No duplica cuadrillas ni contratos. La bandera original
`stock.picking.cosecha` pasa de HR a Cosecha con el mismo campo, columna, ID y
alias antiguo. La recepción y el dashboard leen esa bandera también en
Community; el hook y las migraciones rechazan conflictos de identidad/tipo.
La prueba de Inventario usa un operador desechable sin `su`, crea la recepción
de 20 kg, conserva producto/UdM/compañía, la valida y rechaza duplicados.
La planificación 18.0.1.1.0 usa los planes originales de Gestión y Costos.
Los registros agrícolas 18.0.1.3.0 declaran explícitamente su consumidor de
Movilización: el panel de centros consulta `step.movi.cost.line`.
Declaran también `hr_hourly_cost` oficial Community: las dos relaciones a
`hr.employee.hourly_cost` mantienen el campo monetario original, con su grupo
nativo de RRHH. No se deriva ese valor desde una liquidación ni se crea otro
campo de costo.
No se modifica el límite de fechas de los dos Calendar de Productores.

Los correlativos de Cosecha conservan sus XML IDs, prefijos, compañías,
incrementos y rangos personalizados. La premigración protege los dos alias
antes de cargar XML `noupdate`; cambiar solo el XML no protege un alias legado
que todavía fuera actualizable. Los verificadores nativos proporcionan el tipo obligatorio mediante
`default_type_tarea` del contexto, sin ponerlo en los valores explícitos que
activan el correlativo del override de `create`, y revierten las altas. La numeración automática se
prueba con secuencias de empresas desechables.

## Puente real de Nómina y propietarios M2M

`step_labor_payroll_wizards` conserva los modelos reales
`hr.input.step.wizard`, `hr.entry.xls.wizard` y `success.message`, sus campos,
las vistas, acciones, menús y los dos ACL originales. Depende de `hr_payroll`
y `hr_work_entry_contract_enterprise`; no entra en la instalación Community.
HR consume ese puente; Cosecha ya no importa una segunda definición idéntica
de esos modelos compartidos. Los alias históricos de HR y Cosecha apuntan a
los mismos registros. No se inventa un permiso para el wizard de entradas,
que no tenía ACL propio en el paquete original.

`step_labor_reports` conserva los dos modelos transitorios operacionales,
sus campos, vistas, acciones y ACL originales. Los menús originales siguen
en HR con sus ancestros/grupos; Community añade dos accesos bajo su raíz
laboral, que ya se desactiva cuando existe la raíz legada. No se crea un atajo
activo en Cerro. Los informes conservan sus métodos XLSX y sus relaciones a
empleados y tarjas originales. Se corrige la visibilidad de entrada/resultado
para usar el archivo generado: el nombre calculado ya existía antes de generar
y ocultaba las fechas al abrir. El informe contratista recupera un botón que
llama a su método original; no recibe permisos adicionales.

Los tres propietarios M2M pendientes se adoptan antes de reflejar las tablas,
sin cambiar ID, nombre ni modelo de `ir.model.relation`:

| Relación original | Propietario nuevo |
| --- | --- |
| `employee_wizard_rel` | `step_labor_reports` |
| `employee_process_rel` | `step_labor_reports` |
| `step_hr_payslip_rel` | `step_labor_payroll_wizards` |

La extracción no certifica ni invoca la escritura masiva de entradas salariales.
El algoritmo legado aún busca la primera liquidación por empleado sin resolver
explícitamente el lote/estructura/estado seleccionado: necesita revisión propia
antes de aceptarlo con un motor Community. El importador XLS legado también
contiene un flujo APR ajeno a Cosecha; se preserva, no se ofrece como un nuevo
importador agrícola. No se recalculan ni editan liquidaciones pagadas.
El override bancario Boolean legado sigue en HR: no se puede desinstalar HR
como consecuencia de esta extracción.

## Formatos de empaque compartidos

`step_agriculture_format_core` usa `product.packaging` y `stock.package.type`
nativos. Traslada solo dos capacidades de pallet, cuatro vistas y dos acciones
de Exportación, con sus IDs y alias `step_export.*`. Los campos `kg por caja`
y `cajas por pallet` ya pertenecen a Productores y conservan esa propiedad.
La clasificación `step_packaging_group` permanece en planificación, sin asignar
un grupo ficticio a los embalajes históricos. No se crea otro maestro de envases.

El hook conserva las filas originales que enlazan acciones y vistas; solo crea
enlaces cuando la acción aún no los tiene. Exportación consume el núcleo y
mantiene su resto de DTE/CAF/SII. El retiro de su dependencia desde planificación
no acredita la independencia de Exportación ni autoriza retirar sus módulos.

## Aceptación

`validate_agriculture_core.py --profile harvest` extiende el perfil laboral.
El mismo paquete contiene los puentes necesarios para actualizar Cerro; la
instalación pura excluye HR, Exportación y el puente Enterprise de wizards.
Solo las copias privadas reciben instalaciones/actualizaciones. Los resultados
aceptados, huellas, límites y siguiente paso se registran en continuidad.
No hay publicación automática en Desarrollo/QA, refresco de QA-Cerro, cambio de
vencimiento ni retiro de Enterprise en producción. `210233` sigue descontinuada.

La comprobación de correlativos separa el upgrade de los fixtures funcionales.
Primero actualiza la copia sin pruebas y exige conservar exactamente valores,
parámetros y contadores PostgreSQL existentes. Después ejecuta todas las pruebas
del paquete. Los `nextval` de secuencias estándar no se revierten con savepoints:
se conserva una evidencia separada de su consumo por fixtures en la copia,
se exige progresión nativa y nunca se resetean números para ocultarla.
`ir.sequence` y sus rangos conservan todos sus valores de configuración;
solo se excluyen `write_uid`/`write_date` de esos dos registros de metadatos.
Los documentos de negocio, históricos, saldos y los demás contratos se comparan
también al terminar las pruebas. Los IDs originales de `ir.model.data` se
comparan completos junto con nombre, módulo, modelo y destino; la protección
intencional `noupdate` no cambia esas identidades.

La contabilización de Cosecha usa directamente las cuentas analíticas ya
seleccionadas en `registry.cost_id` y `product.template.actividad_id`.
El código legado intentaba atravesar un `cost_id` inexistente en esas dos
relaciones, confundiéndolas con `step.centro.costo` y `step.actividad`.
No se convierten IDs ni se reconstruyen maestros. La prueba con empresa y
cuentas desechables recorre aprobación, costeo y generación del asiento en
borrador de 60, con distribución de temporada/centro/actividad y bloqueo de
segunda contabilización. No publica asientos ni recalcula registros históricos.

La recepción sincroniza `cos_recibida` al terminar/cancelar la operación nativa
de Inventario. El estado de `stock.picking` es calculado y no garantiza pasar
por `write({'state': ...})`, por lo que ese override legado no marcaba siempre
la recepción validada. Los hooks actúan solamente sobre el registro vinculado
a la recepción actual durante la transición del operador: no hay recomputación
de recepciones anteriores ni cambios de históricos durante el upgrade.

Las raíces Community de maestros (núcleo 18.0.1.1.1) y Tarjas/Cuadrillas
(18.0.1.0.1) reevalúan su estado activo en cada carga XML. Permanecen ocultas
cuando existe la raíz legada de HR, incluso después de un segundo upgrade;
no se depende solamente de `post_init_hook`. La regresión vuelve a cargar ambos
XML dos veces y comprueba la frontera de menús. No modifica grupos de usuarios.
