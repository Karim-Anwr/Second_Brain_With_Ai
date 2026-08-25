import 'package:dio/dio.dart';

import '../config/app_config.dart';
import '../storage/token_storage.dart';
import 'api_exception.dart';
import 'auth_interceptor.dart';

class ApiClient {
  ApiClient({
    required TokenStorage tokenStorage,
    String? baseUrl,
    Future<void> Function()? onSessionExpired,
  }) {
    final resolvedBaseUrl = baseUrl ?? AppConfig.apiBaseUrl;
    _client = Dio(_baseOptions(resolvedBaseUrl));
    _refreshClient = Dio(_baseOptions(resolvedBaseUrl));
    _client.interceptors.add(
      AuthInterceptor(
        client: _client,
        refreshClient: _refreshClient,
        tokenStorage: tokenStorage,
        onSessionExpired: onSessionExpired,
      ),
    );
  }

  static const _connectTimeout = Duration(seconds: 15);
  static const _sendTimeout = Duration(seconds: 30);
  static const _receiveTimeout = Duration(seconds: 30);

  late final Dio _client;
  late final Dio _refreshClient;

  Future<Response<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    bool skipAuthentication = false,
  }) {
    return _execute(
      () => _client.get<T>(
        path,
        queryParameters: queryParameters,
        options: _options(skipAuthentication: skipAuthentication),
      ),
    );
  }

  Future<Response<T>> post<T>(
    String path, {
    Object? data,
    Map<String, dynamic>? queryParameters,
    bool skipAuthentication = false,
  }) {
    return _execute(
      () => _client.post<T>(
        path,
        data: data,
        queryParameters: queryParameters,
        options: _options(skipAuthentication: skipAuthentication),
      ),
    );
  }

  Future<Response<T>> delete<T>(
    String path, {
    Object? data,
    bool skipAuthentication = false,
  }) {
    return _execute(
      () => _client.delete<T>(
        path,
        data: data,
        options: _options(skipAuthentication: skipAuthentication),
      ),
    );
  }

  static BaseOptions _baseOptions(String baseUrl) => BaseOptions(
        baseUrl: baseUrl,
        connectTimeout: _connectTimeout,
        sendTimeout: _sendTimeout,
        receiveTimeout: _receiveTimeout,
        contentType: Headers.jsonContentType,
        responseType: ResponseType.json,
        headers: const <String, dynamic>{
          Headers.acceptHeader: Headers.jsonContentType,
        },
      );

  Options _options({required bool skipAuthentication}) => Options(
        extra: <String, dynamic>{
          if (skipAuthentication) AuthInterceptor.skipAuthenticationKey: true,
        },
      );

  Future<Response<T>> _execute<T>(Future<Response<T>> Function() request) async {
    try {
      return await request();
    } on DioException catch (error) {
      if (error.error is ApiException) {
        throw error.error! as ApiException;
      }
      throw ApiException.fromDioException(error);
    }
  }
}
