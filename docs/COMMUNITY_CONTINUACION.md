# Continuidad de migración Community — Cerro El Plomo

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
