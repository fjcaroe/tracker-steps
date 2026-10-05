# T38 — Arquitectura del módulo Productores (decisión 2026-09-30)

Decisiones de Fernando en sesión interactiva, más la arquitectura resultante.
Reemplaza los "pendientes de confirmación" de la nota de análisis del 2026-09-29.

## Decisiones confirmadas

1. **Productores es un módulo Steps independiente**, instalable como aplicación
   en otros servidores de Steps. No es una sección de Exportaciones.
2. **Contrato/Compras se mueve** desde Gestión de Costos a Productores (no solo
   se referencia). Estado: ya movido en `step_producers` (`step.producer.purchase.contract*`);
   `step_management_costs` no contiene el modelo.
3. **El motor de cálculo lo construimos nosotros**, en la VM propia de Google
   donde corre Odoo. No se requiere un servicio de terceros.
4. **Arquitectura la define Claude** (este documento). Las consultas al cliente
   se hacen en lenguaje de negocio, sin nombres técnicos de módulos.

## Dueño de cada dato (estado objetivo)

| Dato | Dueño objetivo | Estado hoy |
|---|---|---|
| Productor, fundos, cuenta contable del productor | `step_producers` | en `step_producers` (sobre `res.partner`) |
| Contratos de compra y calendario de cuotas | `step_producers` | movido (T30/T38) |
| Lista de precios de preliquidación | `step_producers` | hecho |
| Estimación de fruta y versiones | `step_producers` | movido en 18.0.1.7.0 |
| Tarifa del productor (`grower.rate`) | `step_producers` | movido en 18.0.1.7.0 |
| Liquidación del productor | `step_producers` | núcleo propio; recibidor en puente de Exportaciones |
| Saldo de estimación, recepciones, preliquidación | `step_producer_fruit_flow` | hecho |
| Embarques, ventas, liquidación del recibidor | `step_export` | correcto |
| Tarjas y recepciones de fruta | Inventario/Packing | correcto |

Regla de dependencias (sin ciclos, de abajo hacia arriba):

```
Odoo estándar (purchase, account, analytic, stock)
        └── step_producers            (independiente, instalable solo)
              └── step_export         (embarques y recibidor; depende de Productores)
              └── step_producer_fruit_flow   (puente: Productores + Inventario/Packing)
```

Desde 18.0.1.7.0 la dependencia está invertida hacia el estado objetivo:
`step_export` depende de `step_producers`. Productores conserva dependencias de
catálogos agrícolas Steps (`step_hr`, `step_management_costs`, `step_packing`,
`step_inventory_fruit_tag`); instalarlo sin Exportaciones no significa instalarlo
sin esos catálogos. Se verificó su instalación y liquidación propia sin recibidor.

## Motor de cálculo

- Vive dentro de Odoo, en `step_producers` / `step_producer_fruit_flow`, como
  métodos puros y testeables (preliquidación: FOB estimado, gasto unitario,
  retorno por kg; reparto de FOB en tarjas mixtas; precio pool). Sin servicio
  externo ni cola: el cálculo es determinista y por lote pequeño.
- Se levanta un servicio aparte en la VM **solo si** aparece una necesidad real
  (volumen, cálculo pesado o uso desde fuera de Odoo). No hoy.
- Cada regla del Anexo 1 ("Preliq") tiene una prueba con el ejemplo numérico del
  cliente.

## Plan de migración (por fases)

- **Fase A — hecha (PR #11):** app Productores sobre los modelos existentes,
  contratos movidos, preliquidación, precio pool, PDF de liquidación.
- **Fase B — implementada:** mover `step.export.estimate*`, `step.export.grower.rate*`
  y `step.export.producer.settlement*` a `step_producers` **sin cambiar `_name`
  ni tablas** (migración pre-init que reasigna `ir_model_data.module` y los
  xmlids), invertir la dependencia (`step_export` pasa a depender de
  `step_producers`) y quitar `step_export` de `step_producers.depends`.
  Riesgo: datos reales en Demo/Desarrollo (T35); se hace con respaldo y prueba
  en base clonada antes de tocar ambientes. Requiere coordinar con la rama de
  T35, que es la base del PR #11.
- **Fase C — consolidado implementado; aceptación contable pendiente:**
  consolidación por productor, temporada y especie, filtros por fechas de
  embarque, tipo, variedad y embarques. Conserva liquidaciones completas y
  documentos existentes. El piloto con datos reales sigue en QA antes de SyS.

Evidencia, configuración y límites de esta continuación:
[QA de pendientes](QA_AGRO_PENDIENTES_2026-10-05.md).

## Lenguaje hacia el cliente

El cliente no conoce nombres de módulos. En el ticket se pregunta con términos de
negocio: "liquidación al productor", "estimación de fruta", "gasto por kilo",
"contrato de compra". No se usan `step_export`, `step_producers` ni nombres de
modelos en notas dirigidas al cliente.
