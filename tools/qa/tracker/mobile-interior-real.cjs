/* Existing preview accounts only. Read-only business verification, no relay orders. */
const fs=require('fs'),path=require('path'),assert=require('assert');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [scope,factsFile,out]=process.argv.slice(2),f=JSON.parse(fs.readFileSync(factsFile,'utf8').replace(/^\uFEFF/,''))[scope],host=scope==='development'?'desarrollo.stepsapp.cl':'cerroelplomo.stepsapp.cl';assert(['development','cerro'].includes(scope));fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});let context;
 try{
  context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,timezoneId:'America/Santiago',serviceWorkers:'block'});const page=await context.newPage();let refused=0;
  await page.route('**/*',async route=>{
   const r=route.request(),url=new URL(r.url());
   if(url.hostname===host&&r.method()==='POST'){
    if(url.pathname==='/web/login')return route.continue();
    if(url.pathname.startsWith('/web/dataset/call_kw/')){const p=r.postDataJSON().params;if(['read','search_read','load_menus'].includes(p.method))return route.continue();}
    refused++;return route.abort();
   }
   return route.continue();
  });
  await page.goto('https://'+host+'/tracker?company='+f.company_id+'#live');await page.getByLabel('Correo o usuario',{exact:true}).fill(f.preview_login);await page.getByLabel('Contraseña',{exact:true}).fill(f.preview_password);await page.getByRole('button',{name:'Entrar a mi Tracker',exact:true}).click();const nav=page.getByRole('navigation',{name:'Mi Tracker',exact:true});await nav.waitFor();
  const data=await page.evaluate(async()=>({context:await(await fetch('/steps_tracker/context')).json(),fleet:await(await fetch('/steps_tracker/api/fleet/snapshot')).json()}));assert(data.context.vehicle_limited&&data.context.control_preview);assert.equal(data.fleet.total,1);assert.equal(data.fleet.items[0].asset_id,f.asset_id);
  if(data.fleet.items[0].last_position){await page.locator('.my-vehicle-map .gm-style').first().waitFor();await page.waitForTimeout(1200);}
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(out,'vehicle.png'),fullPage:true});
  await nav.getByRole('button',{name:'Recorridos',exact:true}).click();await page.getByRole('heading',{name:'Tus recorridos',exact:true}).waitFor();await page.getByRole('button',{name:'Últimos 7 días',exact:true}).click();await page.getByText('Consultando posiciones del período…',{exact:true}).waitFor({state:'hidden'});assert.equal(await page.locator('dialog[open]').count(),0);await page.waitForTimeout(1200);await page.screenshot({path:path.join(out,'history.png'),fullPage:true});
  await nav.getByRole('button',{name:'Arranque',exact:true}).click();await page.getByRole('heading',{name:'Bloqueo de arranque',exact:true}).waitFor();await page.getByText('Cuenta de prueba: los controles se simulan y no envían órdenes al vehículo.',{exact:true}).waitFor();assert.equal(await page.locator('.starter-control').count(),1);assert.equal(await page.locator('.my-alerts[open]').count(),0);await page.screenshot({path:path.join(out,'starter.png'),fullPage:true});
  await page.locator('.my-alerts>summary').click();await page.locator('#protection-reason').waitFor();assert.equal(await page.locator('.starter-control').count(),1);await page.locator('.my-alerts>summary').click();
  assert.equal(refused,0);await page.getByLabel('Mi cuenta',{exact:true}).click();await page.getByRole('link',{name:'Cerrar sesión',exact:true}).click();await page.getByRole('heading',{name:'Todo bajo control.',exact:true}).waitFor();
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({scope,real_account:true,assigned_asset_only:true,mobile:true,embedded_history:true,separate_starter:true,alerts_collapsed:true,logout:true,business_writes:0,physical_orders:0}));console.log('TRACKER_INTERIOR_REAL_OK scope='+scope+' writes=0 physical_orders=0');
 }finally{if(context)await context.request.get('https://'+host+'/web/session/logout?redirect=/tracker').catch(()=>{});await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
