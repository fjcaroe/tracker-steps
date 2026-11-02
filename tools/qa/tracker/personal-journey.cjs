/* Actual served app, all classic HTTP directed to a prepared private copy. */
const fs=require('fs');const path=require('path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [proofFile,out]=process.argv.slice(2);const proof=JSON.parse(fs.readFileSync(proofFile,'utf8'));fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:process.env.PLAYWRIGHT_CHANNEL||'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},timezoneId:'America/Santiago',serviceWorkers:'block'});const page=await context.newPage();
  await page.addInitScript(({token})=>{localStorage.setItem('steps_movil_token',token);localStorage.setItem('steps_movil_settings',JSON.stringify({seenHelp:true}));navigator.geolocation.watchPosition=()=>1;navigator.geolocation.clearWatch=()=>{};},proof);
  await page.route('**/tracker-dev-api/**',async route=>{
   const req=route.request();const url='http://127.0.0.1:18013/'+new URL(req.url()).pathname.split('/tracker-dev-api/')[1]+new URL(req.url()).search;
   const response=await context.request.fetch(url,{method:req.method(),headers:{authorization:'Bearer '+proof.token,'content-type':'application/json'},data:req.postData()||undefined});await route.fulfill({response});
  });
  await page.goto('https://desarrollo.stepsapp.cl/truck/');
  await page.getByText('Este vehículo trabaja por distancia.',{exact:false}).waitFor();
  const form=page.locator('form').filter({has:page.getByRole('heading',{name:'Iniciar jornada',exact:true})});
  const machines=form.getByLabel('Máquina',{exact:false});if(await machines.locator('option').count()!==2)throw Error('Expected one real car plus placeholder');
  if(await machines.inputValue()!==String(proof.machine_id))throw Error('The real vehicle was not preselected');
  if(await form.getByLabel('Horómetro inicial',{exact:false}).count())throw Error('Car requires a fictitious hourmeter');
  if(await form.getByLabel('Litros en el estanque (opcional)',{exact:true}).inputValue()!=='')throw Error('Fuel was fabricated');
  await page.screenshot({path:path.join(out,'start-390.png'),fullPage:true});
  await form.getByRole('button',{name:'Iniciar jornada',exact:true}).click();
  await page.getByRole('button',{name:'Finalizar jornada',exact:true}).waitFor();
  await page.getByRole('button',{name:'Revisión previa',exact:true}).click();await page.getByRole('dialog').waitFor();
  await page.keyboard.press('Escape');
  // Close the checklist explicitly when the sheet does not bind Escape.
  const close=page.getByRole('button',{name:/Cerrar|Cancelar/}).first();if(await close.isVisible().catch(()=>false))await close.click();
  await page.getByRole('button',{name:'Finalizar jornada',exact:true}).click();
  const finish=page.getByRole('dialog',{name:'Finalizar jornada'});await finish.waitFor();
  if(await finish.getByLabel('Horómetro final',{exact:false}).count())throw Error('Car closing requires a fictitious hourmeter');
  await finish.getByRole('button',{name:'Confirmar y cerrar',exact:true}).click();
  await page.getByText('Resumen de la jornada',{exact:false}).waitFor();await page.screenshot({path:path.join(out,'closed-390.png'),fullPage:true});
  const response=await context.request.get('http://127.0.0.1:18013/work_orders',{headers:{authorization:'Bearer '+proof.token}});const rows=await response.json();const own=rows.find(r=>r.machine_id===proof.machine_id);
  if(!own||own.hourmeter_initial!==null||own.hourmeter_final!==null||own.fuel_tank_start_liters!==null||own.fuel_tank_end_liters!==null)throw Error('Unknown readings were not preserved as null');
  console.log('PERSONAL_JOURNEY_UI_OK single_car=True actual_defaults=True start_close=True readings_null=True fixture_writes_private_only=True');
 }finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
