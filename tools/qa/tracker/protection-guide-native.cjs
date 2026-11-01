/* Browser fixtures and recordings never modify business data. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const out=process.env.GPS_UI_OUTPUT,fixture=process.env.GPS_PROTECTION_FIXTURE==='1',record=process.env.GPS_GUIDE_VIDEO==='1';
const proof=process.env.GPS_BROWSER_PROOF?JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,'')):null;
const host=proof?.host||'desarrollo.stepsapp.cl';assert.ok(['desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl'].includes(host));assert.ok(!record||fixture);
const id='00000000-0000-4000-8000-000000000101',other='00000000-0000-4000-8000-000000000102',now=Date.now();
const samples=Array.from({length:18},(_,i)=>({id:'guide-position-'+i,recorded_at:new Date(now-1200000+i*60000).toISOString(),received_at:new Date(now-1200000+i*60000).toISOString(),lat:-33.4295-i*.0005,lon:-70.6184+i*.00003,speed_kmh:24,quality:'gps',acc:null,external_power:null}));
const baseAsset={name:'Vehículo de demostración',plate:'DEMO-01',type:'car',cost_center:null,responsible:'Operador de ejemplo',created_at:new Date(now-86400000).toISOString(),position_stale:false,signal_state:'received',motion_state:'moving',protection_state:'disarmed',last_position:samples.at(-1),device:{brand:'Coban',model:'401 · ejemplo',firmware:null,protocol:'gps103-ascii'},capabilities:{tracking:'approved',remote_start_inhibit:'not_approved'}};
let policies=[],incidents=[],writes=0,conflict=false,deny=false,failRead=false,failIncident=false,delayed=false;const forbidden=[];
const ctx={user_id:100, user:'Equipo de demostración',company_id:2,company:'Steps · Capacitación',tenant_key:'DEMO:2',role:'manager',csrf_token:'synthetic-browser-only'};
const assets=()=>[{...baseAsset,asset_id:id,protection_state:incidents.some(i=>i.state!=='closed')?'incident_open':policies[0]?.armed?'armed':'disarmed'},{...baseAsset,asset_id:other,name:'Camioneta de ejemplo',plate:'DEMO-02',motion_state:'stationary',last_position:{...samples[0],speed_kmh:0}}];
function policyFor(body){return {asset_id:body.asset_id,armed:body.armed,version:(policies[0]?.version||0)+1,contacts:body.contacts,allowed_hours_utc:body.allowed_hours_utc,zone:body.zone};}
(async()=>{
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000},...(record?{recordVideo:{dir:path.join(out,'raw-video'),size:{width:1440,height:1000}}}:{})});
 if(proof&&!fixture)await context.addCookies([{name:'session_id',value:proof.session_id,domain:host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:host,path:'/',secure:true}]);
 const page=await context.newPage(),started=Date.now(),errors=[],chapters=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),endpoint=url.pathname.replace('/steps_tracker/api/','');
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  if(url.hostname===host&&url.pathname.startsWith('/web_tracker/')&&process.env.GPS_GUIDE_DIST){const root=path.resolve(process.env.GPS_GUIDE_DIST),file=path.resolve(root,url.pathname.slice('/web_tracker/'.length)||'index.html');assert.ok(file.startsWith(root+path.sep));return route.fulfill({status:200,contentType:({'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});}
  if(fixture&&url.pathname==='/steps_tracker/context')return json(ctx);
  if(fixture&&url.pathname.startsWith('/steps_tracker/api/')){
   const params=new URLSearchParams(req.postData()||''),body=JSON.parse(params.get('payload')||'{}');
   if(req.method()==='GET'){
    if(endpoint==='fleet/snapshot')return json({items:assets(),total:2,next_cursor:null,tenant:ctx.company});
    if(endpoint==='zones')return json([]);
    if(endpoint==='view-preferences/fleet')return json(null);
    if(endpoint==='configuration')return json({items:[],reminders:[],today:new Date().toISOString().slice(0,10),receiver:{supported:true,online:true,last_seen_at:new Date().toISOString(),host:'Servidor Steps',port:5001,transport:'TCP',protocol:'gps103-ascii'}});
    if(endpoint==='security/policies'){if(delayed)await new Promise(r=>setTimeout(r,700));return failRead?json({detail:'Servicio temporalmente no disponible'},503):json(policies);}
    if(endpoint==='security/incidents')return failIncident?json({detail:'Bandeja temporalmente no disponible'},503):json({items:incidents,next_cursor:null});
    if(endpoint.startsWith('security/incidents/'))return json(incidents.find(i=>i.id===endpoint.split('/').at(-1)));
    if(endpoint.endsWith('/positions'))return json({items:[...samples].reverse(),next_cursor:null});
    if(endpoint.startsWith('assets/'))return json(assets().find(a=>a.asset_id===endpoint.split('/')[1]));
    throw new Error('Unhandled fixture read: '+endpoint);
   }
   if(endpoint==='security/policies'){
    writes++;if(deny)return json({detail:'Permiso insuficiente'},403);
    if(conflict){conflict=false;policies=[policyFor({...body,armed:!body.armed})];return json({detail:'La política cambió; vuelve a cargar'},409);}
    if(body.version!==(policies[0]?.version||0))return json({detail:'La política cambió; vuelve a cargar'},409);
    assert.equal(params.get('method'),'PUT');assert.ok(body.reason.trim().length>=5);policies=[policyFor(body)];return json({version:policies[0].version});
   }
   if(endpoint==='security/incidents'){
    assert.equal(params.get('method'),'POST');const stamp=new Date().toISOString();const row={...body,id:crypto.randomUUID(),severity:'high',state:'open',created_at:stamp,updated_at:stamp,timeline:[{id:crypto.randomUUID(),actor:'Demostración',action:'incident_opened',detail:{reason:body.reason},created_at:stamp}]};incidents.push(row);return json(row);
   }
   if(endpoint.startsWith('security/incidents/')){assert.equal(params.get('method'),'PATCH');const row=incidents.find(i=>i.id===endpoint.split('/').at(-1));assert.ok(!(row.state==='open'&&body.state==='closed'));Object.assign(row,{state:body.state,updated_at:new Date().toISOString(),timeline:[...row.timeline,{id:crypto.randomUUID(),actor:'Demostración',action:body.state,detail:{reason:body.reason},created_at:new Date().toISOString()}]});return json(row);}
   forbidden.push(endpoint);return route.abort();
  }
  if(url.hostname===host&&!['GET','HEAD'].includes(req.method())){forbidden.push(url.pathname);return route.abort();}
  return route.continue();
 });
 const control=page.locator('.protection-control'),status=control.locator('.protection-status strong'),reason=page.locator('#protection-reason');
 const go=async()=>{await page.goto('https://'+host+'/web_tracker/'+(fixture?'?asset='+id:'')+'#protection');await page.getByRole('heading',{name:'Armar o desarmar',exact:true}).waitFor();await page.waitForFunction(()=>!document.querySelector('.protection-main-action')?.disabled);};
 const confirm=async armed=>{await page.getByRole('button',{name:armed?'Armar protección':'Desarmar protección',exact:true}).click();await page.getByRole('dialog').waitFor();await page.getByRole('button',{name:armed?'Confirmar armado':'Confirmar desarmado',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await page.waitForFunction(v=>document.querySelector('.protection-status strong')?.textContent===v,armed?'Armada':'Desarmada');};
 async function chapter(title,text,action,min=10500){const at=Date.now();await page.evaluate(({title,text})=>{let e=document.getElementById('training-caption');if(!e){e=document.createElement('div');e.id='training-caption';e.style.cssText='position:fixed;bottom:0;left:0;right:0;z-index:999999;padding:18px 36px;background:#123c33f7;color:white;border-top:3px solid #d8ff62;font:16px/1.6 system-ui;pointer-events:none;box-shadow:0 -8px 30px #123c3322';document.body.append(e);document.body.style.paddingBottom='130px';}e.replaceChildren();let b=document.createElement('b');b.style.cssText='display:block;color:#d8ff62;font-size:12px;letter-spacing:1px';b.textContent=title+' · DATOS DE DEMOSTRACIÓN';e.append(b,document.createTextNode(text));},{title,text});await action();await page.waitForTimeout(Math.max(700,min-(Date.now()-at)));chapters.push({start:(at-started)/1000,end:(Date.now()-started)/1000,title,text});}
 try{
  await go();
  if(record){
   await chapter('01 · Protección','Elige el vehículo. El estado visible confirma si sus reglas de alertas están armadas o desarmadas.',async()=>{await control.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,'guide-protection.png')});});
   await chapter('02 · Motivo obligatorio','Usa un motivo rápido o escribe el tuyo. Así queda registrado por qué cambiaste la protección.',async()=>{await page.getByRole('button',{name:'Vehículo estacionado',exact:true}).click();await reason.scrollIntoViewIfNeeded();});
   await chapter('03 · Confirma el armado','Revisa el vehículo, el motivo y el nuevo estado. Confirma para activar las reglas de protección digital.',async()=>{await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.waitForTimeout(4000);await page.getByRole('button',{name:'Confirmar armado',exact:true}).click();await status.getByText('Armada',{exact:true}).waitFor();});
   await chapter('04 · Antes de salir','Para una salida autorizada, elige el motivo y confirma el desarmado. El GPS seguirá registrando el recorrido.',async()=>{await page.getByRole('button',{name:'Salida autorizada',exact:true}).click();await confirm(false);await control.scrollIntoViewIfNeeded();});
   await chapter('05 · Prueba SOS','Un SOS manual crea un incidente en esta bandeja. Esta demostración no llama ni envía mensajes a servicios de emergencia.',async()=>{await page.locator('.protection-register summary').click();await page.getByLabel('Tipo de incidente',{exact:true}).selectOption('sos');await page.getByLabel('Descripción del incidente',{exact:true}).fill('Prueba coordinada de capacitación, sin emergencia real.');await page.getByRole('button',{name:'Registrar incidente',exact:true}).click();await page.locator('.protection-case').scrollIntoViewIfNeeded();});
   await chapter('06 · Revisa y reconoce','Abre el expediente para revisar la evidencia. Escribe lo que comprobaste y reconoce el incidente antes de cerrarlo.',async()=>{await page.getByLabel('Motivo del seguimiento',{exact:true}).fill('Revisé la prueba coordinada de capacitación.');await page.getByRole('button',{name:'Reconocer incidente',exact:true}).click();});
   await chapter('07 · Cierra con un motivo','Al finalizar la revisión, documenta la resolución. El cierre conserva el historial y es independiente del estado de protección.',async()=>{await page.getByLabel('Motivo del seguimiento',{exact:true}).fill('Prueba finalizada, sin una emergencia real.');await page.getByRole('button',{name:'Cerrar incidente con motivo',exact:true}).click();});
   await chapter('08 · Ubicación en el mapa','En Mapa, selecciona un vehículo para ver su última posición, velocidad, señal y accesos a su historial.',async()=>{await page.getByRole('button',{name:'Mapa',exact:true}).click();await page.locator('.fleet-card').first().click();await page.locator('.fleet-map .gm-style').first().waitFor({timeout:45000});await page.locator('.fleet-operation-layout').scrollIntoViewIfNeeded();});
   await chapter('09 · Historial de recorridos','El historial muestra tramos GPS, paradas probables y reproducción. Las aproximaciones por calles son estimaciones, no caminos comprobados.',async()=>{await page.getByRole('button',{name:'Ver historial de posiciones',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Reproducir',exact:true}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Reproducir',exact:true}).click();await page.waitForTimeout(3500);await page.getByRole('dialog').getByRole('button',{name:'Pausar',exact:true}).click();});
   await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).click();
   await chapter('10 · Señales del equipo','En Equipo GPS puedes revisar modelo, firmware y las señales disponibles. Un dato no informado se muestra como no disponible.',async()=>{await page.getByRole('tab',{name:'Equipo GPS',exact:true}).click();await page.locator('.inspector').scrollIntoViewIfNeeded();});
   await chapter('11 · Listo para operar','Protección digital, mapa e historial funcionan por separado. Para cerrar una prueba, verifica siempre el estado final y conserva su motivo.',async()=>{await page.getByRole('button',{name:'Protección',exact:true}).click();await status.getByText('Desarmada',{exact:true}).waitFor();await control.scrollIntoViewIfNeeded();});
   fs.writeFileSync(path.join(out,'chapters.json'),JSON.stringify(chapters,null,2));
  } else if(fixture){
   await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.getByRole('alert').filter({hasText:'Escribe un motivo'}).waitFor();assert.equal(await reason.evaluate(e=>document.activeElement===e),true);assert.equal(writes,0);
   await page.getByRole('button',{name:'Vehículo estacionado',exact:true}).click();await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Cancelar',exact:true}).click();assert.equal(writes,0);
   await confirm(true);assert.equal(writes,1);await page.getByRole('button',{name:'Prueba finalizada',exact:true}).click();await confirm(false);assert.equal(writes,2);
   conflict=true;await page.getByRole('button',{name:'Vehículo estacionado',exact:true}).click();await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.getByRole('button',{name:'Confirmar armado',exact:true}).click();await page.getByRole('alert').filter({hasText:'El estado cambió'}).waitFor();assert.equal(await reason.inputValue(),'Vehículo estacionado');assert.equal(writes,3);assert.equal(await status.innerText(),'Desarmada');
   await confirm(true);assert.equal(writes,4);
   await page.locator('.protection-register summary').click();await page.getByLabel('Tipo de incidente',{exact:true}).selectOption('sos');await page.getByLabel('Descripción del incidente',{exact:true}).fill('Synthetic SOS regression test');await page.getByRole('button',{name:'Registrar incidente',exact:true}).click();await page.getByRole('button',{name:'Reconocer incidente',exact:true}).waitFor();
   await page.getByRole('button',{name:'Salida autorizada',exact:true}).click();await confirm(false);assert.equal(incidents[0].state,'open');assert.equal(await status.innerText(),'Desarmada');await page.getByText('Su revisión es independiente del armado.',{exact:false}).waitFor();
   for(const [button,reasonText] of [['Reconocer incidente','Prueba revisada'],['Cerrar incidente con motivo','Prueba terminada sin emergencia']]){await page.getByLabel('Motivo del seguimiento',{exact:true}).fill(reasonText);await page.getByRole('button',{name:button,exact:true}).click();}assert.equal(incidents[0].state,'closed');
   failIncident=true;await page.getByRole('button',{name:'Actualizar estado',exact:true}).click();await page.getByRole('alert').filter({hasText:'No se pudo consultar la bandeja'}).waitFor();assert.equal(await status.innerText(),'Desarmada');assert.equal(await page.getByRole('button',{name:'Armar protección',exact:true}).isEnabled(),true);failIncident=false;
   failRead=true;await page.getByRole('button',{name:'Actualizar estado',exact:true}).click();await page.getByText('Estado sin verificar',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Armar protección',exact:true}).isDisabled(),true);failRead=false;delayed=true;await page.getByRole('button',{name:'Actualizar estado',exact:true}).click();assert.equal(await page.getByRole('button',{name:'Armar protección',exact:true}).isDisabled(),true);await page.waitForFunction(()=>!document.querySelector('.protection-main-action').disabled);delayed=false;
   deny=true;await page.getByRole('button',{name:'Vehículo estacionado',exact:true}).click();await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.getByRole('button',{name:'Confirmar armado',exact:true}).click();await page.getByRole('dialog').getByRole('alert').waitFor();assert.equal(await status.innerText(),'Desarmada');await page.getByRole('dialog').getByRole('button',{name:'Cancelar',exact:true}).click();deny=false;
   await page.screenshot({path:path.join(out,'desktop-protection.png'),fullPage:true});await page.setViewportSize({width:390,height:844});await page.screenshot({path:path.join(out,'mobile-protection.png'),fullPage:true});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  }else{
   assert.equal(await status.innerText(),'Desarmada');await page.getByRole('button',{name:'Prueba finalizada',exact:true}).click();await page.getByRole('button',{name:'Armar protección',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Cancelar',exact:true}).click();await page.screenshot({path:path.join(out,'desktop-protection.png'),fullPage:true});await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(out,'mobile-protection.png'),fullPage:true});
  }
  assert.deepEqual(forbidden,[]);assert.deepEqual(errors,[]);console.log('PROTECTION_NATIVE_OK fixture='+fixture+' recorded='+record+' live_business_writes=0 fixture_policy_writes='+writes);
 }catch(e){await page.screenshot({path:path.join(out,'failure.png'),fullPage:true});throw e;}finally{const video=page.video();await context.close();if(video&&record)await video.saveAs(path.join(out,'steps-tracker-guide.webm'));await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
