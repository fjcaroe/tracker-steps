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
