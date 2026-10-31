"""Build the printable commissioning guide; never embeds real IMEI/SIM/secrets."""
from pathlib import Path
import argparse
from html import escape
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

PAGES = [
('Antes de que se lleven los equipos', [
('lead','Cuatro Coban 401C 4G + chips Entel. Destino: Steps Tracker de Cerro El Plomo productivo. Preparación: sábado 31/10; entrega: domingo 01/11; instalación: lunes 02/11/2026.'),
('alert','PENDIENTE CRÍTICO: el servidor tiene receptor Teltonika activo, pero no se encontró un receptor Coban escuchando. El destino TCP/UDP para estos equipos todavía no está confirmado. No configurar el puerto 5027 de Teltonika ni copiar un puerto de Internet.'),
('p','Esta guía permite preparar las SIM y los equipos ahora. La puesta en marcha solo termina cuando cada unidad envía posiciones reales a Steps y se ve en la compañía correcta. Un SMS con ubicación o un punto en la aplicación del vendedor no prueban esa integración.'),
('h','Orden de trabajo esta noche'),
('list',[
'Etiquetar todo como CEP-01, CEP-02, CEP-03 y CEP-04: equipo, SIM, caja y arnés. Fotografiar etiqueta y diagrama del manual.',
'Activar y probar cada SIM primero en un teléfono. Después configurar y validar un GPS completo; replicar el procedimiento en los otros tres.',
'Conservar acceso remoto por SMS: número de cada chip, teléfono administrador, clave del GPS en un gestor privado y acceso a las líneas Entel.',
'Confirmar receptor Coban, destino, protocolo y asociación. Hacer la prueba final de la página 5 antes de embalar.',
'Entregar a tu padre las fichas y el procedimiento del lunes. Identificar cualquier prueba pendiente; no marcarla como aprobada.'
]),
('h','Situación comprobada en Steps'),
('p','Consulta por SSH del 31/10/2026: módulo step_tracker_portal instalado en CERRO_EL_PLOMO. Las cuatro sociedades del portal tienen cero activos, cero GPS en inventario y cero asociaciones activas. Registrar los cuatro IMEI será necesario; poseerlos no los incorpora automáticamente a la aplicación.'),
('p','La revisión fue de lectura. No se habilitó un puerto Coban, no se registraron equipos ni se cambió la configuración de producción. El destino definitivo exige verificar el protocolo de la unidad real.'),
('h','Responsables antes de despachar'),
('p','Preparador de GPS/SIM: ____________________  Instalador: ____________________\nResponsable de receptor/Tracker: ____________________\nTeléfono de soporte y horario del lunes: __________________________________'),
]),
('SIM Entel, identidad y alimentación', [
('h','1. Probar cada chip en un teléfono'),
('list',[
'Completar activación de la línea Entel y su identificación si se solicita. Guardar número telefónico, ICCID y acceso de administración de la línea.',
'Desactivar Wi-Fi y comprobar navegación con datos móviles. Enviar y recibir un SMS con el teléfono que administrará los GPS. Verificar saldo para ambos servicios y vencimiento de la bolsa.',
'Deshabilitar el PIN de la SIM antes de ponerla en el GPS. Conservar PUK y comprobantes de recarga en un lugar privado.',
'APN de referencia oficial Entel: bam.entelpcs.cl. Si la SIM es de un plan IoT/APN privado, confirmar sus parámetros con Entel. No copiar usuario/clave de otro operador.',
'Anotar responsable, próxima recarga y fecha de vencimiento de datos. Una bolsa de solo redes sociales no acredita datos para el servidor GPS.'
]),
('h','2. Probar alimentación y recepción'),
('p','Usar el arnés, tensión y diagrama de la unidad recibida. Las publicaciones de la familia 401 muestran variantes: no deducir voltaje ni colores por la boleta. La conexión debe revisarla una persona competente; usar protección/fusible según el manual. No improvisar una fuente USB ni conectar alimentación a una salida de control.'),
('p','Primera prueba al aire libre, con vista del cielo y alimentación estable. Distinguir red móvil, recepción de satélites y envío al servidor. No aceptar una ubicación antigua o estimada por antenas como posición GPS actual.'),
('alert','Alcance de este piloto: seguimiento. Mantener la salida de corte de motor sin intervenir el circuito del vehículo y aislada según el diagrama del fabricante. No probar inmovilización durante un recorrido.'),
('h','Ficha de correspondencia - completar sin intercambiar chips'),
('table', [['Alias','IMEI (15 dígitos)','N° SIM Entel','Patente / auto'],
['CEP-01','________________','____________','____________'],['CEP-02','________________','____________','____________'],
['CEP-03','________________','____________','____________'],['CEP-04','________________','____________','____________']]),
('p','Para cada alias: guardar ICCID, foto del IMEI, variante/firmware si está disponible y ubicación de su clave privada. No escribir claves en esta hoja de entrega ni en notas visibles de Tracker.'),
]),
('SMS: secuencia de configuración', [
('lead','Referencia de la familia Coban 401. Cotejar con el manual de la caja y la respuesta del equipo antes de aplicar cambios. La boleta identifica el modelo comercial, no su revisión de firmware.'),
('p','PW significa la clave ACTUAL del GPS, sin espacios ni corchetes. No es la contraseña de Entel u Odoo. Enviar un mensaje por vez y conservar la respuesta. Si no responde, detener la secuencia y revisar línea, formato y clave; no encadenar comandos a ciegas.'),
('table', [
['Paso','Texto de referencia','Comprobación'],
['Estado','checkPW','Respuesta de estado; guardar captura privada.'],
['Identidad','imeiPW','Coincide con la etiqueta y la ficha.'],
['Posición','positionPW','Coordenadas y hora actuales al aire libre.'],
['APN Entel','APNPW bam.entelpcs.cl','Confirmación del equipo.'],
['Hora','time zonePW 0','UTC en el dispositivo; verificar hora recibida.'],
['Administrador','adminPW NUMERO_ADMIN','Número en el formato exigido por su manual; probar respuesta.'],
['Clave propia','passwordCLAVE_ACTUAL CLAVE_NUEVA','Solo si coincide con su manual. Guardar y probar nueva clave antes de seguir.'],
['Destino (bloqueado)','dnsPW HOST PUERTO\no adminipPW IP PUERTO','Completar solo con receptor Steps confirmado.'],
['Transporte','GPRSPW,0,0','TCP en el manual consultado; usar únicamente si el receptor acordado es TCP.'],
]),
('p','Si el plan requiere usuario/clave de APN, obtenerlos de Entel y aplicar el comando correspondiente del manual. El APN por sí solo no confirma que haya datos activos.'),
('h','Frecuencia, reposo y persistencia'),
('p','Acordar como objetivo del piloto posiciones cada 30 segundos en movimiento y un reporte de vida en reposo compatible con la batería y el receptor. La sintaxis para repetición ilimitada y reposo debe confirmarse con el manual real. No usar una receta con un número limitado de envíos: podría dejar de reportar antes del lunes.'),
('p','Después de configurar, hacer un ciclo normal de alimentación y repetir check y la prueba de recepción. No hacer restauración de fábrica: borraría la configuración. Tampoco actualizar firmware durante esta preparación sin necesidad comprobada.'),
('alert','HOST/IP/PUERTO, perfil de intervalos y validación de firmware siguen pendientes. Esta página no es una receta completa para enviar al equipo sin completar esos valores.'),
]),
('Alta y recepción en Cerro productivo', [
('h','Acceso y sociedad correcta'),
('p','Entrar a https://cerroelplomo.stepsapp.cl con un usuario que ya tenga administración de Tracker. Abrir Steps Tracker desde Odoo y seleccionar la compañía propietaria de los autos. Confirmar si corresponde Cerro El Plomo SpA u otra sociedad del grupo; no registrar la misma unidad en varias compañías.'),
('p','Usar Steps Tracker / Flota y Configuración. Es la flota de GPS físicos; Tracker Móvil de conductores y la aplicación del vendedor son productos distintos y no acreditan que llegue telemetría a esta flota.'),
('list',[
'Crear o seleccionar el vehículo real, con patente y nombre reconocibles. Si ya existe en Odoo, revisar su vínculo para no duplicar el maestro.',
'Agregar cada GPS por su IMEI exacto en Configuración. Completar marca Coban, modelo 401C, SIM Entel, teléfono, APN, responsable y fechas de recarga/datos.',
'Confirmar quién habilita la recepción Coban. La validación debe usar una trama real y comprobar identificación, fecha, coordenadas, velocidad y respuesta/acuse del protocolo.',
'Asociar cada GPS al vehículo correcto dentro de la sociedad seleccionada. Registrar la instalación con su hora real. La aprobación de seguimiento exige prueba; no se obtiene solo guardando el IMEI.',
'Comprobar en la flota posición reciente, hora GPS y hora recibida. El estado sin señal no significa que el auto esté detenido.'
]),
('h','Datos que deben quedar confirmados por el responsable del receptor'),
('table', [['Parámetro','Valor autorizado para estos cuatro equipos'],
['Protocolo y revisión','________________________________________________'],
['Destino del equipo (host/IP)','________________________________________________'],
['Puerto y transporte TCP/UDP','________________________________________________'],
['Receptor operativo / fecha de prueba','________________________________________________'],
['Intervalo en marcha / reposo','________________________________________________'],
['Sociedad dueña / usuario verificador','________________________________________________']]),
('alert','El puerto 5027 observado sirve Teltonika. El puerto web de Odoo y la URL de la API tampoco son receptores Coban. No dar por confirmado un puerto porque responda una página web o porque lo recomiende un listado genérico.'),
('p','El responsable debe comprobar también firewall, persistencia/reintento y enrutamiento a la compañía correcta. No se deben enviar estos IMEI al receptor legacy de otra flota ni usar datos de demostración para simular la prueba.'),
]),
('Prueba de salida: aprobar los cuatro', [
('lead','Criterios propuestos para este piloto. Hacer primero CEP-01 de punta a punta y luego repetir el mismo procedimiento con CEP-02 a CEP-04. Un equipo aprobado no certifica a los otros tres.'),
('list',[
'SMS: consulta desde el número administrador, identidad correcta y ubicación actual. Guardar hora de la comprobación.',
'Mapa: mientras alguien verifica Cerro productivo, mover el equipo de forma controlada con alimentación adecuada o hacer un recorrido corto. Confirmar varias posiciones nuevas en la trayectoria esperada.',
'Tiempo: observar al menos 10 reportes nuevos y continuidad durante 10-15 minutos con el perfil acordado. Si la frecuencia es distinta, adaptar la duración y anotarla; no aceptar un único punto.',
'Alimentación: ciclo de apagado/encendido normal según el manual y comprobación de reconexión automática sin reenviar toda la configuración. La batería interna puede mantenerlo activo: distinguir ese caso.',
'ACC: con el arnés conectado correctamente, comprobar encendido/apagado y alimentación si esos campos llegan en el protocolo. Si no están validados, anotarlo como pendiente.',
'Administración remota: repetir consulta SMS después del reinicio y conservar acceso al número. Si hay teléfono administrador de respaldo autorizado, probarlo antes de despachar.',
'Embalaje: confirmar que alias, IMEI, SIM, arnés y auto destino coinciden. Dejar la SIM probada instalada y asegurar tapa/sello según el fabricante.'
]),
('table', [['Unidad','SMS / IMEI','Mapa vivo','Reconecta','Control remoto','Resultado'],
['CEP-01','[ ]','[ ]','[ ]','[ ]','__________'],['CEP-02','[ ]','[ ]','[ ]','[ ]','__________'],
['CEP-03','[ ]','[ ]','[ ]','[ ]','__________'],['CEP-04','[ ]','[ ]','[ ]','[ ]','__________']]),
('p','Hora de pruebas: __________________   Verificador en Tracker: __________________\nPendientes por unidad: __________________________________________________\n________________________________________________________________________'),
('alert','No despachar como LISTO si falta una SIM, el acceso remoto, el receptor, la asociación o la posición real en Steps. Si deben llevarse una unidad con un pendiente, dejar constancia y prever recuperación física; no prometer resolver a distancia una SIM sin red o sin alimentación.'),
]),
('Entrega a tu padre y prueba del lunes', [
('h','Lo que debe viajar con cada equipo'),
('p','Alias visible en equipo y bolsa; auto/patente destino; arnés y diagrama de esa revisión; fusible/accesorios indicados; hoja con número SIM y referencia del IMEI; fotos antes de cerrar; contacto del responsable de Tracker. Las claves viajan por un medio privado separado.'),
('h','Secuencia en Talca'),
('list',[
'Antes de ocultarlo, conectar y revisar tensión, polaridad, alimentación permanente y ACC con un instalador competente, según el manual. Mantener sin conexión el corte de motor.',
'Esperar recepción en una ubicación con cielo visible y confirmar por teléfono que el alias correcto aparece actualizado en Cerro productivo.',
'Hacer recorrido de prueba con otra persona observando el mapa. El conductor no manipula teléfonos ni la configuración durante la marcha.',
'Parar, apagar y encender según la prueba acordada. Verificar que regresa a reportar; registrar hora y resultados.',
'Solo después cerrar la instalación y guardar fotos de ubicación, fijación y cableado. Evitar apantallar antenas y dejar datos suficientes para una reparación futura.'
]),
('h','Si falla, diagnosticar sin borrar la configuración'),
('table', [['Síntoma','Revisión inicial'],
['No responde SMS','Alimentación, línea activa, saldo SMS, cobertura, PIN y número administrador.'],
['SMS con posición, sin mapa Steps','Receptor Coban, destino/transporte, datos/APN, IMEI y asociación por compañía.'],
['Punto viejo o aproximado','Hora de captura frente a recepción; fijación GPS al aire libre; no confundir LBS con GPS.'],
['Funcionó y luego se detuvo','Reposo, número limitado de reportes, pérdida de alimentación, vencimiento de datos o reinicio sin persistencia.'],
['Mapa con otro vehículo','Detener aceptación y conciliar etiquetas, IMEI y asociación; conservar el historial.']]),
('h','Referencias y alcance'),
('p','[1] Entel, APN oficial: https://ayuda.entel.cl/hc/es-419/articles/4403105402131\n[2] Manual del fabricante, familia 401, copia de consulta: https://manuals.plus/m/6366e7f61c731118fd028d7858cecf12724a9979971073cc80ce0ab1e2c3b853\n[3] Fabricante Coban: https://www.coban.net/products.aspx?nid=3&typeid=50001\n[4] Traccar, identificación de variantes: https://www.traccar.org/clones/'),
('p','El manual de la unidad recibida prevalece sobre los comandos de referencia. Diagnóstico de servidor: lectura por SSH y código de Steps el 31/10/2026. No se certificó aún compatibilidad ni instalación física de los cuatro equipos. Conservar esta guía junto con sus fichas completadas y respuestas SMS.'),
]),
]


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    style=ParagraphStyle('body',fontName='Helvetica',fontSize=10,leading=14,spaceAfter=8,textColor=colors.HexColor('#23364A'))
    title=ParagraphStyle('title',parent=style,fontName='Helvetica-Bold',fontSize=21,leading=25,spaceAfter=16)
    heading=ParagraphStyle('heading',parent=style,fontName='Helvetica-Bold',fontSize=12,leading=16,spaceBefore=6)
    lead=ParagraphStyle('lead',parent=style,fontSize=11,leading=15)
    alert=ParagraphStyle('alert',parent=style,fontName='Helvetica-Bold',backColor=colors.HexColor('#FFF1DC'),borderPadding=9,spaceBefore=8,spaceAfter=14,fontSize=10,leading=14)
    cell=ParagraphStyle('cell',parent=style,fontSize=8.4,leading=11,spaceAfter=0)
    def para(text,s=style):return Paragraph(escape(text).replace('\n','<br/>'),s)
    story=[]
    for number,(name,blocks) in enumerate(PAGES):
        if number:story.append(PageBreak())
        story.extend([para('STEPS / CERRO EL PLOMO  |  COBAN 401C + ENTEL',heading),para(name,title)])
        for kind,content in blocks:
            if kind=='list':
                story.extend(para(str(i)+'. '+text) for i,text in enumerate(content,1))
            elif kind=='table':
                count=len(content[0]); widths={2:[140,359],3:[82,180,237],4:[49,160,135,155],6:[55,86,86,86,102,84]}[count]
                table=Table([[para(str(v),cell) for v in row] for row in content],colWidths=widths,hAlign='LEFT',repeatRows=1)
                table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#DAE7F1')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.4,colors.HexColor('#B6C5D1')),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8)]))
                story.extend([table,Spacer(1,10)])
            else:story.append(para(content,{'h':heading,'lead':lead,'alert':alert}.get(kind,style)))
    def footer(canvas,doc):
        canvas.setFont('Helvetica',8);canvas.setFillColor(colors.HexColor('#536B80'))
        canvas.drawString(48,27,'31/10/2026 | Preparación y aceptación antes del traslado | Completar valores pendientes')
        canvas.drawRightString(A4[0]-48,27,str(doc.page))
    SimpleDocTemplate(str(args.output),pagesize=A4,leftMargin=48,rightMargin=48,topMargin=33,bottomMargin=46,title='Puesta en marcha - 4 Coban 401C Entel - Cerro El Plomo',author='Steps').build(story,onFirstPage=footer,onLaterPages=footer)
    print('GUIDE_PDF_CREATED '+str(args.output))


if __name__=='__main__':main()
