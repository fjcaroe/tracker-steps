/* Read-only, real-account verification of one vehicle and same-company denial. */
const fs=require('fs'),path=require('path'),assert=require('assert');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,factsFile,out]=process.argv.slice(2),proof=JSON.parse(fs.readFileSync(proofFile,'utf8')),f=JSON.parse(fs.readFileSync(factsFile,'utf8'));assert(proof.host==='cerroelplomo.stepsapp.cl'&&proof.company_id===f.company_id);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,timezoneId:'America/Santiago',serviceWorkers:'block'});await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(f.company_id),domain:proof.host,path:'/',secure:true}]);const page=await context.newPage();await page.goto('https://'+proof.host+'/web_tracker/?company='+f.company_id+'#live');await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).waitFor();
  const state=await page.evaluate(async f=>{
   const context=await (await fetch('/steps_tracker/context')).json(),fleet=await (await fetch('/steps_tracker/api/fleet/snapshot')).json();const denied=[];
   for(const id of f.denied_asset_ids||[])for(const url of ['/steps_tracker/api/assets/'+id,'/steps_tracker/api/assets/'+id+'/positions','/steps_tracker/api/assets/'+id+'/starter-control','/steps_tracker/costs/assets/'+id])denied.push((await fetch(url)).status);
   const request=await fetch('/web/dataset/call_kw/fleet.vehicle/read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model:'fleet.vehicle',method:'read',args:[[f.vehicle_id]],kwargs:{fields:['license_plate','vin_sn','model_year','color','description','model_id','driver_id']}}})});const vehicle=await request.json();if(vehicle.error)throw Error('Native vehicle not readable: '+(vehicle.error.data?.message||vehicle.error.message));
   return {context,fleet,denied,vehicle:vehicle.result[0]};
  },f);
  assert(state.context.user_id===f.source_user_id&&state.context.role==='operator'&&state.context.vehicle_limited&&state.context.can_manage_protection&&state.context.can_control_starter&&!state.context.control_preview);
  assert(state.fleet.total===1&&state.fleet.items[0].asset_id===f.asset_id&&state.fleet.items[0].plate===f.plate);assert(state.denied.length>0&&state.denied.every(s=>s===404));
  assert(state.vehicle.license_plate===f.plate&&state.vehicle.vin_sn===f.vin&&state.vehicle.model_year===f.year&&state.vehicle.color===f.color&&state.vehicle.description.includes(f.engine_number));
  if(f.driver_partner_id)assert(state.vehicle.driver_id[0]===f.driver_partner_id);
  await page.screenshot({path:path.join(out,'my-vehicle.png'),fullPage:true});await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).getByRole('button',{name:'Protección',exact:true}).click();await page.locator('#protection-reason').fill('Revisión de acceso individual');await page.waitForFunction(()=>{const b=document.querySelector('.protection-control button.fleet-primary');return b&&!b.disabled;});await page.getByText('Circuito de arranque verificado',{exact:true}).waitFor();await page.locator('.starter-control').screenshot({path:path.join(out,'starter-readiness.png')});
  await page.goto('https://'+proof.host+'/odoo/action-fleet.fleet_vehicle_action/'+f.vehicle_id);await page.locator('[name="license_plate"]').first().waitFor();await page.screenshot({path:path.join(out,'native-vehicle.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({user_id:state.context.user_id,asset_count:1,native_details:true,driver_link:!!f.driver_partner_id,same_company_ids_denied:true,protection:true,starter_wiring:true,physical_commands_sent:false}));console.log('VEHICLE_OWNER_REVIEW_OK uid='+state.context.user_id+' only_own=True native_details=True other_vehicle_denied=True starter_wiring=True');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
