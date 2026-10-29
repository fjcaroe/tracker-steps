# Admisión de configuración, días no pagados y etiquetas — 29-10-2026

Aceptación de la pareja y upgrade C completada; resumen privado reproducible verificado.
Paquete de addons congelado en `6de3729a`, desde la canónica `c12c1f6e`;
se conserva además la integración concurrente T131 de `96e40339`.
Las herramientas/documentos posteriores no modifican el paquete probado.
La huella común comprende 343 archivos:
`585fdde3d437ed2dd971f81894c855093430e8493a543a43850e4cb179c511af`.
El tar congelado de Git tiene SHA256
`998880653cbc20a8e00ae75c5080338ccd813cbec3018eba287fab57b82d73d4`.

## Resultado y alcance

La pareja C prueba **420 casos en Community oficial y 276 en copia fresca de
Cerro**, cero fallos/errores y dos omisiones previstas por entorno. Community
instala 95 módulos con cero Enterprise; la referencia Cerro instala 389 y
conserva sus 140 Enterprise. **Esta referencia nativa no es una conversión.**
Las dos omisiones CE requieren la aprobación/observación monetaria del proveedor
nativo de lotes; las dos nativas corresponden a las guardas Community de días
teóricos e historial bloqueado, que ese motor no implementa.

Se cierran cuatro contratos de campos adicionales, **26 acumulados** en el
preflight original: nombre obligatorio del tipo, relación inversa de días no
pagados en estructura y ambas relaciones de etiquetas de regla. Quedan ocho
diferencias de campos, seis de columnas y tres observaciones de selecciones.
Este conteo no representa un porcentaje de la migración total ni de nómina.

| Componente | Versión probada |
| --- | --- |
| API OCA | 18.0.1.11.0 |
| Base Simple Digital–OCA | 18.0.1.4.0 |
| Contratos compartidos / referencia nativa | 18.0.1.13.0 / 18.0.1.3.0 |
| Núcleo DTE offline | 18.0.1.1.0 |

Odoo oficial queda fijado a `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` y
OCA a `4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`. El proveedor privado
Simple Digital sigue siendo el AGPL auditado de 52 archivos. No hay copia de
cuerpos OEEL, sustituto ficticio de `hr.payslip` ni cambios de dependencias.

## Configuración y almacenamiento real

[Obligatoriedad original](COMMUNITY_PAYROLL_OBLIGATORIEDAD.md) documenta el
nombre del tipo con `required=True` y NOT NULL real, con admisión anterior al
setup que aborta ante NULL. La categoría del maestro regla usa FK RESTRICT;
la línea histórica mantiene su columna independiente opcional y SET NULL.

Cinco campos permanecen opcionales en OCA por contrato real del proveedor:
tipo de estructura, estructura/categoría/código de regla y código de categoría.
La precondición explícita de adopción original exige sus valores y relaciones
completos, sin inventarlos ni alterar el cálculo OCA genérico legítimo. Todavía
no está conectada a un importador aprobado de los 120 maestros originales.

[Días no pagados](COMMUNITY_PAYROLL_DIAS_NO_PAGADOS.md) usa la tabla M2M
existente en ambos sentidos, copia/archivo y extremos completos por propietario.
Los permisos se verifican con actor normal incluso bajo un cómputo privilegiado.
Las dependencias efectivas de pago afectan sólo a borradores de la estructura
correspondiente; cambiar la política de A no recalcula el borrador ajeno B que
comparte un tipo de entrada. Historia cerrada conserva valores almacenados.
Una futura extensión de fórmula debe actualizar `PAYMENT_DEPENDENCIES`:
añadir únicamente un decorador no amplía esta lista explícita.

Se conserva la anomalía de bootstrap ya observada: estructura Chile de la
referencia CE ligada a compañía US, país de estructura NULL y tipo no pagado CL.
No se deduce ni cambia su propietario. La relación almacenada se conserva y
su procesamiento incompatible se bloquea. La adopción del ámbito original
continúa abierta; el builder no se ha saneado silenciosamente para pasar casos.

