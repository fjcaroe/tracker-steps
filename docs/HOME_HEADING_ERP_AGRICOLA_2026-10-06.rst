Encabezado comercial de Steps: ERP agrícola
==========================================

Pedido: cambiar el H1 de https://stepsapp.cl/ a
«ERP agrícola para gestionar tu campo en Chile».

Código y paquete
----------------

* step_demo_homepage 18.0.2.5.2.
* Commit probado: 8e957a84192d8804feaad3de20e974c6e12dd8f9.
* SHA-256 del paquete:
  3eb7584257f14b179b13a56f11d49a7bd57456a54489214dc14da7e8143d0eb2.
* Rama propia: codex/homepage-erp-agricola. Integrado en
  codex/home-commercial-20261001 y codex/ambientes-canonicos-reparacion.

Se conservó el contenido público vigente del producto. La migración guarda
las variantes publicadas y sus traducciones antes de recargar XML y las repone
antes de cambiar únicamente el H1 con id steps-title. Esto evita que una
migración anterior reemplace las diferencias intencionales de Desarrollo,
incluidas sus secciones de aplicaciones móviles. Se mantienen IDs, fotos,
enlaces, textos restantes y metadatos de las vistas públicas. El dato temporal
de preservación se elimina dentro de la misma transacción.

Verificación y publicación
--------------------------

* Copias privadas frescas:
  MANAGEMENT_QA_DEVELOPMENT_homeheading06b y MANAGEMENT_QA_STEPS_homeheading06b.
* Actualización del paquete exacto y comprobación del módulo realmente cargado.
* Comprobación de las variantes de idioma y el título normalizado completo.
* Servidor HTTP privado por copia: portada renderizada, 20 soluciones,
  texto fuera del H1, enlaces e imágenes idénticos a la portada original de
  cada destino. Se compara el contenido completo, no solo el estado HTTP.
* Filas e importes contables idénticos antes/después de actualizar las copias.
* Desarrollo actualizado y verificado por HTTPS. Respaldo:
  /opt/steps_backups/management_development_20261006T140313Z.
* Steps / karo_consultorias actualizado con el mismo paquete probado.
  Respaldo: /opt/steps_backups/management_steps_20261006T140404Z.
* Verificación posterior en Steps: versión 18.0.2.5.2 cargada desde su overlay
  privado, portada HTTPS renderizada con el H1 exacto y el resto de contenido,
  enlaces e imágenes conservados. Revisión visual en navegador realizada;
  captura privada stepsapp-heading.png.
* El primer acceso tras reiniciar Steps respondió 502 durante el arranque.
  Se repitió únicamente la verificación, sin volver a actualizar la base;
  la portada y el módulo pasaron las comprobaciones posteriores.

El gestor usa overlays privados y /run/lock/steps-environments.lock, respalda
base/configuración y rechaza downgrades, cambios de fuente/configuración o
upgrades concurrentes. Las copias desactivan cron y correo.

La referencia Steps mantiene un problema previo de steps_transport 18.0.1.5,
instalado sin manifest en sus rutas de addons. La comprobación de portada
reconoce solamente esa versión y ausencia de fuente auditadas; no instala,
elimina ni repara Transporte. Desarrollo mantiene la advertencia previa
steps_api. No se ignoran otros errores al actualizar o verificar este paquete.

Evidencias privadas: ~/.codex/local-artifacts/home-heading y
/opt/steps-validation/management_{development,steps}_homeheading06b.
No se modifica Search Console ni se promete una posición concreta en Google.
