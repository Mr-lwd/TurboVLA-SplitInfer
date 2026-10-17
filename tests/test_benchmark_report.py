import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.libero.benchmark_common import summarize
from scripts.libero.build_benchmark_report import add_run, common_success_group, group_rows, import_run, latest_catalog, replace_block, table
from scripts.libero.plot_stage_timings import latency_breakdown


class BenchmarkReportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.directory = Path(temp.name) / 'measured_run'
        self.directory.mkdir()
        self.metadata = {'status': 'completed', 'device_name': 'orin', 'exclude_first_calls_per_episode': 1,
                         'remote_server': {'runtime': {'python_executable': '/private/python', 'torch': '2.5'}},
                         'config': {'remote_policy_url': '', 'chunk_size': 12, 'ckpt_path': '/private/model.pth'}}
        episodes = [{'episode': i, 'success': i == 0, 'executed_steps': 13, 'rollout_wall_time_s': 2.,
                     'inference_timings': [{'step': 0, 'duration_s': first}, {'step': 12, 'duration_s': last}]}
                    for i, (first, last) in enumerate(((.6, .2), (1., .4)))]
        self.result = {'policy_backend': 'local', 'chunk_size': 12, 'num_open_loop_steps': 12,
                       'total_episodes': 2, 'total_successes': 1, 'overall_success_rate': .5, 'timing_scope': 'rollout',
                       'tasks': [{'task_id': 0, 'task_description': 'test', 'episode_results': episodes}]}
        self.saved, _ = summarize(self.result, 1)
        self.write('_metadata', self.metadata)
        self.write('', self.result)
        self.write('_summary', self.saved)

    def write(self, suffix, data):
        (self.directory / f'measured_run{suffix}.json').write_text(json.dumps(data))

    def test_filter_is_per_episode_and_missing_metrics_stay_missing(self):
        run = import_run(self.directory)
        metrics = run['records'][0]['metrics']
        self.assertEqual(metrics['filtered_calls']['count'], 2)
        self.assertAlmostEqual(metrics['filtered_calls']['mean_ms'], 300)
        self.assertAlmostEqual(metrics['filtered_calls']['p95_ms'], 390)
        self.assertIsNone(metrics['control_intervals'])
        self.assertIsNone(metrics['hold_steps'])
        self.assertIn('—', table([(run, run['records'][0])]))
        self.assertNotIn('/private', json.dumps(run))
        self.assertEqual(len(run['source_files']), 3)
        self.assertTrue(all(len(s['sha256']) == 64 for s in run['source_files']))

    def test_failed_or_inconsistent_run_is_rejected(self):
        self.metadata['status'] = 'failed'
        self.write('_metadata', self.metadata)
        with self.assertRaisesRegex(ValueError, 'completed'):
            import_run(self.directory)
        self.metadata['status'] = 'completed'
        self.write('_metadata', self.metadata)
        self.saved['filtered_calls']['mean_ms'] = 999
        self.write('_summary', self.saved)
        with self.assertRaisesRegex(ValueError, 'disagrees'):
            import_run(self.directory)

    def test_new_local_step_timings_reach_published_report(self):
        for episode in self.result['tasks'][0]['episode_results']:
            episode['step_timings'] = [
                {'step': i, 'action_start_s': .6 + i * .1, 'action_end_s': .65 + i * .1,
                 'env_step_s': .05, 'hold': False} for i in range(episode['executed_steps'])]
        summary, _ = summarize(self.result, 1)
        self.write('', self.result)
        self.write('_summary', summary)
        run = import_run(self.directory)
        record = run['records'][0]
        self.assertEqual(record['metrics']['control_intervals']['count'], 24)
        self.assertAlmostEqual(record['metrics']['control_intervals']['p95_ms'], 100)
        self.assertEqual(record['metrics']['hold_steps'], 0)
        self.assertEqual(record['episodes'][0]['hold_steps'], 0)
        self.assertIn('100.00', table([(run, record)]))

    def test_append_is_idempotent_and_preserves_history(self):
        run = import_run(self.directory)
        catalog = {'groups': [], 'runs': []}
        add_run(catalog, run, 'round-1')
        add_run(catalog, copy.deepcopy(run), 'round-1')
        self.assertEqual(len(catalog['runs']), 1)
        self.assertEqual(catalog['groups'][0]['run_ids'], ['measured_run'])
        later = copy.deepcopy(run); later['id'] = 'later_run'
        add_run(catalog, later, 'round-2')
        self.assertEqual(catalog['featured_group'], 'round-1')
        self.assertEqual(len(catalog['groups']), 2)
        changed = copy.deepcopy(run); changed['source_files'][0]['sha256'] = '0'*64
        with self.assertRaisesRegex(ValueError, 'different data'):
            add_run(catalog, changed, 'round-1')

    def test_readme_generation_preserves_manual_content(self):
        self.assertEqual(replace_block('before<S>old<E>after', '<S>', '<E>', 'new'),
                         'before<S>\n\nnew\n\n<E>after')
        with self.assertRaises(ValueError):
            replace_block('no markers', '<S>', '<E>', 'new')

    def test_publication_contains_only_current_comparison_without_mutating_sources(self):
        run = import_run(self.directory)
        run['config']['task_suite_name'] = 'libero_spatial'
        catalog = {'schema_version': 1, 'groups': [], 'runs': []}
        add_run(catalog, run, 'old-round')
        current = copy.deepcopy(run)
        current['id'] = 'current-run'
        add_run(catalog, current, 'current-round', 'LIBERO Spatial · 2026-10-17')
        catalog['featured_group'] = 'current-round'
        catalog['groups'][1]['notes'] = ['2026-10-16 数据，历史分组保留。', '原始组说明：BF16、seed 7。']
        original = copy.deepcopy(catalog)
        published = latest_catalog(catalog)
        self.assertEqual([group['id'] for group in published['groups']], ['current-round'])
        self.assertEqual([item['id'] for item in published['runs']], ['current-run'])
        self.assertEqual(published['runs'][0]['records'], current['records'])
        self.assertEqual(published['groups'][0]['notes'], ['BF16、seed 7。'])
        self.assertNotIn('2026', published['groups'][0]['title'])
        published['runs'][0]['records'][0]['metrics']['successes'] = 999
        self.assertEqual(catalog, original)

    def test_publication_rejects_missing_current_selection(self):
        with self.assertRaisesRegex(ValueError, 'featured_group'):
            latest_catalog({'schema_version': 1, 'groups': [], 'runs': [], 'featured_group': 'missing'})


class CommonSuccessTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.catalog = {'groups': [], 'runs': []}
        for name, failure in [('orin', 2), ('thor', 3)]:
            directory = self.root / name
            directory.mkdir()
            metadata = {'status': 'completed', 'device_name': name,
                        'exclude_first_calls_per_episode': 1,
                        'config': {'task_suite_name': 'libero_spatial', 'seed': 7, 'chunk_size': 12}}
            tasks = []
            for task_id, durations in enumerate(([10., .2], [20., .3, .4], [30., 4.], [40., 5.])):
                episode = {'episode': 0, 'success': task_id != failure,
                           'executed_steps': 3, 'rollout_wall_time_s': 2. if task_id < 2 else 100.,
                           'inference_timings': [{'step': i, 'duration_s': d} for i, d in enumerate(durations)],
                           'step_timings': [{'step': i, 'action_start_s': i * .1, 'action_end_s': i * .1 + .05,
                                             'env_step_s': .05, 'hold': False} for i in range(3)]}
                tasks.append({'task_id': task_id, 'task_description': 'test', 'episode_results': [episode]})
            result = {'policy_backend': 'local', 'chunk_size': 12, 'num_open_loop_steps': 12,
                      'total_episodes': 4, 'total_successes': 3, 'overall_success_rate': .75,
                      'timing_scope': 'rollout', 'tasks': tasks}
            for suffix, data in [('_metadata', metadata), ('', result), ('_summary', summarize(result, 1)[0])]:
                (directory / f'{name}{suffix}.json').write_text(json.dumps(data))
            add_run(self.catalog, import_run(directory), 'full')

    def test_intersection_recomputes_pooled_metrics_and_preserves_originals(self):
        original = copy.deepcopy(self.catalog)
        group = common_success_group(self.catalog, 'full', 'matched', self.root)
        self.assertEqual(group['selection']['retained'], [{'task_id': i, 'episode': 0} for i in [0, 1]])
        self.assertEqual(group['selection']['excluded'], [{'task_id': i, 'episode': 0} for i in [2, 3]])
        self.assertEqual(self.catalog, original)
        # A successful episode in one run must still be removed if another run failed it.
        for run, record in group_rows(self.catalog, group):
            self.assertEqual([e['task_id'] for e in record['episodes']], [0, 1])
            metrics = record['metrics']
            self.assertEqual(metrics['episodes'], 2)
            self.assertEqual(metrics['rollout_wall_time_s'], 4.)
            self.assertEqual(metrics['all_calls']['count'], 5)
            self.assertEqual(metrics['filtered_calls']['count'], 3)
            self.assertAlmostEqual(metrics['filtered_calls']['mean_ms'], 300.)
            self.assertAlmostEqual(metrics['filtered_calls']['p95_ms'], 390.)
            self.assertEqual(metrics['control_intervals']['count'], 4)
            self.assertEqual(metrics['first_call_per_episode']['count'], 2)
            self.assertEqual(run['records'][0]['metrics']['episodes'], 4)
        rendered = table(group_rows(self.catalog, group), matched=True)
        self.assertIn('共同成功案例数', rendered)
        self.assertNotIn('2/2', rendered)
        # Publication needs only portable catalog data, not raw output directories.
        self.catalog['groups'].append(group)
        portable = json.loads(json.dumps(self.catalog))
        self.assertEqual(group_rows(portable, portable['groups'][-1]), group_rows(self.catalog, group))

    def test_changed_source_is_rejected(self):
        path = self.root / 'orin/orin.json'
        path.write_text(path.read_text() + ' ')
        with self.assertRaisesRegex(ValueError, 'Source data changed'):
            common_success_group(self.catalog, 'full', 'matched', self.root)

    def test_remote_modes_filter_stages_and_control_samples_together(self):
        from scripts.libero.benchmark_async import summarize_episodes
        directory = self.root / 'remote'
        directory.mkdir()
        metadata = {'status': 'completed', 'device_name': 'orin', 'exclude_first_calls_per_episode': 1,
                    'experiment': {'modes': ['sync', 'replace', 'blend']},
                    'config': {'task_suite_name': 'libero_spatial', 'seed': 7, 'remote_policy_url': 'http://example'}}
        (directory / 'remote_metadata.json').write_text(json.dumps(metadata))
        local = json.loads((self.root / 'orin/orin.json').read_text())
        for mode in metadata['experiment']['modes']:
            episodes = []
            for task in copy.deepcopy(local['tasks']):
                e = task['episode_results'][0]
                e.update(task_id=task['task_id'], instruction='test', success=True,
                         blocking_waits=[], drain_wall_time_s=.01)
                for c in e['inference_timings']:
                    c.update(start_s=c['step'], end_s=c['step']+c['duration_s'],
                             policy_duration_s=c['duration_s'], expired=False, applied=True,
                             reason='applied', discarded_prefix_actions=0, blended_steps=0,
                             remote={'server_inference_s': c['duration_s'] / 2})
                for step in e['step_timings']:
                    step.update(control_lateness_s=0., oldest_observation_age_steps=0,
                                arm_action_change_l2=None, gripper_changed=False)
                episodes.append(e)
            (directory / f'remote_{mode}.json').write_text(json.dumps({'mode': mode, 'episodes': episodes}))
            (directory / f'remote_{mode}_summary.json').write_text(json.dumps(summarize_episodes(episodes, 1)))
        add_run(self.catalog, import_run(directory), 'full')
        group = common_success_group(self.catalog, 'full', 'matched', self.root)
        remote_rows = [(run, record) for run, record in group_rows(self.catalog, group) if run['kind'] == 'remote']
        self.assertEqual(len(remote_rows), 3)
        for _, record in remote_rows:
            metrics = record['metrics']
            self.assertEqual(metrics['episodes'], 2)
            self.assertEqual(metrics['control_intervals']['count'], 4)
            self.assertEqual(metrics['rollout_wall_time_s'], 4.)
            self.assertEqual(metrics['filtered_calls']['count'], 3)
            stage = metrics['remote_stage_timings']['server_inference_s']['filtered_calls']
            self.assertEqual(stage['count'], 3)
            self.assertAlmostEqual(stage['mean_ms'], 150.)
            self.assertAlmostEqual(stage['p95_ms'], 195.)

    def test_empty_intersection_and_incompatible_seed_are_rejected(self):
        catalog = copy.deepcopy(self.catalog)
        for e in catalog['runs'][0]['records'][0]['episodes']:
            e['success'] = False
        with self.assertRaisesRegex(ValueError, 'No common successful'):
            common_success_group(catalog, 'full', 'matched', self.root)
        self.catalog['runs'][0]['config']['seed'] = 8
        with self.assertRaisesRegex(ValueError, 'same recorded seed'):
            common_success_group(self.catalog, 'full', 'matched', self.root)


