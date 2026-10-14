# T35 — Exportaciones

Ticket: http://35.222.25.110:8069/odoo/helpdesk/action-543/35

## Alcance implementado

`step_export` conserva los modelos y datos portados desde Studio en T33. El nuevo
flujo agrega programas de venta con versiones y cálculo semanal, programas de
embalaje con valorización y necesidades de materiales, estimaciones de productor
con versiones y distribución semanal, forecast de cinco semanas, embarques,
tarjas, guías de despacho, Packing List imprimible, enlaces a ventas y facturas,
reclamos, liquidaciones de recibidor y liquidaciones de productor.

Los modelos de tarjas y guías son los módulos existentes de T22 y T25, incluidos
como dependencias. El mismo registro de tarja conserva productor, variedad,
calibre, kilos, embarque, reclamo y liquidación. Los maestros de fruta de Gestión
y Costos se reutilizan.

## Política contable aplicada

- La factura inicial del embarque se publica desde Ventas/Contabilidad al
  transferirse el control según el contrato e Incoterm. El módulo no presume que
  la fecha de despacho equivale siempre a la transferencia de control.
- La liquidación del recibidor toma ventas convertidas a USD, descuenta reclamos
  aceptados, gastos en destino y comisión calculada sobre las ventas para
  obtener FOB. Puede distribuirse por categoría y calibre, manteniendo las
  tarjas y los kilos de cada grupo. El IVV económico es el FOB menos el importe
  neto de la factura inicial expresado en USD.
- Un IVV positivo aumenta cuentas por cobrar e ingresos; uno negativo los
  disminuye. Si Odoo emite la nota, se usa el tipo de documento de exportación
  111 (débito) o 112 (crédito), en USD y contra la cuenta de ingreso original.
  Se exige el folio IVV del embarque antes de contabilizar.
- Cuando la nota 111/112 ya fue emitida por un proveedor DTE externo, se
  registra su folio y se contabiliza un asiento balanceado con la cuenta por
  cobrar y la cuenta de ingreso de la factura original. No se emite un segundo
  DTE desde Odoo.
- La liquidación del productor se genera desde los kilos y propietario de cada
  tarja. La tarifa contractual puede ser USD/kg o porcentaje del FOB asignado.
  Se vinculan las facturas previas del productor para evitar duplicar la compra:
  solo se documenta la diferencia. Si no existe factura previa, se registra
  la factura inicial 33; si el precio sube o baja tras una factura previa,
  se registra respectivamente la nota de débito 56 o crédito 61 del proveedor.
  Se exige folio, impuestos de compra configurados en la tarifa y revisión
  explícita de facturas previas antes de publicar el ajuste. El documento se
  registra en la moneda local por conversión desde la tarifa en USD.
- Los importes estimados del forecast no generan asientos. Cuando exista una
  estimación de contraprestación variable suficientemente fiable, el cierre
  contable deberá reconocerla según la política contable de la entidad. La
  liquidación final genera el ajuste documentado.

La base de esta política es [NIIF 15 del IFRS Foundation](https://www.ifrs.org/issued-standards/list-of-standards/ifrs-15-revenue-from-contracts-with-customers/),
que trata la contraprestación variable y el reconocimiento al transferirse el
control, y la [tabla de tipos de documento del SII](https://www.sii.cl/declaraciones_juradas/ddjj_3327_3328/instrucciones_llenado_comp_vtas.pdf),
que identifica 111 y 112. El [SII explica la emisión de notas de exportación](https://www.sii.cl/destacados/factura_electronica/guias_ayuda/emitir_nota_credito_debito_exp_electr.pdf).
Para la compra de fruta con precio inicialmente acordado y ajuste posterior
se tomó el [oficio 1219 del SII](https://www.sii.cl/normativa_legislacion/jurisprudencia_administrativa/ley_impuesto_ventas/2010/ja1219.htm),
además de la [codificación DTE del SII](https://www.sii.cl/normativa_legislacion/resoluciones/2026/reso71.pdf).
Si el cliente necesita cambiar el criterio de presentación bruta/neta,
devengo o reparto al productor, debe solicitarlo en otro ticket con los
contratos y la política contable aplicable.

## Configuración requerida

1. Mantener productos exportables, tarjas con propietario y kilos, listas de
   materiales de fruta, conceptos de valorización y tarifas por productor,
   temporada y especie, incluida la cuenta de compra y los impuestos aplicables.
2. Revisar por empresa los valores iniciales en **Exportaciones →
   Configuración → Parámetros contables**: diarios de venta, compra y ajuste,
   cuentas de venta y compra, e impuestos. El impuesto de venta vacío significa
   factura de exportación sin IVA chileno; el impuesto inicial de compra de
   fruta es el 19 % existente de la localización chilena. El cliente puede
   cambiar cualquiera de estos valores desde esa pantalla.
3. La localización de exportación electrónica `l10n_cl_edi_exports` y los
   documentos 110/111/112 están instalados. La emisión y envío efectivos
   dependen además de la autorización, certificado y folios SII de cada empresa.
4. Registrar el folio de la nota externa cuando el proveedor DTE sea externo.
   Registrar además DUS, BL/AWB e IVV del embarque antes del cierre.
5. La emisión electrónica y envío al SII siguen el servicio DTE configurado
   en Contabilidad. Los asientos de una nota externa registran el documento ya
   emitido; no lo sustituyen.
6. Completar cada tarifa contractual en **Exportaciones → Configuración →
   Tarifa Productor** (productor, temporada, especie y valor). Las nuevas
   tarifas heredan la cuenta e impuesto de compra de los parámetros contables.
   No se inventaron tarifas ni comisiones sin contrato.

## Verificación

La instalación y las pruebas se ejecutaron en copias aisladas de Desarrollo,
Demo, Cerro El Plomo y Demo-SyS. La última actualización del módulo terminó
con **11 pruebas, 0 fallas y 0 errores** en cada copia. El despliegue y sus
parámetros iniciales están detallados en
[T35_DESPLIEGUE_2026-09-27.md](T35_DESPLIEGUE_2026-09-27.md).
