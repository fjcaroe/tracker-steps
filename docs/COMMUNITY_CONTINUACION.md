# Continuidad de migración Community — Cerro El Plomo

Estado acumulado, aceptación y siguiente prompt vigentes:
[COMMUNITY_CONFIGURACION_NOMINA.md](COMMUNITY_CONFIGURACION_NOMINA.md), pareja D
de e097560b: 343/244 casos sin fallos y dos omisiones por entorno, catorce campos
originales y reporte desde valores almacenados. La configuración original y la
conversión integral siguen abiertas. Los hitos inferiores son históricos; no
sustituyen las puertas pendientes de esa hoja.

## Pedido y límites

El usuario autorizó el 27-10-2026 planificar y comenzar la independencia real
de Enterprise para que los módulos propios funcionen sobre Community. Solicitó
un prompt para continuar en otra ventana. Leer `PLAN_COMMUNITY_CERRO.md`.
No se ha autorizado ni ejecutado una desinstalación masiva en producción.
No cambiar parámetros de vencimiento, ocultar avisos ni copiar fuentes OEEL-1.

Leer antes de continuar `AGENTS.md`, `~/.odoo/environments.json`,
`docs/OPERACION_ODOO_CANONICA.md` y `docs/WORKFLOW_GIT_COMPARTIDO.md`.
Desarrollo es el único QA público. QA-Cerro conserva sus ejercicios y datos.
Trabajar en un worktree propio desde la rama canónica actualizada
`origin/codex/ambientes-canonicos-reparacion`, sin pisar cambios ajenos.

## Inventario de partida

Informe `CERRO_EDICION_Y_DEPENDENCIAS_20261026.md`: 372 módulos instalados,
140 Enterprise OEEL-1; 79 de 91 módulos prefix-step dependen de Enterprise.
Vencimiento observado: 31-10-2026. Estos datos son una auditoría, no un respaldo
actual para publicar. Producción continúa Enterprise y el vencimiento no se
soluciona con esta primera extracción. No prometer completar antes de esa fecha.

`studio_customization` es metadata virtual sin manifiesto en disco. Los doce
campos manuales requieren clasificación: incluyen campos dinámicos nativos de
planes analíticos, no asumir que todos deben convertirse desde Studio.

## Código de la primera extracción

Rama de trabajo: `codex/community-foundation-20261027`.
Base canónica inicial: `9854563`.

- `step_accounting_multicurrency_core` 18.0.1.0.0, LGPL-3, depende solo de
  `account`. Cálculos, campos y vistas movidos desde el módulo anterior sin
  cambiar la lógica monetaria ni columnas SQL.
- `step_accounting_multicurrency` 18.0.2.1.0 conserva exclusivamente el puente
  de informes Enterprise, depende del núcleo y `account_reports`.
- Hooks de adopción: XMLIDs nuevos y antiguos apuntan a los mismos registros.
  El núcleo toma propiedad antes de actualizar el puente, conservando campos,
  vistas, IDs y valores. Esto no acredita todavía desinstalar todo el puente.
- Once pruebas funcionales de asientos, moneda extranjera, redondeo, pagos,
  fechas históricas, formularios, aliases, conflictos y protección al retirar
  metadatos de un namespace compartido. Los fixtures hacen rollback.
- `tools/community/check_dependencies.py`: comprueba dependencias declaradas
  con el inventario privado y manifiestos actuales. Rechaza Enterprise y
  dependencias desconocidas. No sustituye revisar imports ni probar flujos.
- `tools/community/validate_finance_foundation.py`: solo bases privadas,
  bloqueo compartido; modos `community` y `cerro-copy`, sin despliegue.

Commits de código iniciales: `bd08ac0`, `e0e59c8`, `5b9e321`, `10ad8b2`.
Plan/control de dependencias: `301d0e8`. Reparación de lectura privada del dump:
`0608556`. El último ajuste del script no cambia el paquete de addons probado.

## Evidencia privada

No subir dumps, datos, capturas ni credenciales al repositorio público.

- Windows: `C:/Users/tito4/.codex/local-artifacts/community-foundation-20261027/`.
- Auditoría previa: `C:/Users/tito4/.codex/local-artifacts/cerro-license-20261026/readiness.json`.
- SSH documentado: `odoo-new`.
- Community oficial clonado desde `https://github.com/odoo/odoo.git`, rama 18.0,
  revisión `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
- Ensayo limpio exitoso: `/opt/steps-validation/community-foundation-final-20261027/community/`,
  DB `COMMUNITY_FOUNDATION_20261027B`: 11 pruebas aprobadas, cero Enterprise,
  aliases iguales y formulario nativo comprobados. Ver `passed.json`,
  `tests.log`, `verify.log` y `runtime-revision.txt`.
- Paquete de addons del ensayo: commit `10ad8b2`. Tar SHA256
  `295344469acc1aeaae8566a423324e9c15a4ad01b385a802efeb22f21504fcda`.
- Primer ensayo Community A tuvo dos fallos de fixture, corregidos antes del
  ensayo limpio B. El primer intento de restauración Cerro A falló por permisos
  de lectura de dump; no modificó producción. Sus artefactos se conservaron.

## Siguiente trabajo

1. Confirmar la evidencia de la copia Cerro registrada al final de este archivo.
2. Inventariar y desacoplar Tesorería de `account_reports`: contratos de datos,
   menús, permisos y consultas. Evaluar OCA Financial Reports 18.0 como base,
   adaptando los importes operacionales históricos; no asumir equivalencia.
3. Separar los maestros agrícolas y operacionales de Nómina/Gantt en `step_hr`,
   conservando modelos, IDs, relaciones y liquidaciones históricas. No crear
   tablas alternativas ni recalcular nómina pagada.
4. Después: DTE Chile/exportación, Calidad y componentes de interfaz; retirar
   Enterprise solo cuando cada reemplazo conserve datos y flujo real.
5. Ensayar conversión integral en copia fresca, cero OEEL-1 y fuentes Community,
   conciliación, restauración y aceptación funcional antes del corte controlado.

Para el control estático:

```powershell
python tools/community/check_dependencies.py --audit C:/Users/tito4/.codex/local-artifacts/cerro-license-20261026/readiness.json step_accounting_multicurrency_core
```

Debe aprobar; al cambiar el último argumento por `step_accounting_multicurrency`
debe rechazar el puente Enterprise. No marcar como independiente toda Tesorería.

Al entregar: commits, push, integración revisada en canónica cuando corresponda,
y `python tools/git/verify_handoff.py --require-pushed` obligatorio.

## Prompt para la siguiente ventana

> Continúa la migración real de Cerro El Plomo de Odoo Enterprise a Community.
> Lee AGENTS.md, el registro privado de ambientes, la operación canónica, el
> workflow Git, docs/PLAN_COMMUNITY_CERRO.md y docs/COMMUNITY_CONTINUACION.md.
> Ya se extrajo y validó step_accounting_multicurrency_core; el puente de informes
> todavía depende de Enterprise. Revisa las evidencias y continúa con Tesorería
> e informes sin account_reports, preservando modelos, IDs, permisos, históricos
> y saldos. Trabaja desde la canónica actualizada en un worktree propio. Prueba
> con fuentes Community y en copia fresca de Cerro; no retires Enterprise en
> producción, no alteres vencimientos ni refresques QA-Cerro. Guarda commits,
> push y verifica el handoff antes de terminar. No copies código Enterprise.

### Punto exacto para Tesorería

La búsqueda de referencias actuales en `step_account_treasury` encontró dos
entradas del manifiesto (`account_reports` y el antiguo multimoneda) y cinco
acciones en `views/treasury_menus.xml`: conciliación bancaria, mayor de socios,
estado de flujo de caja, cuentas por cobrar y por pagar. Los modelos propios
no mostraron referencias directas a `account.report` en esa búsqueda. Preparar
un núcleo dependiente del nuevo multimoneda y un puente opcional para las cinco
acciones, conservando sus XMLIDs/menús y permisos al migrar. La ausencia de otras
referencias en la búsqueda no sustituye instalar y probar el paquete Community.
Los lotes `account.batch.payment` siguen en su puente propio y requieren un
reemplazo real que preserve el historial; no quitarlos del manifiesto solamente.
## Cierre de la primera etapa — evidencia completada

- Copia fresca final de Cerro: DB `MANAGEMENT_QA_CERRO_COMMUNITY_20261027E`,
  `/opt/steps-validation/community-foundation-cerro-20261027E/cerro-copy/`.
  `passed.json` y `verify.log` confirman validación completa del ensayo.
- 35 pruebas aprobadas: 11 del núcleo y 24 de pagos T123. Versiones instaladas
  en la copia: núcleo 18.0.1.0.0 y puente 18.0.2.1.0. La copia aún tiene 140
  Enterprise, intencionadamente: se ensayó una extracción, no su retiro total.
- Se compararon 839 tablas de negocio antes y después; importes, relaciones,
  fechas, registros y valores se conservaron. Los 21 IDs de campos conservan
  su identidad; los XMLIDs de núcleo y puente apuntan a los mismos registros.
- Las huellas textuales detectaron un cambio de escala en un peso de envase:
  `15.00` pasa a `15`. El comparador ahora normaliza únicamente ceros decimales
  fraccionarios de números SQL exactos y conserva la huella textual adicional.
  No redondea ni transforma textos, nulos o importes a Python float. Tres
  pruebas sobre PostgreSQL real verifican equivalencia, detección de una
  fracción de 24 decimales y distinción de textos numéricos.
- `tools/community/test_fingerprint_postgres.py` reproduce esas tres pruebas
  mediante tablas TEMP de sesión y solo acepta nombres de bases privadas.
- La huella textual difiere únicamente en `stock_package_type`; las huellas
  de valores concuerdan en todas las tablas. La representación original queda
  en `business-before.json`, además del dump de origen; no se corrigieron ni
  borraron datos para obtener el resultado.
- Se reutilizó `tools/ops/run_sag_cerro_upgrade.py` con
  `preserve_fruit_constraints.py`: conserva las FKs canónicas ya validadas
  mientras el cargador pasa por definiciones anteriores. Dos pruebas del
  adaptador aprobaron; las relaciones finales de categoría/clase de recepción
  siguen apuntando al maestro compartido con restricciones validadas.
- El primer ensayo B encontró ese problema de orden de carga. C aprobó 35
  pruebas pero su comparación textual rechazó `15.00`/`15`. D se detuvo antes
  de actualizar por una función de normalización no disponible en PostgreSQL
  12; se sustituyó por operaciones exactas compatibles. E completó todo.
  Artefactos de los intentos conservados; no se usaron como entregas exitosas.
- Los 21 archivos de ambos addons son idénticos entre el ensayo Community y E;
  `source-files.json` en ambas carpetas guarda SHA256 por archivo. El código
  funcional no cambió desde `10ad8b2`. Herramientas posteriores mejoran el
  resguardo, comparación, compatibilidad PostgreSQL 12 y velocidad del ensayo.
- Para evitar compilación JIT innecesaria durante las huellas, se desactivó
  JIT solamente en la base privada E. La versión final del script lo hace en
  su propia conexión SQL; no modifica la configuración de producción.
- Evidencia también descargada fuera de Git: `community-passed.json`,
  `community-verify.log`, `cerro-passed.json`, `cerro-verify.log`,
  `cerro-C-tests.log` y `cerro-E-tests.log` en la carpeta Windows indicada.
- Producción continúa con `step_accounting_multicurrency` 18.0.2.0.1; el núcleo
  nuevo no se instaló allí. QA-Cerro y Desarrollo público no se modificaron.
  No se publicaron fuentes en servicios activos ni se alteró el vencimiento.

La etapa 1 queda validada como paquete preparatorio. El siguiente bloque es
Tesorería/informes (cinco acciones concretas arriba), antes del retiro integral.
No usar estas evidencias como respaldo fresco para una futura publicación.

## Segunda extracción — Tesorería e informes, 27-10-2026

Esta sección actualiza el punto de continuación anterior. Trabajo desde
`669e3a1`, en worktree propio y rama `codex/community-treasury-20261027`.
Commits de implementación: `2a678c8`, `c882b81`, `2598602`.

- `step_account_treasury` 18.0.1.3.0 conserva todos sus modelos, cálculos,
  tablas, formularios y permisos. Ahora depende de
  `step_accounting_multicurrency_core`, sin `account_reports`.
- `step_account_treasury_reports` 18.0.1.0.0 es el puente opcional para las
  cinco acciones Enterprise identificadas. Conserva el adaptador de informes
  multimoneda. No implementa ni copia el motor Enterprise.
- La premigración de Tesorería exige instalar el puente en la misma operación
  cuando existen los menús anteriores. Adopta sus XMLIDs con alias en ambos
  namespaces; no recrea menús ni escribe acciones, grupos o fechas.
- El hook del puente solo crea los accesos faltantes en instalaciones nuevas.
  No usar XML `noupdate` para adoptar estos menús: el modo de instalación también
  escribe los registros existentes. Dos pruebas del puente verifican menús
  personalizados intactos y creación de accesos con alias históricos.
- Tres pruebas del núcleo comprueban adopción idempotente con permisos,
  rechazo de alias en conflicto y bloqueo de actualización sin puente.
- El control estático aprueba el cierre de dependencias de Tesorería (28) y
  T123 (29); rechaza correctamente el puente Enterprise. T123 se probó en la
  copia Cerro; no se afirma todavía su instalación funcional pura Community.

Paquete de los addons: `2598602`. Archivo privado `treasury-final.tar`, SHA256
`05e85905fcf82ef36a7b646527ac418d06ecf17641c55b62160c87ac1b55c0c9`.
Los 60 archivos de los cuatro addons coinciden por SHA256 entre ambos ensayos.
El validador es `tools/community/validate_treasury_extraction.py`; no publica,
solo admite bases privadas y utiliza `/run/lock/steps-environments.lock`.

### Evidencia y límites

Community final: `/opt/steps-validation/community-treasury-20261027B/community/`,
DB `COMMUNITY_TREASURY_20261027B`, 62 pruebas aprobadas, cero Enterprise,
formularios comprobados. Fuentes oficiales 18.0 en la misma revisión
`4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`. El primer ensayo A también aprobó
62 pruebas; B repitió la instalación con el paquete final del puente.

El primer ensayo Cerro A aprobó 86 pruebas y conservó valores y permisos,
pero la comparación estricta encontró que el XML de instalación escribía las
fechas de modificación de los cinco menús. No se aceptó como entrega; el hook
de creación selectiva y sus dos pruebas corrigen ese comportamiento.
El ensayo B se detuvo al cargar Nómina porque la extracción del overlay excluyó
también una carpeta interna `tools`; no se reutilizó su base. Al preparar C se
anclaron las exclusiones de tar a la raíz con `--anchored`.

Ensayo Cerro final C: DB `MANAGEMENT_QA_CERRO_TREASURY_20261027C`,
`/opt/steps-validation/community-treasury-cerro-20261027C/cerro-copy/`.
`passed.json` y `verify.log` confirman 88 pruebas sin fallos, formularios y
aliases comprobados. Se conservaron los valores de 842 tablas, 225 IDs de
campos, 21 registros de ACL/reglas/grupos y las relaciones de grupos/usuarios.
Los cinco menús conservan sus IDs, acciones, restricciones, estado, padres,
secuencias y fechas de modificación. Las comparaciones JSON son estructurales;
el orden de las claves de un objeto JSON no es significativo.

La única diferencia de representación textual vuelve a ser
`stock_package_type`, con la normalización decimal exacta ya validada en la
primera etapa. Las huellas de valores coinciden en todas las tablas. La copia
mantiene sus 140 Enterprise; no representa todavía una conversión integral.
El dump de origen y todos los intentos se conservaron fuera de Git.

Evidencia Windows: `C:/Users/tito4/.codex/local-artifacts/community-treasury-20261027/`.
`evidence.tar.gz` contiene resultados, logs y huellas de todos los intentos;
los dumps y filestores permanecen en los directorios privados del servidor.
La evidencia de fuentes en `source-files.json` registra los mismos 60 archivos
de addons en Community B y Cerro C.

### Siguiente trabajo real

La etapa 2 sigue abierta. El puente conserva los cinco accesos de informes
Enterprise; no es su sustituto Community. La instalación Community dispone de
la planificación, hojas, resumen y exportaciones propios de Tesorería, sin
anunciar esos cinco informes todavía no reemplazados. Evaluar los candidatos
OCA ya registrados contra los contratos reales de mayor, antigüedad y saldos;
definir y conciliar por separado flujo de efectivo y conciliación bancaria.
Conservar los mismos menús al conectar cada reemplazo validado. No retirar el
puente ni `account_reports` hasta completar estos contratos y sus dependientes.

`step_account_treasury_batch` sigue separado y depende de
`account_batch_payment`: preservar sus lotes históricos y reemplazar el flujo
real antes de retirar Enterprise. Probar también T123 en instalación Community
pura antes de declararlo funcionalmente independiente. La separación de los
maestros de `step_hr`, DTE y Calidad permanece posterior.

No se publicó en servicios activos, no se retiró Enterprise en producción,
no se alteraron vencimientos y no se refrescó QA-Cerro. Estos ensayos privados
no sustituyen Desarrollo público ni son un respaldo fresco de una publicación
futura.

## Tercer bloque completado — cinco alternativas Community y QA-Cerro

Actualización del 27-10-2026: esta sección reemplaza el siguiente paso del bloque
anterior. El usuario autorizó las cinco alternativas y su entrega en QA-Cerro,
sin modificar producción ni refrescar los ejercicios. Se trabajó en el worktree
propio anterior, con rama nueva `codex/community-reports-20261027`, desde `25d11ac`.

### Código y alcance entregados

- `step_treasury_community_reports` 18.0.1.0.0: mayor de socios, antigüedad de
  cobros/pagos, efectivo realizado y control de conciliación bancaria. Asistente
  transitorio con filtros, HTML, CSV, PDF y enlaces a documentos nativos.
- `step_account_treasury` 18.0.1.3.1: su adopción admite el reemplazo Community.
  La prueba por cantidad pedida fija `invoice_policy=order` explícitamente;
  las políticas por entrega y compra tienen sus propias pruebas. No se cambian
  productos ni políticas de facturación de los ambientes activos.
- Los cinco menús mantienen IDs, nombres, padres, grupos, secuencias y estado.
  Solo cambia su acción de destino y el registro de esa modificación.
  Las cinco acciones globales de `account_reports`, con sus IDs y fechas,
  permanecen intactas; otros accesos Enterprise siguen funcionando.
- No se asignan perfiles. Se comprueban lectura contable, empresas autorizadas
  y visibilidad del menú también al invocar el método por RPC. El usuario de
  prueba de Cerro/QA es uno existente autorizado, sin superusuario y con la
  empresa Cerro seleccionada por su identificación canónica, no por el valor
  predeterminado del usuario. Los totales concuerdan con el libro nativo.
- El PDF usa un layout propio sin recursos externos, limitado a este reporte;
  no modifica el layout de otros documentos. Se generó y revisó visualmente
  una muestra sintética horizontal, fuera de Git.

Contratos, permisos y límites detallados: `INFORMES_COMMUNITY_TESORERIA.md`.
El efectivo es directo y realizado, todavía sin clasificación normativa por
actividades. El control bancario distingue saldos al corte y estado actual de
extractos; no publica ni concilia automáticamente. Las columnas operacionales
conservan la valoración histórica declarada, no una liquidación de FX realizada.

### Paquete y ensayos aceptados

Código del paquete: `82a3e8f` (cálculos y presentación definitivos desde
`043002e`; el ajuste posterior del paquete solo hace explícita la política del
fixture). `reports-release.tar` SHA256:
`e45e3a4b2049887fd9ff99a24b530cf08b4d97e3cd9fffa072a4e558088f6bbc`.
Los **70 archivos de cinco addons** coinciden en los cuatro ensayos y ambos
overlays publicados. Huella agregada de esos archivos:
`a0c3a26550b6cc6aeb809674410c0ea44e424d821c62520b985638fa77875505`.
Las herramientas operativas recibieron resguardos adicionales sin cambiar esos
archivos de addons.

| Ensayo | Base privada | Pruebas | Directorio en `/opt/steps-validation/` |
| --- | --- | --- | --- |
| Community oficial | `COMMUNITY_TREASURY_REPORTS_20261027J` | 77 | `community-reports-20261027J/community/` |
| Cerro fresco | `MANAGEMENT_QA_CERRO_TREASURY_REPORTS_20261027C` | 101 | `community-reports-cerro-20261027C/cerro-copy/` |
| Desarrollo fresco | `MANAGEMENT_QA_CERRO_TREASURY_REPORTS_DEV_20261027B` | 101 | `community-reports-dev-20261027B/cerro-copy/` |
| QA-Cerro fresco | `MANAGEMENT_QA_QA-CERRO_reports_20261027a` | 101 | `community-reports-qa-20261027A/cerro-copy/` |

Community tiene cero Enterprise y usa las fuentes oficiales limpias en la
revisión `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`. Las copias conservan
Enterprise: Cerro 140, Desarrollo 168 y QA-Cerro 137, según su inventario propio.
No se igualaron instalaciones ni se retiraron módulos para obtener el resultado.
Se conservaron valores en 842 tablas de Cerro/QA y 916 de Desarrollo, 225 IDs
de campos y 21 registros de ACL/reglas/grupos, además de sus relaciones.
Los cinco registros de acciones Enterprise se comparan íntegramente. Para el
resto de acciones cliente también se conserva el contenido; se admiten solo
fechas/autor de actualización de metadatos recargados normalmente por Odoo.

`validate_community_reports.py` guarda dumps, huellas antes/después, acciones,
menús, campos y permisos. El permiso temporal del rol QA a su única copia privada
se retiró al finalizar. Las comprobaciones adicionales de empresa canónica están
en `company-verify.log` de Cerro y `post-start-verify.log` de la entrega QA.

### Entregas verificadas

Overlays privados y recuperación completa, bajo `/opt/steps-community/releases/`:

- Desarrollo: `development/a0c3a26550b6cc6aeb809674410c0ea44e424d821c62520b985638fa77875505-20261027054222/`.
- QA-Cerro: `qa-cerro/a0c3a26550b6cc6aeb809674410c0ea44e424d821c62520b985638fa77875505-20261027055330/`.

`deployed.json`, `runtime-passed.json`, `http-passed.json` y los logs de cada
directorio confirman versiones, archivos efectivos, configuración del proceso,
formularios, menús y cinco flujos con usuario autorizado. Versiones instaladas
en ambos: núcleo multimoneda 18.0.1.0.0, puente previo 18.0.2.1.0, Tesorería
18.0.1.3.1 y reportes Community 18.0.1.0.0. El puente opcional Enterprise de los
cinco menús no se instala como dependencia del reemplazo.

Acceso de revisión: `https://qa-cerroelplomo.stepsapp.cl`, Tesorería / Informes
y Tesorería / Conciliación bancaria. Desarrollo también está publicado para
revisión. Se conservaron las bases y filestores activos; no se restauró ninguna
base sobre QA-Cerro. Dumps, configuración previa y filestore recuperable quedan
en esos directorios, fuera de Git.

