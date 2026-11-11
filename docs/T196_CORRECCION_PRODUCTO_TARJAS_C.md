# T196 · Corrección de producto de tarjas C recibidas

En Packing → Recepciones → Fruta a proceso, el responsable de Inventario
puede usar **Corregir producto** en una recepción realizada. El asistente
solicita las tarjas, el producto almacenable y el motivo. Comprueba que la
fruta de tercero esté íntegra, en su ubicación original y libre de reservas,
procesos y documentos asociados. Los movimientos de ajuste se consultan
desde la misma recepción.

La corrección conserva el peso, los envases, la ubicación, el dueño, el
número de lote y las operaciones originales. Los ajustes se registran
mediante dos movimientos de inventario por tarja, vinculados a la línea
corregida. El lote del producto de destino se busca o crea en la compañía
receptora.

Se preparó `step_packing_reception_revision` 18.0.1.3.8 desde el commit
`5999caa3a7906bf9cf5cd4b8850df14cb54d043c`, con SHA-256
`442828ed964cfc23c2d53bdabfdf1aa2451f3ed89aef2ee16f01bf6556d07cf2`.

Las copias de Desarrollo, Cerro y QA-Cerro pasaron 31 pruebas cada una.
El ensayo del caso en Cerro comprobó dos tarjas corregidas por 701,10 kg,
una tercera tarja con su producto anterior, los 385 envases de la recepción
y cuatro movimientos de ajuste sin valoración.

Durante la intervención se creó un anticipo en borrador que incluye las
tarjas. La copia fresca reprodujo el bloqueo y el ensayo de cancelación
mostró que el historial de la proforma se conserva. Se revirtió el ensayo.

El asistente quedó publicado y verificado en Desarrollo, Cerro El Plomo
y QA-Cerro El Plomo con el mismo paquete. En Cerro quedó pendiente la
corrección de los datos hasta resolver el borrador activo.
