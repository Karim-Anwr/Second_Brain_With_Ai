import 'package:flutter/widgets.dart';

import 'app.dart';
import 'core/config/app_config.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  AppConfig.validate();
  runApp(const SecondBrainApp());
}
