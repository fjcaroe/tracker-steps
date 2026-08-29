# Matriz Previred — campo oficial → dato del motor

Generado desde el **código de los generadores vigentes**, no deducido. Cada
celda «Origen» es la expresión exacta que produce ese campo hoy en producción.

- Especificación: formato estándar largo variable por separador. El sistema
  usa **v84** hasta julio de 2026 y **v98, agosto de 2026**, desde el período
  2026-08.
  <https://www.previred.com/documents/FormatosArchivos/FormatoLargoVariablePorSeparador.pdf>
- Blueminds (`l10n_cl_hr`): `wizard.export.csv.previred.action_generate_csv`
- SimpleDigital (`l10n_cl_simpledigital_payroll`): `/hr_payroll/previred/txt`

Regenerar tras un cambio del proveedor:

```bash
python tools/regen_previred_matrix.py
```

Tipos de origen: `rule` (línea de la liquidación), `contract`, `employee`,
`company`, `indicator`, `computed`, `constant`, `period`, `unused`.

| # | Campo oficial | Blueminds | Origen Blueminds | SimpleDigital | Origen SimpleDigital |
|---|---|---|---|---|---|
| 1 | RUT Trabajador | computed | `self._acortar_str(rut, 11)` | computed | `clean_rut[:-1] ;; "0" ;; "0"` |
| 2 | DV Trabajador | computed | `self._acortar_str(rut_dv, 1)` | computed | `clean_rut[-1] ;; "0" ;; "0"` |
| 3 | Apellido Paterno | employee | `self._arregla_str(payslip.employee_id.last_name.upper(), 30) if payslip.employee_id.last…` | employee | `normalize_name_part(name_parts[1]) if len(name_parts) > 1 else ''` |
| 4 | Apellido Materno | employee | `self._arregla_str(payslip.employee_id.mothers_name.upper(), 30) if payslip.employee_id.m…` | employee | `normalize_name_part(name_parts[2]) if len(name_parts) > 2 else ''` |
| 5 | Nombres | employee | `"%s %s" % (self._arregla_str(payslip.employee_id.firstname.upper(), 15), self._arregla_s…` | employee | `normalize_name_part(name_parts[0]) if len(name_parts) > 0 else ''` |
| 6 | Sexo | employee | `sexo_data.get(payslip.employee_id.gender, "") if payslip.employee_id.gender else ""` | employee | `'M' if gender == 'male' else ('F' if gender == 'female' else 'M')` |
| 7 | Nacionalidad | employee | `self.get_nacionalidad(payslip.employee_id.country_id.id)` | constant | `'0' if country and country.code == 'CL' else '1'` |
| 8 | Tipo Pago | computed | `self.get_tipo_pago(payslip.employee_id)` | constant | `'01'` |
| 9 | Período Desde | period | `date_start_format` | period | `period_str` |
| 10 | Período Hasta | period | `date_stop_format` | period | `period_str` |
| 11 | Régimen Previsional | computed | `self.get_regimen_provisional(payslip.contract_id)` | constant | `'AFP' ;; 'INP' ;; 'SIP' ;; 'AFP'` |
| 12 | Tipo Trabajador | unused | `"0" (uso futuro / no aplica en este motor)` | constant | `'0' ;; '2' if contract.pension_option == 'sip' else '1' ;; '3'` |
| 13 | Días Trabajados | computed | `int(self.get_dias_trabajados(payslip and payslip[0] or False))` | computed | `self._get_real_worked_days_from_payslip(payslip)` |
| 14 | Tipo de Línea | computed | `self.get_tipo_linea(payslip and payslip[0] or False)` | computed | `"0" del motor; normalizado por el core a "00"` |
| 15 | Código Movimiento de Personal | computed | `payslip.movimientos_personal` | unused | `"0" (uso futuro / no aplica en este motor)` |
| 16 | Fecha Desde | computed | `payslip.date_from.strftime("%d/%m/%Y") if payslip.movimientos_personal != '0' else '00/0…` | unused | `en blanco (uso futuro / no aplica)` |
| 17 | Fecha Hasta | computed | `payslip.date_to.strftime("%d/%m/%Y") if payslip.movimientos_personal != '0' else '00/00/…` | unused | `en blanco (uso futuro / no aplica)` |
| 18 | Tramo Asignación Familiar | rule | `self.get_tramo_asignacion_familiar(payslip, self.get_payslip_lines_value_2(payslip,'TOTI…` | computed | `segment ;; "D" ;; "A" ;; "D"` |
| 19 | N° Cargas Simples | contract | `payslip.contract_id.carga_familiar` | contract | `str(contract.family_simple_loads_count or 0)` |
| 20 | N° Cargas Maternales | contract | `payslip.contract_id.carga_familiar_maternal` | contract | `str(contract.family_maternal_loads_count or 0)` |
| 21 | N° Cargas Inválidas | contract | `payslip.contract_id.carga_familiar_invalida` | contract | `str(contract.family_invalid_loads_count or 0)` |
| 22 | Asignación Familiar | rule | `int(self.get_payslip_lines_value_2(payslip, 'ASIGFAM') if self.get_payslip_lines_value_2…` | computed | `str(int(sum(asignacion_familiar_line.mapped('total')))) if asignacion_familiar_line else…` |
| 23 | Asignación Familiar Retroactiva | rule | `int(self.get_payslip_lines_value_2(payslip, 'ASIGFARET') if self.get_payslip_lines_value…` | unused | `en blanco (uso futuro / no aplica)` |
| 24 | Reintegro Cargas Familiares | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 25 | Solicitud Trabajador Joven | constant | `"N"` | constant | `"N"` |
| 26 | Código de la AFP | contract | `payslip.contract_id.afp_id.codigo if payslip.contract_id.afp_id.codigo else "0"` | computed | `afp_code ;; "00"` |
| 27 | Renta Imponible AFP | rule | `int(self.get_imponible_afp_2(payslip and payslip[0] or False, self.get_payslip_lines_val…` | rule | `0 ;; round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred…` |
| 28 | Cotización Obligatoria AFP | rule | `int(self.get_payslip_lines_value_2(payslip,'PREV') + self.get_payslip_lines_value_2(pays…` | rule | `self._get_payslip_lines(payslip, rule_codes=['AFP', 'AFP_EMP']) or "0"` |
| 29 | Cotización SIS | rule | `int(self.get_payslip_lines_value_2(payslip,'SIS'))` | rule | `self._get_payslip_lines(payslip, rule_codes=['SIS']) or ""` |
| 30 | Cuenta de Ahorro Voluntario AFP | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `str(int(monto_cuenta2)) if monto_cuenta2 > 0 else ""` |
| 31 | Renta Imp. Sustitutiva AFP | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 32 | Tasa Pactada (Sustitutiva) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 33 | Aporte Indemnización (Sustitutiva) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 34 | N° Períodos (Sustitutiva) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 35 | Período Desde (Sustitutiva) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 36 | Período Hasta (Sustitutiva) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 37 | Puesto de Trabajo Pesado | unused | `en blanco (uso futuro / no aplica)` | unused | `en blanco (uso futuro / no aplica)` |
| 38 | % Cotización Trabajo Pesado | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 39 | Cotización Trabajo Pesado | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 40 | Código Institución APVI | rule | `payslip.contract_id.apv_id.codigo if self.get_payslip_lines_value_2(payslip,'APV') else …` | contract | `contract.institucion_apvi_apvc or "" ;; ""` |
| 41 | Número de Contrato APVI | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 42 | Forma de Pago APVI | rule | `payslip.contract_id.forma_pago_apv if self.get_payslip_lines_value_2(payslip,'APV') else…` | contract | `contract.pay_format_apvi_apc or "" ;; ""` |
| 43 | Cotización APVI | rule | `int(self.get_payslip_lines_value_2(payslip,'APV')) if self.get_payslip_lines_value_2(pay…` | computed | `f"{monto_apvi:08d}" if monto_apvi > 0 else "" ;; ""` |
| 44 | Cotización Depósitos Convenidos | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 45 | Código Institución APVC | unused | `en blanco (uso futuro / no aplica)` | contract | `contract.institucion_apvi_apvc or "" ;; ""` |
| 46 | Número de Contrato APVC | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 47 | Forma de Pago APVC | unused | `"0" (uso futuro / no aplica en este motor)` | contract | `contract.pay_format_apvi_apc or "" ;; ""` |
| 48 | Cotización Trabajador APVC | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `f"{monto_apvc_trabajador:08d}" if monto_apvc_trabajador > 0 else "" ;; ""` |
| 49 | Cotización Empleador APVC | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `f"{monto_apvc_empleador:08d}" if monto_apvc_empleador > 0 else "" ;; ""` |
| 50 | RUT Afiliado Voluntario | unused | `en blanco (uso futuro / no aplica)` | unused | `en blanco (uso futuro / no aplica)` |
| 51 | DV Afiliado Voluntario | unused | `en blanco (uso futuro / no aplica)` | unused | `en blanco (uso futuro / no aplica)` |
| 52 | Apellido Paterno Afiliado Voluntario | unused | `en blanco (uso futuro / no aplica)` | unused | `en blanco (uso futuro / no aplica)` |
| 53 | Apellido Materno Afiliado Voluntario | unused | `en blanco (uso futuro / no aplica)` | unused | `en blanco (uso futuro / no aplica)` |
| 54 | Nombres Afiliado Voluntario | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 55 | Código Movimiento de Personal (Afiliado Voluntario) | constant | `"00"` | constant | `"00"` |
| 56 | Fecha Desde (Afiliado Voluntario) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 57 | Fecha Hasta (Afiliado Voluntario) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 58 | Código de la AFP (Afiliado Voluntario) | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 59 | Monto Capitalización Voluntaria | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 60 | Monto Ahorro Voluntario | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 61 | Número de Períodos de Cotización | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 62 | Código Ex-Caja Régimen | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 63 | Tasa Cotización Ex-Caja Previsión | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 64 | Renta Imponible IPS / ISL / Fonasa | rule | `int(self.get_imponible_afp_2(payslip and payslip[0] or False, self.get_payslip_lines_val…` | rule | `min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope…` |
| 65 | Cotización Obligatoria IPS | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 66 | Renta Imponible Desahucio | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 67 | Código Ex-Caja Régimen Desahucio | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 68 | Tasa Cotización Desahucio Ex-Cajas | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 69 | Cotización Desahucio | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 70 | Cotización Fonasa | rule | `int(self.get_payslip_lines_value_2(payslip,'FONASA') if payslip.contract_id.isapre_id.co…` | rule | `min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope…` |
| 71 | Cotización Acc. Trabajo (ISL) | rule | `int(self.get_payslip_lines_value_2(payslip,'ISL')) if self.get_payslip_lines_value_2(pay…` | rule | `"" ;; self._get_payslip_lines(payslip, ['APORTE_MUTUAL']) or 0` |
| 72 | Bonificación Ley 15.386 | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 73 | Descuento por Cargas Familiares IPS | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 74 | Bonos Gobierno | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 75 | Código Institución de Salud | contract | `payslip.contract_id.isapre_id.codigo` | computed | `health_code` |
| 76 | Número del FUN | constant | `" " if payslip.contract_id.isapre_id.codigo=='07' else payslip.contract_id.isapre_fun if…` | constant | `"00000000"` |
| 77 | Renta Imponible Isapre | rule | `"0" if payslip.contract_id.isapre_id.codigo=='07' else self.get_imponible_salud(payslip …` | constant | `"00000000" ;; round(int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), prev…` |
| 78 | Moneda del Plan Pactado Isapre | constant | `"1" if payslip.contract_id.isapre_id.codigo=='07' else "2"` | constant | `"1" ;; "2" ;; "1" ;; ""` |
| 79 | Cotización Pactada | contract | `"0" if payslip.contract_id.isapre_id.codigo=='07' else payslip.contract_id.isapre_cotiza…` | constant | `"00000000" ;; f"{monto_clp:08d}" ;; f"{uf_valor:08.4f}".replace('.', ',') ;; "00000000" …` |
| 80 | Cotización Obligatoria Isapre | rule | `"0" if payslip.contract_id.isapre_id.codigo=='07' else int(self.get_payslip_lines_value_…` | constant | `"00000000" ;; self._get_payslip_lines(payslip, ['SALUD']) or "" ;; ""` |
| 81 | Cotización Adicional Isapre | rule | `"0" if payslip.contract_id.isapre_id.codigo=='07' else int(self.get_payslip_lines_value_…` | constant | `"00000000" ;; self._get_payslip_lines(payslip, ['ISAPRE_EXTRA']) or "" ;; ""` |
| 82 | Monto Garantía Explícita de Salud (GES) | unused | `"0" (uso futuro / no aplica en este motor)` | constant | `"00000000"` |
| 83 | Código CCAF | indicator | `payslip.indicadores_id.ccaf_id.codigo if payslip.indicadores_id.ccaf_id.codigo else "00"` | company | `company.caja_compensacion or "" ;; company.caja_compensacion or ""` |
| 84 | Renta Imponible CCAF | rule | `int(self.get_imponible_afp(payslip and payslip[0] or False, self.get_payslip_lines_value…` | rule | `min(self._get_payslip_lines(payslip, rule_codes=['GROSS']) or 0, previred_indicator.tope…` |
| 85 | Créditos Personales CCAF | rule | `int(self.get_payslip_lines_value_2(payslip,'PCCAF') if self.get_payslip_lines_value_2(pa…` | rule | `self._get_payslip_lines(payslip, rule_codes=['CCAF_CREDITO']) or 0` |
| 86 | Descuento Dental CCAF | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 87 | Descuentos por Leasing | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `f"{int(total_ccaf_leasing):08d}" ;; ""` |
| 88 | Descuentos por Seguro de Vida | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `f"{int(total_ccaf_seguro):08d}" ;; ""` |
| 89 | Otros Descuentos CCAF | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 90 | Cotización a CCAF de no afiliados a Isapres | computed | `field_90` | computed | `f"{cotizacion_ccaf_fonasa:08d}" ;; "00000000" ;; "00000000" ;; ""` |
| 91 | Descuento Cargas Familiares CCAF | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 92 | Renta Imponible Mes Anterior a la Licencia (RIMA) | unused | `"0" (uso futuro / no aplica en este motor)` | period | `"0" ;; self._calculate_renta_imponible_last_month(employee, contract, period_dt)` |
| 93 | Tipo de Jornada | computed | `derivado de la jornada semanal: 1 completa / 2 parcial` | computed | `valor válido del motor o derivado de la jornada semanal` |
| 94 | Cotización Expectativa de Vida | computed | `regla CEV/EXP_VIDA o renta imponible AFP × tasa vigente` | computed | `valor del motor; luego CEV/EXP_VIDA; respaldo por tasa vigente` |
| 95 | Cotización Rentabilidad Protegida | computed | `renta imponible AFP × tasa vigente desde 2026-08` | computed | `renta imponible AFP × tasa vigente desde 2026-08` |
| 96 | Código Mutualidad | indicator | `payslip.indicadores_id.mutualidad_id.codigo if payslip.indicadores_id.mutualidad_id.codi…` | company | `company.mutual ;; "00"` |
| 97 | Renta Imponible Mutual | rule | `self.get_imponible_mutual(payslip and payslip[0] or False, self.get_payslip_lines_value_…` | rule | `int(min(self._get_payslip_lines(payslip, rule_codes=['GROSS']), previred_indicator.tope_…` |
| 98 | Cotización Accidente del Trabajo (Mutual) | rule | `int(self.get_payslip_lines_value_2(payslip,'MUT')) if self.get_payslip_lines_value_2(pay…` | rule | `self._get_payslip_lines(payslip, ['APORTE_MUTUAL']) or 0 ;; ""` |
| 99 | Sucursal para pago Mutual | unused | `"0" (uso futuro / no aplica en este motor)` | unused | `en blanco (uso futuro / no aplica)` |
| 100 | Renta Imponible Seguro Cesantía | rule | `self.get_imponible_seguro_cesantia(payslip and payslip[0] or False, self.get_payslip_lin…` | period | `self._calculate_renta_imponible_last_month(employee, contract, period_dt) ;; renta_impon…` |
| 101 | Aporte Trabajador Seguro Cesantía | rule | `int(self.get_payslip_lines_value_2(payslip,'SECE')) if self.get_payslip_lines_value_2(pa…` | rule | `self._get_payslip_lines(payslip, ['AFC_T']) or ""` |
| 102 | Aporte Empleador Seguro Cesantía | rule | `int(self.get_payslip_lines_value_2(payslip,'SECEEMP')) if self.get_payslip_lines_value_2…` | rule | `self._get_payslip_lines(payslip, ['AFC_EMPLEADOR']) or ""` |
| 103 | RUT Pagadora Subsidio | unused | `"0" (uso futuro / no aplica en este motor)` | computed | `"00000000000" ;; rut_completo` |
| 104 | DV Pagadora Subsidio | unused | `en blanco (uso futuro / no aplica)` | constant | `"" ;; "0"` |
| 105 | Centro de Costos, Sucursal, Agencia | contract | `payslip.contract_id.analytic_account_id.name or ''` | contract | `"" ;; str(contract.analytic_account_id.code)[:20]  # Máximo 20 caracteres` |

