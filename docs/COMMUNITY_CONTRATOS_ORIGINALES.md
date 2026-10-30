# Almacenamiento original y proyección de reglas — 30-10-2026

Base aceptada: [arranque frío F](COMMUNITY_ARRANQUE_ORIGINAL.md), canónica
`bea2a3eb`. Rama propia `codex/community-original-contracts-20261030`.
C aceptado con API `18.0.1.14.0`, desde el paquete congelado
`67972575888ed11a71edd4d566a3594f69bde37c`. La colección C2 corrige únicamente
la serialización del flag de igualdad de dependencias que el collector ya exigía;
no es otro ensayo ni altera los resultados C. No acredita adopción de maestros,
certificación financiera ni conversión integral.

## Contrato real implementado

API `18.0.1.14.0` declara `hr.payslip.input.amount` con el `Float(digits=False)`
oficial de Odoo fijado. Conserva NUMERIC ilimitado, NULL y ausencia de default;
no añade precisión fija ni redondeo. El API Python, su caché y el caster SQL de
Odoo siguen usando Float binario: esto no certifica aritmética Decimal financiera.
La precisión original se comprueba mediante texto SQL, sin convertirla a Float.
Lecturas y rechecks no deben reescribir el dato almacenado.

Una guarda de catálogo corre primero en pre-init, pre-migración y `_auto_init`.
Exige OCA real, cero Enterprise, tipo base NUMERIC/typmod -1/nullable/sin default.
Rechaza Float8 incluso vacío, dominios y precisión/default/NOT NULL incompatibles;
no lee importes, rellena NULL, materializa código/contrato ni ejecuta ALTER.
Falta de tabla sólo se admite en la instalación real del API, nunca en upgrade.

OCA inicializa su dependencia antes del pre-init del API. Para una instalación
nueva se deriva un overlay LGPL del motor fijado
`4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e`: cambia exclusivamente el keyword
`digits=False` de su campo `amount` desde el primer `_auto_init`. Conserva módulo,
modelos, métodos, vistas, datos, permisos y todos los demás bytes; no modifica el
checkout OCA ni el framework. Builder, hashes por archivo, sello y objetos Git
originales permiten reproducirlo offline. Este overlay es parte del paquete frío;
no autoriza convertir automáticamente las referencias antiguas Float8.

La nueva API explícita de estructuras planifica, comprueba y materializa la
proyección `struct_id` original hacia la M2M real de OCA. Recibe pares enteros
explícitos, exige FK actual idéntica y cobertura completa, incluye archivados,
comprueba actor normal/campos/registros y rechaza extras, comparticiones, ciclos,
propietarios NULL, referencias ocultas y propietarios inferidos. Sólo inserta
los pares faltantes con locks deterministas/NOWAIT, savepoint y caché coherente.
No llama `write` de maestros ni altera sus timestamps, IDs o correlativos;
no lee/recalcula nómina histórica. Complementa el preparador pre-ORM existente.
No modifica la política genérica OCA de copia, campos opcionales o compartición.
Tampoco cambia el tipo de metadata M2M a One2many ni adopta identidad original.

El ensayo reveló y corrigió además un error real de creación masiva: el enlace
primario se hacía regla por regla después de guardar todas las FK del lote.
La primera validación veía las demás reglas sin membresía. Ahora enlaza el grupo
completo de cada estructura dentro de la transacción/guardas originales.

## Identidad y límites

La auditoría readonly confirma que los cuatro tipos residuales comparten alias,
modelo, res_id y noupdate canónicos de `hr_contract`. No se deben reubicar por
considerarlos cuatro maestros ajenos. Faltan valores originales (política,
secuencia, estructura por defecto y auditoría) y PK de `ir.model.data`.
La acción 462 sí está ocupada por otra acción; falta resolver su identidad y
referencias. Los candidatos genéricos por número no prueban pertenencia.
El planner recorre FK/M2M, campos polimórficos y Many2one sin FK física; conserva
bloqueos para bindings no demostrados y rutas serializadas/dinámicas.

