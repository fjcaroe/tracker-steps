# Verificación offline del timbre RSA

API propia LGPL-3, sin código OEEL, firma privada, red, emisión, PDF417,
XMLDSIG, reserva de folios ni cambios de estado. Es un candidato para la
aceptación coordinada; los fixtures no son autorizaciones emitidas por el SII.

## APIs y confianza

- `parse_ted(bytes)` conserva el TED y su fragmento CAF literalmente. Rechaza
  DTD/XXE, comentarios, PI, CDATA, envolturas, duplicados, campos/atributos
  desconocidos, namespaces mixtos/prefijados y entradas mayores de 2 MiB.
- `check_ted_against_caf(ted_bytes, original_caf_bytes, expected=None)` exige
  el fragmento CAF original byte a byte, emisor/tipo/folio/fecha compatibles y
  FRMT RSA PKCS#1 v1.5/SHA-1 válido con la clave pública de ese CAF. Devuelve
  **`caf_authority_verified=False`**. No comprueba FRMA ni aprende confianza
  de las claves aportadas por el propio archivo.
- `verify_ted(ted_bytes, authorities, expected=None)` además verifica FRMA
  mediante `verify_caf`, con IDK, clave pública y fingerprint independientes.
  `caf_authority_verified=True` significa verificación contra ese anclaje
  explícito; no demuestra que la clave pertenezca al SII. No se incluye ni se
  configura un ancla oficial en esta entrega.
- `TEDContext` permite comparar todos los datos representativos esperados,
  incluyendo receptor, glosas y total exacto. El consumidor futuro debe obtener
  ese contexto del documento autorizado real. Omitirlo deja
  `expected_context_matched=False`; no demuestra vínculo con un DTE completo.

El método de los proveedores existentes
`l10n_cl.dte.caf.step_custody_check_ted(file_data)` recibe un TED base64 y aplica
la segunda API con el CAF almacenado. Revalida los roles originales y la empresa
antes de leer el binario; rechaza empresa histórica sin asignar. No acepta un
mapa de anclas por RPC. Devuelve sólo metadata del resultado, sin nombres de
receptor, glosas, XML ni claves, y mantiene siempre autoridad, emisión/folios,
certificación SII y verificación XMLDSIG en False. Un estado legado `in_use`
no cambia ese resultado. Las descargas y lecturas anteriores no llaman al parser
TED ni reparan archivos históricos.

## Perfil y fuentes primarias

El [instructivo SII de 28-10-2021](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf),
anexo2, define DD/FRMT y la normalización de su digest. Se usa el texto lexical
DD en ISO-8859-1, sin declaraciones namespace, CR/LF ni blancos/tabs entre tags.
Se conservan entidades y espacios interiores. Nunca se usa c14n/XMLDSIG ni se
reescriben los bytes originales para archivarlos.

La estructura/límites fueron contrastados con el
[ZIP XSD oficial](https://www.sii.cl/factura_electronica/factura_mercado/schema_dte.zip),
descargado el 30-10-2026 como documentación, sin acceder a un servicio fiscal:

| Fuente | SHA256 |
| --- | --- |
| ZIP | `59429e27879824e9eecb0942cee733f7cf93cb61f8b80d5f5a34bcd22b6c5bee` |
| DTE_v10.xsd | `85518401b7dddac1bc0b7b99646a1ce353a4afa645344ea5f10af3a2e6676b37` |
| SiiTypes_v10.xsd | `ce9a84bde70aa9d0f9269d99acd3b0ea81d868022517ac31064b6cdfa0c45bdf` |

Admite tipos ordinarios 33/34/46/52/56/61 (MNT unsignedLong), liquidación43
(entero firmado de18dígitos) y exportación110/111/112 (Decimal exacto no negativo,
máximo `99999999999999.9999`, hasta4decimales). Conserva la representación
original del importe; no usa Float, redondeo, cuantización ni tipo de cambio.
Folio positivo de hasta10dígitos; glosas de hasta40caracteres Latin1; fechas
2000–2050 y timestamp local sin fracciones/offset. No admite boletas, DSA,
controles en glosas ni variantes fuera de ese perfil. No valida el XSD entero
del DTE ni sus reglas tributarias mediante esta API.

## Pruebas y límites operativos

`python tools/community/ted_unit_tests.py` ejecuta 9 casos criptográficos sin DB y
comprueba el inventario concreto Odoo: `TestTEDCore` tiene 10 casos (9 compartidos y
ausencia de almacenes paralelos). `TestTEDCustodyStorage` y
`TestTEDNativeCAFCustody` añaden 5 casos de actor real por proveedor: lectura,
roles/empresa, revocación con caché, rechazo seguro, metadata legada inconsistente y conservación de adjunto,
auditoría, estado, contador y descarga. La referencia conserva los métodos EE
originales y el modelo de14campos; no instala el proveedor CE sobre Enterprise.

Sigue bloqueado reservar/habilitar/consumir folios: falta confianza oficial,
CAF real autorizado para pruebas, contrato nativo de asignación/cancelación,
almacén de reservas que preserve identidad, concurrencia y recuperación.
El contador de IDs del maestro CAF no es un correlativo fiscal. No se altera
esa guarda para mostrar un timbre válido. Certificados/firma XMLDSIG, emisión,
respuestas y reintentos SII y conversión integral continúan pendientes.
