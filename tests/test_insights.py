from uuid import uuid4
from datetime import datetime,timedelta
from tests.test_commerce import client, create, confirm
from libs.common.database import connect
from services.stock_service.app.services.insights import TUNIS, business_day

def test_known_and_unknown_costs_and_damage(client):
    d=create(client);s=confirm(client,d).json()
    client.post(f"/api/commerce/lines/{s['lines'][0]['id']}/returns",json=dict(quantity=1,restock=False,reason='Abîmé',expected_product_version=3,idempotency_key=str(uuid4())))
    r=client.get('/api/insights/sales');assert r.status_code==200,r.text
    total=r.json()['totals']
    assert total['net_ttc']=='119.0000' and total['net_ht']=='100.0000'
    assert total['contribution_ht']=='-20.0000'
    d=create(client,lines=[dict(product_id=2,quantity=1,unit_price_ttc='50',tax_rate='0')]);confirm(client,d)
    r=client.get('/api/insights/sales').json()
    assert r['totals']['contribution_ht'] is None
    assert r['totals']['known_contribution_ht']=='-20.0000'
    assert r['totals']['known_cost_lines']==1 and r['totals']['line_count']==2
    assert r['products'][0]['sku']=='SKU-0'

def test_baskets_customers_and_return_exclusion(client):
    customer=client.post('/api/crm/contacts',json=dict(name='Client QA',kind='CUSTOMER',idempotency_key=str(uuid4()))).json()
    ids=[]
    for i in range(2):
        d=create(client,customer_id=customer['id'],lines=[dict(product_id=p,quantity=1,unit_price_ttc='10',tax_rate='0',unit_cost_ht='4') for p in [1,2]])
        r=confirm(client,d,product_versions={'1':i+2,'2':i+2});assert r.status_code==200,r.text
        ids.append(r.json()['lines'][0]['id'])
    create(client,'QUOTE')
    r=client.get('/api/insights/sales').json()
    assert r['sales_count']==2 and r['associations'][0]['baskets']==2
    assert r['totals']['contribution_ht']=='24.0000'
    assert client.get('/api/insights/sales?customer_id=99').json()['sales_count']==0
    assert client.get(f"/api/insights/sales?customer_id={customer['id']}").json()['sales_count']==2
    client.post(f'/api/commerce/lines/{ids[0]}/returns',json=dict(quantity=1,restock=True,reason='Retour',expected_product_version=4,idempotency_key=str(uuid4())))
    r=client.get('/api/insights/sales').json()
    assert r['associations']==[] and r['totals']['contribution_ht']=='18.0000'

def test_period_and_tunis_day(client):
    assert business_day('2026-10-10T23:30:00+00:00').isoformat()=='2026-10-11'
    assert client.get('/api/insights/sales?start=2026-01-02&end=2026-01-01').status_code==422
    assert client.get('/api/insights/sales?end=2999-01-01').status_code==422
    today=datetime.now(TUNIS).date();old=today-timedelta(days=100)
    d=create(client);confirm(client,d)
    with connect(client.app.state.db_path,write=True) as db:
        db.execute('UPDATE commercial_documents SET confirmed_at=? WHERE id=?',(f'{old.isoformat()}T12:00:00+01:00',d['id']))
    assert client.get('/api/insights/sales').json()['sales_count']==0
    r=client.get(f'/api/insights/sales?start={old}&end={old}').json()
    assert r['sales_count']==1
    client.post('/api/auth/logout');assert client.get('/api/insights/sales').status_code==401
