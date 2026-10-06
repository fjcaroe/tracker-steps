Productores: recorrido con datos de prueba en Desarrollo
=======================================================

Acceso y recorrido
-----------------

Abrir https://desarrollo.stepsapp.cl/odoo/action-2062 (Productores / Inicio).
Los datos agregados se identifican con ``PRUEBA``. Los indicadores de Inicio
incluyen además los registros anteriores del ambiente.

* Maestros / Productores: ``PRUEBA - Agrícola Valle Claro`` y
  ``PRUEBA - Huertos del Sur``, cada uno con su fundo relacionado.
* Planificación / Estimaciones: dos cosechas vigentes, con cuatro semanas
  de entrega cada una, y una nueva versión editable de Valle Claro.
  El volumen previsto es 8.000 kg exportables a proceso y 4.000 kg embalados.
* Planificación / Contratos de compra: ``PRUEBA/CTR/01`` y
  ``PRUEBA/CTR/02``, ambos confirmados, con dos cuotas cada uno. El primero
  tiene su asiento de anticipo; el segundo permite probar Contabilizar.
  Se respetan las unidades de cada producto: kg para fruta base y cajas
  de 5 kg para fruta embalada.
* Control Contratos: precios FOB de 6,50 USD/kg, tarifas por productor,
  cuotas y dos preliquidaciones calculadas. Valle Claro muestra fruta por
  entregar, por embalar, por exportar y liquidada; Huertos del Sur muestra
  recepción embalada y saldo pendiente. Los retornos proyectados son
  36.161 USD y 19.320 USD, respectivamente, después de anticipos pendientes.
* Control fruta: una recepción a proceso de 3.000 kg en dos tarjas y una
  embalada de 1.000 kg. ``PRUEBA/OT/01`` está cerrada: 1.000 kg a proceso,
  800 kg exportables y 200 kg de merma. ``PRUEBA/OT/02`` está validada con
  materiales aprobados y existencias disponibles, para continuar el cierre
  desde la pantalla. La OP, las tarjas y la lista de materiales están vinculadas.
* Liquidación: un embarque de 400 kg con liquidación de recibidor validada,
  FOB de 2.170 USD y liquidación de productor ``PRUEBA/LIQ/01`` validada,
  con neto de 1.833 USD. ``PRUEBA/LIQ/02`` permanece generada, con neto de
  6.250 USD, para revisar tarifa, tarja y descuento.

Los contactos, direcciones y referencias documentales son ficticios. No se
introducen RUT, correos ni teléfonos reales. La factura interna usa un diario
exclusivo de QA sin documentos latinoamericanos; la guía del modo Tercero,
DUS, BL e IVV están rotulados ``PRUEBA-SIN-VALOR``. No se ejecuta emisión
fiscal, mensajería ni servicios externos. Las liquidaciones de productores
quedan para revisión, sin facturas fiscales de proveedores ficticios.

Carga y conservación
--------------------

``tools/ops/seed_producer_sample.py`` utiliza modelos nativos, relaciones
existentes y botones del flujo para generar los estados. Reutiliza los
maestros inequívocos de Cerezas / Santina, las cuentas y el diario permitido
de anticipos; crea una temporada, productos y registros ficticios separados.
No cambia parámetros contables de la empresa ni listas de diarios permitidos.
No crea modelos, campos, vistas, usuarios ni permisos de Studio.

``tools/ops/manage_producer_sample.py`` restringe la operación a Desarrollo y
copias privadas validadas. Ensaya la transacción completa con rollback,
comprueba que todas las filas de negocio anteriores mantienen su contenido
(incluidos importes y fechas de escritura) y prueba una segunda ejecución
sin duplicación ni cambios. La carga obtiene el bloqueo compartido,
rechaza upgrades concurrentes, exige el mismo script y origen de módulos,
guarda un respaldo y confirma una única transacción. Los mensajes y
seguidores automáticos se desactivan por contexto.

La referencia de carga queda en ``steps.qa.productores.walkthrough.v1`` y los
identificadores en el namespace ``steps_qa_productores_walkthrough``. Una
ejecución posterior conserva los cambios manuales realizados al probar;
no borra ni reinicia los ejemplos. Si se eliminó un registro, requiere
auditar el conjunto antes de repetirlo.

Fuente del cargador: ``1406702``. Ensayo exitoso en
``MANAGEMENT_QA_DEVELOPMENT_sample_fruit_1006``; aplicado y vuelto a leer
en ``LAB_TAREAS``. Respaldo previo a los datos:
``/opt/steps_backups/producers_sample_development_20261006T183455Z``.
Evidencia y manifiesto privado: ``/opt/steps-validation/producers_sample_20261006``.

Corrección encontrada al ensayar
-------------------------------

``action_prepare_fruit_stock`` confirmaba movimientos con fusión automática.
Dos tarjas del mismo producto podían eliminar el movimiento recién creado y
provocar ``MissingError`` al continuar. Se confirma con ``merge=False`` para
mantener el vínculo individual de cada tarja y su movimiento.

Se añadió una prueba funcional que prepara y valida la recepción de dos
paquetes del mismo producto, comprobando las existencias y kilos por paquete.
El addon ``step_inventory_packing`` 18.0.1.2.2 pasó nueve pruebas sin fallos ni
errores y la preservación de datos en una copia fresca de Desarrollo.
El paquete inmutable ``0b611a824a5494b20546a6e5bbeb21924947d5dd`` se publicó
únicamente allí, con overlay privado y respaldo
``/opt/steps_backups/management_development_20261006T183146Z``.
SHA-256: ``2ee3657b66647d77034b68b3fcddbde0e9643fa1c37fbcd7b0a450e5f73484fb``.

La comprobación en navegador confirmó los indicadores de Inicio (3 productores,
3 fundos, 3 estimaciones vigentes y 2 liquidaciones abiertas, contando datos
previos), el fundo relacionado, las liquidaciones de ambos productores,
las cuatro etapas de la preliquidación y ambas OT con sus estados. Capturas
privadas en ``~/.codex/local-artifacts/producers-sample-20261006/``.
