# Período local y asistente real de nómina — 29-10-2026

Continuación vigente: [COMMUNITY_ENTRADAS_GUARDADAS.md](COMMUNITY_ENTRADAS_GUARDADAS.md).
Esta aceptación Período C se conserva como origen del upgrade siguiente.

Aceptación de pareja y upgrade Período C completada; resumen privado reproducible verificado.
Base canónica `94ab3d77`; paquete congelado en `5292a820`.
Huella común de 349 archivos:
`62c7cbc95ee8c3988b91d0ca203165175b77008893acf9e465232ede9f3d7ba2`.
Tar de Git:
`d780a2f947668c4ca4acea7d33c1699aca683b3e97a7005cdd54b25aaba3d596`.

Este bloque incorpora el consumidor nuevo de T135 y los seis casos de revisión
de T128, sin perder la aceptación histórica de
[Admisión C](COMMUNITY_ADMISION_NOMINA.md). No adopta los 120 maestros/71 reglas
originales ni convierte integralmente Cerro con cero Enterprise.

## Implementación

`step_payroll_batch_period 18.0.1.1.0` conserva AGPL-3 y los modelos reales
`hr.payslip.employees`, `hr.payslip` y `hr.work.entry`. Los cinco consumidores
HR se prueban juntos; el builder conserva las licencias por módulo. La fuente
canónica mantiene las dependencias nativas. Sólo el overlay Community derivado
cambia prerrequisitos/aliases hacia OCA y los núcleos reales, con hashes de cada
archivo fuente y derivado; no crea módulos vacíos Enterprise.

El preflight del asistente comprueba el lote real abierto, compañía activa,
fechas, selección M2M completa de empleados y contratos existentes mediante
SQL/API y permisos normales. Un recibo previo del empleado en el lote, incluso
protegido u oculto, impide crear otro. No confirma revisiones de parámetros,
reasigna contratos ni activa empleados archivados.

Los límites del período usan la zona del calendario contractual y días civiles
completos. Las entradas se contrastan con sus contratos, empleados, compañías y
tipos originales, incluyendo IDs que un record rule pudiera ocultar. Detecta
conflictos almacenados, tipos ausentes y solapamientos reales, sin llamar al
checker del proveedor que escribe estados. Una notificación identifica al
trabajador y las horas locales; el conflicto de septiembre no bloquea octubre.
Se prueban también jornadas Santiago de 23/25 horas y entradas nocturnas.

El token interno para el buffer nativo no puede forjarse mediante contexto RPC.
Las acciones de retorno eliminan esa capacidad antes de serializar. La ruta
nativa conserva después su proveedor original; no se afirma que ese proveedor
nunca genere entradas nuevas durante su operación ordinaria.

### OCA y días reales

La fuente LGPL OCA fijada llama a `get_payslip_vals` sobre un recordset vacío.
Su helper de días puede por ello caer al calendario teórico, aun con una
estructura que usa entradas. El adaptador conserva los demás valores del
proveedor y sustituye los días antes de crear el recibo usando la API real sobre
un preview ORM `new()` con empleado, contrato, compañía, estructura y fechas
reales. No es otro modelo de liquidación, no se persiste y no se llama a
`compute_sheet` ni se evalúan reglas salariales sobre él.

Antes de la primera creación se comprueban todos los empleados y la cadena de
admisión de configuración existente. La creación y cálculo posterior usan el
asistente y motor OCA reales dentro de un savepoint. No se generan asistencias
ni se modifican las entradas originales para completar el período.

La ruta OCA admite actualmente un contrato abierto inequívoco por empleado,
período completo dentro de sus fechas y estructura con `use_work_entries`.
Contratos parciales, varios contratos y la política OUT siguen pendientes de
certificación; no se habilita una prorrata o un flag temporal que cambie importes
entre cálculo y recálculo. Una ausencia de entradas reales bloquea la operación.

### Entradas originales pendientes

Se corrigió otra omisión del recordset vacío: el `get_inputs` OCA puede devolver
una lista vacía aunque las reglas declaren `hr.rule.input`. Antes de crear un
recibo se leen los descriptores completos por su FK real y las asociaciones
físicas `input_line_type_ids` de estructuras, tras verificar ACL de registro y
campo. Se comprueban también extremos ocultos o archivados de las reglas efectivas
y los tipos asociados; no se auditan reglas archivadas fuera de esa selección.
Se revalida la selección antes de devolver valores al proveedor.

