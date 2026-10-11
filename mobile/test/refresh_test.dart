import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_stock_mobile/models/models.dart';
import 'package:smart_stock_mobile/services/api.dart';
import 'package:smart_stock_mobile/screens/workspace.dart';
import 'package:smart_stock_mobile/screens/product_detail.dart';

class DelayedApi extends StockApi {
  final products = Completer<Json>();
  Completer<Json>? nextProduct;
  DelayedApi() {
    user = User.fromJson({
      'id': 1,
      'name': 'QA',
      'email': 'qa@example.test',
      'role': 'MANAGER',
    });
  }
  @override
  Future<Json?> pending() async => null;
  @override
  Future<Json> request(
    String path, {
    String method = 'GET',
    Json? body,
    bool authenticated = true,
  }) async {
    if (path == '/dashboard') {
      return {
        'product_count': 0,
        'low_stock_count': 0,
        'overstock_count': 0,
        'recent_movements': <Json>[],
      };
    }
    if (path == '/products') return products.future;
    if (path == '/products/1') {
      if (nextProduct != null) return nextProduct!.future;
      return {
        'id': 1,
        'name': 'Produit QA',
        'sku': 'QA',
        'version': 1,
        'current_stock': 0,
        'threshold_min': 0,
      };
    }
    return {'items': <Json>[]};
  }
}

void main() {
  testWidgets(
    'Un nouvel onglet ne réutilise pas la structure de l’ancien résultat',
    (tester) async {
      final api = DelayedApi();
      await tester.pumpWidget(
        MaterialApp(
          home: Workspace(api: api, onLogout: () {}),
        ),
      );
      await tester.pumpAndSettle();
      await tester.tap(find.text('Consulter les produits'));
      await tester.pump();
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      expect(tester.takeException(), isNull);
      api.products.complete({'items': <Json>[]});
      await tester.pumpAndSettle();
      expect(find.text('Rechercher un produit'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
  testWidgets(
    'La fiche masque ses actions tant que sa nouvelle version est inconnue',
    (tester) async {
      final api = DelayedApi();
      await tester.pumpWidget(
        MaterialApp(home: ProductDetailScreen(api: api, id: 1)),
      );
      await tester.pumpAndSettle();
      expect(find.text('Changer le prix'), findsOneWidget);
      api.nextProduct = Completer<Json>();
      await tester.tap(find.byTooltip('Actualiser'));
      await tester.pump();
      expect(find.text('Changer le prix'), findsNothing);
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
      api.nextProduct!.complete({
        'id': 1,
        'name': 'Produit QA',
        'sku': 'QA',
        'version': 2,
        'current_stock': 20,
        'threshold_min': 0,
      });
      await tester.pumpAndSettle();
      expect(find.text('20 unités'), findsOneWidget);
      expect(find.text('Changer le prix'), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
