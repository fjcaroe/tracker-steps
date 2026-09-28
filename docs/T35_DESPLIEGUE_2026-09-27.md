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

## Identidad visual y portada de Exportaciones — 27 de septiembre de 2026

Se añadió un icono propio al lanzador Odoo y una pantalla **Inicio** para
Exportaciones. La portada usa el mismo lenguaje visual de las otras aplicaciones
Steps, muestra programas vigentes, embarques abiertos, forecasts y liquidaciones
de recibidor pendientes, y ofrece accesos al flujo comercial. Los contadores
respetan los registros visibles para el usuario y sus empresas activas.

El Home público compartido incorpora **Exportaciones** como la solución 07 de
Recursos y logística, con sus capacidades y un acceso al módulo a través del
login HTTPS. La página `/soluciones/recursos-y-logistica` también la presenta.
Desarrollo, Demo y Cerro El Plomo sirven ahora la misma portada editorial de
Steps Agro, con 13 soluciones. Las versiones instaladas son
`step_export 18.0.2.2.0` y `step_demo_homepage 18.0.2.4.1`.

| Entorno | Respaldo previo de base y addons | Verificación |
|---|---|---|
| Desarrollo | `/opt/steps_backups/t35_branding_dev_20260927T064002Z/` | Home 200, 13 soluciones, icono y fotografía 200 |
| Demo | `/opt/steps_backups/t35_branding_demo_20260927T064050Z/` | Home 200, 13 soluciones, icono y fotografía 200 |
| Cerro El Plomo | `/opt/steps_backups/t35_branding_cerro_20260927T064136Z/` | Home 200, 13 soluciones, icono y fotografía 200 |

Cerro tenía dos copias de `step_demo_homepage`: la vista de base se actualizó
desde `steps_addons`, pero la ruta estática leía la copia antigua en
`odoo_agriculture`. Se respaldó y sincronizó esa copia para servir las imágenes;
respaldo adicional:
`/opt/steps_backups/t35_branding_cerro_static_20260927T064212Z/`.

En los tres dominios se verificaron `/`, `/soluciones/recursos-y-logistica`,
los recursos del icono y la fotografía, y el destino público
`/web/login?redirect=%2Fodoo%2Faction-step_export.action_step_export_dashboard`:
HTTP 200 sin redirección a HTTP. Los estilos SCSS de Exportaciones y Home
compilaron correctamente en las tres instalaciones. El menú raíz tiene icono
y acción configurados. Se revisó visualmente la portada de Cerro, incluido el
filtro Recursos y logística y la tarjeta expandida de Exportaciones.

La primera actualización de Desarrollo se detuvo antes de terminar por una
referencia de vista incorrecta en la migración; se corrigió, se repitió con
respaldo nuevo y quedó instalada. Una comprobación SQL final también necesitó
ajustarse porque Odoo almacena nombres de menú como JSON; no afectó la
actualización ya completada. El commit de entrega es `47e692a` en la rama
`ticket/35-exportaciones`.
