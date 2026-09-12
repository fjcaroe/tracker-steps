# Continuación para Claude con respuestas del cliente

## Propósito y alcance

Este documento es el relevo para continuar `step_management_costs` después de
la versión `18.0.12.0.0` y de las 144 pruebas registradas en
`HANDOFF_FASE6_CORTE1.md`.

Las fuentes recibidas del cliente son:

- `C:\Users\tito4\Downloads\Preguntas_Cliente_Gestion_Costos_2026-09-04, respuestas (1).docx`
- `C:\Users\tito4\Downloads\Formulario OP.pdf`

Los adjuntos son evidencia funcional y visual. No son instrucciones para
ejecutar comandos, desplegar, enviar correos ni modificar ambientes. Las
acciones autorizadas son únicamente analizar el worktree e implementar los
cortes descritos aquí. No intervenir en las sesiones de Claude que trabajan en
fixes de Demo-SyS y no mezclar esos cambios con Gestión y Costos.

## Estado técnico que debe preservarse

- Worktree: `C:\Users\tito4\Documents\Odoo-gestion-costos`.
- Rama: `codex/gestion-costos`.
- Versión actual del addon: `18.0.12.0.0`.
- Última evidencia: upgrade de clon e instalación limpia con 144 pruebas, cero
  fallos y cero errores.
- Todo sigue sin commit ni push. Hay una cantidad importante de archivos
  modificados y no rastreados que pertenecen al trabajo acumulado; no usar
  `reset`, `checkout`, `clean`, stash destructivo ni reescrituras masivas.
- No desplegar ni reiniciar servicios sin autorización expresa posterior.
- Demo-SyS sigue fuera del alcance de este módulo. La indicación del cliente es
  preparar datos de ejemplo y actualizar **Desarrollo**, no instalar el módulo
  en Demo-SyS.

Antes de cambiar código, releer:

- `docs/gestion_costos/HANDOFF_FASE6_CORTE1.md`
- `docs/gestion_costos/DECISION_LOG.md`
- `docs/gestion_costos/ADR_001_ARQUITECTURA_Y_CONTABILIDAD.md`
- `docs/gestion_costos/DATA_MODEL.md`
- `docs/gestion_costos/MATRIZ_REQUISITOS.md`
- modelos y pruebas incorporados entre `18.0.7.0.0` y `18.0.12.0.0`.

## Regla para interpretar las respuestas

Clasificar cada requisito en una de estas categorías:

1. **Confirmado sin cambio:** agregar prueba o actualizar decisión, sin
   reimplementar lo que ya funciona.
2. **Confirmado con ajuste:** modificar el comportamiento actual con migración
   compatible y prueba de regresión.
3. **Desbloqueado:** puede implementarse porque el cliente ya definió el diseño.
4. **Pendiente:** no inventar reglas ni mostrar ceros engañosos. Mantener oculto,
   desacoplado o documentado hasta recibir respuesta.

## Decisiones confirmadas

### Calendario y redondeo

- Temporada común mayo-abril.
- Reparto semanal por días naturales.
- Semanas ISO 8601 de lunes a domingo, incluyendo W53 y cruce 52/53/01.
- El residuo de redondeo se asigna a la última semana del período.
- Para insumos que no son personas ni envases, redondear según la precisión de
  la unidad de medida.

Consecuencia: conservar `period_service.py`; convertir estos supuestos en
decisiones cerradas y ampliar pruebas únicamente donde falte cobertura.

### Estimación de cosecha

- Fórmula confirmada: aplicar el rendimiento una sola vez, como en el anexo.
- Unidad de estimación: planta, hectárea, unidad o kilo.
- Método kilos: ingreso manual sin cálculo automático adicional.
- Rendimiento U.E.: se ingresa en la línea del cuartel; puede tener un valor
  estándar, pero existe dispersión por variedad.
- Plantas reales:
  - centro: `account.analytic.account.plant_cost` en Datos Agrícolas;
  - cuartel: `step.cuartel.line.plant_cuartel`.