Se detectaron y resolvieron dos resguardos operativos durante la publicación:

- El cron normal de Tracker avanzó su marcador durante el ensayo de Desarrollo.
  Solo se admiten cambios de `last_sync` y `write_date`, comparando todos los
  otros campos/registros contra la copia intacta. Se preserva el corte actual
  completo bajo el servicio detenido; no se restaura el marcador antiguo.
- La recarga de datos activó una definición cron en QA. El control detuvo el
  cierre; `finalize_qa_reports.py` comprobó respaldo original con cero cron
  activos, datos y permisos intactos y versiones correctas, restableció la
  neutralización y verificó todo sin reinstalar ni restaurar la base.

Después del reinicio y la revisión final: cron, correo y fetchmail activos = 0,
planificador configurado en 0, salida de red bloqueada y acceso del rol QA a la
base de producción rechazado. También pasó el formulario nativo de Packing con
el perfil existente. No se amplió el firewall ni se cambiaron claves.
`final-isolation-state.json` registra estas comprobaciones. La configuración,
fuentes y versiones de producción siguen idénticas al contrato del ensayo Cerro.

Evidencia Windows: `C:/Users/tito4/.codex/local-artifacts/community-reports-20261027/`.
`evidence.tar.gz` contiene ensayos aceptados y entregas; omite dumps, filestores
y configuraciones privadas. Los intentos anteriores conservan sus artefactos en
el servidor. Sus correcciones incluyeron instalación/encoding del módulo nuevo,
layout PDF sin recursos HTTP, separación de auditoría de acciones y el fixture
de ventas que dependía de un default distinto en Desarrollo. `steps_api` continúa
como faltante legado documentado de Desarrollo; se usa el mismo clasificador
canónico para esa condición previa, sin crear un stub ni suprimir errores nuevos.

### Próximo bloque

Las cinco alternativas están disponibles para probar en QA-Cerro. No equivalen
todavía a la conversión integral: siguen pendientes los lotes de pago Enterprise,
la separación de maestros de `step_hr`, DTE, Calidad y los demás dependientes.
T123 pasó su regresión en las tres copias; todavía requiere una instalación pura
Community propia antes de declarar independiente todo su flujo.
La clasificación normativa del flujo de efectivo requiere contrato funcional y
conciliación adicionales sobre maestros nativos, sin tablas ni cuentas paralelas.

Producción no recibió el paquete, no se alteraron vencimientos y QA-Cerro no se
refrescó. No usar estos dumps de ensayo como respaldo fresco de otra publicación.

## Cuarto bloque validado — maestros y consumidores agrícolas (27-10-2026)

Implementación guardada en `codex/community-operations-core-20261027`, hasta
`43dcc6c`, sobre la canónica `7926598`. La canónica recibe también estos commits
y esta actualización de continuidad. Este bloque sustituye la separación de
maestros que figuraba pendiente arriba; no completa la conversión integral.

### Paquete

- `step_agriculture_core` 18.0.1.0.0: 18 modelos, 181 campos declarados y 250
  identificadores explícitos, además de campos heredados y selecciones.
- `step_hr` 18.0.1.5.0: conserva personal/operación y los puentes aún Enterprise;
  depende del núcleo para los maestros. No desinstalarlo.
- `step_agriculture_catalogs` 18.0.1.1.0, `step_packing` 18.0.1.2.0,
  `step_inventory_fruit_tag` 18.0.1.1.0 y
  `step_management_costs_agriculture` 18.0.2.2.0 consumen el núcleo Community.
- Se incluye `step_management_costs` 18.0.21.1.0 con fixtures contables propios.

Se preservan modelos, tablas, relaciones, IDs, maestros compartidos y alcance
multicompañía. Los dos namespaces apuntan a los mismos registros. Los menús
anteriores mantienen sus restricciones; el acceso independiente del núcleo
queda inactivo en destinos donde ya existen los menús de Actividades.
Ver `COMMUNITY_MAESTROS_AGRICOLAS.md` para el contrato y los adaptadores de
actualización. No utilizar el publicador de cinco módulos de Tesorería para
este paquete de siete módulos.

### Ensayo aceptado y conservación

Paquete generado mediante `git archive` de `43dcc6c`, con 364 archivos de addons
idénticos en ambos ensayos. SHA256 del mapa ordenado de archivos:
`ae874ab24db05d2ea8dd61c8cf180be40466db498cae9340029917eadd0ebd9a`.
Raíz `/opt/steps-validation/community-agriculture-20261027J/`:

