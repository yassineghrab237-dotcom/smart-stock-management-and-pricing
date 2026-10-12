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
const qa = path.join(root, 'runtime', `crm-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8017';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8017'], {
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
  await navigate('Clients et fournisseurs');
  await page.getByRole('button',{name:'Nouveau contact'}).click();
  await page.getByLabel('Nom du contact').fill('Contact CRM recette');
  await page.getByLabel('Type de relation').selectOption('BOTH');
  await page.getByLabel('Entreprise',{exact:true}).fill('Entreprise QA');
  await page.getByLabel('E-mail du contact').fill('contact@example.test');
  await page.getByRole('button',{name:'Enregistrer la fiche'}).click();
  await page.getByRole('heading',{name:'Contact CRM recette',exact:true}).waitFor();
  await page.getByLabel('Note de suivi').fill('Demande de devis pour un ordinateur.');
  await page.getByRole('button',{name:'Ajouter la note'}).click();
  await page.getByRole('status').filter({hasText:'Note enregistrée'}).waitFor();
  await page.getByLabel('Action à prévoir').fill('Préparer devis QA');
  await page.getByLabel('Échéance',{exact:true}).fill('2026-11-01');
  await page.getByRole('button',{name:'Ajouter la tâche'}).click();
  await page.getByRole('button',{name:'Terminer',exact:true}).click();
  await page.getByRole('button',{name:'Rouvrir',exact:true}).waitFor();
  await page.getByRole('button',{name:'Modifier la fiche'}).click();
  await page.getByLabel('Préférence de contact commercial').selectOption('REFUSED');
  await page.getByLabel('Motif de modification').fill('Préférence confirmée');
  await page.getByRole('button',{name:'Enregistrer la fiche'}).click();
  await page.getByText('Ne pas contacter',{exact:true}).waitFor();
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`crm-${width}.png`),fullPage:true});}
  await page.reload();await page.getByRole('heading',{name:'Votre stock, en un regard'}).waitFor();await navigate('Clients et fournisseurs');
  await page.getByRole('button',{name:/Contact CRM recette/}).click();
  await page.getByText('Ne pas contacter',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Rouvrir',exact:true}).waitFor();
  const contacts=await (await context.request.get(`${url}/api/crm/contacts`)).json();assert.equal(contacts.items.length,1);
  assert.deepEqual(errors,[]);console.log('CRM OK: création, modification, note, tâche clôturée, persistance, 3 largeurs, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
