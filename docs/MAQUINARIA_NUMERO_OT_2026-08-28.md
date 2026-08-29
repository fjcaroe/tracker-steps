# Maquinaria — Número OT y nombre automático (28-08-2026)

Corrección del formulario **Horas Máquina** (`step.hrs.machinery`) según
`A2 Módulo Maquinarias- correcciones.docx`.

## 1. Causa raíz

`name` estaba declarado `required=True` y en el formulario se pintaba con
`readonly="1"` dentro del `oe_title`. El cliente web exige un valor obligatorio
antes de enviar el `create`, pero el campo no era editable: el registro no se
podía guardar nunca desde la interfaz.

El `create` del servidor sí generaba un nombre, pero lo hacía consumiendo la
secuencia equivocada (`step_real_cost_machinery_seq`, la del costo real) y
concatenando el texto digitado. De ahí los nombres degradados que quedaron en
Desarrollo, por ejemplo `CostRM0CostRM00016-0015-CostRM00013-jamie`.

Además, una personalización Studio (`ir.ui.view` id 5470) anteponía al
formulario el campo manual `x_studio_folio_bpa` con etiqueta *Folio BPA*: ése
era el "primer campo Folio BPA" que el documento pide reemplazar por
*Número OT*. El campo no tenía datos en ninguna de las dos bases.

## 2. Modelo de datos final

| Campo | Tipo | Etiqueta | Comentario |
|---|---|---|---|
| `ot_number` | Char | Número OT | Correlativo de `ir.sequence`, `copy=False`, `readonly`, indexado, con seguimiento |
| `date` | Date | Fecha | Sin cambios |
| `folio` | Char | Orden de Trabajo | Campo existente **reutilizado**; ya tenía esa semántica y estaba vacío en las 20 fichas |
| `bpa_order_id` | Many2one `x_aplicacion_foliar` | Folio BPA | Sin cambios de tipo; ya no pisa `folio` |
| `bpa_folio` | Char calculado almacenado | Folio BPA (texto) | Número visible de la OT-BPA, usado para componer el nombre y para lista/búsqueda |
| `name` | Char | Nombre | Generado en servidor, `readonly`, `copy=False` |
| `legacy_name` | Char | Nombre histórico | Guarda el nombre anterior y cualquier `name` que envíe una integración antigua |

Restricción SQL nueva: `unique(company_id, ot_number)`.

## 3. Formato exacto del nombre

```
{Número OT} {dd/MM/yyyy}[ {segmentos unidos por " – "}]
```

Segmentos: `OT {Orden de trabajo}` (aporta `step_machinery`) y
`OT_BPA {Folio BPA}` (aporta `step_bpa_irrigation` extendiendo
`_name_segments`). Los segmentos vacíos no se agregan, por lo que no quedan
`False`, `None`, guiones huérfanos ni dobles espacios.

| Caso | Resultado |
|---|---|
| Completo | `125 28/08/2026 OT W35 – OT_BPA 10` |
| Sin Folio BPA | `125 28/08/2026 OT W35` |
| Sin Orden de trabajo | `125 28/08/2026 OT_BPA 10` |
| Sin ninguno de los dos | `125 28/08/2026` |

La composición vive en un único método reutilizable
`_compose_name()` / `_name_segments()`, invocado desde `create` y `write`
(servidor), nunca sólo desde un `onchange`.

### Cuándo se recompone

- Al crear, siempre.
- Al escribir `date`, `folio`, `bpa_order_id`, `ot_number` o `company_id`,
  mientras el registro **no** esté `Costeado` ni `Contabilizado` y no tenga
  comprobante.
- Un registro costeado o contabilizado conserva su nombre: el dato operacional
  se puede seguir corrigiendo, pero la identidad histórica queda fija (es la
  que aparece en `account.move.ref`).

La recomposición usa `super().write()` sobre el modelo base, de modo que no hay
recursión en `create`/`write` ni doble consumo de secuencia, y el nombre de la
interfaz es siempre el de la base.

## 4. Correlativo y multiempresa

- Secuencia `step.hrs.machinery.ot`, **sin prefijo ni sufijo y con padding 0**,
  declarada en un bloque `noupdate="1"` para que una actualización del módulo
  no reinicie el contador.
- `_next_ot_number(company)` usa `with_company(company).next_by_code(...)`:
  si existe una secuencia con el mismo código asignada a la empresa del
  registro, ésa tiene prioridad sobre la global. Basta duplicar el registro de
  secuencia para tener correlativo propio por empresa, sin tocar código.
- Nunca se usa `MAX(id)+1` ni conteos.
- **Cambio de empresa:** sólo se permite en estado `Nuevo` y sin comprobante;
  al cambiar se emite un correlativo de la secuencia de la empresa destino. En
  cualquier otro estado se bloquea con `UserError`.
