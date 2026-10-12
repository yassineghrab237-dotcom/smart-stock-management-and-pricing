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
const qa = path.join(root, 'runtime', `actions-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8029';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8029'], {
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
  const c=await (await context.request.post(`${url}/api/crm/contacts`,{data:{name:'Client QA',idempotency_key:crypto.randomUUID()}})).json();
  await context.request.post(`${url}/api/crm/contacts/${c.id}/tasks`,{data:{title:'Relance devis QA',due_on:'2020-01-01',idempotency_key:crypto.randomUUID()}});
  await navigate('Alertes');await page.getByText('Mettre à jour le suivi',{exact:true}).click();await page.getByLabel('État du suivi').selectOption('IN_PROGRESS');await page.getByLabel('Motif de prise en charge').fill('Relance préparée en recette');
  await page.route('**/api/actions/decisions',async route=>{await route.fetch();await route.abort('failed');});await page.getByRole('button',{name:'Enregistrer le suivi'}).click();await page.getByRole('alert').filter({hasText:'Connexion impossible'}).waitFor();await page.unroute('**/api/actions/decisions');await page.getByRole('button',{name:'Enregistrer le suivi'}).click();await page.getByText('Dernière décision : Relance préparée en recette',{exact:true}).waitFor();
  const a=await(await context.request.get(`${url}/api/actions`)).json();assert.equal(a.events.length,1);assert.equal(a.items[0].status,'IN_PROGRESS');
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.evaluate(()=>window.scrollTo(0,0));await page.screenshot({path:path.join(evidence,`actions-${width}.png`),fullPage:true});}
  await page.getByRole('button',{name:'Ouvrir le module concerné'}).click();await page.getByRole('heading',{name:'Clients et fournisseurs',exact:true}).waitFor();assert.deepEqual(errors,[]);console.log('OK: échéance, prise en charge, réponse perdue sans doublon, navigation, 3 largeurs et zéro pageerror');
}finally{if(browser)await browser.close();child.kill();}
