# Home de SyS producción

SyS producción se publica en `https://sys.stepsapp.cl/`, base `SyS`, servicio
`odoo18-sys.service`, configuración `/etc/odoo18-sys.conf`, puerto 8070.
El nombre antiguo del sitio en Odoo contiene «Demo», pero esta base es producción.
`sys.stepsconsulting.cl` no resuelve actualmente; no utilizarlo para verificar.

El módulo se carga desde `/opt/luis_odoo18/odoo_agriculture/step_demo_homepage`.
El home de referencia es `https://stepsapp.cl/`, base `karo_consultorias`, módulo
en `/opt/dev_odoo18/odoo_agriculture/step_demo_homepage`.
La base canónica del producto es `codex/home-commercial-20261001`.

## Versión 18.0.2.5.1

Preserva la portada publicada en español latinoamericano (`es_419`), incluyendo
las ediciones del constructor de sitios y las páginas públicas de soluciones.
El sitio servido contiene 20 soluciones, tres paquetes, cinco aplicaciones y
siete preguntas frecuentes. Algunas diferencias con la plantilla anterior del
repositorio son intencionales: el sitio publicado no muestra la sección de apps
móviles futuras. Este despliegue copia el home que hoy ve el público.

La migración actualiza las vistas base y sus copias activas por sitio; también
sincroniza los idiomas instalados para que una traducción antigua de `es_CL`
no conserve el home anterior. No modifica registros contables ni operativos.
El script de despliegue exige que SyS tenga un solo sitio y ningún módulo pendiente.

## Captura y preparación

Ejecutar `tools/home/capture_source.py` en `odoo-new` para exportar solamente las
plantillas públicas y el módulo de referencia. Los archivos resultantes quedan
en `/tmp/steps-home-sys-source/`; descargar a `~/.codex/local-artifacts/`, nunca
versionar dumps de bases ni datos privados. `sys_inventory.py` permite verificar
los servicios, rutas y metadatos de la portada sin imprimir secretos.

Para conservar nuevas ediciones públicas en el código:

```text
python tools/home/sync_public_home.py PUBLIC_TEMPLATES_JSON SOURCE_MODULE_TAR step_demo_homepage
```

Revisar el diff, incrementar la versión y registrar/subir el commit antes de
generar el paquete. El script actual valida explícitamente `18.0.2.5.1`.

## Publicación

Generar fuera del checkout un `git archive` del commit publicado que incluya
`step_demo_homepage` y `tools/home`. Copiarlo a `/tmp/` de `odoo-new` y comprobar
su SHA-256. Ejecutar en esa instancia:

```bash
bash /tmp/deploy_sys_home.sh /tmp/home-sys-release.tar.gz SHA256 COMMIT_COMPLETO
```

El script valida el módulo realmente resuelto por Odoo, respalda configuración,
módulo y base completa en `/opt/steps_backups/home-sys-production-FECHA_UTC/`,
detiene únicamente SyS, copia el módulo y actualiza únicamente `step_demo_homepage`.
Durante esa actualización SyS tiene una interrupción breve. La configuración
existente no se modifica.

La verificación compara texto, encabezados, enlaces e imágenes de ambas portadas,
comprueba estilos y rutas públicas, y exige que el código y las vistas de
`stepsapp.cl` permanezcan idénticos. Revisar también escritorio y móvil en navegador.
El respaldo incluye el commit exacto y el hash del paquete publicado.

## Recuperación

Si la actualización del módulo falla, el script repone su código anterior y
vuelve a iniciar el servicio; la excepción de Odoo revierte la transacción de
actualización. Si la verificación posterior falla, investigar el sitio servido
con el log y el respaldo: no restaurar automáticamente la base completa ni
sobrescribir operaciones posteriores de usuarios. El dump completo es un recurso
de recuperación controlada; antes de usarlo se debe evaluar el impacto de restaurar
todos los datos. Los respaldos contienen información privada y quedan en el servidor.

Cerrar con `python tools/git/verify_handoff.py --require-pushed`.
