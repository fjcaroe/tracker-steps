# Plan de desarrollo — Módulo Gestión y Costos

**Fecha:** 2 de septiembre de 2026
**Plataforma objetivo:** Odoo 18
**Addon existente:** `step_management_costs`
**Estado de este documento:** plan de ejecución; no implica instalación ni despliegue

## 1. Decisión ejecutiva

El proyecto no debe comenzar creando un addon nuevo. En el repositorio ya existe
`step_management_costs`, versión `18.0.1.1.0`, con centros de costo, grupos y
plantillas presupuestarias, presupuesto operacional, planificación manual, tipos
de cambio estimados, costos históricos y un tablero OWL.

La estrategia será evolucionar ese addon sin cambiar sus nombres de modelos,
tablas ni XML IDs existentes. La primera versión objetivo será `18.0.2.0.0`, con
scripts de actualización y pruebas que demuestren que los registros actuales se
conservan. Crear un segundo módulo con los mismos conceptos produciría menús,
maestros y cifras duplicadas.

El paquete funcional entregado contiene 8 documentos Word y 28 libros Excel. Se
revisaron sus 36 archivos y 66 hojas. Son mockups funcionales valiosos, pero no
constituyen todavía una especificación cerrada ni plantillas de importación
listas para producción.

Ruta de la fuente funcional:

`C:\Users\tito4\Downloads\1.6 Módulo Gestión y Costos\1.6 Módulo Gestión y Costos`

## 2. Objetivo del producto

Construir una aplicación Odoo que permita planificar, aprobar y controlar la
temporada agrícola desde el presupuesto por hectárea hasta el costo real
contabilizado, con trazabilidad por empresa, temporada, fundo, centro de costo,
especie, variedad, actividad, origen, grupo presupuestario y producto/labor.

El producto tiene tres flujos paralelos que convergen en la OP, no una cadena
lineal:

```text
Presupuesto aprobado ──> Tareas semanales ──────┐
Estimación vigente ────> Plan de cosecha ───────┼─> OP/OT ─> asiento publicado
Programa aprobado ────> Fito / fertilización ───┘              │
Presupuesto aprobado <──────── comparación y drill-down <──────┘
```

El asiento publicado de Odoo será la fuente única del valor monetario real. La
distribución analítica aportará su imputación; producto, cantidad, UdM, OP/OT y
otros atributos se enriquecerán desde el documento origen mediante contratos
explícitos. Los costos operacionales aún no contabilizados, si se requieren, se
mostrarán como métrica separada y nunca se sumarán al realizado contabilizado.
El módulo aportará la semántica agrícola, los escenarios y los controles, pero
no creará un segundo libro contable.

## 3. Alcance funcional consolidado

El menú objetivo, derivado de `Menú general de Gestión y Costos.xlsx`, comprende:

1. Inicio y panel.
2. Presupuesto:
   - plantillas agrícolas;
   - carga normalizada desde Excel;
   - presupuesto agrícola, general y de maquinaria;
   - versiones, revisión, aprobación y reemplazo;
   - análisis por indicador y reportes.
3. Estimaciones:
   - estimación por cuartel/centro;
   - curvas de semanas, calibres y clases;
   - versiones, validación, importación y reportes.
4. Planificación:
   - tareas semanales desde el presupuesto vigente;
   - plan de cosecha y recursos;
   - programas fitosanitarios y de fertilización;
   - necesidades de stock;
   - orden de producción semanal e integración con OTs.
5. Gestión:
   - gasto real contable;
   - costo histórico externo;
   - comparativos real/presupuesto y temporada contra temporada.
6. Maestros y configuración.

### 3.1 Lo que ya existe

- Centro de costo con hectáreas y cuenta analítica opcional.
- Grupo presupuestario y cuenta contable.
- Plantilla presupuestaria por hectárea.
- Aplicación de una plantilla a varios centros.
- Distribución mayo-abril y presupuesto operacional.
- Tipo de cambio estimado separado de la tasa real de Odoo.
- Planificación manual, costos históricos manuales y tablero.
- Dos perfiles de acceso: usuario y administrador.

### 3.2 Brecha principal

