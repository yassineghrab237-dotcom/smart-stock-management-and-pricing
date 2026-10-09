// Recette d'intégration réelle : nouveau serveur, base dédiée, aucun mock métier.
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { randomBytes, randomUUID } from 'node:crypto';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const evidence = path.join(root, 'docs', 'evidence');
const qa = path.join(root, 'runtime', `browser-qa-${Date.now()}`);
await mkdir(evidence, { recursive: true });
await mkdir(qa, { recursive: true });
const port = Number(process.env.QA_PORT || 8010);
const url = `http://127.0.0.1:${port}`;
const python = process.env.QA_PYTHON || path.join(root, '.venv-local', 'Scripts', 'python.exe');
const child = spawn(python, ['-m', 'uvicorn', 'services.api_gateway.app.main:app', '--host', '127.0.0.1', '--port', String(port)], {
  cwd: root, windowsHide: true,
  env: { ...process.env, SMART_STOCK_DB: path.join(qa, 'isolated.sqlite3'), SMART_STOCK_DEV: '0' },
});
let serverLog = '';
child.stdout.on('data', (data) => { serverLog += data; });
child.stderr.on('data', (data) => { serverLog += data; });
const failures = [];
const checks = [];
let browser;
try {
  for (let i = 0; i < 100; i++) {
    if (child.exitCode !== null) throw new Error(`Serveur arrêté : ${serverLog}`);
    try { if ((await fetch(`${url}/api/health`)).ok) break; } catch { /* readiness */ }
    if (i === 99) throw new Error('Serveur non disponible');
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.on('pageerror', (error) => failures.push(error.message));
  const password = `Recette9!${randomBytes(16).toString('hex')}`;
  await page.goto(url);
  await page.getByRole('heading', { name: 'Créer le premier administrateur' }).waitFor();
  await page.getByLabel('Nom', { exact: true }).fill('Gestionnaire recette');
  await page.getByLabel('Adresse e-mail').fill('qa-admin@example.test');
  await page.getByLabel('Mot de passe', { exact: true }).fill(password);
  await page.getByRole('button', { name: 'Créer mon espace' }).click();
  await page.getByRole('heading', { name: 'Votre stock, en un regard' }).waitFor();
  checks.push('Premier administrateur créé depuis le frontend');
  async function navigate(name) {
    const open = page.getByRole('button', { name: 'Ouvrir le menu' });
    if (await open.isVisible()) await open.click();
    await page.getByRole('navigation', { name: 'Navigation principale' }).getByRole('button', { name, exact: true }).click();
  }
  await navigate('Produits et stock');
  await page.getByRole('heading', { name: 'Votre catalogue commence ici' }).waitFor();
  await page.getByRole('button', { name: 'Ajouter un produit' }).first().click();
  const dialog = page.getByRole('dialog');
  await dialog.getByLabel('Nom du produit').fill('Produit Recette · câble USB');
  await dialog.getByLabel('Référence / SKU').fill('RECETTE-USB-001');
  await dialog.getByLabel('Catégorie (facultatif)').fill('Accessoires');
  await dialog.getByLabel('Unité (facultatif)').fill('pièces');
  await dialog.getByLabel('Seuil minimum').fill('5');
  await dialog.getByLabel('Seuil maximum (facultatif)').fill('110');
  await dialog.getByLabel('Prix actuel (facultatif)').fill('12.34');
  await dialog.getByLabel('Prix minimum (facultatif)').fill('8');
  await dialog.getByRole('button', { name: 'Créer le produit' }).click();
  await dialog.waitFor({ state: 'hidden' });
  await page.reload();
  await navigate('Produits et stock');
  const search = page.getByRole('textbox', { name: 'Rechercher par nom, référence ou catégorie' });
  await search.fill('RECETTE-USB');
  await page.getByLabel('État du stock').selectOption('low');
  await page.getByRole('button', { name: 'Produit Recette · câble USB', exact: true }).click();
  await page.getByRole('heading', { name: 'Produit Recette · câble USB' }).waitFor();
  checks.push('Produit persistant après rechargement, recherche SKU et filtre stock');
  async function operation(kind, quantity, reason) {
    await page.getByRole('button', { name: 'Enregistrer un mouvement', exact: true }).click();
    await dialog.getByRole('button', { name: kind, exact: true }).click();
    await dialog.getByLabel(kind === 'Ajustement' ? 'Stock cible après ajustement' : 'Quantité', { exact: true }).fill(String(quantity));
    await dialog.getByLabel('Motif de l’opération').fill(reason);
    await dialog.getByRole('button', { name: 'Vérifier le mouvement' }).click();
    await dialog.getByRole('button', { name: 'Confirmer le mouvement' }).click();
    await dialog.waitFor({ state: 'hidden' });
    await page.getByRole('status').filter({ hasText: 'Mouvement enregistré.' }).waitFor();
    await page.getByRole('button', { name: 'Enregistrer un mouvement', exact: true }).waitFor();
  }
  await operation('Entrée', 100, 'Réception recette initiale');
  await operation('Sortie', 15, 'Livraison recette');
  await operation('Entrée', 20, 'Réception recette complémentaire');
  const stored = await (await context.request.get(`${url}/api/products`)).json();
  const item = stored.items[0];
  assert.equal(item.current_stock, 105);
  const movements = await (await context.request.get(`${url}/api/movements`)).json();
  assert.equal(movements.items.length, 3);
  assert.equal(await page.locator('.history-item').count(), 3);
  checks.push('Entrée100, sortie15, entrée20 : stock105 et 3 mouvements serveur/UI');
  await page.getByRole('button', { name: 'Retour aux produits' }).click();
  assert.equal(await search.inputValue(), 'RECETTE-USB');
  assert.equal(await page.getByLabel('État du stock').inputValue(), 'low');
  await page.getByRole('heading', { name: 'Aucun produit correspondant' }).waitFor();
  await page.getByLabel('État du stock').selectOption('all');
  checks.push('Retour à la liste conserve le contexte, alerte résolue');
  for (const width of [1440, 768, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.screenshot({ path: path.join(evidence, `products-${width}.png`), fullPage: true });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Débordement ${width}px`);
    await page.getByRole('button', { name: /Produit Recette · câble USB/ }).filter({ visible: true }).first().click();
    await page.getByRole('button', { name: 'Enregistrer un mouvement', exact: true }).click();
    await dialog.getByLabel('Quantité', { exact: true }).fill('200');
    await dialog.getByRole('button', { name: 'Sortie', exact: true }).click();
    await dialog.getByLabel('Motif de l’opération').fill('Refus recette');
    await dialog.getByRole('alert').filter({ hasText: 'dépasse le stock disponible' }).waitFor();
    assert.equal(await dialog.getByRole('button', { name: 'Vérifier le mouvement' }).isDisabled(), true);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `Dialogue déborde ${width}`);
    await page.screenshot({ path: path.join(evidence, `movement-${width}.png`), fullPage: true });
    await page.keyboard.press('Tab');
    assert.equal(await dialog.evaluate((el) => el.contains(document.activeElement)), true);
    await page.keyboard.press('Escape');
    await dialog.waitFor({ state: 'hidden' });
    await operation('Sortie', 1, `Sortie responsive ${width}px`);
    await operation('Entrée', 1, `Retour responsive ${width}px`);
    if (width < 900) {
      const trigger = page.getByRole('button', { name: 'Ouvrir le menu' });
      await trigger.click();
      await page.keyboard.press('Tab');
      assert.equal(await page.locator('.sidebar').evaluate((el) => el.contains(document.activeElement)), true);
      await page.keyboard.press('Escape');
      await page.waitForFunction(() => document.activeElement?.getAttribute('aria-label') === 'Ouvrir le menu');
    }
    await page.getByRole('button', { name: 'Retour aux produits' }).click();
    checks.push(`Produits/dialogue ${width}px sans débordement, opérations réelles, sortie excessive refusée, Tab/Escape`);
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.getByRole('button', { name: 'Produit Recette · câble USB', exact: true }).click();
  await page.locator('#main .tabs').getByRole('button', { name: 'Prix et recommandations', exact: true }).click();
  await page.getByRole('textbox', { name: 'Motif du changement' }).fill('Révision de prix recette');
  await page.getByLabel('Nouveau prix', { exact: true }).fill('12.3456');
  await page.getByRole('button', { name: 'Appliquer ce prix' }).click();
  await page.getByRole('status').filter({ hasText: 'Nouveau prix enregistré.' }).waitFor();
  await page.getByText('Révision de prix recette', { exact: true }).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${item.id}`)).json()).current_price, '12.3456');
  await page.getByText(/Aucun historique réel explicitement lié/).waitFor();
  checks.push('Prix4 décimales persistant, historique, recommandation ML indisponible explicite');
  await page.getByLabel('Nouveau prix', { exact: true }).fill('13.0001');
  await page.getByRole('textbox', { name: 'Motif du changement' }).fill('Conflit prix recette');
  const beforeConcurrent = await (await context.request.get(`${url}/api/products/${item.id}`)).json();
  const concurrentPrice = await context.request.patch(`${url}/api/products/${item.id}/price`, { data: {
    price: '14.0000', reason: 'Modification concurrente recette', expected_version: beforeConcurrent.version, idempotency_key: randomUUID(),
  }});
  assert.equal(concurrentPrice.status(), 200);
  await page.getByRole('button', { name: 'Appliquer ce prix' }).click();
  await page.getByRole('alert').filter({ hasText: 'Le produit a changé.' }).waitFor();
  assert.equal(await page.getByLabel('Nouveau prix', { exact: true }).inputValue(), '13.0001');
  assert.equal(await page.getByRole('textbox', { name: 'Motif du changement' }).inputValue(), 'Conflit prix recette');
  await page.waitForFunction(() => Array.from(document.querySelectorAll('button')).some((b) => b.textContent === 'Appliquer ce prix' && !b.disabled));
  await page.getByRole('button', { name: 'Appliquer ce prix' }).click();
  await page.getByRole('status').filter({ hasText: 'Nouveau prix enregistré.' }).waitFor();
  assert.equal((await (await context.request.get(`${url}/api/products/${item.id}`)).json()).current_price, '13.0001');
  checks.push('Conflit de prix409 conserve saisie/motif puis reconfirmation explicite');
  await navigate('Alertes');
  await page.getByRole('heading', { name: 'Aucune alerte dans cette vue' }).waitFor();
  await navigate('Produits et stock');
  // Réponse réseau perdue APRES commit : le retry garde la même clé.
  await page.getByRole('button', { name: 'Produit Recette · câble USB', exact: true }).click();
  await page.getByRole('button', { name: 'Enregistrer un mouvement', exact: true }).click();
  await dialog.getByLabel('Quantité', { exact: true }).fill('1');
  await dialog.getByLabel('Motif de l’opération').fill('Réponse perdue recette');
  await dialog.getByRole('button', { name: 'Vérifier le mouvement' }).click();
  await page.route('**/api/movements', async (route) => {
    if (route.request().method() === 'POST') { await route.fetch(); await route.abort('failed'); }
    else await route.continue();
  });
  await dialog.getByRole('button', { name: 'Confirmer le mouvement' }).click();
  await dialog.getByRole('alert').filter({ hasText: 'Connexion impossible' }).waitFor();
  assert.equal(await dialog.getByLabel('Motif de l’opération').inputValue(), 'Réponse perdue recette');
  await page.unroute('**/api/movements');
  await dialog.getByRole('button', { name: 'Confirmer le mouvement' }).click();
  await dialog.waitFor({ state: 'hidden' });
  assert.equal((await (await context.request.get(`${url}/api/products/${item.id}`)).json()).current_stock, 106);
  assert.equal((await (await context.request.get(`${url}/api/movements`)).json()).items.length, 10);
  checks.push('Réponse perdue après commit : saisie conservée et retry sans doublon');
  await operation('Ajustement', 2, 'Inventaire recette bas');
  await navigate('Alertes');
  await page.locator('.alert-card').filter({ hasText: 'Produit Recette · câble USB' }).waitFor();
  await navigate('Produits et stock');
  await page.getByRole('button', { name: 'Produit Recette · câble USB', exact: true }).click();
  await operation('Ajustement', 105, 'Inventaire recette résolu');
  await navigate('Alertes');
  await page.getByRole('heading', { name: 'Aucune alerte dans cette vue' }).waitFor();
  checks.push('Ajustements tracés, alerte déclenchée à2 puis résolue à105');
  await page.route('**/api/products', (route) => route.abort('failed'));
  await navigate('Produits et stock');
  await page.getByRole('alert').filter({ hasText: 'Connexion impossible' }).waitFor();
  await page.unroute('**/api/products');
  await page.getByRole('button', { name: 'Réessayer', exact: true }).click();
  await page.getByRole('button', { name: 'Produit Recette · câble USB', exact: true }).waitFor();
  checks.push('Erreur réseau catalogue et reprise par Réessayer');
  assert.equal((await context.request.get(`${url}/design`)).status(), 404);
  await context.request.post(`${url}/api/auth/logout`);
  await navigate('Tableau de bord');
  await page.getByRole('heading', { name: 'Bienvenue' }).waitFor();
  await page.getByText(/Votre session a expiré/).waitFor();
  checks.push('Session invalidée serveur : retour connexion ; /design production404');
  assert.deepEqual(failures, [], 'Erreurs JavaScript navigateur');
  await writeFile(path.join(evidence, 'browser-results.json'), JSON.stringify({ date: new Date().toISOString(), checks, jsErrors: failures, mode: 'Base SQLite QA isolée, aucun déploiement', database: path.relative(root, qa) }, null, 2));
  console.log(JSON.stringify({ success: true, checks }, null, 2));
} catch (error) {
  await writeFile(path.join(qa, 'failure.txt'), String(error.stack || error));
  throw error;
} finally {
  await browser?.close();
  child.kill();
  await writeFile(path.join(qa, 'server.log'), serverLog);
}
