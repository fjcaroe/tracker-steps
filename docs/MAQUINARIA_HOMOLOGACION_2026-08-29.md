# Maquinaria — homologación funcional Desarrollo / Demo (29-08-2026)

Segunda ronda sobre el módulo de Maquinaria: catálogo contable canónico,
búsqueda por nombre histórico, Folio BPA siempre al día y validación completa
del flujo hasta el comprobante contable.

Versiones finales: `step_machinery 18.0.21.0.0`, `step_bpa_irrigation 18.0.2.3.1`.
`step_agricultural_access 18.0.2.1.0` y `step_operations_ui 18.0.2.0.2` sin tocar.

## 1. Hallazgos, causa y solución

| # | Hallazgo | Causa | Solución |
|---|---|---|---|
| 1 | Demo tenía 7 conceptos y códigos corridos: *Mantención preventiva* con `05`, *Depreciación mensual* con `07`, sin *Mano de Obra* | El catálogo se cargó a mano y nunca se homologó con Desarrollo | `type.service.machinery._ensure_canonical_catalog()`: empareja por **significado** (nombre normalizado sin tildes), con respaldo por código, y renumera |
| 2 | Sólo 1 de 7 conceptos de Demo tenía cuentas, y apuntaban a `410160` / `220320` | Configuración manual incompleta | La misma rutina asigna `410161` / `210233` a los ocho conceptos |
| 3 | Las cuentas `410161` y `210233` no existían en Demo | Nunca se crearon en esa base | Se crean por ORM con `account_type` correcto (`expense` / `liability_current`), sin tocar `code_store` ni IDs |
| 4 | El diario `CDMaq` sólo permitía `110220`, lo que hacía fallar *Contabilizar* | `account_control_ids` mal acotado | Se amplía conservando lo autorizado y agregando las cuentas ya usadas en apuntes (Odoo prohíbe restringir un diario con apuntes fuera de la lista) |
| 5 | `UniqueViolation` al renumerar en Demo | Los `write` del ORM quedaban en buffer: los códigos temporales no llegaban a base antes de los definitivos | `flush_all()` explícito entre las fases temporal, definitiva y de creación |
| 6 | `OT W35` y demás referencias históricas ya no se encontraban | `legacy_name` no estaba en la búsqueda | `legacy_name` en `_rec_names_search`, en el `filter_domain` del buscador y como columna opcional de la lista |
| 7 | `bpa_folio` podía quedar obsoleto | `@api.depends` sólo miraba `bpa_order_id` | Depende también de `bpa_order_id.x_studio_nmero_ot_bpa` y `.x_name`; y `x_aplicacion_foliar.write()` recompone los nombres de las Horas Máquina aún editables |

## 2. Catálogo canónico

Idéntico en Desarrollo y Demo, los ocho con cargo `410161 Costo estándar
maquinarias` y abono `210233 Provisión costo maquinarias`:

```
01 Combustible              05 Mano de Obra
02 Aceites y lubricantes    06 Arriendo
03 Repuestos                07 Mantención preventiva
04 Mantención correctiva    08 Depreciación mensual
```

Diario `CDMaq` en ambos ambientes: `110220, 210230, 210233, 410161`.

La rutina es idempotente, no usa IDs de base de datos, no duplica conceptos y
**conserva las relaciones**: en Demo las 7 líneas de `monthly.consumption.line`
y `monthly.radio.line` siguen apuntando al mismo registro, sólo cambió su
código (id 4 `05`→`07`, id 7 `07`→`08`).

Vive en el modelo, no sólo en el script, así que corre desde tres sitios:
`post_init_hook` (instalación limpia), migración `18.0.21.0.0` (bases
existentes) y las pruebas.

## 3. Migraciones creadas

| Migración | Qué hace |
|---|---|
| `step_machinery/migrations/18.0.21.0.0/post-migrate.py` | Homologa catálogo, cuentas y diario. Registra conceptos encontrados / normalizados / creados, cuentas creadas o reutilizadas, relaciones asignadas y configuración final del diario |
| `step_bpa_irrigation/migrations/18.0.2.3.0/post-migrate.py` | Recalcula `bpa_folio` (cambió el `depends`) y recompone nombres editables |
| `step_bpa_irrigation/migrations/18.0.2.3.1/post-migrate.py` | Suelta restricciones `NOT NULL` huérfanas de Studio en tablas BPA cuando el campo Python no es obligatorio. Hoy no encontró ninguna que corregir en ninguna base |

Se conservan las de la ronda anterior (`18.0.20.0.0` y `18.0.2.2.0`).

### Log real de la migración en Demo

```
antes  -> 7 conceptos (['01','02','03','04','05','06','07']), 1 con cargo, 1 con abono
normalizados: 'Mantención preventiva' 05 -> 07 ; 'Depreciación mensual' 07 -> 08
creados: 05 Mano de Obra
cuentas creadas: 410161 (expense), 210233 (liability_current)
relaciones asignadas: los 8 conceptos -> cargo 410161 / abono 210233
diario final: CDMaq: 110220, 210230, 210233, 410161
después -> 8 conceptos (['01'..'08']), 8 con cargo, 8 con abono
```

