# Firma y verificación DTE sin conexión

Código propio LGPL-3, implementado con `cryptography` (RSA/X509) y `lxml`
(C14N/XSD). No lee cuerpos OEEL ni implementa transporte SII. Los XSD públicos
de referencia conservan sus avisos y bytes; su procedencia y SHA256 están en
[xml_schemas/README.md](xml_schemas/README.md).

Las fuentes primarias del contrato son el [Instructivo SII 28/10/2021,
anexo A.3.3.1 y A.3.3.2](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf)
y [XML Signature, procesamiento de referencia y validación](https://www.w3.org/TR/xmldsig-core1/).
El perfil del instructivo usa C14N 1.0 sin comentarios, digest SHA1 y
RSA-SHA1, referencia local a `#ID`, RSAKeyValue y certificado X509. Este perfil
fiscal concreto no negocia algoritmos, XPath, XSLT ni recursos externos.

`dte_signature.CertificatePin(certificate_der, fingerprint_sha256)` exige el
DER exacto y su huella SHA256. `DTEContext(document_id, ted_context, signed_at)`
exige identidad esperada y fecha de firma con zona horaria explícita y segundos
enteros. La hora local corresponde exactamente a TmstFirma; el instante UTC
comprueba la vigencia del certificado. Se rechazan CA como firmante, KeyUsage
sin digitalSignature, otra clave y DER con contenido adicional. No se infiere
que el RUT personal de un firmante coincida con el RUT de la empresa emisora.

`sign_dte(unsigned_bytes, original_caf_bytes, certificate_pin, context,
private_key_object, caf_authorities=...)` construye la firma de un DTE nuevo.
Exige ancla CAF explícita, TED/FRMT real válido, correspondencia byte a byte
con el CAF indicado, contexto exacto y esquema SII válido antes de utilizar la
clave privada. Recibe un objeto RSA en memoria; no abre llaveros, adjuntos,
certificados privados ni servicios. Rechaza un XML que ya contenga firma.
Añade únicamente Signature antes del cierre DTE: los bytes originales de
Documento/Liquidacion/Exportaciones, TED y CAF permanecen intactos, incluidas
entidades, acentos, espacios internos y representación ISO-8859-1/UTF-8.

`verify_signed_dte(raw_bytes, original_caf_bytes, certificate_pin, context,
caf_authorities=None)` vuelve a analizar el documento y verifica esquema,
referencia única, digest, firma, certificado fijado, RSAKeyValue y TED. Vincula
emisor, receptor, tipo, folio, fecha de emisión, total y los primeros 40
caracteres del nombre del receptor y primer ítem. Los importes se comparan con
Decimal exacto: enteros ordinarios, liquidación 43 con signo y exportaciones
110/111/112 hasta cuatro decimales. Exige que la firma no anteceda a emisión o
TSTED. No calcula impuestos ni reconstruye líneas contables.

Admite un único DTE con namespace SII por defecto, version=1.0 y un único nodo
Documento, Liquidacion o Exportaciones con su ID explícito. Signature ocupa
la segunda posición. Rechaza DTD/entidades externas, comentarios, PI,
namespaces extra, IDs alternativos/duplicados, wrapping, firma anidada,
referencia externa/vacía/XPointer y transformaciones ajenas al perfil. No es
un normalizador de XML legado: la descarga existente sigue sin analizar ni
reescribir archivos históricos.

El resultado conserva el documento original y entrega evidencia separada:
firma, esquema, pin y vigencia comprobados. Una huella elegida por el caller
no prueba confianza SII. `caf_authority_verified` sólo refleja la verificación
criptográfica contra el mapa explícito suministrado; sin él es False.
Cadena de confianza, revocación, autorización fiscal del firmante, cálculo
tributario, identidad de un documento de negocio adoptado, operación de
folios, emisión y aceptación SII permanecen False. Las pruebas usan claves y
certificados efímeros marcados SYNTHETIC; no equivalen a certificación SII.

La integración `_step_custody_check_signed_dte(file_data, pin, context)` es
privada de servidor, conserva el modelo/tabla/14 campos/adjunto CAF original
y comprueba actor, roles y empresa antes de leerlo. Revalida empresa, tipo,
rango y fecha del archivo frente al registro. No admite mapa de autoridades,
clave privada ni firma desde RPC. No crea modelos, campos, ACL, roles,
adjuntos, maestros o contadores, y no actualiza estado ni fechas de auditoría.
Los cuatro métodos originales del proveedor nativo permanecen intactos.

Prueba pura reproducible:
`python tools/community/dte_signature_unit_tests.py`.
Son 11 casos criptográficos compartidos con TestDTESignatureCore, más una
prueba Odoo de ausencia de modelos/contadores nuevos: **12** seleccionables.
TestDTESignatureCustodyStorage y TestDTESignatureNativeCAFCustody agregan
**5** casos cada uno con actores, adjuntos y secuencia reales. La aceptación
Community/copia fresca del paquete combinado queda a cargo del runner
central; pasar los casos puros no declara esa aceptación.

Permanecen bloqueados: adopción de fuente/ancla/certificado reales, autoridad
SII y revocación, habilitación y asignación concurrente de folios, vínculo
persistente con DTE originales e identidad de negocio, sobre EnvioDTE,
transporte/reintentos/respuestas SII y aceptación integral. Nada de este
bloque habilita el retiro Enterprise de producción ni resuelve el vencimiento.
