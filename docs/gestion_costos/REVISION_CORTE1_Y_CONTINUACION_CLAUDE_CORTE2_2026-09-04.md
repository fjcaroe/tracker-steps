# Revisión del Corte 1 y continuidad para Claude — Corte 2

## Propósito y autoridad

Este documento revisa la implementación `18.0.13.0.0` descrita en
`HANDOFF_FASE7_CORTE1.md` y define el trabajo siguiente. Es un relevo técnico,
no una autorización de despliegue, commit, push, reinicio de servicios ni
modificación de otros addons o ambientes.

Trabajar únicamente en:

- worktree `C:\Users\tito4\Documents\Odoo-gestion-costos`;
- rama `codex/gestion-costos`;
- addon `step_management_costs` y su documentación.

No intervenir en las sesiones de Claude que atienden fixes de Demo-SyS. No
escribir en `LAB_TAREAS`, `STEPS_DEMO`, `STEPS_DEMO_SYS`, el árbol compartido
de addons agrícolas ni otro worktree. Las bases reales sólo pueden usarse como
fuente de un clon desechable, siguiendo el patrón del handoff anterior.

## Resultado de la revisión

El Corte 1 está sustancialmente implementado y su estructura es coherente con
el plan: vista previa semanal, restricción de variedad, importador Excel de
programas y cruce de necesidades con inventario. El manifiesto está en
`18.0.13.0.0` y agrega la dependencia `stock`.

Validación independiente realizada sobre el worktree actual:

- `py_compile` de los Python del addon: OK;
- parseo de los 25 XML: OK;
- `git diff --check`: OK, salvo avisos informativos LF/CRLF ya registrados;
- 161 métodos `test_*` presentes en el addon.

El upgrade y clean install en Odoo real no se repitieron durante esta revisión.
Se conserva como evidencia la ejecución documentada por Claude: ambos RC 0,
sin fallos ni errores, sobre bases desechables ya eliminadas. El siguiente
handoff debe explicar por qué `odoo.tests.stats` informa 174 pruebas mientras
el addon contiene 161 métodos, distinguiendo pruebas del addon y pruebas
adicionales cargadas por el runner/dependencias.

## Trabajo obligatorio antes del Corte 2

No comenzar la Orden de Producción hasta cerrar estos puntos y agregar sus
pruebas. Como `18.0.13.0.0` todavía no fue desplegada, estas correcciones deben
integrarse en la misma versión y volver a ejecutar upgrade y clean install.

### R1 — La confirmación debe aplicar exactamente la vista previa mostrada

Archivos afectados:

- `models/planning.py`;
- `wizard/plan_weekly_preview.py`;
- `tests/test_fase7_corte1.py`.

Actualmente `default_get()` calcula lo que se muestra, pero `action_confirm()`
vuelve a calcular y aplica el resultado nuevo. Si el presupuesto, el plan o sus
líneas cambian entre ambos momentos, el usuario confirma una vista y el sistema
puede escribir otra. Además, una llamada RPC directa al wizard evita la
validación de estado que hoy sólo está en `action_generate_weekly_tasks()`.

Corregir con un contrato optimista y auditable:

1. Guardar en el wizard una huella determinista de la fuente y de los comandos
   mostrados, junto con los conteos.
2. Al confirmar, validar nuevamente permisos, empresa y estado del plan.
3. Recalcular sólo para comparar la huella. Si cambió, no escribir y pedir al
   usuario abrir una vista previa nueva.
4. Aplicar exactamente los comandos validados. No aceptar comandos arbitrarios
   recibidos desde el cliente.
5. Mantener intactas todas las tareas manuales.

Pruebas mínimas: confirmación sin cambios, presupuesto modificado después de la
vista previa, plan que cambia a un estado no permitido, RPC directa, otra
empresa, usuario sin el rol requerido y preservación de tareas manuales.

### R2 — Normalizar unidades antes de consolidar inventario

Archivo principal: `models/stock_requirement.py`.

