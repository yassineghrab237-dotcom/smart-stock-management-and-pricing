from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'purchases.sqlite3')) as c:
        c.post('/api/auth/setup', json=dict(name='QA',email='qa@example.test',password='LocalTest321!'))
        c.post('/api/crm/contacts',json=dict(name='Fournisseur QA',kind='SUPPLIER',idempotency_key=str(uuid4())))
        for i in range(2):
            c.post('/api/products',json=dict(name=f'Produit {i}',sku=f'QA-{i}'))
        yield c

def create(c, **changes):
    data=dict(reference=str(uuid4()),supplier_id=1,expected_on='2026-12-01',lines=[dict(product_id=1,quantity=5,unit_cost_ht='20.5')],idempotency_key=str(uuid4()))
    data.update(changes)
    r=c.post('/api/purchases/orders',json=data)
    assert r.status_code==201, r.text
    return r.json()

def confirm(c,d):
    r=c.post(f"/api/purchases/orders/{d['id']}/confirm",json=dict(expected_version=d['version'],idempotency_key=str(uuid4())))
    assert r.status_code==200,r.text
    return r.json()

def receive(c,d,qty=2,**changes):
    b=dict(expected_version=d['version'],reason='BL de recette',lines=[dict(line_id=d['lines'][0]['id'],quantity=qty,expected_product_version=1)],idempotency_key=str(uuid4()))
    b.update(changes)
    return c.post(f"/api/purchases/orders/{d['id']}/receive",json=b)

def test_partial_complete_and_replay(client):
    d=create(client);assert d['total_ht']=='102.5000'
    assert receive(client,d).status_code==409
    d=confirm(client,d)
    assert client.get('/api/products/1').json()['current_stock']==0
    key=str(uuid4());r=receive(client,d,idempotency_key=key);assert r.status_code==200,r.text
    assert receive(client,d,idempotency_key=key).json()==r.json()
    d=r.json();assert d['status']=='PART_RECEIVED' and d['remaining_ht']=='61.5000'
    assert client.get('/api/products/1').json()['current_stock']==2
    assert receive(client,d,4).status_code==409
    r=receive(client,d,lines=[dict(line_id=d['lines'][0]['id'],quantity=3,expected_product_version=2)])
    assert r.status_code==200,r.text
    assert r.json()['status']=='RECEIVED' and r.json()['remaining_ht']=='0.0000'
    assert client.get('/api/products/1').json()['current_stock']==5
    assert receive(client,r.json()).status_code==409

def test_atomic_receipt_and_stale_versions(client):
    d=confirm(client,create(client,lines=[dict(product_id=i,quantity=5,unit_cost_ht='1') for i in [1,2]]))
    lines=[dict(line_id=l['id'],quantity=1,expected_product_version=1 if i==0 else 99) for i,l in enumerate(d['lines'])]
    assert receive(client,d,lines=lines).status_code==409
    assert client.get('/api/products/1').json()['current_stock']==0
    assert client.get('/api/purchases/orders/1').json()['receipts']==[]
    assert receive(client,d,expected_version=1).status_code==409
    lines[1]['expected_product_version']=1
    assert receive(client,d,lines=lines).status_code==200
    assert receive(client,d,lines=lines).status_code==409

def test_close_only_remaining(client):
    d=confirm(client,create(client));d=receive(client,d).json()
    body=dict(expected_version=d['version'],reason='Solde indisponible',idempotency_key=str(uuid4()))
    r=client.post('/api/purchases/orders/1/cancel',json=body)
    assert r.status_code==200 and r.json()['status']=='CLOSED'
    assert client.post('/api/purchases/orders/1/cancel',json=body).json()==r.json()
    assert client.get('/api/products/1').json()['current_stock']==2
    assert receive(client,r.json()).status_code==409

def test_supplier_reference_and_line_validation(client):
    d=create(client,reference='UNIQUE')
    payload=dict(reference='UNIQUE',supplier_id=1,expected_on='2026-12-01',lines=[dict(product_id=1,quantity=1,unit_cost_ht='5')],idempotency_key=str(uuid4()))
    assert client.post('/api/purchases/orders',json=payload).status_code==409
    payload['reference']='OTHER';payload['lines']*=2
    assert client.post('/api/purchases/orders',json=payload).status_code==422
    payload['lines']=payload['lines'][:1]
    client.post('/api/crm/contacts',json=dict(name='Client',kind='CUSTOMER',idempotency_key=str(uuid4())))
    payload['supplier_id']=2
    assert client.post('/api/purchases/orders',json=payload).status_code==422
    assert len(client.get('/api/purchases/orders').json()['items'])==1

def test_viewer_cannot_write(client):
    d=create(client)
    client.post('/api/auth/users',json=dict(name='Viewer',email='v@example.test',password='LocalTest321!',role='VIEWER'))
    client.post('/api/auth/logout');client.post('/api/auth/login',json=dict(email='v@example.test',password='LocalTest321!'))
    assert client.get('/api/purchases/orders/1').status_code==200
    assert client.post('/api/purchases/orders/1/confirm',json=dict(expected_version=1,idempotency_key=str(uuid4()))).status_code==403
    assert receive(client,d).status_code==403
    assert client.post('/api/purchases/orders/1/cancel',json=dict(expected_version=1,reason='Non',idempotency_key=str(uuid4()))).status_code==403
    client.post('/api/auth/logout')
    assert client.get('/api/purchases/orders').status_code==401
