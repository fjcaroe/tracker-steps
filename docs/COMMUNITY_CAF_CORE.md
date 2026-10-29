# Núcleo CAF Community — contrato y puerta de adopción

Base de implementación: canónica `f56e221d`, rama propia
`codex/community-caf-core-20261029`. Este bloque no cambia dependencias de las
apps existentes ni convierte el motor DTE instalado.

## Funcionalidad implementada

`step_l10n_cl_edi_core` 18.0.1.0.0, LGPL-3, depende únicamente de `base` y de las
bibliotecas públicas `lxml` y `cryptography`. No declara modelos, campos,
tablas, vistas, menús, ACL ni secuencias. Es una API de lectura que puede usar
un adaptador posterior conservando los propietarios originales.

- `parse_caf(bytes)` admite una autorización RSA completa o un fragmento CAF
  público. Extrae RUT con dígito verificador, tipo, rango, fecha, IDK y clave
  pública. Conserva todos los bytes originales, incluyendo `RSASK`, sin
  publicarlos en representación de objetos ni errores. El fragmento CAF se
  conserva también literalmente; no se serializa nuevamente para archivarlo.
- `verify_caf(parsed, {idk: TrustAnchor(...)})` verifica FRMA RSA PKCS#1 v1.5
  con SHA-1 para este formato legado. El ancla contiene IDK, clave pública PEM
  y fingerprint SHA256 de DER SubjectPublicKeyInfo. No confunde RSAPK con la
  clave de autoridad, no aprende confianza del XML ni descarga claves. Comprueba
  además la identidad matemática RSASK/RSAPUBK/RSAPK cuando están presentes,
  sin firmar con la clave privada. Revalida que metadata y bytes correspondan.
- `validate_folio` comprueba un folio explícito contra emisor, tipo, rango y,
  opcionalmente, fecha de emisión igual o posterior a la autorización.
  `select_caf` exige una única autorización verificada aplicable; rechaza
  solapamientos incluso si ambos candidatos son el mismo objeto. No reserva,
  incrementa, busca el siguiente ni consume folios.
- El parser rechaza DTD, entidades declaradas, comentarios, instrucciones de
  procesamiento, estructuras envueltas, campos duplicados/desconocidos,
  namespaces extraños, prefijos y extensiones. Admite namespace SII por defecto
  y codificación UTF-8 o ISO-8859-1; solo datos firmados representables en Latin1.
  Las excepciones contienen códigos estables, nunca el XML ni sus secretos.

Ejemplo de integración, sin I/O ni escritura:

```python
from odoo.addons.step_l10n_cl_edi_core.caf import (
    TrustAnchor, parse_caf, verify_caf, validate_folio,
)

# Clave y pin obtenidos/autenticados por un proceso independiente.
anchor = TrustAnchor(key_id, approved_sha256_spki, approved_public_pem)
verified = verify_caf(parse_caf(original_bytes), {key_id: anchor})
validate_folio(verified, issuer_rut=company.vat,
               document_type=int(document_type.code), folio=explicit_folio)
```

El consumidor debe aplicar sus ACL originales antes de leer el binario,
entregar únicamente información permitida al rol y guardar evidencia sensible
fuera del checkout. Nunca pasar `original_bytes()` a logs: una autorización
completa incluye la clave privada de timbraje. Un fragmento que hereda namespace
de su envoltura conserva sus bytes originales; no es una reescritura autónoma.

## Fuente pública y normalización

Implementación independiente, sin leer/copiar cuerpos de funciones OEEL. El
[instructivo técnico SII del 28-10-2021](https://www.sii.cl/factura_electronica/factura_mercado/instructivo_emision.pdf),
anexos 1 y 2, describe la firma FRMA sobre DA, su IDK y la diferencia entre la
clave de autoridad y la de timbraje. La verificación usa el perfil indicado en
su apartado A.2.4: DA lexical en ISO-8859-1, sin saltos de línea, separación
entre tags ni declaraciones namespace; conserva espacios interiores y entidades
de los terminales. No usa canonicalización XMLDSIG ni reformatea los originales.
SHA-1 se usa exclusivamente para verificar este formato histórico.

No se incluye ninguna clave pública atribuida al SII. Las pruebas generan una
autoridad local efímera explícitamente identificada como sintética. Antes de
aceptar CAF reales se necesita obtener y autenticar la clave oficial por IDK,
registrar su fingerprint y probar autorizaciones reales sin exponer RSASK.

## Auditoría nativa y preservación

La consulta de solo lectura a Cerro halló `l10n_cl.dte.caf` y cero registros CAF
en ese modelo. Se conservaron sin escritura los campos `caf_file`, `filename`,
`company_id`, `l10n_latam_document_type_id`, `start_nb`, `final_nb`, `issued_date`
y `status`; la relación inversa desde `l10n_latam.document.type`, vistas y dos
ACL manager siguen bajo sus propietarios `l10n_cl_edi`/`l10n_cl_edi_stock`.
`certificate`, `l10n_cl_edi`, sus extensiones stock/exportaciones son OEEL-1;
`l10n_cl` y `account_edi` son LGPL-3. Solo se consultó metadata de licencia,
modelos, relaciones, IDs, permisos y vistas, nunca binarios de CAF/certificados.

`tools/community/caf_inventory.py` reproduce la auditoría en una transacción
REPEATABLE READ READ ONLY y exige salida privada fuera del código. El inventario
privado guarda los IDs/XML IDs/FK/ACL concretos para la futura adopción.

La siguiente capa debe adoptar exactamente ese modelo, columnas, relaciones,
XML IDs, vistas, grupos y reglas antes de retirar el proveedor Enterprise.
No crear otra tabla de autorizaciones, otro maestro de tipos ni correlativos
paralelos. Antes del cambio debe comparar los binarios por hash y comprobar
lectura por rol, acciones/formularios y preservación integral en copia fresca.

## Pruebas y alcance pendiente

`python tools/community/caf_unit_tests.py` ejecuta 17 casos sin base: firmas RSA
reales; acentos, entidades y espacios; bytes originales; identidad de claves;
pins; firmas alteradas; XML hostil; ambigüedad y límites de folios. La suite del
addon añade una prueba Odoo de ausencia de modelos/ACL/secuencias paralelos.
Los fixtures criptográficos efímeros no son CAF emitidos por el SII ni acreditan
certificación tributaria.

Evidencia privada inicial: `/opt/steps-validation/community-caf-core-20261029/`;
`unit-tests.log` contiene los 17 casos aprobados. El coordinador ejecuta la
aceptación del paquete combinado exacto en Community oficial y copia fresca de
Cerro; esos resultados deben leerse en el estado acumulado de ese paquete.

Continúan abiertos: adopción persistente/ACL/acciones; anclas oficiales y CAF
reales; asignación atómica unívoca con correlativos originales; revocación y
políticas aplicables; TED/PDF417; firma XMLDSIG del DTE/envío; certificado,
documentos, guías/exportación; envío aislado, respuestas, reintentos e históricos.
No se han probado emisión ni recepción SII, no se escribe en producción/QA ni se
cambia vencimiento. Este núcleo no acredita conversión integral cero Enterprise
ni resuelve el riesgo del 31 de octubre.