El bucket actual usa `(product_id, period_key)` y suma cantidades de presupuesto
y programa conservando la UdM de la primera fuente. No se verifica que ambas
fuentes estén en la misma categoría ni se convierten a la UdM del producto. La
disponibilidad de Odoo se expresa en la UdM de inventario del producto, por lo
que una suma sin conversión puede producir faltantes incorrectos.

Regla requerida:

- convertir cada cantidad mediante `_compute_quantity()` a
  `product_id.uom_id` antes de agregarla;
- almacenar y mostrar la UdM base del producto en la línea consolidada;
- rechazar con error accionable una fuente sin UdM o con categoría incompatible;
- probar presupuesto y programa en UdM distintas pero compatibles, categoría
  incompatible y precisión/redondeo de la UdM de destino.

El importador de programas debe usar por defecto `product.uom_id` cuando el
Excel no informa UdM y debe validar categoría cuando sí la informa.

### R3 — Definir correctamente el faltante cuando hay varios períodos

Actualmente la misma foto de disponibilidad se copia a cada semana o mes. Por
ejemplo, con stock 100 y dos semanas de demanda 60, ambas líneas muestran
faltante cero, aunque el faltante de temporada es 20. No presentar esa salida
como faltante confiable.

Implementar una de estas representaciones, dejando la decisión en el ADR:

- recomendada: `available_at_snapshot` sólo como dato informativo y
  `cumulative_shortage` calculado en orden cronológico consumiendo una sola vez
  la disponibilidad por producto; o
- separar un resumen por producto/temporada con disponible y faltante total, y
  mantener el detalle semanal sólo como demanda.

Para la métrica pronosticada, no inventar disponibilidad histórica por semana:
el valor leído sigue siendo una foto en `computed_at`. Probar al menos dos
períodos, varios productos, stock insuficiente, stock negativo y orden mayo–abril.

### R4 — Coherencia completa de variedad

`crop_program.py` y `crop_program_import.py` sólo comparan los textos de los
centros entre sí. No comparan `program.variety`/`import.variety` con los centros,
son sensibles a mayúsculas y permiten mezclar un centro sin variedad con otro
informado porque eliminan el valor vacío del conjunto.

Mientras el puente agrícola no exista:

1. Normalizar comparación de texto (`strip` y `casefold`) sin reescribir datos.
2. Si hay centros con variedad informada, exigir una sola variedad y hacer que
   la variedad del encabezado coincida; se puede completar el encabezado sólo
   cuando esté vacío y la inferencia sea inequívoca.
3. Tratar la mezcla de centros informados y no informados como error visible,
   porque no demuestra que sean de la misma variedad.
4. Reutilizar la misma función de validación en programa e importación.
5. Alinear el preflight de migración con esas reglas y registrar IDs/folios
   accionables sin modificar datos.

Agregar pruebas para mayúsculas/espacios, encabezado contradictorio, mezcla
vacío/informado y todos vacíos. Cuando todos estén vacíos, bloquear aprobación
aunque se permita guardar el borrador.

### R5 — Endurecer el importador Excel

Además de R2 y R4:

- semana, carencia y reingreso deben ser enteros; no truncar silenciosamente
  `20.5`, `7.5` o `12.5`;
- definir si dosis cero es válida. Si no existe confirmación, permitirla en
  borrador con advertencia pero bloquear aprobación o documentar el supuesto;
- la idempotencia no puede impedir reutilizar una receta legítima en otra
  temporada o conjunto de centros. La clave debe representar la intención
  completa (empresa, temporada, tipo, centros normalizados y hash del archivo),
  no sólo empresa + archivo;
- proteger la idempotencia frente a concurrencia con constraint/índice de base
  de datos o un mecanismo transaccional equivalente, no sólo `search()`;
- probar dos temporadas con el mismo archivo, intento duplicado idéntico y dos
  importaciones concurrentes.

### R6 — Resolver la contradicción documental D20 sin tocar `step_hr`

