import 'package:flutter/material.dart';

import '../search/search_controller.dart';
import '../search/search_screen.dart';
import '../upload/upload_controller.dart';
import '../upload/upload_screen.dart';
import 'auth_controller.dart';

class AuthenticatedHomeScreen extends StatefulWidget {
  const AuthenticatedHomeScreen({
    super.key,
    required this.controller,
    required this.searchController,
    required this.uploadController,
  });

  final AuthController controller;
  final MemorySearchController searchController;
  final UploadController uploadController;

  @override
  State<AuthenticatedHomeScreen> createState() =>
      _AuthenticatedHomeScreenState();
}

class _AuthenticatedHomeScreenState
    extends State<AuthenticatedHomeScreen> {
  int _currentIndex = 0;

  @override
  Widget build(BuildContext context) {
    final screens = [
      SearchScreen(controller: widget.searchController),
      UploadScreen(controller: widget.uploadController),
    ];

    return Scaffold(
      appBar: AppBar(
        title: Text(_currentIndex == 0 ? 'Search' : 'Upload'),
        actions: [
          IconButton(
            onPressed:
                widget.controller.isLoading ? null : widget.controller.logout,
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: screens,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.search_outlined),
            selectedIcon: Icon(Icons.search),
            label: 'Search',
          ),
          NavigationDestination(
            icon: Icon(Icons.upload_file_outlined),
            selectedIcon: Icon(Icons.upload_file),
            label: 'Upload',
          ),
        ],
      ),
    );
  }
}
