# Arquitectura, estrategia de migración y decisiones — Movilización

## 0. Limitación de partida (bloquea Fase 1.2 tal como está escrita)

El encargo pide, en la Fase 1.2, contar registros "en cada base autorizada"
mediante consultas de lectura. **Este checkout local no tiene acceso a ninguna
base de datos de Odoo**: no hay `odoo-bin`, ni paquete `odoo` instalable, ni
`docker-compose` con Postgres+Odoo, ni credenciales de ninguna base (ni
producción ni desarrollo) configuradas en el repo. El único dump SQL presente
en el repo (`tracker_steps.sql`/`.dump`) es de la API FastAPI del tracker de
maquinaria (`work_orders`, `tracking_sessions`, `tracking_points`...), no de
Odoo — no contiene ninguna tabla `step_movi_*` ni `hr_route`.

Decisión (conservadora): no se inventa ni se asume ningún conteo de datos.
En vez de eso:
- Se levanta **localmente** (no remoto, no producción) un contenedor Docker
  descartable con Odoo 18 + Postgres para poder ejecutar instalación,
  actualización y pruebas automatizadas reales contra una base vacía/sintética
  — esto cubre la Fase 8 (pruebas), no la Fase 1.2 (conteos de datos reales).
- El "Reporte de datos antes/después" exigido como entregable #5 se deja
  como **plantilla de comando ejecutable** (`scripts/movilizacion/auditoria_datos.sql`,
  ver más abajo) más un runbook de cómo correrlo contra una base real
  (desarrollo primero, nunca producción), en vez de un reporte con cifras
  inventadas. Ejecutarlo contra una base real requiere acceso que este agente
  no tiene y que no se le ha autorizado a levantar contra el servidor remoto.
  Esto queda registrado como limitación pendiente de autorización explícita.

## 1. Arquitectura de addons

```
step_mobilization/                  Núcleo, sin dependencia de step_hr
  depends: base, mail, web, hr, contacts, fleet, product, account, analytic
  - Modelos movidos tal cual (mismo _name y tabla): step.movi.registry(.line),
    step.movi.cost.line, step.movi.cont.line, hr.route(.line),
    product.pricelist.move.line
  - Extensiones (_inherit) a hr.employee, res.partner, fleet.vehicle,
    product.template, product.pricelist, res.company, res.config.settings,
    account.move — sólo los campos exclusivos de Movilización (ver inventario)
  - Modelos nuevos: step.mobilization.passenger.event (boarding/alighting
    normalizado), step.mobilization.contract(+.line/.rate.snapshot),
    step.mobilization.right_to_know(+.line), step.mobilization.epp.delivery,
    step.mobilization.document(+.type), step.mobilization.inspection(+.line/.template),
    step.mobilization.gps.point, step.mobilization.driver.device, secuencia
    por compañía, seguridad (9 grupos + reglas), dashboard, 3 informes, API
    /mobilization/v1
  - migrations/18.0.1.0.0/pre-migrate.py: no aplica (módulo nuevo, ver step_hr)

step_mobilization_agriculture/      Adaptador
  depends: step_mobilization, step_hr
  - Vincula step.movi.registry.fundo_id (ya existente) con el costeo agrícola
  - Lee step.tarja/step.temporada (sólo lectura, hooks del núcleo)
  - Migra el fundo_id existente sin tocar la tabla

step_hr/                            Sigue funcionando sin Movilización
  - Se retiran del manifest los archivos movidos (no se borran datos: se
    retira la DECLARACIÓN del modelo/vista/acción/menú, la tabla no se toca)
  - migrations/18.0.1.3.0/pre-migrate.py: reasigna ir.model.data de
    step_hr → step_mobilization para todo lo movido (ver §3)
  - Dashboard de Actividades deja de consultar step.movi.registry directamente
```

No hay dependencia circular: `step_mobilization` no conoce `step_hr`;
`step_mobilization_agriculture` conoce a ambos; `step_hr` no conoce a ninguno
de los dos nuevos (sólo dejó de declarar lo que ya no le pertenece).

## 2. Por qué se conservan `_name`/tabla originales

