import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:smart_stock_mobile/main.dart';
import 'package:smart_stock_mobile/services/api.dart';
import 'package:smart_stock_mobile/models/models.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets('Parcours natif commercial avec serveur réel', (tester) async {
    final api = StockApi();
    await api.vault.remove('stock-session');
    await api.login(
      'http://127.0.0.1:8012',
      'native@example.test',
      'StockQaTest123!',
    );
    Future<Json> post(String path, Json body) => api.request(
      path,
      method: 'POST',
      body: {...body, 'idempotency_key': operationKey()},
    );
    final p = await api.request(
      '/products',
      method: 'POST',
      body: {
        'name': 'Article métier mobile',
        'sku': 'MOBILE-BUSINESS',
        'current_price': '119',
      },
    );
    await post('/movements', {
      'product_id': p['id'],
      'type': 'IN',
      'quantity': 10,
      'reason': 'Stock recette mobile',
      'expected_version': p['version'],
    });
    final supplier = await post('/crm/contacts', {
      'name': 'Fournisseur recette mobile',
      'kind': 'SUPPLIER',
    });
    final order = await post('/purchases/orders', {
      'reference': 'ACHAT-MOBILE-QA',
      'supplier_id': supplier['id'],
      'expected_on': '2026-10-10',
      'lines': [
        {'product_id': p['id'], 'quantity': 5, 'unit_cost_ht': '60'},
      ],
    });
    await post('/purchases/orders/${order['id']}/confirm', {
      'expected_version': order['version'],
    });
    final sale = await post('/commerce/documents', {
      'kind': 'SALE',
      'reference': 'VENTE-MOBILE-QA',
      'lines': [
        {
          'product_id': p['id'],
          'quantity': 2,
          'unit_price_ttc': '119',
          'tax_rate': '19',
          'unit_cost_ht': '60',
        },
      ],
    });
    await tester.pumpWidget(StockApp(api: api));
    Future<void> wait(String text) async {
      for (var i = 0; i < 100; i++) {
        await tester.pump(const Duration(milliseconds: 200));
        if (find.text(text).evaluate().isNotEmpty) return;
        await Future<void>.delayed(const Duration(milliseconds: 100));
      }
      throw TestFailure('Absent : $text');
    }

    Future<void> tap(String text) async {
      await wait(text);
      await tester.ensureVisible(find.text(text).first);
      await tester.tap(find.text(text).first);
      await tester.pump(const Duration(milliseconds: 400));
    }

    Future<void> back() async {
      await tester.pumpAndSettle(const Duration(milliseconds: 200));
      await tester.pageBack();
      await tester.pumpAndSettle(const Duration(milliseconds: 200));
    }

    await wait('Plus');
    await tap('Plus');
    await tap('Espace commercial');
    await wait('Votre activité, sur le terrain');
    await binding.convertFlutterSurfaceToImage();
    await tester.pump();
    await binding.takeScreenshot('native-business-home');
    await tap('Ventes et devis');
    await tap('VENTE-MOBILE-QA');
    await tap('Confirmer la vente');
    await tap('Vérifier et confirmer');
    await wait('Confirmer cette opération');
    await tap('Confirmer');
    await wait('Opération confirmée par le service.');
    expect((await api.request('/products/${p['id']}'))['current_stock'], 8);
    expect(
      (await api.request('/commerce/documents/${sale['id']}'))['status'],
      'CONFIRMED',
    );
    await binding.takeScreenshot('native-business-sale');
    await back();
    await back();
    await tap('Achats et réceptions');
    await tap('ACHAT-MOBILE-QA');
    await tap('Enregistrer une réception');
    await tester.enterText(find.byType(TextFormField).at(0), '2');
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Réception partielle mobile',
    );
    await tap('Vérifier et confirmer');
    await tap('Confirmer');
    await wait('Opération confirmée par le service.');
    expect((await api.request('/products/${p['id']}'))['current_stock'], 10);
    await binding.takeScreenshot('native-business-receipt');
    final inventory = await post('/inventories', {
      'title': 'Comptage mobile QA',
      'product_ids': [p['id']],
    });
    await back();
    await back();
    await tap('Inventaires physiques');
    await tap('Comptage mobile QA');
    await tap('Saisir le comptage');
    await tester.enterText(find.byType(TextFormField).at(0), '9');
    await tester.enterText(
      find.byType(TextFormField).at(1),
      'Comptage rayon mobile',
    );
    await tap('Vérifier et confirmer');
    await tap('Confirmer');
    await wait('Opération confirmée par le service.');
    expect((await api.request('/products/${p['id']}'))['current_stock'], 10);
    await tap('Valider les écarts');
    await tester.enterText(
      find.byType(TextFormField).first,
      'Écart vérifié en recette',
    );
    await tap('Vérifier et confirmer');
    await tap('Confirmer');
    await wait('Opération confirmée par le service.');
    expect((await api.request('/products/${p['id']}'))['current_stock'], 9);
    expect(
      (await api.request('/inventories/${inventory['id']}'))['status'],
      'APPLIED',
    );
    await binding.takeScreenshot('native-business-inventory');
    await back();
    await back();
    await tap('Clients et fournisseurs');
    await tap('Fournisseur recette mobile');
    await tap('Ajouter une note');
    await tester.enterText(
      find.byType(TextFormField).first,
      'Suivi reçu depuis mobile',
    );
    await tap('Vérifier et confirmer');
    await tap('Confirmer');
    await wait('Opération confirmée par le service.');
    expect(
      (await api.request(
        '/crm/contacts/${supplier['id']}',
      ))['events'].first['detail'],
      'Suivi reçu depuis mobile',
    );
    await back();
    await back();
    await tap('Rentabilité');
    await wait('Ventes : 1');
    await binding.takeScreenshot('native-business-insights');
    expect(tester.takeException(), isNull);
  });
}
