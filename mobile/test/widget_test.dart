import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:smart_stock_mobile/main.dart';
import 'package:smart_stock_mobile/services/api.dart';

class MemoryVault implements Vault {
  final values = <String, String>{};
  @override
  Future<String?> read(String key) async => values[key];
  @override
  Future<void> write(String key, String value) async {
    values[key] = value;
  }

  @override
  Future<void> remove(String key) async {
    values.remove(key);
  }
}

void main() {
  test('Transport refuse HTTP distant et URLs avec identifiants', () {
    expect(
      () => validateEndpoint('http://192.168.1.2:8000', localHttp: true),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => validateEndpoint('https://name:secret@example.test'),
      throwsA(isA<ApiException>()),
    );
    expect(
      () => validateEndpoint('http://127.0.0.1:8000', localHttp: false),
      throwsA(isA<ApiException>()),
    );
    expect(validateEndpoint('https://example.test').scheme, 'https');
  });
  test('Clés aléatoires distinctes', () {
    expect(operationKey(), isNot(operationKey()));
    expect(operationKey().length, 48);
  });
  for (final width in [320.0, 390.0, 768.0]) {
    testWidgets('Connexion lisible et formulaire validé à $width', (
      tester,
    ) async {
      tester.view.physicalSize = Size(width, 900);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      await tester.pumpWidget(StockApp(api: StockApi(vault: MemoryVault())));
      await tester.pumpAndSettle();
      expect(find.text('Smart Stock'), findsOneWidget);
      await tester.ensureVisible(find.text('Se connecter'));
      await tester.tap(find.text('Se connecter'));
      await tester.pumpAndSettle();
      expect(find.text('Indiquez votre adresse e-mail.'), findsOneWidget);
      expect(tester.takeException(), isNull);
    });
  }
  test(
    'Réponse perdue : brouillon conservé au redémarrage, même clé au retry',
    () async {
      // Test de protocole réel : le binding des tests widgets remplace sinon HTTP par un 400.
      final previousOverrides = HttpOverrides.current;
      HttpOverrides.global = null;
      addTearDown(() => HttpOverrides.global = previousOverrides);
      final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() => server.close(force: true));
      final keys = <String>[];
      var attempts = 0;
      server.listen((request) async {
        if (request.uri.path == '/api/mobile/auth/login') {
          request.response.headers.contentType = ContentType.json;
          request.response.write(
            jsonEncode({
              'access_token': 'qa-token',
              'user': {
                'id': 1,
                'name': 'QA',
                'email': 'qa@example.test',
                'role': 'MANAGER',
              },
            }),
          );
        } else if (request.uri.path == '/api/auth/me') {
          request.response.write(
            jsonEncode({
              'id': 1,
              'name': 'QA',
              'email': 'qa@example.test',
              'role': 'MANAGER',
            }),
          );
        } else {
          expect(request.headers.value('Authorization'), 'Bearer qa-token');
          final data =
              jsonDecode(await utf8.decoder.bind(request).join())
                  as Map<String, dynamic>;
          keys.add(data['idempotency_key'] as String);
          attempts++;
          if (attempts == 1) {
            request.response.statusCode = 503;
            request.response.write('{"detail":"QA interruption"}');
          } else {
            request.response.write('{"id":1,"stock_after":20}');
          }
        }
        await request.response.close();
      });
      final vault = MemoryVault();
      final api = StockApi(vault: vault);
      await api.login(
        'http://127.0.0.1:${server.port}',
        'qa@example.test',
        'QA test',
      );
      await api.prepare('/movements', 'POST', {
        'idempotency_key': 'same-qa-key',
      }, 'QA entrée');
      await expectLater(api.sendPending(), throwsA(isA<ApiException>()));
      final restarted = StockApi(vault: vault);
      await restarted.restore();
      expect(await restarted.pending(), isNotNull);
      await restarted.sendPending();
      expect(keys, ['same-qa-key', 'same-qa-key']);
      expect(await restarted.pending(), isNull);
    },
  );
}