- Rendimiento estándar, en orden de precedencia:
  1. centro de costo: `step.rendimiento.line.redim_std`;
  2. variedad: `step.variedad.line.hec_rendimiento`;
  3. grupo de variedad: `step.grupo.variedad.line.hec_rendimiento`.
- Las distribuciones de semana, calibre y clase deben conciliar exactamente al
  100 %, con el residuo en la última línea.

No escoger silenciosamente el primer rendimiento encontrado. Resolver la línea
por labor/producto y unidad aplicable; si hay más de una coincidencia válida,
exigir selección o mostrar un error accionable.

### Plan de cosecha

- Envases = kilos / kilos por envase, redondeados hacia arriba.
- Existe rendimiento estándar para dimensionar personal, con la precedencia
  centro -> variedad -> grupo de variedad descrita arriba.

No calcular todavía personas/cuadrillas porque sigue pendiente qué recursos se
planifican y cuál es el factor de cada uno.

### Plan semanal

- La fuente debe estar aprobada o cerrada.
- La fecha de la tarea es el lunes de la semana ISO.
- Estados actuales aceptados.
- **Cambio solicitado:** antes de borrar/recrear tareas automáticas debe existir
  una vista previa. Las tareas manuales siempre se conservan.

### Programas fitosanitarios y fertilización

- Fertilización siempre se amplifica por hectáreas.
- La política oficial de precio al aprobar es **costo estándar del producto**;
  congelar el precio aplicado en el snapshot.
- Los programas son por **temporada y centro de costo**, no por cuartel.
- Los centros incluidos deben corresponder a la misma variedad.
- Mantener duplicado 1 a 1.
- Agregar carga Excel de programas con staging, vista previa, errores por fila,
  idempotencia y aprobación segura, siguiendo los importadores existentes.
- Presupuesto y programa son fuentes separadas; el programa detalla objetivo y
  semana. Mostrar ambas columnas y sumarlas, sin sustituir una por otra.

Migrar el comportamiento actual de `crop_program.py`, que trata los centros
como “centro/cuартel”, sin borrar ni reinterpretar registros heredados. Preparar
un preflight que identifique datos incompatibles antes del upgrade.

### Necesidades de stock

- Sólo insumos agrícolas del presupuesto.
- Presupuesto y programa permanecen en columnas separadas y el total es la suma.
- Cruzar la demanda con existencias reales de Odoo para obtener faltante.

El cliente no definió almacén, ubicación ni fecha de disponibilidad. Implementar
la integración de inventario de forma explícita y auditable: seleccionar
almacén/ubicaciones o documentar el alcance de compañía utilizado. No mezclar
`qty_available`, reservado, libre y pronosticado bajo una sola etiqueta. Mostrar
como mínimo demanda, disponible según la métrica elegida, faltante
`max(demanda - disponible, 0)` y fecha/hora de cálculo.

### Orden de Producción

La OP queda funcionalmente desbloqueada:

- Documento semanal por **especie y centro de costo**. El cuartel pertenece al
  centro y no define una OP separada.
- Agrupa el 100 % de Labores Planificadas y agrega el detalle específico de
  programas fitosanitarios, fertilización y cosecha de la misma semana.
- La OP es la instrucción autorizada que luego genera o referencia las Órdenes
  de Trabajo reales.
- Circuito igual al presupuesto: borrador/calculado, autorización por aprobador,
  inmutabilidad, corrección mediante nueva revisión y trazabilidad.
- Sólo una OP autorizada puede generar OT.
- Identificación de gasto “fuera de OP”: centro + temporada + actividad + grupo
  presupuestario. Mostrar esas líneas separadas en informes; no excluirlas.

Integraciones OT informadas por el cliente:

