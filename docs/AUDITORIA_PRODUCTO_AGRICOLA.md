# Auditoría de producto — módulos agrícolas Steps

Fecha de auditoría: **2026-08-21**
Rama: `codex/web-tracker-redesign`
Entorno auditado: **Desarrollo** (`LAB_TAREAS`, `https://desarrollo.stepsapp.cl`)
Alcance: inspección de código versionado + inspección de solo lectura de la base
de Desarrollo (Odoo shell, sin `commit()`).

---

## 1. Inventario

### 1.1 Módulos versionados en este workspace

| Módulo | Versión | App | Modelos propios | Observación |
|---|---|:--:|---:|---|
| `step_hr` | 18.0.1.2.1 | sí | ~45 | Núcleo: maestros agrícolas, actividades/tarjas, movilización, Tracker |
| `step_cosecha` | 18.0.1.5.1 | sí | 10 | Cosecha, recepción, procesos, historial |
| `step_bpa_irrigation` | 18.0.1.0.2 | sí | **0** | Solo dashboard + capa visual sobre modelos Studio |
| `step_qa` | 18.0.1.0.1 | sí | **0** (1 herencia) | Dashboard + capa visual; datos en `quality.check` y Studio |
| `step_labor_protection` | 18.0.1.0.1 | sí | 4 | Ley Karin nativo; EPP/cursos/riesgos en Studio |
| `step_management_costs` | 18.0.1.1.0 | sí | 12 | Presupuestos, planificación, costos históricos |
| `step_agricultural_access` | 18.0.1.1.0 | no | 0 | 11 grupos de aplicación + 45 permisos funcionales |
| `step_accounting_multicurrency` | 18.0.1.0.0 | no | 0 (1 herencia) | Presentación multimoneda de informes |
| `step_operations_ui` | 18.0.1.0.0 | no | 0 | Portadas Maquinaria/Fletes |
| `step_tracker_odoo` | 18.0.1.0.0 | sí | 10 | **Desinstalado** en Dev y Demo |

### 1.2 Módulos presentes en el servidor y **no versionados aquí**

Detectados en `/opt/dev_odoo18/odoo_agriculture` e instalados en `LAB_TAREAS`:

- `step_machinery` (18.0.18.0) — **instalado**, extendido por `step_operations_ui`
- `step_apr`, `step_hr_liquido`, `step_expire_database`, `steps_api` — instalados
- `step_agro`, `step_pos_preorder` — desinstalados
- Terceros: `agriculture_management_odoo`, `agri_inventory`, `blue_jt_cost_centers`,
  `l10n_cl_*`, etc.

> **Riesgo estructural.** Cinco módulos `step_*` corren en Desarrollo sin estar en
> Git. Cualquier cambio en ellos es irrecuperable y no auditable.

### 1.3 Superficie Odoo Studio

En `LAB_TAREAS` existen **~90 modelos `x_*`**, de los cuales ~50 son de primera
clase. Los dominios agrícolas que viven **completamente** en Studio son:

| Dominio | Modelos Studio principales |
|---|---|
| BPA / fitosanitario | `x_aplicacion_foliar`, `x_objetivo_o_plaga`, `x_sustancia_activa` (659 reg.), `x_aptitud_plaguicidas`, `x_tipo_de_aplicaciones`, `x_forma_de_aplicacion`, `x_estado_fenologico`, `x_cuaderno_de_campo` |
| Riego | `x_riego_y_fertilizacio`, `x_sector_de_riego`, `x_informe_de_riego`, `x_informe_de_fertiliza` |
| Monitoreo | `x_monitoreo_agricola` |
| Planificación cosecha | `x_planificar_cosecha`, `x_pronostico_cosecha`, `x_plantilla_agricola`, `x_curva_calibres` |
| Postcosecha | `x_recepcion_en_acopio`, `x_procesos_post_cosech`, `x_repaletizado`, `x_control_de_temperatu`, `x_calibre_de_fruta`, `x_categoria_de_fruta` |
| Fletes | `x_orden_de_flete`, `x_tarifa_de_fletes`, `x_tramo_de_flete`, `x_rastreo_camiones` |
| Protección laboral | `x_accidentes_laborales`, `x_entrega_epp`, `x_grupo_epp`, `x_riesgos_laborales`, `x_inducciones_y_cursos` |
| QA | `x_inspecciones_interna`, `x_asesor_externo`, `x_control_de_calidad_c`, `x_fumigacion` |

