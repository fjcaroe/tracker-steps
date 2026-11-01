/* Authenticated read-only check on the real Cerro mobile map; no synthetic business rows. */
const {chromium}=require('playwright');const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));assert.equal(proof.host,'cerroelplomo.stepsapp.cl');
 const browser=await chromium.launch({headless:true,channel:'msedge'});const context=await browser.newContext({viewport:{width:390,height:900}});
 await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
 const page=await context.newPage(),errors=[],writes=[];
 await page.addInitScript(()=>{window.phoneGpsCalls=0;Object.defineProperty(navigator,'geolocation',{value:{watchPosition:()=>{window.phoneGpsCalls++;return 1;},clearWatch:()=>{},getCurrentPosition:()=>{window.phoneGpsCalls++;}}});});
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()!=='GET')writes.push(r.url());});
 try{
  const response=page.waitForResponse(r=>r.url().includes('/steps_tracker/api/fleet/snapshot')&&r.status()===200);
  await page.goto('https://'+proof.host+'/truck/#gps');
  const data=await (await response).json();assert.ok(data.tenant_id&&data.user_id);
  await page.getByRole('heading',{name:'Autos y equipos GPS',exact:true}).waitFor();
  await page.getByText(data.tenant,{exact:true}).waitFor();await page.getByRole('application',{name:'Mapa',exact:true}).waitFor();
  if(!data.items.length)await page.getByText(/Todavía no hay vehículos registrados/).waitFor();
  await page.getByRole('button',{name:'Actualizar',exact:true}).click();
  assert.equal(await page.evaluate(()=>window.phoneGpsCalls),0);assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
  if(process.env.GPS_UI_OUTPUT){fs.mkdirSync(process.env.GPS_UI_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.GPS_UI_OUTPUT,'cerro-hardware-map.png'),fullPage:true});}
  console.log('MOBILE_HARDWARE_NATIVE_OK company_scoped=True authenticated=True map=True business_writes=0 phone_gps_calls=0 assets='+data.items.length);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
