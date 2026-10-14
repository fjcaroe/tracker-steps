# T34 opción C — Aserradero como módulo propio (`step_sawmill`)

Decisión (chat, 2026-09-23): para producción, las 4 apps Studio de `steps_qa`
(Packing Campo, Aserradero, Packing Fruta, Exportaciones) pasan a **módulos
Steps con código**, propios, instalables en otras instancias y versiones, y
extensibles. Este documento cubre la primera pieza: **Aserradero**.

## Qué había en Studio (inventario de solo lectura, `steps_qa`)

- 4 apps, 195 entradas de menú, 92 modelos referenciados por sus acciones.
- Aserradero era la única con proceso real y sin código: OP, OT, Aserrío,
  Elaboración, Secado, Impregnado, Certificación, cuadrillas y catálogos de madera.
- **Cero campos calculados y cero automatizaciones** en esos modelos: todo era
  captura manual. El port es fiel; los cálculos que se agregaron están marcados
  como *adición* más abajo.
- Packing Campo y Exportaciones ya tenían un primer port en T33
  (`step_packing`, `step_export`): catálogos y cabeceras, sin flujo.

## `step_sawmill` (18.0.1.0.0)

Dependencias: `base, mail, product, stock, mrp, hr`. **Nada Enterprise y ningún
otro módulo Steps**, para instalarlo solo en cualquier instancia.

| Documento | Modelo | Flujo |
|---|---|---|
| Orden de producción | `step.sawmill.production.order` | kanban por etapa (Nuevo / En progreso / Listo) |
| Orden de trabajo | `step.sawmill.work.order` | estado kanban |
| Aserrío | `step.sawmill.sawing` | Ingresada → Autorizada → Valorizada |
| Elaboración | `step.sawmill.elaboration` | Ingresada → Autorizada → Valorizada |
| Secado | `step.sawmill.drying` | En proceso → Terminado |
| Impregnado | `step.sawmill.impregnation` | Ingresado → Aprobado → Certificado |
| Certificación | `step.sawmill.certification` | Enviada → Certificada |
| Cuadrilla | `step.sawmill.crew` | — |

Catálogos: grado, calidad, tipo de producto, destino, driver de costeo, turno,
tipo de proceso, línea/máquina, días y horas hábiles por mes.

Seguridad: grupos *Aserradero: usuario* y *Aserradero: responsable*; reglas
multiempresa; solo el responsable reabre un registro Valorizado; solo se borran
registros en estado inicial.

## Decisiones de diseño (para revisar)

1. **Autocontenido.** Aserradero trae sus propios catálogos (línea, tipo de
   proceso, turno) en vez de reutilizar los de `step_packing` o `step_hr`.
   Cuesta algo de duplicación con Packing, pero permite instalarlo solo.
2. **Sin Enterprise.** Studio usaba `planning.slot.template` (turnos) y tipos de
   entrada de nómina para la cuadrilla. Se reemplazaron por el catálogo propio
   `step.sawmill.shift` y se quitó el vínculo a nómina de la cuadrilla.
3. **Número de OT como relación.** En Studio "Número OT" era texto/entero suelto
   en Secado, Impregnado y Certificación; aquí es `Many2one` a la OT.
4. **Aserrío y Elaboración comparten cabecera** (`step.sawmill.process.mixin`) y
   líneas (`step.sawmill.output/input/cost.line`).
5. **`mrp.production` y `mrp.workcenter` son vínculos opcionales**, no el eje del
   proceso; los "Tiempos muertos" siguen en Fabricación estándar.

## Adiciones respecto de Studio (no existían, se dejan explícitas)

- Horas totales = término − inicio (Aserrío, Elaboración, Secado, Impregnado);
  editable a mano.
- Costo total por línea = suma de los 6 componentes; costo unitario por UdM y
  por pieza (0 si la cantidad es 0); costo total del documento.
- Dotación = número de trabajadores de la cuadrilla.
- Elaboración con líneas de producto/consumo/valorización (en Studio solo tenía
  cabecera).
- Secuencias OP-, OT-, ASE-, ELA-.

## No portado (y por qué)

- *Informe de secado*, *Informe de impregnado* y *Nivel ocupación máquinas*:
  eran solo un nombre sin campos. Requieren definición funcional.
- Vínculo de cuadrilla con conceptos de sueldo (`hr.payslip.input.type`,
  `hr.work.entry.type`): dependen de nómina; queda para un módulo puente.
- Datos de `steps_qa`: son datos de prueba (1–2 registros por documento). No se
  migraron; los catálogos de madera van como datos de demostración.

## Verificación

- 13 pruebas de `TransactionCase` (etiqueta `step_sawmill`), todas OK en
  `LAB_TAREAS`: secuencias, flujo de estados y sus bloqueos, totales de costo,
  división por cero, cuadrilla, un-solo-padre de las líneas, secado, impregnado,
  certificación, unicidad de catálogos, permisos.
- Instalación limpia en `LAB_TAREAS` (Desarrollo); 41 vistas compiladas contra el
  registro real sin errores; el flujo OP → OT → Aserrío → Valorizada corrido en
  `odoo shell` con rollback.
- Respaldo previo: `/opt/steps_backups/ticket34_sawmill_desarrollo_20260924T015100Z/`
  (`LAB_TAREAS.dump`, 21 MB, con SHA256).

## Portabilidad a otras instancias y versiones

- **Instancias:** copiar la carpeta `step_sawmill` al `addons_path` e instalar.
  No requiere `studio_customization` ni datos previos.
- **Versiones de Odoo:** el código sigue las convenciones de **18.0**
  (`<list>`, `invisible="expr"`, `<chatter/>`, `t-name="card"`, `groups_id`). Para
  otra versión se mantiene **una rama por versión** (`17.0`, `19.0`…); las
  diferencias esperables son de vistas (`tree`/`attrs` en 17; `privilege_id` y
  `group_ids` en 19), no de modelo. Mantener las dependencias en módulos
  Community es lo que hace viable ese camino.

## Lo que falta de la opción C (siguientes piezas)

1. **Desacoplar `step_packing` y `step_export` de `step_hr`**: hoy dependen de
   él solo para Fundo/Especie/Variedad/Temporada/Sector. Decidir dueño de esos
   maestros (módulo base agrícola neutro vs. seguir en `step_hr`) — requiere
   confirmación, porque cambia dependencias ya instaladas en Cerro El Plomo.
2. **Packing Fruta:** recepción de fruta y granel, reserva de stock, órdenes de
   fabricación y traslados. Usa campos Studio sobre modelos estándar
   (`stock.picking`, `mrp.production`) que hay que inventariar uno por uno.
3. **Exportaciones (profundidad):** embarques, liquidaciones a productor,
   contratos, informes. Gran parte de esos menús estaban vacíos en Studio: hay que
   definir el proceso con el cliente antes de programarlos.
4. **Estimación de cosecha:** curvas de calibre/clase (`x_curva_*`).
5. **Base de prueba con las 4 apps de Studio (opción A)** para que el cliente
   compare mientras se construye: sigue sin autorizar.