- Las copias no reutilizan el número (`copy=False` en `ot_number`, `name` y
  `legacy_name`).
- `ot_number` enviado por RPC se ignora: el correlativo lo asigna el servidor.
- `name` enviado por cargas antiguas se acepta, se guarda en `legacy_name` y no
  suplanta al nombre oficial.

## 5. Migración

`step_machinery/migrations/18.0.20.0.0/post-migrate.py` (idempotente, no borra
ni sobrescribe silenciosamente):

1. Copia `name` → `legacy_name` sólo si `legacy_name` está vacío.
2. Asigna `ot_number` a los registros sin número, ordenados por
   `company_id, date, id`, arrancando sobre el mayor número existente.
3. Deja la secuencia por encima del mayor número asignado.
4. Archiva (no borra) la vista Studio que insertaba `x_studio_folio_bpa`,
   verificando antes que el campo no tenga datos.
5. Recompone el nombre de los registros no costeados ni contabilizados.

`step_bpa_irrigation/migrations/18.0.2.2.0/post-migrate.py` vuelve a componer
el nombre una vez que la extensión BPA ya está en el registro, para que el
segmento `OT_BPA` quede incorporado.

### Conteos antes / después

| Base | Encabezados | Líneas | Conciliaciones | Sin Número OT | Sin nombre | Con nombre histórico |
|---|---|---|---|---|---|---|
| LAB_TAREAS antes | 20 | 32 | 27 | 20 | 0 | 0 |
| LAB_TAREAS después | 20 | 32 | 27 | 0 | 0 | 20 |
| STEPS_DEMO antes | 0 | 0 | 0 | 0 | 0 | 0 |
| STEPS_DEMO después | 0 | 0 | 0 | 0 | 0 | 0 |

Números OT 1 a 20 en LAB_TAREAS; secuencia en 21. STEPS_DEMO sin registros,
secuencia en 1.

## 6. Interfaz

Orden en el formulario: **Número OT** (título, sólo lectura) → **Fecha** →
**Orden de trabajo** → **Folio BPA** → **Nombre compuesto** (sólo lectura) →
*Nombre histórico* (visible sólo si existe) → Semana → Temporada.

- Lista: `ot_number`, `name`, `date`, `week_number`, `folio`, `bpa_folio`, …
- Búsqueda: `name` (dominio combinado nombre/Número OT/Orden de trabajo),
  `ot_number`, `folio`, `bpa_order_id`, `bpa_folio`, …
- El bloque introductorio `o_steps_record_intro` aparece **una sola vez**
  (verificado sobre el arch resuelto: `form_intro_blocks = 1`).
- El logo moderno se mantiene: el menú raíz *Maquinaria* usa
  `step_operations_ui,static/description/icon_machinery.png`
  (sha256 `580c4ea5…`, idéntico en Desarrollo y Demo). No hay rastro del logo
  `JE` en assets, manifiestos, menús ni adjuntos.

## 7. Compatibilidad revisada

- `step.hrs.machinery.line.name_parent` (related a `name`) sigue funcionando.
- `account.move.ref` y el concepto de cada apunte siguen usando `name`, ahora
  compuesto y estable tras contabilizar.
- Dashboard de `step_operations_ui` lee `name`: sin cambios necesarios.
- No existe ningún consumidor de `step.hrs.machinery` en `step_tracker_odoo`
  ni en `step_hr`; el contrato RPC queda cubierto por pruebas.
- El `onchange` de BPA ya **no** pisa `folio`: la OT-BPA sólo aporta fundo y
  empresa.

## 8. Archivos modificados

```
step_machinery/__manifest__.py                          18.0.19.0.1 -> 18.0.20.0.0
step_machinery/models/step_hrs_machinery.py
step_machinery/data/ir_sequence.xml
step_machinery/views/step_hrs_machinery_view.xml
step_machinery/migrations/18.0.20.0.0/post-migrate.py   (nuevo)
step_machinery/tests/__init__.py
step_machinery/tests/test_costing.py
step_machinery/tests/test_ot_naming.py                  (nuevo)
step_bpa_irrigation/__manifest__.py                     18.0.2.1.1 -> 18.0.2.2.0
step_bpa_irrigation/models/machinery_integration.py
step_bpa_irrigation/views/bpa_machinery_views.xml
step_bpa_irrigation/migrations/18.0.2.2.0/post-migrate.py (nuevo)
step_bpa_irrigation/tests/__init__.py                   (nuevo)
step_bpa_irrigation/tests/test_machinery_naming.py      (nuevo)
```

