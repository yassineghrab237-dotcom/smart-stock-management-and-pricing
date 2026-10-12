from uuid import uuid4
from tests.test_crm import client, payload


def proposal(**changes):
    b=dict(title='Parc de 10 PC',close_on='2026-12-01',expected_ttc='10000',stage='QUALIFIED',reason='Besoin confirmé',idempotency_key=str(uuid4()))
    b.update(changes);return b

def test_opportunity_update_replay_and_no_revenue(client):
    client.post('/api/crm/contacts',json=payload())
    b=proposal();r=client.post('/api/crm/contacts/1/opportunities',json=b);assert r.status_code==201,r.text
    assert client.post('/api/crm/contacts/1/opportunities',json=b).json()==r.json()
    b.update(stage='WON',reason='Accord verbal à transformer en vente',expected_version=1,idempotency_key=str(uuid4()))
    r=client.patch('/api/crm/opportunities/1',json=b);assert r.status_code==200,r.text
    assert client.patch('/api/crm/opportunities/1',json=b).json()==r.json()
    assert client.patch('/api/crm/opportunities/1',json={**b,'idempotency_key':str(uuid4())}).status_code==409
    assert client.get('/api/insights/sales').json()['sales_count']==0
    assert len(client.get('/api/crm/contacts/1/opportunities').json()['items'])==1
    assert len(client.get('/api/crm/contacts/1').json()['events'])==3

def test_quote_customer_boundary_and_viewer(client):
    for _ in range(2):client.post('/api/crm/contacts',json=payload())
    client.post('/api/products',json=dict(name='PC',sku='PC'))
    q=client.post('/api/commerce/documents',json=dict(reference='D-1',kind='QUOTE',customer_id=1,lines=[dict(product_id=1,quantity=1,unit_price_ttc='100',tax_rate='0')],idempotency_key=str(uuid4()))).json()
    assert client.post('/api/crm/contacts/2/opportunities',json=proposal(quote_id=q['id'])).status_code==422
    assert client.post('/api/crm/contacts/1/opportunities',json=proposal(quote_id=q['id'])).status_code==201
    client.post('/api/auth/users',json=dict(name='Viewer',email='v@example.test',password='LocalTest321!',role='VIEWER'))
    client.post('/api/auth/logout');client.post('/api/auth/login',json=dict(email='v@example.test',password='LocalTest321!'))
    assert client.get('/api/crm/contacts/1/opportunities').status_code==200
    assert client.post('/api/crm/contacts/1/opportunities',json=proposal()).status_code==403
    assert client.patch('/api/crm/opportunities/1',json=proposal(expected_version=1)).status_code==403
