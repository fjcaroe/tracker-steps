# Cosecha, planificaciÃ³n y registros Community

## Contrato operacional

Cosecha 18.0.1.7.0 depende de `step_labor_operations_core` y de mÃ³dulos
oficiales Community. Conserva sus diez modelos de Cosecha/historial, tablas,
campos, acciones, maestros, ACL y reglas. No duplica cuadrillas ni contratos.
La planificaciÃ³n 18.0.1.1.0 usa los planes originales de GestiÃ³n y Costos.
Los registros agrÃ­colas 18.0.1.3.0 declaran explÃ­citamente su consumidor de
MovilizaciÃ³n: el panel de centros consulta `step.movi.cost.line`.
No se modifica el lÃ­mite de fechas de los dos Calendar de Productores.

Los correlativos de Cosecha conservan sus XML IDs, prefijos, compaÃ±Ã­as,
incrementos y rangos personalizados. La premigraciÃ³n protege los dos alias
antes de cargar XML `noupdate`; cambiar solo el XML no protege un alias legado
que todavÃ­a fuera actualizable. Los verificadores nativos omiten el tipo al
crear, lo escriben despuÃ©s y revierten las altas. La numeraciÃ³n automÃ¡tica se
prueba con secuencias de empresas desechables.

## Puente real de NÃ³mina y propietarios M2M

`step_labor_payroll_wizards` conserva los modelos reales
`hr.input.step.wizard`, `hr.entry.xls.wizard` y `success.message`, sus campos,
las vistas, acciones, menÃºs y los dos ACL originales. Depende de `hr_payroll`
y `hr_work_entry_contract_enterprise`; no entra en la instalaciÃ³n Community.
HR consume ese puente; Cosecha ya no importa una segunda definiciÃ³n idÃ©ntica
de esos modelos compartidos. Los alias histÃ³ricos de HR y Cosecha apuntan a
los mismos registros. No se inventa un permiso para el wizard de entradas,
que no tenÃ­a ACL propio en el paquete original.

`step_labor_reports` conserva los dos modelos transitorios operacionales,
sus campos, vistas, acciones y ACL originales. Los menÃºs originales siguen
en HR con sus ancestros/grupos; Community aÃ±ade dos accesos bajo su raÃ­z
laboral, que ya se desactiva cuando existe la raÃ­z legada. No se crea un atajo
activo en Cerro. Los informes conservan sus mÃ©todos XLSX y sus relaciones a
empleados y tarjas originales.

Los tres propietarios M2M pendientes se adoptan antes de reflejar las tablas,
sin cambiar ID, nombre ni modelo de `ir.model.relation`:

| RelaciÃ³n original | Propietario nuevo |
| --- | --- |
| `employee_wizard_rel` | `step_labor_reports` |
| `employee_process_rel` | `step_labor_reports` |
| `step_hr_payslip_rel` | `step_labor_payroll_wizards` |

La extracciÃ³n no certifica ni invoca la escritura masiva de entradas salariales.
El algoritmo legado aÃºn busca la primera liquidaciÃ³n por empleado sin resolver
explÃ­citamente el lote/estructura/estado seleccionado: necesita revisiÃ³n propia
antes de aceptarlo con un motor Community. El importador XLS legado tambiÃ©n
contiene un flujo APR ajeno a Cosecha; se preserva, no se ofrece como un nuevo
importador agrÃ­cola. No se recalculan ni editan liquidaciones pagadas.
El override bancario Boolean legado sigue en HR: no se puede desinstalar HR
como consecuencia de esta extracciÃ³n.

## Formatos de empaque compartidos

`step_agriculture_format_core` usa `product.packaging` y `stock.package.type`
nativos. Traslada solo dos capacidades de pallet, cuatro vistas y dos acciones
de ExportaciÃ³n, con sus IDs y alias `step_export.*`. Los campos `kg por caja`
y `cajas por pallet` ya pertenecen a Productores y conservan esa propiedad.
La clasificaciÃ³n `step_packaging_group` permanece en planificaciÃ³n, sin asignar
un grupo ficticio a los embalajes histÃ³ricos. No se crea otro maestro de envases.

El hook conserva las filas originales que enlazan acciones y vistas; solo crea
enlaces cuando la acciÃ³n aÃºn no los tiene. ExportaciÃ³n consume el nÃºcleo y
mantiene su resto de DTE/CAF/SII. El retiro de su dependencia desde planificaciÃ³n
no acredita la independencia de ExportaciÃ³n ni autoriza retirar sus mÃ³dulos.

## AceptaciÃ³n

`validate_agriculture_core.py --profile harvest` extiende el perfil laboral.
El mismo paquete contiene los puentes necesarios para actualizar Cerro; la
instalaciÃ³n pura excluye HR, ExportaciÃ³n y el puente Enterprise de wizards.
Solo las copias privadas reciben instalaciones/actualizaciones. Los resultados
aceptados, huellas, lÃ­mites y siguiente paso se registran en continuidad.
No hay publicaciÃ³n automÃ¡tica en Desarrollo/QA, refresco de QA-Cerro, cambio de
vencimiento ni retiro de Enterprise en producciÃ³n. `210233` sigue descontinuada.
