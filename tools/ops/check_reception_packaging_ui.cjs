/* Read-only acceptance of live T241 receipts, tags and draft advances. */
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const {chromium}=require('playwright');

(async()=>{
    const proof=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
    const output=process.argv[3];
    assert.equal(proof.host,'cerroelplomo.stepsapp.cl');
    fs.mkdirSync(output,{recursive:true});
    const browser=await chromium.launch({headless:true,executablePath:process.env.CHROME_PATH});
    let page;
    try {
        const context=await browser.newContext({locale:'es-CL',viewport:{width:1440,height:1000}});
        await context.addCookies([
            {name:'session_id',value:proof.session_id,domain:proof.host,path:'/',secure:true,httpOnly:true},
            {name:'cids',value:String(proof.company_id),domain:proof.host,path:'/',secure:true}]);
        page=await context.newPage();page.setDefaultTimeout(20000);
        const errors=[];page.on('pageerror',error=>errors.push(error.message));
        await page.route('**/web/dataset/call_kw/**',async route=>{
            const method=route.request().postDataJSON()?.params?.method || '';
            if (/^(create|write|unlink|web_save|action_)/.test(method)) throw new Error('Unexpected browser business write: '+method);
            await route.continue();
        });
        function relation(value){return typeof value==='number'?value:Array.isArray(value)?value[0]:value?.id;}
        async function open(action,model,id){
            const response=page.waitForResponse(r=>r.url().includes('/'+model+'/web_read'),{timeout:60000});
            await page.goto(`https://${proof.host}/web#action=${action}&model=${model}&id=${id}&view_type=form&cids=${proof.company_id}`,
                {waitUntil:'domcontentloaded',timeout:120000});
            const data=await (await response).json();assert.ok(!data.error,data.error?.data?.message);
            await page.locator('.o_form_view').waitFor();
            assert.equal(await page.locator('.o_error_dialog').count(),0);
            const row=data.result.find(r=>r.id===id);assert.ok(row,'Wrong record opened');return row;
        }
        const receipts=[];
        for(const receipt of proof.receipts){
            const row=await open(proof.actions.receipts,'stock.picking',receipt.id);
            assert.equal(row.name,receipt.name);
            const operations=row.move_ids_without_package || row.move_ids;
            assert.ok(operations?.length,'Missing native operations');
            assert.ok(operations.every(m=>relation(m.product_packaging_id)===proof.packaging.id));
            await page.getByText(proof.packaging.name,{exact:true}).first().waitFor();
            await page.screenshot({path:path.join(output,`receipt-${receipt.id}.png`),fullPage:true});
            receipts.push(receipt.id);
        }
        // Every tag was checked transactionally and by native web_read. Render
        // one per receipt to cover the actual operator form in each origin.
        const tagIds=[];
        for(const receipt of proof.receipts){
            const tag=proof.tags.find(t=>t.receipt_id===receipt.id);
            if(!tag)continue;
            const row=await open(proof.actions.tags,'stock.quant.package',tag.id);
            assert.equal(relation(row.step_packaging_id),proof.packaging.id);
            assert.equal(row.step_actual_kg,tag.kilos);
            const field=page.locator('.o_field_widget[name="step_packaging_id"]');
            await field.scrollIntoViewIfNeeded();
            await page.screenshot({path:path.join(output,`tag-${tag.id}.png`),fullPage:true});tagIds.push(tag.id);
        }
        for(const draft of proof.drafts){
            const row=await open(proof.actions.drafts,'purchase.order',draft.id);
            assert.equal(row.step_fruit_state,'draft');assert.equal(row.amount_total,draft.total);
            assert.ok(row.order_line.some(l=>relation(l.step_advance_packaging_id)===proof.packaging.id));
            await page.locator('.o_field_widget[name="amount_total"]').scrollIntoViewIfNeeded();
            await page.screenshot({path:path.join(output,`draft-${draft.id}.png`),fullPage:true});
        }
        assert.deepEqual(errors,[]);
        const result={receipts,tagForms:tagIds,transactionallyVerifiedTags:proof.tags.length,
                      draftAdvances:proof.drafts.length,nativePackaging:proof.packaging.id,browserWrites:0,errors};
        fs.writeFileSync(path.join(output,'ui-result.json'),JSON.stringify(result,null,2));
        console.log('T241_BROWSER_OK '+JSON.stringify(result));
    }catch(error){if(page)await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});throw error;}
    finally{await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
