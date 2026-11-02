/* Native existing account, actual Development API, no fixture data or writes. */
const fs=require('fs');
const path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,out]=process.argv.slice(2);const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));if(proof.host!=='desarrollo.stepsapp.cl')throw Error('Development only');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},timezoneId:'America/Santiago',serviceWorkers:'block'});
  await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true},{name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  const page=await context.newPage();let eventWrites=0;page.on('request',request=>{if(request.method()==='POST'&&/\/mobile\/services\/.*\/events/.test(request.url()))eventWrites++;});
  await page.addInitScript(()=>localStorage.setItem('steps_movil_settings',JSON.stringify({seenHelp:true})));
  await page.goto('https://'+proof.host+'/truck/');await page.getByRole('button',{name:'Hoy',exact:true}).click();
  await page.getByRole('heading',{name:'Mi servicio',exact:true}).waitFor();await page.getByText('No tienes servicios de pasajeros asignados.',{exact:true}).waitFor();
  await page.screenshot({path:path.join(out,'native-hoy-390.png'),fullPage:true});
  await page.getByRole('button',{name:'Perfil',exact:true}).click();await page.getByText('1.6.0',{exact:false}).waitFor();
  const identity=await page.evaluate(async()=>{const token=localStorage.getItem('steps_movil_token');const response=await fetch('/tracker-dev-api/auth/me',{headers:{authorization:'Bearer '+token}});return response.ok?await response.json():null;});
  const native=await page.evaluate(async()=>{const response=await fetch('/steps_tracker/context');return response.ok?await response.json():null;});
  if(!identity||!native||!identity.username.startsWith('odoo-')||!identity.username.endsWith('-'+native.user_id))throw Error('Existing native Development identity not preserved');
  await page.screenshot({path:path.join(out,'native-profile-390.png'),fullPage:true});
  await page.goto('https://'+proof.host+'/truck/#gps');await page.getByText('PKFX47',{exact:false}).first().waitFor();
  await page.locator('.hardware-car-pin').first().waitFor();await page.screenshot({path:path.join(out,'native-gps-390.png'),fullPage:true});
  if(eventWrites)throw Error('Native review wrote passenger events');
  console.log('PASSENGER_NATIVE_OK existing_account=True development_api=True hoy_menu=True version=1.6.0 hardware_map=True passenger_writes=0');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
