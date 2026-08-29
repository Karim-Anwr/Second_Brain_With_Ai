import 'package:flutter/foundation.dart';

import '../../core/network/api_exception.dart';
import '../../repositories/upload_repository.dart';
import 'upload_state.dart';

class UploadController extends ChangeNotifier {
  UploadController({required UploadRepositoryContract repository})
    : _repository = repository;

  final UploadRepositoryContract _repository;

  UploadState _state = const UploadState.initial();

  UploadState get state => _state;

  Future<void> uploadFile(String filePath) async {
    if (_state.isUploading) {
      return;
    }

    _setState(const UploadState.uploading());

    try {
      final response = await _repository.uploadFile(filePath);

      _setState(UploadState.success(response));
    } on ApiException catch (error) {
      _setState(UploadState.error(_messageFor(error)));
    } catch (_) {
      _setState(
        const UploadState.error(
          'The file could not be uploaded. Please try again.',
        ),
      );
    }
  }

  Future<void> uploadText({required String title, required String text}) async {
    if (_state.isUploading) {
      return;
    }

    _setState(const UploadState.uploading());

    try {
      final response = await _repository.uploadText(title: title, text: text);

      _setState(UploadState.success(response));
    } on ApiException catch (error) {
      _setState(UploadState.error(_messageFor(error)));
    } catch (_) {
      _setState(
        const UploadState.error(
          'The text could not be uploaded. Please try again.',
        ),
      );
    }
  }

  Future<void> uploadLink(String url) async {
    if (_state.isUploading) {
      return;
    }

    _setState(const UploadState.uploading());

    try {
      final response = await _repository.uploadLink(url);

      _setState(UploadState.success(response));
    } on ApiException catch (error) {
      _setState(UploadState.error(_messageFor(error)));
    } catch (_) {
      _setState(
        const UploadState.error(
          'The link could not be uploaded. Please try again.',
        ),
      );
    }
  }

  void reset() {
    _setState(const UploadState.initial());
  }

  void _setState(UploadState state) {
    _state = state;
    notifyListeners();
  }

  String _messageFor(ApiException error) {
    switch (error.code) {
      case 'authentication_required':
      case 'authentication_failed':
        return 'Your session has expired. Please sign in again.';
      case 'network_error':
      case 'request_timeout':
        return 'A network connection could not be established. Please try again.';
      case 'upload_too_large':
        return 'The file is too large. Maximum size is 10 MB.';
      case 'unsupported_file_type':
        return 'This file type is not supported.';
      case 'validation_error':
        return 'Please check the submitted information and try again.';
      case 'ocr_failed':
        return 'Text could not be extracted from the uploaded file.';
      case 'dependency_unavailable':
        return 'A required processing service is temporarily unavailable.';
      case 'malformed_response':
        return 'The server returned an unexpected response.';
      default:
        return 'The upload could not be completed. Please try again.';
    }
  }
}
