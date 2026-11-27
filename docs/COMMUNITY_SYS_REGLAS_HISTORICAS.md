# Por qué difieren 33 liquidaciones históricas de SyS

En 23 liquidaciones de octubre de 2026, quitar del cálculo un crédito de caja de compensación que después quedó inactivo reproduce todas las líneas del borrador actual. Las otras diez liquidaciones ya constaban como editadas en respaldos de SyS. En esas diez, los datos contemporáneos y la fórmula vigente en ese momento dan el mismo primer importe que un borrador actual. El importe guardado en la liquidación cerrada es distinto. Una de las diez también contiene el crédito que quedó inactivo.

Los dos motores, nativo y Community 18.0.1.6.1, dieron las mismas líneas en los 33 casos. El ensayo creó 33 borradores por motor, conservó los días de asistencia de cada liquidación y reprodujo las 33 huellas de cálculo y las 33 huellas pagadas de la comparación anterior. Community se ejecutó en U44VA, restaurada desde el respaldo íntegro de L. Un segundo ensayo de valor creó diez borradores más únicamente en U44VA. Las pruebas se ejecutaron con el operador original y revirtieron cada borrador.

## Primera diferencia por orden de cálculo

| Regla | ID | Secuencia | Liquidaciones | Diferencia guardada frente al borrador |
| --- | ---: | ---: | ---: | --- |
| Crédito CCAF (`CCAF_CREDITO`) | 51 | 162 | 23 | La fila desaparece del borrador |
| Colación (`COLA`) | 35 | 142 | 5 | Cambian el importe y el total de la fila |
| Sueldo base (`BASIC`) | 25 | 1 | 1 | Cambian el importe y el total de la fila |
| Movilización (`MOV`) | 36 | 143 | 1 | Cambian el importe y el total de la fila |
| Asignación familiar (`ASIG_FAM`) | 77 | 144 | 1 | Cambian el importe y el total de la fila |
| Cotización AFP (`AFP`) | 41 | 152 | 1 | Cambian el importe y el total de la fila |
| Total descuentos (`TOTAL_DSCTOS`) | 60 | 171 | 1 | Cambian el importe y el total de la fila |

En los 33 cambia el líquido `NET`. Sólo en la liquidación que empieza por `BASIC` cambian además sueldo base y bruto entre los tres totales principales. El cotejo separa por identidad de regla dos códigos iguales y distingue una línea ausente, un valor nulo y un cero. [Comparador de componentes](../tools/community/sys_rule_variance.py).

## El crédito CCAF en los respaldos

La regla 51 suma las cuotas activas del trabajador con fecha inicial anterior o igual al último día del período y fecha final abierta o posterior o igual al primer día. Los nueve respaldos originales revisados abarcan del 29 de octubre al 13 de noviembre. Para las 33 liquidaciones se encontró una copia ya cerrada cuyas líneas coincidían íntegramente con el histórico posterior.

En 24 liquidaciones, la fila de crédito guardada coincide exactamente con una única cuota activa del período. El mismo registro seguía activo en el respaldo del 13 de noviembre a las 17:56 UTC. Al restaurar la fuente posterior, su importe seguía siendo el mismo, el registro estaba inactivo y su última escritura era del 19 de noviembre. En cada uno de estos 24 períodos, la regla actual encuentra cero cuotas activas que cumplan su condición.

En los 23 casos que empiezan por el crédito, una prueba aritmética retiró esa fila de una representación en memoria del histórico, restó la cuota a `TOTAL_DSCTOS` y la sumó al líquido. La huella de **todo** el resultado coincidió con la del nuevo borrador de ambos motores. En el caso restante, cambia primero el sueldo base y también desaparece el crédito. [Cotejo de fuentes fechadas](../tools/community/trace_sys_historical_rule_sources.py).

## Las diez liquidaciones marcadas como editadas

El cálculo registrado de las 33 liquidaciones corresponde a fechas entre el 27 de octubre y el 3 de noviembre. Las primeras copias cerradas que reproducen todas las líneas son del 29, 30 o 31 de octubre o del 3 de noviembre. En las diez liquidaciones que empiezan por una regla distinta del crédito, el respaldo ya tenía `hr_payslip.edited` activo. El control identificó las mismas jornadas y las mismas identidades de contrato, trabajador, empresa y estructura.

- Para el sueldo base se cotejaron el sueldo mensual del contrato y los días de trabajo y vacaciones guardados.
- Para las cinco colaciones y la movilización se cotejaron el importe mensual, los límites de fecha del contrato y los días pagables. La revisión de noviembre incorporó una opción empresarial de días enteros y conservó la fórmula anterior en la otra rama. Las seis liquidaciones pertenecen a empresas en que esa opción estaba desactivada. La fórmula aplicada coincide con la anterior en los seis casos. [Migración de la opción de días enteros](../step_hr_contract_days/migrations/18.0.1.4.0/post-migrate.py).
- Para la AFP se cotejaron la opción de AFP, la base imponible y el indicador fechado el 31 de octubre que selecciona su regla por mes. Para la asignación familiar, la regla busca el indicador más reciente a la fecha inicial del período. Seleccionó el del 23 de septiembre. También se cotejaron el tramo, las cargas y las jornadas. Ambos indicadores conservaron sus valores entre las dos capturas.
- Para el total de descuentos se reconstruyeron las categorías de las líneas anteriores y se aplicó la regla de redondeo del total.

En cada uno de los diez casos, la reconstrucción con los datos fechados y la reconstrucción con los datos actuales produjeron el primer total observado en el nuevo borrador. Ninguna produjo el valor de la fila cerrada. La marca de edición y los importes guardados permiten distinguir esos resultados. La autoría y el motivo de esos ajustes siguen sin documentarse en las fuentes revisadas. [Verificación de fórmulas y valores](../tools/community/verify_sys_dated_components.py).

## Evidencia

| Comprobación | SHA-256 |
| --- | --- |
| Clasificación por identidad, secuencia y campos | `0cce1a0bbb1e95d96523abd696ca72fa11601a6626faa9b0fb4f49d6f58b1b8f` |
| 33 borradores en el motor nativo | `ef3df022d30c7539857d15d886e99f3b918d644104f4ee7b23f76cc1f85ca84c` |
| 33 borradores en Community | `5e8fc48090b8e2ca2ad3d422f62a2ec422821754c83ff8d77a72326e27c1be29` |
| Fechas, identidades e importes contrastados en nueve respaldos | `9d2f373f0d1e096b7187659a11f212d4e59d15432edaa81b3e08cb26477d3564` |
| Reconstrucción de las 23 liquidaciones y diez pruebas adicionales de valor | `0be6415b17aefaa52fefd73a4d6a2708066bc1b1e4289e367e86b014d73cd5dc` |
| Verificación íntegra después de los 43 borradores de Community | `3b7f140c29ab1a6e382c4c22e914bc0097264236b1b7f7aae0853a579038c55d` |

La comparación final de U44VA encontró intactas las 608.867 filas de 1.138 tablas, las 12.010 columnas con sus propiedades, las 5.816 restricciones, los propietarios y permisos de relaciones, las definiciones de secuencia y las 40 protecciones de escritura. Avanzaron tres contadores privados correspondientes a los identificadores de borradores, líneas y jornadas. En el nativo se habían cotejado también las 16 tablas de la prueba de nómina antes y después de los 33 borradores.
