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
const qa = path.join(root, 'runtime', `replenishment-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8021';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8021'], {
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
  const supplier=await (await context.request.post(`${url}/api/crm/contacts`,{data:{name:'Fournisseur colis QA',kind:'SUPPLIER',idempotency_key:crypto.randomUUID()}})).json();
  await context.request.post(`${url}/api/products`,{data:{name:'PC réassort QA',sku:'RESTOCK-QA',threshold_min:3,threshold_max:10}});
  await navigate('Réapprovisionnement');await page.getByRole('button',{name:'Renseigner les conditions',exact:true}).click();
  await page.getByLabel('Fournisseur de réapprovisionnement').selectOption(String(supplier.id));
  await page.getByLabel('Coût fournisseur TND HT').fill('10');await page.getByLabel('Délai en jours').fill('7');await page.getByLabel('Minimum par commande de ce produit').fill('5');await page.getByLabel('Unités par colis').fill('4');await page.getByLabel('Motif des conditions').fill('Accord de recette');
  await page.getByRole('button',{name:'Enregistrer les conditions',exact:true}).click();await page.getByText('Conditions enregistrées.',{exact:true}).waitFor();await page.keyboard.press('Escape');
  await page.getByLabel('Fournisseur à planifier').selectOption(String(supplier.id));await page.getByLabel('Enveloppe pour ces propositions TND HT').fill('90');await page.getByRole('button',{name:'Calculer la proposition'}).click();
  await page.getByText('8 unité(s)',{exact:true}).waitFor();
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`replenishment-${width}.png`),fullPage:true});}
  await page.getByLabel('Référence du brouillon d’achat').fill('REASSORT-QA');await page.getByRole('checkbox').check();
  await page.route('**/api/replenishment/draft',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Créer le brouillon d’achat proposé'}).click();await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/replenishment/draft');await page.getByRole('button',{name:'Créer le brouillon d’achat proposé'}).click();
  await page.getByRole('button',{name:'Ouvrir les achats'}).waitFor();assert.equal((await (await context.request.get(`${url}/api/purchases/orders`)).json()).items.length,1);
  await page.getByRole('button',{name:'Ouvrir les achats'}).click();await page.getByRole('button',{name:/REASSORT-QA/}).click();await page.getByRole('heading',{name:'REASSORT-QA',exact:true}).waitFor();
  await page.getByText('0 reçue(s) / 8 commandée(s)',{exact:false}).waitFor();
  assert.deepEqual(errors,[]);console.log('Réassort OK : conditions, budget, colis, brouillon relié aux achats, réponse perdue sans doublon, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
