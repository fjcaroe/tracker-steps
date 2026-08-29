# Steps Maquinaria

Módulo Odoo 18 para registrar horas máquina agrícolas, valorizar cada uso por
ocho conceptos, contabilizarlo con distribución analítica y conciliar costo
real versus estándar.

El vínculo con OT-BPA vive en `step_bpa_irrigation`, que depende de este
módulo. Esta separación evita ciclos de dependencias y permite instalar
Maquinaria por sí sola.

La evidencia funcional y de despliegue está en
`docs/MACHINERY_RELEASE_EVIDENCE.md`.