- `community/`, base `COMMUNITY_AGRICULTURE_20261027J`: 309 pruebas sin fallos;
  66 módulos instalados, cero Enterprise y sin `step_hr`. Runtime oficial
  Community limpio en la misma revisión `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
- `cerro-copy/`, base `MANAGEMENT_QA_CERRO_AGRICULTURE_20261027J`: copia fresca
  del destino, 309 pruebas sin fallos. Mantiene sus 140 Enterprise; 373 módulos
  instalados al añadir el núcleo. No es una prueba de retiro Enterprise.
- Tres pruebas locales del preservador de enlaces verifican que solo un reset
  de grafo idéntico puede omitirse; cambios de vista, modo, secuencia o comandos
  distintos siguen el comportamiento normal y deben superar la comparación.

La comparación conservó los valores de 846 tablas de negocio; todos los
1.217 modelos, 26.987 campos y 5.071 valores de selección originales;
2.322 ACL, 610 reglas, 1.327 menús y 417 enlaces de acción/vistas originales.
También se conservaron membresías de menús, reglas y grupos implícitos,
históricos de mensajes/seguimiento/seguidores y adjuntos. Las únicas
normalizaciones son la escala numérica ya documentada y los timestamps de
escritura de iconos binarios de menú recargados por Odoo; sus IDs, contenido
y demás metadatos deben permanecer exactos. Las nuevas membresías del menú
del núcleo se separan explícitamente de las originales.

Ambos ensayos ejecutaron además menús y formularios sin `sudo`. Cerro utilizó
el perfil existente UID 6 y la empresa canónica identificada por su VAT, ID 2;
consultó los seis maestros y guardó un formulario nativo de Packing dentro de
una transacción revertida. No se otorgaron grupos al usuario para pasar.

Los intentos previos conservan sus artefactos. Revelaron y corrigieron:
la dependencia de Labores respecto de los campos de producto; obligatoriedad
intermedia incompatible con cuentas/productos generales y catálogos
compartidos; etiquetas con encoding dañado; recreación de enlaces y orden de
menús; y fixtures que heredaban cuentas obsoletas/impuestos del cliente o
suponían una navegación sin agrupaciones. No se corrigieron datos del cliente
para hacer pasar las pruebas.

`passed.json`, `source-files.json`, `verify.log`, logs de pruebas y contratos
antes/después están en ambos stages. Los archivos, configuración y versiones
del servicio de origen quedaron idénticos al contrato inicial. Producción
mantiene 372 módulos y 140 Enterprise. El vencimiento registrado permanece
intacto; este paquete no lo resuelve.

Evidencia local:
`C:/Users/tito4/.codex/local-artifacts/community-agriculture-20261027/`.
`evidence-J.tar.gz` omite dumps, filestores y configuraciones. El dump de ensayo
permanece privado en el servidor; no sirve como respaldo de un despliegue futuro.

### Continuación necesaria

Este paquete todavía no se publicó en Desarrollo ni QA-Cerro. Los informes
Community de Tesorería siguen siendo el último paquete desplegado allí.
Preparar ensayos frescos de esos destinos, comprobar sus perfiles y publicar
el mismo paquete probado mediante un publicador específico, con respaldo,
bloqueo compartido, overlay privado, ausencia de downgrade y neutralización QA.
No refrescar QA-Cerro ni utilizar una copia de producción sobre su base activa.

`COMMUNITY_INVENTARIO_ENTERPRISE_20261027.md` enumera los 140 módulos Enterprise.
El código candidato deja seis apps propias sin caminos declarados Enterprise
respecto de producción, pero 73 de las 91 aún tienen alguno. Eso no acredita
que las seis tengan todos sus flujos validados en instalación pura: por ejemplo,
la prueba pura propia de T123 sigue pendiente. Las cuatro fronteras agrícolas
de este bloque sí forman parte de los 309 tests del paquete.

Prioridades siguientes: separar los demás consumidores de `step_hr`, resolver
lotes de pago, motor de Nómina/contratos y salidas chilenas, DTE/CAF/SII,
Calidad y vistas restantes. No sustituir datos históricos, copiar código
Enterprise ni crear stubs. Falta el ensayo integral de una copia con fuentes
Community exclusivamente y el ensayo de recuperación antes de cualquier corte.
No se retiró Enterprise de producción ni se alteraron controles de vencimiento.

## Quinto bloque validado — Productores y calendarios Community (27-10-2026)

Fuente del paquete: `70523bc`, rama `codex/community-producers-20261027`, sobre
la canónica `10051bf`. Los commits de esta rama y la continuidad se integran
también en `codex/ambientes-canonicos-reparacion`. No se publicó este bloque en
servicios activos. Ver el contrato en `COMMUNITY_PRODUCTORES.md`.

### Implementación y versiones

- `step_agriculture_core` 18.0.1.1.0 adopta ocho campos de `res.partner`,
  su formulario agrícola y la acción de contratistas. Conserva IDs, columnas
  y XMLIDs antiguos como alias. El contrato total declara 189 campos y 260 IDs.
- `step_hr` 18.0.1.6.0 conserva el puente opcional del mapa y el override
  booleano bancario legado. No retirar este módulo ni convertir ese campo
  silenciosamente. Una instalación pura conserva la relación bancaria nativa.
- `step_producers` 18.0.1.9.0 usa el núcleo y `hr` Community, sin Nómina.
- `step_producer_contract_report`, `step_producer_estimate_report` y
  `step_producer_purchase_mode`, 18.0.1.1.0, usan calendarios Community,
  conservando sus IDs de vistas/acciones/menús y enlaces. Los XMLIDs históricos
  `report_gantt` y los de vistas heredadas se conservan; ahora son calendarios.
- El paquete incluye `step_management_costs_producers` 18.0.1.0.0 y los siete
  módulos agrícolas anteriores: doce módulos, once expuestos a Community.

Los calendarios son de consulta, junto con listado y tabla dinámica. No se
editan vencimientos ni semanas. `calendar_end` es un cálculo no almacenado que
adapta el fin exclusivo original al fin inclusivo de Calendar; la búsqueda por
rango se traduce al campo original. Las cuotas duran su día y las semanas
terminan el domingo. Ambos renderizadores nativos inspeccionados (Community y
runtime Cerro) añaden un día al límite Date; no se corrigió esto escribiendo
datos de negocio. Las proyecciones SQL y sus fórmulas monetarias no cambiaron.

### Evidencia aceptada

Raíz `/opt/steps-validation/community-producers-20261027G/`, paquete generado
mediante `git archive` de `70523bc`. Los 463 archivos de addons son idénticos
en los dos ensayos. SHA256 del mapa ordenado de archivos:
`1f3c3000bedcf6a32722cb26a9632580655fec5f602b61fa30536a956bcb9006`.

- `community/`: base `COMMUNITY_AGRICULTURE_PRODUCERS_20261027G`, 351 pruebas
  sin fallos, 77 módulos instalados y cero Enterprise; sin `step_hr`, `web_gantt`,
  `web_map` ni Nómina Enterprise. Runtime oficial limpio, misma revisión
  `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4` de los bloques anteriores.
- `cerro-copy/`: base `MANAGEMENT_QA_CERRO_AGRICULTURE_PRODUCERS_20261027G`,
  copia fresca de Cerro, 351 pruebas sin fallos. Conserva sus 140 Enterprise;
  373 módulos instalados por la adición del núcleo. No es la conversión integral.
- Se conservaron los valores de 848 tablas y proyecciones, incluidos los dos
  informes SQL completos. Se preservaron los 1.217 modelos, 26.987 campos,
  5.071 selecciones, 2.322 ACL, 610 reglas y 1.327 menús originales. Se añaden
  únicamente dos campos visuales calculados a los informes.
- Los 417 enlaces originales entre acciones y vistas conservaron IDs y
  atributos; solo se permiten dos cambios identificados de modo Gantt a Calendar.
  Se conservaron membresías, históricos y adjuntos, con las normalizaciones
  exactas ya documentadas para escala numérica e iconos de menú.
- El verificador nativo abrió maestros, Packing y ficha de productor y consultó
  calendarios/listas/pivots. Cerro utilizó el usuario existente UID 6, empresa
  canónica ID 2, sin `sudo` ni asignación de grupos. Las altas de formulario
  se revirtieron. Las consultas reales conservaron los indicadores de falta de
  valorización; no se inventaron precios para obtener totales.

`passed.json`, `source-files.json`, `verify.log`, contratos antes/después y logs
están en los stages. La configuración, archivos y versiones del servicio de
origen quedaron idénticos al contrato inicial. Producción mantiene 372 módulos
y 140 Enterprise, sin cambios en vencimiento. QA-Cerro no se refrescó ni recibió
este bloque. Los informes de Tesorería siguen siendo el último despliegue allí.

Evidencia privada Windows:
`C:/Users/tito4/.codex/local-artifacts/community-producers-20261027/`.
`evidence-G.tar.gz` omite dumps, filestores y configuraciones. Los ensayos
anteriores A–F no sustituyen al G aceptado; F tuvo una comprobación diagnóstica
de integridad, pero falló un fixture y no tiene aceptación del paquete completo.

Las correcciones incluyeron el campo de dirección exclusivo de Enterprise,
XPath heredados todavía Gantt, límites inclusivos del renderizador y fixtures
con idioma/roles implícitos, formularios retirados por T35 o categorías del
maestro legado frente al catálogo unificado efectivo. No se cambiaron datos
del cliente ni se retiraron restricciones para pasar pruebas.
La ruta ensayada en Cerro instala el núcleo donde aún no estaba instalado;
el upgrade 18.0.1.0.0 → 18.0.1.1.0 tiene scripts versionados y debe ensayarse
en copia fresca de cualquier destino que ya tenga el núcleo anterior.

### Estado acumulado y siguiente bloque

Base contable, Tesorería y cinco consultas alternativas ya están implementadas;
ese paquete está desplegado y verificado en Desarrollo y QA-Cerro. El núcleo
agrícola, Packing/Tarjas/Costos y este bloque de Productores están validados en
Community y copias de Cerro, todavía sin despliegue en servicios activos.

Frente a los 79 caminos Enterprise originales, quedan 68 apps propias con
alguno, sobre las 91 instaladas en producción: once dejaron de tenerlo en el
código candidato, seis antes y cinco en este bloque. Esto es análisis declarado,
no certificación de todos los flujos de esas once; por ejemplo, la instalación
pura propia de T123 continúa pendiente. La matriz completa sigue vigente.

Faltan, en particular: restantes campos y modelos operacionales de `step_hr`
para Maquinaria/Tareas/Tarjas y sus consumidores; lotes de pago y conciliación
operativa/clasificación del efectivo; Nómina/contratos/entradas de trabajo,
Previred y libros compatibles con Simple Digital; DTE/CAF/SII y exportación;
Calidad, demás Gantt y dependencias Studio/Documentos/Firma. También faltan
ensayos frescos y publicación específica de los paquetes agrícolas en Desarrollo
y QA, conversión integral con cero Enterprise, recuperación y aceptación.
El riesgo del 31 de octubre continúa abierto. No retirar Enterprise de producción.

Siguiente foco de implementación: inventariar y extraer la frontera operacional
que aún vincula Maquinaria y Tareas a `step_hr`, conservando empleados, flota,
tarjas y maestros. No quitar manifiestos sin cerrar relaciones y vistas. El
adaptador agrícola de Movilización también consulta `step.tarja`: no sustituir
esa distribución contable por texto o un fallback silencioso. La prueba nativa
pura de T123 es otro pendiente concreto de la fase contable.

### Prompt para continuar

```text
Continúa la migración de Cerro El Plomo a Odoo Community desde la canónica
origin/codex/ambientes-canonicos-reparacion actualizada. Usa un worktree propio.
Lee AGENTS.md, ~/.odoo/environments.json, docs/OPERACION_ODOO_CANONICA.md,
docs/WORKFLOW_GIT_COMPARTIDO.md, docs/PLAN_COMMUNITY_CERRO.md,
docs/COMMUNITY_CONTINUACION.md, docs/COMMUNITY_PRODUCTORES.md y la matriz Enterprise.

El último paquete de Productores tiene fuente 70523bc y ensayo aceptado
community-producers-20261027G: 351 pruebas en Community y 351 en copia fresca
de Cerro, con 848 tablas/proyecciones conservadas. Hay 68 apps propias con
caminos declarados Enterprise; producción todavía conserva 140 Enterprise.

Continúa separando la frontera operacional de step_hr para Maquinaria/Tareas
y sus consumidores. Cierra modelos, relaciones, vistas y permisos antes de
cambiar dependencias. Preserva IDs, maestros, históricos, saldos y capacitación.
Respeta el override bancario legado y los límites visuales de los calendarios
documentados. No recalcules liquidaciones pagadas ni sustituyas maestros.

Prueba el paquete exacto en Community oficial y copia fresca de Cerro. No
retires Enterprise en producción, alteres vencimientos ni refresques QA-Cerro.
Mantén bloqueo compartido, overlays privados, ausencia de downgrade y respaldo
para cualquier publicación autorizada. No reutilices ensayos fallidos.
Guarda commits, push, integra lo validado a la canónica y ejecuta
python tools/git/verify_handoff.py --require-pushed. Al cerrar actualiza estado,
evidencias, pendientes y el siguiente prompt. No declares resuelto el 31 por
una extracción parcial.
```

## Sexto bloque validado — Maquinaria, Tareas y costos de maquinaria (27-10-2026)

Continuación desde la canónica `3107162`. Rama propia
`codex/community-machinery-20261027`. Fuente de addons: `75d8a48`.
Verificador final de contratos y pruebas SQL: `94e2600`.
Contrato técnico y frontera pendiente: `COMMUNITY_OPERACIONES.md`.

### Implementación

- `step_operations_core` 18.0.1.0.0 adopta 30 campos nativos existentes
  (16 flota, nueve empleado, cinco tarea), tres vistas y una acción: 34 XML IDs
  explícitos, además de los alias de selección. Conserva `step_hr.*` y rechaza
  conflictos de destino. No crea maestros, grupos, ACL ni tablas de negocio.
- `step_hr` 18.0.1.7.0 consume ese núcleo; deja de importar los tres modelos
  extendidos y las tres vistas trasladadas. Conserva los componentes de Nómina
  y Tarjas todavía pendientes y el override bancario booleano legado.
- Maquinaria 18.0.22.1.0 y clasificación agrícola de tareas 18.0.1.1.0 usan
  el núcleo, sin dependencia de `step_hr`. El puente de costos de maquinaria
  se valida en el mismo perfil `operations`, de dieciséis módulos de paquete.
  Su clausura declarada de 36 dependencias no contiene Enterprise.
- Las tareas genéricas conservan la nulabilidad efectiva de sus variedades;
  el consumidor agrícola mantiene sus restricciones de clasificación. No se
  cambian fórmulas de costos, fuentes de saldos ni liquidaciones pagadas.
- La prueba HTTP utiliza un usuario desechable; no altera contraseñas ni grupos
  existentes. Las pruebas de empleado respetan el redondeo de la moneda real.

### Evidencia y límites de aceptación

Ensayo aceptado: `/opt/steps-validation/community-operations-20261027D/`.

- `COMMUNITY_AGRICULTURE_OPERATIONS_20261027D`: 408 pruebas sin fallos,
  94 módulos instalados, cero Enterprise y sin `step_hr`. Runtime oficial limpio
  `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
- `MANAGEMENT_QA_CERRO_AGRICULTURE_OPERATIONS_20261027D`: copia fresca de
  Cerro, 408 pruebas sin fallos; 374 instalados, conservando sus 140 Enterprise.
