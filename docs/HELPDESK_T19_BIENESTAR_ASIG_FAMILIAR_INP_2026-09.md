# Helpdesk T19 — Sociedad de Bienestar: Asignación Familiar por IPS/ex-INP

- **Empresa:** Sociedad de Bienestar Integral y Mantenimiento de la Salud Ltda.
- **Período:** 202608
- **Base indicada por el cliente:** http://35.222.25.110:8070/odoo (motor de
  nómina del proveedor — solo lectura para esta automatización).
- **Área:** Nómina / PreviRed. Módulo `step_hr_previred`.
- **Rama:** `ticket/19-bienestar-asig-familiar-inp` (sobre `develop`, que ya
  contiene `fix/previred-correcciones-2` + tickets #17 y #18).

## Petición (textual)

> Cuando la empresa no tiene Caja para compensar la Asignación Familiar, sino
> que cotiza en INP, el valor de la carga familiar, que va en la columna
> [22] Asig. Familiar, se traslada a la columna [73] Cargas fam. INP.

## Diagnóstico

El archivo PreviRed conserva los importes que concilia el motor de nómina.
Hoy el monto de la asignación familiar sale siempre en el **campo 22
«Asignación Familiar»**. PreviRed, para el empleador que **no está adherido a
una CCAF** y paga las cargas a través del **IPS/ex-INP**, espera ese monto en
el **campo 73 «Descuento por Cargas Familiares IPS»** (bloque IPS, campos
62–74), con el campo 22 en `0`.

No hay recálculo: es un traslado del mismo valor entre dos columnas.

## Cambio implementado

`step_hr_previred` 18.0.3.8.3.

- **`tools/previred.py`**: constantes `F_FAMILY_ALLOWANCE = 22` y
  `F_FAMILY_ALLOWANCE_IPS = 73`.
- **`models/previred_extractor.py`**: nuevo
  `PreviredExtractor._relocate_family_allowance_to_ips(record, dataset)`,
  llamado desde `_enrich_official_fields` **antes** del corte por versión de
  perfil (los campos 22 y 73 existen en v84 y v98). Para cada línea del
  trabajador:
  - condición: empresa sin código de CCAF en el campo 83 (`""`, `"0"` o
    `"00"`), independientemente del régimen previsional del trabajador;
  - si el campo 22 trae un monto `> 0`: se suma al campo 73 (respetando lo que
    ya hubiera) y el campo 22 queda en `"0"`;
  - deja el hallazgo auditable `family_allowance_moved_to_ips` con el detalle
    `«22 Asignación Familiar → 73 Descuento por Cargas Familiares IPS: <monto>»`.
- Un empleador adherido a CCAF (campo 83 con código) **conserva** el campo 22
  intacto.

## Pruebas agregadas (`tests/test_dataset.py`)

- `test_without_ccaf_moves_afp_family_allowance_to_field_73`: afiliado AFP en
  empresa sin CCAF, campo 22 = 27.812 → campo 22 = 0, campo 73 = 27.812.
- `test_with_ccaf_keeps_family_allowance_in_field_22`: una empresa con código
  CCAF conserva el campo 22, sea cual sea el régimen del trabajador.

## Supuestos

- El monto correcto de la asignación familiar es el que ya emite el motor en
  el campo 22 (no se recalcula ni se revalida contra la tabla N°8).
- «Cotiza en INP» describe la vía de pago de cargas familiares de la empresa;
  no significa que cada trabajador deba tener régimen previsional `INP`. La
  evidencia adjunta muestra a Valentina afiliada a AFP y exige el traslado.
- «No tiene Caja» ⇒ campo 83 (Código CCAF) vacío o `0`.
- El traslado se aplica a la línea principal y a cualquier anexa que trajera
  monto en el campo 22 (en la práctica sólo la principal lo trae).

## Pendiente / validación

- Desplegar 18.0.3.8.3 y regenerar el TXT de Sociedad de Bienestar 202608:
  confirmar que las líneas con asignación familiar muestran campo 22 = 0 y
  campo 73 = monto de la carga, y que las empresas con CCAF no cambian.
- «Actualizar en :8070»: es la base del motor del proveedor; esta
  automatización sólo la lee. El cambio vive en el exportador `step_hr_previred`.
