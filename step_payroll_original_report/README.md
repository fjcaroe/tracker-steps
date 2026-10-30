# Ruta original de impresión — candidato 18.0.1.0.1

Este addon opcional depende de los proveedores reales Simple Digital y contratos.
No modifica Base/API, crea acciones, declara un renderer `hr_payroll`, añade
aliases de ese namespace ni reserva/renumera un ID. La coadopción de la acción
original y de sus maestros/FK sigue pendiente del bootstrap; este bloque sólo
resuelve su ruta de impresión cuando la acción correcta ya existe.

En Community, una acción real de `hr.payslip` cuyo `report_name` sea exactamente
`hr_payroll.report_payslip_lang` puede imprimir con el StoredPayslipReport y el
template `step_simpledigital_oca_base.report_payslip` ya probados. Se comprueba
el origen del renderer registrado. En nativo, sin ese backend instalado, el
addon delega la ruta intacta; no importa su código ni reemplaza un modelo nativo.

El ID, nombre, configuración, grupos y FK de la acción se conservan: no se escribe
en ella. La autorización usa el UID real y sus grupos, sin confiar en actor o
valores suministrados por data/context. Admite sólo IDs existentes, positivos,
únicos y explícitos. El renderer almacenado autoriza todos los documentos,
líneas, días y campos con el actor normal antes de leer importes. Se rechazan
configuraciones `attachment`/`attachment_use`; no se evalúa ni recupera una caché.
La guarda PDF se ejecuta en `_pre_render_qweb_pdf`, antes de la preparación
oficial que busca adjuntos. HTML usa exclusivamente el payload almacenado real.

Se mantienen NULL, cero, negativos y la negativa ante NET ambiguo. No se calculan
reglas, reconstruyen importes ni consultan remuneraciones actuales para sustituir
históricos. La estructura puede estar archivada y conservar su presentación.
No se afirma equivalencia legal ni certificación chilena por generar un PDF.

La preparación PDF de esta ruta aplica tipografía explícita sólo al bloque
corporativo `company_address` de una cabecera no ambigua. Conserva texto,
atributos semánticos, logo, cuerpo, pie y argumentos de formato; no escribe
acción, empresa ni FK. En los replays privados el HTML original estaba completo,
pero Qt omitía el texto corporativo. Cambiar espaciado, demora, bloques/tabla o
recorte no lo resolvió; tipografía explícita lo mostró en las seis páginas de
tres repeticiones, sin solapamiento. No se atribuye la causa exclusivamente a
font-face: se fijan conjuntamente fuente, tamaño, altura de línea y visibilidad.
Las otras acciones y el proveedor nativo conservan su preparación intacta.
La pareja final debe volver a comprobar las tres impresiones del paquete exacto.

Casos propuestos: siete TransactionCase CE, un HttpCase CE con PDF real y un caso
nativo de modo inerte/identidad, sin imprimir sus pagadas. Los fixtures CE usan
una acción privada ordinaria generada por ORM, sin simular el ID de la original.
El caso HTTP utiliza un XMLID privado propio y los assets reales del runtime,
sin alterar ninguna acción compartida. No importa fixtures CE en el registro
nativo. Selectores para evitar contar omisiones como casos funcionales:

- CE: `/step_payroll_original_report:OriginalPayrollReportRouteCase,/step_payroll_original_report:OriginalPayrollReportPdfCase` — ocho casos.
- Nativo: `/step_payroll_original_report:NativeOriginalPayrollReportRouteCase` — un caso.

El caso HTTP conserva HTML final, fragmentos, formato, argumentos sin cookies,
assets originales y tres PDF bajo el `data_dir` privado. Su recibo sella bytes y
hash de cada pipeline. `verify_original_report_headers.py` realiza la revisión
offline por página con PyMuPDF; `replay_original_report_pdf.py` permite contrastes
estáticos aislados sin Odoo ni SQL. Un replay diagnóstico nunca acredita por sí
solo nómina, adopción de la acción 462, layout productivo o validez legal.

AST no constituye aceptación. El coordinador debe comprobar el paquete exacto
en ambos entornos y conservar sus evidencias privadas antes de integrar.