- Mismos 542 archivos de addons en ambas pruebas. SHA256 del mapa
  `source-files.json`:
  `a666756eff0efb5e7deedd78a7721d43ed69e076ced4a1a49331acd0b3673330`.
- Las 897 tablas/proyecciones conservaron sus valores; saldos y registros de
  flota, proyectos y costos incluidos. La diferencia numérica `15.00` → `15`
  de `stock_package_type.base_weight` conserva el hash semántico existente;
  su hash de representación permite auditarla, sin redondear valores.
- Se preservaron los 1.217 modelos, 26.987 campos, 5.071 selecciones,
  2.322 ACL, 610 reglas y 1.327 menús originales, así como membresías y los
  417 enlaces acción/vista. Solo los dos modos Calendar permitidos cambian.
  El paquete agrícola añade once menús y Productores dos campos visuales;
  el núcleo operacional no crea tablas, permisos o columnas paralelas.
- Verificadores nativos de maestros/Packing, Productores y Operaciones:
  UID 6, empresa canónica 2, sin superusuario ni nuevos grupos. Guardado web de
  parte de maquinaria y formulario de tarea, con altas revertidas.

El primer cierre de D detectó la regeneración de cachés CSS/JS como una
diferencia de adjuntos. No se modificaron los addons ya probados.
`tools/community/recheck_operations_contract.py` completó la aceptación bajo
bloqueo con el verificador `94e2600`: exigió 408 pruebas completas y verificadores
nativos en cada entorno, identidad exacta del paquete y restauró el dump original
en otra base privada SQL, `…20261027D_ORIGINAL`. Antes de aplicar la excepción,
su histórico completo, identidades y valores coincidieron con la línea base
registrada. No se utilizó una producción cambiante como línea base.

La excepción identifica únicamente bundles públicos binarios CSS/JS generados
de `ir.ui.view`, sin campo, `res_id=0` y URL hexadecimal `/web/assets/…`.
Dos pruebas sobre PostgreSQL real verificaron ese límite y la detección de un
cambio en contenido de negocio. La comparación final conservó 1.124 adjuntos
de negocio, 1.342 mensajes, 738 seguimientos y 554 seguidores, además de
actividades y parámetros de vencimiento. Los originales sin filtrar también
permanecen en evidencia; no se oculta la regeneración de cachés.

El cierre produjo `OPERATIONS_CONTRACT_OK 897` y `cerro-copy/passed.json`,
con hashes del checker, verificador, log de pruebas y dump. Las comparaciones
filtradas son `history-before-business.json` y `history-after-business.json`.
Los contratos de configuración, archivos y versiones del origen coincidieron
antes/después. Producción y QA-Cerro no recibieron este paquete ni cambios de
vencimiento; QA no se refrescó. No hubo recálculo de liquidaciones pagadas.

Evidencia privada local:
`C:/Users/tito4/.codex/local-artifacts/community-operations-20261027/`.
`evidence-D.tar.gz` contiene pruebas y contratos, sin dump, filestore ni
configuraciones; `source-D.tar.gz` y `contract-check-E.tar.gz` preservan las
fuentes exactas de addons y del verificador final. A–C no sustituyen esta
aceptación: A tuvo 396 pruebas puras sin el puente de costos; B pasó las 408
puras pero su copia falló por precisión monetaria del fixture y cuentas
descontinuadas del cliente; C detectó el contexto de empresa del fixture nuevo.

**Limitación contable encontrada:** en la copia de Cerro, `210233` conserva
su marca de cuenta descontinuada. La prueba contable utiliza una empresa y
cuentas desechables. La contabilización real de Cerro que intente usar esa
cuenta seguirá siendo rechazada por Odoo. Resolver esa configuración y aceptar
el flujo real es un pendiente contable; no reactivar ni sustituir cuentas del
cliente para aprobar pruebas de extracción.

### Estado acumulado y próximos pendientes

Base contable, núcleo de Tesorería y sus cinco consultas alternativas están
implementados; Tesorería sigue siendo el último paquete desplegado y verificado
en Desarrollo y QA-Cerro. Núcleo agrícola, Packing, identificación de fruta,
Costos y Productores
están validados en Community y copias de Cerro, sin publicación activa de esos
paquetes. Operaciones incorpora Maquinaria, Tareas y su puente de costos.

La matriz candidata deja 65 de las 91 apps propias con caminos declarados hacia
Enterprise, frente a 79 en producción y 68 después de Productores. Las tres
liberadas aquí son Maquinaria, costos de maquinaria y clasificación de tareas.
Producción conserva 372 módulos instalados y 140 Enterprise; esta entrega no
autoriza retirarlos y no resuelve el riesgo del 31 de octubre.

El siguiente bloque debe cerrar la frontera Tarjas/Cuadrillas: `step.tarja`,
sus líneas/costos/registro, `hr.salary.custom`, contratos, tarifas y cuentas de
costeo. Movilización conserva su distribución por empleado/fundo/fecha/empresa.
No quitar dependencias antes de cerrar modelos, relaciones, vistas y permisos.
Permanecen pendientes Nómina compatible con Simple Digital, contratos/entradas,
Previred/libros, lotes de pago y conciliación operativa/clasificación del efectivo,
DTE/CAF/SII/exportación, Calidad y demás Gantt/Studio/Documentos/Firma. También
la prueba pura propia de T123, la publicación agrícola/operacional en Desarrollo
y QA con sus copias frescas, conversión integral con cero Enterprise,
recuperación y aceptación. No refrescar QA-Cerro.

### Prompt para el siguiente bloque

```text
Continúa la migración de Cerro El Plomo a Community desde la canónica
origin/codex/ambientes-canonicos-reparacion actualizada. Usa un worktree propio.
Lee AGENTS.md, ~/.odoo/environments.json, docs/OPERACION_ODOO_CANONICA.md,
docs/WORKFLOW_GIT_COMPARTIDO.md, docs/PLAN_COMMUNITY_CERRO.md,
docs/COMMUNITY_CONTINUACION.md, docs/COMMUNITY_PRODUCTORES.md,
docs/COMMUNITY_OPERACIONES.md y la matriz Enterprise.

El sexto bloque separa Maquinaria, Tareas y costos de maquinaria de step_hr:
núcleo operacional con 30 campos y 34 XML IDs originales. Consulta en continuidad
el ensayo D aceptado: 408 pruebas por entorno, 897 tablas/proyecciones y fuentes
75d8a48 de addons / 94e2600 de contratos. Quedan 65 apps propias con caminos
declarados Enterprise; producción conserva 140 Enterprise. Esto no resuelve
el vencimiento del 31 de octubre.

Continúa cerrando Tarjas/Cuadrillas y sus consumidores: step.tarja, líneas,
costos y registros, hr.salary.custom, contratos, tarifas y step.haber.costeo.
Movilización distribuye por empleado/fundo/fecha/empresa usando la tarja propia.
Separa el adaptador de Nómina solo después de cerrar modelos, relaciones,
vistas y permisos. No cambies manifiestos dejando relaciones incompletas.

Preserva IDs, maestros, históricos, permisos y saldos. Respeta los límites
visuales de Calendar y el override bancario legado. Conserva la cuenta
210233 descontinuada: su configuración y aceptación del flujo real están
pendientes; no reactives cuentas para aprobar fixtures. No recalcules
liquidaciones pagadas, retires Enterprise en producción, alteres vencimientos
ni refresques QA-Cerro. Los paquetes agrícolas/operacionales aún requieren
publicación específica en Desarrollo y QA tras sus copias frescas.

Prueba el paquete exacto en Community oficial y copia fresca de Cerro, bajo
bloqueo compartido y overlays privados. Guarda commits, push, integra únicamente
lo validado a la canónica y ejecuta python tools/git/verify_handoff.py
--require-pushed. Entrega estado acumulado, evidencia, pendientes y siguiente
prompt. No declares resuelto el vencimiento por una extracción parcial.
```

## Séptimo bloque validado — Tarjas, Cuadrillas y Movilización (27-10-2026)

Base canónica de inicio: `19f9088`. Rama propia:
`codex/community-tarjas-20261027`. Fuente del paquete aceptado: `b781f72`.
Contrato técnico: `COMMUNITY_TARJAS_CUADRILLAS.md`.

### Implementación y frontera conservada

- Núcleo `step_labor_operations_core` 18.0.1.0.0: nueve modelos originales,
  228 campos declarados y 296 XML IDs explícitos, con nueve ACL y cuatro
  secuencias. Se mantienen tablas, maestros, columnas, relaciones y alias
  `step_hr.*`. No se crean maestros ni grupos de permisos paralelos.
- Las cuatro secuencias se adoptan sin reescribir sus parámetros o contadores.
  Sus alias del núcleo quedan `noupdate=True`, necesarios para sobrevivir a
  la limpieza de metadatos de una instalación sin XML de secuencias.
- Los siete registros originales de propiedad M2M se transfieren de HR al
  núcleo sin cambiar sus IDs, nombres o modelos. Se verifica el conjunto
  completo de relaciones y las restricciones SQL/FK laborales originales.
- `step_hr` 18.0.1.8.0 conserva el puente de lotes/estructuras y envío a
  remuneraciones. No se simulan `hr.payslip.run` ni `hr.payroll.structure`
  en Community. No se invoca el envío ni se recalculan liquidaciones pagadas.
- Los costos de contrato conservan sus fórmulas. En Cerro se sigue leyendo
  el campo semanal legado; en Community se obtiene la jornada de los calendarios
  nativos, incluyendo el ciclo de dos semanas y la configuración flexible.
  No se fabrica una jornada ni una tarifa cero cuando faltan horas.
- Las reglas de tarifas permiten completar labor y unidad obligatorias desde
  los dos formularios, conservando las relaciones a los productos existentes.
- Movilización agrícola 18.0.1.1.0 consume el núcleo y lee la distribución
  vigente por empleado/fundo/fecha/empresa. Movilización 18.0.1.0.3 limita su
  pestaña de tarifas a sus perfiles y declara el modelo de documento LATAM
  nativo, evitando que la relación de empresa quede como `_unknown`.

### Ensayos y aceptación

Ensayo aceptado: `/opt/steps-validation/community-labor-20261027G/`.

- `COMMUNITY_AGRICULTURE_LABOR_20261027G`: 440 pruebas sin fallos,
  113 módulos instalados, cero Enterprise y sin `step_hr`. Runtime oficial
  limpio `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
- `MANAGEMENT_QA_CERRO_AGRICULTURE_LABOR_20261027G`: copia fresca de
  Cerro, 440 pruebas sin fallos, 375 módulos instalados y sus 140 Enterprise
  conservados. Se añaden tres núcleos; no es la conversión integral.
- Mismos 632 archivos de addons por hash. SHA256 del mapa `source-files.json`:
  `6d8bcf4ea67591db8ab532c7257fd5de4666e0ea717d9b2943d8acc13c0af6c9`.
  Los diecinueve módulos del paquete no suponen downgrade respecto del origen.
- Se conservaron los valores de 911 tablas/proyecciones, incluidos tarifas,
  calendarios, recursos y relaciones M2M. Los 1.217 modelos, 26.987 campos,
  5.071 selecciones, 2.322 ACL, 610 reglas y 1.327 menús originales mantuvieron
  identidad y atributos. Se añaden únicamente los dos campos visuales de
  Productores ya documentados; el núcleo agrícola añade once menús y el laboral diez.
- Los 463 registros originales de relaciones mantienen sus IDs, nombres y
  modelos. Solo los siete propietarios declarados pasan de HR al núcleo laboral.
  Las 176 restricciones SQL/FK laborales permanecen exactas, al igual que
  los 417 enlaces acción/vista salvo los dos modos Calendar permitidos.
  Se comprobó también la FK nativa del tipo de documento de empresa.
- Se conservaron 1.388 mensajes, 738 seguimientos, 600 seguidores, las actividades,
  1.125 adjuntos de negocio y los parámetros de vencimiento. Se aplica únicamente
  la excepción estricta de cachés web regenerables previamente documentada.
- Verificadores nativos de maestros/Packing, Productores, Operaciones y laboral:
  en Cerro UID 6, empresa canónica 2, sin superusuario ni asignación de grupos.
  Menús y formularios accesibles; altas temporales de empleado/contrato/cuadrilla/
  tarja, costeo y lectura de Movilización, con rollback. En Community, el perfil
  laboral es un usuario desechable con roles explícitos, también sin superusuario.

`passed.json`, `source-files.json`, `tests.log`, `verify.log`, contratos de
negocio, identidades, restricciones, relaciones e históricos antes/después
están en ambos stages. El cierre fue directo: `AGRICULTURE_OK community` y
`AGRICULTURE_OK cerro-copy`, sin normalizar la relación defectuosa del ensayo F.
Los contratos de configuración, archivos y versiones del origen coincidieron
antes/después. Producción sigue con 372 módulos y 140 Enterprise; no recibió
este paquete ni cambios de vencimiento. QA-Cerro no se refrescó ni se publicó
allí este bloque. Tampoco hubo publicación agrícola en Desarrollo.

El corte muestreado no tenía contratos o liquidaciones existentes. Se preserva
esa situación y se prueban contratos nuevos con fixtures; esto no acredita la
conversión de una nómina histórica pagada ni el retiro del motor Enterprise.

Evidencia privada local:
`C:/Users/tito4/.codex/local-artifacts/community-labor-20261027/`.
`evidence-G.tar.gz` contiene las pruebas y contratos sin dump, filestore ni
configuración. `source-G.tar.gz` conserva el paquete exacto. El dump completo
y filestore originales permanecen en el stage privado del servidor.

No usar A–F como aceptación final. A detectó una
expectativa equivocada del test ante la excepción FK de borrado del fundo.
B pasó 438 pruebas puras, pero su copia detectó el alias de secuencia y una
asignación de vacaciones del fixture. Las comprobaciones nativas de Community
se ajustaron para usar un perfil temporal de negocio sin ampliar al administrador.
D/E fueron diagnósticos focalizados del formulario de tarifas. F pasó 439 pruebas
en ambos entornos y sus verificadores nativos, pero detectó el comodel LATAM
incorrecto en el contrato de metadatos; no tiene aceptación. G incorpora la
dependencia explícita y la prueba de relación guardada, con ambas bases nuevas.

### Estado acumulado y pendientes

La base contable y Tesorería están implementadas, con sus cinco consultas
alternativas desplegadas en Desarrollo y QA-Cerro. Los núcleos agrícola y
operacional, Packing, identificación de fruta, Costos y Productores ya tienen
ensayos aceptados en Community y copias frescas; su promoción agrícola a los
servicios activos sigue pendiente. Este bloque incorpora la frontera laboral
y el consumidor de Movilización.

El candidato deja 64 de 91 apps propias con caminos declarados Enterprise,
frente a 79 originales y 65 después de Maquinaria/Tareas. La reducción aquí
corresponde a Movilización agrícola; `step_hr` conserva el puente de Nómina.
La cifra es de manifiestos, no una certificación de todos los flujos de las
apps sin caminos Enterprise. Producción conserva 140 Enterprise y el riesgo
del 31 de octubre continúa abierto.

Siguiente frontera: Cosecha, sus wizards activos de Nómina y planificación/
registros agrícolas. `step_cosecha_planning` también depende de `step_export`
por los formatos de empaque; no basta sustituir su dependencia de HR. Conservar
el maestro nativo `product.packaging`, sus vistas y alias al cerrar ese borde.
Después siguen Nómina/contratos/entradas compatibles con Simple Digital,
Previred/libros, DTE/CAF/SII/exportación, Calidad, restantes Gantt y Studio/
Documentos/Firma. Permanecen T123 en instalación pura propia, lotes de pago,
conciliación operativa y clasificación del efectivo. Faltan publicación en
Desarrollo/QA con sus copias específicas, conversión integral con cero
Enterprise, recuperación y aceptación.

La cuenta `210233` permanece descontinuada. La aceptación de ese flujo real
sigue requiriendo una resolución contable. El override bancario queda en HR,
los límites de Calendar se conservan y QA-Cerro no se refresca.

El inventario final conserva tres relaciones aún propiedad de HR, todas de
wizards pendientes: `employee_wizard_rel` (`report.step.hrs.wizard`),
`step_hr_payslip_rel` (`hr.input.step.wizard`) y `employee_process_rel`
(`report.by.process.wizard`). No retirar HR sin migrar esos propietarios,
sus modelos/IDs/permisos y el override bancario.

### Prompt para el siguiente bloque

```text
Continúa la migración de Cerro El Plomo a Community desde la canónica
origin/codex/ambientes-canonicos-reparacion actualizada. Usa un worktree propio.
Lee AGENTS.md, ~/.odoo/environments.json, docs/OPERACION_ODOO_CANONICA.md,
docs/WORKFLOW_GIT_COMPARTIDO.md, docs/PLAN_COMMUNITY_CERRO.md,
docs/COMMUNITY_CONTINUACION.md, docs/COMMUNITY_PRODUCTORES.md,
docs/COMMUNITY_OPERACIONES.md, docs/COMMUNITY_TARJAS_CUADRILLAS.md y la matriz
Enterprise.

