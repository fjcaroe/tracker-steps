/* Browser-only fixtures. No business request or physical order reaches a server. */
const fs=require('fs'),path=require('path'),assert=require('assert');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [dist,out]=process.argv.slice(2),origin='https://desarrollo.stepsapp.cl';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,timezoneId:'America/Santiago',serviceWorkers:'block',acceptDownloads:true}),page=await context.newPage();page.setDefaultTimeout(15000);
  const ids=['00000000-0000-4000-8000-000000000001','00000000-0000-4000-8000-000000000002'];let manager=false,viewer=false,stale=false,missing=false,connected=true,safe=true,commands=[],sent=0,parking=false;
  const stamp=()=>new Date().toISOString(),position=i=>({id:String(i),lat:-33.455+i*.0005,lon:-70.55+i*.0001,recorded_at:new Date(Date.now()-(12-i)*20000-(i<6?9000000:0)).toISOString(),received_at:stamp(),speed_kmh:18,quality:'gps',acc:false,external_power:true});
  const asset=i=>({asset_id:ids[i],name:i?'Segundo vehículo':'Vehículo de prueba',plate:i?'QA0002':'QA0001',type:'pickup',cost_center:null,responsible:null,created_at:stamp(),position_stale:stale,signal_state:stale?'stale':'received',motion_state:'moving',protection_state:'disarmed',last_position:missing?null:{...position(12),recorded_at:stale?new Date(Date.now()-7200000).toISOString():stamp()},device:{brand:'Coban',model:'401',firmware:null,protocol:'gps103-ascii'},capabilities:{tracking:'approved',remote_start_inhibit:'approved'}});
  await page.route('**/*',async route=>{
   const url=new URL(route.request().url());if(url.origin!==origin)return route.continue();
   if(url.pathname==='/steps_tracker/context')return route.fulfill({json:{user_id:6,user:'Cuenta de revisión',company_id:2,company:'Compañía de prueba',tenant_key:'LAB_TAREAS:2',role:manager?'manager':viewer?'viewer':'operator',csrf_token:'browser-only',vehicle_limited:!manager,can_manage_protection:!viewer,can_control_starter:!viewer,control_preview:false}});
   const prefix='/steps_tracker/api/';
   if(url.pathname.startsWith(prefix)){
    const p=url.pathname.slice(prefix.length);
    if(p==='fleet/snapshot')return route.fulfill({json:{items:manager?[asset(0),asset(1)]:[asset(0)],total:manager?2:1,next_cursor:null}});
    if(p.endsWith('/positions'))return route.fulfill({json:{items:parking?Array.from({length:9},(_,i)=>({...position(i),recorded_at:new Date(Date.now()-(9-i)*3600000).toISOString(),lat:-33.455+(i%3)*.00002,lon:-70.55,speed_kmh:0})):Array.from({length:12},(_,i)=>position(i)),next_cursor:null}});
    if(p.endsWith('/starter-control'))return route.fulfill({json:{wiring_verified:true,connected,can_operate:!viewer,safe_to_inhibit:safe,preview:false,commands}});
    if(p.includes('/starter-control/commands/')&&p.endsWith('/confirm')){const data=JSON.parse(new URLSearchParams(route.request().postData()).get('payload'));commands[0]={...commands[0],state:'confirmed',declared_result:data.observed,confirmed_at:stamp()};return route.fulfill({json:commands[0]});}
    if(p==='configuration')return route.fulfill({json:{items:[],reminders:[],receiver:{online:true}}});
    if(p==='security/policies')return route.fulfill({json:[]});
    if(p==='security/incidents'||p==='zones')return route.fulfill({json:{items:[],next_cursor:null}});
    return route.fulfill({status:404,json:{detail:'Browser fixture: unsupported path'}});
   }
   if(url.pathname.startsWith('/steps_tracker/starter/')&&url.pathname.endsWith('/command')){
    const data=new URLSearchParams(route.request().postData()),payload=JSON.parse(data.get('payload'));assert.equal(data.get('password'),'browser-only');assert(payload.present&&payload.engine_off&&payload.plate_confirmation==='QA0001');assert(payload.reason.length>=5);sent++;
    const receipt={id:'browser-command-'+sent,type:payload.type,state:'sent_unconfirmed',result:'Respuesta simulada; sin envío físico.',created_at:stamp(),confirmed_at:null,declared_result:null};commands=[receipt,...commands];return route.fulfill({json:receipt});
   }
   if(url.pathname.startsWith('/steps_tracker/costs/assets/'))return route.fulfill({status:403,json:{detail:'Sin permiso de contabilidad en la prueba'}});
   if(url.pathname.startsWith('/web/dataset/')){
    const p=route.request().postDataJSON().params;
    if(p.model==='step.tracker.asset.link')return route.fulfill({json:{jsonrpc:'2.0',result:[{id:1,asset_id:ids[0],vehicle_id:[3,'QA0001']}]}});
    if(p.model==='fleet.vehicle.log.services'||p.model==='fleet.vehicle.log.contract'){
     assert.deepEqual(p.kwargs.domain.slice(0,2),[['company_id','=',2],['vehicle_id','=',3]]);
     const common={id:1,amount:45000,currency_id:[1,'CLP']};
     const rows=p.model==='fleet.vehicle.log.services'?[{...common,date:'2026-11-01',service_type_id:[1,'Mantención de prueba'],state:'done',account_move_state:'posted'}]:
      [{...common,name:'Seguro de prueba',state:'open',start_date:'2026-11-01',expiration_date:'2027-11-01',cost_frequency:'monthly',cost_generated:7000}];
     return route.fulfill({json:{jsonrpc:'2.0',result:rows}});
    }
    const result=p.model==='res.users'?[{company_ids:[2]}]:p.model==='res.company'?[{id:2,name:'Compañía de prueba'}]:[];return route.fulfill({json:{jsonrpc:'2.0',result}});
   }
   if(url.pathname.startsWith('/steps_tracker/'))return route.fulfill({status:403,json:{detail:'Consulta no habilitada en este ensayo'}});
   const f=url.pathname==='/tracker'?path.join(dist,'index.html'):path.join(dist,url.pathname.replace(/^\/web_tracker\//,''));
   if(fs.existsSync(f)&&fs.statSync(f).isFile())return route.fulfill({path:f});return route.fulfill({status:404,body:'No external business requests'});
  });
  const nav=()=>page.getByRole('navigation',{name:'Mi Tracker',exact:true});
  const fits=async()=>assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Horizontal overflow');
  await page.goto(origin+'/tracker#live');await page.getByRole('heading',{name:'QA0001',exact:true}).waitFor();await page.locator('.gm-style').first().waitFor();await fits();await page.waitForTimeout(1400);await page.screenshot({path:path.join(out,'vehicle-mobile.png'),fullPage:true});
  await page.getByText('Costos del vehículo',{exact:true}).click();
  await page.getByRole('button',{name:'Ver costos y gastos',exact:true}).click();
  await page.getByRole('link',{name:'Mantención de prueba ↗',exact:true}).waitFor();
  await page.getByText('Contratos con cobertura en el período',{exact:true}).click();
  await page.getByRole('link',{name:'Seguro de prueba ↗',exact:true}).waitFor();
  assert(await page.getByText('Sin permiso de contabilidad en la prueba',{exact:true}).isVisible());
  await page.getByText('Costos del vehículo',{exact:true}).click();
  await nav().getByRole('button',{name:'Recorridos',exact:true}).click();await page.getByRole('heading',{name:'Tus recorridos',exact:true}).waitFor();await page.locator('.trail-embedded .gm-style').first().waitFor();assert.equal(await page.locator('dialog[open]').count(),0);await fits();await page.waitForTimeout(1400);await page.screenshot({path:path.join(out,'history-mobile.png'),fullPage:true});
  await page.getByRole('button',{name:'Últimos 7 días',exact:true}).click();
  await page.locator('.trail-playback input[type="range"][max="11"]').waitFor();
  await page.getByText('Filtros y exportación',{exact:true}).click();await page.getByLabel('Duración mínima de parada').selectOption('5');const download=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar GPX',exact:true}).click();const downloaded=await download;await downloaded.saveAs(path.join(out,'fixture-route.gpx'));assert(fs.readFileSync(path.join(out,'fixture-route.gpx'),'utf8').includes('<trkpt'));
  await page.getByRole('button',{name:'Reproducir',exact:true}).click();await page.getByRole('button',{name:'Pausar',exact:true}).waitFor();await page.locator('.trail-playback select').selectOption('250');await page.getByText('Reproducci\u00f3n pausada en un corte',{exact:true}).waitFor();assert.equal(await page.getByLabel('Posici\u00f3n en el recorrido',{exact:true}).inputValue(),'5');await page.locator('.trail-playback').getByRole('button',{name:'Continuar despu\u00e9s del corte',exact:true}).click();assert(Number(await page.getByLabel('Posici\u00f3n en el recorrido',{exact:true}).inputValue())>=6);
  parking=true;await page.getByRole('button',{name:'Últimos 7 días',exact:true}).click();
  await page.getByText('P · Reposo probable según posiciones registradas',{exact:true}).waitFor();
  assert.equal(await page.getByRole('region',{name:'Cortes del historial'}).count(),0);
  assert.equal(await page.locator('.trail-playback').count(),0);
  await page.getByText('Datos GPS para diagnóstico',{exact:true}).click();
  assert.equal(await page.locator('.trail-diagnostics div p').count(),9);
  await page.getByText('Datos GPS para diagnóstico',{exact:true}).click();
  await fits();await page.screenshot({path:path.join(out,'parked-mobile.png'),fullPage:true});parking=false;
  await nav().getByRole('button',{name:'Arranque',exact:true}).click();await page.getByText('Sin bloqueos registrados en Tracker',{exact:true}).waitFor();assert.equal(await page.getByRole('button',{name:'Restituir arranque',exact:true}).count(),0);await fits();await page.screenshot({path:path.join(out,'starter-mobile.png'),fullPage:true});
  for(const name of ['Bloquear arranque','Restituir arranque']){
   await page.getByRole('button',{name,exact:true}).click();const dialog=page.locator('.starter-dialog[open]');await dialog.waitFor();await dialog.getByRole('button',{name:'Confirmar orden',exact:true}).click();assert.equal(sent,name==='Bloquear arranque'?0:1);
   await dialog.getByLabel('Escribe la patente para confirmar').fill('QA0001');await dialog.getByLabel('Tu contraseña de ingreso a Steps').fill('browser-only');await dialog.getByLabel('El vehículo está detenido y el motor apagado.').check();await dialog.getByLabel('Estoy junto al vehículo o coordinado en este momento con el instalador.').check();await dialog.getByLabel('Motivo / resultado comprobado').fill('Prueba del navegador sin dispositivo real');await dialog.screenshot({path:path.join(out,'confirmation-'+sent+'.png')});await dialog.getByRole('button',{name:'Confirmar orden',exact:true}).click();await dialog.waitFor({state:'hidden'});await page.getByText('Orden pendiente de comprobación',{exact:true}).waitFor();
  }
  assert.equal(sent,2);await page.getByRole('button',{name:'Registrar comprobación de terreno'}).first().click();const observation=page.locator('.starter-dialog[open]');await observation.getByLabel('Estoy junto al vehículo o coordinado en este momento con el instalador.').check();await observation.getByLabel('Motivo / resultado comprobado').fill('Resultado ficticio del ensayo de interfaz');await observation.getByRole('button',{name:'Guardar comprobación',exact:true}).click();await observation.waitFor({state:'hidden'});await page.getByText('Arranque habilitado en la comprobación',{exact:true}).waitFor();
  safe=false;await page.getByRole('button',{name:'Actualizar control de arranque',exact:true}).click();await page.waitForTimeout(100);assert(await page.getByRole('button',{name:'Bloquear arranque',exact:true}).isDisabled());assert.equal(await page.getByRole('button',{name:'Restituir arranque',exact:true}).count(),0);await page.getByText('Recuperación en terreno',{exact:true}).click();assert(await page.getByRole('button',{name:'Restituir bloqueo externo',exact:true}).isEnabled());connected=false;await page.getByRole('button',{name:'Actualizar control de arranque',exact:true}).click();await page.getByText('GPS sin conexión activa',{exact:true}).waitFor();assert(await page.getByRole('button',{name:'Restituir bloqueo externo',exact:true}).isDisabled());
  await page.locator('.my-alerts>summary').click();await page.locator('#protection-reason').waitFor();assert.equal(await page.locator('.starter-control').count(),1);await page.locator('.my-alerts>summary').click();
  stale=true;await nav().getByRole('button',{name:'Vehículo',exact:true}).click();await page.getByRole('button',{name:'Centrar y actualizar ubicación',exact:true}).click();await page.getByText('Sin señal reciente',{exact:true}).waitFor();assert.equal(await page.locator('.my-vehicle-speed>strong').innerText(),'—');
  manager=true;stale=false;await page.goto(origin+'/tracker?asset='+ids[0]+'#live');await page.reload();try{await page.getByLabel('Vehículo seleccionado').selectOption(ids[1]);}catch{await page.screenshot({path:path.join(out,'manager-failure.png'),fullPage:true});throw Error('Manager fixture failed: '+(await page.locator('body').innerText()).slice(0,900));}await page.getByRole('heading',{name:'QA0002',exact:true}).waitFor();await nav().getByRole('button',{name:'Recorridos',exact:true}).click();assert(new URL(page.url()).searchParams.get('asset')===ids[1]);await page.reload();await page.getByRole('heading',{name:'Tus recorridos',exact:true}).waitFor();assert.equal(await page.getByLabel('Vehículo seleccionado').inputValue(),ids[1]);
  await page.getByRole('button',{name:'Administrar flota',exact:true}).click();await page.getByRole('heading',{name:'Vehículos y equipos',exact:true}).waitFor();await page.getByRole('button',{name:'Inicio',exact:true}).click();await page.getByRole('button',{name:'Abrir mapa',exact:true}).waitFor();assert.equal(new URL(page.url()).hash,'#home');assert.equal(new URL(page.url()).searchParams.get('asset'),ids[1]);await page.getByRole('navigation',{name:'Áreas Tracker'}).getByRole('button',{name:'Mapa',exact:true}).click();await nav().waitFor();assert.equal(new URL(page.url()).hash,'#live');await page.getByRole('heading',{name:'QA0002',exact:true}).waitFor();await page.getByRole('link',{name:'Steps Tracker Inicio',exact:true}).click();await page.getByRole('button',{name:'Abrir mapa',exact:true}).waitFor();
  for(const width of [320,430,1440]){await page.setViewportSize({width,height:900});await fits();}await page.screenshot({path:path.join(out,'administrator-desktop.png'),fullPage:true});
  viewer=true;manager=false;await page.goto(origin+'/tracker#protection');await page.reload();await page.getByText('Tu cuenta no tiene habilitado el control de arranque de este vehículo.').waitFor();assert(await page.getByRole('button',{name:'Bloquear arranque',exact:true}).isDisabled());
  missing=true;await page.goto(origin+'/tracker#live');await page.getByRole('heading',{name:'Esperando señal del GPS',exact:true}).waitFor();await fits();assert.equal(sent,2);
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({responsive:true,embedded_history:true,gpx:true,playback:true,gap_pause:true,hourly_parking_grouped:true,raw_positions_retained:true,explicit_gap_continue:true,admin_vehicle_switch_persisted:true,read_only:true,disconnected_blocked:true,unsafe_inhibit_blocked:true,restore_without_fresh_position:true,confirmation_required:true,hardware_orders:0,browser_simulations:sent}));console.log('TRACKER_MOBILE_INTERIOR_OK physical_orders=0');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