[Etiquetas contables](COMMUNITY_ETIQUETAS_NOMINA.md) conserva las dos M2M
físicas originales, sin columnas/tablas históricas nuevas en líneas. La
preparación real OCA une las etiquetas originales con las devueltas por su
proveedor tributario, sin cambiar importes, cuentas, impuestos o reparticiones.
Copiar una regla preserva todos los pares físicos autorizados; etiquetas visibles
incompatibles siguen bloqueando contabilización. Un miembro oculto impide copiar
incluso con caché, sudo, defaults explícitos o contextuales. No se aceptan comandos
de copia que creen, editen o eliminen maestros de etiquetas.

La observación nativa independiente C ejecuta cuatro combinaciones de signo y
`credit_note`, en copia de F y con rollback. Los movimientos observados quedan
**en borrador**; OCA publica en sus casos. El nativo mantiene los signos aun con
la bandera efectiva de nota de crédito, mientras OCA los invierte. Las etiquetas
siguen la cuenta configurada, con `tax_tag_invert=False`. No se ha certificado
equivalencia de reembolsos ni del flujo de aprobación/publicación. La admisión
CE a etiquetas fiscales activas/país compatible es más estricta que el dominio
nativo. Falta certificar lectura empleado/oficial de las proyecciones por rol.
La guarda completa cubre los dos M2M originales, no reconstruye etiquetas que
OCA hubiera filtrado antes de devolver su resultado tributario.

## Actualización y preservación

El ensayo privado C actualiza realmente una copia de la referencia CE F:
API 1.10→1.11 y Base 1.3→1.4. Compara 674 filas de veinte tablas; **672 filas
son literalmente idénticas**, incluyendo JSON, textos históricos y propiedades.
Sólo cambian dos `write_date` de maestros recargados por XML. Sus datos y
derivación fuente, aliases, logs y ventana UTC de SQL se cotejan expresamente;
no se presenta como igualdad literal de las 674 filas.

Conserva 529 IDs de modelo y 10.260 de campo, tres relaciones no vacías y
contadores. Verifica las cinco altas de campo esperadas, NOT NULL y ambas FK.
El origen F y su filestore quedan intactos; respaldo decodificado y runtime
sin red exterior. La lectura cerrada mantiene importes tras cambiar el sueldo
vigente y rechaza recalcular. El marcador de pagada del fixture es sintético:
**no certifica pagos reales ni liquidaciones comerciales**.

La copia fresca nativa conserva **921 tablas/proyecciones y 140 contadores de
negocio**, 59.048 XML IDs completos con `noupdate`, maestros, relaciones y ACL.
Las seis tablas de configuración mantienen exactamente 120 maestros/71 reglas.
De los 91 aliases de la cápsula, 88 son originales con PK íntegra y tres son
referencias nuevas del adaptador; no se anuncian 91 PK originales preservados.
El registro cargado se inspecciona en sólo lectura: 615 contratos en CE y
1.602 en nativo, sin leer documentos ni invocar métodos del proveedor CAF.
Dos PDFs reales del paquete Community y sus cuatro páginas se revisan visualmente,
incluyendo NULL, cero, negativo, BASIC visible/oculto y bloque conjunto de firma.
Eso no certifica equivalencia visual nativa ni adopta la acción original 462.

Todos los runtimes nuevos usan namespace sin red exterior, PostgreSQL por Unix
socket y HTTP sólo de loopback cuando lo requieren las pruebas/PDF. El ensayo
respalda/restaura bases nuevas con overlays, reserva de espacio y bloqueo
`/run/lock/steps-environments.lock`. A y B conservan sus diagnósticos: A tuvo
tres fallos de fixture corregidos; B pasó suites pero una revisión encontró la
pérdida de pares al copiar etiquetas. C incorpora el arreglo y su regresión.

## DTE y camino crítico pendiente

El [parser de recepción SII](../step_l10n_cl_edi_core/UPLOAD_RESPONSE.md) añade
22 casos funcionales puros y Odoo sobre `RECEPCIONDTE`, además de los 18 casos
CAF/DTE previos. Conserva bytes/hash y valida RUT/DV, contexto, filename,
timestamp local sin zona inventada, estado, TrackID y errores; rechaza XML
peligroso, ambiguo o fuera del perfil. Admite sólo el contexto esperado y una
recepción fallida no borra/reemplaza un TrackID existente.

Usa transcripciones de tres ejemplos públicos del manual SII con procedencia
y hashes; no son respuestas comerciales reales. Estado de recepción cero no
equivale a aceptación individual del DTE. La API no autentica el origen, firma,
reserva folios, cambia estados originales, hace HTTP ni emite al SII.

