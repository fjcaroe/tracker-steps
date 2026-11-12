/* Native destination selector acceptance; all edits remain unsaved. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require('playwright');
(async()=>{
 const proof = JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const output = process.argv[3]; fs.mkdirSync(output,{recursive:true});
 const test = proof.warehouse_case; assert.ok(test);
 const browser = await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
 let page;
 try {
  const context = await browser.newContext({viewport:{width:1440,height:1100},locale:'es-CL'});
  await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true,sameSite:'Lax'},
   {name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  page=await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async response=>{
   if(response.url().includes('/web/dataset/')) {
    const data=await response.json().catch(()=>null);
    if(data?.error) {errors.push(data.error.message);fs.writeFileSync(path.join(output,'rpc-error.json'),JSON.stringify(data.error,null,2));}
   }
  });
  const record = test.guide_id ? `&id=${test.guide_id}&model=step.dispatch.guide&view_type=form` : '';
  await page.goto(`https://${proof.host}/web?t209_review=destination#action=${proof.actions.guides}&cids=${proof.company_id}${record}`,{waitUntil:'domcontentloaded',timeout:120000});
  if(!test.guide_id) {
   await page.locator('.o_list_view').waitFor({timeout:120000});
   await page.getByRole('button',{name:/^(Nuevo|New)$/}).click();
  }
  await page.locator('.o_form_view').waitFor({timeout:120000});
  async function choose(field,label) {
   const input=page.locator(`.o_field_widget[name="${field}"] input`);
   await input.fill(label);
   const update=page.waitForResponse(r=>r.url().includes('/step.dispatch.guide/onchange'));
   await page.locator('.o-autocomplete--dropdown-item').filter({hasText:label}).first().click();
   const response=await (await update).json(); assert.ok(!response.error);
   await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))));
  }
  if(!test.guide_id) {
   if(test.type) await choose('dispatch_type_id',test.type);
   if(!test.no_destination) await choose('partner_id',test.partner);
  }
  const input=page.locator('.o_field_widget[name="step_destination_warehouse_id"] input');
  if(test.type) {
   await input.waitFor();
   if(!test.guide_id && test.warehouses.length===1)
    await page.waitForFunction(expected=>document.querySelector('.o_field_widget[name="step_destination_warehouse_id"] input')?.value===expected,test.warehouses[0]);
   await input.fill(''); await input.click();
  }
  else {assert.equal(proof.host,'desarrollo.stepsapp.cl'); assert.equal(await input.isVisible(),false);}
  for(const name of test.warehouses)
   await page.locator('.o-autocomplete--dropdown-item').filter({hasText:name}).first().waitFor();
  await page.screenshot({path:path.join(output,'destination-warehouse-options.png'),fullPage:true});
  if(!test.no_destination) {
   await page.locator('.o-autocomplete--dropdown-item').filter({hasText:test.warehouses[0]}).first().click();
   assert.equal(await input.inputValue(),test.warehouses[0]);
  } else {
   assert.equal(proof.host,'desarrollo.stepsapp.cl');
   if(test.type) assert.equal(await input.inputValue(),'');
  }
  assert.equal(await page.locator('.o_error_dialog').count(),0);
  const cookie=(await context.cookies()).find(x=>x.name==='cids');
  assert.equal(cookie.value,String(proof.company_id));
  const companyField=page.locator('.o_field_widget[name="company_id"]');
  if(await companyField.count()) {
   const companyText=await companyField.locator('input').count() ? await companyField.locator('input').inputValue() : await companyField.innerText();
   assert.ok(companyText.includes(test.source_name));
  } else {
   assert.ok(test.no_destination && proof.host === 'desarrollo.stepsapp.cl');
  }
  assert.equal(errors.length,0);
  await page.screenshot({path:path.join(output,'destination-warehouse-selected.png'),fullPage:true});
  const result={host:proof.host,company:proof.company_id,destinationWarehouseChoices:test.warehouses,
   sourceCompanyUnchanged:true,noConfiguredDestination:!!test.no_destination,existingDraft:!!test.guide_id,businessDocumentSaved:false,errors};
  fs.writeFileSync(path.join(output,'destination-ui-result.json'),JSON.stringify(result,null,2));
  console.log('DESTINATION_UI_OK '+JSON.stringify(result));
 } catch(e) {
  if(page) {
   const details=page.getByText('Ver detalles técnicos',{exact:true});
   if(await details.isVisible().catch(()=>false)) await details.click().catch(()=>{});
   await page.screenshot({path:path.join(output,'destination-failure.png'),fullPage:true}).catch(()=>{});
   fs.writeFileSync(path.join(output,'destination-failure.txt'),await page.locator('body').innerText().catch(()=>''));}
  throw e;
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
