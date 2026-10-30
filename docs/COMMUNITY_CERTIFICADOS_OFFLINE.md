# Certificados de firma DTE: cadena y CRL explícitas

Implementación candidata desde `7d763a68`, en `step_l10n_cl_edi_core`
18.0.1.5.0. La aceptación del paquete completo se registra separadamente en
el último estado de COMMUNITY_CONTINUACION.md. No sustituye las puertas de
configuración original, folios, transporte, autoridad fiscal y conversión.

## Contrato implementado

`certificate_trust.verify_signer_trust` valida los DER reales del firmante,
intermedios y ancla explícita, no un recibo de verificación previo. El nuevo
argumento opcional `certificate_trust` de `sign_dte` y `verify_signed_dte`
vincula ese resultado al certificado exacto y al instante explícito de firma.
La firma rechaza la política inválida antes de usar la clave privada; la
verificación conserva cada byte del DTE firmado. La ruta sin política mantiene
sus indicadores de cadena/revocación en False y no hereda resultados previos.

Se usa el validador PKIX real de OpenSSL mediante pyOpenSSL, sin implementar
una segunda cadena de validación. El store empieza vacío: no carga anclas
del sistema, rutas de archivos, AIA, CRL remotas ni parámetros de red. Exige
`X509_STRICT`, `CRL_CHECK`, `CRL_CHECK_ALL`, `CHECK_SS_SIGNATURE` y `POLICY_CHECK`;
el camino verificado debe coincidir byte por byte con el camino ordenado
proporcionado. Referencia: [API de X509Store y X509StoreContext](https://www.pyopenssl.org/en/22.0.0/api/crypto.html).

Perfil acotado admitido:

- Una raíz autofirmada fijada por SHA256, hasta cinco intermedios ordenados y
  firmante RSA de 2048–8192 bits; DER canónico sin sobrantes, límites previos
  al hash, sin duplicados. Certificados con SHA256/384/512, roles CA, usos de
  clave, AKI/SKI e instante explícito comprobados. La firma XML heredada del
  perfil SII permanece separada del algoritmo de firma de certificados.
- Una CRL completa directa por emisor, firma y AKI reales, ventana
  `thisUpdate <= instante < nextUpdate` y edad máxima explícita, hasta 31 días.
  No se admiten delta, indirectas, distribución parcial, freshest-CRL,
  entradas duplicadas ni removeFromCRL. No se interpreta una CRL fuera de su
  alcance como prueba de ausencia de revocación. Referencia del alcance:
  [RFC 5280, secciones 5–6](https://www.rfc-editor.org/rfc/rfc5280.html).
- El backend comprueba restricciones del camino y revocación de firmante e
  intermedios. Se contrastan además issuer, firma de cada CRL y DER finales.
  Fallos de backend y formatos se devuelven como códigos estables, sin sujetos,
  seriales, XML, claves ni errores internos del backend.

El backend efectivo auditado en los ensayos es pyOpenSSL 21.0.0 y cryptography
3.4.8 de `/usr/bin/python3.10`. El manifiesto declara `OpenSSL` explícitamente;
un backend incompatible falla cerrado. No se modificó el runtime compartido.

## Pruebas y alcance pendiente

Las pruebas criptográficas usan claves, certificados y CRL efímeros sintéticos;
ninguno se instala como autoridad o credencial operativa. Los cinco métodos
nuevos ejercitan DTE firmado/verificado, rechazo de firmante/intermedio revocado,
path length y extensión crítica desconocida, CRL futura/vencida/al límite/antigua,
delta/scope/firma, pins, orden y tipos. Los 18 métodos puros DTE, incluidos los
13 anteriores, se ejecutan sin red; la aceptación Odoo completa exige también
el caso de ausencia de modelos/ACL/contadores paralelos y la regresión conjunta.
No sumar la ejecución pura y la ejecución Odoo como casos de negocio distintos.

Los metadatos dicen expresamente: comprobación de CRL suministradas al instante
de firma, sin consulta de la última CRL online. No certifican EKU/política fiscal
chilena, titular/mandato del emisor, confianza SII del ancla, emisión, aceptación,
tributación, folios o asignación de maestros. Tampoco prueban el estado actual
online de un certificado histórico con una CRL histórica válida. EnvioDTE y
custodia mantienen sus indicadores independientes sin heredar esta admisión.

Falta configurar autoridades operativas y su procedencia, política fiscal,
adquisición/cache y actualización comprobada de revocación, integrar la política
en cada consumidor autorizado y cerrar el flujo completo de documentos/guías,
CAF, folios, firma, respuestas y reintentos. No se usa el módulo para emitir al
SII real ni para eludir vencimientos. No se tocaron producción ni QA-Cerro.
