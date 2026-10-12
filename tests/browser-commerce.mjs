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
const qa = path.join(root, 'runtime', `commerce-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8018';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8018'], {
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
  let p=await (await context.request.post(`${url}/api/products`,{data:{name:'PC commerce QA',sku:'QA-SALE'}})).json();
  await context.request.post(`${url}/api/movements`,{data:{product_id:p.id,type:'IN',quantity:10,reason:'Recette commerce',expected_version:1,idempotency_key:crypto.randomUUID()}});
  await navigate('Ventes et devis');await page.getByRole('button',{name:'Nouveau document'}).click();
  await page.getByLabel('Document',{exact:true}).selectOption('QUOTE');
  await page.getByLabel('Référence du document').fill('DEVIS-QA');
  await page.getByLabel('Produit ligne 1',{exact:true}).selectOption(String(p.id));
  await page.getByLabel('Quantité ligne 1',{exact:true}).fill('2');
  await page.getByLabel('Prix unitaire TTC ligne 1',{exact:true}).fill('119');
  await page.getByLabel('Taxe en % ligne 1',{exact:true}).fill('19');
  await page.getByLabel('Coût unitaire HT ligne 1',{exact:true}).fill('60');
  await page.getByRole('button',{name:'Créer le brouillon',exact:true}).click();
  await page.getByRole('heading',{name:'DEVIS-QA',exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,10);
  await page.getByLabel('Référence de la vente issue du devis').fill('VENTE-QA');
  await page.getByRole('checkbox').check();
  await page.route('**/api/commerce/documents/*/confirm',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Convertir en vente et retirer le stock',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/commerce/documents/*/confirm');
  await page.getByRole('button',{name:'Convertir en vente et retirer le stock',exact:true}).click();
  await page.getByRole('heading',{name:'VENTE-QA',exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,8);
  await page.getByLabel('Quantité retournée').fill('1');
  await page.getByLabel('État du produit retourné').selectOption('yes');
  await page.getByLabel('Motif du retour').fill('Retour revendable de recette');
  await page.getByRole('button',{name:'Confirmer le retour',exact:true}).click();
  await page.getByRole('heading',{name:'Historique des retours',exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,9);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`commerce-${width}.png`),fullPage:true});}
  await page.reload();await page.getByRole('heading',{name:'Votre stock, en un regard'}).waitFor();await navigate('Ventes et devis');
  await page.getByRole('button',{name:/VENTE-QA/}).click();await page.getByRole('heading',{name:'Historique des retours'}).waitFor();
  assert.deepEqual(errors,[]);console.log('Commerce OK : devis, conversion, réponse perdue/reprise sans doublon, retour et stock, persistance, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
