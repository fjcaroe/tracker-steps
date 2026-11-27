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
La primera comparación cubrió las relaciones. La prueba posterior U41L calcula
además una huella de todas las columnas originales, incluidos URL y tokens, y
una huella del vínculo y almacenamiento de cada adjunto. Los valores sensibles
permanecen dentro de PostgreSQL.

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

## Biblioteca histórica interna de SyS

En la copia privada U41L, `step_document_library` 18.0.1.0.4 abre los
registros de `documents.document` y `documents.access` en sus tablas
originales. El menú histórico conserva su identificador y sus grupos. El
formulario permite navegar por carpetas, abrir el archivo o la URL y gestionar
el permiso individual de una cuenta interna. Las visitas previas se conservan
al retirar un permiso. La operación no envía notificaciones.

El programa de captura registra el resultado de la búsqueda original por
usuario y combinación de compañías. El ensayo Community compara los IDs
visibles y sus niveles de lectura y edición, incluyendo archivados. Un segundo
catálogo guarda la huella del marcador que produce Odoo para cada registro.
Su adopción exige que coincidan los originales y todos los IDs y rechaza
conflictos. La repetición en SyS produjo cero escrituras.

| Comprobación en SyS U41L | Resultado |
| --- | ---: |
| Documentos y marcadores originales | 1.430 |
| Permisos individuales preexistentes | 3.955 |
| Usuarios internos originales | 2 |
| Contextos de usuario y compañía, incluido el usuario público | 59 |
| Comparaciones de permiso por registro | 84.370 |
| Objetos restaurados del filestore completo | 2.679 |
| Módulos instalados / Enterprise | 187 / 0 |

Un editor recorrió el menú original y sus carpetas hasta un archivo TXT
histórico restringido. El controlador normal de descargas devolvió los bytes
correspondientes al tamaño y SHA-1 existentes. Tras el permiso de lectura,
el segundo usuario abrió ese mismo archivo y obtuvo el mismo SHA-256. Su
intento de gestionar accesos fue denegado. La repetición de la concesión
conservó la misma fila y su retirada restituyó el alcance anterior. El ensayo
comprobó también el marcador autenticado y la acción de la URL original,
sin visitar su destino. Después del rollback volvieron a coincidir la matriz
de permisos, las huellas y las 859 secuencias.


### Biblioteca interna de Cerro El Plomo

U41L conserva los 48 documentos, los 48 marcadores y las 32 filas de acceso
de la biblioteca nativa. Las identidades y las huellas de los registros
originales coinciden en el control nativo, la semilla Community y la derivada
ensayada. La segunda adopción de marcadores escribió cero filas.

| Comprobación en Cerro U41L | Resultado |
| --- | ---: |
| Usuarios internos originales | 15 |
| Contextos de usuario y compañía, incluido el usuario público | 65 |
| Comparaciones de permiso por registro | 3.120 |
| Objetos del filestore restaurado | 677 |
| Módulos instalados / Enterprise | 148 / 0 |

El usuario original recorrió el menú, carpeta y formulario y descargó un TXT
restringido. El destinatario comprobó el mismo contenido después de la
concesión. La repetición mantuvo la fila del permiso, la revocación restituyó
el acceso anterior y el usuario público recibió la denegación. También se
abrieron el marcador autenticado y la acción que conserva la URL original.
Tras el rollback coincidieron la matriz, las huellas históricas y las 1.247
secuencias.

El directorio de contactos original usa el inverso de los fundos. La derivada
adoptó los proveedores libres de agricultura, directorio y fundos compartidos.
El paquete `d20e40fe40f8e92687978e898ff47f3578bc668f021ee0bd697a843ab3cfc83b`
preservó 53 fundos, 95 asignaciones a compañías, cuatro reglas, quince
permisos y seis identidades originales. La revisión de cierre contrastó las
8.370 restricciones de la semilla, incluidas las tres columnas de la
unicidad histórica de estimaciones. El recibo del flujo se guarda en
`~/.codex/local-artifacts/community-resume-20261125/U30/u41l-cerro-internal-proof.json`.


### Referencias externas de archivos en SyS

La copia estricta del portal U41P tiene 188 módulos activos, todos libres.
Cada uno de los 1.430 registros de la biblioteca conserva la huella de su
referencia pública calculada por el sistema original. La adopción verifica
primero la identidad y el token almacenado de cada documento. El segundo
ensayo de adopción escribió cero filas.

Para los 1.319 archivos binarios de la biblioteca se comparó por ID la decisión
de acceso mediante referencia válida en el controlador nativo y en Community.
El acceso público coincidió para los 38 archivos permitidos y los 1.281
denegados. La comprobación interceptó el flujo de bytes en el controlador
nativo después de la decisión de acceso y devolvió sólo la identidad. La
prueba de permisos no abrió contenido histórico. Después de la transacción
coincidían las filas de documentos y permisos. El recibo privado está en
`~/.codex/local-artifacts/community-resume-20261125/U30/u41p-historical-public-scope.json`.

La prueba HTTP nativa usa dos cuentas de portal temporales con su propia
contraseña y un archivo de texto sintético. Solamente el destinatario designado
pudo descargarlo durante la concesión individual. Al habilitar la lectura
mediante enlace, el destinatario, la otra cuenta y el usuario anónimo
obtuvieron los mismos bytes. Al retirar el acceso por enlace volvió la
denegación al anónimo. Para cuentas autenticadas, la ruta de la ficha puede
devolver una pantalla con HTTP 200 aunque la descarga del archivo esté
denegada. La prueba verifica ambas respuestas.

### Aceptación del portal de archivos en SyS, versión 18.0.1.0.2

La derivada Community U41PA completó 72 solicitudes HTTP contra el mismo
archivo sintético que la referencia nativa. Se abrieron sesiones con contraseña
para el destinatario y una segunda cuenta temporal de portal. Un tercer cliente
visitó las mismas rutas como anónimo. Se verificaron seis estados de acceso en
cuatro rutas por cliente.

| Estado del archivo | Cliente que recibió los bytes exactos |
| --- | --- |
| Referencia sin emitir | Ninguno |
| Archivo restringido | Ninguno |
| Permiso individual de lectura | Destinatario |
| Permiso individual revocado | Ninguno |
| Lectura habilitada mediante enlace | Los tres |
| Lectura mediante enlace revocada | Ninguno |

La ficha, la descarga y los dos marcadores históricos coincidieron con la
referencia en las 72 solicitudes. El primer marcador respondió con HTTP 301
hacia el segundo y éste con HTTP 307 hacia la ficha. En las fichas denegadas de
las cuentas autenticadas se verificó además que el nombre del archivo quedara
oculto. La consulta a los 1.319 binarios históricos volvió a dar 38 permitidos
y 1.281 denegados, con cero diferencias por identidad.

El cotejo con U41P conservó las 1.430 fichas, los 3.955 registros de acceso y
los permisos originales de sus siete cuentas, junto con 40 protecciones de
base de datos. El ensayo completó la reversión de los datos temporales y las
colas de correo conservaron sus cifras. U41PA arrancó con 188 módulos libres.

El archivo instalado en U41P y U41PA tiene SHA-256
`12fb428e5abd6e7a26e74bd41d1ef2645d604c323aea17a4dea82a6443550cfe`.
Los recibos privados de las solicitudes y los permisos se guardan en
`~/.codex/local-artifacts/community-resume-20261125/U30/u41pa-portal-file-final.json`
y `u41p-historical-public-scope-final.json` en el mismo directorio.