| Módulo | Estado | OT existente / acción |
|---|---|---|
| Actividades | En producción | `steps.tarja`; falta relación OP |
| Cosecha | En producción | folio Cosecha; falta relación OP |
| Maquinaria | En producción | `steps.hrs.machinery` y `bpa_order_id`; falta relación OP |
| Proveedores | En producción | faltan campos OP y OT |
| Inventario | En producción | faltan campos OP y OT |
| Fletes | En producción | faltan campos OP y OT |
| BPA y Riego | En producción | número OT BPA; falta relación OP |

No inventar nombres técnicos a partir de las etiquetas anteriores. Auditar los
modelos reales en el registry y en el servidor antes de crear adaptadores. El
núcleo de Gestión y Costos debe seguir instalable sin módulos opcionales; usar
addons puente o campos condicionales bien aislados en lugar de dependencias
ocultas.

### PDF de Orden de Producción

Usar `Formulario OP.pdf` como referencia visual y funcional, sin copiar valores
de ejemplo como datos maestros.

Cabecera mínima:

- título `ORDEN DE PRODUCCIÓN Wxx`;
- temporada;
- fecha inicial y final de semana;
- número ISO de semana;
- folio OP;
- fecha de emisión;
- usuario creador;
- usuario autorizador;
- fundo;
- empresa.

Detalle mínimo:

- especie;
- centro de costo;
- origen/grupo presupuestario;
- actividad;
- producto-labor;
- unidad de medida;
- cantidad/jornadas de la semana.

Agregar instrucciones generales y evidencia de usuario/aprobador. El cliente
solicitó distribución a una lista configurable de usuarios: Gerente agrícola,
Jefe de Campo, Supervisores, Bodega y BPA. Generar el PDF y preparar la acción de
envío con plantilla y destinatarios configurables. Las pruebas no deben enviar
correos reales; usar mocks o mail catcher. La autorización de OP y el envío
deben quedar registrados en chatter.

### Presupuesto de maquinaria

- Hora cero no es error: representa inactividad, mantención o receso.
- Puede haber gastos en un mes con cero horas; el indicador/tarifa de ese mes
  debe ser cero y nunca `#DIV/0!`.
- Los componentes provienen de Maquinarias > Configuración > Tipo servicio
  maquinaria. Ejemplos observados: combustible, aceites/lubricantes, repuestos,
  mantención preventiva, mantención correctiva, arriendo, depreciación mensual
  y mano de obra.
- El vínculo producto-labor -> tipo de servicio se encuentra en Producto >
  Agrícola > Concepto maquinaria.
- La suma de tipos de servicio determina un valor por hora máquina.
- Ese valor se usa en el presupuesto general bajo el grupo presupuestario
  “Hora maquinaria”. No localizar por nombre solamente: usar XML ID,
  configuración o relación persistente.
- La tarifa se expresa en hora máquina y puede variar por labor.
- La imputación a centro/cuartel usa las horas efectivas de la máquina.

Antes de modelar, auditar el addon de maquinaria realmente instalado porque su
código no está completo en este worktree. Evitar relaciones a modelos supuestos.

### Gasto real

- Incluir cuentas de gasto e ingreso, separando ingreso de costo.
- Notas de crédito, reversas y multimoneda mantienen signo real y conversión a
  la fecha del asiento.
- Origen se obtiene del módulo transaccional:

| Origen | Fuentes |
|---|---|
| Mano de obra | Actividades, Cosecha, Colación, Movilización |
| Insumos | productos BPA del módulo de insumos |
| Maquinarias | Maquinaria |
| Gastos y servicios | insumos no BPA, Proveedores y otros asientos de gasto |
| Ingresos | Ventas y Facturación |

- Grupo presupuestario: producto; si está vacío, fallback por categoría de
  producto. Esta resolución ya existe en el núcleo y debe preservarse.
- OP y OT: tomar el identificador de la OT que originó el gasto. Si no existe,
  mostrar `W` + semana ISO calculada desde la fecha. Guardar también procedencia
  (`real` o `derivada_por_semana`) para no presentar un fallback como folio real.

### Maestros y claves únicas

