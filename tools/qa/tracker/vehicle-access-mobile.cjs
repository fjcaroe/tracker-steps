/* Real login and read-only mobile checks. Never submits a relay or policy change. */
const fs=require('fs'),path=require('path');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [factsFile,scope,out]=process.argv.slice(2),facts=JSON.parse(fs.readFileSync(factsFile,'utf8'))[scope];
 const host=scope==='development'?'desarrollo.stepsapp.cl':'cerroelplomo.stepsapp.cl';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},timezoneId:'America/Santiago',isMobile:true,hasTouch:true,serviceWorkers:'block'});const page=await context.newPage();
  if(process.env.SESSION_PROOF){
   const proof=JSON.parse(fs.readFileSync(process.env.SESSION_PROOF,'utf8'));if(proof.host!==host||proof.company_id!==facts.company_id)throw Error('Wrong native session');
   await context.addCookies([{name:'session_id',value:proof.session_id,domain:host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(facts.company_id),domain:host,path:'/',secure:true}]);
   await page.goto('https://'+host+'/web_tracker/?company='+facts.company_id+'#live');
  }else{
   await page.goto('https://'+host+'/web/login?redirect=%2Fweb_tracker%2F');
   await page.locator('input[name="login"]').fill(facts.preview_login);await page.locator('input[name="password"]').fill(facts.preview_password);await page.locator('form:has(input[name="password"]) button[type="submit"]').click();
  }
  await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).waitFor({timeout:60000});
  const current=await page.evaluate(async()=>{
   const context=await (await fetch('/steps_tracker/context')).json();const fleet=await (await fetch('/steps_tracker/api/fleet/snapshot')).json();
   const config=await fetch('/steps_tracker/api/configuration');
   const legacy=await fetch('/steps_tracker/classic-session',{method:'POST',body:new URLSearchParams({csrf_token:context.csrf_token})});
   return {context,fleet,config:config.status,legacy:legacy.status};
  });
  if(!current.context.vehicle_limited||!current.context.can_manage_protection||current.context.role!=='operator')throw Error('Wrong profile');
  if(current.fleet.total!==1||current.fleet.items[0].asset_id!==facts.asset_id||current.config!==403||current.legacy!==403)throw Error('Scope differs');
  if(await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).getByRole('button').count()!==3)throw Error('Wrong mobile navigation');
  await page.screenshot({path:path.join(out,'my-vehicle.png'),fullPage:true});
  await page.getByRole('button',{name:'Ver recorridos',exact:true}).click();await page.getByRole('dialog').waitFor();await page.screenshot({path:path.join(out,'history.png'),fullPage:true});
  await page.getByRole('dialog').getByRole('button',{name:'Cerrar',exact:true}).last().click();
  await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).getByRole('button',{name:'Protección',exact:true}).click();
  await page.locator('#protection-reason').waitFor();await page.locator('#protection-reason').fill('Revisión de permisos');
  await page.getByRole('heading',{name:'Bloqueo de arranque',exact:true}).waitFor();
  await page.waitForFunction(()=>{const b=document.querySelector('.protection-control button.fleet-primary');return b&&!b.disabled;});
  const relay=await page.evaluate(async id=>{const r=await fetch('/steps_tracker/api/assets/'+id+'/starter-control');return {status:r.status,value:await r.json()};},facts.asset_id);
  if(relay.status!==200||relay.value.can_operate!==current.context.can_control_starter)throw Error('Starter access response differs');
  if(scope==='cerro'&&!relay.value.wiring_verified)throw Error('Confirmed starter wiring missing');
  if(!current.context.control_preview&&relay.value.wiring_verified)await page.getByText('Circuito de arranque verificado',{exact:true}).waitFor();
  if(current.context.control_preview){
   await page.getByRole('button',{name:'Bloquear arranque',exact:true}).click();
   await page.getByText(/Simulación: bloqueo de arranque/).waitFor();
   const denied=await page.evaluate(async({id,csrf})=>(await fetch('/steps_tracker/starter/'+id+'/command',{method:'POST',body:new URLSearchParams({csrf_token:csrf,payload:'{}'})})).status,{id:facts.asset_id,csrf:current.context.csrf_token});
   if(denied!==403)throw Error('Preview reached physical control');
  }
  await page.screenshot({path:path.join(out,'protection.png'),fullPage:true});
  await page.goto('https://'+host+'/web_tracker/#ops');await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).waitFor();
  if(await page.locator('body').evaluate(el=>el.scrollWidth>window.innerWidth+2))throw Error('Mobile overflow');
  console.log('TRACKER_VEHICLE_MOBILE_OK login=True assigned_only=True configuration_denied=True classic_denied=True history=True protection=True navigation=True');
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({commit:process.env.REVIEW_COMMIT,scope,limited:true,preview:current.context.control_preview===true,starter_control:current.context.can_control_starter===true,asset_count:current.fleet.total}));
  if(!process.env.SESSION_PROOF)await page.goto('https://'+host+'/web/session/logout?redirect=/web/login');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
