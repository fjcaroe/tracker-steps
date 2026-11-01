/* Browser acceptance; API data can be the exact synthetic snapshot from target-copy TCP QA. */
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,channel:'msedge'});const context=await browser.newContext({viewport:{width:390,height:900}});const page=await context.newPage();const mutations=[];const errors=[];
 await page.addInitScript(()=>{window.gpsPhoneCalls=0;Object.defineProperty(navigator,'geolocation',{value:{watchPosition:()=>{window.gpsPhoneCalls++;return 1;},clearWatch:()=>{},getCurrentPosition:()=>{window.gpsPhoneCalls++;}}});});
 page.on('request',r=>{if(r.method()!=='GET'&&/sessions\/start|work_orders|classic-session/.test(r.url()))mutations.push(r.url());});page.on('pageerror',e=>errors.push(e.message));
 const stamp=new Date().toISOString();
 let snapshot=process.env.GPS_COPY_SNAPSHOT?JSON.parse(fs.readFileSync(process.env.GPS_COPY_SNAPSHOT,'utf8').replace(/^\uFEFF/,'')):{tenant:'Cerro de prueba',tenant_id:'qa-tenant',user_id:'qa-viewer',items:[{asset_id:'a1',name:'Auto Coban de prueba',plate:'QA0001',signal_state:'received',motion_state:'moving',position_stale:false,device:{brand:'Coban',model:'401C'},last_position:{id:'p1',lat:-35.4,lon:-71.6,recorded_at:stamp,received_at:stamp,speed_kmh:20,quality:'gps'}}],total:1,next_cursor:null,generated_at:stamp};
 let status=200,reads=0;
 await page.route('**/steps_tracker/**',async route=>{
  if(route.request().url().includes('/api/fleet/snapshot')){reads++;return route.fulfill({status,contentType:'application/json',body:JSON.stringify(status===200?snapshot:{detail:'QA unavailable'})});}
  if(route.request().url().includes('/api/configuration'))return route.fulfill({status,contentType:'application/json',body:JSON.stringify({items:(snapshot.installations||[]).map(d=>({id:d.id,imei:'000000000000001',asset_id:d.asset_id,asset_name:d.asset_name,commissioning:d}))})});
  if(route.request().url().endsWith('/context'))return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({csrf_token:'qa',role:'viewer'})});
  return route.fulfill({status:403,contentType:'application/json',body:'{}'});
 });
 await page.route('https://*.tile.openstreetmap.org/**',route=>route.fulfill({status:200,contentType:'image/png',body:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j6V8AAAAASUVORK5CYII=','base64')}));
 const output=process.env.GPS_UI_OUTPUT;if(output)fs.mkdirSync(output,{recursive:true});
 try{
  await page.goto((process.env.GPS_UI_BASE||'http://127.0.0.1:4176')+'/truck/#gps');
  await page.getByRole('heading',{name:'Autos y equipos GPS'}).waitFor();
  await page.getByRole('heading',{name:snapshot.items[0]?.name||snapshot.installations[0].label,exact:true}).waitFor();
  await page.locator('.hardware-google-canvas').waitFor();
  await page.locator('.hardware-car-pin').first().waitFor();assert.equal(await page.locator('.mk--machine,.mk--stale,.mk--test').count(),1);
  assert.equal(await page.evaluate(()=>window.gpsPhoneCalls),0);assert.deepEqual(mutations,[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(output)await page.screenshot({path:path.join(output,'hardware-map.png'),fullPage:true});
  const oldReads=reads;snapshot={...snapshot,items:snapshot.items.map(a=>({...a,last_position:{...a.last_position,lat:-35.555555}})),installations:(snapshot.installations||[]).map(d=>({...d,lat:-35.555555}))};
  await page.getByText('-35.555555,', {exact:false}).waitFor({timeout:15000});assert.ok(reads>oldReads,'Automatic polling');
  status=503;await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByRole('alert').waitFor();
  assert.equal(await page.locator('.mk--stale').count(),1);
  status=403;await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByRole('link',{name:'Entrar con Odoo'}).waitFor();
  assert.equal(await page.locator('.hardware-google-canvas').count(),0);
  status=200;snapshot={...snapshot,tenant:'Otra compañía autorizada',tenant_id:'other',role:'viewer',items:[],total:0,installations:[]};
  await page.getByRole('button',{name:'Actualizar',exact:true}).click();await page.getByText(/Todavía no hay vehículos registrados/).waitFor();
  assert.equal(await page.getByRole('heading',{name:'Auto Coban de prueba'}).count(),0);
  assert.deepEqual(mutations,[]);assert.deepEqual(errors,[]);
  console.log('MOBILE_HARDWARE_UI_OK actual_marker=True automatic_poll=True old_position_warning=True revoked_access_cleared=True tenant_switch=True no_journey=True no_phone_gps=True');
 }catch(e){if(output)await page.screenshot({path:path.join(output,'failure.png'),fullPage:true});throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
