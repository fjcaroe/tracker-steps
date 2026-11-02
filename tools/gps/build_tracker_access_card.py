"""Generate a private access card for a newly requested preview account."""
import html,json,sys
from pathlib import Path

facts=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))['cerro']
destination=Path(sys.argv[2]);assert destination.suffix=='.html'
link='https://cerroelplomo.stepsapp.cl/web_tracker/?company='+str(int(facts['company_id']))+'#live'
destination.write_text('''<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Acceso de prueba · Steps Tracker</title>
<style>body{font:18px system-ui;color:#173e36;background:#f2f6ef;max-width:620px;margin:40px auto;padding:24px}article{background:white;padding:24px;border-radius:20px}code{font-size:18px;overflow-wrap:anywhere}a{color:#173e36}</style>
<article><h1>Tu acceso de prueba a Tracker</h1>
<p>Vehículo: <strong>'''+html.escape(facts['plate'])+'''</strong></p>
<p>Usuario: <code>'''+html.escape(facts['preview_login'])+'''</code></p>
<p>Contraseña: <code>'''+html.escape(facts['preview_password'])+'''</code></p>
<p>Abre el enlace en una ventana privada e inicia sesión con este usuario para conservar tu sesión de administrador.</p>
<p><a href="'''+html.escape(link,quote=True)+'''">Abrir Tracker productivo</a></p>
<p>En el teléfono: Mi vehículo, Recorridos y Protección. Los controles de arranque de esta cuenta son una simulación y no envían órdenes físicas. La cuenta de Patricio conserva su contraseña actual.</p>
<p>Documento privado. Contiene la clave de la cuenta de prueba.</p></article>''',encoding='utf-8')
destination.chmod(0o600)
print('Private preview access card generated')