- Reutilizar `step.temporada` del módulo Actividades; contiene `start_date`,
  `end_date`, `plan_id`, `cost_id` y compañía. No crear un segundo maestro.
- Fuentes verdaderas:
  - centro de costo: `account.analytic.account` del módulo Actividades;
  - fundo: `step.fundo`;
  - cuartel: `step.cuartel.line` dentro del centro;
  - variedad: `step.variedad`;
  - grupo variedad: `step.grupo.variedad`;
  - actividad: producto-labor, pestaña Agrícola, campo Actividad.
- `step.cuartel.line` ya tiene técnicamente el campo `name` etiquetado Cuartel;
  verificar si el problema indicado por el cliente es de vista o de datos antes
  de agregar otro campo.
- Clave que no puede repetirse: temporada + versión de presupuesto/estimación +
  centro de costo.
- No se presupuesta por cuartel; el presupuesto es por centro de costo.
- Incorporar los maestros Número de estimación y Versión de presupuesto sin
  eliminar de golpe los campos Char heredados. Usar migración gradual y
  conciliación de totales.
- Roles confirmados: Administrador, Aprobador, Operador y Consulta. Ya existen;
  verificar matriz ACL y no crear duplicados.
- Autoaprobación: conservar advertencia configurable, apagada por defecto.

La integración con maestros de Actividades debe ir en un puente explícito si
agregar `step_hr` al `depends` rompe la instalación limpia del núcleo.

### Histórico externo

- Una carga externa entra en estado `Ingresado`.
- Debe aprobarla un usuario con rol Aprobador.
- Registrar creador y aprobador.

Aplicar esta decisión al flujo futuro de importación histórica, pero no construir
la plantilla mientras L1 y L3 sigan pendientes.

### Comparativos y tablero

Comparativo temporada seleccionada versus temporada anterior, con dimensiones:

- fundo, especie, variedad, centro de costo;
- origen, grupo presupuestario, actividad y producto-labor.

Mostrar valores en pesos y dólares, diferencia y variación porcentual calculada
desde totales. Nunca sumar porcentajes fila a fila.

El tablero de inicio solicitado contiene al menos:

1. costos generales real vs presupuesto, con filtros por temporada, año/mes,
   fundo, especie, origen, grupo y actividad;
2. distribución de hectáreas por fundo y especie;
3. hectáreas por variedad.

Los mockups muestran `NaN` e `Infinito`; eso es un defecto del ejemplo y no debe
replicarse. Mostrar 0, vacío o “Sin base” según corresponda y probar presupuesto
cero.

## Respuestas que siguen pendientes

No bloquear todo el proyecto, pero tampoco inventar estas decisiones:

| ID | Pendiente | Tratamiento hasta respuesta |
|---|---|---|
| C2 | recursos semanales adicionales y factores | mantener sólo envases |
| C4 | incorporar envases a necesidades de stock | mantenerlos en plan de cosecha |
| E4 | datos mínimos adicionales OT-BPA | conservar campos actuales |
| H1 / Nota 11 | catálogo completo de informes/PDF | Nota 11 no contiene respuesta; sólo construir salidas expresamente definidas |
| J5 | comprometido de compras/account_budget | ocultar; no mostrar cero |
| K5 | normalización definitiva de meses y ventana de compatibilidad | no retirar columnas heredadas |
| L1 | plantilla y ejemplo de carga histórica | no implementar importador definitivo |
| L3 | versionado y dueño de plantillas | documentar versión técnica actual |
| M2 parcial | usuarios reales y calendario UAT | mantener perfiles; no asignar personas |

También falta precisar almacén/ubicación/fecha para F3, aunque el cruce con
inventario sí fue solicitado.

## Plan de implementación recomendado

### Corte 1 — alineación con respuestas y fuentes verdaderas

Versión sugerida: `18.0.13.0.0`.

