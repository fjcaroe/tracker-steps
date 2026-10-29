# Proveedor real de custodia CAF — candidato 29-10-2026

Base canónica `6e3c8298`, rama `codex/community-caf-custody-20261029`.
Este bloque implementa almacenamiento y recuperación privados; no certifica
folios, autenticidad SII ni conversión integral. La pareja Odoo queda pendiente
de ejecución coordinada. No se hicieron upgrades, restores o escrituras DB
durante la preparación del código.

## Paquete y aislamiento de proveedores

Los tres addons son LGPL-3, versión 18.0.1.0.0:

| Addon | Función | Perfil |
| --- | --- | --- |
| `step_l10n_cl_caf_custody_core` | Mixin Python sin tabla, parser real, descarga autenticada y guards de adjuntos/binarios | Ambos |
| `step_l10n_cl_caf_storage` | Proveedor CE real `l10n_cl.dte.caf`, tabla original `l10n_cl_dte_caf` | Community oficial |
| `step_l10n_cl_caf_native_reference` | Añade APIs `step_*` de lectura al modelo nativo existente | Copia nativa |

El proveedor CE depende del core y este de `step_l10n_cl_edi_core`, `l10n_cl`
y `stock` Community. La referencia depende además de `l10n_cl_edi`, explícitamente
Enterprise: no es un reemplazo Community ni se instala en el perfil CE. El
pre-init del proveedor CE rechaza una clase/fuente nativa ya cargada o instalada.
El bridge no declara campos, datos XML, defaults ni overrides de los cuatro
métodos nativos `create`, `_decode_caf`, `action_enable`, `action_spend`.

## Almacén y permisos

CE conserva ocho campos declarados y seis automáticos, catorce en total,
Binary `caf_file` attachment=True/store=True/required=False, sin columna bytea
nueva. Mantiene las relaciones a empresa/tipo originales, los estados
`in_use`/`spent`, `UNIQUE(filename)` y la inversa
`l10n_latam.document.type.l10n_cl_dte_caf_ids`. No hay maestro paralelo ni
contador fiscal. Las dos ACL CRUD usan los grupos originales de responsables de
Contabilidad e Inventario. La regla global conserva exactamente
`[('company_id', 'in', company_ids + [False])]`.

La carga CE procesa los bytes originales con el parser RSA ya validado y
comprueba la identidad matemática de las claves cuando están presentes. El
emisor debe coincidir con el RUT de la empresa seleccionada, y el tipo con un
maestro chileno existente y único. No crea ni modifica maestros. El resto de
metadata se toma del CAF, rechazando contradicciones o intentos de alterar
auditoría/identidad. Los registros nuevos quedan en False, valor nullable del
campo original, sin inventar un tercer estado ni afirmar que están habilitados.
No se admiten cambios de archivo/metadata/estado o eliminación posterior.

Los aliases del namespace original solo se crean si no existen, o se aceptan
si apuntan exactamente al mismo modelo/campo/selección/ACL/regla. No se pisan
IDs en conflicto. En la referencia permanecen sus 25 XML IDs y ownership
originales: no se retira el proveedor nativo. No se acredita todavía adoptar
todo el catálogo de vistas/acciones/constraints durante una retirada histórica.

La descarga usa una ruta autenticada, sin token, con no-store/private y revisa
rol y empresa cada vez. Leer/recuperar el original no parsea, reescribe ni
normaliza históricos; incluso un formato legado no admitido por el parser
puede recuperarse por el responsable autorizado. Una empresa False histórica
no se infiere ni se rellena; la API de custodia rechaza descargarla hasta contar
con una decisión de propiedad explícita, sin cambiar su ACL/regla almacenadas.

Los guards comunes impiden adjuntos CAF públicos, con token, URL, reemplazo,
reasignación, borrado o un segundo `caf_file`. Revalidan al usuario real antes
de convertir un binario a stream, aunque el mecanismo original haya entregado
un recordset sudo/cacheado. Las consultas de control leen únicamente metadata
del vínculo después de comprobar permisos del CAF.

Para crear un adjunto, se toma la fila CAF original antes de insertar bytes.
Un UPDATE id=id sin cambiar valores ni write_date obliga a serializar/reintentar
escritores bajo REPEATABLE READ; un lock sin nueva versión no bastaría con un
snapshot anterior. Se verifica que el archivo no exista y se valida el archivo
dentro del mismo savepoint. Este protocolo no se ejecuta al leer y no asigna,
consume o restaura ningún correlativo. Su concurrencia debe evaluarse en la
aceptación; no se presenta como el asignador fiscal pendiente.

## Acciones permitidas y bloqueos

La interfaz CE permite guardar y recuperar el original y dice expresamente que
no habilita folios ni emisión. `step_custody_metadata` devuelve únicamente
metadata y `authority_verified=False`, sin claves ni XML; SHA256 permite
comparar originales. No hay ancla oficial aceptada ni falsa validación FRMA.
El parser y verificador criptográfico siguen disponibles como núcleo real,
sin aprender confianza de claves aportadas por un cliente.

En CE `action_enable`, `action_spend` y reserva fiscal fallan explícitamente.
No se adivina una salida compatible de `_decode_caf`. El bridge nativo deja
intactos esos métodos del proveedor original y bloquea su nueva API de carga;
solo ofrece custodia de lectura. No llama al SII ni a la emisión nativa.

## Pruebas candidatas y puerta coordinada

Hay **15 casos concretos CE y 9 nativos**, tags:

```text
/step_l10n_cl_caf_storage,/step_l10n_cl_caf_native_reference
```

Ambos perfiles ejercitan originales byte a byte, roles originales, límites de
empresa y legacy False, público/token, inmutabilidad de adjunto, binario cacheado
tras revocar rol y bloqueo fiscal. CE añade carga/formulario, catorce campos,
attachment real/inversa, metadata/identidad, XML hostil, filename único, aliases
sin conflictos, adjunto ambiguo y rollback de una carga pública por contexto.

La referencia siembra un fixture **sintético** en la tabla y adjunto nativos,
sin ejecutar la carga EE ni copiar sus fuentes. Usa ID negativo solo después
de comprobar que el ORM lo reconoce como registro persistido. Comprueba que el
contador de IDs nativo no cambie y que los cuatro métodos originales sigan
perteneciendo al proveedor nativo. No toca CAF o llaves reales.

El coordinador instalará solo storage en CE y solo bridge en la copia fresca,
con core/parser idénticos y huellas del paquete exacto. Debe comprobar formularios,
roles, descarga/streams, 25 IDs/ACL/regla/FK originales y snapshots antes/después.
La compilación/inspección de fuentes no sustituye esos casos Odoo aún pendientes.

Siguen abiertos ancla/CAF reales, asignador fiscal concurrente, estados de
habilitación/consumo, firma/TED/PDF417/DTE/guías/exportación, respuestas/reintentos
SII y adopción integral restaurable cero Enterprise. El 31 continúa en riesgo.
