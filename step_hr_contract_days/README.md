# Días de contratos parciales

Complemento de `l10n_cl_simpledigital_payroll` para contratos de Nómina Chile
que comienzan y terminan dentro del período de liquidación. El motor ya acota
la base a la vigencia del contrato, pero vuelve a descontar los días anteriores
al ingreso. Este complemento calcula asistencia sobre esa vigencia y conserva
las licencias, faltas y vacaciones normalizadas por el proveedor.

Por ejemplo, un contrato del 8 al 16 de septiembre debe tener 9 días antes de
ausencias, en vez de 9 menos 7 = 2. No modifica los demás casos ni las reglas
salariales, divisores, entradas de trabajo o fechas contractuales. Conserva la
convención de 8 horas por día usada por el motor para líneas de nómina.

Instalar en la base correspondiente y recalcular únicamente los recibos
autorizados. La instalación no modifica liquidaciones existentes ni registra
asientos o pagos. No requiere parámetros adicionales.

## Descuento de atrasos (T47, 18.0.1.1.0)

El motor del proveedor calcula la asistencia (WORK100) como 30 días menos
licencias, faltas y vacaciones, e ignora las entradas de trabajo
`LEAVECL131` («Ausentismo atrasos»). Este complemento suma las horas de esas
entradas del trabajador en el período, las convierte a días (8 h = 1 día) y
las resta de WORK100 de forma proporcional al importe ya calculado. La línea
`LEAVECL131` queda informada en los días trabajados con importe 0. Los días
previsionales para Previred no cambian (el atraso se descuenta en horas, no en
días). El descuento reduce el sueldo base y por tanto el imponible.
