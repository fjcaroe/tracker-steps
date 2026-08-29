# Previred y contabilidad bimoneda — release 2026-08-29

## Previred

Módulo: `step_hr_previred` 18.0.3.3.1.

- Campo 13: toma días de asistencia efectiva (`WORK100` cuando existe) y
  excluye tipos de entrada marcados como ausencia, incluidas licencias.
- Campo 93: toma el código configurado en el horario de trabajo: `1` jornada
  completa, `2` jornada parcial. La migración inicial clasifica horarios de
  hasta 30 horas como parciales.
- Campo 105: toma la cuenta analítica/centro de costo del contrato; usa su
  código y, si está vacío, su nombre, limitado a 20 caracteres.
- Las tres correcciones se aplican a perfiles v84 y v98.

Validación real en `STEPS_DEMO_SYS`, liquidación `SLIP/380`:

`DAYS 1 · WORKDAY 1 · COST Maquinarias`

## Contabilidad bimoneda

Módulo: `step_accounting_multicurrency` 18.0.2.0.1.

- Configuración por empresa de moneda operacional.
- El asiento conserva fecha de tasa, dólar observado, tasa por apunte,
  débito, crédito y saldo operacional.
- La fecha de tasa es la más temprana entre fecha del documento y fecha
  contable; sin documento usa la fecha contable.
- Si tasas distintas por línea descuadran el libro operacional se agrega un
  apunte operacional de diferencia de cambio, sin alterar el balance en la
  moneda principal.
- Pagos muestran dólar observado y valor convertido en ambos sentidos.
- Balance General y Estado de Resultados pueden agregar columnas operacionales
  y consultan `account_move_line.operational_balance`, no convierten el total
  a la fecha del informe. Los reportes con handlers SQL especializados no
  muestran una columna operacional hasta contar con un adaptador propio, para
  evitar rotular importes CLP como USD.

La moneda operacional quedó configurada en USD para Desarrollo y Demo. En
Demo-SyS el módulo está instalado, pero la moneda se dejó sin configurar por
tener múltiples empresas; debe definirse individualmente por compañía.

## Pruebas y despliegue

- Previred: 21 casos del dataset, 0 fallas, 0 errores.
- Bimoneda: 5 flujos funcionales, 0 fallas, 0 errores.
- Desplegado en `LAB_TAREAS`, `STEPS_DEMO` y `STEPS_DEMO_SYS`.
- Código idéntico en los tres árboles; SHA-256 compuesto:
  `6b2ac5886c223b50aafd94474ad5bec3466a4621869e4c500b6b0232e58551ac`.
- Respaldos verificables en
  `/opt/backups/codex_previred_bimoneda_20260829/`.

No se modificaron datos históricos para inventar una segunda moneda. Los
nuevos asientos capturan la moneda operacional desde su creación; cualquier
conversión histórica debe hacerse mediante una migración contable aprobada.
