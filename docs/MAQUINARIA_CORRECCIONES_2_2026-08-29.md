# Maquinaria — Correcciones 2 (29-08-2026)

Distribución analítica del comprobante contable de horas máquina.

`step_machinery 18.0.21.0.0` → **`18.0.22.0.0`**.

## 1. Lo pedido

> En la contabilización de las horas máquina, al generar el comprobante
> contable, se debe modificar la Distribución Analítica. […] Temporada: está
> definida en el encabezado del formulario. Centro de costos: está Ok.
> Actividad: en el formulario de horas máquina está definida en la línea de
> detalle, campo «actividad». Nota: la cuenta de pasivo no lleva cuenta
> analítica, sólo las cuentas de gastos.

Los planes analíticos de la empresa, idénticos en Demo y Desarrollo:

| id | Plan |
|---|---|
| 2 | Temporada |
| 3 | Centro de costos |
| 4 | Actividad |

## 2. Hallazgos, causa y solución

| # | Hallazgo | Causa | Solución |
|---|---|---|---|
| 1 | En el cargo aparecía «4 Exportaciones» en vez de la actividad *Aplicaciones* | `action_conta` repartía por `line.actividad_id`, que es un registro **`step.actividad`**, no una cuenta analítica. El id del maestro (4 = Cosecha) se usó como id de cuenta analítica (4 = Exportaciones) | Se reparte por `line.actividad_id.cost_id`, la cuenta analítica del maestro |
| 2 | La Temporada no llegaba al apunte | El campo tomado (`temp_id.cost_id`) es el correcto, pero en Demo la temporada **T26-27** no tenía cuenta analítica configurada y no existía la cuenta en el plan Temporada | Migración `18.0.22.0.0`: vincula la cuenta existente por nombre y crea la que falta |
| 3 | El abono a la cuenta de pasivo `210233` llevaba analítica (el centro de costos de la maquinaria) | `action_conta` calculaba una `credit_distribution` a partir de `machinery_ids.cost_id` | El abono va sin distribución analítica |
| 4 | Mismo defecto del punto 1 en `real.cost.machinery.action_conta` (costo real) | Código heredado con el mismo `str(line.actividad_id.id)` | Se corrige igual, y el abono queda sin analítica |
| 5 | *(hallado al revisar los datos)* En Desarrollo hay 22 líneas históricas cuyo «Centro de costos» apunta al plan **Project** y 4 al plan **Temporada** | Captura anterior sin el plan acotado | Odoo rechaza dos cuentas del mismo plan raíz en una distribución. `_distribution()` ahora descarta la cuenta que repite plan —gana la primera, es decir la temporada del encabezado— en vez de reventar la contabilización |

## 3. Cómo queda el asiento

Para el registro del ejemplo (OT 23, 29/08/2026, temporada T26-27, centro de
costos *Arándanos Brigitta 2019*, actividad *Aplicaciones*):

| Cuenta | D/H | Distribución analítica |
|---|---|---|
| `410161` Costo estándar maquinarias | Debe | `T26-27` + `Arándanos Brigitta 2019` + `Aplicaciones` — 100 % |
| `210233` Provisión costo maquinarias | Haber | *(sin distribución analítica)* |

La clave de `analytic_distribution` es `"<temporada>,<centro>,<actividad>": 100.0`:
un segmento por plan, que es como Odoo 18 representa una distribución
multiplán al 100 %.

Si alguno de los tres maestros no tiene cuenta analítica configurada, ese
segmento simplemente no se agrega; el asiento se genera igual y los otros dos
segmentos quedan correctos.

## 4. Cambios en el código

| Archivo | Cambio |
|---|---|
| `models/step_hrs_machinery.py` | Nuevo `_debit_analytic_distribution()`; el abono va sin analítica |
| `models/real_cost_machinery.py` | Nuevo `_analytic_distribution()`; misma corrección en el flujo de costo real |
| `hooks.py` | Nuevo `ensure_analytic_masters()`, llamado también desde `post_init_hook` |
| `migrations/18.0.22.0.0/post-migrate.py` | Ejecuta `ensure_analytic_masters()` sobre bases existentes |
| `tests/test_accounting.py` | Tres pruebas nuevas en reemplazo de la genérica anterior |

`ensure_analytic_masters()` es idempotente y **conservador**: sólo toca los
maestros que no tienen cuenta analítica. A los que ya la tienen no los
reasigna —aunque el nombre no calce— porque eso cambiaría analítica ya
contabilizada; los registra en el log bajo `revisar`.

## 5. Pruebas

`step_machinery/tests/test_accounting.py`:

