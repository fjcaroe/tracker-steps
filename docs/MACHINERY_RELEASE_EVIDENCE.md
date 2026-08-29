# Maquinaria agrícola — release 18.0.19.0.1

Fecha de validación: **28 de agosto de 2026**.

## Ambientes

| Ambiente | Base | Estado |
|---|---|---|
| Desarrollo | `LAB_TAREAS` | instalado y validado |
| Demo | `STEPS_DEMO` | instalado y validado |
| Demo-SyS | `STEPS_DEMO_SYS` | no instalado; ambiente especializado de Nómina SyS |

Desarrollo y Demo usan exactamente los mismos archivos y versiones. No se
copiaron bases ni datos entre ambientes.

## Alcance implementado

- Menú Maquinaria simplificado a **Horas Máquina** y **Detalle Horas Máquina**.
- `Costos Auto`, rastreo temporal y el costeo anterior quedan archivados, sin
  borrar modelos ni registros.
- Nuevo menú **Costeo de Maquinarias** con conciliación real versus estándar.
- Fecha, semana ISO y temporada relacionadas automáticamente.
- Folio BPA enlazado por `Many2one` a una aplicación foliar en estado
  **Ingresado**, con validación de empresa.
- Estado BPA promovido desde Studio a un campo nativo y migrado sin pérdida.
- Costeo almacenado por línea para los ocho conceptos 01-08:
  combustible, aceites, repuestos, mantención correctiva, mano de obra,
  arriendo, mantención preventiva y depreciación.
- El combustible usa el costo vigente del producto de la máquina; los demás
  conceptos usan su costo horario mensual/provisionado.
- Hoja Costeo visible desde el estado **Costeado**, con costo unitario, total
  por concepto, costo total máquina y costo total HrMq.
- Un comprobante por registro, balanceado y agrupado por cuenta y distribución
  analítica. El cargo conserva temporada, centro de costo y actividad; el
  abono identifica el centro analítico vinculado a la maquinaria.
- Configuración del Diario de Maquinarias corregida para abrir el módulo
  adecuado.
- Perfil técnico renombrado a **Costeo y contabilización**.
- Ícono `JE` eliminado físicamente y reemplazado por el logo agrícola de
  Maquinaria.

## Defectos corregidos

- `action_conta()` ya no escribe el estado inexistente `conta`.
- Mantención y provisión ya no se calculan desde colecciones intercambiadas.
- Las horas ya no sobrescriben el costo calculado dentro del mismo compute.
- `step_cost_hrmq_standar` es ahora un campo calculado y almacenado de forma
  determinística.
- Los horómetros se leen por fecha descendente, no por un registro arbitrario.
- Las OT-BPA no dependen del nombre técnico de un campo Studio.

## Pruebas

En Desarrollo y Demo:

```text
3 pruebas automatizadas · 0 fallas · 0 errores
```

Además se ejecutó una prueba transaccional completa en Desarrollo:

```text
3 litros × $100 combustible = $300
2 horas × $10 aceites       =  $20
2 horas ×  $5 preventiva    =  $10
2 horas ×  $2 depreciación  =   $4
Costo total máquina         = $334
Costo total HrMq            = $167
Comprobante                 = balanceado
```

La transacción se revirtió al terminar. Se confirmó que no quedaron registros
ni vehículos de prueba.

## Conservación de datos

En Desarrollo se conservaron los conteos previos: 20 registros de Horas
Máquina, 32 líneas y 27 conciliaciones de costo real. La migración del estado
BPA terminó con 0 valores nulos y 0 diferencias frente al estado Studio.

## Respaldos

- Desarrollo: `/opt/backups/steps_20260828_codex_machinery_dev/`
- Demo: `/opt/backups/steps_20260828_codex_machinery_demo/`

Los dumps fueron validados con `pg_restore --list` antes del despliegue y se
respaldaron por separado Maquinaria, BPA, Perfiles Agrícolas y Operations UI.

## Seguridad operativa

`fcaro.ruiz@gmail.com` hereda en ambos ambientes Maquinaria, Costeo y
contabilización, Maestros, Informes y Configuración. No se contabilizó ningún
registro real, no se enviaron documentos y no se hizo `git push`.
