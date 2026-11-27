# Alta de liquidaciones desde el menú original de SyS

El operador abre **Nómina → Recibos de nómina → Todos los recibos de nómina → Nuevo**. Al elegir al empleado, el formulario selecciona el contrato vigente y la estructura registrada en su tipo de contrato. Trae las entradas de trabajo del período con sus tipos originales. Un cambio de fecha conserva las entradas manuales que ya digitó el operador. Un recibo cerrado sigue abriéndose con la misma ficha y la misma identidad.

La copia independiente U48D arrancó con los 193 módulos de la entrega U46R. Sólo `step_payroll_oca_sys_history` pasó de `18.0.1.6.1` a `18.0.1.6.2`. El archivo de nueve piezas mide 61.440 bytes. Su SHA-256 es `e1f3d645ce6ca3b1c967114c72efb6db8c33c8e70c391d258caf6eb58ec27642`. El respaldo de partida conserva su firma `35dfde4c6734efcb9575d7957381d06d1874326d245605b11d7d84e4f08942da`.

## Recorrido de los operadores

| Comprobación | Resultado en la copia |
| --- | --- |
| Todos los recibos y Por pagar | Los menús 951 y 952 conservan sus acciones 1420 y 1418. Las dos abrieron la lista y la ficha 5018 en las 13 empresas del primer operador y las 12 autorizadas del segundo. La decimotercera empresa mantuvo la denegación para este último. |
| Alta con ausencia aprobada | Una aprobación simple y una doble incorporaron ocho horas cada una. Ambos operadores crearon desde la ficha original un borrador con dos tipos de día y una entrada manual. Al guardar y reabrir, el contrato, las horas, la suma y el tipo de entrada conservaron sus valores. |
| Calcular y confirmar desde el alta | Cada operador creó cinco recibos con los contratos reales de octubre. Los diez reprodujeron la huella completa de las líneas calculadas a partir de las entradas de trabajo vigentes. Se confirmaron, abrieron su asiento nuevo y generaron el HTML de la impresión 1431 con la identidad de su línea imprimible. |
| Recibos históricos | El primer operador leyó 765 recibos y 90 advertencias, el segundo 763 y 88. Ambos conservaron acceso a 702 enlaces contables y a las tres marcas de neto negativo. Abrieron el asiento, las entradas de trabajo y la acción original 1431 en las 12 empresas con recibos cerrados. |
| Nómina Chile | En nueve pruebas financieras se mantuvieron los resultados de referencia. De los 133 casos de las 12 empresas con nómina cerrada, 130 calcularon y confirmaron el asiento como en el origen y tres reprodujeron el rechazo original. Las mismas 33 diferencias respecto de los importes pagados ya constaban en el control nativo. |

La ficha conserva los accesos a asistencias, gastos, entradas de trabajo, impresión, pagos y asientos con los permisos del usuario. Para los netos negativos presenta las tres actividades originales y las marcas almacenadas. El botón **Ver actividades de neto negativo** permite consultar el seguimiento. El ensayo nativo posterior comprobó que «Reporte» genera una deducción, recalcula el borrador y retira las marcas del trabajador. Esa operación económica sigue pendiente en .6.2. [Ensayo original de netos negativos](COMMUNITY_SYS_NETO_NEGATIVO.md) Planificación y deducciones salariales tenían cero filas vinculadas y carecen de proveedor activo en este registro. El exportador reservado al superusuario tampoco tiene proveedor. El informe de pago operativo del usuario conserva su propia acción.

## Preservación y reproducción

La restauración de U48D comprobó las 609.137 filas, las 861 secuencias y los 2.708 archivos físicos de la entrega. Al terminar, las 1.141 tablas conservaron todas sus filas de negocio. Las 20.338 definiciones de campo, incluidas sus traducciones, siguieron idénticas. Se cotejaron asimismo las 12.035 columnas, 5.826 restricciones, 2.490 índices, 26 vistas y los permisos del catálogo completo. La huella es `a2535d3213a101a03297564d282b0aa2a2f6940f2fbc5073a2b707c3797b2e4d`.

La actualización oficial añadió 23 identificadores de su módulo, registró dos dependencias previamente instaladas y programó una tarea de mantenimiento. El núcleo actualizó marcas de auditoría de módulos y de una vista. Las arquitecturas de las 4.720 vistas y todas las identidades originales siguieron iguales. Las pruebas de borradores y de asientos se revirtieron y sus secuencias de ensayo avanzaron normalmente.

Las pruebas usaron el simulador de formularios de Odoo, las llamadas de lectura y guardado del cliente web y los métodos de los botones bajo las cuentas originales. El recibo de formularios tiene SHA-256 `f780d6ac33baa52ac9a921396d33644c50cb4c5d4cec39a27d1bce8b876e3a0d`. El de las diez confirmaciones es `879d0b45398ea4744585aa1730e0f40ff86f091b43856b5e46e7d6ead45c062e`. El cotejo financiero es `088e4ffb3d54b7a1a9b91f835ddb9fe7568aafb94be2304a048744eea3b8c04f` y el control final `f3733c1567cced4fbb6fe5774b68aecdbcf6fe9efa5afe6399f81d4a66eed652`.

El ejecutor `tools/community/prepare_sys_payslip_form_trial.py` restaura el respaldo íntegro U46R y genera el mismo paquete desde el proveedor original sellado y los archivos del repositorio. En el entorno WSL privado se usa `SYS_PAYSLIP_FORM_FINAL=1`, primero con `--restore` y después con `--upgrade`. `tools/community/check_sys_payslip_operator_form.py` ejecuta `form`, `payroll`, `october` y `postflight` con la raíz privada de referencias. Cada operador usa su compañía autorizada. El servicio, la base y los objetos de esta prueba se mantuvieron en RAM, sin salida de red.
