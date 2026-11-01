/* Synthetic UI acceptance; no requests to an actual Odoo or receiver. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}});
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const output=process.env.GPS_UI_OUTPUT;if(output)fs.mkdirSync(output,{recursive:true});
 const asset={asset_id:'a1',name:'Vehículo de prueba',plate:'QA-0000',type:'car',created_at:new Date().toISOString(),signal_state:'no_signal',motion_state:'unknown',position_stale:true,protection_state:'disarmed',last_position:null,device:null,capabilities:{tracking:'not_approved',remote_start_inhibit:'not_approved'}};
 let items=[];const writes=[];
 const receiver={supported:true,online:true,last_seen_at:new Date().toISOString(),host:'35.222.25.110',port:5001,transport:'TCP',protocol:'gps103-ascii'};
 await page.route('**/steps_tracker/**',async route=>{
  const url=new URL(route.request().url());let result={};
  if(url.pathname==='/steps_tracker/context')result={user_id:2,user:'Prueba QA',company_id:2,company:'Compañía de prueba',tenant_key:'QA:2',role:'manager',csrf_token:'test-only'};
  else if(url.pathname.endsWith('/configuration')&&route.request().method()==='GET')result={items,reminders:[],today:'2026-10-31',receiver};
  else if(url.pathname.endsWith('/fleet/snapshot'))result={items:[asset],total:1,next_cursor:null,counts:{}};
  else if(url.pathname.endsWith('/zones'))result=[];
  else if(url.pathname.includes('/view-preferences/'))result=null;
  else if(url.pathname.startsWith('/steps_tracker/costs/assets/'))result={linked:false,message:'Equipo de prueba sin vínculo contable.'};
  else if(url.pathname==='/steps_tracker/classic-session')result={access_token:'test-only-classic',token_type:'bearer',user:{id:2,username:'qa',full_name:'Prueba QA'},cost_centers:[]};
  else if(route.request().method()==='POST'){
   const form=new URLSearchParams(route.request().postData());const body=JSON.parse(form.get('payload'));writes.push({url:url.pathname,body});
   if(url.pathname.endsWith('/configuration/devices')){items=[{...body,id:'r1',device_id:'d1',version:1,asset_id:null,asset_name:null,tracking_approved:false,signal_state:'no_signal',commissioning:{mode:'disabled',last_seen_at:null,fix_at:null,fix_received_at:null,lat:null,lon:null,pending:0,last_error:null}}];result={id:'r1'};}
   else if(url.pathname.endsWith('/assignment')){Object.assign(items[0],{asset_id:body.asset_id,asset_name:asset.name,version:items[0].version+1});}
   else if(url.pathname.endsWith('/commissioning')){assert.equal(body.version,items[0].version);Object.assign(items[0].commissioning,{mode:body.mode});items[0].version++;}
   else throw Error('Unexpected write '+url.pathname);
  }else throw Error('Unexpected request '+url.pathname);
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)});
 });
 for(const pattern of ['**/tracker-steps/**','http://localhost:8000/**'])await page.route(pattern,route=>route.fulfill({status:200,contentType:'application/json',body:JSON.stringify([])}));
 try{
  await page.goto((process.env.GPS_UI_BASE||'http://127.0.0.1:4173')+'/web_tracker/#settings');
  await page.getByRole('heading',{name:'Preparar los equipos Coban'}).waitFor();
  await page.getByRole('button',{name:'Agregar GPS',exact:true}).click();
  await page.getByLabel('IMEI (15 dígitos)',{exact:true}).fill('000000000000001');
  await page.getByLabel('Número de la SIM',{exact:true}).fill('+56000000000');
  await page.getByRole('button',{name:'Guardar GPS y SIM'}).click();
  await page.getByText('IMEI 000000000000001',{exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:'Activar seguimiento',exact:true}).isDisabled(),true);
  await page.getByRole('button',{name:'Asociar vehículo',exact:true}).click();
  await page.getByRole('combobox',{name:/Vehículo o equipo/}).selectOption('a1');
  await page.getByLabel('Motivo de la asociación o cambio').fill('Instalación física de prueba');
  await page.getByRole('button',{name:'Confirmar asociación'}).click();
  await page.getByRole('button',{name:'Probar recepción',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Motivo',{exact:true}).fill('Prueba antes del traslado');
  await page.getByRole('button',{name:'Confirmar',exact:true}).click();
  await page.getByRole('heading',{name:'Prueba de recepción',exact:true}).waitFor();
  Object.assign(items[0].commissioning,{last_seen_at:new Date().toISOString(),fix_at:new Date().toISOString(),fix_received_at:new Date().toISOString(),lat:-33,lon:-70});
  await page.getByRole('button',{name:'Actualizar diagnóstico'}).click();
  await page.getByRole('link',{name:'-33.000000, -70.000000 ↗'}).waitFor();
  await page.getByRole('button',{name:'Activar seguimiento',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Motivo',{exact:true}).fill('Identidad y ubicación verificadas');
  await page.getByRole('button',{name:'Confirmar',exact:true}).click();
  assert.equal(await page.getByRole('dialog').count(),1); // required physical-review checkbox
  await page.getByRole('checkbox',{name:/He comprobado/}).check();
  await page.getByRole('button',{name:'Confirmar',exact:true}).click();
  await page.getByRole('heading',{name:'Seguimiento activo',exact:true}).waitFor();
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Horizontal overflow at '+width);
   if(output)await page.screenshot({path:path.join(output,'configuration-'+width+'.png'),fullPage:true});
  }
  await page.getByRole('button',{name:'Deshabilitar recepción',exact:true}).click();
  await page.getByRole('dialog').getByLabel('Motivo',{exact:true}).fill('Equipo retirado para revisión');
  await page.getByRole('button',{name:'Confirmar',exact:true}).click();
  await page.getByRole('heading',{name:'Recepción deshabilitada',exact:true}).waitFor();
  assert.equal(writes.filter(w=>w.url.endsWith('/commissioning')).length,3);
  assert.equal(writes.find(w=>w.body.mode==='forward').body.verified,true);
  await page.getByRole('button',{name:'Flota',exact:true}).click();
  await page.getByRole('button',{name:/Vehículo de prueba.*QA-0000/}).first().click();
  await page.getByRole('button',{name:'Ver costos y gastos',exact:true}).click();
  await page.getByText('Equipo de prueba sin vínculo contable.',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Operación',exact:true}).click();
  await page.getByRole('navigation',{name:'Navegación principal'}).waitFor();
  for(const name of ['Resumen','Registro','Ingreso manual','Cosecha','Monitoreo','Odómetro','Indicadores','Analítica','Maestros','Historial'])await page.getByRole('navigation',{name:'Navegación principal'}).getByRole('button',{name:new RegExp('^'+name)}).waitFor();
  await page.getByRole('button',{name:'Registro',exact:true}).click();
  await page.getByRole('heading',{name:'Registro de operación',exact:true}).waitFor();
  await page.getByRole('button',{name:'← Flota y GPS',exact:true}).click();
  await page.getByRole('button',{name:'Configuración',exact:true}).click();
  await page.getByRole('heading',{name:'Preparar los equipos Coban'}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('GPS_UI_OK register_sim=true associate=true capture=true physical_review=true activation=true revocation=true responsive=true operation_menu=true classic_session=true costs=true gps_preserved=true');
 }catch(e){if(output)await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