**15 automatizaciones (`base.automation`) activas — todas asignan folio.** No
existe ni una sola automatización de negocio: nada calcula, alerta, valida ni
bloquea.

**Crons:** los dos únicos crons `step_*` (`step_apr`, sincronización Tracker)
están **inactivos**. El producto no tiene procesos de fondo.

### 1.4 Volumen de datos en Desarrollo

```
step.fundo 2      res.sector 1       step.temporada 3     step.especie 8
step.variedad 11  step.grupo.variedad 9                   step.labor 6
step.actividad 9  account.analytic.account 23             step.cuartel.line 16
step.hilera.line 9                    step.tarja 72       step.tarja.line 108
step.cosecha.registry 14              step.cosecha.recepcion 0
step.cosecha.proceso 0                step.movi.registry 7
hr.salary.custom 21                   quality.check 1
step.management.operational.budget 1  hr.employee 13      fleet.vehicle 18
product.template 1480                 x_sustancia_activa 659
x_aplicacion_foliar 4                 x_riego_y_fertilizacio 3
x_monitoreo_agricola 2                x_registro_cosecha 2
x_cuaderno_de_campo 0
```

En Demo (`STEPS_DEMO`) los maestros compartidos existen (1480 productos,
16 cuarteles) y las tablas transaccionales están en 0.

---

## 2. Mapa de datos compartidos y fuente de verdad

| Entidad | Fuente de verdad actual | Consumidores | Problema |
|---|---|---|---|
| Predio/Fundo | `step.fundo` | tarja, cosecha, BPA (`x_studio_fundo`), riego | OK, pero sin `active`, sin geolocalización, sin superficie coherente (4 campos `hec_*` `Integer` sueltos) |
| Sector | `res.sector` (**geográfico**: región/comuna) y `x_sector_de_riego` (**agronómico**) | fundo / BPA | **Dos conceptos distintos con el mismo nombre.** `res.sector` no es un sector productivo |
| Cuartel | `step.cuartel.line` (línea `One2many` de `account.analytic.account`) | cosecha (`cuartel_id`), BPA (línea maquinaria) | **No es un maestro de primera clase**: sin `company_id`, sin `active`, sin código único, sin especie/variedad propia (se heredan del centro de costo) |
| Hilera | `step.hilera.line` | — | Se captura y **nadie la consume** |
| Centro de costo | `account.analytic.account` (extendido) | todo | Correcto y bien reutilizado. Concentra especie, variedad, has, fechas de plantación/producción/cosecha |
| Especie / Variedad / Grupo variedad | `step.especie`, `step.variedad`, `step.grupo.variedad` | tarifas, cosecha, BPA | OK. `step.especie` arrastra código muerto copiado de `res.partner` (`_compute_avatar_*`, `is_company`, `type`) que no existen en el modelo |
| Temporada | `step.temporada` | costeo (`action_conta`) | Se resuelve por rango de fechas en cada contabilización; sin unicidad ni validación de solapamiento |
| Labor | **`step.labor` Y `product.template`** (`is_labor`, `cod_labor`, `grupo_labor`, `met_costeo` duplicados) | tarja y cosecha usan `product.template`; `step.labor` casi no se usa (6 registros) | **Duplicidad real de maestro.** `step.labor` es huérfano |
| Actividad | `step.actividad` **y** `account.analytic.account` (`actividad_id` en producto) | tarja, costeo | Duplicidad conceptual |
| Producto fitosanitario | `product.template` (`dia_carencia`, `hrs_reingreso`, `x_studio_das_carencia_*`, `x_studio_sustancia_activa`, `x_studio_vencimiento_autorizacin`) | **nadie** | Ver §4.1 |
| Trabajador | `hr.employee` | tarja, cosecha, BPA, EPP | OK |
| Maquinaria | `fleet.vehicle` + `step_machinery` | BPA, actividades, Tracker | OK, pero `step_machinery` no versionado |

### 2.1 Flujo punta a punta — actual vs. objetivo

**Actual** (las flechas punteadas son saltos que hoy el usuario cubre a mano):

