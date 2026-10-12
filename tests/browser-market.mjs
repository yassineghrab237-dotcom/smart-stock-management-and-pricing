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
const qa = path.join(root, 'runtime', `market-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8016';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8016'], {
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
  const created = await context.request.post(`${url}/api/products`, {data:{name:'PC recette veille',sku:'QA-MARKET',current_price:'1200'}});
  const item = await created.json(); assert(created.ok());
  await navigate('Veille concurrentielle');
  await page.getByLabel('Produit à surveiller').selectOption(String(item.id));
  await page.getByLabel('URL de la fiche produit').fill('https://www.tunisianet.com.tn/qa-pc.html');
  await page.getByLabel('Référence fabricant').fill('QA-M123');
  await page.getByLabel('Variante et garantie').fill('16 Go / 512 Go / neuf / garantie 1 an');
  await page.getByLabel('Prix affiché').fill('1000.1234');
  await page.getByLabel('Base du prix').selectOption('TTC');
  await page.getByLabel('Livraison pour une unité').fill('0');
  await page.getByLabel('Disponibilité affichée').selectOption('IN_STOCK');
  const localDate = await page.evaluate(() => { const d=new Date(); return new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16); });
  await page.getByLabel('Date et heure du relevé').fill(localDate);
  await page.getByLabel('Conditions et justification').fill('Recette synthétique, correspondance vérifiée pour ce test');
  await page.getByRole('checkbox').check();
  await page.route('**/api/market/observations',async route => {await route.fetch();await route.abort('failed');});
  await page.getByRole('button',{name:'Enregistrer le relevé',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();
  await page.unroute('**/api/market/observations');
  await page.getByRole('button',{name:'Enregistrer le relevé',exact:true}).click();
  await page.getByRole('status').filter({hasText:'Relevé enregistré'}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/market/products/${item.id}`)).json()).items.length,1);
  await page.getByLabel('Enseigne',{exact:true}).selectOption('Mytek');
  await page.getByLabel('URL de la fiche produit').fill('https://mytek.tn/qa-pc.html');
  await page.getByLabel('Prix affiché').fill('1010.1234');
  await page.getByRole('button',{name:'Enregistrer le relevé',exact:true}).click();
  await page.getByText('Écart au minimum : +10,00 TND',{exact:true}).waitFor();
  for(const width of [1440,768,390]) {
    await page.setViewportSize({width,height:1000});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`Overflow ${width}`);
    await page.evaluate(() => window.scrollTo(0,0));
    await page.screenshot({path:path.join(evidence,`market-${width}.png`),fullPage:true});
  }
  await page.getByLabel('Référence fabricant').focus();await page.keyboard.press('Tab');
  assert.equal(await page.getByLabel('Variante et garantie').evaluate(el=>el===document.activeElement),true);
  await page.reload();await navigate('Veille concurrentielle');
  await page.getByLabel('Produit à surveiller').selectOption(String(item.id));
  await page.getByText('Écart au minimum : +10,00 TND',{exact:true}).waitFor();
  assert.deepEqual(await (await context.request.get(`${url}/api/products/${item.id}`)).json(),item);
  assert.deepEqual(errors,[]);
  console.log('OK: enregistrement, reprise réseau sans doublon, comparaison exacte, persistance, clavier, 3 largeurs, zéro pageerror, produit intact');
} finally { if(browser) await browser.close(); child.kill(); }