En Desarrollo la migración encontró los 8 conceptos ya correctos: sólo amplió
el diario (`210233`, `410161`).

## 4. Conteos antes / después

| | Encabezados | Líneas | Costo real | Conceptos | Con `legacy_name` |
|---|---|---|---|---|---|
| LAB_TAREAS antes | 20 | 32 | 27 | 8 | 20 |
| LAB_TAREAS después | 21¹ | 32 | 27 | 8 | 20 |
| STEPS_DEMO antes | 0 | 0 | 0 | 7 | 0 |
| STEPS_DEMO después | 1¹ | 0 | 0 | 8 | 0 |

¹ El registro adicional es el de validación QA, anulado y documentado abajo.
Los 20 encabezados, 32 líneas y 27 registros de costo real históricos de
Desarrollo están intactos.

## 5. Registros QA

| Ambiente | Modelo | ID | Número OT | Nombre | Estado |
|---|---|---|---|---|---|
| Desarrollo | `step.hrs.machinery` | **36** | 22 | `22 28/08/2026 OT PRUEBA QA W36 – OT_BPA 15255` | Anulado |
| Demo | `step.hrs.machinery` | **41** | 8 | `8 28/08/2026 OT PRUEBA QA W36 – OT_BPA 10` | Anulado |
| Demo | `x_aplicacion_foliar` | **11** | — | `BPA202600007`, número OT-BPA `10` | Ingresado (sintética para QA) |

Ambos llevan la nota *"Registro de validación QA 29-08-2026. No usar."* y su
Orden de Trabajo empieza con `PRUEBA QA`. Secuencias dejadas coherentes:
`number_next` 23 en Desarrollo y 9 en Demo (ningún hueco reutilizable).

## 6. Pruebas

### Base desechable

`MAQ_TEST_20260828`, creada e instalada desde cero y **eliminada al terminar**:

```
0 failed, 0 error(s) of 50 tests
step_machinery: 46 tests · step_bpa_irrigation: 16 tests
```

Cubre, además de lo de la ronda anterior:

- catálogo con los 8 conceptos, todos con cuentas canónicas;
- idempotencia (segunda pasada sin crear, renumerar ni reasignar);
- códigos intercambiados reparados **con el estado roto ya en base**, que es lo
  que reprodujo el fallo real de Demo;
- relación existente que sobrevive a la renumeración;
- creación de cuentas por ORM con el `account_type` correcto;
- diario restringido ampliado sin perder cuentas autorizadas;
- diario sin restricción que se deja como está;
- concepto renombrado por la casa: se reconoce por código y no se duplica;
- costeo de los ocho conceptos con verificación importe por importe;
- comprobante balanceado con cargo `410161` y abono `210233`;
- distribución analítica presente en el cargo;
- doble contabilización bloqueada;
- multiempresa con cuentas propias por empresa;
- búsqueda por `legacy_name` (dominio y `name_search`);
- Folio BPA: cambio de número, cambio de referencia, registro costeado que
  conserva su nombre, `bpa_folio` nunca obsoleto en base, escritura masiva
  sobre varias OT-BPA y ausencia de recursión / escrituras inútiles;
- **guardado por la ruta real del cliente web**: `HttpCase` autenticado que
  llama `/web/dataset/call_kw` → `get_views`, `onchange` y `web_save` sin
  enviar `name`, y comprueba el Número OT y la recomposición del nombre.

### Flujo controlado en Desarrollo y Demo (transacción con rollback)

Idéntico resultado en ambos:

| | Desarrollo | Demo |
|---|---|---|
| Catálogo | 01–08, 8 con cuentas | 01–08, 8 con cuentas |
| Diario | CDMaq: 110220, 210230, 210233, 410161 | igual |
| Creado sin `name` | `21 28/08/2026 OT W35` | `1 28/08/2026 OT W35` |
| Componentes 01–08 | 300 / 20 / 16 / 12 / 40 / 30 / 10 / 4 ✓ | idénticos ✓ |
| Total máquina / hora | 432,00 / 216,00 | 432,00 / 216,00 |
| Comprobante | debe 432 = haber 432, cargo `410161`, abono `210233`, diario CDMaq | igual |
| Distribución analítica | presente en el cargo | presente |
| Doble contabilización | bloqueada | bloqueada |
| Nombre tras contabilizar | congelado | congelado |
| Tras rollback | 20 encab. / 32 líneas, sin vehículos QA | 0 / 0, sin vehículos QA |

## 7. Archivos modificados

