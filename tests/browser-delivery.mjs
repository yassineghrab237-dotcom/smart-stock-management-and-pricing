import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const qa = path.join(root, 'runtime', `delivery-qa-${Date.now()}`), evidence = path.join(root, 'docs/evidence');
await mkdir(qa, {recursive:true}); await mkdir(evidence, {recursive:true});
const url = 'http://127.0.0.1:8013';
const child = spawn(path.join(root,'.venv-local/Scripts/python.exe'), ['-m','uvicorn','services.api_gateway.app.main:app','--host','127.0.0.1','--port','8013'], {cwd:root,windowsHide:true,env:{...process.env,SMART_STOCK_DB:path.join(qa,'isolated.sqlite3'),SMART_STOCK_DEV:'0'}});
let log=''; child.stdout.on('data',d=>{log+=d;}); child.stderr.on('data',d=>{log+=d;});
let browser; const errors=[], checks=[];
try {
  for(let i=0;i<100;i++){if(child.exitCode!==null)throw new Error(log);try{if((await fetch(`${url}/api/health`)).ok)break;}catch{}if(i===99)throw new Error('Serveur indisponible');await new Promise(r=>setTimeout(r,100));}
  browser=await chromium.launch({headless:true}); const context=await browser.newContext({viewport:{width:1440,height:1000}}); const page=await context.newPage(); page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url); await page.getByLabel('Nom',{exact:true}).fill('QA Livraison'); await page.getByLabel('Adresse e-mail').fill('delivery@example.test'); await page.getByLabel('Mot de passe',{exact:true}).fill('DeliveryQa123!'); await page.getByRole('button',{name:'Créer mon espace'}).click();
  await page.getByRole('heading',{name:'Votre première action'}).waitFor();
  async function navigate(name){const open=page.getByRole('button',{name:'Ouvrir le menu'});if(await open.isVisible())await open.click();await page.getByRole('navigation').getByRole('button',{name,exact:true}).click();}
  await page.screenshot({path:path.join(evidence,'dashboard-start.png'),fullPage:true});
  for(const width of [1440,768,390]){await page.setViewportSize({width,height:1000});await navigate('Guide de démarrage');await page.getByRole('heading',{name:'Commencer en 5 minutes'}).waitFor();assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`guide-${width}.png`),fullPage:true});}
  checks.push('Accueil vide avec première action et guide réel 390/768/1440 sans overflow');
  const product=(await (await context.request.post(`${url}/api/products`,{data:{sku:'QA-DEMAND',name:'Produit recette · historique synthétique'}})).json());
  const monday=new Date();monday.setUTCHours(0,0,0,0);monday.setUTCDate(monday.getUTCDate()-((monday.getUTCDay()+6)%7));
  const rows=Array.from({length:24},(_,i)=>{const d=new Date(monday);d.setUTCDate(d.getUTCDate()-(24-i)*7);return `QA-W-${i},QA-DEMAND,${d.toISOString().slice(0,10)},${[20,50,80][i%3]},10`;});
  const body={kind:'sales',filename:'qa-synthetic.csv',csv_text:'reference,sku,sold_on,quantity,unit_price\n'+rows.join('\n')};
  const preview=(await (await context.request.post(`${url}/api/imports/preview`,{data:body})).json());assert(preview.valid);assert.equal((await context.request.post(`${url}/api/imports/commit`,{data:{...body,preview_token:preview.preview_token}})).status(),200);
  await navigate('Analyser les ventes');await page.getByRole('button',{name:'Lancer l’analyse',exact:true}).click();await page.getByText('Terminé',{exact:true}).waitFor({timeout:60000});
  const jobs=(await (await context.request.get(`${url}/api/analysis/jobs`)).json()).items;assert.equal(jobs[0].progress,100);assert.equal(jobs[0].result.products[0].status,'available');assert(jobs[0].result.products[0].model_mae<jobs[0].result.products[0].baseline_mae);
  assert.equal((await (await context.request.get(`${url}/api/products/${product.id}`)).json()).current_stock,0);
  for(const width of [390,768,1440]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`analysis-${width}.png`),fullPage:true});}
  checks.push('Import réel d’un historique explicitement QA/synthétique, calcul suivi jusqu’au résultat, contrôle temporel/baseline, aucune modification stock');
  await context.request.post(`${url}/api/products`,{data:{sku:'QA-NEW',name:'QA modification du corpus'}});await navigate('Guide de démarrage');await navigate('Analyser les ventes');await page.getByRole('alert').filter({hasText:'Ses résultats sont historiques'}).waitFor();assert.equal(await page.locator('.forecast-value').count(),0);
  checks.push('Analyse périmée signalée et estimation masquée après modification du corpus');
  await page.setViewportSize({width:1440,height:1000});await page.getByRole('button',{name:'Collaborateurs',exact:true}).click();
  await page.getByLabel('Nom',{exact:true}).fill('QA Collaborateur');await page.getByLabel('Adresse e-mail').fill('access@example.test');await page.getByLabel('Mot de passe initial').fill('Collaborateur123!');await page.getByRole('button',{name:'Créer le compte',exact:true}).click();
  const row=()=>page.locator('.user-row').filter({hasText:'access@example.test'});await row().getByText('Actif',{exact:true}).waitFor();
  await row().getByRole('button',{name:'Désactiver',exact:true}).click();const modal=page.getByRole('dialog');await modal.getByLabel('Motif du changement d’accès').fill('Fin de mission recette');await modal.getByRole('button',{name:'Confirmer le changement'}).click();await row().getByText('Désactivé',{exact:true}).waitFor();
  await row().getByRole('button',{name:'Réactiver',exact:true}).click();await modal.getByLabel('Motif du changement d’accès').fill('Retour recette');await modal.getByRole('button',{name:'Confirmer le changement'}).click();await row().getByText('Actif',{exact:true}).waitFor();
  await row().getByRole('button',{name:'Déconnecter partout',exact:true}).click();await modal.getByRole('button',{name:'Confirmer le changement'}).click();await modal.waitFor({state:'hidden'});
  for(const width of [1440,390]){await page.setViewportSize({width,height:1000});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(evidence,`accounts-${width}.png`),fullPage:true});}
  checks.push('Compte créé, désactivé et réactivé par confirmation, révocation des sessions, pages collaborateurs 390/1440 sans débordement');assert.deepEqual(errors,[]);
  await writeFile(path.join(evidence,'delivery-browser-results.json'),JSON.stringify({date:new Date().toISOString(),checks,jsErrors:errors,mode:'SQLite QA isolée, corpus synthétique identifié'},null,2));console.log(JSON.stringify({success:true,checks},null,2));
}finally{await browser?.close();child.kill();await writeFile(path.join(qa,'server.log'),log);}
