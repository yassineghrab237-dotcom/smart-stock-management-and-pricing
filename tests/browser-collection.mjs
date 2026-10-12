// Import CSV réel sur SQLite dédiée ; aucun mock de persistance.
import assert from 'node:assert/strict';
import { spawn, execFileSync } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomBytes } from 'node:crypto';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, 'runtime', `collection-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8028';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8028'], {
  cwd: root, windowsHide: true,
  env: { ...process.env, SMART_STOCK_DB: path.join(qa, 'isolated.sqlite3'), SMART_STOCK_DEV: '0', SMART_STOCK_COLLECTION:'0' },
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
  const created = await context.request.post(`${url}/api/products`, {data:{name:'PC recette veille',sku:'QA-MARKET',current_price:'1200'}});
  const item = await created.json(); assert(created.ok());
  await navigate('Veille concurrentielle');
  await page.getByLabel('Produit à surveiller').selectOption(String(item.id));
  await page.getByLabel('Marque canonique').fill('QA');
  await page.getByLabel('Référence constructeur canonique').fill('MPN-1');
  await page.getByLabel('Configuration, état et garantie').fill('16 Go / 512 Go / neuf / garantie 1 an');
  await page.getByLabel('Motif de définition de l’identité').fill('Recette synthétique');
  await page.route('**/api/collection/products/*/identity',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Enregistrer l’identité',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/collection/products/*/identity');
  await page.getByRole('button',{name:'Enregistrer l’identité',exact:true}).click();
  await page.getByText('2. Ajouter une fiche à surveiller',{exact:true}).click();
  await page.getByLabel('Enseigne à collecter').selectOption('Mytek');
  await page.getByLabel('URL publique à collecter').fill('https://www.mytek.tn/pc-qa.html');
  await page.getByRole('button',{name:'Activer cette surveillance',exact:true}).click();
  await page.getByRole('button',{name:'Collecter maintenant',exact:true}).waitFor();
  // Real durable worker with explicit synthetic network fixture; no retailer contacted.
  execFileSync(path.join(root,'.venv-local','Scripts','python.exe'),['-c',`from tests.test_collection import fake_fetch; from services.stock_service.app.services.collection.worker import run_one; import os; run_one(os.environ['SMART_STOCK_DB'],fetcher=fake_fetch,throttle=False)`],{cwd:root,windowsHide:true,env:{...process.env,SMART_STOCK_DB:path.join(qa,'isolated.sqlite3'),SMART_STOCK_COLLECTION:'0'}});
  await page.getByRole('button',{name:'Actualiser les collectes'}).click();
  await page.getByText('Valider ou refuser le rapprochement',{exact:true}).click();
  await page.getByLabel('Décision de rapprochement').selectOption('accept');
  await page.getByLabel('Taxes vérifiées sur la fiche').selectOption('TTC');
  await page.getByLabel('Livraison vérifiée pour une unité').fill('0');
  await page.getByLabel('Preuve et motif de rapprochement').fill('Fixture produit identique ; aucune observation réelle.');
  await page.route('**/api/collection/jobs/*/review',async route=>{await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Enregistrer la décision'}).click();
  await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/collection/jobs/*/review');
  await page.getByRole('button',{name:'Enregistrer la décision'}).click();
  await page.getByText('Offre validée',{exact:true}).waitFor();
  const observations=await (await context.request.get(`${url}/api/market/products/${item.id}`)).json();assert.equal(observations.items.length,1);assert.equal(observations.items[0].price,'100.5000');
  await page.getByRole('button',{name:'Mettre en pause',exact:true}).click();await page.getByRole('button',{name:'Reprendre la surveillance'}).waitFor();
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow ${width}`);await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(evidence,`collection-${width}.png`),fullPage:true});}
  await page.reload();await page.getByRole('heading',{name:'Votre stock, en un regard'}).waitFor();await navigate('Veille concurrentielle');await page.getByLabel('Produit à surveiller').selectOption(String(item.id));await page.getByText('Offre validée',{exact:true}).waitFor();
  assert.deepEqual(await (await context.request.get(`${url}/api/products/${item.id}`)).json(),item);assert.deepEqual(errors,[]);
  console.log('OK: identité, surveillance, vrai worker sur fixture synthétique, validation avec réponse perdue sans doublon, pause, persistance, 3 largeurs, zéro pageerror, prix/stock intacts');
} finally {if(browser)await browser.close();child.kill();}
