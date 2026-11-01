/* Fixtures remain in browser responses. Real mode is strictly read-only. */
const {chromium}=require('playwright'),fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const fixture=process.env.GPS_OPERATIONS_FIXTURE==='1',output=process.env.GPS_UI_OUTPUT;
const proof=process.env.GPS_BROWSER_PROOF?JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,'')):null;
const host=proof?.host||'desarrollo.stepsapp.cl';assert.ok(['desarrollo.stepsapp.cl','cerroelplomo.stepsapp.cl'].includes(host));
const first='00000000-0000-4000-8000-000000000101',second='00000000-0000-4000-8000-000000000102';
const identity={user_id:100,user:'Operador de prueba',company_id:2,company:'Empresa de prueba',tenant_key:'CERRO_EL_PLOMO:2',role:'manager',csrf_token:'fixture-only'};
const now=Date.now(),points=Array.from({length:25},(_,i)=>({id:'ops-qa-'+i,recorded_at:new Date(now-3600000+i*60000).toISOString(),received_at:new Date(now-3600000+i*60000).toISOString(),lat:-33.4295-i*.0006,lon:-70.6184,speed_kmh:20,quality:'gps',acc:null,external_power:null}));
const asset=(id,plate)=>({asset_id:id,name:id===first&&syncName?syncName:'Vehículo de prueba',plate,type:'car',cost_center:null,responsible:null,created_at:new Date(now-86400000).toISOString(),position_stale:false,signal_state:'received',motion_state:'moving',protection_state:'disarmed',last_position:points.at(-1),device:{brand:'Coban',model:'401',firmware:null,protocol:'gps103-ascii'},capabilities:{tracking:'approved',remote_start_inhibit:'not_approved'}});
const vehicle={id:701,name:'Vehículo nativo de prueba',license_plate:'QA-001',odometer:1000,odometer_unit:'kilometers',driver_id:[801,'Conductor de prueba']};
let syncUpdates=0,syncName=null;
let link=null,logs=[{id:1001,date:'2026-10-31',value:1000,unit:'kilometers'}],linkWrites=0,odometerWrites=0,denied=false,scopeChanged=false;const unexpected=[];
(async()=>{
 fs.mkdirSync(output,{recursive:true});const browser=await chromium.launch({headless:true,channel:'msedge'}),context=await browser.newContext({viewport:{width:1440,height:1000},acceptDownloads:true});
 if(proof&&!fixture)await context.addCookies([{name:'session_id',value:proof.session_id,domain:host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:host,path:'/',secure:true}]);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',async route=>{
  const request=route.request(),url=new URL(request.url()),endpoint=url.pathname.replace('/steps_tracker/api/','');
  const json=(data,status=200)=>route.fulfill({status,contentType:'application/json',body:JSON.stringify(data)});
  if(url.hostname===host&&url.pathname.startsWith('/web_tracker/')&&process.env.GPS_OPERATIONS_DIST){const root=path.resolve(process.env.GPS_OPERATIONS_DIST),file=path.resolve(root,url.pathname.slice('/web_tracker/'.length)||'index.html');assert.ok(file.startsWith(root+path.sep));return route.fulfill({status:200,contentType:({'.js':'application/javascript','.css':'text/css','.html':'text/html','.svg':'image/svg+xml'})[path.extname(file)]||'application/octet-stream',body:fs.readFileSync(file)});}
  if(fixture&&url.pathname==='/steps_tracker/context')return json({...identity,...(scopeChanged?{company_id:3,tenant_key:'CERRO_EL_PLOMO:3'}:{})});
  if(fixture&&url.pathname.startsWith('/steps_tracker/api/')){
   if(endpoint==='assets/'+first&&request.method()==='POST'){const params=new URLSearchParams(request.postData()),body=JSON.parse(params.get('payload'));assert.equal(params.get('method'),'PATCH');assert.equal(body.name,vehicle.name);syncUpdates++;syncName=body.name;return json({asset_id:first});}
   assert.equal(request.method(),'GET');
   if(endpoint==='fleet/snapshot')return json({items:[asset(first,'QA-001'),asset(second,'QA-002')],total:2,next_cursor:null,tenant:identity.company});
   if(endpoint==='assets/'+first)return json(asset(first,'QA-001'));
   if(endpoint==='zones')return json([]);
   if(endpoint==='configuration')return json({items:[],reminders:[],today:'2026-11-01'});
   if(endpoint==='view-preferences/fleet')return json(null);
   if(endpoint.endsWith('/positions'))return denied?json({detail:'Acceso revocado'},403):json({items:endpoint.includes(second)?[]:points.slice(url.searchParams.has('before')?0:12,url.searchParams.has('before')?12:25).reverse(),next_cursor:url.searchParams.has('before')||endpoint.includes(second)?null:'ops-page'});
   unexpected.push(endpoint);return route.abort();
  }
  if(fixture&&url.pathname.startsWith('/web/dataset/call_kw/')){
   const payload=request.postDataJSON(),p=payload.params;assert.deepEqual(p.kwargs.context,{allowed_company_ids:[2]});
   const rpc=data=>json({jsonrpc:'2.0',id:payload.id,result:data});
   if(p.model==='ir.ui.menu'&&p.method==='load_menus')return rpc({root:{id:false,children:[1,2,3]},1:{id:1,name:'Flota',xmlid:'fleet.menu_root',action:'ir.actions.act_window,101',children:[]},2:{id:2,name:'Cosecha',xmlid:'step_cosecha.menu_root',action:'ir.actions.client,102',children:[]},3:{id:3,name:'Gastos',xmlid:'hr_expense.menu_root',action:'ir.actions.act_window,103',children:[]}});
   if(p.method==='check_access_rights')return rpc(true);
   if(p.model==='step.tracker.asset.link'){
    if(p.method==='search_read'){assert.ok(p.kwargs.domain.some(d=>d[0]==='company_id'&&d[2]===2));return rpc(link?[link]:[]);}
    if(p.method==='create'){assert.equal(p.args[0][0].asset_id,first);assert.equal(p.args[0][0].vehicle_id,701);assert.equal(p.args[0][0].company_id,2);linkWrites++;link={id:901,asset_id:first,vehicle_id:[701,vehicle.name]};return rpc([901]);}
   }
   if(p.model==='fleet.vehicle'&&p.method==='search_read')return rpc([vehicle]);
   if(p.model==='fleet.vehicle.odometer'){
    if(p.method==='search_read')return rpc([...logs].reverse());
    if(p.method==='create'){const vals=p.args[0][0];assert.equal(vals.vehicle_id,701);odometerWrites++;const row={id:1002,date:vals.date,value:vals.value,unit:'kilometers'};logs.push(row);vehicle.odometer=vals.value;return rpc([row.id]);}
    if(p.method==='read')return rpc(logs.filter(r=>p.args[0].includes(r.id)));
   }
   unexpected.push(p.model+':'+p.method);return route.abort();
  }
  if(fixture&&url.pathname.startsWith('/steps_tracker/costs/'))return json({linked:false,message:'Vínculo nativo de prueba; revisar costos en Odoo.'});
  if(url.hostname===host&&!['GET','HEAD'].includes(request.method())){
   if(!fixture&&url.pathname.startsWith('/web/dataset/call_kw/')){const p=request.postDataJSON().params;if(['search_read','read','check_access_rights','load_menus'].includes(p.method))return route.continue();}
   unexpected.push(url.pathname);return route.abort();
  }
  return route.continue();
 });
 try{
  await page.goto('https://'+host+'/web_tracker/'+(fixture?'?asset='+first:'')+'#ops');await page.getByRole('heading',{name:'Tu actividad real, en un solo lugar.',exact:true}).waitFor();await page.getByText('Consultando posiciones reales del equipo…',{exact:true}).waitFor({state:'hidden'});
  assert.equal(await page.getByText('Laboratorio demo',{exact:true}).count(),0);assert.equal(await page.getByText('Dataset activo',{exact:true}).count(),0);assert.equal(await page.getByLabel('Explorar demo',{exact:true}).count(),0);
  await page.getByRole('button',{name:'Analítica GPS',exact:true}).click();await page.getByRole('heading',{name:'Actividad respaldada por GPS',exact:true}).waitFor();
  if(fixture){assert.equal(await page.locator('.real-ops-kpis article').nth(2).locator('strong').innerText(),'25');const download=page.waitForEvent('download');await page.getByRole('button',{name:'Exportar informe CSV',exact:true}).click();await (await download).saveAs(path.join(output,'report.csv'));}
  await page.getByRole('button',{name:'Vehículo y lecturas',exact:true}).click();await page.getByText('Consultando la ficha y los permisos de Odoo…',{exact:true}).waitFor({state:'hidden'});
  if(fixture){
   await page.getByRole('button',{name:'Elegir vehículo de Odoo',exact:true}).click();assert.equal(await page.getByRole('button',{name:'Confirmar vínculo con este vehículo',exact:true}).isDisabled(),true);assert.equal(linkWrites,0);await page.getByLabel('Vehículo de Odoo a vincular',{exact:true}).selectOption('701');await page.getByRole('button',{name:'Confirmar vínculo con este vehículo',exact:true}).click();await page.getByRole('heading',{name:'Registrar una lectura real',exact:true}).waitFor();assert.equal(linkWrites,1);
   await page.getByLabel('Valor del tablero (km)',{exact:true}).fill('900');await page.locator('.real-ops-check input').check();await page.getByRole('button',{name:'Guardar lectura en Odoo',exact:true}).click();await page.getByRole('alert').filter({hasText:'no es coherente'}).waitFor();assert.equal(odometerWrites,0);
   await page.getByLabel('Valor del tablero (km)',{exact:true}).fill('1020,5');await page.getByRole('button',{name:'Guardar lectura en Odoo',exact:true}).click();await page.getByRole('status').filter({hasText:'Lectura guardada y comprobada'}).waitFor();await page.getByRole('heading',{name:'Registrar una lectura real',exact:true}).waitFor();assert.equal(odometerWrites,1);assert.ok((await page.locator('.real-ops-reading strong').innerText()).includes('1.020,5'));
   await page.getByLabel('Valor del tablero (km)',{exact:true}).fill('1020,5');await page.locator('.real-ops-check input').check();await page.getByRole('button',{name:'Guardar lectura en Odoo',exact:true}).click();await page.getByRole('status').filter({hasText:'ya estaba registrada'}).waitFor();assert.equal(odometerWrites,1);
   scopeChanged=true;await page.getByLabel('Valor del tablero (km)',{exact:true}).fill('1030');await page.locator('.real-ops-check input').check();await page.getByRole('button',{name:'Guardar lectura en Odoo',exact:true}).click();await page.getByRole('alert').filter({hasText:'La compañía o los permisos cambiaron'}).waitFor();assert.equal(odometerWrites,1);scopeChanged=false;
  }
  await page.getByRole('button',{name:'Costos de Odoo',exact:true}).click();await page.getByRole('button',{name:'Ver costos y gastos',exact:true}).click();await page.locator('.asset-costs-body,.asset-costs-note,.asset-costs-error').first().waitFor();
  await page.getByRole('button',{name:'Recorridos GPS',exact:true}).click();await page.getByRole('heading',{name:'Recorrido del período',exact:true}).waitFor();
  if(fixture){await page.locator('.trail-map-canvas .gm-style').first().waitFor({timeout:45000});await page.getByRole('button',{name:'Abrir reproducción e historial',exact:true}).click();await page.getByRole('dialog').getByRole('button',{name:'Reproducir',exact:true}).waitFor();await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).click();await page.getByLabel('Vehículo de Operaciones',{exact:true}).selectOption(second);await page.getByRole('heading',{name:'No hay posiciones en este período',exact:true}).waitFor();assert.equal(await page.locator('.trail-map-canvas').count(),0);await page.getByLabel('Vehículo de Operaciones',{exact:true}).selectOption(first);await page.locator('.trail-map-canvas .gm-style').first().waitFor({timeout:45000});denied=true;await page.getByRole('button',{name:'Actualizar datos',exact:true}).click();await page.getByRole('alert').filter({hasText:'Acceso revocado'}).waitFor();assert.equal(await page.locator('.trail-map-canvas').count(),0);assert.equal(await page.getByRole('button',{name:'Exportar informe CSV',exact:true}).isDisabled(),true);denied=false;await page.getByRole('button',{name:'Actualizar datos',exact:true}).click();await page.locator('.trail-map-canvas .gm-style').first().waitFor({timeout:45000});}
  if(fixture){await page.getByRole('button',{name:'Ver en el mapa',exact:true}).click();await page.getByRole('button',{name:'Sincronizar Odoo',exact:true}).click();await page.getByRole('status').filter({hasText:'1 vehículos actualizados y 0 incorporados'}).waitFor();assert.equal(syncUpdates,1);assert.equal(linkWrites,1);await page.getByRole('button',{name:'Operación',exact:true}).click();await page.getByRole('heading',{name:'Tu actividad real, en un solo lugar.',exact:true}).waitFor();}
  await page.getByRole('button',{name:'Resumen',exact:true}).click();await page.screenshot({path:path.join(output,'desktop-operations.png'),fullPage:true});await page.setViewportSize({width:390,height:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);await page.screenshot({path:path.join(output,'mobile-operations.png'),fullPage:true});
  assert.deepEqual(unexpected,[]);assert.deepEqual(errors,[]);console.log('REAL_OPERATIONS_NATIVE_OK fixture='+fixture+' real_business_writes=0 gps_scoped=True native_odometer='+fixture+' company_change_blocked='+fixture+' mobile=True');
 }catch(e){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
