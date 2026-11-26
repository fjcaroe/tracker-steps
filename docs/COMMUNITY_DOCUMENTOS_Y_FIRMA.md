# Documentos laborales, biblioteca y firma

Las copias privadas de los tres productos del 26 de noviembre de 2026 conservan
el adjunto y la jerarquía de la biblioteca de Documentos. El recuento incluye
archivados, carpetas y enlaces.

| Producto | Biblioteca | Binarios / carpetas / URL | Adjuntos de archivo en filestore | Permisos explícitos |
| --- | ---: | ---: | ---: | ---: |
| SyS | 1.430 | 1.319 / 110 / 1 | 1.317 | 3.955 |
| Steps | 98 | 81 / 16 / 1 | 81 | 87 |
| Cerro El Plomo | 48 | 28 / 19 / 1 | 28 | 32 |

Todos los adjuntos, propietarios, compañías y permisos explícitos referenciados
existen. En Cerro, uno de los 38 registros con padre apunta a un documento que
no es carpeta. La anomalía ya está en la referencia nativa restaurada.

`tools/community/audit_document_relations.py` obtiene estas cantidades con una
transacción SQL de solo lectura. Compara mediante SHA-256 los IDs de documentos,
relaciones, visibilidad y permisos explícitos. Las derivadas de SyS U40A y U40C
y el par de Cerro U40D mantienen esas relaciones y cantidades de sus controles.
La comparación excluye el contenido de los archivos, las direcciones URL y el
valor de los tokens de acceso.

Los tres productos tienen cero documentos laborales emitidos en
`hr.labor.document`. SyS tiene 238 contratos y dos plantillas laborales validadas.
Cerro y Steps tienen sus tablas de contratos y plantillas vacías. En SyS y Cerro
está instalado el proveedor de Firma y existe una plantilla de firma en cada
base, con cero solicitudes, firmantes y elementos de firma. Steps carece del
proveedor instalado.

La versión original de `step_hr_contract_lifecycle` es 18.0.2.0.1 en los tres
productos. Su PDF laboral se guarda en `ir.attachment`, con vínculos al
documento, contrato, trabajador y plantilla. En el grafo de dependencias
siguen presentes `hr_payroll` y `hr_work_entry_contract_enterprise`, utilizados
por la navegación de nómina y la relación de los finiquitos con liquidaciones.

## Recorrido de los usuarios

En la biblioteca nativa, el usuario interno de Steps pudo acceder a 90 documentos
activos y navegar por una carpeta con 62 entradas. El de Cerro pudo acceder a 45
y navegar por una carpeta con 26. En SyS el usuario administrador pudo acceder
a 1.395 y navegar por una carpeta con 1.240. En los tres casos se verificaron
menú, formulario, adjunto y permiso del lector en una transacción de solo
lectura. La prueba está en `tools/community/probe_restored_document_library.py`.

En SyS, los 86 contratos abiertos de la compañía de las plantillas carecían
de modalidad y de plantilla asignadas. En la transacción de ensayo se escogió
un contrato y se le asignaron una modalidad y una plantilla validada. El
asistente original falló al intentar leer un campo exclusivo del adaptador
agrícola en SimpleDigital. El núcleo usa ahora la ubicación contractual y el
adaptador agrícola conserva el nombre del fundo original cuando está asignado.

El formulario permite descargar el PDF con los permisos del documento y del
adjunto, registrar el motivo y cancelar. En SyS se verificaron la igualdad
de los bytes del PDF descargado con el original, su SHA-256 y la denegación
del usuario público. El historial del empleado y el del contrato llevan al
mismo archivo emitido.

## Preparación de firma

El proveedor OCA probado es `sign_oca` 18.0.1.4.4, AGPL-3, revisión
`6163139a41710e4192140ad42b2f4812f75b67b0`. El complemento opcional
`step_hr_contract_lifecycle_sign_oca` crea un borrador para el PDF emitido
y comprueba su SHA-256. Conserva una relación con la solicitud y la compañía.
Al abrirlo dos veces se reutiliza el borrador. Al cancelar el documento también
se cancela el borrador. El usuario de Firma debe resolver primero una solicitud
que ya esté enviada o firmada. El estado de Firma se puede consultar en el
formulario laboral. [Código del proveedor probado](https://github.com/OCA/sign/tree/6163139a41710e4192140ad42b2f4812f75b67b0/sign_oca)

La acción previa intentaba crear una solicitud de Enterprise sin la plantilla
obligatoria y fallaba en la restricción SQL. El núcleo 18.0.2.1.2 conserva
las referencias históricas y el acceso al PDF. El complemento OCA habilita
el botón **Preparar firma** para los usuarios de ese proveedor. Las pruebas
ejercitan borradores y cancelaciones con cero destinatarios. El envío,
la firma de una persona y la recepción del ejemplar firmado quedan pendientes.
