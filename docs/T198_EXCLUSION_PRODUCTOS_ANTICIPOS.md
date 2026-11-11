# T198 · Exclusión de productos en anticipos

En Productores → Anticipos → Preparar anticipos, la sección **Exclusiones**
permite seleccionar los productos valorizados que se omitirán en esa
preparación. El filtro se aplica por kilos recibidos y por kilos procesados
antes de buscar las tarifas, calcular importes o reservar los kilos.

El nuevo borrador guarda la selección. Una preparación posterior agrega
líneas al mismo borrador cuando coincide el conjunto de exclusiones.
Las fuentes ya reservadas se rigen por el control de duplicados. Si la
selección deja todos los kilos fuera, el asistente explica el resultado.

El paquete incluye `step_producer_advances` 18.0.1.2.1 y
`step_packing_fruit_proforma` 18.0.1.2.2. Se construyó desde el commit
`9c1207d00b4430b1e55c0093abc419a334d07fbe`, con SHA-256
`0826684f91c409c83db7cf739d08a0287c43145d5e558f33f523f72e8a85dfb2`.

En la copia de Cerro, seleccionar AR11 excluyó dos tarjas y 701,10 kg.
El borrador incluyó las otras once tarjas, por 4.417,40 kg. Una segunda
ejecución devolvió el mismo borrador. Se conservó el historial del anticipo
anterior y se revirtió el ensayo.

Las copias frescas de Desarrollo, Cerro El Plomo y QA-Cerro El Plomo
pasaron 73 pruebas cada una. Se comprobó la factura en borrador, la
exclusión de un producto sin tarifa, la preparación posterior con ese
producto y el historial de borradores mixtos. Se revisaron las proformas
y sus anexos en las tres copias.

El mismo paquete se publicó con respaldo y se verificó en los tres
ambientes. Cerro y QA-Cerro ejecutan las mismas versiones y el mismo
código efectivo de ambos módulos.