`DECISION_LOG.md` D20 dice a la vez que el puente requiere una decisión y que
se usará `product.template.actividad_id -> account.analytic.account`. El campo
existe, pero su modelo destino coincide con centro de costo y no demuestra que
sea el maestro funcional `step.actividad` solicitado por el cliente.

Actualizar el log para distinguir:

- hecho técnico observado: destino actual `account.analytic.account`;
- incógnita funcional: si ese campo realmente representa Actividad o contiene
  datos legados/mal modelados;
- decisión temporal: no construir el puente ni modificar `step_hr` hasta tener
  confirmación del dueño funcional/técnico.

Esta incógnita no bloquea la OP central si la OP usa snapshots de las fuentes
que ya existen en `step_management_costs`. Sí bloquea cualquier sustitución de
maestros o dependencia agrícola nueva.

## Corte 2 — Orden de Producción central y PDF

Versión objetivo después de cerrar R1–R6: `18.0.14.0.0`.

### Alcance funcional confirmado

- Una OP por empresa, temporada, año/semana ISO, especie y centro de costo.
- El cuartel se presenta como atributo del centro; no crea otra OP.
- Consolida actividades planificadas y agrega detalle aprobado/confirmado de
  programas fitosanitarios, fertilización y cosecha.
- Estados mínimos: borrador, autorizada y reemplazada/cancelada según el patrón
  de revisión. Una OP autorizada es inmutable.
- Sólo el rol Aprobador/Control autoriza. Las correcciones se hacen mediante una
  nueva revisión; nunca se reabre o edita el documento autorizado.
- La autorización congela snapshot JSON determinista y hash SHA-256.
- Este corte no crea OT ni escribe en addons operacionales. Sólo deja una API
  interna segura que el futuro puente podrá consumir y que rechaza OP no
  autorizadas.

### Fuentes y trazabilidad

Cada línea debe conservar procedencia inequívoca. No usar sólo texto ni IDs
sueltos. Preferir relaciones explícitas y mutuamente excluyentes a:

- `step.management.plan.line` para tareas planificadas;
- `step.management.crop.program.application` para fito/ferti;
- plan/estimación de cosecha para cosecha.

La combinación exacta debe impedir duplicar una misma fuente dentro de la OP.
Guardar snapshots de descripción, producto/labor, UdM, cantidad, centro,
especie, grupo presupuestario y demás campos que deban permanecer estables.

Antes de implementar cosecha, resolver la granularidad: hoy
`harvest.plan.line` es semanal pero agregado y no contiene centro. La OP es por
centro. Auditar si la distribución puede derivarse de cada
`estimation.line.total_kg` por el porcentaje semanal congelado. Si no se puede
demostrar una asignación determinista y conciliable, documentar el bloqueo y no
repartir kilos arbitrariamente.

La generación debe abrir una vista previa sin escritura, con líneas nuevas,
eliminadas y conservadas. Aplicar el mismo contrato de huella de R1. Sólo tomar
fuentes de la misma empresa/temporada/centro/semana y en estados válidos. La
suma por tipo de fuente debe conciliar antes de autorizar.

### Identidad, revisiones y concurrencia

- Definir una clave estable normalizada para empresa + temporada + año ISO +
  semana ISO + especie + centro.
- Asegurar por SQL la unicidad de revisión dentro de esa clave.
- Impedir de forma transaccional dos OP vigentes/autorizadas para la misma clave.
- La nueva revisión debe enlazar origen y reemplazo, aumentar correlativo y
  conservar el folio trazable.
- Validar semana 53 y las fechas lunes–domingo mediante
  `step.management.period.service`; no duplicar lógica de calendario.
- Probar autorización concurrente y generación concurrente.

### Formulario y PDF

Usar `Formulario OP.pdf` sólo como referencia visual/funcional. El reporte QWeb
debe mostrar:

