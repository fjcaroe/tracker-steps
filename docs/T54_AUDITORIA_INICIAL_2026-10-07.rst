T54 actualización de Cerro El Plomo: auditoría inicial
=====================================================

Solicitud
---------

El usuario informó la creación del ticket 54. Su descripción pide las últimas
versiones de Nómina Simple Digital con complementos Steps, Tesorería,
Contabilidad, Actividades/Task, Cosecha/Harvest, Tracker, Exportaciones,
Productores, Packing, Guías, Inventario, Ventas, Compras, Contactos,
Maquinarias, Fletes, BPA-Riego y Gestión/Costos. Mensaje 9235 confirma la
asignación y destino Cerro El Plomo. El ticket permanece New; no se cierra
por esta auditoría.

Ambientes y fuente
------------------

Registro ~/.odoo/environments.json y operación canónica consultados. QA único:
Desarrollo, LAB_TAREAS, https://desarrollo.stepsapp.cl. Destino de producción:
CERRO_EL_PLOMO, https://cerroelplomo.stepsapp.cl, servicio
odoo18-cerroelplomo.service y /etc/odoo18-cerroelplomo.conf. Inspección por SSH
con audit_runtime.py; salida privada fuera del repositorio. Se compararon
versiones y hashes de los archivos que efectivamente cargan ambos ambientes,
además del contenido de Git. No se imprimieron ni cambiaron credenciales.

Base Git: origin/codex/ambientes-canonicos-reparacion, deed728. Worktree propio
codex/t54-cerro-20261007. Otros checkouts y cambios se conservaron.

Diferencias instaladas
----------------------

Seis módulos instalados presentan diferencias con Desarrollo; el código de
Git coincide con el código efectivo de Desarrollo para los seis:

=========================== ================ ================
Módulo                      Cerro            Desarrollo
=========================== ================ ================
step_account_treasury_batch 18.0.1.2.0       18.0.1.4.1
step_demo_homepage          18.0.2.4.1       18.0.2.5.2
step_dispatch_guide         18.0.1.0.0       18.0.2.0.4
step_export                 18.0.2.4.0       18.0.2.9.8
step_operations_ui          18.0.2.1.0       18.0.2.7.2
step_producers              18.0.1.0.0       18.0.1.8.2
=========================== ================ ================

Los complementos instalados step_hr_contract_days, step_hr_contract_lifecycle,
step_hr_contract_lifecycle_simpledigital, step_hr_previred,
step_hr_previred_simpledigital y step_hr_remuneration_book coinciden en versión
y código entre Desarrollo y Cerro. Esto no sustituye una comprobación del
motor del proveedor Simple Digital ni autoriza recalcular nómina pagada.

Tesorería base/agro, Contabilidad Multimoneda, Cosecha, Maquinaria, Gestión y
sus puentes instalados, Packing base, Riego y step_tracker_odoo también tienen
fuente idéntica. Los módulos Task, Harvest launcher y Tracker portal existen
en ambos ambientes con fuente igual, pero su código no está en este checkout;
no se reemplazan por carpetas elegidas por nombre o versión.

step_hr tiene código igual entre los dos ambientes pero distinto de Git,
aunque los tres manifiestos indican 18.0.1.4.0. No incluir ciegamente su carpeta
del repositorio en un paquete: hay que reconciliar la diferencia antes.

Alcance por definir
------------------

No están instalados en Cerro varios componentes que sí están en Desarrollo:
step_inventory_packing, step_packing_operations, step_packing_batch,
step_producer_fruit_flow, step_producers_integrations,
step_management_costs_tracker, step_project_agriculture_scope y
step_agro_traceability. No se deduce que toda diferencia entre ambientes deba
instalarse: Colaciones, APR, Aserradero y otras aplicaciones no forman parte
del alcance pedido. Se solicitó al usuario distinguir entre incorporar las
aplicaciones nuevas de las áreas solicitadas y actualizar solo lo instalado.

Las herramientas de promoción existentes tienen guardas por alcance. Por
ejemplo manage_freight solo publica Desarrollo y el publicador de settings
también es QA-only. No saltar esas guardas ni improvisar un upgrade de todas
las aplicaciones. Se requiere preparar el paquete con el alcance acordado,
probarlo en Desarrollo y en una copia privada fresca de Cerro, verificar
migración Studio/native de Fletes y Guías, preservación de datos, dependencias,
ausencia de downgrade y cambios concurrentes, y promover exactamente ese
paquete con respaldo, bloqueo compartido y overlay privado.

Estado
------

Auditoría de solo lectura completada. No se ejecutaron upgrades, instalación
de aplicaciones, cambios de configuración, reinicios ni publicación en Cerro.
No se enviaron comentarios al cliente ni se cambió la etapa del ticket 54.
Faltan definición de alcance, paquete probado, promoción y validación real.
