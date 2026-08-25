import '../core/network/api_client.dart';
import '../core/network/api_exception.dart';
import '../core/storage/token_storage.dart';
import '../models/auth_tokens.dart';

abstract interface class AuthenticationRepository {
  Future<AuthTokens> register({
    required String email,
    required String password,
    String? displayName,
  });

  Future<AuthTokens> login({
    required String email,
    required String password,
  });

  Future<AuthTokens> refresh({required String refreshToken});
  Future<bool> restoreSession();
  Future<void> logout();
}

class AuthRepository implements AuthenticationRepository {
  AuthRepository({
    required ApiClient apiClient,
    required TokenStorage tokenStorage,
  })  : _apiClient = apiClient,
        _tokenStorage = tokenStorage;

  final ApiClient _apiClient;
  final TokenStorage _tokenStorage;

  @override
  Future<AuthTokens> register({
    required String email,
    required String password,
    String? displayName,
  }) {
    return _authenticate(
      'auth/register',
      <String, dynamic>{
        'email': email,
        'password': password,
        'display_name': displayName,
      },
    );
  }

  @override
  Future<AuthTokens> login({
    required String email,
    required String password,
  }) {
    return _authenticate(
      'auth/login',
      <String, dynamic>{
        'email': email,
        'password': password,
      },
    );
  }

  @override
  Future<AuthTokens> refresh({required String refreshToken}) async {
    try {
      return await _authenticate(
        'auth/refresh',
        <String, dynamic>{'refresh_token': refreshToken},
      );
    } catch (error, stackTrace) {
      try {
        await _tokenStorage.clearTokens();
      } catch (_) {
        // The original refresh failure remains the caller-facing result.
      }
      Error.throwWithStackTrace(error, stackTrace);
    }
  }

  @override
  Future<bool> restoreSession() => _tokenStorage.hasTokens();

  @override
  Future<void> logout() => _tokenStorage.clearTokens();

  Future<AuthTokens> _authenticate(
    String path,
    Map<String, dynamic> payload,
  ) async {
    final response = await _apiClient.post<dynamic>(
      path,
      data: payload,
      skipAuthentication: true,
    );
    final data = response.data;
    if (data is! Map) {
      throw ApiException.malformedResponse();
    }

    try {
      final tokens = AuthTokens.fromJson(Map<String, dynamic>.from(data));
      await _tokenStorage.saveTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      return tokens;
    } on FormatException {
      throw ApiException.malformedResponse();
    } on ApiException {
      rethrow;
    } catch (_) {
      throw ApiException.secureStorageFailure();
    }
  }
}
