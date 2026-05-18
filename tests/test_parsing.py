import tempfile
import unittest
from pathlib import Path

from easy_task.parsing import (
    collect_task_entries,
    extract_existing_max_id,
    format_params,
    normalize_task_id,
    parse_param_tokens,
    split_param_tokens,
)


class ParseParamTokensTests(unittest.TestCase):
    def test_split_param_tokens_keeps_tag_lists_together(self):
        self.assertEqual(
            split_param_tokens('#T12, status:open, tags: {ui, bug}, timestamp:2026-05-17T19:00:00'),
            ['#T12', 'status:open', 'tags: {ui, bug}', 'timestamp:2026-05-17T19:00:00'],
        )

    def test_parse_current_metadata_format(self):
        taskid, status, tags, timestamp = parse_param_tokens(
            '#T12, status:open, tags: {ui, bug}, timestamp:2026-05-17T19:00:00'
        )

        self.assertEqual(taskid, '#T12')
        self.assertEqual(status, 'open')
        self.assertEqual(tags, ['ui', 'bug'])
        self.assertEqual(timestamp, '2026-05-17T19:00:00')

    def test_parse_legacy_status_and_tag_tokens(self):
        taskid, status, tags, timestamp = parse_param_tokens('7, in-progress, backend')

        self.assertEqual(taskid, '#T7')
        self.assertEqual(status, 'in-progress')
        self.assertEqual(tags, ['backend'])
        self.assertIsNone(timestamp)

    def test_format_params_defaults_missing_status(self):
        self.assertEqual(
            format_params('#T3', '', ['script', 'feature'], '2026-05-17T19:11:25'),
            '#T3, status:new, tags: {script, feature}, timestamp:2026-05-17T19:11:25',
        )

    def test_normalize_task_id_accepts_common_forms(self):
        self.assertEqual(normalize_task_id('#T3'), '#T3')
        self.assertEqual(normalize_task_id('T3'), '#T3')
        self.assertEqual(normalize_task_id('3'), '#T3')


class TaskCollectionTests(unittest.TestCase):
    def test_collect_task_entries_finds_line_and_block_tasks_with_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'example.c').write_text(
                '\n'.join([
                    '// TASK(#T1, status:new, tags: {script, feature}): line task',
                    '// more detail',
                    '/* TASK(#T4, status:done, tags: {docs}): block task',
                    ' * extra detail',
                    ' */',
                    '// TASK(status:new, tags: {skip}): no id',
                ]),
                encoding='utf-8',
            )

            entries = collect_task_entries(root)

        self.assertEqual(
            entries,
            [
                {
                    'taskid': '#T1',
                    'status': 'new',
                    'tags': 'script, feature',
                    'file': 'example.c:1',
                    'desc': 'line task',
                    'body': 'line task more detail',
                    'timestamp': '-',
                },
                {
                    'taskid': '#T4',
                    'status': 'done',
                    'tags': 'docs',
                    'file': 'example.c:3',
                    'desc': 'block task',
                    'body': 'block task extra detail',
                    'timestamp': '-',
                },
            ],
        )

    def test_extract_existing_max_id_ignores_skipped_dirs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'src').mkdir()
            (root / 'src' / 'app.c').write_text('// TASK(#T8): visible\n', encoding='utf-8')
            (root / '.git').mkdir()
            (root / '.git' / 'ignored.c').write_text('// TASK(#T99): ignored\n', encoding='utf-8')

            self.assertEqual(extract_existing_max_id(root), 8)


if __name__ == '__main__':
    unittest.main()