El último bloque, fuente b781f72 y ensayo community-labor-20261027G, separó
nueve modelos de Tarjas/Cuadrillas y Movilización: 440 pruebas por entorno,
911 tablas/proyecciones, 463 relaciones y 176 restricciones SQL preservadas.
Conservó 296 XML IDs y transfirió siete propietarios M2M manteniendo sus IDs.
Quedan 64 apps propias con caminos declarados Enterprise y producción conserva
140 Enterprise. Este bloque no resuelve el vencimiento del 31 de octubre.

Continúa con la frontera de Cosecha y planificación/registros agrícolas.
Separa sus wizards activos de Nómina mediante un puente real; no simules
hr.payslip ni retires campos/IDs. step_cosecha_planning también consume
step_export por los formatos: conserva product.packaging, vistas y alias antes
de cambiar dependencias. Revisa los wizards laborales que aún quedan en HR y
sus tres propietarios M2M pendientes descritos en continuidad.

Cierra modelos, relaciones, vistas y permisos antes de cambiar manifiestos.
Preserva maestros, IDs, históricos, permisos, saldos y correlativos. Respeta
los límites de Calendar, el override bancario y la cuenta 210233 descontinuada.
No recalcules liquidaciones pagadas, retires Enterprise en producción, alteres
vencimientos ni refresques QA-Cerro. No amplíes perfiles para pasar pruebas.
Los fixtures de contratos usan el mes actual para evitar generar asignaciones
acumuladas de vacaciones de Simple Digital; no desactives ese motor.

Prueba el mismo paquete en Community oficial y copia fresca de Cerro, con
bloqueo compartido y overlays privados. Los despliegues agrícolas en Desarrollo
y QA siguen pendientes y necesitan sus propios ensayos frescos. Guarda commits,
push, integra solo lo validado a la canónica y ejecuta python
tools/git/verify_handoff.py --require-pushed. Entrega estado, evidencias,
pendientes y siguiente prompt; no declares resuelto el vencimiento por una
extracción parcial.
```


## Octavo bloque validado: Cosecha, planificación y registros (27-10-2026)

Base recibida: `a57e707`, canónica
`origin/codex/ambientes-canonicos-reparacion`. Rama propia:
`codex/community-cosecha-20261027`, en el worktree privado de esta continuidad.
Contrato detallado: `COMMUNITY_COSECHA.md`.

### Implementación aceptada

- `step_cosecha` 18.0.1.8.0 consume `step_labor_operations_core` y módulos
  oficiales Community, sin HR propio, Nómina ni Gantt Enterprise. Conserva los
  diez modelos de Cosecha/historial, relaciones, acciones, menús, permisos y datos.
- `step_cosecha_planning` 18.0.1.1.0 consume
  `step_agriculture_format_core` 18.0.1.0.0. Los formatos siguen en
  `product.packaging` y `stock.package.type` nativos. El núcleo adopta dos
  capacidades de pallet, cuatro vistas y dos acciones de Exportación. Kg/caja
  y cajas/pallet siguen perteneciendo a Productores; la clasificación de empaque
  sigue en planificación. Ningún histórico recibe una clasificación inventada.
- `step_labor_reports` 18.0.1.0.0 adopta los dos informes XLSX operacionales,
  sus modelos transitorios, campos, vistas, acciones y dos ACL originales.
  Corrige la visibilidad de fechas/resultado y el botón del informe contratista.
  La prueba exporta el empleado original y 60 de su tarja, sin Nómina.
- `step_labor_payroll_wizards` 18.0.1.0.0 conserva los tres modelos transitorios
  compartidos reales y sus ocho campos, vistas, acciones, menús y dos ACL
  originales. HR 18.0.1.9.0 consume ese puente; Cosecha ya no duplica sus
  definiciones. El puente depende de Nómina real y no entra en Community pura.
  No se inventa un ACL para el wizard de entradas que no lo tenía.
- Se adoptan `employee_wizard_rel`, `employee_process_rel` y
  `step_hr_payslip_rel`, con sus IDs/nombres/modelos originales. La última tiene
  dos filas de metadatos originales, de HR y de Cosecha: ambas se conservan y
  pasan al puente, sin fusionarlas. Junto a las siete relaciones del bloque
  laboral anterior son once cambios declarados de propietario, conservando las
  463 filas originales de `ir.model.relation`.
- La bandera `stock.picking.cosecha` pasa de HR a Cosecha con la misma columna,
  campo y alias original. Recepción, dashboard y enlace a Inventario funcionan
  en Community. La prueba con usuario de Inventario sin `su` recibe 20 kg,
  valida, marca recibido y rechaza duplicados. La sincronización actúa solo
  durante una transición del operador sobre la recepción vinculada; no recalcula
  recepciones anteriores durante el upgrade.
- El costeo usa directamente las relaciones analíticas existentes de centro y
  actividad del producto. El recorrido contratista aprueba, costea y genera un
  asiento en borrador de 60 balanceado, con temporada/centro/actividad reales y
  protección contra segunda contabilización. No modifica asientos históricos.
- Registros agrícolas 18.0.1.3.0 declara Movilización y `hr_hourly_cost` oficial
  Community. Conserva las dos relaciones al costo horario original del empleado,
  con su grupo nativo de RRHH; no lo calcula desde liquidaciones ni lo duplica.
- Exportación 18.0.2.9.9 consume el núcleo de formatos y conserva sus DTE/SII
  pendientes. La extracción de formatos no certifica independencia de Exportación.
- Los núcleos agrícola 18.0.1.1.1, operacional 18.0.1.0.1 y laboral 18.0.1.0.1
  protegen también alias de modelos nativos, campos delegados y metadatos de
  herencia existentes. Las raíces nuevas permanecen ocultas con la raíz legada
  de HR incluso al repetir el upgrade. No cambian las membresías de usuarios.

### Evidencia aceptada

Paquete de 27 módulos del perfil `harvest`: 824 archivos de addons idénticos
por SHA256 en los dos entornos. Fuente de addons `c7017f2`; el ejecutor final
`13d0611` añade la protección de idiomas al cierre completo de CLI, sin cambiar
esos archivos. Los ajustes de documentación posteriores no cambian el paquete.

- Community: `/opt/steps-validation/community-harvest-20261027P/community/`,
  base `COMMUNITY_AGRICULTURE_HARVEST_20261027P`: **464 pruebas, cero fallos**;
  134 instalados, cero Enterprise, sin HR propio ni puente de Nómina.
- Copia fresca de Cerro:
  `/opt/steps-validation/community-harvest-20261027Q/cerro-copy/`, base
  `MANAGEMENT_QA_CERRO_AGRICULTURE_HARVEST_20261027Q`: **464 pruebas, cero fallos**;
  378 instalados, conservando los 140 Enterprise. No es una conversión integral.
- Runtime oficial Community limpio de `https://github.com/odoo/odoo.git`,
  revisión `4b4efe68291d6def5bb7d2e1f2b829e0cda577d4`.
- SHA256 idéntico de `source-files.json`:
  `97ce2c394fb094facdba9bcb0c362117e5ac44d41fc26cdc036c7b9aa771d978`.
  Archivo fuente Q con addons/herramientas: SHA256
  `c8d99e1917cfa7bee46a033534f8c5e837f3f11c3d8f2a1209a8a0045b4a9d1e`.
- El upgrade sin fixtures preservó exactamente 918 tablas/proyecciones y los
  140 objetos de secuencia estándar existentes. Después se ejecutó toda la
  batería; 23 secuencias tuvieron consumo de fixtures en la copia, registrado
  separadamente con progresión nativa, sin resetear números. Las tablas de
  configuración de secuencias/rangos conservan valores, excluyendo solo sus
  sellos `write_uid`/`write_date`. Los documentos y saldos se vuelven a comparar
  al terminar. Ver `business-after-upgrade.json` y `fixture-counter-consumption.json`.
- Se preservaron las identidades de **58.939 XML IDs originales**, 1.217 modelos,
  26.987 campos, 5.071 selecciones, 2.322 ACL, 610 reglas, 1.327 menús y los
  417 enlaces acción/vista. Las relaciones suman 463 y las restricciones SQL/FK
  comparadas 526 (176 laborales y 350 de Cosecha/registros/empaques/wizards).
  Solo se admiten los dos modos Calendar y los once propietarios ya declarados.
- Quedan 26.989 campos: solo los dos visuales Calendar previos se añaden.
  Hay 1.350 menús: los 23 nuevos de núcleos/informes no alteran los originales;
  las raíces nuevas están ocultas en Cerro. Las dos membresías nuevas pertenecen
  solo a raíces nuevas. Grupos de usuarios, reglas e implicaciones originales
  permanecen exactos.
- Históricos idénticos: 1.388 mensajes, 738 seguimientos, 600 seguidores,
  cero actividades y 1.125 adjuntos de negocio. Se conserva la excepción estricta
  de bundles web regenerables. Vencimiento y fuentes/versiones/configuración
  de producción permanecen iguales.
- Verificadores nativos de maestros/Packing, Productores, Operaciones, Tarjas y
  Cosecha aprobados. En Cerro usan UID 6, empresa 2, sin `su` ni nuevos grupos;
  comprueban menús, formularios, dashboard de recepción, maestro de empaque,
  descarga XLSX y los 33 formularios de registros. Las altas se revierten.
- Una prueba PostgreSQL adicional comprueba recuperación de idiomas omitidos,
  respeto de textos base cambiados y traducciones nuevas explícitas, nulos e
  idempotencia. El campo nativo de calendario de contratos conserva su ayuda
  española también después de toda la batería y apertura nativa. No se excluye
  su traducción del contrato de identidad.
- Artefactos privados Windows:
  `C:/Users/tito4/.codex/local-artifacts/community-harvest-20261027/`;
  `source-P.tar.gz`, `source-Q.tar.gz`, `evidence-PQ.tar.gz`, `evidence-PQ/`,
  `summary-PQ.json` y `field-translations-postgres.log`. Dumps/filestore quedan
  privados en el servidor y no se incluyen en el paquete de evidencia local.

Los ensayos anteriores rechazados y las bases de diagnóstico no son aceptación.
Puro E aprobó 460 casos, pero aún no cubría la recepción/costeo completo ni la
regresión de permisos/alias. Los cierres aceptados son únicamente Community P
con copia Q y el mismo mapa de archivos. No se reutilizó una migración fallida
como línea base nueva. El bloqueo compartido respetó las operaciones concurrentes.

### Estado acumulado y fecha del 31 de octubre

Tesorería y sus cinco informes alternativos ya fueron publicados y revisados
previamente en Desarrollo y QA-Cerro. Los núcleos contable/agrícola, Productores,
dos calendarios, Operaciones, Tarjas/Cuadrillas, Movilización y ahora
Cosecha/planificación/registros tienen ensayos Community y copias de Cerro.
Los despliegues agrícolas activos siguen pendientes de sus propios ensayos de
destino y revisión; este bloque no publicó en producción ni refrescó QA-Cerro.

La matriz candidata baja **64 → 59 apps propias con caminos Enterprise** de
las 91 inventariadas (79 al inicio). Son clausuras declaradas; no es un porcentaje
de conversión ni una certificación de todos los flujos. Las cinco clausuras
liberadas incluyen `step_harvest_launcher`, presente en el inventario del
servidor pero sin fuentes versionadas en este checkout; su arranque aislado
Community todavía necesita inventario/aceptación. Las cuatro apps agrícolas
incluidas en el perfil sí se prueban.

Producción continúa con **372 instalados / 140 Enterprise**. No existe todavía
un ensayo integral de Cerro con cero Enterprise. **No hay evidencia para
comprometer un corte seguro el 31 de octubre; el riesgo sigue alto.** Falta:

