import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../models/models.dart';

abstract interface class Vault {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
  Future<void> remove(String key);
}

class SecureVault implements Vault {
  final FlutterSecureStorage storage = const FlutterSecureStorage();
  @override
  Future<String?> read(String key) => storage.read(key: key);
  @override
  Future<void> write(String key, String value) =>
      storage.write(key: key, value: value);
  @override
  Future<void> remove(String key) => storage.delete(key: key);
}

class ApiException implements Exception {
  final String message;
  final int status;
  ApiException(this.message, [this.status = 0]);
  @override
  String toString() => message;
}

String operationKey() => List.generate(
  24,
  (_) => Random.secure().nextInt(256).toRadixString(16).padLeft(2, '0'),
).join();

Uri validateEndpoint(
  String value, {
  bool localHttp = const bool.fromEnvironment('ALLOW_LOCAL_HTTP'),
}) {
  final uri = Uri.tryParse(value.trim());
  if (uri == null ||
      uri.host.isEmpty ||
      uri.userInfo.isNotEmpty ||
      uri.hasQuery ||
      uri.hasFragment ||
      !['', '/'].contains(uri.path)) {
    throw ApiException(
      'Adresse attendue : https://votre-service, sans chemin ni identifiant.',
    );
  }
  if (uri.scheme != 'https' &&
      !(localHttp &&
          uri.scheme == 'http' &&
          ['127.0.0.1', 'localhost'].contains(uri.host))) {
    throw ApiException(
      'Utilisez HTTPS. Le test HTTP est réservé au tunnel USB local.',
    );
  }
  return uri.replace(path: '');
}

class StockApi {
  final Vault vault;
  Uri? endpoint;
  String? _token;
  User? user;
  void Function()? onExpired;
  StockApi({Vault? vault}) : vault = vault ?? SecureVault();

  Future<void> restore() async {
    final saved = await vault.read('stock-session');
    if (saved == null) return;
    final json = jsonDecode(saved) as Json;
    endpoint = validateEndpoint(json['endpoint'] as String);
    _token = json['token'] as String;
    user = User.fromJson(await request('/auth/me'));
  }

  Future<Json> request(
    String path, {
    String method = 'GET',
    Json? body,
    bool authenticated = true,
  }) async {
    if (endpoint == null) {
      throw ApiException('Choisissez l’adresse du service.');
    }
    final client = HttpClient()
      ..connectionTimeout = const Duration(seconds: 12);
    try {
      return await (() async {
        final request = await client.openUrl(
          method,
          endpoint!.resolve('/api$path'),
        );
        request.followRedirects = false;
        request.headers.contentType = ContentType.json;
        if (authenticated && _token != null) {
          request.headers.set('Authorization', 'Bearer $_token');
        }
        if (body != null) request.write(jsonEncode(body));
        final response = await request.close();
        final text = await utf8.decoder.bind(response).join();
        Json data;
        try {
          data = jsonDecode(text) as Json;
        } catch (_) {
          throw ApiException(
            'Réponse du service illisible. Réessayez.',
            response.statusCode,
          );
        }
        if (response.statusCode < 200 || response.statusCode >= 300) {
          if (response.statusCode == 401 && authenticated) {
            await vault.remove('stock-session');
            _token = null;
            user = null;
            onExpired?.call();
          }
          throw ApiException(
            data['detail'] as String? ?? 'Le service refuse cette demande.',
            response.statusCode,
          );
        }
        return data;
      })().timeout(const Duration(seconds: 25));
    } on TimeoutException {
      throw ApiException(
        'Le service met trop de temps à répondre. Vérifiez la connexion.',
      );
    } on SocketException {
      throw ApiException(
        'Connexion impossible. Vérifiez le service et le câble USB.',
      );
    } on HttpException {
      throw ApiException(
        'La connexion a été interrompue. Vérifiez l’historique avant de réessayer une opération.',
      );
    } on HandshakeException {
      throw ApiException(
        'La connexion sécurisée a échoué. Vérifiez le certificat HTTPS.',
      );
    } finally {
      client.close(force: true);
    }
  }

  Future<void> login(String address, String email, String password) async {
    endpoint = validateEndpoint(address);
    final result = await request(
      '/mobile/auth/login',
      method: 'POST',
      authenticated: false,
      body: {'email': email, 'password': password},
    );
    final token = result['access_token'] as String;
    try {
      await vault.write(
        'stock-session',
        jsonEncode({'endpoint': endpoint.toString(), 'token': token}),
      );
    } catch (_) {
      _token = token;
      try {
        await request('/mobile/auth/logout', method: 'POST', body: {});
      } catch (_) {}
      _token = null;
      throw ApiException(
        'Le téléphone ne peut pas protéger la session. Vérifiez son stockage sécurisé.',
      );
    }
    _token = token;
    user = User.fromJson(result['user'] as Json);
  }

  Future<void> logout() async {
    await request('/mobile/auth/logout', method: 'POST', body: {});
    await vault.remove('stock-session');
    _token = null;
    user = null;
  }

  String get _pendingKey => 'stock-pending-${endpoint.toString()}-${user?.id}';
  Future<Json?> pending() async {
    final value = await vault.read(_pendingKey);
    return value == null ? null : jsonDecode(value) as Json;
  }

  Future<void> prepare(
    String path,
    String method,
    Json body,
    String summary,
  ) async {
    if (await pending() != null) {
      throw ApiException(
        'Vérifiez d’abord l’opération en attente depuis l’accueil.',
      );
    }
    await vault.write(
      _pendingKey,
      jsonEncode({
        'path': path,
        'method': method,
        'body': body,
        'summary': summary,
      }),
    );
  }

  Future<Json> sendPending() async {
    final operation = await pending();
    if (operation == null) throw ApiException('Aucune opération en attente.');
    final key = _pendingKey;
    final result = await request(
      operation['path'] as String,
      method: operation['method'] as String,
      body: operation['body'] as Json,
    );
    await vault.remove(key);
    return result;
  }

  // Un abandon efface uniquement le brouillon local. Il n'annule jamais le serveur.
  Future<void> forgetPending() => vault.remove(_pendingKey);
}
