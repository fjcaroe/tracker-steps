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
Los registros anteriores no se rellenan ni sustituyen durante la instalación;
el panel muestra los documentos faltantes como pendientes y el instructivo
permite completar únicamente las líneas que falten, sin duplicar las previas.

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

Estado de pruebas y publicación: pendiente.
