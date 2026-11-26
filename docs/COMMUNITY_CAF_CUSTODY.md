# Proveedor real de custodia CAF — candidato 29-10-2026

Base canónica `6e3c8298`, rama `codex/community-caf-custody-20261029`.
Este bloque implementa almacenamiento y recuperación privados; no certifica
folios, autenticidad SII ni conversión integral. La pareja G fue aceptada en
[COMMUNITY_CUSTODIA_LOTES.md](COMMUNITY_CUSTODIA_LOTES.md); esa hoja conserva
el paquete exacto, resultados y límites. No se hicieron upgrades, restores o
escrituras DB durante la preparación independiente del código.

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

Hay **20 casos concretos CE y 9 nativos**, tags:

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

## Verificación histórica por folio, 26 de noviembre de 2026

Contabilidad e Inventario pueden verificar un TED que ya contiene folio. El método
`step_custody_check_ted_for_folio` localiza el rango del emisor y tipo de
documento en la empresa activa, comprueba el acceso al CAF y verifica la firma
del timbre con el original guardado. Un rango agotado puede verificar un timbre
antiguo. Si dos CAF abarcan el folio, incluso si una regla de acceso oculta uno
de ellos, la operación se detiene.

El paquete `c075cdd4` pasó una prueba funcional en cada copia privada restaurada
del par U40F, con Odoo 18 Community y con el proveedor nativo de Cerro. Se
ejercitaron los dos perfiles autorizados, un empleado sin permiso, un emisor
ajeno, un timbre alterado y rangos superpuestos. El estado del CAF, la secuencia
y el número de registros originales se conservaron. Las pruebas usaron llaves
efímeras sintéticas y se ejecutaron con la red aislada. La autorización y el
consumo fiscal de folios continúan fuera de este flujo.

La referencia U40FQ repitió el caso sobre una restauración nueva de Cerro tomada
el 26 de noviembre. Usó el respaldo SQL U40D
`1d8c636dba84fbc851368fa3fd4d7785c32fbc88efc6d19652557c1aa4e0310c`
y los adjuntos U40Q
`b2e8884bb67a26d37c742f740ed061328dcdefab901f184d0f205fb424175efe`.
El mismo paquete de ambas pruebas U40F
(`2956c36f2f39db3767789030817975a447b8274d2d376735aaa84628266558c9`)
ejecutó el caso completo con el proveedor original. Pasó 1 de 1 pruebas con
cero fallos y errores. El conteo de registros CAF se conservó. El recibo de
esta ejecución tiene SHA-256
`c4938c03a6fe48211c83b9e831e73c61e376b8556c860678b920c357a3746abf`.

## Concurrencia de custodia, 26 de noviembre de 2026

En U40FC se ejecutaron dos escrituras Odoo simultáneas por cada escenario,
sobre los registros CAF originales de copias privadas de Community y Cerro.
PostgreSQL confirmó que un escritor esperaba al otro en ambos escenarios y
en los dos proveedores. Cada escritor presentó un CAF sintético distinto,
válido para la misma empresa, tipo y rango. Se conservaron los registros
originales con su auditoría y la secuencia de identificadores.

Cuando el primero confirmó, el segundo recibió un conflicto de serialización.
La repetición en una transacción nueva rechazó el adjunto duplicado. Cuando
el primero revirtió, el segundo confirmó y conservó su archivo. Cada rango
pudo verificar únicamente el TED correspondiente al archivo que prevaleció.
El ensayo cubrió la custodia de archivos para verificar folios históricos.
La reserva y la emisión fiscal siguen pendientes de validación.

El recibo de ambos proveedores tiene SHA-256
`76db9cd06b16202fc5ce95baeec12eaedfacc3c3cd2029f78f5ea9d6d8e7ed2c`.

## Verificación del DTE firmado por folio

La verificación privada que ya recibe un DTE firmado, el certificado fijado y
los datos esperados de un documento puede localizar el CAF original usando el
emisor, el tipo y el folio de esos datos. Después coteja el documento con el CAF y
el certificado. La misma operación sigue admitiendo un registro CAF seleccionado.
El timbre y el DTE usan la misma búsqueda de rangos históricos en la empresa
activa. Un solapamiento, incluso con un registro oculto por permisos, impide
seleccionar un CAF.

En U40FD se utilizaron documentos, certificados y llaves sintéticos con el
acceso a red aislado. El caso funcional cubre Contabilidad e Inventario,
un empleado sin permiso, otra empresa, un folio distinto del timbrado, un
tipo inválido, un certificado que difiere del previsto y un rango superpuesto.
Se comprobaron el estado de un rango agotado, su adjunto original y la
secuencia de identificadores. Este ensayo verifica documentos históricos.
La emisión, la autorización fiscal del firmante y la aceptación del SII siguen
pendientes.

En el primer ensayo, la creación de los siete registros sintéticos de Community
adelantó en siete posiciones el contador de identificadores técnicos. La
comparación integral confirmó que las filas de CAF y los adjuntos originales
eran idénticos a la fuente. Para ensayar lecturas históricas, los casos
preparan ahora registros sintéticos con identificadores negativos reservados
en la misma tabla. Las pruebas existentes de carga conservan la creación
habitual por Odoo.

La repetición U40FD2 restauró ambas bases en los espacios privados de
PostgreSQL en `/opt`. El paquete
`bbe67c8016d598bb7fde72692e95a42ae3158b7f412f91c6a80965731d9f8951`
registró la versión 18.0.1.4.0 en ambos proveedores. Community oficial pasó
7 de 7 pruebas y la referencia de Cerro, restaurada desde U40FQ, pasó las
mismas 7. Las filas CAF, todos sus adjuntos y la secuencia de identidad
conservaron sus huellas en ambas copias, incluida la preparación y reversión
de los datos sintéticos. Pasaron además 18 pruebas de firma DTE y 17 de CAF
sin acceso de red. El recibo funcional tiene SHA-256
`217d9fa190d1a0e6e2176b512131c2da8957aa1fce5cb64c6ceda685ebb9041d`.
