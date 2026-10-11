import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';
import 'package:smart_stock_mobile/main.dart';
import 'package:smart_stock_mobile/services/api.dart';

void main() {
  final binding = IntegrationTestWidgetsFlutterBinding.ensureInitialized();
  testWidgets(
    'Backend réel : connexion, produit, stock, prix, reprise et historique',
    (tester) async {
      final api = StockApi();
      await api.vault.remove('stock-session');
      await tester.pumpWidget(StockApp(api: api));
      Future<void> waitText(String text) async {
        for (var i = 0; i < 100; i++) {
          await tester.pump(const Duration(milliseconds: 200));
          if (find.text(text).evaluate().isNotEmpty) return;
          await Future<void>.delayed(const Duration(milliseconds: 100));
        }
        throw TestFailure('Texte absent : $text');
      }

      Future<void> tapText(String text) async {
        await tester.ensureVisible(find.text(text).first);
        await tester.tap(find.text(text).first);
        await tester.pump(const Duration(milliseconds: 400));
      }

      await waitText('Se connecter');
      final fields = find.byType(TextFormField);
      await tester.enterText(fields.at(0), 'http://127.0.0.1:8012');
      await tester.enterText(fields.at(1), 'native@example.test');
      await tester.enterText(fields.at(2), 'StockQaTest123!');
      await tapText('Se connecter');
      await waitText('Bonjour QA Native');
      await binding.convertFlutterSurfaceToImage();
      await tester.pump();
      await binding.takeScreenshot('native-home');
      await tapText('Ajouter un produit');
      await waitText('Créer le produit');
      await tester.enterText(fields.at(0), 'Câble QA mobile');
      await tester.enterText(fields.at(1), 'QA-NATIVE-CABLE');
      await tapText('Créer le produit');
      await waitText('Bonjour QA Native');
      await tapText('Consulter les produits');
      await waitText('Câble QA mobile');
      await tapText('Câble QA mobile');
      await waitText('Enregistrer un mouvement');
      await tapText('Enregistrer un mouvement');
      await waitText('Vérifier le mouvement');
      await tester.enterText(fields.at(0), '20');
      await tester.enterText(fields.at(1), 'Réception QA native');
      await tapText('Vérifier le mouvement');
      await waitText('Vérifier l’opération');
      await binding.takeScreenshot('native-confirmation');
      await tapText('Confirmer');
      await waitText('Opération enregistrée par le service.');
      final products = await api.request('/products');
      final product =
          (products['items'] as List).single as Map<String, dynamic>;
      expect(product['current_stock'], 20);
      await binding.takeScreenshot('native-product');
      await tapText('Changer le prix');
      await tester.pump();
      await tester.enterText(fields.at(0), '12.3456');
      await tester.enterText(fields.at(1), 'Prix QA natif');
      await tapText('Vérifier le prix');
      await waitText('Vérifier l’opération');
      await tapText('Confirmer');
      await waitText('Opération enregistrée par le service.');
      expect(
        (await api.request('/products/${product['id']}'))['current_price'],
        '12.3456',
      );
      expect(
        (await api.request(
          '/movements?product_id=${product['id']}',
        ))['items'].length,
        1,
      );
      // Une requête appliquée, puis répétée via le brouillon persistant.
      final updated = await api.request('/products/${product['id']}');
      final body = <String, dynamic>{
        'product_id': product['id'],
        'type': 'IN',
        'quantity': 7,
        'reason': 'QA réponse perdue simulée après commit',
        'expected_version': updated['version'],
        'idempotency_key': operationKey(),
      };
      await api.prepare('/movements', 'POST', body, 'QA reprise entrée 7');
      await api.request('/movements', method: 'POST', body: body);
      final restored = StockApi();
      await restored.restore();
      expect(await restored.pending(), isNotNull);
      await restored.sendPending();
      expect(
        (await restored.request('/products/${product['id']}'))['current_stock'],
        27,
      );
      expect((await restored.request('/movements'))['items'].length, 2);
      expect(await restored.pending(), isNull);
      final fresh = await api.request('/products/${product['id']}');
      await api.request(
        '/products/${product['id']}',
        method: 'PATCH',
        body: {'threshold_min': 30, 'expected_version': fresh['version']},
      );
      await tester.pageBack();
      await tester.pump(const Duration(milliseconds: 400));
      await tapText('Alertes');
      await waitText('Câble QA mobile');
      await binding.takeScreenshot('native-alerts');
      await tapText('Plus');
      await waitText('Analyser les ventes');
      await tapText('Analyser les ventes');
      await waitText('Lancer l’analyse');
      await tapText('Lancer l’analyse');
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 300));
        final jobs = await api.request('/analysis/jobs');
        if ((jobs['items'] as List).first['status'] == 'SUCCEEDED') break;
        await Future<void>.delayed(const Duration(milliseconds: 200));
      }
      await tester.tap(find.byTooltip('Actualiser'));
      await waitText('Analyse 1 · Terminé');
      await tapText('Analyse 1 · Terminé');
      await waitText('Résultat de l’analyse');
      await binding.takeScreenshot('native-analysis');
      await api.logout();
      try {
        await restored.request('/auth/me');
        fail('Le jeton révoqué devait être refusé');
      } on ApiException catch (e) {
        expect(e.status, 401);
      }
    },
  );
}
