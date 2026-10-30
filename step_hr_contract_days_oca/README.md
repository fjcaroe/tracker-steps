# Días contractuales T138 sobre Simple Digital y OCA

Puente del motor real, sin modelos, campos, tablas, XML IDs ni permisos nuevos.
`hr.leave.type.unpaid` y su relación `work_entry_type_id` ya pertenecen a los
módulos oficiales LGPL de Community. El complemento T138 mantiene su dependencia
en Simple Digital y su política aprobada de faltas, licencias, contratos parciales
y atrasos. Este puente se instala exclusivamente con el motor Community real.

La cadena API de entradas reales, proveedor AGPL y T138 produce los días, horas e
importes. El puente conserva los importes explícitos de esa cadena en los mismos
días tipados de OCA; no vuelve a elegir el divisor 30/31. También conserva el cero
explícito de atrasos/OUT. Las ausencias sin importe explícito conservan la relación
original de tipos no pagados, sin inferirla a partir del nombre o código.

OCA actualiza los días mediante la API real antes de calcular reglas. Por eso su
ruta conserva la admisión y transacción de T138, pero deja esa actualización al
motor en vez de ejecutar la corrección previa destinada al proveedor nativo.
Datos faltantes, líneas ambiguas, días/horas distintos del proveedor o entradas
de trabajo ausentes se rechazan; no se fabrica una asistencia alternativa.

Los cálculos operan con el actor normal y requieren acceso a todos los días,
entradas de trabajo y ausencias del período. Un lote con una liquidación pagada,
validada o bloqueada se rechaza antes de modificar el primer día. Los históricos
leen sus importes almacenados y no consultan la política actual de ausencias.

La adaptación de días no certifica las 71 reglas chilenas ni importa los 120
maestros originales. Las guardas de configuración, datos chilenos y contabilización
permanecen activas. La conversión integral y el vencimiento siguen pendientes.
