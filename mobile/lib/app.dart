import 'package:flutter/material.dart';

import 'core/network/api_client.dart';
import 'core/storage/token_storage.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_gate.dart';
import 'repositories/auth_repository.dart';
import 'features/search/search_controller.dart';
import 'repositories/search_repository.dart';

class SecondBrainApp extends StatefulWidget {
  const SecondBrainApp({
    super.key,
    this.controller,
    this.searchController,
  });

  final AuthController? controller;
  final MemorySearchController? searchController;

  @override
  State<SecondBrainApp> createState() => _SecondBrainAppState();
}

class _SecondBrainAppState extends State<SecondBrainApp> {
  late final AuthController _controller;
  late final MemorySearchController _searchController;
  late final bool _ownsController;
  late final bool _ownsSearchController;

  @override
  void initState() {
    super.initState();
    _ownsController = widget.controller == null;
    _ownsSearchController = widget.searchController == null;
    if (widget.controller == null) {
      final dependencies = _createDependencies();
      _controller = dependencies.authController;
      _searchController = widget.searchController ?? dependencies.searchController;
    } else if (widget.searchController != null) {
      _controller = widget.controller!;
      _searchController = widget.searchController!;
    } else {
      _controller = widget.controller!;
      _searchController = _createSearchController(_controller);
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
    super.dispose();
  }

  _AppDependencies _createDependencies() {
    final tokenStorage = SecureTokenStorage();
    late final AuthController controller;
    final apiClient = ApiClient(
      tokenStorage: tokenStorage,
      onSessionExpired: () => controller.handleSessionExpired(),
    );
    final repository = AuthRepository(
      apiClient: apiClient,
      tokenStorage: tokenStorage,
    );
    controller = AuthController(repository: repository);
    return _AppDependencies(
      authController: controller,
      searchController: _searchControllerFor(apiClient),
    );
  }

  MemorySearchController _createSearchController(AuthController controller) {
    final tokenStorage = SecureTokenStorage();
    final apiClient = ApiClient(
      tokenStorage: tokenStorage,
      onSessionExpired: controller.handleSessionExpired,
    );
    return _searchControllerFor(apiClient);
  }

  MemorySearchController _searchControllerFor(ApiClient apiClient) {
    return MemorySearchController(repository: ApiSearchRepository(apiClient: apiClient));
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SecondBrain',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF315D9B)),
        useMaterial3: true,
      ),
      home: AuthGate(
        controller: _controller,
        searchController: _searchController,
      ),
    );
  }
}

class _AppDependencies {
  const _AppDependencies({
    required this.authController,
    required this.searchController,
  });

  final AuthController authController;
  final MemorySearchController searchController;
}
