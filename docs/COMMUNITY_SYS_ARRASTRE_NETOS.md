# Aplicación de netos pendientes en Nómina Chile de SyS

El botón **Reporte** de la ficha de liquidación aplica al borrador el saldo marcado del trabajador en la empresa seleccionada. La prueba ejecutó los tres casos históricos con las cuentas y los permisos ordinarios de dos operadores de SyS, tanto en el producto original U40RP como en la restauración Community U49F. Se usaron las tablas originales de cada copia y se revirtió cada operación al terminar. Los originales cerrados conservan su ficha y su acceso a las actividades históricas.

| Acción del operador | Resultado en los tres casos |
| --- | --- |
| Abrir el recibo cerrado | El botón económico está oculto. |
| Crear el siguiente borrador y pulsar **Reporte** | Se crea una entrada del tipo original `DEDUCTION`, sin etiqueta individual, por el valor absoluto de la suma mostrada. El recibo queda en verificación. La acción genera cero actividades, mensajes y asientos. |
| Calcular primero y volver a leer el recibo en verificación | La primera lectura programa una actividad del tipo histórico para el responsable del contrato, con vencimiento en la fecha del operador. Releer conserva una sola actividad. |
| Pulsar **Reporte** después de abrir la verificación | Se aplica la misma deducción, se completa esa actividad y se registra un mensaje de cierre. La contabilidad sigue sin asiento. |
| Volver a invocar la operación después de aplicarla | Se mantienen el importe, la entrada ya creada y las marcas despejadas. |

Los tres casos despejaron una, dos y dos marcas respectivamente. En el caso retrospectivo, la suma original incluía un recibo marcado cuyo período empezaba después de abrirse el período del borrador. La comparación conserva esa conducta. Los dos operadores obtuvieron las mismas 13, 18 y 17 reglas en ambos motores. Se cotejaron identidad de regla, código, importe, cantidad, tasa, total y tipos de días. Las entradas anteriores conservaron sus valores. En dos casos el original actualizó campos de auditoría de ausencias durante el cálculo. Sus datos de negocio permanecieron iguales. [Prueba comparativa de la operación](../tools/community/check_sys_negative_net.py)

## Protección de los históricos

El módulo `step_payroll_oca_sys_history` pasa de `18.0.1.6.2` a `18.0.1.6.3`. Mantiene sus cinco dependencias declaradas y utiliza los maestros originales de deducción y actividad. El actualizador verifica como propietario el cuerpo de la función histórica instalada y prepara la excepción específica antes de la actualización oficial de Odoo. La excepción sólo se activa cuando la nueva versión figura como instalada. La cuenta del servicio conserva sus permisos.

La operación bloquea los recibos del trabajador y comprueba su acceso de escritura. Para retirar la marca de un recibo cerrado, la protección exige una deducción nueva de la transacción en una liquidación abierta del mismo trabajador y empresa, el maestro original, el operador y el valor exacto del saldo. Los importes históricos permanecen protegidos. Una falla de cálculo después de insertar la deducción revierte tanto la entrada como todas las marcas. La prueba independiente intentó además despejar una marca directamente, modificar un importe y eliminar un recibo cerrado. Las tres escrituras fueron rechazadas. [Migración del control de escritura](../step_payroll_oca_sys_history/migrations/18.0.1.6.3/post-payroll-history.py) · [Prueba de reversión e integridad](../tools/community/check_sys_negative_protection.py)

## Entrega y restauración

La regresión de 12 empresas reprodujo los nueve escenarios financieros, 130 cálculos y confirmaciones, y los tres rechazos del motor original. Coincidieron las 2.098 líneas calculadas. En 33 casos ambos motores actuales difieren por igual del recibo pagado. Se cotejaron las 1.141 tablas y los 2.708 archivos físicos. La actualización modificó cinco tablas técnicas de metadatos y programación, conservó las definiciones y la activación de todos los disparadores, y los ensayos hicieron avanzar 19 secuencias. El índice de los 78 componentes recuperables tiene SHA-256 `14f85462d0840000388ad6ad6198d3587f5409e5e23a39daa769321f69889daa`.

La entrega privada `U49/recovery-kit` incorpora el respaldo anterior de 193 módulos, el TAR exacto de la actualización, el recuperador y los recibos de ambos recorridos. El TAR tiene 11 archivos y SHA-256 `246f45bee249a4a674b076de75669561499dcd9d1d8492c77a4877f4abda6dde`. El índice de la base .6.2 conserva su SHA-256 `9631b6cf47ac43a798622da746bdd044e8921cbaed356f753af161cc81ea7cfe`. El original nativo se identificó por su volcado íntegro `acfa47a2642725b22d92a0f53c40ccafc2c43205097db87dacbc987f6071de2b`. Los recibos nativos de la acción directa y la acción desde verificación tienen SHA-256 `63e4c83e78efbf4c777a1858890f792da8cd03afca28b4180b5ce273c868e820` y `dcd70c30a7f7957e8b8d6edad6e48f7f2323b4627988d3f691a088ff4dd073f4`.

En la estación local de QA puede comprobarse el paquete y restaurarlo en el entorno Focal preparado con PostgreSQL 12 y Odoo 18. La restauración comienza desde una memoria privada nueva, recupera la base .6.2 y aplica a una copia independiente el TAR probado de .6.3. [Entorno y recuperación de .6.2](COMMUNITY_SYS_RECUPERACION_LIQUIDACIONES.md)

```bash
python3 -B "$KIT/tools/package_sys_negative_release.py" verify "$KIT"
flock /dev/shm/steps-shared-qa-restore.lock python3 -B "$KIT/tools/package_sys_negative_release.py" restore "$KIT"
```
