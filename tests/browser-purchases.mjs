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
const qa = path.join(root, 'runtime', `purchases-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8019';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8019'], {
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
  const supplier=await (await context.request.post(`${url}/api/crm/contacts`,{data:{name:'Fournisseur QA',kind:'SUPPLIER',idempotency_key:crypto.randomUUID()}})).json();
  const p=await (await context.request.post(`${url}/api/products`,{data:{name:'PC achats QA',sku:'QA-BUY'}})).json();
  await navigate('Achats fournisseurs');await page.getByRole('button',{name:'Nouvelle commande fournisseur',exact:true}).click();
  await page.getByLabel('Référence de commande').fill('ACHAT-QA');
  await page.getByLabel('Fournisseur',{exact:true}).selectOption(String(supplier.id));
  await page.getByLabel('Date de réception prévue').fill('2026-12-01');
  await page.getByLabel('Produit à commander ligne 1').selectOption(String(p.id));
  await page.getByLabel('Quantité commandée ligne 1').fill('5');
  await page.getByLabel('Coût HT ligne 1').fill('60');
  await page.getByRole('button',{name:'Créer la commande brouillon',exact:true}).click();
  await page.getByRole('heading',{name:'ACHAT-QA',exact:true}).waitFor();
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Confirmer la commande',exact:true}).click();
  await page.getByRole('heading',{name:'Réceptionner la livraison'}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,0);
  await page.getByLabel('Quantité reçue QA-BUY').fill('2');await page.getByLabel('Référence du bon ou motif de réception').fill('BL-1');
  await page.route('**/api/purchases/orders/*/receive',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Enregistrer la réception et augmenter le stock',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/purchases/orders/*/receive');
  await page.getByRole('button',{name:'Enregistrer la réception et augmenter le stock',exact:true}).click();
  await page.getByText('2 reçue(s) / 5 commandée(s)',{exact:false}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,2);
  assert.equal(await page.getByLabel('Référence du bon ou motif de réception').inputValue(),'');
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`purchases-${width}.png`),fullPage:true});}
  await page.getByLabel('Quantité reçue QA-BUY').fill('3');await page.getByLabel('Référence du bon ou motif de réception').fill('BL-2');
  await page.getByRole('button',{name:'Enregistrer la réception et augmenter le stock',exact:true}).click();
  await page.getByText('5 reçue(s) / 5 commandée(s)',{exact:false}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,5);
  await page.reload();await page.getByRole('heading',{name:'Votre stock, en un regard'}).waitFor();await navigate('Achats fournisseurs');
  await page.getByRole('button',{name:/ACHAT-QA/}).click();await page.getByText('5 reçue(s) / 5 commandée(s)',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);console.log('Achats OK : commande, réception partielle, réponse perdue/reprise sans doublon, solde complet, persistance, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