- `test_debit_distribution_uses_the_three_analytic_plans`: el cargo reparte
  exactamente por Temporada + Centro de costos + Actividad al 100 %.
- `test_activity_uses_its_analytic_account_not_its_own_id`: la regresión
  corregida — el id del maestro `step.actividad` **no** aparece en la
  distribución; sí su cuenta analítica.
- `test_repeated_plan_does_not_break_posting`: un centro de costos histórico
  mal clasificado en el plan Temporada no bloquea la contabilización.
- `test_liability_line_carries_no_analytic_distribution`: el abono al pasivo
  queda sin analítica.

## 6. Despliegue

| Ambiente | Base | `step_machinery` | Servicio | HTTP |
|---|---|---|---|---|
| Desarrollo | `LAB_TAREAS` | `18.0.22.0.0` instalado | `odoo18-dev.service` activo | `https://desarrollo.stepsapp.cl/web/login` → 200 |
| Demo | `STEPS_DEMO` | `18.0.22.0.0` instalado | `odoo18-demo.service` activo | `https://demo.stepsapp.cl/web/login` → 200 |

Producción no se tocó: `step_machinery` figura **desinstalado** en
`karo_consultorias`, así que el cambio de código no la afecta pese a que
`/opt/dev_odoo18/odoo_agriculture` está en su `addons_path`.

Respaldo previo (dumps de ambas bases y tar de ambos módulos):

```
/opt/fernando_odoo18/backups/maquinaria-correcciones2-20260829-235627
├── LAB_TAREAS.dump
├── STEPS_DEMO.dump
├── step_machinery.dev.rsync-dry-run.txt
├── step_machinery.demo.rsync-dry-run.txt
└── modules/
    ├── step_machinery.dev.tar.gz
    └── step_machinery.demo.tar.gz
```

El `dry-run` de ambos ambientes mostró exactamente seis archivos modificados y
un directorio nuevo (`migrations/18.0.22.0.0/`), sin borrados ni archivos
ajenos al módulo.

### Log de la migración

Desarrollo — todas las temporadas ya tenían cuenta analítica, nada que crear:

```
revisar: ['step.temporada T24-25 -> T25-26',
          'step.actividad Mantención de campo -> Mantención del campo',
          'step.actividad Labores en verde -> Poda',
          'step.actividad Labores generales -> [01777001] Administración']
```

Demo — faltaba la cuenta de la temporada vigente:

```
creadas: ['step.temporada T26-27 -> T26-27']
revisar: ['step.temporada T24-25 -> T2526', … (los mismos tres de actividad)]
```

## 7. Evidencia funcional

Flujo completo (crear → costear → contabilizar) ejecutado en ambas bases
dentro de una transacción revertida, así que **no quedó ningún registro ni
comprobante nuevo**. Resultado idéntico en Demo y Desarrollo:

```
comprobante  | diario: Costeo Maquinarias
  410161  Costo estándar maquinarias   D=34.272,00  H=0,00
          T26-27 [plan Temporada] + [01777001] Administración [plan Centro de
          costos] + Poda [plan Actividad] = 100,0 %
  210233  Provisión costo maquinarias  D=0,00       H=34.272,00
          (sin distribución analítica)
```

Pruebas automatizadas sobre base desechable `MAQ_TEST_20260829`, creada e
instalada desde cero y **eliminada al terminar**:

```
step_machinery: 49 tests
0 failed, 0 error(s)
```

## 8. Pendientes para el cliente

1. **`step.actividad` «Labores en verde» apunta a la cuenta analítica
   «Poda»**, y «Labores generales» a «[01777001] Administración». La migración
   **no** las reasigna a propósito —cambiarlas movería analítica ya
   contabilizada—, pero conviene revisarlas: mientras sigan así, esas
   actividades cargan a la cuenta equivocada.
2. **Temporada «T24-25» apunta a la cuenta «T25-26»** en ambos ambientes
   (en Demo, a «T2526»). Mismo criterio: se reporta, no se toca.
3. En Desarrollo hay **22 líneas históricas** cuyo «Centro de costos» es una
   cuenta del plan *Project* y **4** del plan *Temporada*. Ya no bloquean la
   contabilización, pero su analítica no es la que corresponde.
4. El registro **OT 23** de Desarrollo (`step.hrs.machinery` id 37) —el del
   documento de correcciones— ya está contabilizado con la distribución
   anterior. Su comprobante (`account.move` id 270) sigue en **borrador**, así
   que puede rehacerse si se quiere ver la corrección sobre ese mismo
   registro; no se modificó por tratarse de un asiento contable existente.