El addon actual es un MVP, no la implementación completa del paquete 1.6. Las
estimaciones, curvas, cosecha, programas fito/ferti, necesidades de stock, OP,
importadores Excel, gasto real contable, reportes documentales y pruebas
automáticas están ausentes. Presupuesto y planificación sólo están cubiertos de
forma parcial.

## 4. Decisiones funcionales que deben cerrarse

Estas decisiones no deben resolverse copiando literalmente las planillas, pues
los artefactos contienen contradicciones.

| ID | Tema | Recomendación inicial | Quién valida | Momento límite |
|---|---|---|---|---|
| D01 | Fuente del gasto real | Valor desde `account.move.line` publicado; imputación desde analítica; enriquecimiento desde origen; histórico sólo externo/ajuste | Contabilidad | Antes de Fase 2 |
| D02 | Presupuesto estándar | Detectar `account_budget`; usar adaptador si está disponible, sin dependencia rígida | TI/Contabilidad | Fase 0 |
| D03 | Temporada | Maestro con rango; valor inicial mayo-abril, configurable por empresa | Dueño funcional | Fase 1 |
| D04 | Semanas | ISO-8601; semana 53 soportada; semanas que cruzan mes se prorratean por días | Operaciones | Fase 0 |
| D05 | Fórmula de estimación | `Total UE × factor de conversión a kg`; no volver a multiplicar por rendimiento | Agronomía | Fase 3 |
| D06 | Versión vigente | Definir clave natural distinta para presupuesto, estimación, plantilla, programa y OP; una vigente por cada clave | Control gestión | Fase 2 |
| D07 | Precio de programas | Política configurable; snapshot de fuente, precio, moneda, fecha y UdM al aprobar | Compras/Contabilidad | Fase 5 |
| D08 | Redondeo de recursos | Personas/envases indivisibles hacia arriba; insumos según precisión de UdM | Operaciones | Fase 4 |
| D09 | Segregación | Creador no aprueba su propio documento salvo permiso excepcional auditado | Administración | Fase 1 |
| D10 | Importaciones | Vista previa, staging, errores por fila y clave idempotente; nunca importar directo a definitivo | Dueño funcional | Fase 2 |
| D11 | No planificado | Marcar una línea real como fuera de OP por clave dimensional, no por texto | Operaciones/Contabilidad | Fase 6 |
| D12 | Demo-SyS | Instalar sólo el núcleo si tiene utilidad funcional y supera compatibilidad | Dueño producto | Fase 8 |
| D13 | Dueño de maestros | ADR por centro, temporada, fundo, cuartel, especie, variedad y actividad; fallback sin duplicados | TI/Datos | Fase 0 |
| D14 | Datos heredados | Líneas/periodos normalizados como canónicos; campos antiguos calculados o sólo lectura tras migración verificada | TI/Control gestión | Fase 1 |
| D15 | Hecho real de 25 campos | Mapear cada campo a contabilidad, analítica o módulo origen; cubrir signo, reversa, NC y moneda | Contabilidad/Operaciones | Fase 0 |
| D16 | Estados | Matriz estado–acción–rol–efecto para plantillas, presupuesto, estimación, programas, OP y OT-BPA | Dueño funcional | Fase 0 |
| D17 | Comprometido | Capacidad opcional ligada a `account_budget`, o fallback probado desde PO; ocultar si no existe | Compras/Contabilidad | Fase 2 |
| D18 | Catálogo de informes | Dataset, filtros, moneda, fórmula y conciliación para cada salida/PDF | Control gestión | Fase 0 |

### 4.1 Defectos de los mockups que no deben heredarse

- El texto de estimación multiplica dos veces el rendimiento; el anexo visual
  usa conversión a kg.
- Fertilización no amplifica correctamente por hectáreas, mientras
  fitosanitario sí lo hace.
- El total del plan de cosecha omite semanas visibles después de W50.
- Algunos reportes suman hectáreas dentro de los importes.
- La variación porcentual total se obtiene sumando porcentajes en vez de
  recalcularla desde los totales.
- Hay un `#DIV/0!` en el presupuesto de maquinaria.
- Los estados de estimación, OP y OT-BPA no son consistentes entre texto e
  imágenes.
