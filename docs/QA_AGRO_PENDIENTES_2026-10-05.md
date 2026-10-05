# Continuación de Packing, Productores y Exportaciones

Rama: `codex/packing-productores-exportaciones-qa`. Esta continuación amplía
la [entrega anterior](QA_PACKING_PRODUCTORES_EXPORTACIONES_2026-10-05.md).
El destino autorizado es Desarrollo y Demo para aceptación funcional antes
de producción. Estado de despliegue: pendiente de completar las verificaciones.

## Documento funcional revisado

Se contrastaron los originales de Packing revisión 1, Productores revisión 2
y Exportaciones revisión 2. Sus adjuntos privados permanecen fuera del repositorio.

- Packing sitúa costos directos y asignación por OT en la segunda etapa.
  La revisión no especifica una fórmula adicional de capitalización. Se ofrece
  capitalización explícita y revisable mediante el mecanismo nativo de Odoo;
  no se capitaliza automáticamente al cerrar una OT.
- Productores requiere temporada y especie, con filtros por fechas de embarque.
- Exportaciones distingue la provisión del IVV revisado de la nota definitiva.
- La instrucción del usuario permite perfiles generales USB/Bluetooth mientras
  se obtienen las marcas y modelos. La homologación física permanece pendiente.

## Cambios preparados

| Aplicación | Versión | Cambio |
|---|---|---|
| Productores | 18.0.1.7.0 | Núcleo independiente de Exportaciones, migración y aliases de IDs existentes |
| Exportaciones | 18.0.2.8.0 | Puente con Productores, consolidación por especie y provisión IVV |
| Inventario Packing | 18.0.1.2.0 | Perfiles de impresoras y recepción de tramas BLE fragmentadas |
| Operación Packing | 18.0.2.7.0 | Costeo por OT, asignación de costos y capitalización nativa |
| Flujo fruta Productores | 18.0.1.2.0 | Versión conservada; se verifica con la integración |

Los modelos, tablas, IDs de registros y XML IDs públicos de Productores se
conservan. La migración cambia la propiedad de metadatos y copia fecha,
temporada y especie desde el recibidor para los registros históricos. Los
consolidados ligados a embarques y el vínculo con el recibidor quedan en el
puente de Exportaciones. Productores mantiene sus dependencias de catálogos
agrícolas Steps, compras y contabilidad; independencia significa que no instala
Exportaciones. Puede generar una liquidación con detalle propio sin recibidor.

## Prueba de costeo

1. En **Exportaciones → Configuración → Parámetros contables**, seleccionar
   el diario nativo de costos en destino (general), el producto de servicio para
   el costo de embalajes y la cuenta de consumo de embalajes. Debe corresponder
   al cargo contable real del consumo; no se crean cuentas ni diarios por defecto.
2. Cerrar la OT con sus materiales aprobados. En **Costeo por OT**, importar
   los costos de embalajes desde las capas de valoración nativas, o registrar
   costos directos respaldados. El importador reutiliza cada consumo.
3. En **Packing → Proceso → Asignación de costos**, seleccionar OT cerradas,
   importe, respaldo y base: kilos ingresados, horas efectivas u horas-persona.
   Cada OT debe tener base positiva. El reparto conserva el total, incluido
   el residuo de redondeo. Si se vincula un gasto publicado, no se permite
   asignar más que su importe contable entre las OT.
4. Revisar costos y porcentaje capitalizable. Las asignaciones proponen el
   porcentaje de kilos E sobre E + comercial + precalibre; el desecho no recibe
   valor. Es una base operativa explícita para revisar en QA, no una política
   contable supuesta a partir del documento. Los costos directos permiten
   revisar este porcentaje. Reabrir una asignación requiere que todas sus OT
   sigan sin costeo aprobado; reabrir un costeo exige que no esté capitalizado.
