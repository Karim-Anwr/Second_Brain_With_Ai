import 'package:dio/dio.dart';

import '../core/network/api_client.dart';
import '../models/memory_response.dart';

abstract interface class UploadRepositoryContract {
  Future<MemoryResponse> uploadFile(String filePath);

  Future<MemoryResponse> uploadText({
    required String title,
    required String text,
  });

  Future<MemoryResponse> uploadLink(String url);
}

class UploadRepository implements UploadRepositoryContract {
  UploadRepository(this._apiClient);

  final ApiClient _apiClient;

  @override
  Future<MemoryResponse> uploadFile(String filePath) async {
    final fileName = filePath.split(RegExp(r'[\\/]')).last;

    final formData = FormData.fromMap({
      'file': await MultipartFile.fromFile(filePath, filename: fileName),
    });

    final response = await _apiClient.post<Map<String, dynamic>>(
      '/upload',
      data: formData,
    );

    return MemoryResponse.fromJson(response.data!);
  }

  @override
  Future<MemoryResponse> uploadText({
    required String title,
    required String text,
  }) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/upload/text',
      data: {'title': title, 'text': text},
    );

    return MemoryResponse.fromJson(response.data!);
  }

  @override
  Future<MemoryResponse> uploadLink(String url) async {
    final response = await _apiClient.post<Map<String, dynamic>>(
      '/upload/link',
      data: {'url': url},
    );

    return MemoryResponse.fromJson(response.data!);
  }
}
