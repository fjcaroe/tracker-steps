/* Read-only browser acceptance. No business document is saved. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { chromium } = require('playwright');
(async () => {
 const proof = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
 const output = process.argv[3]; fs.mkdirSync(output, {recursive:true});
 const browser = await chromium.launch({headless:true, executablePath:process.env.CHROME_PATH});
 let page;
 try {
  const context = await browser.newContext({viewport:{width:1440,height:1000},locale:'es-CL'});
  await context.addCookies([{name:'session_id',value:proof.session_id,domain:proof.host,path:'/',httpOnly:true,secure:true,sameSite:'Lax'},
   {name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
  page = await context.newPage(); const errors=[];
  page.on('pageerror', e=>errors.push(e.message));
  async function openAction(name, selector) {
   await page.goto(`https://${proof.host}/web#action=${proof.actions[name]}&cids=${proof.company_id}`,{waitUntil:'domcontentloaded',timeout:120000});
   await page.locator(selector).waitFor({timeout:120000});
   assert.equal(await page.locator('.o_error_dialog').count(),0);
  }
  await openAction('receipts','.o_list_view');
  await page.getByText('Recepciones vigentes',{exact:true}).first().waitFor();
  await page.screenshot({path:path.join(output,'current-receipts.png'),fullPage:true});
  await openAction('report','.o_pivot');
  await page.screenshot({path:path.join(output,'current-reception-report.png'),fullPage:true});
  await openAction('interplant','.o_list_view');
  await page.screenshot({path:path.join(output,'interplant-receipts.png'),fullPage:true});
  await openAction('guides','.o_list_view');
  await page.getByRole('button',{name:/^(Nuevo|New)$/}).click();
  await page.locator('.o_form_view').waitFor();
  const type=page.locator('.o_field_widget[name="dispatch_type_id"]');
  const recipient=page.locator('.o_field_widget[name="partner_id"]');
  assert.ok((await type.boundingBox()).y < (await recipient.boundingBox()).y);
  await page.getByRole('tab',{name:'Folio Pallet',exact:true}).click();
  await page.locator('.o_field_widget[name="load_tag_ids"] .o_field_x2many_list_row_add a').click();
  const dialog=page.getByRole('dialog'); await dialog.waitFor();
  const headers=await dialog.locator('th').allTextContents();
  for (const fragment of ['Tipo de tarja','Número de tarja','Productor','Cajas','Kilos'])
   assert.ok(headers.some(h=>h.includes(fragment)),`Missing selector column ${fragment}: ${headers}`);
  await page.screenshot({path:path.join(output,'dispatch-tag-selector.png'),fullPage:true});
  assert.equal(errors.length,0,errors.join('; '));
  const result={host:proof.host,company:proof.company_id,currentReceiptFilter:true,receptionPivot:true,
   interplantMenu:true,typeBeforeRecipient:true,tagSelectorColumns:headers,errors};
  fs.writeFileSync(path.join(output,'ui-result.json'),JSON.stringify(result,null,2));
  console.log('INTERPLANT_UI_OK '+JSON.stringify(result));
 } catch(e) {
  if(page) { await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});
   fs.writeFileSync(path.join(output,'failure.txt'),await page.locator('body').innerText().catch(()=>'')); }
  throw e;
 } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exitCode=1;});
