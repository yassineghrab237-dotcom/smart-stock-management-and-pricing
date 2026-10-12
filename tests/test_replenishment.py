from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from tests.test_purchases import client

def setup(c,**changes):
    assert c.patch('/api/products/1',json=dict(expected_version=1,threshold_min=3,threshold_max=10)).status_code==200
    body=dict(supplier_id=1,unit_cost_ht='10',lead_days=7,min_quantity=5,pack_size=4,enabled=True,expected_version=0,reason='Accord fournisseur',idempotency_key=str(uuid4()))
    body.update(changes)
    r=c.post('/api/replenishment/policies/1',json=body)
    assert r.status_code==200,r.text
    return body

def proposal(c,budget=None):
    r=c.get('/api/replenishment/plan',params=dict(supplier_id=1,**({'budget':budget} if budget is not None else {})))
    assert r.status_code==200,r.text
    return r.json()

def draft(c,p,**changes):
    body=dict(supplier_id=1,budget=p['budget'],expected_fingerprint=p['fingerprint'],reference=str(uuid4()),idempotency_key=str(uuid4()))
    body.update(changes)
    return c.post('/api/replenishment/draft',json=body)

def test_rounding_budget_drafts_and_receipts(client):
    setup(client)
    p=proposal(client);assert p['items'][0]['needed']==12 and p['total_ht']=='120.0000'
    p=proposal(client,'90');assert p['items'][0]['quantity']==8 and p['total_ht']=='80.0000' and p['remaining_budget']=='10.0000'
    key=str(uuid4());r=draft(client,p,idempotency_key=key,reference='RESTOCK-QA');assert r.status_code==201,r.text
    d=r.json();assert draft(client,p,idempotency_key=key,reference='RESTOCK-QA').json()==d
    assert client.get('/api/products/1').json()['current_stock']==0
    q=proposal(client);assert q['items'][0]['draft_units']==8 and q['items'][0]['quantity']==0
    d=client.post(f"/api/purchases/orders/{d['id']}/confirm",json=dict(expected_version=d['version'],idempotency_key=str(uuid4()))).json()
    q=proposal(client);assert q['items'][0]['incoming']==8 and q['items'][0]['draft_units']==0 and q['items'][0]['quantity']==0
    r=client.post(f"/api/purchases/orders/{d['id']}/receive",json=dict(expected_version=d['version'],reason='BL',lines=[dict(line_id=d['lines'][0]['id'],quantity=3,expected_product_version=2)],idempotency_key=str(uuid4())))
    assert r.status_code==200,r.text
    q=proposal(client);assert q['items'][0]['current_stock']==3 and q['items'][0]['incoming']==5 and q['items'][0]['position']==8

def test_budget_minimum_and_stale_plan(client):
    setup(client);assert proposal(client,'50')['items'][0]['quantity']==0
    p=proposal(client)
    client.post('/api/movements',json=dict(product_id=1,type='IN',quantity=1,expected_version=2,reason='Concurrent',idempotency_key=str(uuid4())))
    assert draft(client,p).status_code==409
    assert client.get('/api/purchases/orders').json()['items']==[]
    assert client.get('/api/replenishment/plan?budget=-1').status_code==422

def test_concurrent_drafts_do_not_double_order(client):
    setup(client);p=proposal(client)
    with ThreadPoolExecutor(max_workers=2) as pool:
        codes=list(pool.map(lambda _:draft(client,p).status_code,range(2)))
    assert sorted(codes)==[201,409]
    assert len(client.get('/api/purchases/orders').json()['items'])==1

def test_policy_history_idempotence_and_disable(client):
    b=setup(client)
    assert client.post('/api/replenishment/policies/1',json=b).status_code==200
    assert len(client.get('/api/replenishment/policies/1').json()['events'])==1
    assert client.post('/api/replenishment/policies/1',json={**b,'idempotency_key':str(uuid4())}).status_code==409
    b.update(enabled=False,expected_version=1,idempotency_key=str(uuid4()))
    assert client.post('/api/replenishment/policies/1',json=b).status_code==200
    assert proposal(client)['items'][0]['quantity']==0
    assert len(client.get('/api/replenishment/policies/1').json()['events'])==2

def test_missing_thresholds_and_roles(client):
    r=client.get('/api/replenishment/plan').json();assert all(i['quantity']==0 for i in r['items'])
    b=setup(client)
    client.post('/api/auth/users',json=dict(name='Viewer',email='viewer@example.test',password='LocalTest321!',role='VIEWER'))
    client.post('/api/auth/logout');client.post('/api/auth/login',json=dict(email='viewer@example.test',password='LocalTest321!'))
    assert client.get('/api/replenishment/plan').status_code==200
    assert client.post('/api/replenishment/policies/1',json=b).status_code==403
    assert draft(client,proposal(client)).status_code==403
