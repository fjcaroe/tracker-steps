/* Real native account, current installation inventory and Fleet form. Read only. */
const fs=require('fs'),path=require('path');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,factsFile,deliveryFile,out]=process.argv.slice(2);const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));const facts=JSON.parse(fs.readFileSync(factsFile,'utf8'));const delivery=JSON.parse(fs.readFileSync(deliveryFile,'utf8'));if(proof.host!=='cerroelplomo.stepsapp.cl'||proof.company_id!==facts.company_id)throw Error('Wrong company');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},timezoneId:'America/Santiago',serviceWorkers:'block'});await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  const page=await context.newPage();await page.goto('https://'+proof.host+'/web_tracker/?company='+facts.company_id+'&asset='+facts.asset_id+'#settings');
  await page.getByText('GPS y SIM',{exact:false}).first().waitFor();
  const current=await page.evaluate(async()=>{const r=await fetch('/steps_tracker/api/configuration');return r.ok?r.json():null;});
  const device=current?.items.find(r=>r.imei===facts.imei);if(!device||device.asset_id!==facts.asset_id||device.asset_name!==facts.plate||current.items.length!==4)throw Error('Device association differs');
  await page.getByText(facts.plate,{exact:true}).first().waitFor();await page.screenshot({path:path.join(out,'gps-settings.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/odoo/fleet.vehicle/'+delivery.result.vehicle_id);const plate=page.locator('[name="license_plate"] input').first();await plate.waitFor();if(await plate.inputValue()!==facts.plate)throw Error('Wrong native plate');
  const vin=page.locator('[name="vin_sn"] input').first();await vin.waitFor();if(await vin.inputValue()!==facts.vin)throw Error('Native VIN differs');await page.screenshot({path:path.join(out,'native-vehicle.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/truck/#gps');await page.locator('.hardware-sidebar').getByText(facts.plate,{exact:true}).first().waitFor();await page.screenshot({path:path.join(out,'mobile-gps.png'),fullPage:true});
  const item=await page.evaluate(async(id)=>{const r=await fetch('/steps_tracker/api/assets/'+id);return r.ok?r.json():null;},facts.asset_id);if(!item||item.plate!==facts.plate)throw Error('Wrong fleet projection');
  if(process.env.REQUIRE_APPROVED==='1'||process.env.REQUIRE_LIVE==='1'){
   if(device.commissioning.mode!=='forward'||!device.tracking_approved||item.capabilities.tracking!=='approved')throw Error('Tracking not approved');
   if(process.env.REQUIRE_LIVE==='1'&&!item.last_position)throw Error('Waiting for first tracked position');
   if((await page.locator('body').innerText()).includes('Posición GPS recibida en prueba'))throw Error('Mobile test-position label remains');
   await page.goto('https://'+proof.host+'/web_tracker/?company='+facts.company_id+'&asset='+facts.asset_id+'#live');
   await page.getByText(facts.plate,{exact:true}).first().waitFor();
   await page.screenshot({path:path.join(out,'live-map.png'),fullPage:true});
   if((await page.locator('body').innerText()).includes('Posición GPS recibida en prueba'))throw Error('Test-position label remains');
  }
  console.log('VEHICLE_INSTALLATION_NATIVE_OK account=True company=True configuration_form=True native_vehicle=True vin=True mobile_fleet=True receiver_mode='+device.commissioning.mode+' vehicle_position='+Boolean(item.last_position));
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
