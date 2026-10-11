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
const qa = path.join(root, 'runtime', `design-qa-${Date.now()}`);
await mkdir(qa, { recursive: true });
await mkdir(path.join(root, 'docs/evidence'), { recursive: true });
const backend = spawn(path.join(root, '.venv-local/Scripts/python.exe'), ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', '8000'], {
  cwd: root, windowsHide: true, env: { ...process.env, SMART_STOCK_DB: path.join(qa, 'isolated.sqlite3'), SMART_STOCK_DEV: '1' },
});
const vite = spawn(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '5281'], { cwd: path.join(root, 'frontend'), windowsHide: true });
let log = '';
for (const child of [backend, vite]) {
  child.stdout.on('data', (data) => { log += data; });
  child.stderr.on('data', (data) => { log += data; });
}
let browser;
try {
  for (let i = 0; i < 100; i++) {
    if (backend.exitCode !== null || vite.exitCode !== null) throw new Error(`Port occupé ou lancement refusé: ${log}`);
    try { if ((await fetch('http://127.0.0.1:5281/api/health')).ok) break; } catch { /* readiness */ }
    if (i === 99) throw new Error(`Serveurs indisponibles: ${log}`);
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  const password = `Design9!${randomBytes(16).toString('hex')}`;
  await page.goto('http://127.0.0.1:5281/design');
  await page.getByLabel('Nom', { exact: true }).fill('Recette design');
  await page.getByLabel('Adresse e-mail', { exact: true }).fill('design@example.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Créer mon espace' }).click();
  // Navigation explicite également si l'authentification revient au dashboard.
  const design = page.getByRole('button', { name: 'Design system', exact: true });
  await design.click();
  await page.getByRole('heading', { name: 'Design system', exact: true }).waitFor();
  const built = await context.newPage();
  built.on('pageerror', (error) => errors.push(error.message));
  await built.goto('http://127.0.0.1:8000');
  await built.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor();
  assert.equal(await built.getByRole('button', { name: 'Design system', exact: true }).count(), 0);
  await built.close();
  await page.getByRole('button', { name: 'Afficher une notification' }).click();
  await page.getByRole('status').filter({ hasText: 'Exemple de notification' }).waitFor();
  await page.getByRole('button', { name: 'Afficher le chargement' }).click();
  await page.getByRole('status').filter({ hasText: 'Chargement des données' }).waitFor();
  await page.getByRole('button', { name: 'Masquer le chargement' }).click();
  const trigger = page.getByRole('button', { name: 'Ouvrir le dialogue' });
  await trigger.click();
  await page.getByRole('dialog').waitFor();
  await page.getByLabel('Saisie de démonstration', { exact: true }).fill('Recette de composant');
  await page.keyboard.press('Escape');
  await page.getByRole('dialog').waitFor({ state: 'hidden' });
  assert.equal(await trigger.evaluate((el) => el === document.activeElement), true);
  await page.screenshot({ path: path.join(root, 'docs/evidence/design-1440.png'), fullPage: true });
  await page.getByRole('button', { name: 'Collaborateurs', exact: true }).click();
  await page.getByLabel('Nom', { exact: true }).fill('Lecteur recette');
  await page.getByLabel('Adresse e-mail', { exact: true }).fill('design-reader@example.test');
  await page.getByLabel('Mot de passe initial', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Créer le compte', exact: true }).click();
  await page.getByRole('status').filter({ hasText: 'Collaborateur créé.' }).waitFor();
  await page.getByRole('button', { name: 'Se déconnecter' }).click();
  await page.getByRole('heading', { name: 'Bienvenue' }).waitFor();
  await page.getByLabel('Adresse e-mail', { exact: true }).fill('design-reader@example.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Se connecter', exact: true }).click();
  await page.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor();
  await page.getByRole('navigation').getByRole('button', { name: 'Produits et stock', exact: true }).click();
  await page.getByRole('heading', { name: 'Votre catalogue commence ici' }).waitFor();
  assert.equal(await page.getByRole('button', { name: 'Ajouter un produit' }).count(), 0);
  assert.equal((await context.request.post('http://127.0.0.1:5281/api/products', { data: { name: 'Interdit', sku: 'NO' } })).status(), 403);
  await page.screenshot({ path: path.join(root, 'docs/evidence/viewer-1440.png'), fullPage: true });
  assert.deepEqual(errors, []);
  const result = { success: true, checks: ['Vite proxy CSRF same-origin', 'Frontend compilé vérifié à127.0.0.1:8000, menu design absent', 'Design : notification, chargement, dialogue partagé, Escape et focus', 'Création collaborateur depuis UI', 'Connexion VIEWER après ADMIN sans écran vide', 'Actions masquées et refus serveur403 VIEWER'], jsErrors: errors };
  await writeFile(path.join(root, 'docs/evidence/design-results.json'), JSON.stringify(result, null, 2));
  console.log(JSON.stringify(result, null, 2));
} finally {
  await browser?.close();
  backend.kill();
  vite.kill();
  await writeFile(path.join(qa, 'server.log'), log);
}
