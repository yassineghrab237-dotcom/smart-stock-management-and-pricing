import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const require=createRequire(import.meta.url);
const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
const browser=await chromium.launch({headless:true});
try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto('http://127.0.0.1:8012');
  await page.getByLabel('Adresse e-mail').fill('native@example.test');await page.getByLabel('Mot de passe',{exact:true}).fill('StockQaTest123!');await page.getByRole('button',{name:'Se connecter',exact:true}).click();
  await page.getByRole('navigation').getByRole('button',{name:'Produits et stock',exact:true}).click();await page.getByRole('button',{name:'Câble QA mobile',exact:true}).click();await page.getByRole('heading',{name:'Câble QA mobile',exact:true}).waitFor();
  const products=(await (await page.request.get('http://127.0.0.1:8012/api/products')).json()).items;
  assert.equal(products.length,1);assert.equal(products[0].current_stock,27);assert.equal(products[0].current_price,'12.3456');assert.equal((await (await page.request.get('http://127.0.0.1:8012/api/movements')).json()).items.length,2);
  await page.screenshot({path:path.join(root,'docs/evidence/native-web-consistency.png'),fullPage:true});assert.deepEqual(errors,[]);
  await writeFile(path.join(root,'docs/evidence/native-web-results.json'),JSON.stringify({date:new Date().toISOString(),stock:27,price:'12.3456',movements:2,checks:['Produit créé depuis les vrais écrans Flutter retrouvé dans le web','Mouvement et prix natifs persistants','Reprise via stockage natif sécurisé sans double mouvement'],jsErrors:errors},null,2));console.log('Cohérence web/native vérifiée : stock 27, prix 12.3456, 2 mouvements.');
}finally{await browser.close();}