Alternativas consideradas:
1. **Renombrar modelos** (`step.movi.registry` → `step.mobilization.trip`, etc.)
   — más "limpio" de cara al futuro, pero obliga a recrear `ir.model`,
   `ir.model.fields`, reescribir todos los dominios/vistas/reportes, y
   duplica el riesgo de perder relaciones. Rechazada por el propio criterio
   del encargo ("no continúes si la migración implica recrear tablas o volver
   a cargar registros").
2. **Conservar nombre/tabla, mover sólo el archivo Python + reasignar
   `ir.model.data`** (elegida) — cero cambios de esquema, cero riesgo sobre
   filas existentes, compatible con "conserva nombres de tabla cuando sea
   razonable".

## 3. Mecanismo de reasignación de `ir.model.data`

Técnica estándar de Odoo para mover la propiedad de un modelo/vista/acción/menú
de un addon a otro sin perder datos (la misma que usa Odoo core cuando fusiona
o separa módulos): un script `pre-migrate.py` en la carpeta `migrations/` de
`step_hr` (se ejecuta automáticamente al hacer `-u step_hr`, **antes** de que
se procesen los archivos de datos de cualquier módulo en esa misma corrida),
que hace:

```sql
UPDATE ir_model_data SET module = 'step_mobilization'
WHERE module = 'step_hr' AND (
  (model = 'ir.model' AND name = ANY(%(model_ids)s)) OR
  (model = 'ir.model.fields' AND name = ANY(%(field_ids)s)) OR
  (model IN ('ir.ui.view','ir.actions.act_window','ir.ui.menu',
             'ir.sequence','ir.model.access') AND name = ANY(%(ui_ids)s))
);
```

No se toca ninguna tabla de datos de negocio (`step_movi_registry`, `hr_route`,
etc.) — sólo la tabla de metadatos `ir_model_data`, que es precisamente el
mecanismo que Odoo usa para saber "quién es dueño de este XML ID". Esto
**no** es "renombrar tablas con SQL improvisado" (prohibido explícitamente):
es reasignar metadatos de propiedad, la técnica documentada para este caso.

Debe correr en la MISMA operación de actualización que instala
`step_mobilization` por primera vez (`-u step_hr -i step_mobilization` en un
solo comando), para que el registro de modelos nunca quede sin una clase
Python que declare `step.movi.registry` durante la transición.

## 4. Alias temporal para el único XML ID externo

`step_agricultural_access` referencia `step_hr.menu_step_moviliza`. Alternativas:
1. Mantener un menú vacío en step_hr como alias permanente — genera confusión
   ("¿por qué hay un menú Movilización dentro de Actividades si la app ya se
   separó?").
2. **Actualizar la referencia y declarar `step_mobilization` como dependencia
   de `step_agricultural_access`** (elegida) — es un cambio de una línea en un
   addon que ya se mantiene en este mismo repo, controlado, sin usuarios
   externos de ese XML ID fuera del monorepo. Se documenta aquí como el único
   XML ID externo detectado y su fecha de retiro es inmediata (no hay periodo
   de convivencia porque no hay una tercera parte que lo consuma).

## 5. Identificador móvil del chofer/trabajador

El encargo prohíbe usar el PIN del empleado como identificador visible o clave
en texto plano. Decisión: cada `hr.employee`/chofer recibe un
`mobile_credential_uuid` opaco (uuid4, generado una vez, no secuencial) que es
lo que se codifica en el QR/código de barra de la credencial física. El PIN
existente (`hr.employee.pin`) se sigue usando como método de marcación
alternativo, pero nunca se persiste en el dispositivo móvil: la app lo envía
una vez por evento a un endpoint que lo valida server-side y descarta el valor
(no se guarda en el payload sincronizado, sólo el resultado válido/inválido y
el método usado). NFC, cuando el hardware lo permite, lee el mismo
`mobile_credential_uuid`.

## 6. Alcance de la app móvil / API en esta entrega

El encargo permite explícitamente entregar "un prototipo ejecutable completo
si el alcance se entrega por hitos". Decisión conservadora: se entrega
completa y funcional la **API versionada** (`/mobilization/v1`, autenticación
por dispositivo, sesiones de viaje, eventos de pasajero por lote, puntos GPS
por lote, resolución de conflictos idempotente) más un **cliente web PWA
mínimo** que ejercita el flujo completo (login chofer → abrir sesión → marcar
pasajero por PIN/código → ver a bordo → GPS → cerrar sesión), en vez de una
app nativa iOS/Android completa (fuera de alcance razonable para una sola
sesión de trabajo; requeriría además publicación en tiendas, gestión de
certificados, etc., todas acciones que necesitan autorización explícita del
usuario y no pueden hacerse hoy). Este PWA sirve como prueba end-to-end del
contrato de API y como base sobre la que un desarrollo móvil nativo posterior
podría construirse sin cambiar el backend.

## 6.1 Secuencia de numeración de viajes

La secuencia heredada (`seq_step_moviliza`) es global (`company_id=False`,
riesgo confirmado en la auditoría). Se reemplaza por una secuencia creada bajo
demanda **por compañía** (`step.movi.registry._next_sequence`). Para no
colisionar con la numeración histórica (que sí era continua porque todas las
compañías compartían el mismo contador), la migración siembra el
`number_next` de cada secuencia nueva por compañía con el valor actual de la
secuencia global antigua, en vez de reiniciar en 1. Esto significa que, tras
el corte, dos compañías pueden compartir temporalmente un mismo número de
folio en paralelo — aceptable porque `name` nunca fue una clave única real
(no tenía `_sql_constraints` de unicidad ni en step_hr ni aquí), sólo un
folio legible; lo que sí se evita es reutilizar un folio ya emitido.

## 7. Entorno de pruebas

No hay Odoo instalable localmente en este equipo (sólo vive en el servidor
remoto). Se usa Docker (disponible localmente) para levantar un Odoo 18 +
Postgres **descartable y local** únicamente para correr instalación limpia,
actualización y la suite de tests — nunca se conecta a, ni se copia desde/hacia,
ninguna base remota. Se documenta como parte del runbook de pruebas, no de
despliegue.
