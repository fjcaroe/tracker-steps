# Sobre EnvioDTE firmado sin conexión

Código propio LGPL-3 con `cryptography` y `lxml`; usa los cuatro XSD públicos
inalterados y fijados en [xml_schemas/README.md](xml_schemas/README.md). No
incorpora nuevas fuentes normativas ni código Enterprise. Fuentes primarias:
[Instructivo SII, anexo 3, páginas 22–27](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf),
[Manual de Certificación SII, ejemplo público](https://www.sii.cl/servicios_online/docs/manual_certificacion.pdf)
y [XMLDSig/W3C](https://www.w3.org/TR/xmldsig-core1/).

`SignedDTEInput(original, original_caf, certificate_pin, context)` representa
un documento ya firmado y su fuente/contexto explícitos. `EnvelopeContext`
exige ID del conjunto, RUT emisor/envía/receptor, fecha y número de resolución,
instante de firma con zona horaria, conteos ordenados por tipo, codificación y
política de destinatario. No obtiene datos desde compañía, sesión, credenciales
o defaults. Resolución y RUT son afirmaciones suministradas; no se presume su
autorización fiscal ni se consultan servicios.

`build_envelope(inputs_tuple, pin, context, private_key_object,
caf_authorities=...)` crea Carátula, DTE íntegros y firma XMLDSig del SetDTE.
La primera línea declara la codificación; la segunda contiene xmlns:xsi y
xsi:schemaLocation exactos del perfil SII. Valida XSD EnvioDTE, firmas
DTE/TED/CAF y contexto antes de utilizar la clave del sobre. No llama al
firmador de los documentos recibidos.

`verify_envelope(raw, inputs_tuple, pin, context, caf_authorities=None)`
verifica encabezado físico, XSD, Carátula, firma del conjunto, certificado
fijado y cada documento. Cada fragmento DTE debe coincidir byte a byte y en
orden con su original. Las firmas internas se comprueban también sobre los
elementos del árbol final, con sus namespaces heredados. Una verificación
aislada no basta. Se conserva el hash de cada archivo original completo;
al insertar un DTE sólo se excluyen su declaración XML y espacios de framing
fuera del nodo raíz, que no pueden aparecer dentro de otro documento XML.
Ningún byte del fragmento DTE, incluido TED/CAF, se serializa de nuevo,
convierte de codificación o normaliza.

Todos los emisores coinciden con la Carátula. La política `sii` exige destino
SII explícito 60803000-K y admite distintos receptores dentro de los DTE.
`counterparty` exige que todos coincidan con el destinatario del sobre. No se
infiere una política desde el RUT. Se contrastan conteos reales por tipo y se
rechazan IDs repetidos/colisiones con SetDTE y duplicados emisor/tipo/folio
aunque usen otro ID XML. Admite los diez tipos de las tres familias DTE ya
cubiertas. El límite normativo es 2.000 documentos/20 subtotales; el límite
local de recursos de 20 MiB no se presenta como límite oficial SII.

La resolución no puede ser posterior a documentos o firma; el sobre no puede
firmarse antes que sus documentos. RutEnvia debe coincidir exactamente con un
único subject.serialNumber del certificado fijado. Es un **perfil admitido
explícito**, no un extractor universal de identidad chilena ni una afirmación
de que SII exige ese OID en todos los certificados. Otros perfiles, incluidos
certificados cuya identidad sólo esté en SAN, se rechazan hasta auditar su
contrato. Coincidir con una afirmación de un certificado elegido por el caller
no demuestra confianza en su emisor ni autorización SII.

## Namespace antes de firmar documentos nuevos

C14N inclusiva incorpora namespaces de los ancestros. Añadir xmlns:xsi al
sobre rompe firmas de documentos firmados sin ese contexto. Para un documento
**nuevo y sin firma**, `prepare_unsigned_dte_for_envelope(unsigned)` añade
sólo la declaración xsi al nodo DTE, conservando Documento/TED/CAF intactos.
Luego se firma con `DTEContext(..., namespace_profile='sii-envelope')`.
El default `standalone` mantiene el contrato previo. La elección llega en un
objeto de contexto de la API pura/privada, nunca desde el contexto RPC Odoo.

La preparación rechaza documentos ya firmados. El sobre exige el perfil
preparado y falla antes de devolver bytes utilizables si recibe un documento
standalone, un contexto falseado o namespace incompatible. No re-firma ni
reescribe históricos para acomodarlos. Descargas legadas y los cuatro métodos
originales del proveedor nativo permanecen intactos.

## Evidencia y puertas restantes

`python tools/community/envelope_unit_tests.py`: **10** casos puros
compartidos con TestEnvioDTECore y **1** caso Odoo sin modelo/ACL/contador nuevo.
`dte_signature_unit_tests.py` conserva once casos previos y agrega dos de
preparación/perfil: **13** puros/**14** concretos Odoo. Positivos incluyen las
tres familias, sobre y firmas internas en el árbol final, ISO-8859-1/UTF-8 y
bytes originales; negativos incluyen mezcla de emisores/destinatarios,
conteos, IDs, wrapping/XXE, URI externa, algoritmos, cuerpo/firma alterados,
resolución, certificado y encabezado físico incompleto.

Se distingue encabezado XML oficial/esquema/firmas comprobados de transporte
operativo: `transport_profile_complete=False` permanece porque este núcleo no
contiene un adaptador de envío, recepción o aceptación. Cadena de confianza,
revocación, autorización fiscal, autoridad real de resolución/CAF, folios,
emisión y aceptación SII permanecen False. Los casos usan claves/certificados
efímeros SYNTHETIC; no hay emisión real ni sandbox. La aceptación conjunta en
Community y copia fresca corresponde al runner central. No adopta maestros
originales ni habilita retiro Enterprise o resuelve el vencimiento.
