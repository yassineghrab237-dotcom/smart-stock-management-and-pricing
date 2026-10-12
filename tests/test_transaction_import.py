from uuid import uuid4
from tests.test_commerce import client, create
from tests.test_imports import source, analyze, commit
from libs.common.database import connect
from services.stock_service.app.services.analysis import snapshot

HEADER='reference,sku,sold_on,quantity,unit_price_ttc,tax_rate,discount_ttc,unit_cost_ht,customer_id\n'

def body(lines):return source(HEADER+lines,'transactions')

def test_transaction_baskets_stock_cost_and_retry(client):
    b=body('PANIER-A,SKU-0,2025-01-01,2,119,19,0,60,\nPANIER-A,SKU-1,2025-01-01,1,50,0,0,20,\nPANIER-B,SKU-0,2025-01-02,1,119,19,0,60,')
    p=analyze(client,b);assert p['valid']
    assert p['rows'][0]['data']['stock_after_batch']==7
    r=commit(client,b,p);assert r.status_code==200,r.text
    assert commit(client,{**b,'filename':'renamed.csv'},p).json()['already_imported']
    assert client.get('/api/products/1').json()['current_stock']==7
    assert client.get('/api/products/2').json()['current_stock']==9
    docs=client.get('/api/commerce/documents').json()['items'];assert len(docs)==2
    assert all(d['status']=='CONFIRMED' for d in docs)
    report=client.get('/api/insights/sales?start=2025-01-01&end=2025-01-02').json()
    assert report['sales_count']==2 and report['totals']['contribution_ht']=='150.0000'
    assert client.get('/api/insights/sales').json()['sales_count']==0
    detail=client.get('/api/commerce/documents/1').json();assert detail['sold_on']=='2025-01-01'
    assert not analyze(client,{**b,'csv_text':b['csv_text']+'\n'})['valid']

def test_atomic_shortage_and_stale_stock(client):
    b=body('A,SKU-0,2025-01-01,6,10,0,0,,\nB,SKU-0,2025-01-01,6,10,0,0,,')
    p=analyze(client,b);assert not p['valid']
    assert commit(client,b,p).status_code==422
    assert client.get('/api/commerce/documents').json()['items']==[]
    assert client.get('/api/products/1').json()['current_stock']==10
    b=body('A,SKU-0,2025-01-01,2,10,0,0,,');p=analyze(client,b)
    client.post('/api/movements',json=dict(product_id=1,type='OUT',quantity=1,reason='Concurrent',expected_version=2,idempotency_key=str(uuid4())))
    assert commit(client,b,p).status_code==409
    assert client.get('/api/commerce/documents').json()['items']==[]

def test_inconsistent_metadata_and_duplicate_sku(client):
    for lines in ['A,SKU-0,2025-01-01,1,10,0,0,,\nA,SKU-0,2025-01-01,1,10,0,0,,','A,SKU-0,2025-01-01,1,10,0,0,,\nA,SKU-1,2025-01-02,1,10,0,0,,','A,SKU-0,2999-01-01,1,10,0,0,,','A,SKU-0,2025-01-01,1,10,101,0,,','A,SKU-0,2025-01-01,1,10,0,0,,999']:
        b=body(lines);p=analyze(client,b);assert not p['valid'];assert commit(client,b,p).status_code==422
    assert client.get('/api/commerce/documents').json()['items']==[]

def test_prevent_cross_source_duplicates(client):
    historical=source('reference,sku,sold_on,quantity,unit_price\nOLD,SKU-0,2025-01-01,1,10','sales')
    assert commit(client,historical).status_code==200
    assert not analyze(client,body('OLD,SKU-0,2025-01-01,1,10,0,0,5,'))['valid']
    create(client,reference='DRAFT')
    assert not analyze(client,source('reference,sku,sold_on,quantity,unit_price\nDRAFT,SKU-0,2025-01-01,1,10','sales'))['valid']

def test_ml_uses_operational_net_and_invalidates_after_return(client):
    b=body('A,SKU-0,2025-01-01,2,119,19,0,60,');assert commit(client,b).status_code==200
    with connect(client.app.state.db_path) as db:
        src,old=snapshot(db)
    assert src['sales'][0]['sold_on']=='2025-01-01' and src['sales'][0]['quantity']==2
    line=client.get('/api/commerce/documents/1').json()['lines'][0]
    r=client.post(f"/api/commerce/lines/{line['id']}/returns",json=dict(quantity=2,restock=True,reason='Retour total',expected_product_version=3,idempotency_key=str(uuid4())))
    assert r.status_code==201,r.text
    with connect(client.app.state.db_path) as db:
        src,new=snapshot(db)
    assert src['sales'][0]['quantity']==0 and old!=new
