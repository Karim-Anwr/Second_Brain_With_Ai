import 'package:flutter/material.dart';

import '../../models/search_response.dart';
import 'search_controller.dart';
import 'search_state.dart';

class SearchScreen extends StatefulWidget {
  const SearchScreen({super.key, required this.controller});

  final SearchController controller;

  @override
  State<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends State<SearchScreen> {
  final _queryController = TextEditingController();

  @override
  void dispose() {
    _queryController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    await widget.controller.search(_queryController.text);
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final state = widget.controller.state;
        return Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(20, 20, 20, 12),
              child: TextField(
                controller: _queryController,
                enabled: !state.isLoading,
                textInputAction: TextInputAction.search,
                onSubmitted: (_) => _submit(),
                decoration: InputDecoration(
                  labelText: 'Search your memories',
                  hintText: 'Ask about anything you saved',
                  prefixIcon: const Icon(Icons.search),
                  suffixIcon: IconButton(
                    tooltip: 'Search',
                    onPressed: state.isLoading ? null : _submit,
                    icon: const Icon(Icons.arrow_forward),
                  ),
                  border: const OutlineInputBorder(),
                ),
              ),
            ),
            Expanded(child: _SearchContent(controller: widget.controller, state: state)),
          ],
        );
      },
    );
  }
}

class _SearchContent extends StatelessWidget {
  const _SearchContent({required this.controller, required this.state});

  final SearchController controller;
  final SearchState state;

  @override
  Widget build(BuildContext context) {
    switch (state.status) {
      case SearchStatus.initial:
        return const _SearchMessage(
          icon: Icons.manage_search_outlined,
          title: 'Search your memory',
          message: 'Enter a question to find relevant saved knowledge.',
        );
      case SearchStatus.loading:
        return const Center(child: CircularProgressIndicator());
      case SearchStatus.empty:
        return _SearchMessage(
          icon: Icons.search_off_outlined,
          title: 'No memories found',
          message: 'Try different wording or a broader question.',
          action: FilledButton.tonal(
            onPressed: controller.retry,
            child: const Text('Retry search'),
          ),
        );
      case SearchStatus.error:
        return _SearchMessage(
          icon: Icons.error_outline,
          title: 'Search unavailable',
          message: state.message ?? 'Search could not be completed. Please try again.',
          action: FilledButton.tonal(
            onPressed: controller.retry,
            child: const Text('Retry search'),
          ),
        );
      case SearchStatus.success:
        final response = state.response!;
        return ListView(
          padding: const EdgeInsets.fromLTRB(20, 4, 20, 24),
          children: [
            if (response.llmAnswer case final answer? when answer.trim().isNotEmpty) ...[
              _AnswerCard(answer: answer),
              const SizedBox(height: 16),
            ],
            Text(
              '${response.total} ${response.total == 1 ? 'result' : 'results'}',
              style: Theme.of(context).textTheme.labelLarge,
            ),
            const SizedBox(height: 8),
            ...response.results.map(
              (result) => Padding(
                padding: const EdgeInsets.only(bottom: 12),
                child: _SearchResultCard(result: result),
              ),
            ),
          ],
        );
    }
  }
}

class _SearchMessage extends StatelessWidget {
  const _SearchMessage({
    required this.icon,
    required this.title,
    required this.message,
    this.action,
  });

  final IconData icon;
  final String title;
  final String message;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(icon, size: 48, color: Theme.of(context).colorScheme.primary),
            const SizedBox(height: 16),
            Text(title, style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center),
            if (action != null) ...[
              const SizedBox(height: 20),
              action!,
            ],
          ],
        ),
      ),
    );
  }
}

class _AnswerCard extends StatelessWidget {
  const _AnswerCard({required this.answer});

  final String answer;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Answer', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(answer),
          ],
        ),
      ),
    );
  }
}

class _SearchResultCard extends StatelessWidget {
  const _SearchResultCard({required this.result});

  final SearchResult result;

  @override
  Widget build(BuildContext context) {
    final relevance = (result.scores.finalScore * 100).clamp(0, 100).round();
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(result.fileName, style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(result.summary),
            if (result.matchedText.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(result.matchedText, maxLines: 3, overflow: TextOverflow.ellipsis),
            ],
            const SizedBox(height: 12),
            Text('Relevance $relevance% · ${result.createdAt}', style: Theme.of(context).textTheme.bodySmall),
            if (result.tags.isNotEmpty) ...[
              const SizedBox(height: 12),
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: result.tags
                    .map((tag) => Chip(label: Text(tag), visualDensity: VisualDensity.compact))
                    .toList(growable: false),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
