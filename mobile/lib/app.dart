import 'package:flutter/material.dart';

import 'core/network/api_client.dart';
import 'core/storage/token_storage.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_gate.dart';
import 'features/search/search_controller.dart';
import 'features/upload/upload_controller.dart';
import 'repositories/auth_repository.dart';
import 'repositories/search_repository.dart';
import 'repositories/upload_repository.dart';

class SecondBrainApp extends StatefulWidget {
  const SecondBrainApp({
    super.key,
    this.controller,
    this.searchController,
    this.uploadController,
  });

  final AuthController? controller;
  final MemorySearchController? searchController;
  final UploadController? uploadController;

  @override
  State<SecondBrainApp> createState() => _SecondBrainAppState();
}

class _SecondBrainAppState extends State<SecondBrainApp> {
  late final AuthController _controller;
  late final MemorySearchController _searchController;
  late final UploadController _uploadController;

  late final bool _ownsController;
  late final bool _ownsSearchController;
  late final bool _ownsUploadController;

  @override
  void initState() {
    super.initState();

    _ownsController = widget.controller == null;
    _ownsSearchController = widget.searchController == null;
    _ownsUploadController = widget.uploadController == null;

    /*
     * If all dependencies are injected, use them directly.
     *
     * This is important for widget tests because tests should not
     * construct a real ApiClient and therefore should not require
     * API_BASE_URL.
     */
    if (widget.controller != null &&
        widget.searchController != null &&
        widget.uploadController != null) {
      _controller = widget.controller!;
      _searchController = widget.searchController!;
      _uploadController = widget.uploadController!;
    } else if (widget.controller == null) {
      /*
       * Normal application startup.
       *
       * Create the complete dependency graph once so Auth,
       * Search, and Upload share the same ApiClient/token storage.
       */
      final dependencies = _createDependencies();

      _controller = dependencies.authController;
      _searchController = dependencies.searchController;
      _uploadController = dependencies.uploadController;
    } else {
      /*
       * Partial dependency injection.
       *
       * AuthController was injected, but one or both feature
       * controllers were not. In this case create only the missing
       * feature dependencies.
       */
      _controller = widget.controller!;

      final dependencies = _createFeatureDependencies(_controller);

      _searchController =
          widget.searchController ?? dependencies.searchController;

      _uploadController =
          widget.uploadController ?? dependencies.uploadController;
    }

    _controller.restoreSession();
  }

  @override
  void dispose() {
    if (_ownsController) {
      _controller.dispose();
    }

    if (_ownsSearchController) {
      _searchController.dispose();
    }

    if (_ownsUploadController) {
      _uploadController.dispose();
    }

    super.dispose();
  }

  _AppDependencies _createDependencies() {
    final tokenStorage = SecureTokenStorage();

    late final AuthController controller;

    final apiClient = ApiClient(
      tokenStorage: tokenStorage,
      onSessionExpired: () => controller.handleSessionExpired(),
    );

    final authRepository = AuthRepository(
      apiClient: apiClient,
      tokenStorage: tokenStorage,
    );

    controller = AuthController(repository: authRepository);

    return _AppDependencies(
      authController: controller,
      searchController: MemorySearchController(
        repository: ApiSearchRepository(apiClient: apiClient),
      ),
      uploadController: UploadController(
        repository: UploadRepository(apiClient),
      ),
    );
  }

  _FeatureDependencies _createFeatureDependencies(
    AuthController controller,
  ) {
    final tokenStorage = SecureTokenStorage();

    final apiClient = ApiClient(
      tokenStorage: tokenStorage,
      onSessionExpired: controller.handleSessionExpired,
    );

    return _FeatureDependencies(
      searchController: MemorySearchController(
        repository: ApiSearchRepository(apiClient: apiClient),
      ),
      uploadController: UploadController(
        repository: UploadRepository(apiClient),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SecondBrain',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF315D9B),
        ),
        useMaterial3: true,
      ),
      home: AuthGate(
        controller: _controller,
        searchController: _searchController,
        uploadController: _uploadController,
      ),
    );
  }
}

class _AppDependencies {
  const _AppDependencies({
    required this.authController,
    required this.searchController,
    required this.uploadController,
  });

  final AuthController authController;
  final MemorySearchController searchController;
  final UploadController uploadController;
}

class _FeatureDependencies {
  const _FeatureDependencies({
    required this.searchController,
    required this.uploadController,
  });

  final MemorySearchController searchController;
  final UploadController uploadController;
}