`step_agricultural_access` y `step_operations_ui` no se modificaron.

## 9. Respaldos verificados

Ubicación `/opt/backups/maquinaria_20260828/`:

| Archivo | Validación | SHA-256 |
|---|---|---|
| `LAB_TAREAS_20260828.dump` | `pg_restore --list` → 29 869 entradas | `65a8564122799216876707bcfd531730e9377c6d112b7ee05221eb6c2f5d01cd` |
| `STEPS_DEMO_20260828.dump` | `pg_restore --list` → 29 339 entradas | `a17bfb67660ee23c88294c32ce86da1145a42114516b1fd659561b09fc56a770` |
| `dev_addons_maquinaria_20260828.tgz` | `tar -tzf` → 130 archivos | `a9866fa7ce1d59f7a685a559b50bbd32df2d9eb82e8a11da924d90fdadfe0ff9` |
| `demo_addons_maquinaria_20260828.tgz` | `tar -tzf` → 130 archivos | `4571c08900234a56c6e57e516b5db8f97b15b94a07aeadbc08c4bde4195c0ad6` |

## 10. Pruebas

Ejecutadas en una base desechable `MAQ_TEST_20260828` (creada e instalada desde
cero y eliminada al terminar) para no dejar datos ni consumir secuencias en las
bases funcionales.

```
0 failed, 0 error(s) of 25 tests
step_machinery: 22 tests / step_bpa_irrigation: 9 tests
```

Cobertura frente a las 14 pruebas mínimas del encargo: crear sin `name`;
correlativos consecutivos y sin duplicados; nombre igual al ejemplo funcional;
nombre sin Orden de trabajo; nombre sin Folio BPA; cambio de fecha/OT/BPA antes
del costeo; identidad congelada tras costear; copia con nuevo correlativo; dos
empresas sin colisiones; creación por RPC con `name` heredado; migración
idempotente; costeo $334 y costo HrMq $167; comprobante balanceado; dominio BPA
sólo para órdenes ingresadas de la empresa correcta.

## 11. Estado final de los ambientes

| | Desarrollo | Demo |
|---|---|---|
| URL | https://desarrollo.stepsapp.cl (HTTP 200) | https://demo.stepsapp.cl (HTTP 200) |
| Base | LAB_TAREAS | STEPS_DEMO |
| Servicio | `odoo18-dev.service` activo | `odoo18-demo.service` activo |
| `step_machinery` | 18.0.20.0.0 | 18.0.20.0.0 |
| `step_bpa_irrigation` | 18.0.2.2.0 | 18.0.2.2.0 |
| `step_agricultural_access` | 18.0.2.1.0 | 18.0.2.1.0 |
| `step_operations_ui` | 18.0.2.0.2 | 18.0.2.0.2 |
| SHA-256 `step_machinery` | `a964185a5e96b5e587fe26446d956945b345ddf4c02c5c86dc86f89415ad0f0d` | idéntico |
| SHA-256 `step_bpa_irrigation` | `918432d35e72129f75ed2ac49dac39d5c8737d1d77135b28c444dd4dbc9b59e6` | idéntico |

El árbol local `C:\Users\tito4\Documents\Odoo` coincide archivo por archivo con
ambos servidores.

## 12. Pendientes reales (no introducidos por este cambio)

1. **Diario de maquinaria mal configurado en ambas bases.** El diario `CDMaq`
   tiene *Cuentas permitidas* limitado a `110220 Acciones`, mientras que los
   ocho conceptos usan `410161` (cargo) y `210233` (abono). `Contabilizar`
   falla con "no puede usar esta cuenta en este diario". Solución: vaciar esa
   lista en el diario o agregar las cuentas 410161 y 210233. Es configuración
   contable, no se modificó.
2. **`steps_api` figura instalado** en LAB_TAREAS y STEPS_DEMO pero su código no
   está en ningún `addons_path`; el arranque registra el aviso "Some modules are
   not loaded". Es previo (se repite desde al menos el 27-08).
3. **`steps_qa`** tiene `step_machinery 18.0.18.0` instalado y es alcanzable por
   el servicio de Desarrollo (`list_db = True`, `dbfilter` vacío). Ya estaba
   desalineado con el código en disco antes de este trabajo; no es un ambiente
   autorizado y no se tocó.
4. **Validación en navegador** pendiente de captura visual: la pestaña
   automatizada quedó en una ventana de Chrome en segundo plano, donde
   `requestAnimationFrame` no se dispara y el cliente OWL nunca monta
   (`rootStatus = 1`). Las llamadas RPC del cliente sí responden 200. La
   validación equivalente se hizo del lado servidor sobre el arch resuelto de
   las vistas y sobre datos reales en transacción con rollback.
