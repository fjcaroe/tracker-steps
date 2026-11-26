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
