class MandatoryRow {
  MandatoryRow({
    required this.articleNo,
    required this.stdCode,
    required this.version,
    required this.mandatory,
    required this.text,
    required this.validFrom,
    required this.validTo,
    required this.kind,
    this.page,
  });

  final String articleNo;
  final String stdCode;
  final String version;
  final bool mandatory;
  final String text;
  final String validFrom;
  final String validTo;
  final String kind;
  final int? page;

  factory MandatoryRow.fromJson(Map<String, dynamic> j) {
    return MandatoryRow(
      articleNo: (j['article_no'] ?? '').toString(),
      stdCode: (j['std_code'] ?? '').toString(),
      version: (j['version'] ?? '').toString(),
      mandatory: j['mandatory'] == true || j['mandatory'] == 1,
      text: (j['text'] ?? '').toString(),
      validFrom: (j['valid_from'] ?? '').toString(),
      validTo: (j['valid_to'] ?? '').toString(),
      kind: (j['kind'] ?? '').toString(),
      page: j['page'] is int ? j['page'] as int : int.tryParse('${j['page'] ?? ''}'),
    );
  }

  Map<String, Object?> toMap() => {
        'article_no': articleNo,
        'std_code': stdCode,
        'version': version,
        'mandatory': mandatory ? 1 : 0,
        'text': text,
        'valid_from': validFrom,
        'valid_to': validTo,
        'kind': kind,
        'page': page,
      };
}
