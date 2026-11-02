/* Verify unrestricted administrator inventory and the real per-user native form. */
const fs=require('fs'),path=require('path'),assert=require('assert');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,factsFile,out]=process.argv.slice(2),proof=JSON.parse(fs.readFileSync(proofFile,'utf8')),f=JSON.parse(fs.readFileSync(factsFile,'utf8')).cerro;assert(proof.host==='cerroelplomo.stepsapp.cl'&&proof.company_id===f.company_id);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},serviceWorkers:'block'});await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(f.company_id),domain:proof.host,path:'/',secure:true}]);const page=await context.newPage();
  await page.goto('https://'+proof.host+'/tracker#settings');await page.getByRole('heading',{name:'Permisos por usuario',exact:true}).waitFor();
  const state=await page.evaluate(async f=>{
   const context=await (await fetch('/steps_tracker/context')).json(),config=await (await fetch('/steps_tracker/api/configuration')).json(),fleet=await (await fetch('/steps_tracker/api/fleet/snapshot?limit=500')).json();
   const r=await fetch('/web/dataset/call_kw/res.users/search_read',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({jsonrpc:'2.0',method:'call',params:{model:'res.users',method:'search_read',args:[],kwargs:{domain:[['login','in',[f.existing_login,f.preview_login]]],fields:['id','login','tracker_restricted','tracker_vehicle_ids','tracker_starter_control','tracker_control_preview']}}})});const users=await r.json();if(users.error)throw Error('Native user read failed');return {context,config,fleet,users:users.result};
  },f);
  assert(state.context.role==='manager'&&!state.context.vehicle_limited&&state.config.items.length===4);
  for(const expected of f.expected_classes||[])assert(state.fleet.items.some(a=>a.asset_id===expected.asset_id&&a.type===expected.type));
  const u=state.users.find(u=>u.login===f.existing_login),preview=state.users.find(u=>u.login===f.preview_login);assert(u&&preview&&u.tracker_restricted&&u.tracker_starter_control&&!u.tracker_control_preview);assert.deepStrictEqual(u.tracker_vehicle_ids,[f.vehicle_id]);assert(preview.tracker_control_preview&&!preview.tracker_starter_control);
  await page.screenshot({path:path.join(out,'administrator-settings.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/odoo/action-base.action_res_users/'+u.id);await page.locator('.o_form_view').waitFor();await page.screenshot({path:path.join(out,'native-user-before-tab.png'),fullPage:true});await page.getByRole('tab',{name:'Acceso Tracker',exact:true}).click();
  assert(await page.locator('[name="tracker_restricted"] input').isChecked());assert(await page.locator('[name="tracker_starter_control"] input').isChecked());assert(!await page.locator('[name="tracker_control_preview"] input').isChecked());
  await page.locator('[name="tracker_vehicle_ids"]').getByText(new RegExp(f.plate)).first().waitFor();await page.screenshot({path:path.join(out,'native-user-access.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/tracker#fleet');await page.getByRole('heading',{name:'Vehículos y equipos',exact:true}).waitFor();await page.screenshot({path:path.join(out,'administrator-fleet.png'),fullPage:true});
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({administrator_unrestricted:true,gps_count:4,native_user_form:true,actual_starter_control:true,preview_physical_disabled:true,normalized_classes:(f.expected_classes||[]).length}));console.log('TRACKER_ACCESS_ADMIN_OK inventory=4 native_user_form=True individual_scope=True');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
