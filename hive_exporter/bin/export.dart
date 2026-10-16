import 'dart:io';
import 'dart:convert';
import 'package:hive_ce/hive.dart';
import 'package:anime_tracker_exporter/history_module.dart';
import 'package:anime_tracker_exporter/bangumi_item.dart';
import 'package:anime_tracker_exporter/bangumi_tag.dart';

// Reuses the user's existing models and generated adapters. Only a private
// temporary copy is opened: Hive may compact/recover a file when it opens it.
Future<void> main(List<String> args) async {
  if (args.length != 2) {
    stderr.writeln('用法：dart run bin/export.dart 输入.hive 输出.json（请先退出 Kazumi）');
    exitCode = 64; return;
  }
  final input = File(args[0]);
  final output = File(args[1]);
  if (await output.exists()) {
    stderr.writeln('输出文件已存在，请选择新文件名。'); exitCode = 1; return;
  }
  final temp = await Directory.systemTemp.createTemp('anime_tracker_hive_');
  try {
    final before = await input.stat();
    final original = await input.readAsBytes();
    await File('${temp.path}/histories.hive').writeAsBytes(original);
    final after = await input.stat();
    if (before.modified != after.modified || before.size != after.size) {
      throw StateError('复制时源文件发生变化，请退出 Kazumi 后重试。');
    }
    Hive.init(temp.path);
    Hive.registerAdapter(BangumiItemAdapter());
    Hive.registerAdapter(HistoryAdapter());
    Hive.registerAdapter(ProgressAdapter());
    Hive.registerAdapter(BangumiTagAdapter());
    final box = await Hive.openBox<History>('histories', crashRecovery: false);
    final records = <Map<String,dynamic>>[];
    for (final key in box.keys) {
      final h = box.get(key)!;
      final b = h.bangumiItem;
      records.add({
        'hive_key': key, 'history_key': h.key, 'adapter_name': h.adapterName,
        'entry_kind': h.entryKind, 'last_watch_episode': h.lastWatchEpisode,
        'last_watch_time': h.lastWatchTime.toUtc().toIso8601String(),
        'last_watch_episode_name': h.lastWatchEpisodeName,
        'last_src': h.lastSrc, 'episode_page_url': h.episodePageUrl,
        'bangumi': {
          'id': b.id, 'type': b.type, 'name': b.name, 'name_cn': b.nameCn,
          'summary': b.summary, 'air_date': b.airDate, 'air_weekday': b.airWeekday,
          'rank': b.rank, 'images': b.images, 'tags': b.tags.map((t)=>t.toJson()).toList(),
          'aliases': b.alias, 'rating_score': b.ratingScore, 'votes': b.votes,
          'votes_count': b.votesCount, 'info': b.info,
        },
        'progresses': h.progresses.entries.map((e)=>{
          'key': e.key, 'episode': e.value.episode, 'road': e.value.road,
          'progress_ms': e.value.progress.inMilliseconds,
          'updated_at_ms': e.value.updatedAtMs,
        }).toList(),
      });
    }
    await box.close();
    final current = await input.readAsBytes();
    if (original.length != current.length ||
        !Iterable<int>.generate(original.length).every((i)=>original[i]==current[i])) {
      throw StateError('源文件已变化，未输出结果，请退出 Kazumi 后重试。');
    }
    await output.parent.create(recursive:true);
    await output.writeAsString(const JsonEncoder.withIndent('  ').convert({
      'format': 'kazumi-history-v1', 'exported_at': DateTime.now().toUtc().toIso8601String(),
      'source_filename': input.uri.pathSegments.last, 'history_count': records.length,
      'histories': records,
    }));
    stdout.writeln(jsonEncode({'records':records.length,'unique_history_keys':records.map((h)=>h['history_key']).toSet().length,'source_unchanged':true,'output':output.path}));
  } catch(e, st) {
    stderr.writeln('$e\n$st'); exitCode=1;
  } finally {
    await Hive.close();
    await temp.delete(recursive:true);
  }
}
