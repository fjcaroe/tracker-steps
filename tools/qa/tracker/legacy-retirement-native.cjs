/* Real Cerro UI after confirmed fixture retirement. Never creates a journey. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const proof=JSON.parse(fs.readFileSync(process.env.GPS_BROWSER_PROOF,'utf8').replace(/^\uFEFF/,''));
 assert.equal(proof.host,'cerroelplomo.stepsapp.cl');
 const browser=await chromium.launch({headless:true,channel:'msedge'});
 const context=await browser.newContext({viewport:{width:390,height:900}});
 await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
 const page=await context.newPage(),blocked=[],errors=[];
 await page.addInitScript(()=>{window.phoneGpsCalls=0;Object.defineProperty(navigator,'geolocation',{value:{watchPosition:()=>{window.phoneGpsCalls++;return 1;},clearWatch:()=>{},getCurrentPosition:()=>{window.phoneGpsCalls++;}}});});
 await page.route('**/*',async route=>{
  const r=route.request();
  if(!['GET','HEAD','OPTIONS'].includes(r.method())&&!/\/steps_tracker\/classic-session$|\/auth\/refresh$|\/mobile\/heartbeat$/.test(new URL(r.url()).pathname)){
   blocked.push(new URL(r.url()).pathname);return route.abort();
  }
  return route.continue();
 });
 page.on('pageerror',e=>errors.push(e.message));
 try{
  const machines=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/machines')&&r.status()===200);
  const sessions=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/sessions/my')&&r.status()===200);
  const login=page.waitForResponse(r=>r.url().includes('/steps_tracker/classic-session')&&r.status()===200);
  await page.goto('https://'+proof.host+'/truck/');
  assert.deepEqual(await (await machines).json(),[]);
  assert.deepEqual(await (await sessions).json(),[]);
  const auth=await (await login).json();
  const apiRoot=(await machines).url().replace(/\/machines(?:\?.*)?$/,'');
  for(const endpoint of ['/work_orders','/mobile/routes']){
   const response=await context.request.get(apiRoot+endpoint,{headers:{Authorization:'Bearer '+auth.access_token}});
   assert.equal(response.status(),200);assert.deepEqual(await response.json(),[]);
  }
  await page.getByRole('heading',{name:'Iniciar jornada',exact:true}).waitFor();
  const helpClose=page.getByRole('button',{name:'Cerrar',exact:true});
  if(await helpClose.count())await helpClose.click();
  const machine=page.getByRole('combobox',{name:/^Máquina/});
  await machine.waitFor();
  assert.equal(await machine.locator('option').count(),1);
  assert.equal(await page.getByRole('heading',{name:'Tienes jornadas abiertas',exact:true}).count(),0);
  assert.equal(await page.evaluate(()=>window.phoneGpsCalls),0);
  assert.deepEqual(blocked,[]);assert.deepEqual(errors,[]);
  if(process.env.GPS_UI_OUTPUT){fs.mkdirSync(process.env.GPS_UI_OUTPUT,{recursive:true});await page.screenshot({path:path.join(process.env.GPS_UI_OUTPUT,'cerro-clean-journey.png'),fullPage:true});}
  console.log('LEGACY_RETIREMENT_NATIVE_OK machines=0 open_test_journeys=0 work_orders=0 routes=0 phone_gps_calls=0 business_writes=0');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
