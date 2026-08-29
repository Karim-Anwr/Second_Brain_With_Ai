import '../../models/memory_response.dart';

enum UploadStatus { initial, uploading, success, error }

class UploadState {
  const UploadState({required this.status, this.response, this.message});

  const UploadState.initial() : this(status: UploadStatus.initial);

  const UploadState.uploading() : this(status: UploadStatus.uploading);

  const UploadState.success(MemoryResponse response)
    : this(status: UploadStatus.success, response: response);

  const UploadState.error(String message)
    : this(status: UploadStatus.error, message: message);

  final UploadStatus status;
  final MemoryResponse? response;
  final String? message;

  bool get isUploading => status == UploadStatus.uploading;
}