1. Frontera restante de HR/Tracker/Actividades/configuración/histórico y motor
   Community real compatible con Simple Digital, estructuras/reglas, entradas,
   Previred y libro de remuneraciones. Auditar licencia/API del proveedor real.
   El puente de wizards preserva las API, no sustituye el motor.
2. DTE/CAF/folios/certificados/firmas/SII y Exportación Community con los
   documentos, respuestas e históricos originales. No se emitió al SII real.
3. Calidad, otras vistas Enterprise, Studio, Documentos/Firma e inventario de
   apps instaladas sin fuente consolidada. No retirar por datos vacíos.
4. Lotes de Tesorería, conciliación operativa, clasificación normativa del
   efectivo y aceptación Community pura de T123; los informes actuales cubren
   efectivo realizado/control, con los límites ya documentados.
5. Resolver la configuración contable que todavía intenta usar `210233`
   descontinuada para Maquinaria. No se reactivó ni sustituyó para pasar pruebas.
   El override bancario Boolean legado permanece en HR y requiere migración
   explícita antes de retirarlo; no se convirtió silenciosamente a relación.
6. Publicación de los paquetes agrícolas en Desarrollo y posterior circuito
   autorizado; conversión integral de una copia a fuentes exclusivamente
   Community, cero OEEL instalados, comparación completa y recuperación ensayada,
   aceptación por empresa/perfil y plan de corte/continuidad.

Límite de la evidencia de Nómina: la copia de Cerro de este bloque tiene cero
contratos y cero liquidaciones en sus tablas originales. Se verifican fixtures
operacionales/contratos nuevos y preservación de metadatos, no una conversión
de liquidaciones pagadas reales. No se invoca el importador masivo legado:
aún elige la primera liquidación por empleado sin cerrar lote/estructura/estado.
Los límites de Calendar, el override bancario, los saldos, históricos,
correlativos y el vencimiento se mantienen. No declarar resuelto el 31 por
esta extracción parcial; hace falta cerrar los bloques críticos y el ensayo global.

### Prompt para continuar después de Cosecha

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow,
plan, continuidad, Productores, Operaciones, Tarjas/Cuadrillas, COMMUNITY_COSECHA.md
y matriz Enterprise.

El bloque Cosecha usa addons c7017f2 y ejecutor 13d0611: Community P y copia
fresca Cerro Q, 464 pruebas por entorno, 824 archivos idénticos, 918 tablas/
proyecciones, 140 contadores preservados durante upgrade, 58.939 XML IDs,
463 relaciones y 526 restricciones SQL/FK. Se cerraron Cosecha, planificación,
registros y formatos product.packaging; se separaron wizards reales de Nómina,
conservando los dos propietarios originales de step_hr_payslip_rel. Quedan
59 apps propias con caminos declarados Enterprise; producción mantiene 140.
No está resuelto el vencimiento del 31 de octubre.

Prioriza la frontera restante de HR y la compatibilidad real de Simple Digital
con un motor Community: audita modelos, campos, reglas, estructuras, contratos,
entradas, Previred/libro y licencia/API del proveedor. Implementa el siguiente
bloque real sin stubs de hr.payslip ni cambios de IDs. Revisa el importador que
elige la primera liquidación sin validar lote/estructura/estado y el flujo APR
legado; no lo presentes como motor salarial. Mantén el diagnóstico del camino
crítico del 31: DTE/CAF/SII y el ensayo integral siguen abiertos. Audita también
los módulos del servidor sin fuente consolidada, incluido step_harvest_launcher.

Preserva modelos, IDs, maestros, relaciones, permisos, históricos, saldos y
correlativos. No recalcules liquidaciones pagadas ni retires Enterprise en
producción, cambies vencimientos o refresques QA-Cerro. Respeta Calendar,
210233 descontinuada y el override bancario Boolean de HR; no cambies su tipo
silenciosamente. Prueba el paquete exacto en Community oficial y copia fresca
con overlays privados, bloqueo compartido, sin downgrade ni cambios concurrentes.
La copia de este bloque no contiene liquidaciones/contratos originales: no
la presentes como aceptación de históricos de nómina reales. Mantén las
traducciones y los alias de modelos/campos delegados, además de sus destinos.
Guarda commits, push, integra solo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Entrega estado, evidencia,
pendientes, valoración honesta del 31 y el siguiente prompt.
```


## HR operacional y auditoría de Nómina — aceptación final F, 27-10-2026

Base de trabajo: canónica `ca45289`, que ya contiene `a6a7f66` y las entregas
concurrentes T124/T125/T126. Código exacto de addons `6e418ef`, en la rama
`codex/community-hr-payroll-20261027`. Contratos y prompt completo:
[COMMUNITY_HR_PAYROLL.md](COMMUNITY_HR_PAYROLL.md).

`step_hr` 18.0.1.10.0 conserva Actividades/Tracker, configuración, históricos,
assets, IDs y relaciones; instala en Community oficial sin Nómina ni mapa EE.
`step_hr_payroll_bridge` conserva las cuatro vistas y los campos originales de
Nómina, el método real de Tarjas y el Boolean bancario legado. La premigración
rechaza actualizar HR con Nómina instalada sin incluir ese puente. Se mantienen
los alias de campos delegados y de herencias reales, los límites de Calendar y
`210233` descontinuada. El importador masivo valida empresa/lote/estructura,
contrato, unicidad, borrador no pagado y duplicados, con bloqueo de filas y sin
recalcular. Respeta la API real: el lote pasa a `verify` al contener borradores.
Los permisos originales se conservan.

Evidencia aceptada: **468 pruebas Community / 516 en copia fresca de Cerro**,
**28 addons / 837 archivos idénticos**, **918 tablas/proyecciones**, **140
contadores exactos durante upgrade**, **58.956 XML IDs originales**, **463
relaciones**, **526 restricciones SQL/FK**, **2.322 ACL y 610 reglas**.
Se conservan las 1.614 membresías usuario/grupo y 36 usuario/compañía, además de
los grupos implicados y de reglas. Las fixtures consumen luego 30 contadores
estándar de la copia, monótonos y sin reset. Los históricos, adjuntos, saldos y
vencimiento permanecen iguales. Los formularios, menús y flujos nativos pasan
con UID 6, compañía 2 y `su=False`. Detalle y huellas en el documento HR.

La regresión incluye 34 casos de Exportación; se corrigieron sus expectativas
para los consumidores instalados (Control, roles y bloqueo de guías), conservando
el orden guardado del cliente. El preflight dirigido aprobó 48 casos antes de
repetir el paquete final completo. No se emitió al SII real ni se probó aún su
reemplazo Community.

El motor real OCA `payroll`/`payroll_account`, fijado a `4c71cd4`, pasa **38
pruebas**, cálculo/entrada/asiento balanceado y menú/formularios con usuario
sin superpoderes sobre Community oficial `4b4efe6`, cero EE. Usa datos de ejemplo
oficiales requeridos por la suite upstream en una base privada nueva. **No es
compatible todavía con Simple Digital**: la comprobación nativa demuestra al
menos siete brechas de API. Los tipos base de estructura sí existen en Community;
faltan enlaces, tipos de entrada, worked days por work entries, relación de reglas,
métodos y contexto de cálculo, además de equivalencia contable/chilena.
Simple Digital declara AGPL-3 pero depende de tres componentes OEEL-1. Se auditan
4 estructuras, 71 reglas, 6 tipos de entrada, los puentes de contratos, días,
redondeos/correcciones, 2 perfiles Previred y 2 de libro con 42 líneas.
Cerro tiene cero contratos, liquidaciones y snapshots salariales originales:
las fixtures no acreditan una conversión de nómina pagada histórica.

Estado acumulado: base contable, cinco consultas de Tesorería, maestros,
Productores/Calendar, Operaciones, Tarjas/Cuadrillas, Movilización,
Cosecha/planificación/registros y ahora HR operacional tienen ensayos parciales
Community y copias de Cerro. El inventario actual tiene **374 instalados / 140
Enterprise / 93 propios**. Sobre el mismo inventario, HR reduce **60 → 53** las
apps propias con clausuras Enterprise; el bloque anterior contaba 59 sobre 91.
No usar esos números como porcentaje de conversión. `step_task` y
`step_harvest_launcher` siguen pendientes de consolidación/aceptación aislada.

**No hay todavía una copia integral de Cerro aceptada con cero Enterprise.
No existe evidencia para comprometer un corte seguro el 31 de octubre; riesgo
alto.** Quedan motor Simple Digital compatible, reglas/Previred/libro, DTE/CAF/
folios/firmas/respuestas SII/Exportación, Calidad/Studio/Documentos/Firma,
lotes/conciliación de Tesorería, revisión de `210233`, extracción bancaria
explícita, consumidores restantes, ensayo integral/recuperación y aceptación
por empresa/perfil. Los paquetes agrícolas/HR no se publicaron en ambientes
activos; seguir el circuito de Desarrollo antes de una publicación autorizada.
Producción conserva 140 Enterprise. No se refrescó QA-Cerro ni se alteraron
vencimientos ni liquidaciones pagadas.

Evidencia privada: `~/.codex/local-artifacts/community-hr-payroll-20261027/`,
`evidence-F/`, `summary-F.json` y `source-F-final.tar.gz`. Todos los hashes y
comandos reproducibles figuran en `COMMUNITY_HR_PAYROLL.md`.

### Prompt siguiente después de HR

```text
Continúa desde origin/codex/ambientes-canonicos-reparacion actualizada, en un
worktree propio. Lee AGENTS.md, ~/.odoo/environments.json, operación, workflow,
plan, continuidad, Productores, Operaciones, Tarjas/Cuadrillas, Cosecha,
COMMUNITY_HR_PAYROLL.md y la matriz Enterprise. Revisa la evidencia final allí.

Prioriza la adaptación real de Simple Digital a OCA payroll/payroll_account,
fijados a 4c71cd42e46a09a7512d92f5c63c0a9f7c26ad3e. El paquete HR pasó
468 pruebas en Community y 516 en copia fresca de Cerro,
con 837 archivos idénticos, 918 tablas/proyecciones, 58.956 XML IDs y 140
contadores preservados durante upgrade. El candidato OCA pasó 38 pruebas
y cálculo/asiento nativo en Community oficial 4b4efe6, pero NO es compatible aún
con Simple Digital: quedan al menos siete brechas de API comprobadas. Los modelos base
hr.payroll.structure.type y hr.contract.structure_type_id sí existen en Community;
faltan vínculos/complementos, tipos de entradas, worked_days por work entries,
relación de reglas a estructuras y métodos/contexto de cálculo. No inventes
hr.payslip ni un módulo vacío hr_payroll para engañar al cargador. Usa el motor real.

Audita y conserva los 71 registros de reglas, 4 estructuras, 6 tipos de entrada,
2 perfiles Previred y 2 de libro/42 líneas, además de los puentes de contratos,
redondeos, días, correcciones y transición del motor. Adopta XML IDs, campos,
grupos y relaciones antes de cambiar dependencias. Certifica casos chilenos,
contabilización, Previred y libro, con permisos reales y pruebas de no recálculo
pagado. Cerro no contiene contratos/liquidaciones originales ni snapshots del
motor previo: no presentes sus fixtures como conversión de históricos pagados.
El lote nativo pasa a verify al contener borradores; no confundirlo con cierre.

Mantén explícito el camino crítico DTE/CAF/folios/firmas/respuestas SII y el ensayo
integral de Cerro con cero Enterprise. Producción conserva 140 Enterprise;
53 apps propias aún tienen caminos declarados Enterprise sobre 93 inventariadas.
No está resuelto el vencimiento del 31 de octubre. No emitas al SII real.