Los 120 maestros/71 reglas de la cápsula C siguen intactos y sin adoptar.
Persisten siete diferencias de campos, cinco físicas y doce bloqueos de seguridad;
la proyección funcional no convierte esa metadata. Beneficios requiere un puente
real: `payroll_contract_advantages` libre no equivale por nombre al catálogo nativo.
También siguen pendientes las columnas `code`/`contract_id` almacenadas de OCA
frente a relacionados no almacenados nativos. NUMERIC no resuelve esa frontera.

## Aceptación C y custodia reproducible

A instaló el motor NUMERIC y probó formularios, pero falló en fixtures y en la
creación masiva real. B pasó los 25 casos; la guarda rechazó dos logs ERROR de
rechazos Infinity deliberados en PostgreSQL. La consulta específica esperada
ahora silencia sólo su logger y conserva las aserciones de error/rollback;
cualquier otro error SQL o de prueba sigue haciendo fallar la aceptación.
A/B son diagnósticos. C repitió la pareja en bases nuevas y después la regresión
Community normal, bajo el bloqueo compartido y sin solapar upgrades.

| Entorno | Casos / omisiones | Instalados / Enterprise | Alcance |
| --- | --- | --- | --- |
| Community frío C | 25 / 0 | 94 / 0, cero demo | 12 casos previos + 13 de almacenamiento/proyección; formularios, defaults, menú, permisos y rollback. |
| Copia fresca Cerro C | 294 / 6 | 391 / 140 | Referencia nativa; no conversión. |
| Community normal C | 473 / 3 | 96 / 0 | Repite 460 casos normales + 13 nuevos con las semillas de referencia, sin adopción original. |

Cero fallos/errores en los tres contextos y 58 pruebas puras aprobadas. Las suites
se solapan: no se suman como 792 casos únicos. Las omisiones son adaptadores de
otro proveedor y el replay mensual BASIC privado, cuyo input no se adjuntó a estos
dos contextos. La referencia BASIC/SyS anterior permanece conservada; este bloque
no la vuelve a certificar ni certifica las 71 reglas, Previred o libro.

La pareja comparte 361 archivos, SHA256
`3b14a4dd45af56bbf88ce79a70142e6ce6977578cd6e2405f0547944041ad4c0`.
El perfil normal tiene 364: mismos 22 addons propios y los 52 archivos del
proveedor normal frente a 49 fríos; su derivación se verifica por separado.
Tar Git congelado C SHA256
`8f2b060195cb54f76ffbdc9694caf4a0fe4036304853dc3ac3e2c2a34049e7e5`.

El motor OCA contiene 144 blobs originales, ligados por sus hashes Git al commit
fijado y a 14 objetos de árbol exportados. Se reproduce cada byte original y el
único keyword modificado sin ejecutar código de artefactos. No se confunde esta
prueba completa de su fuente con la atestación de definiciones de otras dependencias.

La referencia nativa conserva 921 tablas/proyecciones, 140 contadores y 59.079
XML IDs/noupdate originales, además de históricos y metadata. De 1.061 snapshots,
1.060 son literales; el restante tiene el mismo valor numérico y un testigo nuevo
reconstruido desde su propio respaldo: cinco filas/19 columnas completas, sólo
ceros decimales finales en una celda. No se reutilizó el testigo F. El verificador
rechaza cualquier otro delta y no declara esa representación idéntica en bytes.

Dos capturas readonly confirman fuente/cápsula C intactas, 120 maestros/71 reglas,
cuatro identidades canónicas compartidas, cero conflictos XML IDs nominales,
siete diferencias de campos, cinco físicas y doce bloqueos de seguridad. Se
mantiene el conflicto de acción 462, tres observaciones de selección y una ACL.
Los 71 pares de las pruebas son fixtures reales OCA; no son importación ni
certificación de las 71 reglas chilenas originales.