- Una hoja de plan de cosecha declara rango usado hasta la fila 1.048.576 por
  formato residual; el importador no puede confiar en `max_row`.

## 5. Arquitectura objetivo

### 5.1 Núcleo portable

Se mantiene un único addon de aplicación, `step_management_costs`, con sólo
dependencias estándar imprescindibles. Dentro del addon, el código se divide
por dominios y servicios para evitar un archivo monolítico:

```text
step_management_costs/
├── models/
│   ├── mixins/                 # aprobación, snapshot, compañía
│   ├── masters/                # temporada, origen, grupos, curvas
│   ├── budget/                 # plantillas, revisiones, líneas y meses
│   ├── forecast/               # estimaciones y distribuciones
│   ├── planning/               # tareas, cosecha, programas y OP
│   └── reporting/              # modelos de consulta, no segundo libro
├── services/
│   ├── analytic_actuals.py     # lectura conciliable del real
│   ├── budget_adapter.py       # interfaz propia/estándar
│   ├── import_service.py       # staging, validación e idempotencia
│   └── period_service.py       # temporada, meses y semanas ISO
├── wizard/                     # importación, aplicación y revisiones
├── report/                     # QWeb/PDF y datasets de exportación
├── demo/                       # datos demo declarativos
├── tests/                      # Python, JS/tours cuando aplique
└── upgrades/18.0.2.0.0/       # migración idempotente de la versión actual
```

No se renombrarán modelos actuales ni se borrarán campos en la primera
actualización. Los campos obsoletos se conservarán durante una ventana de
compatibilidad y se migrarán de forma explícita.

### 5.2 Integraciones opcionales

Las dependencias agrícolas no presentes en todos los entornos vivirán en
addons puente pequeños, instalables automáticamente sólo cuando ambas partes
existan:

- `step_management_costs_account_budget` para presupuestos analíticos estándar;
- `step_management_costs_agriculture` para maestros `step_hr`/cuarteles;
- `step_management_costs_bpa` para programa, instrucción y OT-BPA;
- `step_management_costs_machinery` para horas y costos de maquinaria;
- `step_management_costs_operations` para actividades, cosecha y otras OTs.

Los nombres finales de los puentes se validarán en Fase 0. Demo-SyS no debe
recibir el addon paraguas `step_agricultural_access`, porque arrastra el stack
agrícola que esa base no tiene.

### 5.3 Analítica y presupuesto Odoo

Cada centro de costo deberá estar vinculado a una cuenta analítica válida de su
empresa antes de aprobar nuevas operaciones. El upgrade primero inventariará
faltantes y duplicados, creará o seleccionará el plan correcto y producirá un
reporte de saneamiento; no inventará asociaciones ambiguas ni bloqueará la
instalación por datos heredados incompletos. Los gastos compartidos usarán
distribución analítica. Odoo admite
múltiples planes analíticos, obligatoriedad por dominio y distribución
porcentual, lo que permite separar centro, temporada/cultivo y actividad sin
inventar columnas contables paralelas: [Contabilidad analítica de Odoo 18](https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/analytic_accounting.html).

