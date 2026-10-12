from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from services.api_gateway.app.main import create_app

@pytest.fixture
def client(tmp_path):
    with TestClient(create_app(tmp_path/'crm.sqlite3')) as c:
        assert c.post('/api/auth/setup',json=dict(name='CRM QA',email='qa@example.test',password='LocalTest321!')).status_code==201
        yield c

def payload(**kwargs):
    return dict(name='Contact recette',kind='BOTH',idempotency_key=str(uuid4()),**kwargs)

def test_contact_edit_conflict_and_replay(client):
    b=payload();r=client.post('/api/crm/contacts',json=b);assert r.status_code==201,r.text
    assert client.post('/api/crm/contacts',json=b).json()==r.json()
    assert len(client.get('/api/crm/contacts').json()['items'])==1
    fields={k:v for k,v in r.json().items() if k not in ('id','version','created_at','updated_at')}
    edit={**fields,'name':'Nouveau nom','expected_version':1,'reason':'Correction QA','idempotency_key':str(uuid4())}
    result=client.patch('/api/crm/contacts/1',json=edit);assert result.status_code==200,result.text
    assert client.patch('/api/crm/contacts/1',json=edit).json()==result.json()
    assert client.patch('/api/crm/contacts/1',json={**edit,'idempotency_key':str(uuid4())}).status_code==409
    detail=client.get('/api/crm/contacts/1').json();assert detail['version']==2
    assert len(detail['events'])==2
    assert 'Contact recette' in detail['events'][0]['detail']

def test_notes_tasks_and_conflicts(client):
    client.post('/api/crm/contacts',json=payload())
    note={'detail':'Client demande un devis.','idempotency_key':str(uuid4())}
    for _ in range(2):assert client.post('/api/crm/contacts/1/notes',json=note).status_code==201
    task={'title':'Préparer le devis','due_on':'2026-11-01','idempotency_key':str(uuid4())}
    for _ in range(2):assert client.post('/api/crm/contacts/1/tasks',json=task).status_code==201
    status={'status':'DONE','expected_version':1,'idempotency_key':str(uuid4())}
    for _ in range(2):assert client.patch('/api/crm/tasks/1',json=status).status_code==200
    assert client.patch('/api/crm/tasks/1',json={**status,'idempotency_key':str(uuid4())}).status_code==409
    result=client.get('/api/crm/contacts/1').json()
    assert len(result['tasks'])==1 and result['tasks'][0]['status']=='DONE'
    assert len(result['events'])==4
    assert client.post('/api/crm/contacts/2/notes',json={**note,'idempotency_key':str(uuid4())}).status_code==404

@pytest.mark.parametrize('changes',[{'email':'bad'},{'lead_days':-1},{'min_order':0},{'contact_permission':'YES'},{'name':'   '}])
def test_invalid_contact(client,changes):
    b=payload();b.update(changes)
    assert client.post('/api/crm/contacts',json=b).status_code==422
    assert client.get('/api/crm/contacts').json()['items']==[]

def test_rights_and_origin(client):
    client.post('/api/crm/contacts',json=payload())
    assert client.post('/api/crm/contacts',json=payload(),headers={'origin':'https://evil.test'}).status_code==403
    assert client.get('/api/crm/contacts/999999999999999999999999').status_code==422
    client.post('/api/auth/users',json=dict(name='Viewer',email='viewer@example.test',password='LocalTest321!',role='VIEWER'))
    client.post('/api/auth/logout');client.post('/api/auth/login',json=dict(email='viewer@example.test',password='LocalTest321!'))
    assert client.get('/api/crm/contacts/1').status_code==200
    assert client.post('/api/crm/contacts',json=payload()).status_code==403
    assert client.post('/api/crm/contacts/1/notes',json={'detail':'no','idempotency_key':str(uuid4())}).status_code==403
    client.post('/api/auth/logout');assert client.get('/api/crm/contacts').status_code==401