5. Aprobar con administrador de Inventario. Capitalizar requiere también
   permisos de Contabilidad, diario configurado y fruta E propia con valoración
   automática FIFO/promedio. El mecanismo nativo distribuye por los kilos reales
   de cada producto E. Excluye N, materia prima y materiales consumidos.
6. Comprobar la capitalización, sus capas de valoración y el asiento publicado.
   Se capitaliza solo la parte aprobada para E; el resto permanece como costo
   del proceso. Repetir la acción no duplica el documento. No se permite alterar
   sus líneas ni devolver su asiento a borrador desde esta integración.
7. Imprimir **Costeo de OT** y revisar valor inicial E, transformación, costo
   total de OT, importe capitalizable y costo por kg E. El informe no crea facturas.

La capitalización utiliza [costos en destino de Odoo 18](https://www.odoo.com/documentation/18.0/applications/inventory_and_mrp/inventory/product_management/inventory_valuation/landed_costs.html).
Odoo trata también la parte de costos correspondiente a existencias ya salidas;
no se simula inventario disponible ni se modifica directamente su valoración.

## Prueba de liquidaciones

1. Configurar **Diario provisión liquidaciones**, de tipo general, en los
   parámetros contables. Mantener el diario de ventas y el de ajustes externos.
2. Revisar y validar la liquidación del recibidor. **Provisionar IVV revisado**
   publica la variación contra las cuentas de clientes e ingreso de la factura
   inicial, sin exigir todavía el folio oficial de IVV o de la nota.
3. Cuando llegue el documento definitivo, indicar fecha de la nota, IVV del
   embarque y, si se emitió externamente, folio de nota externa. Los importes
   revisados permanecen bloqueados; el folio puede completarse después de validar.
4. **Contabilizar notas** publica la nota definitiva y revierte exactamente la
   provisión. Conciliar provisión y reversión evita saldos provisionales abiertos
   y duplicación del ingreso. La nota conserva su fecha y conversión de moneda.
5. En **Productores → Generar consolidados**, elegir temporada, especie y
   fechas de embarque. Se agrupa por productor y especie. Una liquidación que
   mezcla embarques fuera del alcance se excluye completa; no se prorratean sus
   descuentos sin una regla del cliente. Los consolidados antiguos conservan
   su selección e importes, incluso si aún no tenían dimensión de especie.

## Prueba de equipos

En **Packing → Configuraciones**, crear perfiles de balanza e impresora.

- Balanza: puerto serie USB/Bluetooth SPP con baudios/formato de trama, o BLE
  con UUID del servicio y característica. El patrón identifica el peso y puede
  exigir el indicador de estabilidad del fabricante. La lectura fragmentada
  se acumula con un límite de tamaño y tiempo.
- Impresora: PDF con controlador del sistema como opción general. Para envío
  directo se ofrece ZPL por puerto serie USB/SPP, BLE o WebUSB. Configurar UUID,
  interfaz/endpoint y tamaño de etiqueta según el fabricante. No todos los
  dispositivos USB ni los lenguajes de impresora son intercambiables.
- Desde una tarja, **Imprimir USB / Bluetooth / PDF** selecciona perfil y
  prepara la etiqueta. El envío directo exige un clic y el selector de equipo
  del navegador. «Etiqueta enviada» no acredita que el papel se imprimió.

Se requiere HTTPS y un navegador con la API correspondiente. Bluetooth clásico
SPP utiliza [Web Serial](https://developer.chrome.com/blog/serial-over-bluetooth);
BLE utiliza [GATT](https://developer.chrome.com/docs/capabilities/bluetooth).
No se ha verificado hardware físico. Los lectores que actúan como teclado
siguen usando los campos de escaneo existentes.

## Evidencia y cierre

Pendiente de registrar resultados finales de clones, instalación independiente,
respaldo, commit exacto y verificación de ambos QA. Producción queda fuera de
esta publicación; requiere aceptación funcional de cuentas, folios y equipos.
