# Tesorería, días reales y TED — 30-10-2026

Base canónica inicial `e847d54f`; rama propia `codex/community-multifront-20261030`.
Productos congelados en `7ab214029c3a26f75ddc62527273ee8d60017bb4`.
Se integró durante el trabajo la canónica concurrente `c0c36173`: política de
paridad Cerro/QA-Cerro y herramientas T138, sin modificar estos 27 addons ni
publicar los prototipos Community. La regla conserva el alcance privado y no
autoriza refrescar QA-Cerro.
Complementa la aceptación [C/C2](COMMUNITY_CONTRATOS_ORIGINALES.md), que permanece
conservada. No reemplaza sus bloqueos de adopción original ni acredita conversión
integral, nómina chilena certificada o vencimiento resuelto.

## Implementación

- Tesorería: núcleo `18.0.1.3.2`, consultas Community `18.0.1.1.1` y puente
  `step_account_treasury_reports` `18.0.2.0.0`. Las cinco acciones abren consultas
  reales sobre contabilidad: conciliación bancaria, cuentas corrientes, flujo,
  cuentas por cobrar y por pagar. Formulario, consulta, CSV y PDF con actor normal.
  El puente ya depende del proveedor Community; no modifica acciones globales de
  `account_reports`. Conserva IDs/atributos/grupos/flags de los menús originales;
  la única diferencia admitida en ellos es su acción hacia el formulario específico.
  Propiedad independiente y lifecycle real protegen aliases incluso con noupdate
  original falso. Una regla global nueva aísla la consulta temporal por autor,
  además de su empresa; deniega lectura, caché, exportación y PDF ajenos con sudo
  entrante. No amplía ACL ni roles.
- T138 `step_hr_contract_days` `18.0.1.3.0` y puente real
  `step_hr_contract_days_oca` `18.0.1.0.0`. Conservan la política aprobada de
  faltas, mensualidad, contratos parciales y atrasos. El puente consume días e
  importes de la cadena API–AGPL–T138 con entradas de trabajo reales. Autoriza
  registros/campos/fuentes completos antes de modificar, protege lotes con historia
  cerrada y restaura cache/SQL ante fallo. No declara campos/modelos/tablas/ACL
  paralelos ni cambia dependencias del núcleo nativo. El salario cerrado se lee
  desde almacenamiento; no se revaloriza con el sueldo o política actuales.
- DTE: `step_l10n_cl_edi_core` `18.0.1.2.0` y custodia `18.0.1.1.0` verifican
  criptografía TED/FRMT, vínculo exacto al CAF y contexto, importes enteros/con
  signo o decimales de exportación. FRMA exige un ancla explícita. La API de
  custodia comprueba sus bytes originales y mantiene falsa la certificación de
  autoridad/SII: no acepta una clave RPC como confianza oficial, activa CAF,
  reserva folios, firma documentos de negocio ni emite. Ver [contrato TED](../step_l10n_cl_edi_core/TED.md).

## Aceptación y preservación

El paquete común contiene 27 addons propios y 52 archivos del proveedor normal
AGPL: **442 archivos**, fingerprint
`b5575a5e2920c4383a482f3270ee1ae74b041081c470a7ae40b1830072910957`.
Tar Git congelado SHA256
`761edcfbc86820c75076b34f6b6041ce9dded3530fb8096cef8f9e9663582c7b`.
Los valores de todas las acciones client originales se comparan con tipos JSON
estrictos. Sólo se admite write_date para siete aliases propios explícitos, ligados
a sus IDs/modelos/flags originales; cada cambio queda registrado con antes/después.
write_uid, parámetros, tags, aliases y cualquier otra acción siguen exactos;
ninguna excepción puede alcanzar un propietario account_reports. Las capturas raw
no se modifican. El motor OCA conserva el overlay NUMERIC de C y su prueba de 144 blobs/14 árboles
ligados al commit fijado; no convierte las bases Float8 anteriores.

| Contexto | Resultado | Alcance |
| --- | --- | --- |
| Community oficial H | 576 casos / 3 omisiones, cero fallos/errores; 114 instalados, cero EE | Regresión normal completa, dos PDF de nómina almacenada; no adopción original. |
| Copia fresca Cerro H | 391 casos / 6 omisiones, cero fallos/errores; 393 instalados, 140 EE | Referencia nativa; no conversión. |

Las omisiones corresponden a adaptadores del otro proveedor y al replay mensual
BASIC privado sin input de días reales. Se conserva la referencia anterior; no
se inventan asistencias para aprobarlo. La referencia nativa usa el proveedor
AGPL original fijado, no carga el proveedor normal transformado ni OCA.
Las suites se solapan; no se suman como casos únicos. Las pruebas puras separan
46 verificaciones de herramientas de 17 CAF y 9 TED. El cierre añade 19
comprobaciones de custodia que se solapan con las anteriores; no son 91 únicas.
La instalación real verifica 25 versiones en CE y 23 en nativo, con 22 módulos
propios requeridos por modo y sus motores reales. Los ensayos A–E son
diagnósticos: corrigieron el selector/instalador, fuentes privadas de prueba
solapadas y un bypass real de propiedad de informes. No son aceptación parcial. F se canceló mientras esperaba el bloqueo, antes
de crear base o iniciar upgrade. G terminó únicamente Community; se evitó repetir la referencia con el fixture
de picking.batch ya identificado. H repite la pareja con las cinco secuencias
privadas y todas las guardas vigentes. No se reinicia ningún contador original.

