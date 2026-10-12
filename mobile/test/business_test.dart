import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_stock_mobile/models/models.dart';
import 'package:smart_stock_mobile/models/business.dart';
import 'package:smart_stock_mobile/services/api.dart';
import 'package:smart_stock_mobile/screens/business/business_detail.dart';

class ReadOnlyBusinessApi extends StockApi {
  ReadOnlyBusinessApi() {
    user = User.fromJson({
      'id': 1,
      'name': 'Viewer',
      'email': 'qa@example.test',
      'role': 'VIEWER',
    });
  }
  @override
  Future<Json> request(
    String path, {
    String method = 'GET',
    Json? body,
    bool authenticated = true,
  }) async => {
    'id': 1,
    'reference': 'Devis de recette pour une entreprise',
    'kind': 'QUOTE',
    'status': 'DRAFT',
    'version': 1,
    'customer_name':
        'Client avec un nom particulièrement long pour tester le mobile',
    'totals': {'total_ttc': '119.0000'},
    'net_total_ttc': '119.0000',
    'lines': [
      {
        'name': 'Ordinateur portable de recette',
        'sku': 'QA-MOBILE',
        'quantity': 1,
        'unit_price_ttc': '119.0000',
        'tax_rate': '19.0000',
        'unit_cost_ht': null,
        'returned': 0,
      },
    ],
  };
}

void main() {
  for (final width in [320.0, 390.0, 768.0]) {
    testWidgets('Document commercial lecteur à $width', (tester) async {
      tester.view.physicalSize = Size(width, 1000);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(
        MaterialApp(
          home: BusinessDetail(
            api: ReadOnlyBusinessApi(),
            kind: BusinessKind.sales,
            id: 1,
          ),
        ),
      );
      await tester.pumpAndSettle();
      expect(find.textContaining('Total TTC : 119,0000'), findsOneWidget);
      expect(find.text('Convertir ce devis en vente'), findsNothing);
      expect(find.textContaining('Non renseigné HT'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
}
