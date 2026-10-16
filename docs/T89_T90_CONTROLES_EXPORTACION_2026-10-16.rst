T89 y T90 Control de documentos y naves
=====================================

Alcance autorizado: Desarrollo y Cerro El Plomo. Adjuntos de T89 3356/3357
y T90 3358/3359; respuestas humanas 9471 y 9476. Se agregan funciones en
código, sin Studio, sobre el embarque, nave, puerto y documentación nativos.
No se duplican sus maestros ni se copian documentos comerciales.

T89
---

Control / Panel de documentos muestra las doce siglas y sus fechas/plazos.
El maestro solicitado permite administrar días desde zarpe y recepción de
aduana; los valores iniciales siguen el adjunto. Se conserva la tabla
``step.export.shipping.document`` y sus IDs, estados, copias e instrucciones.
La inicialización posterior, versionada y probada en ambas copias, añadió
únicamente los tipos faltantes: 43 filas en cuatro embarques de Desarrollo
y siete filas en un embarque de Cerro. Conservó íntegros los cinco documentos
previos de cada destino y todos los valores comerciales de los embarques.
Odoo actualizó únicamente su usuario y fecha de auditoría al añadir la relación.
El instructivo también permite completar las líneas faltantes sin duplicarlas.

La pestaña Control documentos usa esa misma relación. Hay fechas de creación,
recepción, envío y evidencia manual. El correo conserva mensaje y adjuntos
de un envío exitoso. Impresión, nota interna, correo en cola o fallido no
acreditan envío. Proforma e Invoice disponen de preparación de correo con
su PDF; la factura contable usa el envío nativo. Los demás documentos se
identifican en el compositor del instructivo. No se envían correos reales
durante esta entrega. Las pruebas interceptan SMTP antes de toda conexión.

T90
---

La aplicación A dónde va la lancha y Control / Panel de naves permiten
filtrar temporada, embarque, contenedor y nave, y elegir fecha de consulta.
Transit time se calcula ETA menos ETD; si se edita, se actualiza ETA desde
ETD. Se calcula estado por zarpar, en tránsito, arribado o revisar fechas.
En la fecha ETA ya se considera arribado, con cero días arribado. El umbral
de proximidad es configurable por empresa y por defecto siete días; siete
o más es amarillo y menos de siete celeste, como en el ejemplo del adjunto.
Se siguen los ejemplos ETD + tránsito = ETA, evitando la fórmula inconsistente
de una nota de la planilla que restaría tránsito una segunda vez a ETA.

El mapa teórico interpola sobre rutas explícitas y puntos de navegación,
con coordenadas verificadas en el puerto nativo. No dibuja posiciones
inventadas para embarques sin ruta. El mapa base Natural Earth 110m se
sirve localmente y es de dominio público:
https://www.naturalearthdata.com/about/terms-of-use/

El usuario solicitó además elegir e implementar un proveedor AIS, idealmente
gratuito. Se seleccionó AISStream por su API gratuita y filtrado por MMSI.
No proporciona SLA ni replay durable; la cobertura no garantiza recepción
continua en alta mar. Se comparó con AISHub, que requiere aportar un receptor,
y VesselFinder/Datalastic, cuyos API operativos son pagados.

* https://aisstream.io/
* https://aisstream.io/documentation/
* https://www.aishub.net/terms
* https://www.vesselfinder.com/vessel-positions-api
* https://datalastic.com/pricing/

El colector persistente usa WSS del lado servidor, compresión, reconexión
con espera progresiva, hasta 200 MMSI exactos por suscripción y credencial
solo en ``/etc/steps/aisstream.env``. Nunca expone la clave al navegador.
Dos servicios, uno por destino, quedan dentro del límite publicado de tres
conexiones por cuenta/IP. No vincula naves por coincidencias de nombre.
Se rechazan coordenadas inválidas, lecturas sin fecha, futuras y anteriores
a la última recibida. El mapa distingue estimación, lectura AIS vigente,
lectura antigua y ausencia de datos. AIS es la última lectura recibida,
no una reconstrucción histórica de la fecha seleccionada para el estado.

La creación/activación de una clave AISStream y la obtención de una lectura
real son requisitos de cierre integral de T90. Una prueba simulada no los
sustituye. El instalador conserva toda clave existente y no activa el
servicio sin credencial.

Pruebas, publicación y estado al cierre
-------------------------------------

Paquete final inmutable: commit 5827240cf830a49827c3d502358c62c47ee6660e,
versión 18.0.1.0.1, SHA256
1f6fce39e92f3a5f7516a6b49474695192c56f36beb478cc9607ea4f8ba149b8.
Cuatro pruebas funcionales pasaron en cada copia de destino: documentación,
correo interceptado antes de SMTP, fechas/rutas y recepción/antigüedad AIS.
El mismo archivo se publicó en ambos destinos bajo exclusión compartida y
overlays privados, sin downgrade. Se comprobaron versión y registro después
de publicar y se repitieron las cuatro pruebas transaccionales con rollback.

Respaldos previos al despliegue:

* /opt/steps_backups/management_development_20261016T211205Z
* /opt/steps_backups/management_cerro_20261016T211334Z

La revisión en navegador detectó que el empaquetado original conservaba fecha
cero en los recursos, impidiendo renovar la URL de assets. El procedimiento
versionado refresh_release_assets.py se probó en ambas copias antes de su
ejecución en vivo. Solo ajustó las fechas de los recursos privados al commit;
verificó los hashes completos antes y después, sin alterar bytes del paquete.
Se corrigió además el empaquetador para futuras entregas. El paquete final
publicado no se reconstruyó. Los textos correctos se verificaron en navegador.

La inicialización documental pasó primero en cada copia con rollback y luego
en vivo, con nuevos respaldos:

* /opt/steps_backups/document_control_development_20261016T212546Z
* /opt/steps_backups/document_control_cerro_20261016T212606Z

Se verificaron visualmente los dos paneles, los menús y la pestaña Control
documentos con sus doce filas en ambos ambientes. Se comprobó el filtro de
fecha en Desarrollo: en ETA el embarque resulta arribado con cero días.
Capturas, logs, certificados y hashes de evidencia se conservan fuera del
checkout en ~/.codex/local-artifacts/t89-t90-20261016/visual-review.json.

T89: resuelto, nota interna 9477. T90: en progreso, nota interna 9478; panel,
mapa teórico e integración implementados. Los servicios AIS quedaron preparados
e inactivos. Sigue pendiente la autorización humana solicitada para vincular
AISStream con los datos públicos de GitHub fjcaroe y crear/guardar la clave
privada del servidor. No se autorizó el OAuth ni se generó una clave. La
recepción real no se ha comprobado y T90 no se cerró. Los embarques actuales
carecen de MMSI/ruta completos; se muestra esa ausencia sin inventar posiciones.
No se enviaron notificaciones de cierre ni correos a clientes.