class StageTimingTests(unittest.TestCase):
    def record(self):
        means = {'client_preprocess_s': 7, 'client_encode_s': 6, 'server_decode_s': 2,
                 'server_queue_s': 1, 'server_inference_s': 30, 'server_total_s': 33,
                 'round_trip_s': 100, 'transport_overhead_s': 67}
        return {'label': 'Sync', 'metrics': {
            'filtered_calls': {'count': 5, 'mean_ms': 114, 'p95_ms': 250},
            'remote_stage_timings': {key: {'filtered_calls': {'count': 5, 'mean_ms': value,
                                                            'p95_ms': 999, 'missing_count': 0}}
                                     for key, value in means.items()}}}

    def test_mean_stages_reconcile_without_double_counting_round_trip(self):
        result = latency_breakdown(self.record())
        self.assertEqual(result['values'], [7, 6, 3, 30, 67, 1])
        self.assertEqual(sum(result['values']), result['total'])
        self.assertEqual(result['p95'], 250)  # Never sum stage percentiles.

    def test_incomplete_samples_are_not_drawn_as_zero(self):
        record = self.record()
        stage = record['metrics']['remote_stage_timings']['server_decode_s']['filtered_calls']
        stage.update(count=4, missing_count=1)
        self.assertIsNone(latency_breakdown(record))
        stage.update(count=5, missing_count=0, mean_ms=None)
        self.assertIsNone(latency_breakdown(record))
        record['metrics']['remote_stage_timings'] = None
        self.assertIsNone(latency_breakdown(record))

    def test_inconsistent_decomposition_is_rejected(self):
        record = self.record()
        record['metrics']['remote_stage_timings']['round_trip_s']['filtered_calls']['mean_ms'] = 120
        with self.assertRaisesRegex(ValueError, 'Round trip'):
            latency_breakdown(record)
        record = self.record()
        record['metrics']['filtered_calls']['mean_ms'] = 100
        with self.assertRaisesRegex(ValueError, 'exceed'):
            latency_breakdown(record)


if __name__ == '__main__':
    unittest.main()
