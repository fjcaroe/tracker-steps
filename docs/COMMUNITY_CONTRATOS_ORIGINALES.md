# Almacenamiento original y proyección de reglas — 30-10-2026

Base aceptada: [arranque frío F](COMMUNITY_ARRANQUE_ORIGINAL.md), canónica
`bea2a3eb`. Rama propia `codex/community-original-contracts-20261030`.
La implementación está guardada; aceptación C y cierre de evidencia pendientes.
No acredita adopción de los maestros originales, certificación ni conversión.

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

## Validación pendiente de cierre

A instaló el motor NUMERIC y probó formularios, pero falló en fixtures y en la
creación masiva real. B pasó los 25 casos; la guarda rechazó dos logs ERROR de
rechazos Infinity deliberados en PostgreSQL. La consulta específica esperada
ahora silencia sólo su logger y conserva las aserciones de error/rollback;
cualquier otro error SQL o de prueba sigue haciendo fallar la aceptación.
A/B son diagnósticos. C repite la pareja en bases nuevas y después una regresión
Community con el perfil normal, bajo el bloqueo compartido y sin solapar upgrades.

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
