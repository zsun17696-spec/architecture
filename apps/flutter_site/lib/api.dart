import 'dart:convert';

import 'package:http/http.dart' as http;

import 'models.dart';

class SpecGateApi {
  SpecGateApi({required this.base, http.Client? httpClient})
      : _http = httpClient ?? http.Client();

  final String base;
  final http.Client _http;

  Future<List<MandatoryRow>> syncMandatory() async {
    final res = await _http.get(Uri.parse('$base/v1/sync/mandatory'));
    if (res.statusCode != 200) {
      throw Exception('sync ${res.statusCode}');
    }
    final list = jsonDecode(utf8.decode(res.bodyBytes)) as List<dynamic>;
    return list
        .map((e) => MandatoryRow.fromJson(Map<String, dynamic>.from(e as Map)))
        .toList();
  }

  Future<Map<String, dynamic>> ask({
    required String query,
    required String projectId,
  }) async {
    final res = await _http.post(
      Uri.parse('$base/v1/ask'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'query': query,
        'project_id': projectId,
        'client': 'flutter',
      }),
    );
    if (res.statusCode != 200) {
      throw Exception('ask ${res.statusCode} ${res.body}');
    }
    return Map<String, dynamic>.from(jsonDecode(utf8.decode(res.bodyBytes)) as Map);
  }
}
