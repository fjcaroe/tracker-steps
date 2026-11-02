"""Create a private HTML QR sheet for explicitly fictional manifest lines."""
import argparse,html,json
from pathlib import Path
import qrcode
import qrcode.image.svg
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan',type=Path);parser.add_argument('output',type=Path);args=parser.parse_args()
plan=json.loads(args.plan.read_text(encoding='utf-8'));cards=[]
for passenger in plan['passenger_trial']['passengers']:
 assert passenger['name'].startswith('Pasajero ficticio ') and passenger['document'].startswith('PRUEBA-')
 code='steps:passenger:'+passenger['id'];svg=qrcode.make(code,image_factory=qrcode.image.svg.SvgPathImage).to_string(encoding='unicode')
 cards.append('<article><h2>'+html.escape(passenger['name'])+'</h2>'+svg+'<p>Asiento '+str(passenger['seat'])+' · '+html.escape(passenger['document'])+'</p><code>'+html.escape(code)+'</code></article>')
body='''<!doctype html><html lang="es"><meta charset="utf-8"><title>Prueba de pasajeros · Desarrollo</title><style>body{margin:36px;font:16px system-ui;color:#173e35;background:#f4f7f2}h1{font-size:28px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:24px}article{background:white;border:1px solid #dbe5d7;border-radius:18px;padding:24px;text-align:center}svg{width:220px;height:220px}code{display:block;font-size:12px;overflow-wrap:anywhere}a{color:#173e35}@media(max-width:650px){.grid{grid-template-columns:1fr}}@media print{body{margin:0;background:white}article{break-inside:avoid}svg{width:180px;height:180px}}</style><h1>Cuatro pasajeros ficticios · Solo Desarrollo</h1><p>Abre <a href="https://desarrollo.stepsapp.cl/truck/">Steps Tracker en Desarrollo</a> → Hoy → Mi servicio → Preparar servicio en este teléfono. Lee el QR desde otra pantalla y confirma la subida o bajada. También puedes buscar por nombre. No son RUT reales ni reservas de transporte.</p><div class="grid">'''+''.join(cards)+'</div></html>'
args.output.write_text(body,encoding='utf-8');print('PASSENGER_QR_SHEET_READY count='+str(len(cards)))
