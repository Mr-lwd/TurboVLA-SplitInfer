import copy
import json
from pathlib import Path
import tempfile
import unittest

from scripts.libero.benchmark_common import summarize
from scripts.libero.build_benchmark_report import add_run, import_run, replace_block, table
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
