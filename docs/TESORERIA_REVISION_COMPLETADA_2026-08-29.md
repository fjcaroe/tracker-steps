# Tesorería — revisión y cierre del release

Fecha: 29 de agosto de 2026

## Resultado

Se auditó el release dejado por Claude, se corrigieron brechas funcionales y se
completaron las funciones pendientes que podían implementarse sin inventar un
formato bancario. El release canónico quedó homologado en Desarrollo, Demo y
Demo-SyS, conservando separadas las tres bases y sus datos.

## Hallazgos corregidos

1. La proyección de pedidos no respetaba realmente las políticas de facturación
   por entrega/recepción. Ahora usa `qty_to_invoice`, que es el dato canónico de
   Odoo para pedido, entrega, recepción y facturación acumulada.
2. `doc_type_id` apuntaba a `l10n_latam.document.type` sin declarar su dependencia.
   Se agregó `l10n_latam_invoice_document` para soportar instalaciones limpias.
3. Faltaba una portada de Tesorería. Se agregó un dashboard OWL con escenario
   activo, KPI, curva de saldo, cubetas, alertas, accesos y últimos flujos.
4. Faltaba PDF. Se agregó un reporte QWeb PDF derivado de la misma matriz canónica
   usada por pantalla y XLSX.
5. Faltaba una salida segura para el puente de pagos por lotes. Se agregó un CSV
   de revisión interna marcado como **NO CARGABLE AL BANCO**, sin cuentas bancarias,
   más una interfaz versionada de adaptadores reales deshabilitada por defecto.
6. La primera versión de la portada quedaba recortada porque el padre Odoo ocultaba
   el excedente. Se corrigió el alto y el contenedor de scroll; en navegador se
   verificó desplazamiento efectivo hasta el historial.

## Pruebas

- Núcleo de Tesorería: 54 pruebas, 0 fallos, 0 errores.
- Puente de pagos por lotes: 5 pruebas, 0 fallos, 0 errores.
- Instalación limpia y actualización sobre el esquema anterior probadas en base
  desechable.
- PDF real generado: 32.672 bytes, cabecera `%PDF` válida.
- Prueba de volumen con 5.000 líneas:
  - creación ORM: 2,7595 s;
  - matriz/resumen: 0,0870 s;
  - payload del dashboard: 0,0779 s;
  - render PDF: 2,8233 s.
- Navegador:
  - Desarrollo: portada con datos, KPI, gráfico, alerta, historial y scroll real;
  - Demo: portada y estado vacío guiado;
  - Demo-SyS: portada y estado vacío guiado respetando la empresa SyS;
  - formulario real: botones `Exportar XLSX` y `Exportar PDF` visibles;
  - sin errores JavaScript atribuibles al módulo.

## Release desplegado

| Componente | Versión | Desarrollo | Demo | Demo-SyS |
|---|---:|---:|---:|---:|
| `step_account_treasury` | 18.0.1.1.1 | instalado | instalado | instalado |
| `step_account_treasury_batch` | 18.0.1.1.0 | instalado | instalado | no aplica |
| `step_account_treasury_agro` | 18.0.1.0.0 | instalado | instalado | no aplica |

SHA-256 normalizado del núcleo en los tres árboles:
`375370d5edee32c98f4adae167dea8b3314343a00affad85fff39002b602d33f`.

Datos verificados después del despliegue:

- Desarrollo: 2 flujos, 38 líneas y 12 conceptos.
- Demo: sin flujos de Tesorería previos.
- Demo-SyS: sin flujos de Tesorería previos.

## Respaldos

Directorio: `/opt/backups/tesoreria_codex_20260829/`

Contiene un `pg_dump -Fc` verificado con `pg_restore --list` para cada base y un
archivo de los tres addons por ambiente antes del despliegue.

## Pendiente que requiere información externa

El archivo bancario real sigue deliberadamente deshabilitado. Para implementarlo
se necesita la especificación del banco o convenio: banco, producto, versión,
codificación, largo fijo/variable, campos, validaciones, nombre de archivo,
cabecera/tráiler y archivo de ejemplo aprobado. Hasta entonces el sistema sólo
entrega el CSV interno de control y nunca lo presenta como cargable al banco.

## Observaciones ajenas a este release

- `steps_api` figura instalado en Desarrollo y Demo, pero su código no está en el
  `addons_path`; Odoo ya reportaba este problema antes de Tesorería.
- Durante la primera compilación concurrente de assets en Demo se agotó una vez
  el pool de seis conexiones. La solicitud siguiente respondió correctamente y
  la portada quedó validada. Conviene revisar el dimensionamiento del pool si se
  repite bajo tráfico normal.
