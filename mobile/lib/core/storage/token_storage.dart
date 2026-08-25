import 'package:flutter_secure_storage/flutter_secure_storage.dart';

abstract interface class TokenStorage {
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  });

  Future<String?> readAccessToken();
  Future<String?> readRefreshToken();
  Future<void> clearTokens();
  Future<bool> hasTokens();
}

class SecureTokenStorage implements TokenStorage {
  SecureTokenStorage({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  static const _accessTokenKey = 'second_brain_access_token';
  static const _refreshTokenKey = 'second_brain_refresh_token';

  final FlutterSecureStorage _storage;

  @override
  Future<void> saveTokens({
    required String accessToken,
    required String refreshToken,
  }) async {
    final previousAccessToken = await readAccessToken();
    final previousRefreshToken = await readRefreshToken();

    try {
      await _storage.write(key: _accessTokenKey, value: accessToken);
      await _storage.write(key: _refreshTokenKey, value: refreshToken);
    } catch (_) {
      await _restorePreviousTokens(
        accessToken: previousAccessToken,
        refreshToken: previousRefreshToken,
      );
      rethrow;
    }
  }

  @override
  Future<String?> readAccessToken() => _storage.read(key: _accessTokenKey);

  @override
  Future<String?> readRefreshToken() => _storage.read(key: _refreshTokenKey);

  @override
  Future<void> clearTokens() async {
    await _storage.delete(key: _accessTokenKey);
    await _storage.delete(key: _refreshTokenKey);
  }

  @override
  Future<bool> hasTokens() async {
    final accessToken = await readAccessToken();
    final refreshToken = await readRefreshToken();
    return accessToken != null && accessToken.isNotEmpty &&
        refreshToken != null && refreshToken.isNotEmpty;
  }

  Future<void> _restorePreviousTokens({
    required String? accessToken,
    required String? refreshToken,
  }) async {
    if (accessToken == null) {
      await _storage.delete(key: _accessTokenKey);
    } else {
      await _storage.write(key: _accessTokenKey, value: accessToken);
    }

    if (refreshToken == null) {
      await _storage.delete(key: _refreshTokenKey);
    } else {
      await _storage.write(key: _refreshTokenKey, value: refreshToken);
    }
  }
}
