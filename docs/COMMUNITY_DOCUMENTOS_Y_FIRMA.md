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

SyS tiene dos usuarios internos activos que pueden usar Firma y emitir
documentos laborales. En Cerro hay once usuarios de Firma, ocho son
administradores de Firma y dos tienen también el permiso de emisión laboral.
Steps carece de emisores asignados en esta copia. Los conteos excluyen a
la cuenta técnica del sistema.

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
obligatoria y fallaba en la restricción SQL. El núcleo 18.0.2.1.3 conserva
las referencias históricas y el acceso al PDF. El complemento OCA habilita
el botón **Preparar firma** para los usuarios de ese proveedor. Las pruebas
ejercitan borradores y cancelaciones con cero destinatarios. El envío,
la firma de una persona y la recepción del ejemplar firmado quedan pendientes.

## Adopción en la copia Community de Cerro

En una derivada privada del control U40D se restauraron los 677 objetos
referenciados. El núcleo y el complemento de firma OCA quedaron instalados
con 148 módulos activos y cero módulos Enterprise. Los 848 identificadores
externos previos del núcleo conservaron su ID de metadato, modelo y registro.
El núcleo incorporó un identificador nuevo. Los 48 registros de la biblioteca
y sus 32 permisos explícitos mantuvieron sus relaciones.

La primera instalación encontró tres fechas del calendario legal ya cargadas.
Sus cinco valores coincidían con los del paquete distribuido. La versión
18.0.2.1.3 reconoce esa recarga idéntica y conserva las tres filas tal como
están. Las modificaciones efectivas continúan sujetas al permiso técnico.
La comparación de las columnas originales de los doce modelos persistentes
del núcleo y de los vínculos contractuales confirmó los mismos datos en las
trece tablas. Incluye las tres transiciones y las 21 causales de término.

El usuario interno emitió un contrato de ensayo en esa copia desde el menú
de emisión masiva. En la transacción se prepararon un contrato, una ubicación
y una plantilla. El PDF incluyó la ubicación relacionada con el contrato.
El permiso de lectura y la descarga por el controlador web permitieron obtener
los mismos bytes que el original, con denegación al usuario público. Se
verificaron los vínculos en el historial laboral y la preparación, reapertura
y cancelación de una misma solicitud OCA sin destinatarios.

El mismo paquete se probó en dos copias nativas de SyS con un emisor original.
En una se ejercitó la firma manual mediante descarga. En la otra se le asignó
durante el ensayo el permiso OCA de usuario de sus propios documentos.
La asignación se revirtió junto con el contrato y el borrador.
