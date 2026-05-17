import os
import sys
from pathlib import Path

from .parsing import (
    BLOCK_TASK_PATTERN,
    LINE_TASK_PATTERN,
    current_timestamp,
    parse_param_tokens,
)


def _load_textual():
    try:
        from textual.app import App
        from textual.containers import Horizontal, Vertical
        from textual.widgets import Button, DataTable, Footer, Header, Input, Label, Static
    except ImportError:
        return None

    return {
        'App': App,
        'Button': Button,
        'DataTable': DataTable,
        'Footer': Footer,
        'Header': Header,
        'Horizontal': Horizontal,
        'Input': Input,
        'Label': Label,
        'Static': Static,
        'Vertical': Vertical,
    }


def textual_supported():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    term = os.environ.get('TERM', '')
    return bool(term and term != 'dumb' and _load_textual())


def _build_edit_app(file_path: Path, default_taskid, default_status, default_tags, default_timestamp, default_desc):
    textual = _load_textual()
    if textual is None:
        raise RuntimeError('Textual is not installed')

    App = textual['App']
    Button = textual['Button']
    Horizontal = textual['Horizontal']
    Input = textual['Input']
    Label = textual['Label']
    Static = textual['Static']
    Vertical = textual['Vertical']

    class TaskEditApp(App):
        CSS = """
        Screen {
            align: center middle;
        }

        #dialog {
            width: 80;
            max-width: 95%;
            height: auto;
            border: solid $primary;
            padding: 1 2;
        }

        #description {
            min-height: 3;
            margin: 1 0;
            color: $text-muted;
        }

        #title {
            text-style: bold;
            margin-bottom: 1;
        }

        #help {
            color: $text-muted;
            margin-top: 1;
        }

        Label {
            margin-top: 1;
        }

        #actions {
            height: auto;
            margin-top: 1;
        }

        Button {
            margin-right: 1;
        }
        """

        BINDINGS = [
            ('escape', 'cancel', 'Cancel'),
            ('ctrl+s', 'save', 'Save'),
        ]

        def compose(self):
            desc = default_desc or ''
            with Vertical(id='dialog'):
                yield Static('TASK EDITOR', id='title')
                yield Label(f'File: {file_path.name}')
                yield Static(desc or '(no description)', id='description')
                yield Label('Task ID')
                yield Input(value=default_taskid, id='taskid')
                yield Label('Status')
                yield Input(value=default_status or 'new', id='status')
                yield Label('Tags')
                yield Input(value=', '.join(default_tags), id='tags')
                yield Label('Timestamp')
                yield Input(value=default_timestamp, id='timestamp')
                with Horizontal(id='actions'):
                    yield Button('Save', id='save', variant='primary')
                    yield Button('Skip', id='cancel')
                yield Static('Ctrl+S saves. Escape skips.', id='help')

        def on_mount(self):
            self.query_one('#taskid', Input).focus()

        def on_button_pressed(self, event):
            if event.button.id == 'save':
                self.action_save()
            elif event.button.id == 'cancel':
                self.action_cancel()

        def action_save(self):
            taskid = self.query_one('#taskid', Input).value.strip() or default_taskid
            status = self.query_one('#status', Input).value.strip() or 'new'
            tags_value = self.query_one('#tags', Input).value
            tags = [tag.strip() for tag in tags_value.split(',') if tag.strip()]
            timestamp = self.query_one('#timestamp', Input).value.strip() or default_timestamp
            self.exit((taskid, status, tags, default_desc, timestamp))

        def action_cancel(self):
            self.exit(None)

    return TaskEditApp()


def text_edit_dialog(file_path: Path, default_taskid, default_status, default_tags, default_timestamp, default_desc):
    print(f"Editing TASK in: {file_path}")
    if default_desc:
        print(f"Description: {default_desc.splitlines()[0]}")
    taskid = input(f"Task ID [{default_taskid}]: ") or default_taskid
    status = input(f"Status [{default_status}]: ") or default_status
    tags_s = input(f"Tags (comma separated) [{', '.join(default_tags)}]: ") or ', '.join(default_tags)
    timestamp = input(f"Timestamp [{default_timestamp}]: ") or default_timestamp
    tags = [t.strip() for t in tags_s.split(',') if t.strip()]
    return taskid, status, tags, default_desc, timestamp


