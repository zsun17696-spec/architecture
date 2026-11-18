import 'package:flutter/material.dart';

import 'api.dart';
import 'header.dart';
import 'local_store.dart';
import 'models.dart';

class SpecGateSiteApp extends StatelessWidget {
  const SpecGateSiteApp({
    super.key,
    required this.store,
    required this.api,
  });

  final LocalStore store;
  final SpecGateApi api;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: '矩典工地速查',
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFFC9A227),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      home: SiteHome(store: store, api: api),
    );
  }
}

class SiteHome extends StatefulWidget {
  const SiteHome({super.key, required this.store, required this.api});

  final LocalStore store;
  final SpecGateApi api;

  @override
  State<SiteHome> createState() => _SiteHomeState();
}

class _SiteHomeState extends State<SiteHome> {
  final _article = TextEditingController(text: '8.5.1');
  final _ask = TextEditingController(text: '纵向受力钢筋最小配筋率的强制性条文是哪一条');
  bool _flight = false;
  bool _busy = false;
  String _status = '未同步';
  String _result = '';
  bool _showHeader = false;

  @override
  void dispose() {
    _article.dispose();
    _ask.dispose();
    super.dispose();
  }

  Future<void> _sync() async {
    if (_flight) {
      setState(() => _result = '飞行模式：无法同步，请先在线同步');
      return;
    }
    setState(() => _busy = true);
    try {
      final rows = await widget.api.syncMandatory();
      await widget.store.replaceMandatory(rows);
      final n = await widget.store.countMandatory();
      setState(() {
        _status = '已同步 $n 条';
        _result = '离线包已写入本地 SQLite（指针 + 已 sync 的 55008 页）。';
      });
    } catch (e) {
      setState(() => _result = '同步失败：$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  Future<void> _lookup() async {
    setState(() {
      _busy = true;
      _showHeader = false;
      _result = '';
    });
    try {
      final n = await widget.store.countMandatory();
      if (n == 0) {
        setState(() => _result = '请先在线同步');
        return;
      }
      final row = await widget.store.lookupArticle(_article.text);
      if (row == null) {
        setState(() => _result = '本地没有条文号 ${_article.text.trim()}');
        return;
      }
      setState(() {
        _showHeader = row.mandatory;
        _result = _formatRow(row);
      });
    } finally {
      setState(() => _busy = false);
    }
  }

  String _formatRow(MandatoryRow row) {
    final buf = StringBuffer()
      ..writeln('${row.stdCode}-${row.version} 第${row.articleNo}条')
      ..writeln(row.text);
    if (buf.toString().contains('条款正文')) {
      return '拒绝展示编造正文。';
    }
    return buf.toString();
  }

  Future<void> _onlineAsk() async {
    if (_flight) {
      setState(() => _result = '飞行模式：在线问答已关闭，请用条文号离线查询');
      return;
    }
    setState(() {
      _busy = true;
      _showHeader = false;
    });
    try {
      final data = await widget.api.ask(
        query: _ask.text,
        projectId: 'P-2018',
      );
      final answer = (data['answer'] ?? '').toString();
      await widget.store.cacheAsk(_ask.text, 'P-2018', answer);
      setState(() {
        _showHeader = data['mandatory_hit'] == true;
        _result = answer;
      });
    } catch (e) {
      setState(() => _result = '在线问答失败：$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('矩典 · 工地离线速查'),
        actions: [
          Row(
            children: [
              const Text('飞行模式'),
              Switch(
                value: _flight,
                onChanged: (v) => setState(() => _flight = v),
              ),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('client=flutter · $_status', style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 8),
          FilledButton(
            onPressed: _busy ? null : _sync,
            child: const Text('同步 GET /v1/sync/mandatory'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _article,
            decoration: const InputDecoration(
              labelText: '条文号（离线）',
              hintText: '8.5.1',
            ),
          ),
          const SizedBox(height: 8),
          FilledButton.tonal(
            onPressed: _busy ? null : _lookup,
            child: const Text('离线查询'),
          ),
          const SizedBox(height: 16),
          TextField(
            controller: _ask,
            maxLines: 2,
            decoration: const InputDecoration(labelText: '在线问答（同一 /v1/ask）'),
          ),
          const SizedBox(height: 8),
          OutlinedButton(
            onPressed: _busy ? null : _onlineAsk,
            child: const Text('在线提问 client=flutter'),
          ),
          const SizedBox(height: 20),
          if (_showHeader)
            Text(
              kMandatoryHeader,
              style: TextStyle(
                color: Theme.of(context).colorScheme.error,
                fontWeight: FontWeight.w700,
                fontSize: 18,
              ),
            ),
          SelectableText(_result),
        ],
      ),
    );
  }
}
