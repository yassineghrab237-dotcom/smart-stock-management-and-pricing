// Import CSV réel sur SQLite dédiée ; aucun mock de persistance.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, 'runtime', `insights-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8020';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8020'], {
  cwd: root, windowsHide: true,
  env: { ...process.env, SMART_STOCK_DB: path.join(qa, 'isolated.sqlite3'), SMART_STOCK_DEV: '0' },
});
let logs = '';
child.stdout.on('data', d => { logs += d; }); child.stderr.on('data', d => { logs += d; });
let browser;
const checks = []; const errors = [];
try {
  for (let i = 0; i < 100; i++) {
    if (child.exitCode !== null) throw new Error(logs);
    try { if ((await fetch(`${url}/api/health`)).ok) break; } catch {}
    if (i === 99) throw new Error('Serveur indisponible');
    await new Promise(r => setTimeout(r, 100));
  }
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message));
  const password = `Import9!${randomBytes(16).toString('hex')}`;
  await page.goto(url);
  await page.getByLabel('Nom', { exact: true }).fill('QA Imports');
  await page.getByLabel('Adresse e-mail').fill('qa-import@example.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Créer mon espace' }).click();
  await page.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor();
  async function navigate(name) {
    if (await page.getByRole('button', { name: 'Ouvrir le menu' }).isVisible()) await page.getByRole('button', { name: 'Ouvrir le menu' }).click();
    await page.getByRole('navigation').getByRole('button', { name, exact: true }).click();
  }
  async function upload(text, filename = 'recette.csv') {
    await page.getByLabel('Fichier CSV').setInputFiles({ name: filename, mimeType: 'text/csv', buffer: Buffer.from(text) });
    await page.getByRole('button', { name: 'Analyser le fichier', exact: true }).click();
  }
  const contact=await (await context.request.post(`${url}/api/crm/contacts`,{data:{name:'Client paniers QA',idempotency_key:crypto.randomUUID()}})).json();
  const products=[];
  for(const [sku,name] of [['PC-QA','Portable recette'],['MOUSE-QA','Souris recette']]){
    const p=await (await context.request.post(`${url}/api/products`,{data:{name,sku}})).json();products.push(p);
    await context.request.post(`${url}/api/movements`,{data:{product_id:p.id,type:'IN',quantity:10,reason:'Recette',expected_version:1,idempotency_key:crypto.randomUUID()}});
  }
  for(let i=0;i<2;i++){
    const draft=await (await context.request.post(`${url}/api/commerce/documents`,{data:{kind:'SALE',reference:`VENTE-${i}`,customer_id:contact.id,lines:products.map(p=>({product_id:p.id,quantity:1,unit_price_ttc:'119',tax_rate:'19',unit_cost_ht:'60'})),idempotency_key:crypto.randomUUID()}})).json();
    const response=await context.request.post(`${url}/api/commerce/documents/${draft.id}/confirm`,{data:{expected_version:1,product_versions:Object.fromEntries(products.map(p=>[p.id,i+2])),idempotency_key:crypto.randomUUID()}});assert.equal(response.status(),200);
  }
  await navigate('Rentabilité et paniers');await page.getByRole('heading',{name:'Produits phares par contribution'}).waitFor();
  await page.getByRole('heading',{name:'PC-QA + MOUSE-QA',exact:true}).waitFor();
  assert.equal(await page.locator('.insights-metrics article').nth(3).locator('strong').innerText(),'160,00 TND');
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`insights-${width}.png`),fullPage:true});}
  await page.getByLabel('Ventes depuis le').fill('2020-01-01');await page.getByLabel('Ventes jusqu’au').fill('2020-01-31');await page.getByRole('button',{name:'Appliquer la période'}).click();await page.getByText('Aucune vente pour cette période.').waitFor();
  await navigate('Clients et fournisseurs');await page.getByRole('button',{name:/Client paniers QA/}).click();await page.getByRole('heading',{name:'Achats du client · 90 derniers jours'}).waitFor();await page.getByText('476,00 TND TTC',{exact:true}).waitFor();
  assert.deepEqual(errors,[]);console.log('Rentabilité OK : calcul depuis ventes réelles, associations, filtres, fiche client, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
