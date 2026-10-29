# CAF: preflight de identidad y almacenamiento — 29-10-2026

Base canónica `5d827f9e`, rama propia `codex/community-caf-storage-20261029`.
Continúa el núcleo criptográfico de `COMMUNITY_CAF_CORE.md`. No instala un
reemplazo de `l10n_cl_edi`, no cambia dependencias y no asigna folios.

## Bloque implementado y comprobado

`tools/community/caf_storage_preflight.py` inspecciona una copia privada existente
en una única transacción PostgreSQL REPEATABLE READ READ ONLY. No importa Odoo,
no ejecuta computes, no lee cuerpos OEEL y no consulta contenido de CAF,
certificados o llaves. Rechaza los nombres de producción y QA-Cerro antes de
conectar. Los resultados privados se crean exclusivamente fuera del checkout.

Las 22 secciones incluyen identidad del modelo; campos, tipos y relaciones;
columnas físicas; XML IDs y selecciones; restricciones/FK; permisos y sus grupos
originales; regla multiempresa; hashes de arquitectura de vistas; acciones y
sus vínculos; metadata agregada de CAF/adjuntos; estado del contador de IDs;
campos y restricciones de la frontera de documentos. Las huellas de filas son
solo de metadata: no leen ni acreditan integridad de los binarios.

El preflight verifica las correspondencias del modelo/campo/selección con sus
XML IDs, los tipos físicos y su nulabilidad, la política ON DELETE original,
el constraint de filename, grupos/ACL y dominio global exactos. Con `--baseline`
compara todas las secciones sin excepciones ni restaurar secuencias. Reporta
por separado `metadata_contract_valid`, `preserved`, `adoption_ready` y
`folio_allocation_ready`. Los dos últimos permanecen false deliberadamente:
la metadata no demuestra el comportamiento del proveedor ni la concurrencia.

## Contrato nativo observado

Las copias de Cerro M y SyS Storage B conservan el mismo esquema lógico, con
IDs específicos de cada producto:

- Modelo `l10n_cl.dte.caf`, tabla `l10n_cl_dte_caf`, 14 campos y 12 columnas.
  El campo `display_name` no está almacenado; `caf_file` es binary/store pero
  carece de columna propia. La vía física pendiente de confirmar en runtime es
  `ir.attachment` con `res_model`/`res_field` originales. No crear una columna
  bytea nueva ni otra tabla para sustituir ese almacenamiento.
- Metadatos propios del CAF: `filename`, `issued_date`, `start_nb`, `final_nb`,
  `status`, `company_id`, `l10n_latam_document_type_id` y auditoría original.
  Se conservan los 25 XML IDs, incluidas acciones y constraint.
- Los estados originales son `in_use` y `spent`. Hay seis restricciones SQL:
  PK, `UNIQUE(filename)` y cuatro FK ON DELETE SET NULL. La relación inversa
  original es `l10n_latam.document.type.l10n_cl_dte_caf_ids` mediante
  `l10n_latam_document_type_id`.
- Dos ACL CRUD corresponden a los grupos originales `account.group_account_manager`
  y `stock.group_stock_manager`, con namespaces `l10n_cl_edi` y
  `l10n_cl_edi_stock`. La regla global activa conserva literalmente
  `[('company_id', 'in', company_ids + [False])]`; no endurecer o ampliar ese
  dominio silenciosamente al adoptar históricos. Hay dos vistas y dos acciones.
- El contador `l10n_cl_dte_caf_id_seq` genera IDs del maestro, no folios fiscales.
  La tabla CAF no contiene un siguiente folio ni una reserva persistida.
  Account Move y Stock Picking conservan sus propios identificadores/campos de
  documento; esta auditoría no prueba cómo el proveedor coordina su numeración.

Los propietarios nativos `l10n_cl_edi`, su extensión stock/exportación y
`certificate` conservan licencia OEEL-1. `l10n_cl`/`account_edi` son Community;
el núcleo propio `step_l10n_cl_edi_core` es LGPL-3. Este bloque consulta esas
licencias y metadata instaladas, sin leer o copiar sus métodos propietarios.
No se encontró un almacén CAF propio preexistente en el código versionado que
permita evitar esta puerta de adopción.

## Evidencia privada y reproducción

Copias leídas, sin upgrade, restore, DDL/DML ni cambio de contadores:

| Referencia | Campos | XML IDs | ACL/reglas | CAF/adjuntos CAF | Antes/después |
| --- | ---: | ---: | --- | --- | --- |
| Cerro M | 14 | 25 | 2/1 | 0/0 | 22 secciones idénticas |
| SyS Storage B | 14 | 25 | 2/1 | 0/0 | 22 secciones idénticas |

Servidor: `/opt/steps-validation/community-caf-storage-20261029/evidence/`.
Archivos definitivos `cerro-v2-before.json`, `cerro-v2-after.json`,
`sys-v2-before.json`, `sys-v2-after.json` y `tests-v2.log`. Copia privada local:
`C:/Users/tito4/.codex/local-artifacts/community-caf-storage-20261029/`.
Los ensayos preliminares sin las secciones añadidas quedan identificados aparte;
no se mezclan sus fingerprints con los definitivos.

```bash
sudo python3.10 tools/community/caf_storage_preflight.py \
  --database MANAGEMENT_QA_CERRO_PAYROLL_API_ACCELERATED_20261029M \
  --output /private/evidence/before.json
sudo python3.10 tools/community/caf_storage_preflight.py \
  --database MANAGEMENT_QA_CERRO_PAYROLL_API_ACCELERATED_20261029M \
  --baseline /private/evidence/before.json --output /private/evidence/after.json
python3.10 tools/community/caf_storage_preflight_test.py
```

Los 17 casos nuevos del preflight pasan en Windows y Python 3.10 del host.
Prueban rechazo de producción antes de acceso DB, modo de lectura, identidad,
campos/aliases, relaciones y ON DELETE, permisos, exposición de adjuntos,
almacenamiento paralelo, detección del consumo del contador y separación entre
metadata válida y adopción autorizada. Son fixtures de metadata sintética y
pruebas de una herramienta, no una instalación Community del almacén ni otra
certificación de los 18 casos Odoo del núcleo criptográfico ya aceptado.

## Bloqueo preciso y siguiente implementación

No es seguro implementar una reserva fiscal tomando `final_nb` o el contador
de IDs como siguiente folio. Faltan el contrato operativo del asignador nativo,
su llave de unicidad y bloqueo para facturas/guías, cancelaciones, reutilización
y estados; y la adopción ORM de la política binary/attachment, defaults,
compute/inverse y métodos sin copiar cuerpos OEEL. Las tablas vacías de ambas
referencias no permiten demostrar conservación de un CAF real o su clave.
Tampoco hay ancla oficial/fingerprint aceptados ni autorización para leer llaves
reales en este bloque.

La siguiente entrega debe cerrar esos contratos con metadata runtime permitida
y fuentes Community/propias, crear fixtures criptográficos sintéticos claramente
marcados en copias aisladas y probar propiedad, lectura por rol/empresa,
concurrencia y rollback sobre los modelos/columnas/adjuntos originales. Solo
después puede incorporarse un proveedor Community de ese mismo almacenamiento
y probarse la transición de identidad. No crear stubs, un maestro paralelo o
un correlativo sustitutivo para presentar progreso artificial.

DTE/CAF/SII y conversión integral cero Enterprise siguen pendientes. El
preflight no habilita emisión, no modifica producción/QA y no resuelve el 31.