```
step_machinery/__manifest__.py                             18.0.20.0.0 -> 18.0.21.0.0 (+ post_init_hook)
step_machinery/__init__.py
step_machinery/hooks.py                                    (nuevo)
step_machinery/models/type_service_machinery.py            (catálogo canónico)
step_machinery/models/step_hrs_machinery.py                (legacy_name en _rec_names_search)
step_machinery/views/step_hrs_machinery_view.xml           (buscador y lista)
step_machinery/migrations/18.0.21.0.0/post-migrate.py      (nuevo)
step_machinery/tests/__init__.py
step_machinery/tests/test_ot_naming.py                     (+ búsqueda por nombre histórico)
step_machinery/tests/test_canonical_catalog.py             (nuevo)
step_machinery/tests/test_accounting.py                    (nuevo)
step_machinery/tests/test_web_form.py                      (nuevo)
step_bpa_irrigation/__manifest__.py                        18.0.2.2.0 -> 18.0.2.3.1
step_bpa_irrigation/models/machinery_integration.py        (depends + propagación)
step_bpa_irrigation/views/bpa_machinery_views.xml          (buscador)
step_bpa_irrigation/migrations/18.0.2.3.0/post-migrate.py  (nuevo)
step_bpa_irrigation/migrations/18.0.2.3.1/post-migrate.py  (nuevo)
step_bpa_irrigation/tests/test_machinery_naming.py         (+ 7 pruebas de Folio BPA)
```

## 8. Respaldos verificados

`/opt/backups/maquinaria_20260828_r2/`

| Archivo | Validación | SHA-256 |
|---|---|---|
| `LAB_TAREAS_20260828_r2.dump` | `pg_restore --list` → 29 877 entradas | `5670a7dfd78ce0acee2ee0b184e9e517f7307ae0f10ed95bad227083cee70df4` |
| `STEPS_DEMO_20260828_r2.dump` | `pg_restore --list` → 29 347 entradas | `1b70ee1fc0ad2b28df7ec57d06f9ca03c322b7cb0844efc657667a69dc2cf65e` |
| `dev_addons_20260828_r2.tgz` | `tar -tzf` → 102 archivos | `dfc9ea3525e19bfceca60c16b372fd080f695d2242ac91e9efbfb4eba6ca3d7f` |
| `demo_addons_20260828_r2.tgz` | `tar -tzf` → 102 archivos | `7f2196184cce597ec5edacb638259ae9b9fd7c0c9fc26aa27432a8c7722a3573` |

Se conservan además los respaldos de la ronda anterior en
`/opt/backups/maquinaria_20260828/`.

## 9. Estado final

| | Desarrollo | Demo |
|---|---|---|
| Servicio | `odoo18-dev.service` activo | `odoo18-demo.service` activo |
| Odoo directo | `127.0.0.1:8075` → 200 | `127.0.0.1:8080` → 200 |
| nginx (Host header) | 200 | 200 |
| `step_machinery` | 18.0.21.0.0 | 18.0.21.0.0 |
| `step_bpa_irrigation` | 18.0.2.3.1 | 18.0.2.3.1 |
| SHA-256 `step_machinery` | `8edd8df366841be99729392623cbf8e0f2eff6aa3ceeea7c519e688f3e717432` | idéntico |
| SHA-256 `step_bpa_irrigation` | `d528b152ebe5c53bfb8576003d90d394044ef3d75404efbc22121450af19445b` | idéntico |

El árbol local `C:\Users\tito4\Documents\Odoo` coincide **archivo por archivo**
con ambos servidores. Logo moderno intacto, sin rastro de `JE`.

## 10. Pendientes reales

1. **DNS de `stepsapp.cl` caído.** `stepsapp.cl`, `desarrollo.stepsapp.cl` y
   `demo.stepsapp.cl` responden `NXDOMAIN` en 8.8.8.8 y en 1.1.1.1 desde el
   servidor y desde el PC. nginx y Odoo sirven 200 correctamente cuando se les
   llama con la cabecera `Host`, así que es un problema de zona DNS, ajeno al
   despliegue. Es lo único que impide la validación visual por navegador contra
   las URLs públicas.
2. **Diario `CDMaq` con lista de cuentas permitidas.** Quedó ampliado y
   funcional, pero sigue siendo una lista cerrada: cualquier concepto nuevo con
   otra cuenta volverá a fallar. Conviene decidir si esa restricción tiene
   sentido o se vacía.
3. **Crear una OT-BPA revienta si *Capacidad lts aplicadora* va en 0.** El campo
   Studio calculado `x_studio_maquinadas` divide por él y lanza
   `ZeroDivisionError`. Ocurre igual en Desarrollo y en Demo. Fuera del alcance
   de Maquinaria; se documenta para un encargo de BPA.
4. **`x_studio_consumo_lt_x_hora` está marcado obligatorio** en el modelo
   `x_aplicacion_foliar` de ambas bases. No es divergencia entre ambientes, pero
   obliga a informarlo para crear cualquier OT-BPA. No se modificó: es una
   decisión funcional del formulario BPA.
5. **`steps_api` figura instalado** en ambas bases sin código en ningún
   `addons_path`. Aviso previo, desde al menos el 27-08.
6. **Despliegue concurrente detectado.** A las 03:11 otra sesión estaba
   actualizando `step_hr_previred` en STEPS_DEMO y STEPS_DEMO_SYS; una de mis
   transacciones chocó con un `SerializationFailure`. Esperé a que terminara y
   repetí. No se tocó Previred ni Demo-SyS.
