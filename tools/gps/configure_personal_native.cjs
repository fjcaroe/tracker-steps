/* Authorized native configuration through the real user's ORM permissions. */
const fs=require('fs');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,planFile]=process.argv.slice(2);const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));const plan=JSON.parse(fs.readFileSync(planFile,'utf8'));if(proof.host!=='desarrollo.stepsapp.cl'||proof.company_id!==plan.company_id)throw Error('Development only');
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const ctx=await browser.newContext();await ctx.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  const call=async(model,method,args,kwargs={})=>{
   const response=await ctx.request.post('https://'+proof.host+'/web/dataset/call_kw/'+model+'/'+method,{data:{jsonrpc:'2.0',method:'call',id:1,params:{model,method,args,kwargs:{...kwargs,context:{allowed_company_ids:[plan.company_id],tracking_disable:true,mail_notrack:true,mail_create_nosubscribe:true,mail_notify_force_send:false}}}}});
   const body=await response.json();if(body.error)throw Error('Native '+method+' failed');return body.result;
  };
  const fields=['license_plate','company_id','odometer','cost_id','analytic_id','step_max_pass'];const before=(await call('fleet.vehicle','read',[[plan.vehicle_id]],{fields}))[0];if(before.license_plate!==plan.plate||before.company_id[0]!==plan.company_id)throw Error('Wrong native vehicle');
  await call('fleet.vehicle','write',[[plan.vehicle_id],{cost_id:plan.analytic_id,analytic_id:plan.analytic_id,step_max_pass:plan.passenger_capacity}]);
  const after=(await call('fleet.vehicle','read',[[plan.vehicle_id]],{fields}))[0];if(after.cost_id[0]!==plan.analytic_id||after.analytic_id[0]!==plan.analytic_id||after.odometer!==before.odometer||after.step_max_pass!==4)throw Error('Native read-back failed');
  console.log('PERSONAL_NATIVE_LINKS_CONFIGURED actual_user=True native_analytic_relation=True physical_odometer_preserved=True passenger_capacity=4');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
