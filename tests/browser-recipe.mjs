import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH||'playwright');
const meta=JSON.parse((await readFile('runtime/latest-recipe.json','utf8')).replace(/^\uFEFF/,''));
const access=await readFile(meta.access_file,'utf8');const password=access.match(/^Mot de passe : (.+)$/m)[1];
const browser=await chromium.launch({headless:true});const context=await browser.newContext({viewport:{width:1440,height:1000}});const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
try{
 assert.equal((await(await fetch('http://127.0.0.1:8000/api/health')).json()).demo,true);
 await page.goto('http://127.0.0.1:8000');await page.getByLabel('Adresse e-mail').fill('demo@precios.test');await page.getByLabel('Mot de passe',{exact:true}).fill(password);await page.getByRole('button',{name:'Se connecter',exact:true}).click();await page.getByText('Environnement de recette · données fictives.',{exact:false}).waitFor();
 async function nav(name){if(await page.getByRole('button',{name:'Ouvrir le menu'}).isVisible())await page.getByRole('button',{name:'Ouvrir le menu'}).click();await page.getByRole('navigation').getByRole('button',{name,exact:true}).click();}
 const r=await(await context.request.get('http://127.0.0.1:8000/api/insights/sales')).json();assert.equal(r.sales_count,2);assert.equal(r.totals.net_ttc,'2451.4000');assert.equal(r.totals.contribution_ht,'464.0000');
 for(const width of [1440,390]){await page.setViewportSize({width,height:1000});for(const name of ['Tableau de bord','Ventes et devis','Clients et fournisseurs','Achats fournisseurs','Réapprovisionnement','Inventaires physiques','Alertes','Rentabilité et paniers','Veille concurrentielle','Guide de démarrage']){await nav(name);await page.waitForTimeout(250);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} ${width}`);if(name==='Tableau de bord'||name==='Rentabilité et paniers'){await page.screenshot({path:`docs/evidence/recipe-${name==='Tableau de bord'?'home':'insights'}-${width}.png`,fullPage:true});}}}
 assert.deepEqual(errors,[]);console.log('OK: recette isolée, bandeau, connexion, chiffres du guide, 10 écrans 1440/390, zéro erreur JS, aucune mutation métier');
}finally{await browser.close();}