En esta versión cualquier descriptor o tipo de entrada configurado bloquea
el lote OCA: todavía falta la ruta para admitir valores originales del período,
aunque existan en otra nómina. No se generan importes cero como sustituto,
ni se infieren conceptos desde nombres, códigos o fórmulas. Un tipo global sin
asociación a esta estructura no bloquea el lote. Cargar y certificar valores
reales de entradas continúa como siguiente puerta funcional.

### Previews y protección histórica

Base Simple Digital–OCA **18.0.1.5.0** permite verificar la configuración del
preview real sin enviar un `NewId` a PostgreSQL. Los registros guardados siguen
leyendo todos los días físicos con sus permisos; los previews con origen suman
los días originales y los visibles del preview. El campo de relación se autoriza
explícitamente incluso con caché caliente y `sudo` entrante.

Un origen guardado cerrado/pagado/histórico se rechaza antes de permitir una
apariencia de borrador. La lectura histórica conserva sus snapshots; no obtiene
importes desde sueldo, reglas o política actuales. No hay columnas o tablas
paralelas nuevas.

## Pruebas y actualización

La pareja C pasa **439 casos Community y 294 nativos**, cero fallos/errores. Hay dos omisiones CE
previas y cinco nativas: las dos anteriores y tres casos de generación que
ejercitan exclusivamente el adaptador OCA. Los nueve casos neutrales de período
comprueban admisión, formulario real, notificación, ACL, compañías y fechas;
no certifican el cálculo monetario del proveedor nativo.

Los tres casos OCA usan el asistente real: creación con horas existentes,
rechazo de datos/políticas/entradas ausentes antes de crear y rollback por una
regla privada que falla realmente. No se simula una respuesta exitosa de motor.
El caso Base adicional comprueba el preview, país, campos y origen protegido.

El upgrade privado parte de la Community aceptada de Admisión C:
API **1.11 permanece 1.11**, Base **1.4→1.5**. Compara 674 filas de veinte tablas,
conserva literalmente 672 y audita sólo dos `write_date` de maestros recargados
por XML. Preserva **529 IDs de modelo, 10.265 IDs de campo**, tres relaciones
no vacías, propiedades JSON y contadores, sin campos nuevos. El origen C y su
filestore quedan intactos; el respaldo se decodifica antes de restaurar.

El fixture de pagada y los datos de cálculo son privados/sintéticos sobre
modelos reales. No acreditan pagos comerciales ni certifican las 71 reglas.
La secuencia privada `no_gap` comprueba rollback transaccional; **una secuencia
OCA `standard` puede consumir un número ante un error tardío del proveedor**.
No se cambia su implementación, reinicia ni retrocede un correlativo para ocultar
ese comportamiento. Los errores conocidos del preflight bloquean antes de crear.

A queda como diagnóstico: 1 fallo/1 error de fixtures y errores de aprovisionar
vacaciones fuera del flujo probado; no se ejecutó su rama nativa. B pasó los
12 casos de período pero falló un fixture de preview al invalidar su caché después
de cambiar compañías. C reconstruye los previews desde IDs/fechas originales
y conserva los roles del actor. Sus maestros de prueba se aprovisionan como autor del fixture;
la asignación operativa de vacaciones no se declara certificada por este bloque.
Las aserciones de previews sólo de lectura conservan su caché virtual: el wrapper
de `assertRaises(AccessError)` de Odoo lo borra y no sirve para ese escenario.

Community instala **96 módulos, cero Enterprise**; la copia fresca nativa
instala **391 y conserva 140 EE**. Es una referencia nativa, no una conversión.
Se preservan **921 tablas/proyecciones y 140 contadores comerciales** (1.061
contratos), **59.079 XML IDs originales con noupdate**, saldos e históricos.
El auditor verifica los IDs originales de modelos, campos, ACL, grupos, reglas,
menús y relaciones; las tres ediciones de mensajes de campos HR se auditan
mediante la política explícita existente. Las comprobaciones pasivas posteriores
conservan 615 contratos de registro Community y 1.602 nativos.
Los dos PDFs nuevos del servidor, cuatro páginas renderizadas e inspeccionadas,
conservan cero, negativos, NULL, visibilidad BASIC y el bloque de firma.
No equivalen a una certificación de importes de clientes.

