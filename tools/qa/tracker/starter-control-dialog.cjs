/* Hardware fixtures only in Development. Both dispatches are intercepted in-browser. */
const fs=require('fs'),path=require('path'),assert=require('assert');const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
(async()=>{
 const [factsFile,out]=process.argv.slice(2),f=JSON.parse(fs.readFileSync(factsFile,'utf8')).development;fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({headless:true,channel:'chrome'});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,serviceWorkers:'block'});const page=await context.newPage();let receipts=[],sent=[];
  await page.route('**/steps_tracker/context',async route=>{const r=await route.fetch();const data=await r.json();assert(data.vehicle_limited&&data.control_preview);await route.fulfill({json:{...data,control_preview:false,can_control_starter:true}});});
  await page.route('**/steps_tracker/api/assets/*/starter-control',route=>route.fulfill({json:{wiring_verified:true,connected:true,can_operate:true,preview:false,safe_to_inhibit:true,commands:receipts}}));
  await page.route('**/steps_tracker/starter/*/command',async route=>{
   assert(new URL(route.request().url()).hostname==='desarrollo.stepsapp.cl');const form=new URLSearchParams(route.request().postData());const body=JSON.parse(form.get('payload'));
   assert(form.get('password')==='browser-copy-only'&&body.present&&body.engine_off&&body.plate_confirmation===f.plate&&body.intention_id);sent.push(body.type);
   const row={id:'00000000-0000-0000-0000-00000000005'+sent.length,type:body.type,state:'sent_unconfirmed',result:'Entrega simulada en el navegador; sin orden al dispositivo.',created_at:new Date().toISOString(),confirmed_at:null,declared_result:null};receipts=[row,...receipts];await route.fulfill({json:row});
  });
  await page.goto('https://desarrollo.stepsapp.cl/web/login?redirect=%2Fweb_tracker%2F%23protection');await page.locator('input[name="login"]').fill(f.preview_login);await page.locator('input[name="password"]').fill(f.preview_password);await page.locator('form:has(input[name="password"]) button[type="submit"]').click();
  await page.getByRole('navigation',{name:'Mi Tracker',exact:true}).waitFor();await page.goto('https://desarrollo.stepsapp.cl/web_tracker/#protection');
  for(const label of ['Bloquear arranque','Restituir arranque']){
   await page.getByRole('button',{name:label,exact:true}).click();const d=page.getByRole('dialog',{name:label==='Bloquear arranque'?'Bloquear el próximo arranque':'Restituir el arranque'});await d.waitFor();
   await d.getByLabel('Escribe la patente para confirmar').fill(f.plate);await d.getByLabel('Tu contraseña de ingreso a Steps').fill('browser-copy-only');
   await d.getByLabel('El vehículo está detenido y el motor apagado.').check();await d.getByLabel('Estoy junto al vehículo o coordinado en este momento con el instalador.').check();await d.getByLabel('Motivo / resultado comprobado').fill('Ensayo aislado del diálogo sin envío físico');
   await d.getByRole('button',{name:'Confirmar orden',exact:true}).click();await d.waitFor({state:'hidden'});await page.getByText('Entrega simulada en el navegador; sin orden al dispositivo.',{exact:false}).first().waitFor();
  }
  assert.deepStrictEqual(sent,['inhibit_next_start','restore_start']);await page.locator('.starter-control').screenshot({path:path.join(out,'simulated-relay-dialog-result.png')});
  fs.writeFileSync(path.join(out,'proof.json'),JSON.stringify({development:true,block_dialog:true,restore_dialog:true,real_orders:false,hardware_responses:'browser fixtures'}));
  console.log('STARTER_DIALOGS_QA_OK block=True restore=True real_orders=False');await page.goto('https://desarrollo.stepsapp.cl/web/session/logout?redirect=/web/login');
 }finally{await browser.close();}
})().catch(e=>{console.error(e.message);process.exitCode=1;});