## Notas de revisión — Blueminds

- **12 Tipo Trabajador** — El motor fija «0» (activo no pensionado) en vez de leer el tipo de trabajador de la tabla N°5; el campo existe en el contrato.
- **14 Tipo de Línea** — Fijo en «00». Correcto para este motor: no tiene modelo de movimientos múltiples, así que no hay anexas que informar.
- **24 Reintegro Cargas Familiares** — Reintegro de cargas familiares siempre en cero.
- **25 Solicitud Trabajador Joven** — Subsidio trabajador joven siempre «N» (tabla N°9, uso futuro).
- **64 Renta Imponible IPS / ISL / Fonasa** — Renta imponible IPS sólo cuando la institución de salud es «07» (Fonasa).
- **90 Cotización a CCAF de no afiliados a Isapres** — Cotización a CCAF de no afiliados a Isapre: se calcula como renta imponible CCAF x tasa del indicador del período.
- **93 Tipo de Jornada** — El core completa el valor requerido por la tabla N°22: 1 jornada completa o 2 jornada parcial.
- **94 Cotización Expectativa de Vida** — Se usa primero la regla salarial CEV/EXP_VIDA y, si no existe, se calcula con la tasa vigente.
- **95 Cotización Rentabilidad Protegida** — Se calcula desde agosto de 2026 sobre la renta imponible AFP con la tasa del período.
- **105 Centro de Costos, Sucursal, Agencia** — Centro de costos: el motor envía el **nombre** de la cuenta analítica; la especificación admite 20 caracteres y el validador rechaza el registro si se excede.

