#!/usr/bin/env bash
# Explicit deployment whitelist. SyS real is a separate environment, not a target.
case "${1:?Environment required}" in
  desarrollo) DB=LAB_TAREAS; CONFIG=/etc/dev_odoo18.conf; TARGET=/opt/dev_odoo18/odoo_agriculture; SERVICE=odoo18-dev.service; URL=https://desarrollo.stepsapp.cl ;;
  demo) DB=STEPS_DEMO; CONFIG=/etc/demo_odoo18.conf; TARGET=/opt/demo_odoo18/odoo_agriculture; SERVICE=odoo18-demo.service; URL=https://demo.stepsapp.cl ;;
  demo-sys) DB=STEPS_DEMO_SYS; CONFIG=/etc/odoo18-demo-sys.conf; TARGET=/opt/demosys_odoo18/odoo_agriculture; SERVICE=odoo18-demo-sys.service; URL=https://demo-sys.stepsapp.cl ;;
  cerroelplomo) DB=CERRO_EL_PLOMO; CONFIG=/etc/odoo18-cerroelplomo.conf; TARGET=/opt/cerroelplomo_odoo18/odoo_agriculture; SERVICE=odoo18-cerroelplomo.service; URL=https://cerroelplomo.stepsapp.cl ;;
  produccion) DB=karo_consultorias; CONFIG=/etc/odoo18.conf; TARGET=/opt/dev_odoo18/odoo_agriculture; SERVICE=odoo18.service; URL=https://stepsapp.cl ;;
  *) printf 'Unknown environment\n' >&2; exit 2 ;;
esac
