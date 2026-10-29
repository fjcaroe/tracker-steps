# Recibo de upload SII: parser offline

`upload_response.py` implementa lectura y admisión de contexto sin modelos,
tablas, permisos, HTTP, credenciales ni cambios de dependencias. Convive con el
núcleo CAF y no sustituye al proveedor DTE instalado.

## Contrato y fuentes

El [manual oficial SII de envío automático](https://www.sii.cl/factura_electronica/factura_mercado/envio.pdf),
OI2003_UPDTE_MDE_1.5, apartados 2.1/2.2 y figuras 2.1–2.3, publica
`RECEPCIONDTE`: emisor del envío, compañía, archivo, fecha/hora, estado y TrackID.
Un estado cero asigna identificación de recepción; los ejemplos de error
omiten TrackID y el de esquema incluye varios `DETAIL/ERROR`. El formato informa
recepción del archivo; no aporta aceptación individual de sus documentos.

Es un perfil histórico publicado, no una promesa de compatibilidad con todos
los servicios SII actuales. El propio manual usa descripciones diferentes para
el código 5 en su lista y ejemplo: se conserva el número, sin deducir reintentos.
No se implementa transporte, consulta de estado ni emisión.

La base de sintaxis es [XML 1.0 del W3C](https://www.w3.org/TR/xml/).
Este perfil deliberadamente rechaza DTD, entidades declaradas, namespaces,
comentarios/PI, atributos, envolturas, campos desconocidos/duplicados y contenido
mixto. Usa parser sin red, resolución de entidades ni recuperación. Acepta
UTF-8/ISO-8859-1, hasta 2 MiB, 100 errores y 8.192 caracteres por terminal;
estos límites son del consumidor y no se atribuyen al SII.

## Uso y preservación

```python
from odoo.addons.step_l10n_cl_edi_core.upload_response import (
    parse_upload_response, admit_upload_receipt,
)

parsed = parse_upload_response(original_response_bytes)
receipt = admit_upload_receipt(
    parsed, sender_rut=original_sender_rut, company_rut=original_company_rut,
    filename=original_filename, existing_track_id=stored_track_id_or_none,
)
```

`original_bytes()` devuelve el payload exacto. La metadata valida RUT/DV,
incluido el relleno cero del ejemplo publicado, y conserva literalmente los
dígitos del TrackID. La fecha/hora se interpreta como local sin asignarle zona.
El estado numérico desconocido se conserva como recepción fallida. Un éxito sin
TrackID, un error con TrackID o un éxito con errores es contradictorio y falla.
La admisión vuelve a parsear los bytes y rechaza un objeto alterado, un emisor,
compañía o archivo diferente, y cualquier conflicto con el TrackID almacenado.
No limpia, sustituye o incrementa ese identificador.

La representación del objeto y los errores no exponen XML, RUT, nombre de
archivo o texto remoto. `dte_acceptance` permanece `None` y
`source_authentication_verified=False`: un XML offline no autentica su origen.
El adaptador futuro debe comprobar ACL originales, empresa y transporte antes
de leer/persistir originales o cambiar un estado. No hay escrituras de estado,
asignación de folios, llamadas SII ni reintentos automáticos en esta API.

## Evidencia y límites

Hay 22 casos compartidos puros y 22 forwarders Odoo explícitos en
`tests/test_upload_response.py`. Las transcripciones de las tres figuras
publicadas tienen procedencia y hashes en `tests/fixtures/upload_manual_provenance.json`;
se corrigen únicamente artefactos de diagramación del PDF para producir XML.
No son respuestas obtenidas del SII ni maestros de negocio. Las demás variantes
son sintéticas; no utilizan certificados, claves privadas o CAF reales.

El PDF consultado se conserva fuera del checkout, SHA256
`875792e9e2926f363614edade4271055a4c39cd88730c86e2a9e02b630e75b2d`, en
`C:/Users/tito4/.codex/local-artifacts/community-dte-offline-20261029/`.
Sólo se consultaron documentos públicos, sin operaciones tributarias.

La aceptación del paquete en Community/copia fresca corresponde al coordinador.
Siguen pendientes integración al almacenamiento/estados originales, transporte
autenticado, respuesta de procesamiento/resultado individual, conciliación,
reintentos idempotentes, folios concurrentes, CAF/anclas reales y firma/emisión.
Este bloque no cambia calendarios, bancos, saldos, históricos, vencimientos ni
producción/QA; no acredita conversión integral ni resuelve el 31 de octubre.