Antes de implementar un motor duplicado se comprobará la edición y la presencia
de `account_budget`. Cuando esté disponible, el módulo agrícola generará y
vinculará presupuestos/revisiones estándar y reutilizará comprometido,
realizado y teórico: [Presupuestos de Odoo 18](https://www.odoo.com/documentation/18.0/applications/finance/accounting/reporting/budget.html).

Si `account_budget` no está disponible, el presupuesto propio continuará detrás
de `budget_adapter.py`. La capacidad “comprometido” se implementará y probará
desde órdenes de compra confirmadas no facturadas, o se declarará opcional y se
ocultará de UI/reportes; nunca se mostrará un cero engañoso.

### 5.4 Modelo de datos nuevo o extendido

Se preservan los modelos actuales y se agregan, como mínimo:

- temporada y períodos año-mes normalizados;
- origen, unidad de cálculo y reglas de imputación por grupo;
- revisión y snapshot de presupuesto;
- lote de importación, línea de staging y error por fila;
- curva y líneas de curva reutilizables;
- estimación, detalle por cuartel y distribuciones semana/calibre/clase;
- planificación semanal y conciliación con presupuesto;
- plan de cosecha, recursos y factores;
- programa agrícola genérico con tipo `fitosanitario` o `fertilizacion`;
- orden de producción semanal y líneas;
- lectura de gasto real analítico con drill-down;
- ajuste histórico externo con procedencia, archivo y bloqueo;
- vistas SQL de comparación; no una copia permanente del asiento analítico.

Los meses y semanas serán líneas, no 12 o 24 columnas físicas. Los Excel pueden
seguir mostrando meses/semanas como columnas, pero el importador los normaliza.
La migración convertirá mayo-abril y temporadas de texto, pondrá en cuarentena
valores no interpretables y demostrará igualdad de totales antes/después. Los
campos legados quedarán calculados o sólo lectura durante la compatibilidad.

Cada maestro compartido tendrá un ADR de propiedad: modelo canónico, fallback
portable, clave de correspondencia, política de deduplicación y migración. Las
vistas SQL `_auto=False` incluirán `company_id`, ACL y regla global, y se
probarán con dos compañías para impedir agregaciones cruzadas.

## 6. Seguridad, aprobación y auditoría

Perfiles mínimos:

| Perfil | Facultades |
|---|---|
| Consulta/Gerencia | Paneles, informes y exportación |
| Presupuestador | Plantillas, presupuestos e importación |
| Planificador/Agrónomo | Estimaciones, planes y programas |
| Aprobador/Control | Aprobar, reemplazar, autorizar y reabrir con motivo |
| Contabilidad | Conciliar, reprocesar y cargar históricos externos |
| Administrador | Maestros, tasas, secuencias, integración y permisos |

Todos los modelos con empresa usarán `_check_company_auto = True`, relaciones
compatibles con `check_company=True` y reglas globales de aislamiento. Odoo
advierte que las reglas de grupo se unen y pueden ampliar acceso, mientras las
globales se intersectan: [Seguridad](https://www.odoo.com/documentation/18.0/developer/reference/backend/security.html) y [consistencia multiempresa](https://www.odoo.com/documentation/18.0/developer/howtos/company.html).

Los métodos públicos validarán rol y transición, no sólo la visibilidad del
botón. Todo documento aprobado conservará `approved_by`, `approved_at`, número
de revisión, motivo, hash/snapshot de líneas, tasa, precios y unidades. Una
versión aprobada será inmutable; la corrección se hará mediante nueva revisión.

## 7. Roadmap por fases

Las duraciones son esfuerzo de ingeniería, no fechas comprometidas. El rango
completo estimado es 70–105 días de ingeniería; con Claude y Codex trabajando
en cortes no solapados, revisión cruzada y decisiones oportunas, el calendario
razonable es 10–16 semanas más el tiempo de UAT del usuario.

| Fase | Esfuerzo | Entregable | Claude | Codex | Puerta de salida |
|---|---:|---|---|---|---|
| 0. Descubrimiento técnico | 3–5 d | Matriz requisito→modelo, 25 campos del real, dueños de maestros, estados, reportes, inventario por base, ADR y decisiones D01–D18 | Audita código y propone diseño detallado | Contrasta con los 36 artefactos y Odoo oficial | Sin contradicciones P0 abiertas para la primera vertical |
| 1. Fundaciones | 6–9 d | Multiempresa, roles, estados, auditoría, maestros mínimos, migración `18.0.2.0.0` | Implementa y prueba | Revisión de seguridad, datos y upgrade | Instalación limpia y upgrade preservan datos |
| 2. MVP vertical | 18–27 d | Plantillas; presupuesto agrícola/general/maquinaria; importaciones; real contable; desviación | Implementa por cortes pequeños con pruebas | Define oráculos, revisa diff y prueba contabilidad/UAT | Cifras concilian con presupuesto y asiento |
| 3. Estimaciones | 8–12 d | Curvas, estimación por cuartel, versiones, Excel y reportes | Implementa modelos y cálculos | Valida fórmulas, tolerancias y casos límite | Kg y distribuciones reconcilian al 100% |
| 4. Plan semanal y cosecha | 8–12 d | Tareas semanales, plan de cosecha y recursos | Implementa servicios de períodos y UI | Prueba cruces de mes/año, W53 y redondeos | Plan reconcilia presupuesto/estimación |
| 5. Fito y fertilización | 10–15 d | Motor común, duplicación/importación, estados, valorización y data normalizada | Implementa núcleo sin acoplarlo a OP | Revisa cálculos, autorización, seguridad y trazabilidad | Programa aprobado reproduce cantidades por hectárea |
| 6. OP, stock e integraciones | 10–15 d | OP semanal/PDF, stock semana-mes-temporada, OT-BPA y puentes operacionales | Implementa contratos y adaptadores | Pruebas de integración y líneas fuera de OP | Sólo OP autorizada alimenta OT; stock concilia; sin duplicidad |
| 7. Informes y endurecimiento | 7–11 d | Reportes, tablero, rendimiento, demo y documentación | Optimiza y agrega tours/reportes | Audita queries, UX, exportaciones y DoD | Sin errores, totales conciliados, volumen aceptable |
| 8. Promoción de ambientes | 3–4 d | Desarrollo → Demo → Demo-SyS condicional | Corrige sólo defectos reproducibles | Ejecuta runbook, evidencia y rollback autorizado | Cada ambiente cumple su gate independiente |

### 7.1 Primera vertical obligatoria

El primer resultado útil será “Presupuesto agrícola aprobado → gasto real
contable → desviación auditable”:

1. Endurecer multiempresa y roles.
2. Normalizar maestros mínimos. Auditar y sanear la cuenta analítica del centro;
   permitir el upgrade, pero bloquear nuevas aprobaciones si falta o cruza
   empresa.
3. Versionar plantillas y presupuestos; distinguir ingreso/costo; conciliar el
   total anual con los meses y congelar el aprobado.
4. Aplicar la plantilla a varios centros sin duplicar líneas al reintentar.
5. Importar el formato normalizado del Anexo 1.6.2.1 mediante staging.
6. Obtener valor sólo de apuntes contables publicados; asignarlo por analítica y
   enriquecerlo con el origen. Inventariar históricos actuales, clasificar su
   procedencia y excluir ambiguos hasta que el dueño los resuelva.
7. Mostrar Budget, Actual, Varianza $ y Varianza % por mes, centro, grupo y
   producto/labor, con drill-down al asiento.

No se comenzará fito/ferti, cosecha u OP antes de que esta vertical concilie.

## 8. Estrategia de importación

Los anexos se usarán para comprender el negocio, no como contrato binario. Se
publicará una plantilla de importación versionada por caso de uso.

Cada importación debe:

- limitar filas/celdas y no recorrer dimensiones residuales del libro;
- verificar extensión, tamaño, cabeceras y versión de plantilla;
- normalizar texto, fechas, monedas y unidades;
- resolver maestros por claves únicas de empresa, nunca por coincidencia vaga;
- mostrar vista previa y errores por fila antes de confirmar;
- usar clave natural más hash del archivo/línea para ser idempotente;
- crear todo o nada por lote, salvo que el usuario elija confirmar sólo filas
  válidas de forma explícita;
- conservar archivo, usuario, fecha, resultado y relación con registros creados;
- impedir fórmulas, vínculos externos o contenido activo como fuente de datos.

## 9. Estrategia de pruebas y Definition of Done

Odoo proporciona pruebas Python, JavaScript y tours; el proyecto seguirá su
marco oficial: [Pruebas en Odoo 18](https://www.odoo.com/documentation/18.0/developer/reference/backend/testing.html).

Pruebas mínimas por entrega:

- cálculos por hectárea, cero hectáreas, UoM, moneda y redondeo;
- temporada mayo-abril, cruces de mes/año, W53 y distribución 100%;
- creación repetida/importación repetida sin duplicados;
- transiciones, inmutabilidad y snapshot después de aprobar;
- `with_user` y `with_company` para cada rol y dos compañías;
- factura de proveedor contabilizada con distribución analítica, nota de
  crédito, reversa/cancelación y drill-down;
- factura de cliente, nota de crédito cliente, multimoneda e
  ingreso/costo/margen;
- un contrato por origen operacional (actividades, maquinaria, inventario,
  movilización, colación, cosecha y fletes) que impida contar OT y asiento dos
  veces;
- `committed` tanto en el adaptador estándar como en cualquier fallback que se
  decida exponer;
- fallback determinista grupo producto→categoría, código único, tasa estimada
  mensual, ausencia de tasa y snapshot multicompañía/multimoneda;
- instalación limpia con y sin demo;
- actualización desde `18.0.1.1.0` conservando IDs, folios y totales;
- JS/tour del panel e importador cuando la UI lo amerite;
- carga cuyo volumen, concurrencia, tiempo máximo y presupuesto de consultas se
  fijarán en Fase 0; mínimo inicial: 100 centros y cientos de indicadores.

Los cálculos se harán por lotes, con `_read_group`, índices selectivos y
medición de consultas donde corresponda, siguiendo las [prácticas de rendimiento de Odoo](https://www.odoo.com/documentation/18.0/developer/reference/backend/performance.html).

Una historia está terminada sólo cuando:

1. Tiene criterio de aceptación trazable al requisito.
2. Incluye prueba automática positiva, negativa y de permisos.
3. No introduce advertencias de instalación, XML, ACL ni registro.
4. Preserva datos al actualizar.
5. Tiene texto de ayuda y traducción de etiquetas visibles.
6. La evidencia de prueba queda registrada en el handoff.
7. Codex revisó el diff y Claude respondió o corrigió cada hallazgo.

## 10. Trabajo coordinado entre Claude y Codex

### 10.1 Reglas de colaboración

- Una sola rama de trabajo: `codex/gestion-costos`.
- Un worktree limpio separado del checkout actual, que contiene cambios de otros
  trabajos y no debe tocarse.
- Ningún agente editará al mismo tiempo los mismos archivos.
- Claude implementa una vertical pequeña y entrega diff, pruebas, supuestos y
  pendientes.
- Codex revisa trazabilidad, arquitectura, seguridad, multiempresa, migración,
  cálculos y pruebas; reproduce los resultados de forma independiente.
- Claude corrige sobre hallazgos concretos; Codex vuelve a verificar.
- Cada fase termina con un documento de handoff y una matriz de requisitos
  actualizada.
- No se hará push, merge ni despliegue sin una instrucción posterior del usuario.

### 10.2 Reparto inicial

**Claude**

- preflight del worktree y auditoría detallada del addon;
- matriz de cobertura y ADR de la primera vertical;
- implementación de Fase 1 en cambios lógicos claramente separados; commits
  locales sólo si el usuario los autoriza;
- migraciones, pruebas y documentación técnica.

**Codex**

- dueño de la especificación consolidada y de las decisiones D01–D18;
- revisión de cada diff y pruebas adversariales;
- verificación de Odoo oficial, analítica y `account_budget`;
- matriz por ambiente, UAT, evidencia de promoción y runbook de rollback;
- coordinación del siguiente corte con Claude.

**Usuario/dueño funcional**

- valida decisiones de negocio y usuarios de prueba;
- acepta las verticales en Desarrollo y los hitos de UAT en Demo;
- autoriza explícitamente promoción o rollback.

## 11. Plan de instalación por ambiente

No se instalará directamente desde el checkout actual. Primero se construye un
artefacto trazable desde el worktree limpio y se prueba contra copias.

| Ambiente | Estado/recomendación | Qué instalar | Gate obligatorio |
|---|---|---|---|
| Desarrollo — `LAB_TAREAS` / `https://desarrollo.stepsapp.cl` | Sí; el addon ya tiene datos y requiere **upgrade**, no recreación | Núcleo más puentes agrícolas disponibles | Instalación vacía, upgrade de clon, backup, pruebas P0 y smoke |
| Demo — `STEPS_DEMO` / `https://demo.stepsapp.cl` | Sí, después de aceptación en Desarrollo | Mismo conjunto de addons que Desarrollo | UAT, comparación de conteos/totales, logs limpios y rollback ensayado |
| Demo-SyS — `STEPS_DEMO_SYS` / `https://demo-sys.stepsapp.cl` | Posible, pero condicional | Sólo núcleo portable; sin `step_agricultural_access` ni datos/scripts agrícolas | Preflight en copia restaurada, dependencias/edición verificadas y utilidad aprobada |

Inventario operativo provisional, que debe reconfirmarse mediante preflight de
sólo lectura y guardarse como evidencia antes de cualquier uso:

| Ambiente | Código | Configuración | Servicio |
|---|---|---|---|
| Desarrollo | `/opt/dev_odoo18/odoo_agriculture` | `/etc/dev_odoo18.conf` | `odoo18-dev.service` |
| Demo | `/opt/demo_odoo18/odoo_agriculture` | `/etc/demo_odoo18.conf` | `odoo18-demo.service` |
| Demo-SyS | `/opt/demosys_odoo18/odoo_agriculture` | `/etc/odoo18-demo-sys.conf` | `odoo18-demo-sys.service` |

Para cada promoción:

1. Congelar commit/artefacto y checksum.
2. Confirmar que no hay instalación/actualización concurrente.
3. Neutralizar o verificar correo, cron, pagos, banca y conectores externos en
   toda copia usada para prueba.
4. Detener el servicio o aislar un único proceso de upgrade.
5. Tomar un snapshot consistente e inseparable de base y filestore; respaldar
   además addon y configuración.
6. Probar restauración en copia aislada.
7. Ejecutar con configuración, base y módulo explícitos, `--stop-after-init`, y
   exigir exit code 0 antes de iniciar el servicio.
8. Revisar logs, menús, ACL, HTTP y casos contables.
9. Comparar conteos y totales antes/después.
10. Conservar evidencia y ventana de observación.

Desarrollo podrá recibir cortes iterativos sólo después del gate técnico de cada
fase y con autorización. Fase 8 representa la promoción formal de release a
Demo y, condicionalmente, Demo-SyS; no obliga a esperar hasta el final para
validar verticales en Desarrollo.

El rollback será restaurar el snapshot completo y el artefacto anterior; no se
usará la desinstalación del addon como rollback. Los upgrades reales vivirán en
`upgrades/<versión>/`, como recomienda la documentación de
[scripts de actualización](https://www.odoo.com/documentation/18.0/developer/reference/upgrades/upgrade_scripts.html), y se validarán primero en una base personalizada clonada: [upgrade de bases con módulos propios](https://www.odoo.com/documentation/18.0/developer/howtos/upgrade_custom_db.html).

Odoo 18 mantiene soporte estándar planificado hasta septiembre de 2027; se
dejará una actividad de compatibilidad con Odoo 19 antes de esa fecha:
[versiones soportadas](https://www.odoo.com/documentation/18.0/administration/supported_versions.html).

## 12. Riesgos y mitigaciones

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Especificación contradictoria | Cálculos incorrectos | Decisiones D01–D12 y pruebas con oráculos aprobados |
| Doble libro de costos | Cifras no conciliables | Real desde analítica; histórico sólo externo |
| Cruces multiempresa | Exposición/corrupción de datos | Checks de compañía, reglas globales y tests RPC |
| Duplicación por import/recalcular | Presupuesto inflado | Staging, claves naturales, constraints e idempotencia |
| Ruptura de datos existentes | Pérdida operativa | Upgrade versionado, backups y prueba sobre clon |
| Dependencias distintas en Demo-SyS | Instalación fallida | Núcleo portable y puentes `auto_install` |
| N+1/tablero lento | Mala adopción | `_read_group`, caché acotada, índices y pruebas de volumen |
| Integración Studio/BPA frágil | OT/programa inconsistente | Puente separado y contrato estable; no IDs hardcodeados |
| Dos agentes colisionando | Cambios perdidos | Un worktree, dueño por archivo y revisión por corte |

## 13. Próximo paso aprobado por este plan

Entregar a Claude el prompt
`docs/PROMPT_INICIAL_CLAUDE_GESTION_COSTOS_2026-09-02.md` para ejecutar sólo:

1. preflight seguro y worktree limpio;
2. Fase 0;
3. diseño e implementación del primer corte de Fase 1;
4. pruebas y handoff a Codex.

Claude no queda autorizado por este plan a desplegar, modificar bases remotas,
ejecutar scripts manuales de migración, hacer push ni iniciar fases posteriores
sin revisión.