Evidencia privada: `community-original-contracts-20261030/acceptance-C2`.
Incluye snapshots AGPL/LGPL, objetos Git, logs, preflight, plan de identidad,
inventario completo, omisiones revisadas y verificador offline. Excluye dumps,
filestore, credenciales y cuerpos OEEL. La colección inicial C se conserva como
diagnóstico de custodia; el booleano ausente no se inventó en la aceptación.

- Exportación C2 SHA256 `1ab26b4354a888d3c11e0968dd4e6b9f97624cbfb6c8027f755d2337e2f3881d`.
- Testigo representacional C SHA256 `356df7b4d1bf0d7c0c7c2b877e6aebaca36fc01b9cc142a8b0ca03407adcb6dd`.
- Resumen completo SHA256 `61d7dcbf9cdf1221a888f13eb39af18fa30e82bfc74cc1d5f975747caeb3598c`.

La custodia final añade reproducción final, pruebas, inventario y handoff a un
manifiesto/recibo privado junto al tar final en
`/opt/steps-validation/community-original-contracts-20261030/`.

El paquete conserva 21 addons propios y el proveedor frío de F; cambia sólo API.
No hay cambios de dependencias. El inventario previo cubrió todos los productos,
fuentes privadas y apps fuera de Cerro: 381/140/100 en Cerro, 310/123/19 en Steps,
332/142/17 en SyS (instalados/Enterprise/propios). Sólo Packing cambió por otra
entrega validada. La matriz mantiene 54 apps instaladas con caminos Enterprise,
126 módulos propios y 30 fuera de Cerro.

## Camino crítico siguiente

Adoptar realmente identidad/maestros y cerrar beneficios, referencias externas,
acción 462, ACL y almacenamiento del motor. Certificar las reglas chilenas con
SyS, días/ausencias, entradas, redondeos/YTD, asientos, Previred y libro.
Mantener DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad,
Studio/Documentos/Firma y demás productos; ensayar conversión integral restaurable
con cero Enterprise y aceptación funcional. **El 31 mantiene riesgo alto.**

No escribir en producción, refrescar QA-Cerro, retirar allí Enterprise ni tocar
vencimientos. No recalcular pagadas/validadas, emitir al SII real, enviar mensajes,
copiar OEEL o inventar maestros. Se conservan Calendar, Boolean bancario y 210233.

Durante el cierre se integró la entrega concurrente T138 de `step_hr_contract_days`
18.0.1.2.0, documentada en [su acta](T138_DIAS_NOMINA_20261029.md). Ese módulo queda
fuera de estos 22 addons y conserva su propia evidencia de cuatro destinos;
este bloque no lo publica ni lo acredita convertido a Community. Su política
real de faltas/maestro unpaid debe entrar en el siguiente puente de consumidores.
No sobrescribirla con los supuestos previos del proveedor.

> Continúa desde la canónica actualizada en worktree propio. Lee AGENTS, registro,
> operación, workflow, autonomía y COMMUNITY_CONTRATOS_ORIGINALES.md. Conserva C:
> 25 fríos/294 nativos/473 normales y su colección C2 sellada. Revisa inventario
> completo y T138 antes de implementar. Prioriza la adopción real de identidad y
> 120 maestros/71 reglas: cuatro tipos con identidad canónica compartida, PK de
> metadata, beneficios, referencias externas/acción 462 y ACL. La proyección ya
> funciona, pero no cierra las siete brechas/cinco columnas ni convierte M2M/O2M.
> Preserva NUMERIC/NULL sin cast Float8 y cierra code/contract_id relacionados,
> demás tablas históricas del motor y consumidores; incorpora T138 sin recalcular
> pagadas. Certifica reglas chilenas con SyS, días, entradas, redondeo/YTD,
> asientos, Previred/libro. Mantén DTE/CAF/SII y conversión integral cero EE.
> Prueba el paquete exacto en Community y copia fresca; respeta todas las
> restricciones, guarda/push, integra sólo lo validado y verifica handoff.
