
#!/usr/bin/env python3

import argparse
import curses
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from collections import defaultdict

# Patterns to detect TASK comments
LINE_TASK_PATTERN = re.compile(r'//\s*TASK\((?P<params>[^)]*)\)\s*:?\s*(?P<desc>.*)')
BLOCK_TASK_PATTERN = re.compile(r'/\*\s*TASK\((?P<params>[^)]*)\)\s*:?\s*(?P<desc>.*)')
ID_RE = re.compile(r'^(?:#T|T)?(?P<id>\d+)$')
SKIP_DIRS = {'.git', '__pycache__'}


def extract_existing_max_id(path: Path):
    max_id = 0
    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                params = m_line.group('params')
                taskid, _, _, _ = parse_param_tokens(params)
                if taskid:
                    try:
                        val = int(ID_RE.fullmatch(taskid).group('id'))
                        if val > max_id:
                            max_id = val
                    except Exception:
                        pass
                i += 1
                continue
            if m_block:
                params = m_block.group('params')
                taskid, _, _, _ = parse_param_tokens(params)
                if taskid:
                    try:
                        val = int(ID_RE.fullmatch(taskid).group('id'))
                        if val > max_id:
                            max_id = val
                    except Exception:
                        pass
                i += 1
                continue
            i += 1
    return max_id


def parse_param_tokens(param_str: str):
    # split by comma, strip
    tokens = [t.strip() for t in param_str.split(',') if t.strip()]
    taskid = None
    status = None
    tags = []
    timestamp = None
    for t in tokens:
        # try to detect an ID token like #T123, #123, T123 or 123
        m_id = ID_RE.fullmatch(t)
        if m_id and taskid is None:
            taskid = f"#T{m_id.group('id')}"
            continue
        if t.startswith('status:'):
            status = t.split(':', 1)[1]
            continue
        if t.startswith('tags:'):
            inner = t.split(':', 1)[1].strip()
            inner = inner.strip('{}')
            tags = [x.strip() for x in inner.split(',') if x.strip()]
            continue
        if t.startswith('timestamp:'):
            timestamp = t.split(':', 1)[1]
            continue
        # legacy single-word status or tags
        if t in ('new', 'open', 'in-progress', 'done') and status is None:
            status = t
            continue
        # otherwise treat as a tag
        tags.append(t)
    return taskid, status, tags, timestamp


def current_timestamp():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def normalize_task_id(task_id: str):
    m = ID_RE.search(task_id)
    if not m:
        return task_id
    return f"#T{m.group('id')}"


def format_params(taskid: str, status: str, tags: list, timestamp=None):
    # ensure status defaults to 'new'
    if not status:
        status = 'new'
    tags_part = ', '.join(tags) if tags else ''
    if timestamp:
        return f"{taskid}, status:{status}, tags: {{{tags_part}}}, timestamp:{timestamp}"
    return f"{taskid}, status:{status}, tags: {{{tags_part}}}"


def curses_supported():
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    term = os.environ.get('TERM', '')
    return term and term != 'dumb'


