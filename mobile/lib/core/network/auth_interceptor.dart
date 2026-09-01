import 'package:dio/dio.dart';

import '../../models/auth_tokens.dart';
import '../storage/token_storage.dart';
import 'api_exception.dart';

class AuthInterceptor extends Interceptor {
  AuthInterceptor({
    required Dio client,
    required Dio refreshClient,
    required TokenStorage tokenStorage,
    this.onSessionExpired,
  })  : _client = client,
        _refreshClient = refreshClient,
        _tokenStorage = tokenStorage;

  static const skipAuthenticationKey = 'skipAuthentication';
  static const _hasRetriedKey = 'hasRetriedAfterRefresh';

  final Dio _client;
  final Dio _refreshClient;
  final TokenStorage _tokenStorage;
  final Future<void> Function()? onSessionExpired;
  Future<AuthTokens?>? _refreshInFlight;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    if (options.extra[skipAuthenticationKey] == true) {
      handler.next(options);
      return;
    }

    try {
      final accessToken = await _tokenStorage.readAccessToken();
      if (accessToken != null && accessToken.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $accessToken';
      }
      handler.next(options);
    } catch (_) {
      handler.reject(
        DioException(
          requestOptions: options,
          error: ApiException.secureStorageFailure(),
          type: DioExceptionType.unknown,
        ),
      );
    }
  }

  @override
  Future<void> onError(
    DioException error,
    ErrorInterceptorHandler handler,
  ) async {
    final options = error.requestOptions;
    if (!_shouldAttemptRefresh(error, options)) {
      handler.next(error);
      return;
    }

    final tokens = await _refreshTokens();
    if (tokens == null) {
      await _notifySessionExpired();
      handler.next(error);
      return;
    }

    try {
      final retryOptions = options.copyWith(
        headers: <String, dynamic>{
          ...options.headers,
          'Authorization': 'Bearer ${tokens.accessToken}',
        },
        extra: <String, dynamic>{
          ...options.extra,
          _hasRetriedKey: true,
        },
      );
      final response = await _client.fetch<dynamic>(retryOptions);
      handler.resolve(response);
    } on DioException catch (retryError) {
      handler.next(retryError);
    }
  }

  bool _shouldAttemptRefresh(DioException error, RequestOptions options) {
    return error.response?.statusCode == 401 &&
        options.extra[skipAuthenticationKey] != true &&
        options.extra[_hasRetriedKey] != true &&
        !options.path.endsWith('auth/refresh');
  }

  Future<AuthTokens?> _refreshTokens() {
    final activeRefresh = _refreshInFlight;
    if (activeRefresh != null) {
      return activeRefresh;
    }

    final refreshOperation = _performRefresh();
    _refreshInFlight = refreshOperation;
    refreshOperation.whenComplete(() {
      if (identical(_refreshInFlight, refreshOperation)) {
        _refreshInFlight = null;
      }
    });
    return refreshOperation;
  }

  Future<AuthTokens?> _performRefresh() async {
    try {
      final refreshToken = await _tokenStorage.readRefreshToken();
      if (refreshToken == null || refreshToken.isEmpty) {
        await _clearCredentialsSilently();
        return null;
      }

      final response = await _refreshClient.post<dynamic>(
        '/auth/refresh',
        data: <String, dynamic>{'refresh_token': refreshToken},
      );
      final data = response.data;
      if (data is! Map) {
        throw ApiException.malformedResponse();
      }

      final tokens = AuthTokens.fromJson(Map<String, dynamic>.from(data));
      await _tokenStorage.saveTokens(
        accessToken: tokens.accessToken,
        refreshToken: tokens.refreshToken,
      );
      return tokens;
    } catch (_) {
      await _clearCredentialsSilently();
      return null;
    }
  }

  Future<void> _clearCredentialsSilently() async {
    try {
      await _tokenStorage.clearTokens();
    } catch (_) {
      // The original authentication failure remains the caller-facing result.
    }
  }

  Future<void> _notifySessionExpired() async {
    try {
      await onSessionExpired?.call();
    } catch (_) {
      // The original protected-request failure remains the caller-facing result.
    }
  }
}
