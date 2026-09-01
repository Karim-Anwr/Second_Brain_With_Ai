import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';

import 'upload_controller.dart';
import 'upload_state.dart';

class UploadScreen extends StatefulWidget {
  const UploadScreen({
    super.key,
    required this.controller,
  });

  final UploadController controller;

  @override
  State<UploadScreen> createState() => _UploadScreenState();
}

class _UploadScreenState extends State<UploadScreen> {
  final _textTitleController = TextEditingController();
  final _textContentController = TextEditingController();
  final _linkController = TextEditingController();

  PlatformFile? _selectedFile;

  @override
  void initState() {
    super.initState();
    widget.controller.addListener(_onControllerChanged);
  }

  @override
  void dispose() {
    widget.controller.removeListener(_onControllerChanged);
    _textTitleController.dispose();
    _textContentController.dispose();
    _linkController.dispose();
    super.dispose();
  }

  void _onControllerChanged() {
    if (mounted) {
      setState(() {});
    }
  }

  Future<void> _pickFile() async {
    final file = await FilePicker.pickFile(
      type: FileType.custom,
      allowedExtensions: ['pdf', 'jpg', 'jpeg', 'png', 'webp'],
    );

    if (file == null || !mounted) {
      return;
    }

    setState(() {
      _selectedFile = file;
    });
  }

  Future<void> _uploadSelectedFile() async {
    final file = _selectedFile;

    if (file == null) {
      _showMessage('Please choose a file first.');
      return;
    }

    final path = file.path;

    if (path == null || path.isEmpty) {
      _showMessage('The selected file path is not available.');
      return;
    }

    await widget.controller.uploadFile(path);

    if (!mounted) return;

    if (widget.controller.state.status == UploadStatus.success) {
      setState(() {
        _selectedFile = null;
      });

      _showMessage('File uploaded successfully.');
    }
  }

  Future<void> _uploadText() async {
    final title = _textTitleController.text.trim();
    final text = _textContentController.text.trim();

    if (title.isEmpty || text.isEmpty) {
      _showMessage('Please enter a title and text.');
      return;
    }

    await widget.controller.uploadText(
      title: title,
      text: text,
    );

    if (!mounted) return;

    if (widget.controller.state.status == UploadStatus.success) {
      _textTitleController.clear();
      _textContentController.clear();
      _showMessage('Text uploaded successfully.');
    }
  }

  Future<void> _uploadLink() async {
    final url = _linkController.text.trim();

    if (url.isEmpty) {
      _showMessage('Please enter a link.');
      return;
    }

    await widget.controller.uploadLink(url);

    if (!mounted) return;

    if (widget.controller.state.status == UploadStatus.success) {
      _linkController.clear();
      _showMessage('Link uploaded successfully.');
    }
  }

  void _showMessage(String message) {
    ScaffoldMessenger.of(context)
      ..hideCurrentSnackBar()
      ..showSnackBar(
        SnackBar(content: Text(message)),
      );
  }

  String _fileTypeLabel(PlatformFile file) {
    final extension = file.extension;

    if (extension == null || extension.isEmpty) {
      return 'File';
    }

    return extension.toUpperCase();
  }

  @override
  Widget build(BuildContext context) {
    final state = widget.controller.state;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Upload'),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text(
                'Add to your memory',
                style: TextStyle(
                  fontSize: 24,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                'Upload files, text, or links to your Second Brain.',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
              const SizedBox(height: 24),

              _buildTextUpload(state),

              const SizedBox(height: 24),

              _buildLinkUpload(state),

              const SizedBox(height: 24),

              _buildFileUpload(state),

              if (state.status == UploadStatus.error) ...[
                const SizedBox(height: 20),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Text(
                      state.message ?? 'Upload failed.',
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTextUpload(UploadState state) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Text',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _textTitleController,
              enabled: !state.isUploading,
              decoration: const InputDecoration(
                labelText: 'Title',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _textContentController,
              enabled: !state.isUploading,
              minLines: 5,
              maxLines: 10,
              decoration: const InputDecoration(
                labelText: 'Text',
                alignLabelWithHint: true,
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: state.isUploading ? null : _uploadText,
              icon: const Icon(Icons.text_snippet_outlined),
              label: const Text('Upload Text'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildLinkUpload(UploadState state) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'Link',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _linkController,
              enabled: !state.isUploading,
              keyboardType: TextInputType.url,
              decoration: const InputDecoration(
                labelText: 'URL',
                hintText: 'https://example.com',
                border: OutlineInputBorder(),
                prefixIcon: Icon(Icons.link),
              ),
            ),
            const SizedBox(height: 12),
            FilledButton.icon(
              onPressed: state.isUploading ? null : _uploadLink,
              icon: const Icon(Icons.link),
              label: const Text('Upload Link'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFileUpload(UploadState state) {
    final file = _selectedFile;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Text(
              'File',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            const Text(
              'Supported files: PDF, JPG, JPEG, PNG, WEBP.',
            ),
            const SizedBox(height: 12),

            OutlinedButton.icon(
              onPressed: state.isUploading ? null : _pickFile,
              icon: const Icon(Icons.folder_open),
              label: Text(
                file == null ? 'Choose File' : 'Choose Another File',
              ),
            ),

            if (file != null) ...[
              const SizedBox(height: 12),
              Card(
                color: Theme.of(context).colorScheme.surfaceContainerHighest,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: Row(
                    children: [
                      const Icon(Icons.insert_drive_file_outlined),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              file.name,
                              maxLines: 2,
                              overflow: TextOverflow.ellipsis,
                              style: const TextStyle(
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              _fileTypeLabel(file),
                              style: Theme.of(context)
                                  .textTheme
                                  .bodySmall,
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        tooltip: 'Remove file',
                        onPressed: state.isUploading
                            ? null
                            : () {
                                setState(() {
                                  _selectedFile = null;
                                });
                              },
                        icon: const Icon(Icons.close),
                      ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed:
                    state.isUploading ? null : _uploadSelectedFile,
                icon: state.isUploading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                          strokeWidth: 2,
                        ),
                      )
                    : const Icon(Icons.cloud_upload_outlined),
                label: Text(
                  state.isUploading ? 'Uploading...' : 'Upload File',
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