- título `ORDEN DE PRODUCCIÓN Wxx`;
- temporada, rango lunes–domingo, año/semana ISO, folio, fecha de emisión;
- creador, autorizador, empresa y fundo;
- especie, centro de costo y cuartel informativo;
- origen/grupo de presupuesto, actividad, producto-labor, UdM y cantidad
  semanal;
- instrucciones/observaciones y firmas o identificación de usuario/aprobador.

El PDF debe usar exactamente el snapshot autorizado, no volver a consultar
maestros cambiables. Una prueba debe extraer el texto del PDF y comprobar folio,
semana, centro, líneas y totales; otra debe demostrar que cambios posteriores en
productos/centros no alteran el PDF de una OP ya autorizada.

### Destinatarios y correo

Permitir destinatarios configurables para los perfiles informados por el
cliente: gerente agrícola, jefe de campo, supervisores, bodega y BPA. Como los
usuarios reales siguen pendientes, no asignar personas ni correos por defecto.

Registrar quién preparó, autorizó y solicitó el envío, fecha, destinatarios y
resultado. En pruebas usar mocks o mail catcher; nunca enviar correo real. El
envío no debe ser condición para autorizar la OP ni debe cambiar el snapshot.

### Seguridad y multiempresa

- ACL y reglas globales por `company_ids` para cabecera, líneas, revisiones y
  wizard de vista previa.
- Métodos públicos deben validar rol, estado, empresa y transición también por
  RPC directa.
- `check_company=True` y `_check_company_auto` donde corresponda.
- Las líneas autorizadas no se crean, editan ni eliminan directamente.
- No usar contextos forjables como bypass de inmutabilidad.

### Pruebas y puerta de salida

Agregar pruebas positivas y negativas para:

1. identidad por especie + centro + semana y separación de compañías;
2. W01, cruce de año y W53;
3. vista previa sin escritura y detección de fuente cambiada;
4. conciliación independiente de tareas, fito, ferti y cosecha;
5. no duplicación de fuentes;
6. autorización sólo por aprobador;
7. snapshot/hash deterministas, inmutabilidad y revisión;
8. concurrencia de creación/autorización;
9. PDF desde snapshot;
10. destinatarios y envío simulado;
11. API futura de OT rechazando borrador y aceptando sólo autorizada, sin crear
    todavía registros externos.

Puerta de salida:

- R1–R6 cerrados y documentados;
- `py_compile`, XML y `git diff --check` limpios;
- upgrade desde clon desechable de `LAB_TAREAS` y clean install con 0 fallos y
  0 errores;
- conciliación exacta de cada fuente y PDF reproducible;
- bases, dumps, addons_path, data-dir y configuración temporales eliminados;
- ningún cambio en Desarrollo, Demo o Demo-SyS;
- nuevo `HANDOFF_FASE7_CORTE2.md` con evidencia exacta, decisiones y límites.

## Prompt operativo para iniciar Claude

Continúa en `C:\Users\tito4\Documents\Odoo-gestion-costos`, rama
`codex/gestion-costos`. Lee completos
`REVISION_CORTE1_Y_CONTINUACION_CLAUDE_CORTE2_2026-09-04.md`,
`HANDOFF_FASE7_CORTE1.md`, `DECISION_LOG.md`, `MATRIZ_REQUISITOS.md` y
`ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md`. No toques otras sesiones, worktrees,
addons ni ambientes. Primero corrige y prueba R1–R6 manteniendo
`18.0.13.0.0`; informa cualquier discrepancia antes de modificar. Sólo cuando
upgrade y clean install vuelvan a quedar verdes, implementa el Corte 2 como
`18.0.14.0.0`: Orden de Producción semanal central, vista previa, trazabilidad
de fuentes, autorización/revisión inmutable, snapshot/hash, PDF QWeb y correo
simulado. No implementes el puente agrícola D20 ni integración OT, no envíes
correos reales y no despliegues. Termina con pruebas, limpieza de artefactos
temporales y `HANDOFF_FASE7_CORTE2.md`; deja todo sin commit ni push.
