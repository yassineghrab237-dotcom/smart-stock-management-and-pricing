from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app

@pytest.fixture
def client(tmp_path):
 with TestClient(create_app(tmp_path/'commerce.sqlite3')) as c:
  c.post('/api/auth/setup',json=dict(name='QA',email='qa@example.test',password='LocalTest321!'))
  for i in range(2):
   p=c.post('/api/products',json=dict(name=f'Produit {i}',sku=f'SKU-{i}')).json()
   c.post('/api/movements',json=dict(product_id=p['id'],quantity=10,type='IN',reason='Stock recette',expected_version=1,idempotency_key=str(uuid4())))
  yield c

def create(c,kind='SALE',**changes):
 body=dict(reference=str(uuid4()),kind=kind,lines=[dict(product_id=1,quantity=2,unit_price_ttc='119',unit_cost_ht='60',tax_rate='19')],idempotency_key=str(uuid4()))
 body.update(changes);r=c.post('/api/commerce/documents',json=body);assert r.status_code==201,r.text;return r.json()

def confirm(c,d,**changes):
 body=dict(expected_version=d['version'],product_versions={'1':2,'2':2},idempotency_key=str(uuid4()))
 body.update(changes);return c.post(f"/api/commerce/documents/{d['id']}/confirm",json=body)

def test_sale_totals_stock_and_retry(client):
 d=create(client);assert d['totals']==dict(total_ttc='238.0000',total_ht='200.0000',tax='38.0000',contribution_ht='80.0000')
 assert client.get('/api/products/1').json()['current_stock']==10
 key=str(uuid4());r=confirm(client,d,idempotency_key=key);assert r.status_code==200,r.text
 assert confirm(client,d,idempotency_key=key).json()==r.json()
 assert client.get('/api/products/1').json()['current_stock']==8
 assert confirm(client,d).status_code==409

def test_atomic_insufficient_second_line(client):
 d=create(client,lines=[dict(product_id=1,quantity=2,unit_price_ttc='119',tax_rate='19'),dict(product_id=2,quantity=11,unit_price_ttc='100',tax_rate='0')])
 assert confirm(client,d).status_code==409
 assert client.get('/api/products/1').json()['current_stock']==10
 assert client.get('/api/commerce/documents/1').json()['status']=='DRAFT'
 assert d['totals']['contribution_ht'] is None

def test_quote_conversion(client):
 d=create(client,'QUOTE');assert confirm(client,d).status_code==422
 r=confirm(client,d,sale_reference='SALE-QA');assert r.status_code==200,r.text
 assert r.json()['source_quote_id']==d['id'] and r.json()['kind']=='SALE'
 assert client.get('/api/commerce/documents/1').json()['status']=='CONVERTED'
 assert len(client.get('/api/commerce/documents').json()['items'])==2
 assert confirm(client,d,sale_reference='SALE-OTHER').status_code==409

def test_returns_damage_and_idempotence(client):
 d=create(client);sale=confirm(client,d).json();line=sale['lines'][0]
 b=dict(quantity=1,restock=False,reason='Produit endommagé',expected_product_version=3,idempotency_key=str(uuid4()))
 r=client.post(f"/api/commerce/lines/{line['id']}/returns",json=b);assert r.status_code==201,r.text
 assert client.post(f"/api/commerce/lines/{line['id']}/returns",json=b).json()==r.json()
 assert r.json()['lines'][0]['net']['contribution_ht']=='-20.0000'
 assert client.get('/api/products/1').json()['current_stock']==8
 b.update(restock=True,idempotency_key=str(uuid4()))
 r=client.post(f"/api/commerce/lines/{line['id']}/returns",json=b);assert r.status_code==201,r.text
 assert r.json()['net_total_ttc']=='0.0000'
 assert r.json()['lines'][0]['net']['contribution_ht']=='-60.0000'
 assert client.get('/api/products/1').json()['current_stock']==9
 b.update(expected_product_version=4,idempotency_key=str(uuid4()))
 assert client.post(f"/api/commerce/lines/{line['id']}/returns",json=b).status_code==409

def test_cancel_and_version(client):
 d=create(client);assert confirm(client,d,product_versions={'1':1}).status_code==409
 b=dict(expected_version=1,reason='Erreur de saisie',idempotency_key=str(uuid4()))
 assert client.post('/api/commerce/documents/1/cancel',json=b).status_code==200
 assert confirm(client,d).status_code==409
 assert client.get('/api/products/1').json()['current_stock']==10

def test_duplicate_reference_and_invalid_money(client):
 create(client,reference='UNIQUE')
 b=dict(reference='UNIQUE',kind='SALE',lines=[dict(product_id=1,quantity=1,unit_price_ttc='0',tax_rate='0')],idempotency_key=str(uuid4()))
 assert client.post('/api/commerce/documents',json=b).status_code==409
 b['reference']='SECOND';b['lines'][0]['discount_ttc']='1'
 assert client.post('/api/commerce/documents',json=b).status_code==422
 b['lines'][0]['discount_ttc']='0';b['lines'][0]['tax_rate']='101'
 assert client.post('/api/commerce/documents',json=b).status_code==422
