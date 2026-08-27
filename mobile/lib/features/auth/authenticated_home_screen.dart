import 'package:flutter/material.dart';

import 'auth_controller.dart';
import '../search/search_controller.dart';
import '../search/search_screen.dart';

class AuthenticatedHomeScreen extends StatelessWidget {
  const AuthenticatedHomeScreen({
    super.key,
    required this.controller,
    required this.searchController,
  });

  final AuthController controller;
  final SearchController searchController;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Search'),
        actions: [
          IconButton(
            onPressed: controller.isLoading ? null : controller.logout,
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SearchScreen(controller: searchController),
    );
  }
}
