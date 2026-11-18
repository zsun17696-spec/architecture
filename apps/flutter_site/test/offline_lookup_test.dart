import 'package:flutter_test/flutter_test.dart';

import 'package:flutter_site/api.dart';
import 'package:flutter_site/app.dart';
import 'package:flutter_site/header.dart';
import 'package:flutter_site/local_store.dart';
import 'package:flutter_site/models.dart';

void main() {
  LocalStore seeded() {
    final store = LocalStore.memory();
    return store;
  }

  testWidgets('empty store asks to sync first', (tester) async {
    await tester.pumpWidget(
      SpecGateSiteApp(
        store: LocalStore.memory(),
        api: SpecGateApi(base: 'http://127.0.0.1:9'),
      ),
    );
    await tester.tap(find.text('离线查询'));
    await tester.pumpAndSettle();
    expect(find.text('请先在线同步'), findsOneWidget);
  });

  testWidgets('offline 8.5.1 shows header and 743 pointer, not fabricated body', (
    tester,
  ) async {
    final store = seeded();
    await store.replaceMandatory([
      MandatoryRow(
        articleNo: '8.5.1',
        stdCode: 'GB 50010',
        version: '2010',
        mandatory: true,
        text:
            '8.5 纵向受力钢筋的最小配筋率；GB 50010-2010 第8.5.1条为强制性条文，自 2022-04-01 起废止，由 GB 55008-2021 承担。来源：住建部公告第743号。',
        validFrom: '2011-07-01',
        validTo: '2099-12-31',
        kind: 'pointer',
      ),
    ]);
    await tester.pumpWidget(
      SpecGateSiteApp(
        store: store,
        api: SpecGateApi(base: 'http://127.0.0.1:9'),
      ),
    );
    await tester.tap(find.text('离线查询'));
    await tester.pumpAndSettle();
    expect(find.text(kMandatoryHeader), findsOneWidget);
    expect(find.textContaining('住建部公告第743号'), findsWidgets);
    expect(find.textContaining('8.5 纵向受力钢筋的最小配筋率'), findsOneWidget);
    expect(find.textContaining('条款正文'), findsNothing);
  });
}