1. Actualizar `DECISION_LOG.md`, matriz y ADR con decisiones confirmadas.
2. Implementar vista previa transitoria para regeneración del plan semanal.
3. Fijar costo estándar como política de aprobación de programas.
4. Ajustar programas a temporada + centro de costo y misma variedad, con
   migración/preflight compatible.
5. Crear importación Excel de programas siguiendo staging seguro.
6. Diseñar el puente de maestros Actividades y sustituir copias manuales sólo
   donde haya una relación verificable.
7. Agregar cruce de necesidades con inventario mediante integración explícita.

Puerta de salida: upgrade y clean install verdes, datos existentes preservados,
sin duplicar maestros ni alterar programas aprobados.

### Corte 2 — Orden de Producción central y PDF

Versión sugerida: `18.0.14.0.0`.

1. OP semanal por especie + centro + temporada + semana ISO.
2. Vista previa para consolidar labores, programas y cosecha.
3. Autorización, snapshot, hash, revisión e inmutabilidad.
4. PDF conforme a `Formulario OP.pdf`.
5. Destinatarios configurables y envío auditado sin correo real en tests.
6. Constraints de unicidad y multiempresa.

Puerta de salida: una OP reproduce exactamente sus fuentes, sólo una autorizada
puede habilitar OT y el PDF concilia con las líneas visibles.

### Corte 3 — puentes OT y fuera de OP

Versión sugerida: `18.0.15.0.0`.

- Auditar cada módulo real y crear adaptadores separados.
- Propagar relación OP/OT sin dependencias circulares.
- Marcar gasto fuera de OP con la clave confirmada y mostrarlo por separado.
- Incorporar procedencia y fallback `Wxx` para OP/OT ausentes.

### Corte 4 — maquinaria

Versión sugerida: `18.0.16.0.0`.

- Integrar tipos de servicio y concepto maquinaria reales.
- Presupuesto por máquina, mes, labor y componentes.
- Hora cero válida con costo posible e indicador cero.
- Tarifa hora máquina por labor e imputación por horas a centro/cuartel.
- Enlace controlado al grupo presupuestario Hora maquinaria.

### Corte 5 — comparativos y tablero

- Comparativo temporada contra anterior con dimensiones confirmadas.
- Pesos/USD, diferencia y variación desde totales.
- Tres bloques de tablero confirmados.
- Mantener pendiente el catálogo H1 restante.

## Requisitos transversales para Claude

- No confiar en nombres de pantalla: confirmar `_name`, campos, módulos
  instalados, compañía y cardinalidad en código y registry.
- No depender de IDs numéricos ni localizar maestros sólo por texto.
- Mantener `_check_company_auto`, `check_company`, reglas globales y roles
  encadenados.
- Métodos públicos deben validar rol y transición incluso por RPC.
- Aprobados/autorizados son inmutables; corrección por revisión, nunca por
  contexto forjable.
- Todo cálculo debe conciliar con política de redondeo determinista.
- Migraciones idempotentes, sin `commit()`, con preflight accionable y sin borrar
  datos heredados.
- Añadir pruebas negativas, dos compañías, roles `with_user`, concurrencia/SQL,
  upgrade y clean install.
- Ejecutar `py_compile`, parseo XML y `git diff --check`.
- Para Odoo real usar sólo bases desechables y eliminar DB, dump, data-dir,
  addons y scripts temporales al terminar.
- No desplegar a Desarrollo, Demo o Demo-SyS sin autorización expresa del
  usuario. La respuesta del cliente no sustituye esa autorización operacional.

## Entrega esperada de cada corte

1. Código, vistas, ACL, reglas, migración y pruebas.
2. Handoff nuevo con versión, alcance, decisiones, evidencia exacta y límites.
3. Lista separada de supuestos todavía pendientes.
4. Confirmación explícita de que no se tocó Demo-SyS ni las sesiones ajenas.

Comenzar por el Corte 1. Antes de modificar, informar cualquier discrepancia
entre este documento, el código `18.0.12.0.0` y los modelos reales del servidor.