Preserva IDs, maestros, relaciones, permisos, históricos, saldos y correlativos.
Respeta Calendar, 210233 descontinuada y el Boolean bancario legado del puente HR.
No recalcules liquidaciones pagadas, retires Enterprise en producción, alteres
vencimientos ni refresques QA-Cerro. Prueba primero los casos nuevos dirigidos
y después el paquete exacto completo en Community oficial y copia fresca de Cerro,
con overlays privados, bloqueo compartido, sin downgrade ni cambios concurrentes.
Guarda commits, push, integra solo lo validado y ejecuta
python tools/git/verify_handoff.py --require-pushed. Entrega estado acumulado,
evidencia, pendientes, valoración honesta del 31 y siguiente prompt.
```


## Contratos API Simple Digital–OCA — 27-10-2026

Nuevo bloque de código `7c95671`: adaptador sobre OCA real, sin `hr.payslip`
simulado ni fachada `hr_payroll`. Paquete G: tres addons/15 archivos idénticos,
53 pruebas Community oficial (64 instalados/0 EE) y seis contratos compartidos
en copia fresca nativa de Cerro (376/140 EE). Se preservan 918 tablas/proyecciones,
140 contadores exactos incluso tras fixtures, 58.956 XML IDs, permisos, relaciones,
históricos y saldos. No se repite ni se suma la regresión HR anterior 468/516.

Se implementan tipos de entrada/FK, enlace de tipos de estructura, relación
primaria de reglas con M2M OCA, totales por código y acceso real a entradas por
diccionario. Se bloquea recálculo pagado/validado, repetición ambigua de entradas
tipadas y cambios de relación inconsistentes. `payslip` ya era un registro real
OCA; no se sustituyó. La comparación genérica incluye moneda CLP y asiento real.
Las siete brechas del inventario de API anterior son el diagnóstico inicial;
no interpretar su implementación parcial como certificación de Simple Digital.

Quedan días/ausencias/work entries, agregación, cantidades/redondeos/YTD,
instalación real del proveedor sobre OCA, adopción de modelos/campos/XML IDs/grupos,
71 reglas chilenas, Previred/libro e históricos pagados representativos. OCA
hereda líneas desde reglas: requiere mapear ese esquema en la conversión.
Siguen DTE/CAF/SII y la conversión integral con cero EE, recuperación y aceptación.
No cambian las 53 clausuras Enterprise sobre 93 apps del inventario anterior;
producción conserva 140 EE. El riesgo del 31 sigue alto y el vencimiento no
está resuelto. No se modifican producción, QA-Cerro, vencimientos ni pagadas.

Estado detallado, límites, hashes, evidencia privada reproducible y **prompt de
continuidad vigente** en [COMMUNITY_PAYROLL_API.md](COMMUNITY_PAYROLL_API.md).


## Días reales, entradas repetidas y redondeo OCA — 28-10-2026

Código `bebf5ab`, paquete F: tres addons/17 archivos idénticos, 68 pruebas
Community oficial (64/0 EE) y 15 contratos compartidos contra Nómina real en
copia fresca de Cerro (376/140 EE). Se conservan 918 tablas/proyecciones,
140 contadores exactos incluso después de fixtures, 58.956 XML IDs, relaciones,
permisos, históricos y saldos. Menú, formulario, configuración y onchange de
liquidación se comprueban con permisos normales y fixtures revertidas.

Se implementan horas/días sobre work entries y calendarios reales, tipos FK,
OUT sin maestros paralelos y actualización de días conservando IDs. El cálculo
con ese modo rechaza entradas faltantes, conflictos y relaciones heredadas sin
adoptar. Las repeticiones tipadas homogéneas ahora se evalúan y agregan sin perder
filas, incluidos conceptos no lineales, categorías y el helper de totales OCA;
la mezcla ambigua con entradas sin tipo sigue rechazada. Se contrasta el
redondeo CLP por concepto con dos escenarios del puente chileno, sin cambiarlo
en producción ni recalcular pagadas. YTD sigue explícitamente pendiente.

La copia es referencia con su motor original; no instala OCA ni representa una
conversión integral. El nuevo mapa de lectura registra diferencias de campos,
FK/M2M, HTML/selecciones/estados que deben cerrarse antes de cambiar dependencias.
Simple Digital completo, las 71 reglas, Previred/libro, históricos pagados,
DTE/CAF/SII y el ensayo integral cero EE siguen pendientes. No se actualizan
servicios activos ni QA-Cerro, no se cambian vencimientos. Siguen 53 clausuras EE
sobre 93 apps inventariadas y 140 EE en producción. El 31 continúa con riesgo alto.

Alcance vigente, hashes, evidencia, mapa y **siguiente prompt** en
[COMMUNITY_PAYROLL_WORK_ENTRIES.md](COMMUNITY_PAYROLL_WORK_ENTRIES.md).


## Instalación Simple Digital–OCA — 28-10-2026

Paquete K, código c930d5a: 80 pruebas Community oficial (68 módulos/0 EE) y
27 en copia fresca nativa de Cerro (377/140 EE), con 82 archivos idénticos.
Se conservan 918 tablas/proyecciones, 140 contadores, 58.956 XML IDs y metadatos,
permisos, relaciones, históricos y saldos originales. El proveedor real instala
sin campos faltantes ni diferencias en los atributos comparados de sus campos;
se prueban aliases de IDs originales, acceso propio/ajeno, formulario/acción e
informe. La referencia mantiene su motor: la conversión integral, almacenamiento
histórico, 71 reglas, YTD, Previred/libro y DTE/CAF/SII siguen pendientes.
El vencimiento del 31 no está resuelto. Producción y QA-Cerro no se modifican.

Estado, alcance, evidencia privada y **prompt vigente** en
[COMMUNITY_SIMPLEDIGITAL_OCA.md](COMMUNITY_SIMPLEDIGITAL_OCA.md).
La continuidad horaria autorizada y sus puertas de cierre están en
[COMMUNITY_AUTONOMIA.md](COMMUNITY_AUTONOMIA.md); la matriz completa actualizada es
[COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md](COMMUNITY_INVENTARIO_ENTERPRISE_20261028.md).


## Históricos monetarios OCA — continuidad del 28-10-2026

Paquete C de código 434fc86: 90 pruebas Community (68/0 EE) y 30 en copia fresca
nativa (377/140 EE). Se conservan 918 tablas/proyecciones, 140 contadores,
58.956 XML IDs y metadatos/relaciones/permisos/saldos originales. Se cierran cinco
contratos de almacenamiento monetario; las diferencias de store bajan de 17 a 12.
Hay protección de históricos al leer/cambiar sueldos y admisión antes del upgrade,
con un upgrade Community real 1.0->1.1 sobre fixtures, sin convertir Cerro.
Estado, evidencia, límites y **siguiente prompt vigente** en
[COMMUNITY_PAYROLL_HISTORY.md](COMMUNITY_PAYROLL_HISTORY.md). La configuración
original, histórico real, DTE/CAF/SII y conversión integral siguen pendientes;
no se considera resuelto el 31 y no se modifican producción ni QA-Cerro.


## Configuración esencial y procedencia — 28-10-2026

Paquete B de código 510b7d2: 96 pruebas Community y 36 en copia fresca nativa,
conservando 918 tablas/proyecciones, 140 contadores y 58.956 XML IDs. El guard
estructural detecta que la configuración de Cerro no demuestra la conexión
BASIC/GROSS. Se conservan sus reglas y los aliases de tres IDs originales, con
retiro seguro. SyS fue consultado únicamente en lectura para contrastar perfiles;
no se trasladan ni corrigen configuraciones automáticamente. Estado, evidencia,
límites y **siguiente prompt vigente** en
[COMMUNITY_PAYROLL_CONFIGURATION.md](COMMUNITY_PAYROLL_CONFIGURATION.md).
No hay conversión integral ni certificación financiera; el 31 sigue en riesgo.


## Orden de reglas e identidad histórica — 28-10-2026

Código f79071a, paquete A: 99 pruebas Community oficial y 39 copia fresca nativa.
Orden OCA explícito por secuencia/ID original, contratos reales de NET repetido
y condicionado, y diagnóstico de todos los IDs candidatos sin adoptar ambiguos.
Se preservan 918 tablas/proyecciones, 140 contadores y 58.956 XML IDs. Auditoría
de solo lectura conserva visibles las tres identidades NET referidas históricamente
en SyS; no se recalcula ni cambia ninguna. Matriz completa regenerada sin diferencias:
374 instalados, 93 propios, 140 EE y 53 clausuras EE candidatas pendientes.
Estado, evidencia, límites y **siguiente prompt vigente**:
[COMMUNITY_PAYROLL_RULE_ORDER.md](COMMUNITY_PAYROLL_RULE_ORDER.md).
La configuración original sigue bloqueada; 71 reglas, YTD, Previred/libro,
DTE/CAF/SII y conversión integral cero Enterprise no están certificados. El 31
sigue en riesgo alto; producción y QA-Cerro permanecen intactos.


## YTD calendario almacenado — 28-10-2026

Código 7191d77, paquete E: 106 pruebas Community oficial y 46 copia fresca nativa.
Motor OCA real con YTD calendario almacenado y API de lectura, admisión de snapshots
originales e inmutabilidad de credit_note en cerradas; falla si el acceso oculta
liquidaciones o líneas del histórico. El alcance deja bloqueados fiscalidad especial,
cambios de contrato, créditos actuales y conceptos repetidos hasta validarlos.
Se preservan 918 tablas/proyecciones, 140 contadores y 58.956 XML IDs. Cinco campos
cierran su ausencia (1.081->1.076); no se adoptan IDs ni cambian dependencias.
Matriz completa regenerada sin cambios: 374 instalados, 93 propios, 140 EE y
53 clausuras EE candidatas pendientes. Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_PAYROLL_YTD.md](COMMUNITY_PAYROLL_YTD.md). Siguen pendientes la
configuración original y las 71 reglas, YTD restante, Previred/libro, consumidores,
DTE/CAF/SII y conversión integral restaurable cero Enterprise. El 31 sigue en riesgo
alto. No se modifican producción ni QA-Cerro.


## Núcleo Previred independiente del motor — 28-10-2026

Código 9044539, paquete A: 113 pruebas Community con OCA/proveedor y 53 en copia
fresca nativa. Siete pruebas adicionales instalan el núcleo en Community sin motor,
sin hr.payslip registrado ni Enterprise. Se conservan sus modelos, relaciones,
perfiles, lotes, acciones, grupos y ACL; los roles resuelven el grupo real sin
fabricar identidades. Solo después de cerrar esa frontera se admite la dependencia
neutra step_payroll_contracts. Se preservan 918 tablas/proyecciones, 140 contadores
y 58.956 XML IDs. El mapa parcial baja de 1.076 a 984 campos ausentes; no se adoptan
IDs del motor ni se certifica Previred oficial. La matriz completa baja de 53 a 52
apps propias con caminos EE pendientes; producción sigue con 140 Enterprise.
Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_PREVIRED_CORE.md](COMMUNITY_PREVIRED_CORE.md). Siguen pendientes la
configuración original y las 71 reglas, YTD restante, puente Simple Digital de
Previred, Libro/consumidores, DTE/CAF/SII y conversión integral restaurable cero EE.
El 31 sigue en riesgo alto. Producción y QA-Cerro permanecen intactos.


## Puente Previred Simple Digital y capacidad — 28-10-2026

Paquete C, addons 647fa7a: 139 pruebas Community y 79 copia fresca nativa.
El puente carga con OCA real, conserva paid, respeta cero/NULL almacenados y
controla salarios parciales ocultos antes de sudo; el generador real no vacío
aún no está certificado. Se preservan 918 tablas/proyecciones, 140 contadores,
58.956 XML IDs y exactamente 1.614 relaciones usuario-grupo/283 implicaciones.
Quedan 52 apps con caminos EE y producción conserva 140; el mapa mantiene 984
ausencias y baja de seis a cinco diferencias de selección.

El usuario autorizó limpieza de respaldos antiguos: se retiraron 60 bases
temporales inactivas y 19 dumps redundantes, conservando referencias y tres
respaldos completamente comprobados antes de retirarlos. El volumen PostgreSQL
era distinto al de /opt; el validador ahora exige 5 GiB allí y 2 GiB en artefactos,
con bloqueo y restauración que se detiene al primer error. No se borró producción,
QA-Cerro ni datos/respaldos de otros productos. Estado, evidencia y siguiente prompt:
[COMMUNITY_PREVIRED_SIMPLEDIGITAL.md](COMMUNITY_PREVIRED_SIMPLEDIGITAL.md).
No hay conversión integral ni resolución del 31; siguen configuración/71 reglas,
Previred no vacío, Libro/consumidores, YTD restante y DTE/CAF/SII.


## Base salarial histórica y auditoría completa — 28-10-2026

Código c8ab6e3/780c9c8, paquete A: 143 pruebas Community (cero Enterprise) y
83 en copia fresca nativa. El puente rechaza helpers que derivan una liquidación
cerrada desde el contrato vigente, incluidos contextos que retornarían cero;
conserva acceso a los importes originales almacenados y las ACL. No añade campos,
backfill ni dependencias. Se preservan 919 tablas/proyecciones, 140 contadores,
59.036 XML IDs y 1.614 relaciones usuario-grupo/283 implicaciones. Esta copia ya
incluye BPA; no mezclar sus recuentos con el corte anterior.

El auditor revisa todas las reglas chilenas y categorías sin exportar fórmulas.
Sigue bloqueada la desconexión BASIC/IMP/GROSS; SyS tiene dos NET activos y no es
una configuración para importar automáticamente. El Libro consulta además datos
vivos que aún requieren cierre histórico. Quedan 52 apps con caminos EE y 140
Enterprise en producción. No hay conversión integral ni certificación salarial,
Previred/Libro oficial o resolución del 31. Estado, evidencia y **siguiente prompt
vigente**: [COMMUNITY_PAYROLL_WAGE_BASIS.md](COMMUNITY_PAYROLL_WAGE_BASIS.md).


## Libro: snapshots salariales y permisos — 28-10-2026

Código de addons 97a1ec9, paquete E: 150 pruebas Community (cero Enterprise) y
90 en copia fresca nativa, sin fallos. El Libro del proveedor real lee los totales
SQL originales, incluido cero y líneas archivadas OCA, sin reconstruir importes.
Comprueba padres, campos y todas las líneas; rechaza NULL o líneas ocultas antes
de formatear. Selecciona done/paid por período/compañía sin sudo y vuelve a aplicar
el actor HTTP si recibe un registro elevado. No cambia dependencias ni identidades.

Se preservan 919 tablas/proyecciones, 140 contadores, 59.039 XML IDs y las 1.614
relaciones usuario-grupo/283 implicaciones. El inventario ya incluye entrada
manual de contactos: 377 instalados/96 propios/140 Enterprise, 114 manifiestos
en repo y 22 fuera de Cerro. Siguen 52 apps instaladas con caminos EE.
Se retiraron ocho ensayos propios inactivos con dos planes verificados, cero dumps,
y se conservaron caso dorado, referencias y cuatro respaldos decodificados.

No se certifica el CSV oficial completo ni se convierte Cerro: quedan las columnas
basadas en datos vivos, Libro/tablero propio, configuración original/71 reglas,
identidad y almacenamiento del motor, casos chilenos, YTD, asientos y Previred.
Se pidió una referencia aprobada para resolver BASIC/IMP/GROSS sin inventar reglas.
Siguen DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma, demás productos
y conversión integral restaurable cero Enterprise. El 31 sigue en riesgo alto.
Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_PAYROLL_BOOK_LINES.md](COMMUNITY_PAYROLL_BOOK_LINES.md).


## Consumidores del Libro propio — 28-10-2026

Código 151c585, paquete C: 153 pruebas Community y 94 en copia fresca nativa.
Se adopta el mapa por código/ID de liquidación original en el extractor del Libro
propio y sus adaptadores de reglas, sin reconstruir totales ni eludir permisos.
La captura se pasa por lote a la resolución. Se mantiene hr_payroll y solo se
explicita el contrato neutral ya transitivo; aún no se instala el Libro completo
en Community. Allí se prueba su biblioteca Python real con OCA/Simple Digital;
la referencia nativa actualiza el módulo real 3.4.0->3.4.1 y su extractor registrado.
Los ámbitos se comprueban por SQL y no se presentan como conversión de Cerro.

Se preservan 919 tablas/proyecciones, 140 contadores, 59.039 XML IDs y exactamente
1.614 relaciones usuario-grupo/283 implicaciones. El inventario conserva 377
instalados/96 propios/140 EE, 114 manifiestos y 22 fuera de Cerro; siguen 52 apps
con caminos EE. La retención revisada retira cuatro copias propias obsoletas,
conserva casos dorados/referencia E y cuatro respaldos decodificados; no borra dumps.

Quedan Libro completo (herencia, menús, acciones, vistas, permisos), fuentes vivas,
tablero/archivo oficial, configuración original/71 reglas e identidad del motor,
casos chilenos, YTD/contabilización/Previred, DTE/CAF/SII, Tesorería, Calidad,
Studio/Documentos/Firma, demás productos y conversión integral restaurable cero EE.
La referencia humana BASIC/IMP/GROSS sigue pendiente. El 31 continúa en riesgo alto.
Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_OWN_BOOK_CONTRACTS.md](COMMUNITY_OWN_BOOK_CONTRACTS.md).


## Libro instalado realmente en Community — 28-10-2026

Paquete B, código 9b415b4: 158 pruebas Community (71 módulos, cero Enterprise)
y 98 en copia fresca nativa. El candidato Simple Digital instala el Libro completo,
con modelos, herencia real, vistas, menús, aliases de roles y permisos, consolidado
Excel y acción/renderizado HTML. Ya no es solo biblioteca. El CSV oficial OCA del
Libro propio queda bloqueado hasta certificarlo; faltan también rutas del proveedor,
tablero/navegador y PDF binario, casos chilenos e identidad del motor.

La derivación privada cambia solo el prerequisito del manifiesto por el puente
real Simple Digital. La dependencia genérica canónica sigue pendiente para no
forzar ese proveedor en otros productos. No se publica en servicios ni se retira
Enterprise en producción. Se preservan 919 tablas/proyecciones, 140 contadores,
59.039 XML IDs, 1.614 vínculos usuario-grupo y 283 implicaciones. El mapa baja de
984 a 934 campos ausentes; no acredita conversión ni certificación financiera.
El inventario mantiene 52 apps con caminos genéricos EE y 140 EE en producción.

Quedan reglas/configuración aprobada BASIC/IMP/GROSS, identidad/almacenamiento,
YTD/asientos/Previred/CSV, DTE/CAF/SII, Tesorería, Calidad, Studio/Documentos/Firma,
demás productos y conversión integral restaurable cero Enterprise. El 31 sigue
en riesgo alto. Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_BOOK_INSTALL.md](COMMUNITY_BOOK_INSTALL.md).


## Libro: descargas y tablero por HTTP real — 28-10-2026

Paquete B, código 562624c: 164 pruebas en Community oficial/OCA (71 módulos,
cero Enterprise), 104 en copia fresca nativa (380 módulos/140 Enterprise), sin
fallos. Se prueba descarga firmada, contenido del Excel, auditoría del actor,
firma/vencimiento de enlace/compañía/período/titular y bloqueo sin reporte ante
líneas ocultas. El tablero responde por JSON-RPC con acciones reales y totales
almacenados; respeta el permiso independiente Previred sin elevar privilegios.
El CSV oficial OCA del Libro propio continúa bloqueado por falta de certificación.

Mismo paquete de 196 archivos, preservando 919 tablas/proyecciones, 140 contadores,
59.039 XML IDs y los 1.614/283 vínculos de permisos originales. No se cambian
modelos, relaciones, IDs, ACL ni dependencia genérica. El candidato privado sigue
cambiando solamente el prerequisito por el puente Simple Digital real. El mapa
permanece en 934 campos ausentes: no acredita adopción histórica ni conversión.

Quedan referencia aprobada BASIC/IMP/GROSS, identidad/almacenamiento del motor,
71 reglas, estructuras/entradas, días reales, YTD/asientos, Previred/CSV oficiales
no vacíos, PDF binario y aceptación visual, rutas del proveedor, DTE/CAF/SII,
Tesorería, Calidad, Studio/Documentos/Firma y demás productos. La producción sigue
con 140 Enterprise; 52 apps propias mantienen caminos Enterprise. Falta conversión
integral restaurable cero Enterprise, conciliación y aceptación. El 31 sigue en
riesgo alto; no se escribe en producción ni se refresca QA-Cerro.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_BOOK_HTTP.md](COMMUNITY_BOOK_HTTP.md).


## Libro: PDF binario real y alcance — 28-10-2026

Paquete D, exportado de53d8d: 167 pruebas Community oficial/OCA y 107 en copia
fresca nativa, sin fallos. Libro real instalado en ambos; Community 71 módulos,
cero Enterprise; referencia 380/140. Conserva ceros visibles, fuente local,
propiedad del asistente, rechazo de IDs múltiples y auditoría única por PDF.
Los dos formatos se descargan por HTTP autenticado con wkhtmltopdf real,
no-store y recursos reales del runtime. Cuatro PDF/textos/tamaños/fuentes y PNG
verificados; alcance de una línea/página por formato, no certificación financiera,
aceptación del navegador ni prueba de volúmenes reales.

Mismo paquete de 196 archivos, preservando 919 tablas/proyecciones, 140 contadores,
59.039 XML IDs, 1.614 vínculos usuario-grupo y 283 implicaciones. Dependencia
genérica intacta; candidato privado específico cambia solo el prerequisito real.
934 campos siguen ausentes: no se acepta adopción histórica del motor.

Permanecen configuración aprobada BASIC/IMP/GROSS y 71 reglas, identidad/almacén,
entradas/días/YTD/asientos, Previred/CSV oficiales no vacíos, rutas del proveedor,
DTE/CAF/folios/firma/respuestas SII, Tesorería, Calidad, Studio/Documentos/Firma y
otros productos. Producción conserva 140 EE; 52 apps propias aún tienen caminos
EE. Falta conversión integral restaurable cero Enterprise y aceptación. El 31
sigue en riesgo alto. No se escribe en producción ni se refresca QA-Cerro.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_BOOK_PDF.md](COMMUNITY_BOOK_PDF.md).


## SyS real, identidad histórica y capacidad — 28-10-2026

Referencia aportada por el usuario: SyS, auditada por SQL de solo lectura.
623 liquidaciones done, 622 completas sin ambigüedad y una con NET de dos reglas
(8/32). Cápsula privada de septiembre preparada; falta reproducción con hechos
históricos probados, sin usar sueldo/fórmulas actuales como historia.

step_payroll_contracts 18.0.1.6.0 impide sumar dos identidades de regla para
BASIC/GROSS/NET al exportar con el lector compartido; conserva filas repetidas
de la misma regla y los originales. Paquete F de 04c8e43: 163 pruebas Community
oficial y 103 copia fresca nativa, sin errores. Mismos 196 archivos, Libro real
instalado, 71/0 módulos/EE en Community y 383/140 en referencia. Preservados
919 tablas/proyecciones, 140 contadores, 59.048 XML IDs y permisos originales.

Se retiraron ocho bases propias obsoletas (914.938.744 bytes), cero dumps,
verificando cinco respaldos distintos. El usuario autorizó ampliar el disco
compartido de 100 a 150 GiB: dumps SyS/Cerro decodificados, snapshot READY,
ext4 ampliado bajo bloqueo, sin DML de negocio ni reinicios. Reserva final
de la ampliación 54.364.999.680 bytes. Sin refrescar QA-Cerro.

Inventario posterior a T130: 380 instalados, 99 propios y 140 Enterprise;
117 manifiestos propios, 22 fuera de Cerro, 54 apps instaladas con caminos EE.
Siguen pendientes identidad/almacén del motor (934 campos ausentes), evaluación
real de NET duplicado, configuración/certificación de 71 reglas, días/entradas/
YTD/asientos, Previred y CSV no vacíos, DTE/CAF/SII, Tesorería, Calidad, Studio/
Documentos/Firma y otros productos. Falta conversión integral restaurable cero
Enterprise y aceptación: el 31 sigue en riesgo alto.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_SYS_REFERENCE.md](COMMUNITY_SYS_REFERENCE.md).


## Colisiones de reglas y límite temporal SyS — 28-10-2026

Paquete D de 8ca0d3b: 166 pruebas Community oficial/OCA y 106 en copia fresca
nativa, cero errores; mismos 196 archivos. step_payroll_contracts 18.0.1.7.0
reporta todos los códigos activos directos duplicados y el guard de Nómina Chile
los rechaza antes de cambiar líneas existentes, sin escoger/desactivar maestros.
Cuatro observaciones con motores reales coinciden: código repetido puede
sobrescribir la línea anterior y dejar efectos en categorías; no certifican SyS.
Preservados 919 tablas/proyecciones, 140 contadores, 59.048 XML IDs y permisos.
Libro/proveedor reales instalados: Community 71/0 módulos/EE, referencia 383/140.

Auditoría temporal de solo lectura ligada a la cápsula de septiembre: contrato
modificado después del período, cero tracking salarial, hr.contract.history
es vista dependiente de hr_contract.wage actual. Eso no acredita sueldo histórico.
Recuperar referencia temporal aprobada antes del replay; si falta, avanzar DTE
sin inventar maestros ni recalcular el original cerrado. Anomalía NET 8/32 intacta.

Inventario completo reauditado: 380 instalados/99 propios/140 EE, 117 manifiestos
propios, 22 fuera de Cerro y 54 apps con caminos EE; matriz sin cambios. Siguen
identidad/almacén (934 campos ausentes), 71 reglas, días/entradas/YTD/asientos,
Previred/libro no vacíos, DTE/CAF/SII, otros productos y conversión integral
restaurable cero Enterprise con aceptación. Sin publicación en producción ni
refresco QA-Cerro. El 31 continúa en riesgo alto, no resuelto.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_RULE_COLLISIONS.md](COMMUNITY_RULE_COLLISIONS.md).


## Referencia documental positiva SyS — 28-10-2026

Paquete D de 1d7e626, núcleo 18.0.1.8.0: 124 pruebas Community oficial/OCA y
64 en copia fresca nativa, cero errores. Perfil simpledigital, proveedor real
instalado: 68/0 módulos/EE Community y 383/140 referencia. Se conserva aceptación
previa de Libro/Previred/HTTP/PDF sin repetir rutas sin cambios. Mismos 95 archivos,
919 tablas/proyecciones, 140 contadores, 59.048 XML IDs y permisos preservados.

La selección anterior era un caso cero válido. El nuevo helper conserva todos
los casos y prioriza uno cerrado positivo de períodos anteriores al actual.
Auditoría SyS actual: 627 done, 626 completos no ambiguos, uno NET 8/32;
612 referencias positivas de períodos previos. Se preserva PDF existente
vinculado por checksum/hash, sin generar reporte ni recalcular. BASIC/NET
coinciden con SQL; GROSS coincide con imponible, no con total haberes. Sueldo
impreso observado en cápsula privada; cronología maestra y certificación
financiera aún no aceptadas. Falta replay aislado y adaptación real de reglas.

Inventario completo y matriz regenerada sin cambios: 380 instalados/99 propios/
140 EE, 117 manifiestos, 22 fuera de Cerro y 54 apps con caminos EE. Siguen
identidad/almacén, 71 reglas, días/entradas/redondeos/YTD/asientos, Previred/libro
no vacíos, DTE/CAF/SII y demás productos; falta conversión integral restaurable
cero Enterprise y aceptación. El 31 sigue en riesgo alto. Sin publicación en
producción, recálculos de originales ni refresco QA-Cerro.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_SYS_DOCUMENT_REFERENCE.md](COMMUNITY_SYS_DOCUMENT_REFERENCE.md).


## BASIC mensual y relación tipada de días — 28-10-2026

Núcleo 18.0.1.9.0 reconoce sin ejecutar Python la base mensual por días
explícitos; conserva guardas de ambigüedad/conexión y financial_certified=false.
API Community 18.0.1.5.0 conserva la relación tipo/código obligatorio al crear
y editar días abiertos, bloquea cambios de códigos usados y no reconstruye
históricos al leer. Lista y subformulario usan el maestro existente sin creación
rápida. Sin cambios de dependencias ni ACL.

Paquete F de 648d15e: 131 pruebas Community oficial/OCA y 68 copia fresca nativa,
cero errores. BASIC aislado de SyS coincide con SQL original en ambos motores
reales, con sueldo documental y snapshots de días/horas. TransactionCase y
verificación SQL de cero empresas/usuarios restantes: rollback comprobado.
WORK100 conserva ID 1. No es replay completo de período/empleado, certificación
de 71 reglas ni adopción de identidad. E se rechazó por un alta de fixture desde
shell que autoinstaló módulos/dejó empresa solo en la base privada Community.

Mismos 96 archivos; Community 68/0 módulos/EE, referencia 383/140. Preservados
919 tablas/proyecciones, 140 contadores, 59.048 XML IDs y permisos originales.
Matriz completa idéntica: 380 instalados/99 propios/140 EE, 117 manifiestos,
22 fuera de Cerro y 54 apps con caminos EE. Siguen campos/almacén/IDs históricos,
amount/quantity/rate, reglas/estructuras, GROSS imponible y NET 8/32, días reales,
YTD/asientos, Previred/libro no vacíos, DTE/CAF/SII y demás productos. Falta
conversión integral restaurable cero EE y aceptación. El 31 sigue en riesgo alto.
Sin publicación en producción, recálculos originales ni refresco QA-Cerro.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_PAYROLL_REAL_BASIS.md](COMMUNITY_PAYROLL_REAL_BASIS.md).


## Componentes históricos y BASIC — 29-10-2026 UTC

Núcleo 18.0.1.10.0 añade lector SQL autorizado por línea: ID/liquidación/regla,
código, amount/quantity/rate/total guardados. No suma factores ni reconstruye
totales; rechaza nulos/no finitos y conserva reglas ambiguas como filas distintas.
El agregado anterior continúa bloqueando NET ambiguo. Cuatro contratos reales
prueban redondeo, estabilidad, permisos completos y falta de reparación al leer.

Paquete D de c4e8d0b: 135 pruebas Community oficial/OCA y 72 copia fresca nativa,
cero errores. BASIC positivo de SyS coincide por separado en sus cuatro
componentes; FK aplicada y snapshot/write_date originales comprobados. Rollback
verificado, cero empresas/usuarios de fixture. No es replay completo, certificación
de 71 reglas ni adopción de identidad. Se preservan 919 tablas/proyecciones,
140 contadores, 59.048 XML IDs y permisos; mismos 96 archivos entre entornos.
Community 68/0 módulos/EE, referencia 383/140. Sin despliegue, recálculo original
ni refresco QA-Cerro.

Matriz completa idéntica: 380 instalados/99 propios/140 EE, 117 manifiestos,
22 fuera de Cerro y 54 apps con caminos Enterprise. Prioridad siguiente:
almacenamiento/identidad de días y códigos con históricos reales en copia privada
SyS, antes de dependencias; después contexto efectivo, GROSS/NET, 71 reglas, YTD/
asientos y salidas oficiales. DTE/CAF/SII y los otros productos siguen pendientes.
Falta conversión integral restaurable cero EE y aceptación. El 31 sigue en riesgo alto.

Estado, evidencia y **siguiente prompt vigente**:
[COMMUNITY_PAYROLL_COMPONENTS.md](COMMUNITY_PAYROLL_COMPONENTS.md).
