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
const qa = path.join(root, 'runtime', `import-qa-${Date.now()}`);
const evidence = path.join(root, 'docs', 'evidence');
await mkdir(qa, { recursive: true });
await mkdir(evidence, { recursive: true });
const url = 'http://127.0.0.1:8011';
const child = spawn(path.join(root, '.venv-local', 'Scripts', 'python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8011'], {
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
  await navigate('Imports CSV');
  await upload('sku,name\nQA-CSV-A,Produit CSV A\nQA-CSV-A,Produit doublon');
  await page.getByText('Import bloqué', { exact: true }).waitFor();
  assert(await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).isDisabled());
  assert.equal((await (await context.request.get(`${url}/api/products`)).json()).items.length, 0);
  checks.push('Doublon dans le fichier : aperçu bloqué et aucune écriture');
  await upload('sku,name,current_price,threshold_min\nQA-CSV-A,Produit CSV A,12.3456,2');
  await page.getByText('Toutes les lignes sont valides').waitFor();
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow ${width}`);
    await page.screenshot({ path: path.join(evidence, `imports-${width}.png`), fullPage: true });
  }
  await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).click();
  const dialog = page.getByRole('dialog');
  await dialog.waitFor(); await page.keyboard.press('Escape'); await dialog.waitFor({ state: 'hidden' });
  assert.equal(await page.evaluate(() => document.activeElement?.textContent), 'Vérifier et confirmer l’import');
  await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).click();
  await dialog.getByRole('button', { name: 'Confirmer l’enregistrement' }).click();
  await page.getByRole('status').filter({ hasText: '1 ligne(s) importée(s)' }).waitFor();
  const product = (await (await context.request.get(`${url}/api/products`)).json()).items[0];
  assert.equal(product.current_stock, 0); assert.equal(product.current_price, '12.3456');
  checks.push('Catalogue enregistré ; quatre décimales ; stock zéro ; mobile/tablette/desktop sans overflow ; Escape restaure le focus');
  await page.getByRole('button', { name: 'Historique des ventes', exact: true }).click();
  await upload('reference,sku,sold_on,quantity,unit_price\nSALE-CSV-1,QA-CSV-A,2025-01-02,3,9.8765');
  await page.getByText('Toutes les lignes sont valides').waitFor();
  assert.equal((await (await context.request.get(`${url}/api/imports/sales`)).json()).items.length, 0);
  await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).click();
  await dialog.getByRole('button', { name: 'Confirmer l’enregistrement' }).click();
  await page.getByRole('status').filter({ hasText: 'Le stock actuel est conservé' }).waitFor();
  assert.deepEqual((await (await context.request.get(`${url}/api/products/${product.id}`)).json()), product);
  assert.equal((await (await context.request.get(`${url}/api/movements`)).json()).items.length, 0);
  checks.push('Vente persistée sans mouvement ni changement du prix/stock actuel');
  await upload('reference,sku,sold_on,quantity,unit_price\nSALE-CSV-2,QA-CSV-A,2025-01-03,1,9.8765');
  await page.getByText('Toutes les lignes sont valides').waitFor();
  await page.route('**/api/imports/commit', async route => { await route.fetch(); await route.abort('failed'); });
  await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).click();
  await dialog.getByRole('button', { name: 'Confirmer l’enregistrement' }).click();
  await page.getByRole('alert').filter({ hasText: 'En cas de réponse perdue' }).waitFor();
  await page.unroute('**/api/imports/commit');
  await page.getByRole('button', { name: 'Vérifier et confirmer l’import' }).click();
  await dialog.getByRole('button', { name: 'Confirmer l’enregistrement' }).click();
  await page.getByRole('status').filter({ hasText: 'Ce fichier avait déjà été enregistré' }).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/imports/sales`)).json()).items.length, 2);
  checks.push('Réponse perdue après commit : reprise sans doublon');
  await page.reload(); await page.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor(); await navigate('Imports CSV');
  await page.getByText('SALE-CSV-2 · Produit CSV A').waitFor();
  await context.request.post(`${url}/api/auth/users`, { data: { name: 'QA Lecteur Import', email: 'viewer-import@example.test', password, role: 'VIEWER' } });
  await context.request.post(`${url}/api/auth/logout`);
  await context.request.post(`${url}/api/auth/login`, { data: { email: 'viewer-import@example.test', password } });
  await page.reload(); await page.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor(); await navigate('Imports CSV');
  await page.getByText('SALE-CSV-2 · Produit CSV A').waitFor();
  assert.equal(await page.getByLabel('Fichier CSV').count(), 0);
  assert.equal((await context.request.post(`${url}/api/imports/preview`, { data: { kind: 'catalogue', csv_text: 'sku,name\nX,X' } })).status(), 403);
  checks.push('Rechargement persistant ; VIEWER consulte les ventes et ne peut pas importer');
  assert.deepEqual(errors, []);
  await writeFile(path.join(evidence, 'imports-results.json'), JSON.stringify({ date: new Date().toISOString(), checks, jsErrors: errors, mode: 'SQLite QA isolée, aucun déploiement' }, null, 2));
  console.log(JSON.stringify({ success: true, checks }, null, 2));
} finally { await browser?.close(); child.kill(); await writeFile(path.join(qa, 'server.log'), logs); }
