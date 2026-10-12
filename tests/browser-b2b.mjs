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
const qa = path.join(root, 'runtime', `b2b-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8023';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8023'], {
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
  const c=await (await context.request.post(`${url}/api/crm/contacts`,{data:{name:'Entreprise QA',kind:'CUSTOMER',idempotency_key:crypto.randomUUID()}})).json();
  const p=await (await context.request.post(`${url}/api/products`,{data:{name:'Portable entreprise',sku:'B2B-PC'}})).json();
  const q=await (await context.request.post(`${url}/api/commerce/documents`,{data:{kind:'QUOTE',reference:'DEVIS-B2B-QA',customer_id:c.id,lines:[{product_id:p.id,quantity:10,unit_price_ttc:'119',tax_rate:'19',unit_cost_ht:'60'}],idempotency_key:crypto.randomUUID()}})).json();
  await navigate('Clients et fournisseurs');await page.getByRole('button',{name:/Entreprise QA/}).click();await page.getByRole('button',{name:'Nouvelle opportunité'}).click();
  await page.getByLabel('Besoin commercial').fill('Équipement du bureau');await page.getByLabel('Montant potentiel TND TTC').fill('1190');await page.getByLabel('Date de décision visée').fill('2026-12-01');await page.getByLabel('Étape commerciale').selectOption('PROPOSAL');await page.getByLabel('Devis lié au client').selectOption(String(q.id));await page.getByLabel('Motif ou résultat commercial').fill('Proposition de recette');
  await page.getByRole('button',{name:'Enregistrer l’opportunité'}).click();await page.getByRole('heading',{name:'Équipement du bureau'}).waitFor();
  await page.getByRole('button',{name:'Modifier l’opportunité'}).click();await page.getByLabel('Étape commerciale').selectOption('WON');await page.getByLabel('Motif ou résultat commercial').fill('Accord de principe');await page.getByRole('button',{name:'Enregistrer l’opportunité'}).click();await page.getByText('Gagnée',{exact:true}).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/insights/sales`)).json()).sales_count,0);
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await page.evaluate(()=>window.scrollTo(0,0));assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`b2b-${width}.png`),fullPage:true});}
  await navigate('Ventes et devis');await page.getByRole('button',{name:/DEVIS-B2B-QA/}).click();await page.getByRole('button',{name:'Imprimer le document'}).waitFor();
  await page.setViewportSize({width:900,height:1200});await page.emulateMedia({media:'print'});await page.screenshot({path:path.join(evidence,'quote-print.png'),fullPage:true});await page.pdf({path:path.join(evidence,'quote-print.pdf'),format:'A4',preferCSSPageSize:true});
  assert.equal(await page.locator('.document-print').isVisible(),true);assert.equal(await page.locator('#root').isVisible(),false);
  const print=await page.locator('.document-print').innerText();assert(print.includes('1 190,00'));assert(!print.includes('60,00'));assert(!print.includes('400,00'));
  await page.emulateMedia({media:'screen'});await navigate('Tableau de bord');assert.equal(await page.locator('.document-print').count(),0);
  assert.deepEqual(errors,[]);console.log('B2B OK : opportunité liée au devis, gain sans vente fictive, trois largeurs, document imprimable sans coût ni contribution, zéro erreur JS');
}finally{if(browser)await browser.close();child.kill();}