La verificación offline reproduce las derivaciones Community, herramientas y
paquete exacto de 349 archivos contra Git; comprueba el upgrade y la clasificación
88 XML IDs originales + 3 aliases nuevos de referencia. Las observaciones
nativas previas de etiquetas siguen vigentes: borrador y reembolsos no son
monetariamente equivalentes a la contabilización OCA; no se declara paridad.

## Estado acumulado y siguiente bloque

El inventario inicial capturó Cerro **380 instalados/140 EE/99 propios**.
La canónica concurrente `72ae351b` incorporó Packing T132/T134: el inventario
final registra **381/140/100**, con `step_packing_ticket_revision` nuevo y
recepciones 1.1→1.2. Steps mantiene **310/123/19** y SyS **332/142/17**,
incluido el período nativo de T135. Se conservan las dos capturas y sus auditores.
Los auditores sólo difieren en finales de línea LF/CRLF, con ambos hashes comprobados.
El repo tiene ahora **126 manifiestos propios**, **30 fuera de Cerro**; hay
**54 apps propias instaladas con caminos EE**, incluida la nueva app Packing.
El aumento desde 53 viene de ese alcance concurrente, no del retiro de una puerta.
Los cambios de Packing y los tres cambios de fuentes de empresas en Cerro
se distinguen de esta migración.
`steps_transport` sigue recuperado como fuente inactiva, pendiente de procedencia
y aceptación. Véase la matriz Enterprise vigente.

Siguen abiertos ocho contratos distintos de campo, seis físicos y la adopción
de IDs/ACL/maestros/relaciones originales: **26 contratos de campos cerrados**
continúan siendo el acumulado de Admisión C. Se mantienen los 12 bloqueos de
seguridad, las colisiones de 24 IDs/60 XML IDs y la acción 462. Este bloque no
los convierte en aprobados por haber calculado un fixture.

Las ocho brechas concretas son `structure.rule_ids` (O2M/M2M),
`structure.type_id` obligatorio, `structure.type.salary_benefits_ids` ausente,
traducción física de `input.type.name` y obligatoriedad de
`rule.category_id`, `rule.code`, `rule.struct_id` y `rule.category.code`.
Cerrar la propiedad real de reglas y el modelo de beneficios antes de migrar
identidad; no basta con cambiar la dependencia del manifiesto.

Priorizar ahora identidad original sin demo/colisiones, estructuras/71 reglas
y entradas reales con SyS como referencia; completar períodos parciales y
certificar redondeo/YTD, reembolsos, asientos, Previred y libro. DTE conserva
los 40 casos previos de CAF/recepción, pero firma, folios, transporte, respuestas
individuales y estados originales siguen en el camino crítico. Faltan también
los restantes consumidores, Tesorería, Calidad, Studio/Documentos/Firma y la
conversión integral restaurable con cero Enterprise y aceptación en Desarrollo.

**El 31 mantiene riesgo alto y no está resuelto.** No se escribe en producción,
refresca QA-Cerro, recalculan pagadas, alteran vencimientos ni emite al SII.
Calendar, Boolean bancario y 210233 continúan protegidos. La automatización sigue
hasta las puertas de autonomía; el corte productivo queda fuera.

Evidencia privada: `/opt/steps-validation/community-payroll-period-20261029C`,
`/opt/steps-validation/community-period-upgrade-20261029C` y
`/opt/steps-validation/community-period-preflight-20261029C`.
Copia local en
`C:/Users/tito4/.codex/local-artifacts/community-payroll-period-20261029/acceptance-C`.
El recibo `accepted-evidence-C-final.receipt.json` queda en su carpeta padre,
junto al tar final; registra hashes, resumen y handoff publicado.

> Continúa desde la canónica remota actualizada en worktree propio. Lee AGENTS,
> registro, operación, workflow, autonomía, continuidad y COMMUNITY_PERIODO_NOMINA.md.
> Conserva Período C y Admisión C. Cierra la adopción real de maestros/IDs/ACL y
> estructuras/reglas originales; no importes sobre demo ni inventes valores.
> Usa SyS para entradas/71 reglas y certificación financiera. Resuelve valores
> originales de entradas y períodos parciales sin teóricos persistidos, sin
> ocultar límites de secuencias o reembolsos. Avanza DTE/firma/folios/respuestas y
> resto de productos. Respeta todas las restricciones; paquete exacto en ambos
> motores, upgrade, preservación, evidencia privada, push/integración y handoff.
