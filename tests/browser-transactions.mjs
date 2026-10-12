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
const qa = path.join(root, 'runtime', `transactions-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8022';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8022'], {
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
  const p=await (await context.request.post(`${url}/api/products`,{data:{name:'PC CSV QA',sku:'CSV-QA'}})).json();
  await context.request.post(`${url}/api/movements`,{data:{product_id:p.id,type:'IN',quantity:10,reason:'Recette',expected_version:1,idempotency_key:crypto.randomUUID()}});
  await navigate('Imports CSV');await page.getByRole('button',{name:'Ventes avec sortie de stock',exact:true}).click();
  await upload('reference,sku,sold_on,quantity,unit_price_ttc,tax_rate,discount_ttc,unit_cost_ht,customer_id\nCSV-VENTE-QA,CSV-QA,2026-10-01,2,119,19,0,60,');
  await page.getByText('Toutes les lignes sont valides',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Vérifier et confirmer l’import'}).click();
  await page.route('**/api/imports/commit',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Confirmer l’enregistrement',exact:true}).click();await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/imports/commit');await page.getByRole('button',{name:'Vérifier et confirmer l’import'}).click();await page.getByRole('button',{name:'Confirmer l’enregistrement',exact:true}).click();
  await page.getByText('Ce fichier avait déjà été enregistré. Aucune ligne ajoutée.',{exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,8);
  await navigate('Ventes et devis');await page.getByRole('button',{name:/CSV-VENTE-QA/}).click();await page.getByRole('heading',{name:'CSV-VENTE-QA',exact:true}).waitFor();await page.getByText(/Vente du 2026-10-01/).waitFor();
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`transactions-${width}.png`),fullPage:true});}
  assert.deepEqual(errors,[]);console.log('CSV opérationnel OK : aperçu, commit, réponse perdue/reprise, sortie unique, document daté, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