El inventario completo volvió a cotejarse antes de implementar: Cerro
380 instalados/140 EE/99 propios; Steps 310/123/19 y SyS 331/142/16. Las tres
capturas y sus huellas efectivas coinciden con el inventario previo. En repo
hay 124 manifiestos propios, 29 fuera de Cerro y 53 apps instaladas con caminos
Enterprise pendientes. La fuente recuperada inactiva `steps_transport` sigue
requiriendo procedencia/licencia y prueba funcional.

Prioridades pendientes:

1. Destino de adopción original sin colisiones: 24 IDs ocupados, 60 conflictos
   XML ID y acción 462 ocupada por otro tipo. Resolver maestros externos y ámbito
   de compañías/diarios, relación O2M/M2M y beneficios salariales sin renumerar.
2. Ocho brechas de campo/seis físicas, dos modos `input` y catálogo completo de
   `schedule_pay` aún desconocido. Los catálogos SQL vacíos no prueban paridad.
   Cerrar 12 clases de bloqueo de seguridad, ACL originales y reglas por rol;
   no se han concedido permisos ni cambiado membresías para ocultar diferencias.
3. Adoptar y certificar las 71 reglas/estructuras/entradas originales con los
   procesos reales de SyS: días, ausencias, agregación, cantidades, redondeo/YTD,
   reembolsos, contabilización, Previred y libro. El replay BASIC y los fixtures
   actuales son evidencia parcial; no certifican la nómina completa.
4. Motor DTE completo: almacenamiento/estados originales, folios concurrentes,
   CAF, firma, transporte autenticado aislado, respuestas de procesamiento,
   resultados individuales, conciliación y reintentos idempotentes.
5. Tesorería/conciliación/lotes, Calidad, Studio, Documentos/Firma, interfaz y
   consumidores restantes, incluidos todos los productos fuera de Cerro.
6. Conversión integral restaurable, exclusivamente Community y cero Enterprise,
   con pruebas de formularios/menús/flujos por rol y aceptación en Desarrollo.

**El 31 de octubre mantiene riesgo alto. No hay evidencia suficiente para
comprometer el cierre integral antes de esa fecha.** Producción conserva sus
140 Enterprise; ninguna extracción parcial resuelve el vencimiento. No se ha
escrito en producción, refrescado QA-Cerro, alterado vencimientos ni recalculado
pagadas/validadas. Calendar, Boolean bancario legado y 210233 siguen protegidos.
La automatización continúa; el corte productivo queda fuera de ella.

## Evidencia y siguiente prompt

Evidencia privada principal: `/opt/steps-validation/community-payroll-admission-20261029C`,
upgrade `/opt/steps-validation/community-admission-upgrade-20261029C`, preflight
`/opt/steps-validation/community-admission-preflight-20261029C` y observación
`/opt/steps-validation/community-native-tag-observation-20261029C`.
Copia local completa en
`C:/Users/tito4/.codex/local-artifacts/community-payroll-admission-20261029/acceptance-C`.
`summary.json`, manifiesto de hashes y recibo final permiten contrastar el
paquete congelado, fuentes/derivaciones, preservación, PDFs y handoff publicado.
Los dumps, datos privados y fuentes del proveedor permanecen fuera del checkout.

> Continúa desde la canónica remota actualizada, en worktree propio. Lee AGENTS,
> registro de ambientes, operación, workflow, continuidad, autonomía y
> COMMUNITY_ADMISION_NOMINA.md con sus referencias. Conserva la pareja C y sus
> límites. Prioriza la adopción real de los 120 maestros/71 reglas sobre OCA:
> destino sin demo/colisiones, identidad externa, beneficios, O2M/M2M y permisos
> originales antes de cambiar dependencias. Usa SyS como referencia real para
> certificar nómina, asientos, Previred y libro; no supongas equivalencia de
> notas de crédito/publicación. Avanza en paralelo DTE/firma/folios/respuestas y
> los restantes productos. Conserva Calendar, Boolean bancario, 210233 y todas
> las restricciones. Paquete exacto en Community y copia fresca, upgrade,
> preservación, evidencia privada, commits/push/integración y verify_handoff.
> Sólo termina la programación con las puertas integrales de autonomía cumplidas.