## Notas de revisión — SimpleDigital

- **8 Tipo Pago** — Tipo de pago fijo en «01» (remuneraciones del mes, tabla N°3).
- **14 Tipo de Línea** — El generador emite «0»; el módulo escribe el valor canónico «00» requerido por la tabla N°6.
- **23 Asignación Familiar Retroactiva** — Asignación familiar retroactiva en blanco; sólo aplica a empresas adheridas a CCAF.
- **76 Número del FUN** — Número de FUN fijo en «00000000».
- **86 Descuento Dental CCAF** — El generador nombra la variable `codigo_ex_caja_regimen_ips` pero la posición 86 de la especificación es «Descuento Dental CCAF».
- **88 Descuentos por Seguro de Vida** — La variable se llama `renta_imponible_ips_ex_caja` y transporta `total_ccaf_seguro`, que es lo que la posición 88 pide («Descuentos por seguro de vida»).
- **90 Cotización a CCAF de no afiliados a Isapres** — La variable se llama `codigo_accidente_trabajo_isl` y transporta `cotizacion_ccaf_fonasa`, que es lo que la posición 90 pide («Cotización a CCAF de no afiliados a Isapres»).
- **92 Renta Imponible Mes Anterior a la Licencia (RIMA)** — Renta imponible del mes anterior a la licencia (RIMA).
- **93-95 Reforma previsional** — El core valida/completa jornada, expectativa de vida y rentabilidad protegida conforme al perfil vigente, preservando el valor calculado por el motor cuando corresponde.
- **105 Centro de Costos, Sucursal, Agencia** — Centro de costos: el motor envía el **código** de la cuenta analítica recortado a 20 caracteres, que es lo que pide la especificación.
