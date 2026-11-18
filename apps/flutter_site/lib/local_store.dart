import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import 'models.dart';

class LocalStore {
  LocalStore();

  LocalStore.memory() : _memory = [];

  Database? _opened;
  List<MandatoryRow>? _memory;
  final List<Map<String, String>> _askCache = [];

  bool get isMemory => _memory != null;

  Future<Database> get _db async {
    if (_opened != null) return _opened!;
    final dir = await getApplicationDocumentsDirectory();
    _opened = await openDatabase(
      p.join(dir.path, 'specgate_offline.sqlite'),
      version: 1,
      onCreate: (db, _) async {
        await db.execute('''
CREATE TABLE mandatory (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  article_no TEXT,
  std_code TEXT,
  version TEXT,
  mandatory INTEGER,
  text TEXT,
  valid_from TEXT,
  valid_to TEXT,
  kind TEXT,
  page INTEGER
)''');
        await db.execute('''
CREATE TABLE ask_cache (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  query TEXT,
  project_id TEXT,
  answer TEXT,
  created_at TEXT
)''');
      },
    );
    return _opened!;
  }

  Future<void> replaceMandatory(List<MandatoryRow> rows) async {
    final mem = _memory;
    if (mem != null) {
      mem
        ..clear()
        ..addAll(rows);
      return;
    }
    final db = await _db;
    await db.transaction((txn) async {
      await txn.delete('mandatory');
      for (final row in rows) {
        await txn.insert('mandatory', row.toMap());
      }
    });
  }

  Future<int> countMandatory() async {
    final memCount = _memory;
    if (memCount != null) return memCount.length;
    final db = await _db;
    final r = await db.rawQuery('SELECT COUNT(*) c FROM mandatory');
    return (r.first['c'] as int?) ?? 0;
  }

  Future<MandatoryRow?> lookupArticle(String articleNo) async {
    final key = articleNo.trim();
    final memLookup = _memory;
    if (memLookup != null) {
      for (final row in memLookup) {
        if (row.articleNo == key) return row;
      }
      return null;
    }
    final db = await _db;
    final rows = await db.query(
      'mandatory',
      where: 'article_no = ?',
      whereArgs: [key],
      limit: 1,
    );
    if (rows.isEmpty) return null;
    return MandatoryRow.fromJson(rows.first);
  }

  Future<void> cacheAsk(String query, String projectId, String answer) async {
    if (_memory != null) {
      _askCache.add({'query': query, 'project_id': projectId, 'answer': answer});
      return;
    }
    final db = await _db;
    await db.insert('ask_cache', {
      'query': query,
      'project_id': projectId,
      'answer': answer,
      'created_at': DateTime.now().toIso8601String(),
    });
  }
}
