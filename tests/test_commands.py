import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from easy_task.commands import edit_task, list_tasks, scan, stats


class CommandTests(unittest.TestCase):
    def test_list_tasks_prints_plain_output_when_curses_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'todos.list').write_text(
                '// TASK(#T1, status:new, tags: {script, feature}): add task\n',
                encoding='utf-8',
            )

            output = io.StringIO()
            with patch('easy_task.commands.curses_supported', return_value=False), redirect_stdout(output):
                list_tasks(root)

        self.assertEqual(output.getvalue(), '#T1 new script, feature todos.list:1 add task\n')

    def test_stats_prints_plain_summary_when_curses_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'todos.list').write_text(
                '\n'.join([
                    '// TASK(#T1, status:new, tags: {script, feature}): one',
                    '// TASK(status:open, tags: {script}): two',
                ]),
                encoding='utf-8',
            )

            output = io.StringIO()
            with patch('easy_task.commands.curses_supported', return_value=False), redirect_stdout(output):
                stats(root)

        text = output.getvalue()
        self.assertIn('Total tasks: 2', text)
        self.assertIn('With ID:    1', text)
        self.assertIn('Without ID: 1', text)
        self.assertIn('  new: 1', text)
        self.assertIn('  open: 1', text)
        self.assertIn('  script: 2', text)
        self.assertIn('  feature: 1', text)

    def test_scan_assigns_metadata_using_prompt_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'app.c'
            source.write_text('// TASK(): implement feature\n// keep detail\n', encoding='utf-8')

            output = io.StringIO()
            with patch(
                'easy_task.commands.prompt_edit',
                return_value=('#T1', 'open', ['ui', 'bug'], 'implement feature', '2026-05-17T19:00:00'),
            ), redirect_stdout(output):
                scan(root)

            self.assertEqual(
                source.read_text(encoding='utf-8'),
                '// TASK(#T1, status:open, tags: {ui, bug}, timestamp:2026-05-17T19:00:00): implement feature\n'
                '// keep detail\n',
            )
            self.assertIn('Updated', output.getvalue())

    def test_edit_task_rewrites_matching_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'app.c'
            source.write_text(
                '// TASK(#T2, status:new, tags: {old}, timestamp:2026-05-17T18:00:00): old summary\n',
                encoding='utf-8',
            )

            output = io.StringIO()
            with patch(
                'easy_task.commands.prompt_edit',
                return_value=('#T2', 'done', ['new'], 'new summary', '2026-05-17T19:00:00'),
            ), redirect_stdout(output):
                edit_task(root, '2')

            self.assertEqual(
                source.read_text(encoding='utf-8'),
                '// TASK(#T2, status:done, tags: {new}, timestamp:2026-05-17T19:00:00): new summary\n',
            )


if __name__ == '__main__':
    unittest.main()