def prompt_edit(file_path: Path, task_lines: list[str], next_id: int):
    first = task_lines[0]
    line_match = LINE_TASK_PATTERN.search(first)
    block_match = BLOCK_TASK_PATTERN.search(first)
    if line_match:
        params = line_match.group('params')
        desc = line_match.group('desc')
        extra_desc_lines = []
        for line in task_lines[1:]:
            if line.lstrip().startswith('//'):
                extra_desc_lines.append(line.lstrip()[2:].strip())
        if extra_desc_lines:
            desc = desc + '\n' + '\n'.join(extra_desc_lines)
    elif block_match:
        params = block_match.group('params')
        desc = block_match.group('desc')
        if len(task_lines) > 1:
            rest = [line.strip().lstrip('*').strip() for line in task_lines[1:-1]]
            if rest:
                desc = desc + '\n' + '\n'.join(rest)
    else:
        params = ''
        desc = ''

    taskid, status, tags, timestamp = parse_param_tokens(params)
    if not taskid:
        taskid = f'#T{next_id}'
    if not timestamp:
        timestamp = current_timestamp()

    if textual_supported():
        try:
            result = _build_edit_app(
                file_path,
                taskid,
                status or 'new',
                tags,
                timestamp,
                desc,
            ).run()
        except Exception as exc:
            print(f"[warning] Textual TUI failed: {exc}. Falling back to plain prompt.", file=sys.stderr)
            result = text_edit_dialog(file_path, taskid, status or 'new', tags, timestamp, desc)
    else:
        if _load_textual() is None:
            print("[info] Textual is not installed; using plain prompt.", file=sys.stderr)
        else:
            print("[info] Textual TUI unavailable; using plain prompt.", file=sys.stderr)
        result = text_edit_dialog(file_path, taskid, status or 'new', tags, timestamp, desc)

    if result is None:
        return None

    taskid, status, tags, desc, timestamp = result
    return taskid, status, tags, desc, timestamp


def show_task_list_dialog(tasks, header: str | None = None):
    textual = _load_textual()
    if textual is None:
        raise RuntimeError('Textual is not installed')

    App = textual['App']
    DataTable = textual['DataTable']
    Footer = textual['Footer']
    Header = textual['Header']
    Label = textual['Label']

    class TaskListApp(App):
        TITLE = 'Task List'

        CSS = """
        DataTable {
            height: 1fr;
        }
        """

        BINDINGS = [
            ('q', 'quit', 'Quit'),
            ('escape', 'quit', 'Quit'),
        ]

        def compose(self):
            yield Header(show_clock=False)
            if header:
                yield Label(header)
            yield Label(f'Tasks: {len(tasks)}')
            yield DataTable(id='tasks')
            yield Footer()

        def on_mount(self):
            table = self.query_one('#tasks', DataTable)
            table.cursor_type = 'row'
            table.add_columns('ID', 'Status', 'Tags', 'File:Line', 'Summary')
            for task in tasks:
                table.add_row(
                    task['taskid'],
                    task['status'],
                    task['tags'],
                    task['file'],
                    task['desc'],
                )

    TaskListApp().run()


def show_stats_dialog(total, with_id, without_id, status_counts, tag_counts):
    textual = _load_textual()
    if textual is None:
        raise RuntimeError('Textual is not installed')

    App = textual['App']
    DataTable = textual['DataTable']
    Footer = textual['Footer']
    Header = textual['Header']
    Horizontal = textual['Horizontal']
    Label = textual['Label']
    Static = textual['Static']
    Vertical = textual['Vertical']

    class TaskStatsApp(App):
        TITLE = 'Task Stats'

        CSS = """
        #content {
            margin: 1 2;
            height: 1fr;
        }

        #summary {
            height: 7;
            margin-bottom: 1;
        }

        #breakdowns {
            height: 1fr;
        }

        .panel {
            width: 1fr;
            margin-right: 2;
        }

        .panel-title {
            text-style: bold;
            margin-bottom: 1;
        }

        DataTable {
            height: 1fr;
        }
        """

        BINDINGS = [
            ('q', 'quit', 'Quit'),
            ('escape', 'quit', 'Quit'),
        ]

        def compose(self):
            yield Header(show_clock=False)
            with Vertical(id='content'):
                yield Static('TASKS SUMMARY', classes='panel-title')
                yield DataTable(id='summary')
                with Horizontal(id='breakdowns'):
                    with Vertical(classes='panel'):
                        yield Label('By status', classes='panel-title')
                        yield DataTable(id='statuses')
                    with Vertical(classes='panel'):
                        yield Label('Top tags', classes='panel-title')
                        yield DataTable(id='tags')
            yield Footer()

        def on_mount(self):
            self._populate_summary()
            self._populate_counts(
                '#statuses',
                'Status',
                sorted(status_counts.items(), key=lambda x: (-x[1], x[0])),
            )
            self._populate_counts(
                '#tags',
                'Tag',
                sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])),
            )

        def _populate_summary(self):
            table = self.query_one('#summary', DataTable)
            table.cursor_type = 'row'
            table.add_columns('Metric', 'Count')
            table.add_row('Total tasks', str(total))
            table.add_row('With ID', str(with_id))
            table.add_row('Without ID', str(without_id))

        def _populate_counts(self, selector, label, rows):
            table = self.query_one(selector, DataTable)
            table.cursor_type = 'row'
            table.add_columns(label, 'Count')
            if not rows:
                table.add_row('(none)', '0')
                return
            for name, count in rows:
                table.add_row(str(name), str(count))

    TaskStatsApp().run()
