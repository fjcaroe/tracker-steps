# Cierre Helpdesk PreviRed — tickets 9 y 11 a 15

Fecha de validación final: 10 de septiembre de 2026. Base productiva: `SyS`.

## Casos comprobados con datos reales

- **#9 Marcelo Soto, Los Lingues:** campo 29 = 11.993; campo 94 = 4.851;
  campos 97 y 98 = 0; RIMA campo 92 = 673.750.
- **#11 Félix Gajardo, mayor de 65 activo:** AFP base = 335.536; AFP
  empleador, SIS, Expectativa de Vida y Rentabilidad Protegida = 0, tanto
  antes como después de recalcular la liquidación en una transacción
  revertida.
- **#12 Filomena Muñoz:** campo 93 idéntico (`1`) en la línea principal y la
  anexa.
- **#13 Lorena Pereira, EMCA:** SIS campo 29 = 12.317; Expectativa de Vida
  campo 94 = 4.982; campos Mutual 97 y 98 = 0; RIMA = 691.941. El segundo
  caso del ticket, Valentina Parada, quedó validado y cerrado en el #18.
- **#14 Karen Flies:** el horario real de 24 horas queda como jornada parcial
  (`campo 93 = 2`) en la principal y la anexa, aunque la base productiva
  conserve una marca histórica de jornada completa.
- **#15 Celestina Peñaloza:** campo 98 corregido de 4.159 a 4.076, que
  corresponde a `438.229 × 0,93 %`; la RIMA no se suma a la Mutual.

## Despliegue final

`step_hr_previred 18.0.3.8.4` quedó en Demo-Sys y producción SyS. Las dos
pruebas dirigidas nuevas pasaron sin fallos en Demo-Sys; la actualización de
SyS terminó sin errores. Ambos servicios quedaron activos y respondieron HTTP
200. Respaldos previos:

- Demo-Sys:
  `/opt/steps_backups/ticket14_15_previred_18_0_3_8_4_20260910-014556/demosys`.
- SyS:
  `/opt/steps_backups/ticket14_15_previred_18_0_3_8_4_20260910-014648/sys`.

Los cambios están integrados en `develop`.
