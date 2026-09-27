# T35 — Despliegue de Exportaciones, 27 de septiembre de 2026

## Entornos disponibles para prueba

| Entorno | Base Odoo | Parámetros contables |
|---|---|---|
| Desarrollo | `LAB_TAREAS` | [Abrir parámetros](https://desarrollo.stepsapp.cl/odoo/action-2031) |
| Demo | `STEPS_DEMO` | [Abrir parámetros](https://demo.stepsapp.cl/odoo/action-1951) |
| Cerro El Plomo | `CERRO_EL_PLOMO` | [Abrir parámetros](https://cerroelplomo.stepsapp.cl/odoo/action-1446) |
| Demo-SyS | `STEPS_DEMO_SYS` | [Abrir parámetros](https://demo-sys.stepsapp.cl/odoo/action-1885) |

La ruta dentro de Odoo es **Exportaciones → Configuración → Parámetros
contables**. Requiere permisos de administrador de Contabilidad. También puede
abrirse desde los enlaces anteriores después de iniciar sesión.

## Valores iniciales editables

| Parámetro | Desarrollo, Demo y Cerro El Plomo | Demo-SyS |
|---|---|---|
| Diario de facturas de exportación | `EXPT` — Exportaciones T35 | `EXPT` — Exportaciones T35 |
| Diario de compras de productores | `PRDT` — Productores T35 | `PRDT` — Productores T35 |
| Diario de ajustes con DTE externo | `IVVT` — Ajustes IVV T35 | `IVVT` — Ajustes IVV T35 |
| Cuenta de ventas de exportación | `310125` | `310125` |
| Cuenta de compra de fruta | `410230` | `410102` |
| Impuesto de venta de exportación | Sin impuesto de venta chileno | Sin impuesto de venta chileno |
| Impuesto de compra de fruta | IVA compras 19 % existente | IVA compras 19 % existente |

En Cerro El Plomo se configuraron sus cuatro empresas: Cerro El Plomo SpA,
Comercial Volcán San Pedro SpA, Exportadora Cerro Tronador SpA y Agrícola
Cerro El Plomo SpA. En Demo-SyS se configuró solo la empresa principal
**Asesores S&S Asociados Spa**; las demás compañías de esa base pueden
configurarse independientemente si usarán Exportaciones.

Los valores se cambian desde la pantalla indicada. Los diarios, cuentas e
impuestos también se pueden revisar en **Contabilidad → Configuración**.
Los tipos DTE 110/111/112 y el módulo `l10n_cl_edi_exports` quedaron
instalados en los cuatro entornos. La autorización, certificado y folios
electrónicos del SII son datos propios de cada empresa y no se generaron
ni reemplazaron en este despliegue.

Las tarifas reales se ingresan en **Exportaciones → Configuración → Tarifa
Productor**. Se debe indicar productor, temporada, especie y valor contractual.
Las nuevas tarifas toman por defecto la cuenta y el impuesto de compra de la
empresa; esos valores pueden ajustarse en cada tarifa antes de liquidar.

## Validación y respaldo

- Versión instalada de `step_export`: `18.0.2.1.0` en las cuatro bases.
- En una copia aislada de cada base: 11 pruebas Odoo, 0 fallas y 0 errores.
- Servicios de los cuatro entornos activos y acceso público a `/web/login` con
  HTTP 200 después del reinicio.
- Respaldo previo de las cuatro bases, sus filestores y los addons anteriores:
  `/opt/steps_backups/t35_export_20260927_060113/` en la instancia `odoo-new`.
- Código versionado en la rama `ticket/35-exportaciones`, commit `e315c81`.
