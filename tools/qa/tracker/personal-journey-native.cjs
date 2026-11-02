/* Real account and real prepared defaults. Does not start a live journey. */
const fs=require('fs');const path=require('path');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,planFile,out]=process.argv.slice(2);const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));const plan=JSON.parse(fs.readFileSync(planFile,'utf8'));if(proof.host!=='desarrollo.stepsapp.cl')throw Error('Development only');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},timezoneId:'America/Santiago',serviceWorkers:'block'});await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  const page=await context.newPage();let writes=0;page.on('request',request=>{if(request.method()==='POST'&&/\/(work_orders|sessions\/start)/.test(request.url()))writes++;});
  await page.addInitScript(()=>localStorage.setItem('steps_movil_settings',JSON.stringify({seenHelp:true})));
  await page.goto('https://'+proof.host+'/truck/');await page.getByText('Este vehículo trabaja por distancia.',{exact:false}).waitFor();
  const machine=page.getByLabel('Máquina',{exact:false});if(await machine.locator('option').count()!==2)throw Error('Old machine is still selectable');
  if(await machine.inputValue()===''||await page.getByLabel('Labor',{exact:false}).inputValue()===''||await page.getByLabel('Centro de costo',{exact:false}).inputValue()===''||await page.getByLabel('Conductor',{exact:false}).inputValue()==='')throw Error('Real defaults not ready');
  if(!(await page.getByRole('button',{name:'Iniciar jornada',exact:true}).isEnabled()))throw Error('Journey is not ready to start');
  await page.screenshot({path:path.join(out,'native-start-390.png'),fullPage:true});
  const snapshot=await page.evaluate(async()=>{const r=await fetch('/steps_tracker/api/fleet/snapshot?limit=500');return r.ok?r.json():null;});if(!snapshot||snapshot.total!==1||snapshot.items[0].asset_id!==plan.asset_id)throw Error('Expected only protected real GPS in Development');
  await page.getByRole('button',{name:'GPS',exact:true}).click();await page.locator('.hardware-sidebar').getByText(plan.plate,{exact:true}).waitFor();await page.locator('.hardware-car-pin').waitFor();await page.screenshot({path:path.join(out,'native-gps-390.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/odoo/fleet.vehicle/'+plan.vehicle_id);const plate=page.locator('[name="license_plate"] input').first();await plate.waitFor();if(await plate.inputValue()!==plan.plate)throw Error('Wrong native vehicle');await page.screenshot({path:path.join(out,'native-vehicle.png'),fullPage:true});
  if(writes)throw Error('Read-only native proof started a real session');console.log('PERSONAL_JOURNEY_NATIVE_OK real_account=True one_machine=True one_gps=True native_form=True defaults_ready=True live_journeys_started=0');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
