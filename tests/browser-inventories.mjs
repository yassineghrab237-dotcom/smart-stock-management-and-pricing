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
const qa = path.join(root, 'runtime', `inventories-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8025';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8025'], {
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
  const p=await (await context.request.post(`${url}/api/products`,{data:{name:'PC inventaire QA',sku:'COUNT-QA'}})).json();
  await context.request.post(`${url}/api/movements`,{data:{product_id:p.id,type:'IN',quantity:10,reason:'Recette',expected_version:1,idempotency_key:crypto.randomUUID()}});
  await navigate('Inventaires physiques');await page.getByRole('button',{name:'Nouvelle campagne d’inventaire'}).click();
  await page.getByLabel('Nom de la campagne').fill('Inventaire bureau QA');await page.getByRole('button',{name:'Sélectionner tous les produits'}).click();await page.getByRole('button',{name:'Ouvrir le comptage',exact:true}).click();
  await page.getByRole('heading',{name:'Inventaire bureau QA',exact:true}).waitFor();await page.getByLabel('Quantité comptée COUNT-QA').fill('8');await page.getByLabel('Motif du comptage COUNT-QA').fill('Comptage réel de recette');await page.getByRole('button',{name:'Enregistrer le comptage COUNT-QA'}).click();
  await page.getByText('Théorique au comptage : 10 · compté : 8 · écart : -2',{exact:true}).waitFor();assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,10);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`inventories-${width}.png`),fullPage:true});}
  await page.getByLabel('Motif de validation de l’inventaire').fill('Écart vérifié');await page.getByRole('checkbox').check();
  await page.route('**/api/inventories/*/apply',async route=>{await route.fetch();await route.abort('failed');});await page.getByRole('button',{name:'Valider et ajuster les stocks'}).click();await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/inventories/*/apply');await page.getByRole('button',{name:'Valider et ajuster les stocks'}).click();await page.getByText('Inventaire validé, écarts appliqués.',{exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${p.id}`)).json()).current_stock,8);
  assert.equal((await (await context.request.get(`${url}/api/movements`)).json()).items.filter(m=>m.type==='ADJUSTMENT').length,1);
  assert.deepEqual(errors,[]);console.log('Inventaire OK : sélection, comptage sans mouvement, ajustement final, réponse perdue sans doublon, trois largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
