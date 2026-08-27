import 'package:dio/dio.dart';

import '../../models/api_error.dart';

class ApiException implements Exception {
  const ApiException({
    required this.code,
    required this.message,
    this.statusCode,
  });

  final int? statusCode;
  final String code;
  final String message;

  factory ApiException.fromDioException(DioException exception) {
    final response = exception.response;
    final backendError = _tryReadBackendError(response?.data);
    if (backendError != null) {
      return ApiException(
        statusCode: response?.statusCode,
        code: backendError.code,
        message: backendError.message,
      );
    }

    switch (exception.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return const ApiException(
          code: 'request_timeout',
          message: 'The request timed out. Please try again.',
        );
      case DioExceptionType.connectionError:
      case DioExceptionType.badCertificate:
        return const ApiException(
          code: 'network_error',
          message: 'A network connection could not be established.',
        );
      case DioExceptionType.cancel:
        return const ApiException(
          code: 'request_cancelled',
          message: 'The request was cancelled.',
        );
      case DioExceptionType.transformTimeout:
      case DioExceptionType.badResponse:
      case DioExceptionType.unknown:
        return ApiException(
          statusCode: response?.statusCode,
          code: 'http_error',
          message: 'The request could not be completed.',
        );
    }
  }

  factory ApiException.malformedResponse() => const ApiException(
        code: 'malformed_response',
        message: 'The server returned an unexpected response.',
      );

  factory ApiException.secureStorageFailure() => const ApiException(
        code: 'secure_storage_error',
        message: 'Secure credentials could not be accessed.',
      );

  static ApiError? _tryReadBackendError(Object? data) {
    if (data is! Map) {
      return null;
    }
    final error = data['error'];
    if (error is! Map) {
      return null;
    }

    try {
      return ApiError.fromJson(Map<String, dynamic>.from(error));
    } on FormatException {
      return null;
    }
  }

  @override
  String toString() => 'ApiException(code: $code, statusCode: $statusCode)';
}
