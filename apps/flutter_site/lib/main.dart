import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:sqflite_common_ffi/sqflite_ffi.dart';

import 'api.dart';
import 'app.dart';
import 'local_store.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  if (!kIsWeb && (Platform.isWindows || Platform.isLinux || Platform.isMacOS)) {
    sqfliteFfiInit();
    databaseFactory = databaseFactoryFfi;
  }
  const base = String.fromEnvironment(
    'GATEWAY',
    defaultValue: 'http://127.0.0.1:8000',
  );
  runApp(SpecGateSiteApp(store: LocalStore(), api: SpecGateApi(base: base)));
}