def curses_edit_dialog(stdscr, file_path, orig_lines, default_taskid, default_status, default_tags, default_timestamp, default_desc):
    curses.curs_set(1)
    stdscr.keypad(True)
    stdscr.clear()
    maxy, maxx = stdscr.getmaxyx()

    width = min(80, maxx - 4)
    height = min(20, maxy - 4)
    top = max(0, (maxy - height) // 2)
    left = max(0, (maxx - width) // 2)

    desc_lines = (default_desc or '').splitlines() or ['']
    desc_height = min(5, len(desc_lines))
    content_height = 10 + desc_height
    if content_height > height:
        height = min(maxy - 4, content_height)
        top = max(0, (maxy - height) // 2)

    win = curses.newwin(height, width, top, left)
    win.keypad(True)
    win.border()
    try:
        curses.start_color()
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
        curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    except curses.error:
        pass

    def safe_addstr(win, y, x, text, attr=0):
        try:
            win.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            try:
                win.addnstr(y, x, text, max(0, width - x - 1))
            except curses.error:
                pass

    title = ' TASK EDITOR '
    title_x = max(2, (width - len(title)) // 2)
    safe_addstr(win, 0, title_x, title, curses.color_pair(1) | curses.A_BOLD)

    header = f'File: {file_path.name}'
    safe_addstr(win, 1, 2, header, curses.A_BOLD)
    safe_addstr(win, 2, 2, 'Description:', curses.A_UNDERLINE)

    for idx in range(desc_height):
        text = desc_lines[idx]
        safe_addstr(win, 3 + idx, 2, text)
    if desc_height < 5:
        safe_addstr(win, 3 + desc_height, 2, '(read-only)', curses.A_DIM)

    fields = [
        ('Task ID', default_taskid),
        ('Status', default_status or 'new'),
        ('Tags', ', '.join(default_tags)),
        ('Timestamp', default_timestamp),
    ]
    values = [list(value) for _, value in fields]
    cursors = [len(val) for val in values]
    current = 0
    field_y = 4 + max(desc_height, 1)

    instructions = 'Enter=save  Tab/Down=next  Shift-Tab/Up=prev  Esc=skip'
    field_width = width - 18

    def draw_fields():
        for idx, (label, _) in enumerate(fields):
            y = field_y + idx * 2
            label_text = f'{label}:'.ljust(14)
            field_attr = curses.color_pair(2) | curses.A_BOLD if idx == current else curses.A_NORMAL
            safe_addstr(win, y, 2, label_text, field_attr)
            content = ''.join(values[idx])
            display = content[:field_width]
            safe_addstr(win, y, 16, ' ' * field_width)
            safe_addstr(win, y, 16, display, field_attr)
            if idx == current:
                cursor_x = 16 + min(cursors[idx], field_width - 1)
                try:
                    win.move(y, cursor_x)
                except curses.error:
                    pass
        safe_addstr(win, height - 2, 2, ' ' * (width - 4))
        safe_addstr(win, height - 2, 2, instructions[:width - 4], curses.A_DIM)

    while True:
        draw_fields()
        win.refresh()
        try:
            ch = win.get_wch()
        except curses.error:
            continue

        if ch in ('\n', '\r', curses.KEY_ENTER):
            taskid = ''.join(values[0]).strip()
            status = ''.join(values[1]).strip() or 'new'
            tags = [t.strip() for t in ''.join(values[2]).split(',') if t.strip()]
            timestamp = ''.join(values[3]).strip() or default_timestamp
            if not taskid:
                taskid = default_taskid
            return taskid, status, tags, default_desc, timestamp

        if ch == '\x1b':
            return None

        if ch == '\t' or ch == curses.KEY_DOWN:
            current = (current + 1) % len(fields)
            continue
        if ch == curses.KEY_BTAB or ch == curses.KEY_UP:
            current = (current - 1) % len(fields)
            continue

        if ch == curses.KEY_LEFT:
            if cursors[current] > 0:
                cursors[current] -= 1
            continue
        if ch == curses.KEY_RIGHT:
            if cursors[current] < len(values[current]):
                cursors[current] += 1
            continue

        if ch in (curses.KEY_BACKSPACE, '\b', '\x7f'):
            if cursors[current] > 0:
                cursors[current] -= 1
                values[current].pop(cursors[current])
            continue

        if isinstance(ch, str) and ch.isprintable():
            values[current].insert(cursors[current], ch)
            cursors[current] += 1
            continue

        # ignore other keys


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
    # derive existing param and description
    first = task_lines[0]
    line_match = LINE_TASK_PATTERN.search(first)
    block_match = BLOCK_TASK_PATTERN.search(first)
    if line_match:
        params = line_match.group('params')
        desc = line_match.group('desc')
        # append subsequent // lines to desc if present
        extra_desc_lines = []
        for l in task_lines[1:]:
            if l.lstrip().startswith('//'):
                extra_desc_lines.append(l.lstrip()[2:].strip())
        if extra_desc_lines:
            desc = desc + '\n' + '\n'.join(extra_desc_lines)
    elif block_match:
        params = block_match.group('params')
        desc = block_match.group('desc')
        # include following lines until closing */ as part of desc
        if len(task_lines) > 1:
            rest = [l.strip().lstrip('*').strip() for l in task_lines[1:-1]]
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

    # launch curses UI when available
    if curses_supported():
        try:
            result = curses.wrapper(
                curses_edit_dialog,
                file_path,
                task_lines,
                taskid,
                status or 'new',
                tags,
                timestamp,
                desc,
            )
        except Exception as exc:
            print(f"[warning] curses TUI failed: {exc}. Falling back to plain prompt.", file=sys.stderr)
            result = text_edit_dialog(file_path, taskid, status or 'new', tags, timestamp, desc)
    else:
        print("[info] curses TUI unavailable; using plain prompt.", file=sys.stderr)
        result = text_edit_dialog(file_path, taskid, status or 'new', tags, timestamp, desc)

    # if curses editor signaled skip (returns None), propagate None
    if result is None:
        return None

    taskid, status, tags, desc, timestamp = result
    return taskid, status, tags, desc, timestamp


def apply_update_to_file(file_path: Path, lines: list[str], start_idx: int, end_idx: int, replacement_lines: list[str]):
    # Replace lines[start_idx:end_idx] with replacement_lines
    new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]
    file_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')


def collect_task_entries(path: Path):
    entries = []
    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('//'):
                    task_lines.append(lines[i])
                    i += 1

                params = m_line.group('params')
                desc_first = m_line.group('desc')
                taskid, status, tags, _ = parse_param_tokens(params)
                if taskid:
                    file_label = str(file_path.relative_to(path))
                    entries.append({
                        'taskid': taskid,
                        'status': status or 'new',
                        'tags': ', '.join(tags),
                        'file': f"{file_label}:{start+1}",
                        'desc': desc_first.strip(),
                    })
                continue

            if m_block:
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines):
                    task_lines.append(lines[i])
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1

                params = m_block.group('params')
                desc_first = m_block.group('desc')
                taskid, status, tags, _ = parse_param_tokens(params)
                if taskid:
                    file_label = str(file_path.relative_to(path))
                    entries.append({
                        'taskid': taskid,
                        'status': status or 'new',
                        'tags': ', '.join(tags),
                        'file': f"{file_label}:{start+1}",
                        'desc': desc_first.strip(),
                    })
                continue

            i += 1
    return entries


def curses_task_list_dialog(stdscr, tasks):
    curses.curs_set(0)
    stdscr.keypad(True)
    curses.start_color()
    try:
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
        curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_CYAN)
    except curses.error:
        pass

    def safe_addstr(win, y, x, text, attr=0):
        try:
            win.addnstr(y, x, text, max(0, curses.COLS - x - 1), attr)
        except curses.error:
            try:
                win.addnstr(y, x, text, max(0, curses.COLS - x - 1))
            except curses.error:
                pass

    height, width = stdscr.getmaxyx()
    table_top = 4
    visible_rows = max(1, height - table_top - 3)
    selected = 0
    top_idx = 0

    while True:
        stdscr.erase()
        title = ' TASK LIST '
        title_x = max(2, (width - len(title)) // 2)
        safe_addstr(stdscr, 0, title_x, title, curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 1, 2, f'Tasks: {len(tasks)}  Navigate: ↑/↓  PgUp/PgDn  q/Esc=quit', curses.A_DIM)

        id_w = 8
        status_w = 12
        tags_w = 22
        file_w = max(20, min(30, width // 4))
        summary_w = max(10, width - 4 - id_w - status_w - tags_w - file_w - 4)

        header = (
            f"{'ID'.ljust(id_w)} {'Status'.ljust(status_w)} {'Tags'.ljust(tags_w)} "
            f"{'File:Line'.ljust(file_w)} {'Summary'.ljust(summary_w)}"
        )
        safe_addstr(stdscr, 3, 2, header, curses.A_UNDERLINE | curses.A_BOLD)

        for visible_index in range(visible_rows):
            row_idx = top_idx + visible_index
            y = table_top + visible_index
            if row_idx >= len(tasks):
                break
            task = tasks[row_idx]
            row_attr = curses.A_REVERSE if row_idx == selected else curses.A_NORMAL
            desc = task['desc'][:summary_w]
            line = (
                f"{task['taskid'].ljust(id_w)} {task['status'].ljust(status_w)} "
                f"{task['tags'][:tags_w].ljust(tags_w)} {task['file'][:file_w].ljust(file_w)} "
                f"{desc.ljust(summary_w)}"
            )
            safe_addstr(stdscr, y, 2, line, row_attr)

        if len(tasks) > visible_rows:
            status = f"Showing {top_idx+1}-{min(len(tasks), top_idx+visible_rows)} of {len(tasks)}"
            safe_addstr(stdscr, height - 2, 2, status, curses.A_DIM)

        stdscr.refresh()
        ch = stdscr.getch()
        if ch in (ord('q'), 27):
            break
        if ch in (curses.KEY_DOWN, ord('j')):
            if selected < len(tasks) - 1:
                selected += 1
                if selected >= top_idx + visible_rows:
                    top_idx += 1
            continue
        if ch in (curses.KEY_UP, ord('k')):
            if selected > 0:
                selected -= 1
                if selected < top_idx:
                    top_idx = selected
            continue
        if ch == curses.KEY_NPAGE:
            top_idx = min(len(tasks) - visible_rows, top_idx + visible_rows)
            selected = min(len(tasks) - 1, top_idx + visible_rows - 1)
            continue
        if ch == curses.KEY_PPAGE:
            top_idx = max(0, top_idx - visible_rows)
            selected = max(0, top_idx)
            continue


def curses_stats_dialog(stdscr, total, with_id, without_id, status_counts, tag_counts):
    curses.curs_set(0)
    stdscr.keypad(True)
    curses.start_color()
    try:
        curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_BLUE)
    except curses.error:
        pass

    def safe_addstr(win, y, x, text, attr=0):
        try:
            win.addnstr(y, x, text, max(0, width - x - 1), attr)
        except curses.error:
            try:
                win.addnstr(y, x, text, max(0, width - x - 1))
            except curses.error:
                pass

    height, width = stdscr.getmaxyx()
    title = ' TASK STATS '
    title_x = max(2, (width - len(title)) // 2)

    while True:
        stdscr.erase()
        safe_addstr(stdscr, 0, title_x, title, curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 1, 2, f'Total tasks: {total}', curses.A_BOLD)
        safe_addstr(stdscr, 2, 2, f'With ID:    {with_id}')
        safe_addstr(stdscr, 3, 2, f'Without ID: {without_id}')

        status_start = 5
        safe_addstr(stdscr, status_start, 2, 'By status:', curses.A_UNDERLINE | curses.A_BOLD)
        for idx, (status, cnt) in enumerate(sorted(status_counts.items(), key=lambda x: (-x[1], x[0]))):
            y = status_start + idx + 1
            if y >= height - 3:
                break
            safe_addstr(stdscr, y, 4, f'{status}: {cnt}')

        tag_x = width // 2
        safe_addstr(stdscr, status_start, tag_x, 'Top tags:', curses.A_UNDERLINE | curses.A_BOLD)
        for idx, (tag, cnt) in enumerate(sorted(tag_counts.items(), key=lambda x: (-x[1], x[0]))):
            y = status_start + idx + 1
            if y >= height - 3:
                break
            safe_addstr(stdscr, y, tag_x + 2, f'{tag}: {cnt}')

        safe_addstr(stdscr, height - 2, 2, 'Press q or Esc to exit.', curses.A_DIM)
        stdscr.refresh()

        ch = stdscr.getch()
        if ch in (ord('q'), 27):
            break


def scan(path: Path):
    max_id = extract_existing_max_id(path)
    next_id = max_id + 1
    found_to_assign = False
    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        i = 0
        changed = False
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                # collect contiguous // lines
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('//'):
                    task_lines.append(lines[i])
                    i += 1

                params = m_line.group('params')
                desc_first = m_line.group('desc')
                existing_id, status, tags, timestamp = parse_param_tokens(params)
                if existing_id and timestamp:
                    # already has id and timestamp — skip in scan
                    continue

                if existing_id:
                    # existing task missing timestamp
                    found_to_assign = True
                    res = prompt_edit(file_path, task_lines, next_id)
                    if res is None:
                        print(f'Skipped {file_path}:{start+1}')
                        continue
                    taskid, status, tags, desc_first, timestamp = res
                    formatted = format_params(existing_id, status or 'new', tags, timestamp)
                    leading_ws = ''
                    m_ws = re.match(r'(\s*)', lines[start])
                    if m_ws:
                        leading_ws = m_ws.group(1)
                    first_line = f"{leading_ws}// TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [first_line] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                    print(f"Updated {file_path}:{start+1}: id={existing_id}, timestamp={timestamp}")
                    changed = True
                    try:
                        lines = file_path.read_text(encoding='utf-8').splitlines()
                    except Exception:
                        break
                    i = start + 1
                    continue

                # found a task without id (needs assignment)
                found_to_assign = True

                # need to assign id and ask user
                res = prompt_edit(file_path, task_lines, next_id)
                if res is None:
                    print(f'Skipped {file_path}:{start+1}')
                    continue
                taskid, status, tags, desc_first, timestamp = res
                next_id += 1
                formatted = format_params(taskid, status or 'new', tags, timestamp)
                # build replacement that only updates the opening line and preserves the rest
                leading_ws = ''
                m_ws = re.match(r'(\s*)', lines[start])
                if m_ws:
                    leading_ws = m_ws.group(1)
                first_line = f"{leading_ws}// TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                replacement = [first_line] + task_lines[1:]
                apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                print(f"Updated {file_path}:{start+1}: id={taskid}, status={status}, tags={tags}")
                changed = True
                # reload file after edit
                try:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                except Exception:
                    break
                i = start + 1
                continue

            if m_block:
                # collect until closing */
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines):
                    task_lines.append(lines[i])
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1

                params = m_block.group('params')
                desc_first = m_block.group('desc')
                existing_id, status, tags, timestamp = parse_param_tokens(params)
                if existing_id and timestamp:
                    # already has id and timestamp — skip in scan
                    continue

                if existing_id:
                    # existing task missing timestamp
                    found_to_assign = True
                    res = prompt_edit(file_path, task_lines, next_id)
                    if res is None:
                        print(f'Skipped {file_path}:{start+1}')
                        continue
                    taskid, status, tags, desc_first, timestamp = res
                    formatted = format_params(existing_id, status or 'new', tags, timestamp)
                    leading_ws = ''
                    m_ws = re.match(r'(\s*)', lines[start])
                    if m_ws:
                        leading_ws = m_ws.group(1)
                    opening = f"{leading_ws}/* TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [opening] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                    print(f"Updated {file_path}:{start+1}: id={existing_id}, timestamp={timestamp}")
                    changed = True
                    try:
                        lines = file_path.read_text(encoding='utf-8').splitlines()
                    except Exception:
                        break
                    i = start + 1
                    continue

                # found a block task without id
                found_to_assign = True

                res = prompt_edit(file_path, task_lines, next_id)
                if res is None:
                    print(f'Skipped {file_path}:{start+1}')
                    continue
                taskid, status, tags, desc_first, timestamp = res
                next_id += 1
                formatted = format_params(taskid, status or 'new', tags, timestamp)
                # update only the opening line of the block and preserve the rest
                leading_ws = ''
                m_ws = re.match(r'(\s*)', lines[start])
                if m_ws:
                    leading_ws = m_ws.group(1)
                opening = f"{leading_ws}/* TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                replacement = [opening] + task_lines[1:]
                apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                print(f"Updated {file_path}:{start+1}: id={taskid}, status={status}, tags={tags}")
                changed = True
                try:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                except Exception:
                    break
                i = start + 1
                continue

            else:
                i += 1


    if not found_to_assign:
        print('Nothing new found')


def edit_task(path: Path, task_id: str):
    task_id = normalize_task_id(task_id)
    found = False
    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('//'):
                    task_lines.append(lines[i])
                    i += 1
                params = m_line.group('params')
                existing_id, status, tags, timestamp = parse_param_tokens(params)
                if existing_id == task_id:
                    found = True
                    res = prompt_edit(file_path, task_lines, 0)
                    if res is None:
                        print(f'Skipped {file_path}:{start+1}')
                        return
                    taskid, status, tags, desc_first, timestamp = res
                    formatted = format_params(taskid, status or 'new', tags, timestamp)
                    leading_ws = ''
                    m_ws = re.match(r'(\s*)', lines[start])
                    if m_ws:
                        leading_ws = m_ws.group(1)
                    first_line = f"{leading_ws}// TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [first_line] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                    print(f"Updated {file_path}:{start+1}: id={taskid}, status={status}, tags={tags}, timestamp={timestamp}")
                    return
                continue
            if m_block:
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines):
                    task_lines.append(lines[i])
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1
                params = m_block.group('params')
                existing_id, status, tags, timestamp = parse_param_tokens(params)
                if existing_id == task_id:
                    found = True
                    res = prompt_edit(file_path, task_lines, 0)
                    if res is None:
                        print(f'Skipped {file_path}:{start+1}')
                        return
                    taskid, status, tags, desc_first, timestamp = res
                    formatted = format_params(taskid, status or 'new', tags, timestamp)
                    leading_ws = ''
                    m_ws = re.match(r'(\s*)', lines[start])
                    if m_ws:
                        leading_ws = m_ws.group(1)
                    opening = f"{leading_ws}/* TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [opening] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start+len(task_lines), replacement)
                    print(f"Updated {file_path}:{start+1}: id={taskid}, status={status}, tags={tags}, timestamp={timestamp}")
                    return
                continue
            i += 1

    if not found:
        print(f'Task {task_id} not found in {path}')


def list_tasks(path: Path):
    tasks = collect_task_entries(path)
    if not tasks:
        print('No tasks found')
        return

    if curses_supported():
        try:
            curses.wrapper(curses_task_list_dialog, tasks)
            return
        except Exception as exc:
            print(f"[warning] curses TUI failed: {exc}. Falling back to plain output.", file=sys.stderr)

    for task in tasks:
        print(f"{task['taskid']} {task['status']} {task['tags']} {task['file']} {task['desc']}")


def stats(path: Path):
    total = 0
    with_id = 0
    without_id = 0
    status_counts = defaultdict(int)
    tag_counts = defaultdict(int)

    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            text = file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue

        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                # single-line or //-style multi
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('//'):
                    task_lines.append(lines[i])
                    i += 1
                params = m_line.group('params')
                existing_id, status, tags, _ = parse_param_tokens(params)
                total += 1
                if existing_id:
                    with_id += 1
                else:
                    without_id += 1
                status_counts[status or 'new'] += 1
                for t in tags:
                    tag_counts[t] += 1
                continue
            if m_block:
                start = i
                task_lines = [lines[i]]
                i += 1
                while i < len(lines):
                    task_lines.append(lines[i])
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1
                params = m_block.group('params')
                existing_id, status, tags, _ = parse_param_tokens(params)
                total += 1
                if existing_id:
                    with_id += 1
                else:
                    without_id += 1
                status_counts[status or 'new'] += 1
                for t in tags:
                    tag_counts[t] += 1
                continue
            i += 1

    if curses_supported():
        try:
            curses.wrapper(
                curses_stats_dialog,
                total,
                with_id,
                without_id,
                status_counts,
                tag_counts,
            )
            return
        except Exception as exc:
            print(f"[warning] curses TUI failed: {exc}. Falling back to plain output.", file=sys.stderr)

    # print summary
    print('TASKS SUMMARY')
    print('-------------')
    print(f'Total tasks: {total}')
    print(f'With ID:    {with_id}')
    print(f'Without ID: {without_id}')
    print('\nBy status:')
    for s, cnt in sorted(status_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f'  {s}: {cnt}')
    print('\nTop tags:')
    if tag_counts:
        for t, cnt in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f'  {t}: {cnt}')
    else:
        print('  (none)')

def main():
    parser = argparse.ArgumentParser(
        description='easy-task: scan for inline TASK comments'
    )
    subparsers = parser.add_subparsers(dest='command') #!/usr/bin/env python

    scan_parser = subparsers.add_parser(
        'scan', help='List all TASK comments in files under a directory'
    )
    scan_parser.add_argument(
        'path', nargs='?', default='.', help='Directory to scan (default: current directory)'
    )

    list_parser = subparsers.add_parser(
        'list', help='List TASK comments that already have assigned IDs'
    )
    list_parser.add_argument(
        'path', nargs='?', default='.', help='Directory to scan (default: current directory)'
    )

    stats_parser = subparsers.add_parser(
        'stats', help='Print summary statistics about TASK comments'
    )
    stats_parser.add_argument(
        'path', nargs='?', default='.', help='Directory to scan (default: current directory)'
    )

    edit_parser = subparsers.add_parser(
        'edit', help='Edit the metadata of an existing TASK by ID'
    )
    edit_parser.add_argument(
        'taskId', help='Task ID to edit, e.g. #T123'
    )
    edit_parser.add_argument(
        'path', nargs='?', default='.', help='Directory containing TASK comments (default: current directory)'
    )

    args = parser.parse_args()
    if args.command == 'scan':
        scan(Path(args.path))
    elif args.command == 'list':
        list_tasks(Path(args.path))
    elif args.command == 'stats':
        stats(Path(args.path))
    elif args.command == 'edit':
        edit_task(Path(args.path), args.taskId)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()
