import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_exception.dart';
import 'package:mobile/features/upload/upload_controller.dart';
import 'package:mobile/features/upload/upload_state.dart';
import 'package:mobile/models/memory_response.dart';
import 'package:mobile/repositories/upload_repository.dart';

import 'dart:async';

void main() {
  group('UploadController', () {
    test('starts in the initial state', () {
      final controller = UploadController(repository: _FakeUploadRepository());

      expect(controller.state.status, UploadStatus.initial);
    });

    test('uploads a file successfully', () async {
      final repository = _FakeUploadRepository(response: _response());
      final controller = UploadController(repository: repository);
      final states = <UploadStatus>[];

      controller.addListener(() => states.add(controller.state.status));

      await controller.uploadFile('C:\\temp\\receipt.pdf');

      expect(repository.filePaths, ['C:\\temp\\receipt.pdf']);
      expect(states, [UploadStatus.uploading, UploadStatus.success]);
      expect(controller.state.response!.memoryId, 'mem_123');
    });

    test('uploads text successfully', () async {
      final repository = _FakeUploadRepository(response: _response());
      final controller = UploadController(repository: repository);

      await controller.uploadText(
        title: 'Laptop notes',
        text: 'My laptop purchase notes.',
      );

      expect(repository.textRequests, [
        'Laptop notes|My laptop purchase notes.',
      ]);
      expect(controller.state.status, UploadStatus.success);
    });

    test('uploads a link successfully', () async {
      final repository = _FakeUploadRepository(response: _response());
      final controller = UploadController(repository: repository);

      await controller.uploadLink('https://example.com/article');

      expect(repository.links, ['https://example.com/article']);
      expect(controller.state.status, UploadStatus.success);
    });

    test('maps API errors to safe user-facing states', () async {
      final controller = UploadController(
        repository: _FakeUploadRepository(
          error: const ApiException(code: 'network_error', message: 'offline'),
        ),
      );

      await controller.uploadFile('C:\\temp\\file.pdf');

      expect(controller.state.status, UploadStatus.error);
      expect(
        controller.state.message,
        'A network connection could not be established. Please try again.',
      );
    });

    test('prevents a second upload while already uploading', () async {
      final repository = _BlockingUploadRepository();
      final controller = UploadController(repository: repository);

      final firstUpload = controller.uploadFile('first.pdf');

      await Future<void>.delayed(Duration.zero);

      final secondUpload = controller.uploadFile('second.pdf');

      expect(repository.filePaths, ['first.pdf']);

      repository.complete();
      await firstUpload;
      await secondUpload;

      expect(repository.filePaths, ['first.pdf']);
    });

    test('reset returns to the initial state', () async {
      final controller = UploadController(
        repository: _FakeUploadRepository(response: _response()),
      );

      await controller.uploadFile('file.pdf');
      expect(controller.state.status, UploadStatus.success);

      controller.reset();

      expect(controller.state.status, UploadStatus.initial);
      expect(controller.state.response, isNull);
      expect(controller.state.message, isNull);
    });
  });
}

class _FakeUploadRepository implements UploadRepository {
  _FakeUploadRepository({this.response, this.error});

  final MemoryResponse? response;
  final Object? error;

  final List<String> filePaths = [];
  final List<String> textRequests = [];
  final List<String> links = [];

  @override
  Future<MemoryResponse> uploadFile(String filePath) async {
    filePaths.add(filePath);
    _throwIfNeeded();
    return response ?? _response();
  }

  @override
  Future<MemoryResponse> uploadText({
    required String title,
    required String text,
  }) async {
    textRequests.add('$title|$text');
    _throwIfNeeded();
    return response ?? _response();
  }

  @override
  Future<MemoryResponse> uploadLink(String url) async {
    links.add(url);
    _throwIfNeeded();
    return response ?? _response();
  }

  void _throwIfNeeded() {
    final failure = error;
    if (failure != null) {
      throw failure;
    }
  }
}

class _BlockingUploadRepository implements UploadRepositoryContract {
  final List<String> filePaths = [];

  Completer<MemoryResponse>? _completer;

  @override
  Future<MemoryResponse> uploadFile(String filePath) {
    filePaths.add(filePath);
    _completer = Completer<MemoryResponse>();
    return _completer!.future;
  }

  @override
  Future<MemoryResponse> uploadText({
    required String title,
    required String text,
  }) async {
    throw UnimplementedError();
  }

  @override
  Future<MemoryResponse> uploadLink(String url) async {
    throw UnimplementedError();
  }

  void complete() {
    _completer?.complete(_response());
  }
}

class _Completer<T> {
  final Future<T> future = Future<T>(() async {
    while (!_completed) {
      await Future<void>.delayed(const Duration(milliseconds: 1));
    }
    return _value as T;
  });

  static bool _completed = false;
  static Object? _value;

  void complete([T? value]) {
    _value = value;
    _completed = true;
  }
}

MemoryResponse _response() {
  return const MemoryResponse(
    memoryId: 'mem_123',
    fileName: 'receipt.pdf',
    fileType: MemoryFileType.pdf,
    summary: 'Laptop receipt',
    tags: ['shopping'],
    category: MemoryCategory.technology,
    importance: 0.9,
    totalChunks: 2,
    status: 'success',
  );
}
