from uuid import uuid4
from tests.test_commerce import client

def create(c):
 r=c.post('/api/inventories',json=dict(title='Inventaire QA',product_ids=[1,2],idempotency_key=str(uuid4())));assert r.status_code==201,r.text;return r.json()
def count(c,campaign,line,quantity,**extra):
 b=dict(quantity=quantity,expected_version=line['version'],expected_product_version=line['current_product_version'],reason='Comptage physique',idempotency_key=str(uuid4()));b.update(extra)
 return c.post(f"/api/inventories/{campaign['id']}/lines/{line['id']}/count",json=b)
def apply(c,campaign,**extra):
 b=dict(expected_version=campaign['version'],reason='Écarts vérifiés',idempotency_key=str(uuid4()));b.update(extra)
 return c.post(f"/api/inventories/{campaign['id']}/apply",json=b)

def test_count_apply_and_retry(client):
 d=create(client);assert apply(client,d).status_code==422
 for line in d['lines']:
  r=count(client,d,line,8);assert r.status_code==200,r.text;d=r.json()
 assert client.get('/api/products/1').json()['current_stock']==10
 key=str(uuid4());r=apply(client,d,idempotency_key=key);assert r.status_code==200,r.text
 assert apply(client,d,idempotency_key=key).json()==r.json()
 assert client.get('/api/products/1').json()['current_stock']==8
 assert client.get('/api/products/2').json()['current_stock']==8
 assert count(client,r.json(),r.json()['lines'][0],6).status_code==409
 movements=client.get('/api/movements').json()['items'];assert len([m for m in movements if m['type']=='ADJUSTMENT'])==2

def test_concurrent_movement_atomic_and_recount(client):
 d=create(client)
 for line in d['lines']:d=count(client,d,line,7).json()
 client.post('/api/movements',json=dict(product_id=2,type='OUT',quantity=1,expected_version=2,reason='Vente pendant comptage',idempotency_key=str(uuid4())))
 assert apply(client,d).status_code==409
 assert client.get('/api/products/1').json()['current_stock']==10
 d=client.get('/api/inventories/1').json();line=next(l for l in d['lines'] if l['product_id']==2)
 d=count(client,d,line,8).json();assert apply(client,d).status_code==200
 assert client.get('/api/products/2').json()['current_stock']==8

def test_count_replay_conflict_cancel_and_roles(client):
 d=create(client);line=d['lines'][0];key=str(uuid4())
 r=count(client,d,line,0,idempotency_key=key);assert r.status_code==200
 assert count(client,d,line,0,idempotency_key=key).json()==r.json()
 assert count(client,d,line,1).status_code==409
 d=r.json();r=client.post('/api/inventories/1/cancel',json=dict(expected_version=d['version'],reason='Report du comptage',idempotency_key=str(uuid4())))
 assert r.status_code==200 and r.json()['status']=='CANCELLED'
 assert client.get('/api/products/1').json()['current_stock']==10
 client.post('/api/auth/users',json=dict(name='Viewer',email='viewer@example.test',password='LocalTest321!',role='VIEWER'))
 client.post('/api/auth/logout');client.post('/api/auth/login',json=dict(email='viewer@example.test',password='LocalTest321!'))
 assert client.get('/api/inventories/1').status_code==200
 assert apply(client,d).status_code==403
 assert count(client,d,line,1).status_code==403