La licencia médica LIC original mantiene íntegra su relación con la estructura
del proveedor en otra compañía. Se comprueban los valores devueltos y la negativa
a adoptar una política oculta; no se almacena su importe como si esa configuración
estuviera adoptada. El almacenamiento médico con divisor 31 se prueba con una
relación privada explícita, sin vecinos externos. La guardia financiera de Chile
incompleto continúa denegando el cálculo. No se certifican las 71 reglas por pasar
fixtures de motor. Cerro carece de liquidaciones calculadas; la referencia
real de SyS sigue pendiente de replay/certificación con sus cohortes originales.

La comparación conserva 921 tablas/proyecciones, 140 contadores y 59.079 XML IDs
con sus flags originales; históricos exactos. Son 1.061 contratos de snapshot:
1.060 literales y el cambio representacional de stock_package_type con cinco
filas/19 columnas completas reconstruidas de SU propio respaldo, sin Float ni
redondeo. El log_cnt, last_value e is_called de los contadores permanecen exactos.
La auditoría comprueba todas las identidades originales bajo las políticas
explícitas de cinco acciones, siete timestamps y tres ayudas HR ya admitidas.
Los raws no se normalizan en disco. Las acciones client globales de account_reports permanecen exactas.

Custodia offline reproducida contra Git, 27 addons y proveedor normal52 exactos,
144 blobs/14 árboles OCA, formularios/PDF, versiones y conservación:

- Cápsula privada: `community-multifront-20261030/acceptance-H`, 471 archivos.
- Exportación SHA256 `3a5e7836c72f297ca21471ddcd5f47f6ba92af97995421a622722431b163fce7`.
- Testigo representacional SHA256 `659736af8ec657bde3f49fe36562f33cee62f545b3f1ba8606a97d1b8afb47f9`.
- Resumen verificado SHA256 `50405902234120999709aa725af37732b208f773ffd96b3e7a665e8df1da8ebe`.
- Inventarios inicial/final readonly de Cerro/Steps/SyS: metadata idéntica;
  los hashes de herramientas LF/CRLF se registran por separado.

El collector excluye dumps, filestore, credenciales y cuerpos OEEL; el verificador
no ejecuta Python de artefactos. Su única reparación de custodia posterior al
paquete exige los 15 aliases bancarios reales de ambos modos, incluidos los dos
campos del configurador manual ahora registrado; no altera ni repite Odoo verde.
El sello final incluye cápsula, resumen, pruebas, tar Git y handoff con manifiesto
y recibo privado en `/opt/steps-validation/community-multifront-20261030/`.
La rama preserva la integración concurrente c0c36173; sólo se integra este bloque
validado, sin publicar prototipos en ningún ambiente activo.
Se usan respaldo fresco, overlays y bases nuevas, bloqueo compartido y reserva
5/2 GiB. No hubo publicación productiva, refresh QA-Cerro, cambio de vencimientos,
recalculo de pagadas, emisión SII ni copia OEEL. Calendar, Boolean bancario legado
y cuenta 210233 descontinuada conservan sus límites.

## Estado acumulado y siguiente bloque

La [matriz del 30](COMMUNITY_INVENTARIO_ENTERPRISE_20261030.md) cubre todos los
productos y fuentes privadas: Cerro 381/140/100, Steps 310/123/19, SyS 332/142/17
(instalados/EE/propios). Hay 127 módulos propios en repo, 31 fuera de Cerro y
**54 apps propias instaladas con caminos EE pendientes**. El puente opcional de
informes no estaba instalado en Cerro/SyS: su cierre no reduce artificialmente 54.

Prioridad inmediata: [coadopción original y certificación SyS](COMMUNITY_PROXIMO_BOOTSTRAP.md).
Faltan cerrar referencias externas y acción 462, preservar los cuatro tipos
canónicos in situ, adoptar los 120 maestros/71 reglas con sus IDs y política,
beneficios reales y almacenamiento restante del motor. Persisten los bloqueos de
seguridad/metadata documentados en C; no se resuelven renombrando dependencias.
Luego: equivalencia de reglas chilenas, días/entradas/redondeos/YTD, asientos,
Previred/libro con cohortes privadas SyS y aceptación de discrepancias reales.

También faltan DTE/CAF/folios/firma/respuestas/reintentos SII, lotes y conciliación,
Calidad, Studio/Documentos/Firma y los demás productos. La puerta final sigue
siendo una copia integral restaurable, operativa y aceptada con cero Enterprise,
preservación de identidad/permisos/históricos/saldos/correlativos. **El 31 mantiene
riesgo alto; no hay una estimación fiable de cierre total ni un porcentaje de
funcionalidad deducible del conteo de manifiestos.** La automatización continúa;
el corte productivo queda fuera.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro,
> operación, workflow, autonomía, COMMUNITY_MULTIFRENTE.md y
> COMMUNITY_PROXIMO_BOOTSTRAP.md, conservando C/C2 y la pareja H. Revisa inventario
> completo y fuentes privadas antes de implementar. Prioriza el bootstrap nuevo
> de coadopción original: referencias externas explícitas, acción 462 sin colisión,
> cuatro tipos compartidos in situ y preservación atómica de maestros/aliases/71
> pares. Cierra beneficios con un puente real y conserva los bloqueos no resueltos.
> No mezcles fórmulas Cerro/SyS ni recalcules sus pagadas; usa cohortes privadas
> para certificar reglas, entradas, días, YTD, asientos, Previred y libro. Avanza
> frentes independientes autorizados de DTE/CAF/SII y Tesorería sin simular motores
> ni activar folios sin autoridad/almacenamiento demostrado. Mantén todas las
> restricciones y puertas integrales. Prueba el paquete exacto en Community y
> copia fresca Cerro, guarda evidencia privada, commit/push, integra sólo lo
> validado y ejecuta verify_handoff.py --require-pushed. No declares resuelto el 31.