```
Planificación (x_planificar_cosecha, Studio)
   ⇢ preparación            (no modelado)
   ⇢ siembra/plantación     (solo fechas sueltas en el centro de costo)
   ⇢ manejo del cultivo     (x_monitoreo_agricola, sin consecuencia)
   → labores                (step.tarja + step.tarja.line)          ✔ costea
   ⇢ insumos                (x_aplicacion_foliar líneas, sin stock)
   → cosecha                (step.cosecha.registry)                 ✔ costea
   ⇢ calidad                (quality.check / Studio, sin vínculo a cosecha)
   ⇢ postcosecha            (step.cosecha.proceso, 0 registros)
   ⇢ inventario/destino     (stock.picking parcial)
   → costos                 (asientos analíticos)                   ⚠ ver §4.3
   ⇢ indicadores            (dashboards descriptivos)
```

**Ninguna etapa impone una condición sobre la siguiente.** El sistema registra;
no controla.

**Objetivo mínimo de producto:** que cada etapa deje un *estado* que la siguiente
consulte — empezando por la única que es obligación legal: **carencia y
reingreso**.

---

## 3. Referencias externas consultadas

| Fuente | Qué aporta | Consultada |
|---|---|---|
| SAG — [Registro de plaguicidas y fertilizantes](https://www.sag.gob.cl/temas-normativas/registro-de-plaguicidas-y-fertilizantes) | Marco de autorización de plaguicidas en Chile | 2026-08-21 |
| SAG — [Actualización Resolución N°243 sobre plaguicidas](https://www.sag.gob.cl/noticias/sag-y-sector-privado-acuerdan-actualizacion-de-la-resolucion-ndeg243-sobre-plaguicidas) | **Hecho:** obliga a registrar cada aplicación en cuaderno de campo con nombre del plaguicida, lote, fecha y hora, y **periodo de reingreso** a la zona tratada | 2026-08-21 |
| SAG — [Borrador resolución obligaciones de uso de plaguicidas](https://www.sag.gob.cl/sites/default/files/Borrador_Resolucion_Obligaciones_Uso_Plaguicidas_para_CP_11_04_2024.pdf) | **Hecho:** define *carencia* (tiempo entre última aplicación y cosecha, según etiqueta) y *reingreso* (tiempo hasta poder entrar sin EPP, según etiqueta) | 2026-08-21 |
| GLOBALG.A.P. — [IFA para frutas y hortalizas](https://globalgap.org/what-we-offer/solutions/ifa-fruit-and-vegetables/) y [General Regulations v6](https://documents.globalgap.org/documents/220929_GG_GR_Rules_for_plants_v6_0_Sep22_en.pdf) | **Recomendación:** el módulo de productos fitosanitarios de IFA v6 exige registro y trazabilidad de aplicaciones; el detalle de los P&C requiere el estándar oficial | 2026-08-21 |

**Inferencia propia (no es hecho citado):** en fruta de exportación chilena la
carencia relevante suele ser la del **mercado de destino** (UE/USA), habitualmente
más restrictiva que la de etiqueta. Por eso el maestro de producto ya tiene
`x_studio_das_carencia_ue` / `_usa` / `_mayor`, y por eso el criterio debe ser
**configurable** y su valor por defecto el más conservador.

---

## 4. Hallazgos

### 4.1 Hallazgo mayor — la trazabilidad fitosanitaria se captura y se descarta

Es el hallazgo central de esta auditoría.

**El dato existe, completo y de buena calidad:**

- `product.template.dia_carencia` (Integer) y `product.template.hrs_reingreso`
  (Float) — nativos, definidos en `step_hr/models/product_template.py:31-32`.
- `product.template.x_studio_das_carencia_mayor` / `_ue` / `_usa` (Integer).
- `product.template.x_studio_sustancia_activa` → `x_sustancia_activa`
  (**659 sustancias cargadas**), `x_studio_aptitud_plaguicida`,
  `x_studio_mximo_veces_a_aplicar`, `x_studio_primera_autorizacin`,
  `x_studio_vencimiento_autorizacin`, `x_studio_titular_autorizacin`.
- `x_aplicacion_foliar` registra fecha, fundo, especie, objetivo/plaga, tipo y
  forma de aplicación, condiciones meteorológicas (viento, humedad, T°), litros
  de mezcla, costos y responsables.
- `x_aplicacion_foliar_line_6808a` registra el **producto aplicado**, su
  sustancia activa, dosis, y trae por `related` las cuatro carencias.
- `x_aplicacion_foliar_line_2f222` registra el **cuartel** intervenido
  (`x_studio_cuartel` → `step.cuartel.line`, almacenado), hectáreas aplicadas,
  máquina, implemento, horómetros y aplicador.
- `step.cosecha.registry` registra `cuartel_id`, `fundo_id`, `variedad_id` y
  `date`.

**Y no se usa en ninguna parte.** Búsqueda sobre todo el código versionado:

```
grep -rin "carencia|reingreso" step_*/
→ product_template.py:31,32   (definición del campo)
→ product_template_views.xml:51,52  (se pinta en el formulario)
```

Dos definiciones y dos etiquetas de formulario. **Cero reglas de negocio.**

Consecuencias concretas hoy:

1. El sistema **no puede responder** "¿puedo cosechar este cuartel hoy?".
   `action_apro()` de `step.cosecha.registry`
   ([step_cosecha_registry.py:345](../step_cosecha/models/step_cosecha_registry.py))
   solo valida que el estado sea `in`.
2. El sistema **no puede responder** "¿puede entrar personal sin EPP a este
   cuartel?" pese a que el reingreso es exigido explícitamente por SAG.
3. Un incumplimiento de carencia — rechazo de embarque, pérdida de
   certificación, multa — es hoy **indetectable dentro del ERP**.
4. Los datos de Desarrollo ya contienen el caso: aplicación `BPA202600001`
   (2026-02-02, glifosato, carencia etiqueta 7 / mayor 9 / UE 6 / USA 5) sobre
   el cuartel `C01 Crunch 18`; y tres cosechas del mismo cuartel el 2026-02-17.
   Nadie cruzó jamás esos dos hechos.

Esta es la diferencia más nítida entre "demo de agricultura sobre Odoo" y
producto: el producto **impide** la operación ilegal, la demo la registra.

### 4.2 Hallazgo — BPA y riego no tienen módulo

`step_bpa_irrigation` declara `"application": True` y no contiene ni un solo
modelo Python: son 3 archivos de vistas que inyectan clases CSS sobre vistas
Studio, más un dashboard de conteos.

Su `__manifest__.py` no declara `studio_customization` como dependencia pese a
que `views/bpa_studio_layout_views.xml` referencia XML IDs de ese módulo
(`studio_customization.default_form_view_fo_1025eed1-…`).

> **Corrección de esta auditoría.** El diagnóstico inicial fue que faltaba la
> dependencia. Es incorrecto: `studio_customization` **no tiene directorio en
> disco** (`get_module_path()` devuelve `False`; sus datos viven en la base).
> Declararlo como dependencia lo vuelve una dependencia no satisfecha y deja el
> módulo sin cargar — se comprobó en Desarrollo y se revirtió. Los `ref()` a sus
> XML IDs se resuelven contra `ir.model.data` en tiempo de ejecución sin
> necesidad de la dependencia. **No hay nada que corregir aquí**; el
> acoplamiento real a Studio es de fondo, no de manifiesto.

### 4.3 Hallazgo — el costeo de tarjas propias produce analítica incorrecta

En `step_hr/models/step_tarja.py`, `action_conta()`:

- **Variable de bucle filtrada.** Los asientos de sueldo/seguro/feriado/IAS usan
  `line.cost_id` y `line.labor_id` fuera del `for line in salary.tarja_line`
  ([step_tarja.py:305-330](../step_hr/models/step_tarja.py)). Toma el centro de
  costo de **la última línea** y lo aplica al total de la tarja. Con la tarja sin
  líneas, es `NameError`.
- **Clave analítica inválida.** Se escribe
  `str(line.labor_id.actividad_id.id)` como componente de
  `analytic_distribution`. `actividad_id` en `product.template` sí es
  `account.analytic.account`, pero la versión comentada inmediatamente encima usa
  `.actividad_id.cost_id.id` — el código vivo y el comentado no concuerdan y no
  hay validación de que las claves sean cuentas analíticas existentes.
- **Totales mal acumulados.** `total_debito += round(total_seguro, 4)` se repite
  para feriado y para IAS (copiar-pegar). El débito acumulado no cuadra.
- **Sin idempotencia.** Pulsar "Contabilizar" dos veces crea dos asientos.
  `step_cosecha` sí protege esto (`if salary.invoice_id: raise`); `step_hr` no.
- **`work_entry_type_id` hardcodeado a `1` y `2`** (`envio_nomina`), contra la
  regla de no usar IDs numéricos.
- `action_pag()` escribe `state='pag'`, valor **eliminado del `Selection`**.

### 4.4 Hallazgo — `step.tarja.line._compute_total_hrs` es no determinista

`step_hr/models/step_tarja_line.py`:

- `@api.depends('hrs','hrs_extra','quantity','tarifa')` con ~15 campos
  almacenados que dependen además de `contract_id`, `tarja_id.date`,
  `tarja_id.pricelist_id` y de 6 parámetros de `res.company`. Los valores
  almacenados quedan obsoletos ante cualquier cambio de tarifa o contrato.
- El cómputo **asigna `tarifa`, que está en su propio `@api.depends`**.
- `hoy = date.today()` decide el día de la semana usado para `sab_dom` y para la
  jornada del contrato: **recalcular en otra fecha da otro resultado**. Debería
  usar `move.tarja_id.date`.
- Cuando `tarja_id.state == 'conta'` el método **no asigna ningún campo**, lo que
  en Odoo 18 provoca `ValueError: Compute method failed to assign`.
- `0.00777777` como constante mágica del valor de la hora extra.

### 4.5 Otros hallazgos

| # | Hallazgo | Ubicación |
|---|---|---|
| 0 | **`UserError` usado en 26 puntos sin importarlo.** Toda validación de negocio de Cosecha (aprobar, costear, contabilizar, recepcionar) fallaba con `NameError` y mostraba «Ocurrió un error» genérico en lugar del mensaje. Detectado al validar el corte; **corregido** en esta entrega | `step_cosecha/models/step_cosecha_registry.py` |
| a | `step.labor` (maestro de labores) está huérfano: tarjas y cosechas usan `product.template` | `step_hr/models/step_labor.py` |
| b | `step.hilera.line` se captura y nadie la consume | `step_hr/models/step_hilera_line.py` |
| c | `step.especie` hereda métodos de avatar de `res.partner` con `@api.depends` sobre campos inexistentes (`user_ids.share`, `is_company`, `type`) | `step_hr/models/step_especie.py:63-96` |
| d | `step_hr/models/step_cosecha_*.py` son copias muertas de los modelos de `step_cosecha` (comentadas en `__init__.py`) | `step_hr/models/` |
| e | `generate_report_per_worker()` es código muerto: escribe en un campo `file` inexistente y retorna `res_model: 'step_tarja'` | `step_tarja.py:434-688` |
| f | `step.cuartel.line` sin `company_id`: la regla multiempresa de cosecha no alcanza al cuartel | `step_hr/models/step_cuartel_line.py` |
| g | ACL de `step_hr` concede CRUD completo a `base.group_user` en 50 modelos; la segregación real vive solo en menús | `step_hr/security/ir.model.access.csv` |
| h | `step_tracker_odoo` redefine los mismos `_name` que `step_hr` (`step.tracker*`). Hoy no colisiona porque está desinstalado; instalarlo fusionaría ambas definiciones | `step_tracker_odoo/models/` |
| i | Los dos crons del producto están inactivos | `ir.cron` en `LAB_TAREAS` |
| j | `steps_api` y `studio_customization` están instalados pero sin directorio en disco; Odoo registra en cada arranque `Some modules are not loaded … ['steps_api']` | `LAB_TAREAS` y `STEPS_DEMO` |
| k | `step.tarja.cost.line` mezcla campos computados almacenados y no almacenados en un mismo método; Odoo advierte que leer `employee_id_domain` puede recomputar y escribir `cost_id_domain` y `trato_total` | `step_hr/models/step_tarja_cost_line.py` |
| l | `step_cosecha_registry.product_uom_id` es `required=True` pero hay filas históricas con `NULL`: Odoo no puede aplicar la restricción (`unable to set NOT NULL`) en cada actualización | `step_cosecha` |

---

## 5. Matriz de mejoras

| Proceso | Implementación actual | Problema real | Mejora propuesta | Impacto | Riesgo | Esfuerzo | Dependencias |
|---|---|---|---|:--:|:--:|:--:|---|
| **Fitosanitario → cosecha** | Aplicación y carencia se registran; cosecha las ignora | Se puede cosechar dentro de carencia sin que el ERP lo note. Incumplimiento SAG / GLOBALG.A.P. | **Restricciones de carencia y reingreso por cuartel**, calculadas desde las aplicaciones, con estado en el registro de cosecha y bloqueo/advertencia configurable al aprobar | **Alto** | Bajo | M | `step_cosecha`, `step_bpa_irrigation`, Studio (lectura defensiva) |
| **Reingreso a zona tratada** | `hrs_reingreso` en producto, sin uso | Personal puede entrar sin EPP a un cuartel tratado | Misma restricción, dimensión horaria + tablero "cuarteles con reingreso vigente" | **Alto** | Bajo | S | ídem |
| Costeo tarja propia | `action_conta()` | Analítica tomada de una línea arbitraria, débito descuadrado, sin idempotencia | Reescribir el asiento por línea, validar cuadratura y bloquear doble contabilización | Alto | **Alto** (toca asientos históricos) | M | `step_hr`, `account` |
| Cálculo de remuneración de tarja | `_compute_total_hrs` | Resultado depende del día en que se recalcula | Corregir `@api.depends`, usar la fecha de la tarja, no asignar `tarifa` dentro del cómputo | Alto | **Alto** (recalcula 108 líneas históricas) | M | `step_hr` |
| Maestro de labores | `step.labor` vs `product.template` | Doble maestro; `step.labor` huérfano | Declarar `product.template` fuente de verdad y convertir `step.labor` en catálogo de referencia o migrarlo | Medio | Medio | M | `step_hr` |
| Cuartel | Línea del centro de costo | No es maestro: sin empresa, sin código único, sin superficie confiable | Promover a modelo con `company_id`, `active`, código único y superficie validada, con puente de compatibilidad | Alto | **Alto** (migración de datos) | L | `step_hr`, `step_cosecha`, Studio |
| BPA / riego | 100 % Studio | Sin reglas, sin versión, sin pruebas | Migración gradual a módulo nativo, empezando por los campos que sostienen reglas | Alto | Alto | XL | Studio |
| Cuaderno de campo | `x_cuaderno_de_campo` (0 registros) | Obligación SAG sin implementar | Generarlo desde aplicaciones + restricciones ya calculadas | Alto | Bajo | M | corte de carencia |
| Módulos no versionados | 5 módulos `step_*` fuera de Git | Cambios irrecuperables | Incorporar `step_machinery` y hermanos al repo | Medio | Bajo | M | — |
| ACL | CRUD a `base.group_user` | Segregación solo visual | Reasignar ACL a los grupos granulares ya existentes | Medio | **Alto** (puede quitar accesos) | L | `step_agricultural_access` |
| Crons | Inactivos | Sin procesos de fondo | Activar sincronización Tracker y agregar refresco de restricciones | Bajo | Bajo | S | — |

---

## 6. Priorización (Fase B)

Puntuación 1-5. Total = valor + doble digitación + trazabilidad + decisiones +
reutilización − migración − riesgo operacional.

| Iniciativa | Valor | Anti-doble-digitación | Trazabilidad | Decisiones/costos | Reutiliza arquitectura | Migración | Riesgo | **Total** |
|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| **Carencia y reingreso** | 5 | 5 | 5 | 4 | 5 | 1 | 1 | **22** |
| Cuaderno de campo | 4 | 4 | 5 | 2 | 4 | 1 | 1 | 17 |
| Corrección `_compute_total_hrs` | 4 | 2 | 3 | 5 | 5 | 4 | 4 | 11 |
| Corrección `action_conta` | 4 | 1 | 3 | 5 | 5 | 4 | 5 | 9 |
| Cuartel como maestro | 5 | 4 | 5 | 3 | 3 | 5 | 5 | 10 |
| ACL granular real | 3 | 1 | 2 | 1 | 4 | 3 | 5 | 3 |

**Seleccionado para la Fase C: carencia y reingreso.**

Es el único que combina máximo valor con mínimo riesgo: **no migra datos, no
altera estados históricos, no toca el costeo ni la contabilidad**. Solo agrega
campos calculados nuevos y una validación configurable en una transición de
estado. Y es lo que un jefe agrícola, un encargado de BPA y un auditor de
certificación miran primero.

Los dos hallazgos de costeo (§4.3, §4.4) tienen alto valor pero exigen recalcular
registros históricos ya contabilizados; requieren decisión explícita del usuario
sobre la migración antes de tocarse. Quedan documentados y propuestos, **no
ejecutados** en esta entrega.

---

## 7. Diseño del corte implementado

Ver **[docs/CORTE_CARENCIA_REINGRESO.md](CORTE_CARENCIA_REINGRESO.md)**.
