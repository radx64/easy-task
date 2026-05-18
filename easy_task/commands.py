import re
from collections import defaultdict
from pathlib import Path

from .parsing import (
    BLOCK_TASK_PATTERN,
    LINE_TASK_PATTERN,
    apply_update_to_file,
    collect_task_entries,
    extract_existing_max_id,
    format_params,
    iter_text_files,
    normalize_task_id,
    parse_param_tokens,
)
from .ui import prompt_edit


def scan(path: Path):
    max_id = extract_existing_max_id(path)
    next_id = max_id + 1
    found_to_assign = False
    for file_path, text in iter_text_files(path):
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
                while (
                    i < len(lines)
                    and lines[i].lstrip().startswith('//')
                    and not LINE_TASK_PATTERN.search(lines[i])
                ):
                    task_lines.append(lines[i])
                    i += 1

                existing_id, status, tags, timestamp, depends_on = parse_param_tokens(m_line.group('params'))
                if existing_id and timestamp:
                    continue

                found_to_assign = True
                res = prompt_edit(file_path, task_lines, next_id)
                if res is None:
                    print(f'Skipped {file_path}:{start + 1}')
                    continue
                taskid, status, tags, desc_first, timestamp, depends_on = res
                id_to_write = existing_id or taskid
                if not existing_id:
                    next_id += 1
                formatted = format_params(id_to_write, status or 'new', tags, timestamp, depends_on)
                leading_ws = re.match(r'(\s*)', lines[start]).group(1)
                first_line = f"{leading_ws}// TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                replacement = [first_line] + task_lines[1:]
                apply_update_to_file(file_path, lines, start, start + len(task_lines), replacement)
                if existing_id:
                    print(f"Updated {file_path}:{start + 1}: id={existing_id}, timestamp={timestamp}")
                else:
                    print(f"Updated {file_path}:{start + 1}: id={taskid}, status={status}, tags={tags}, depends_on={depends_on}")
                try:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                except Exception:
                    break
                i = start + 1
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

                existing_id, status, tags, timestamp, depends_on = parse_param_tokens(m_block.group('params'))
                if existing_id and timestamp:
                    continue

                found_to_assign = True
                res = prompt_edit(file_path, task_lines, next_id)
                if res is None:
                    print(f'Skipped {file_path}:{start + 1}')
                    continue
                taskid, status, tags, desc_first, timestamp, depends_on = res
                id_to_write = existing_id or taskid
                if not existing_id:
                    next_id += 1
                formatted = format_params(id_to_write, status or 'new', tags, timestamp, depends_on)
                leading_ws = re.match(r'(\s*)', lines[start]).group(1)
                opening = f"{leading_ws}/* TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                replacement = [opening] + task_lines[1:]
                apply_update_to_file(file_path, lines, start, start + len(task_lines), replacement)
                if existing_id:
                    print(f"Updated {file_path}:{start + 1}: id={existing_id}, timestamp={timestamp}")
                else:
                    print(f"Updated {file_path}:{start + 1}: id={taskid}, status={status}, tags={tags}, depends_on={depends_on}")
                try:
                    lines = file_path.read_text(encoding='utf-8').splitlines()
                except Exception:
                    break
                i = start + 1
                continue

            i += 1

    if not found_to_assign:
        print('Nothing new found')


def edit_task(path: Path, task_id: str):
    task_id = normalize_task_id(task_id)
    found = False
    for file_path, text in iter_text_files(path):
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
                while (
                    i < len(lines)
                    and lines[i].lstrip().startswith('//')
                    and not LINE_TASK_PATTERN.search(lines[i])
                ):
                    task_lines.append(lines[i])
                    i += 1
                existing_id, _, _, _, existing_depends = parse_param_tokens(m_line.group('params'))
                if existing_id == task_id:
                    found = True
                    res = prompt_edit(file_path, task_lines, 0)
                    if res is None:
                        print(f'Skipped {file_path}:{start + 1}')
                        return
                    taskid, status, tags, desc_first, timestamp, depends_on = res
                    formatted = format_params(taskid, status or 'new', tags, timestamp, depends_on)
                    leading_ws = re.match(r'(\s*)', lines[start]).group(1)
                    first_line = f"{leading_ws}// TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [first_line] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start + len(task_lines), replacement)
                    print(f"Updated {file_path}:{start + 1}: id={taskid}, status={status}, tags={tags}, timestamp={timestamp}, depends_on={depends_on}")
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
                existing_id, _, _, _, existing_depends = parse_param_tokens(m_block.group('params'))
                if existing_id == task_id:
                    found = True
                    res = prompt_edit(file_path, task_lines, 0)
                    if res is None:
                        print(f'Skipped {file_path}:{start + 1}')
                        return
                    taskid, status, tags, desc_first, timestamp, depends_on = res
                    formatted = format_params(taskid, status or 'new', tags, timestamp, depends_on)
                    leading_ws = re.match(r'(\s*)', lines[start]).group(1)
                    opening = f"{leading_ws}/* TASK({formatted}): {desc_first.splitlines()[0] if desc_first else ''}"
                    replacement = [opening] + task_lines[1:]
                    apply_update_to_file(file_path, lines, start, start + len(task_lines), replacement)
                    print(f"Updated {file_path}:{start + 1}: id={taskid}, status={status}, tags={tags}, timestamp={timestamp}, depends_on={depends_on}")
                    return
                continue

            i += 1

    if not found:
        print(f'Task {task_id} not found in {path}')


def _print_task_entries(tasks: list[dict], header: str | None = None):
    if not tasks:
        print('No tasks found')
        return

    if header:
        print(header)

    for task in tasks:
        body = task.get('body', '')
        desc = task.get('desc', '')
        suffix = '...' if body and body != desc else ''
        print(f"{task['taskid']} {task['status']} {task['tags']} {task['file']} {task['timestamp']} {desc}{suffix}")


def display_task(path: Path, task_id: str):
    task_id = normalize_task_id(task_id)
    tasks = collect_task_entries(path)
    task = next((entry for entry in tasks if entry['taskid'] == task_id), None)
    if task is None:
        print(f'Task {task_id} not found in {path}')
        return

    print(f"Task: {task['taskid']} {task['status']} {task['tags']} {task['file']} {task['timestamp']}")
    if task.get('depends_on'):
        print(f"Depends on: {', '.join(task['depends_on'])}")
    else:
        print('Depends on: (none)')

    print('\nFull description:')
    print(task.get('body', ''))


def list_tasks(path: Path):
    _print_task_entries(collect_task_entries(path))

def search_tasks(path: Path, query: str):
    query_lower = query.lower()
    tasks = [
        task for task in collect_task_entries(path)
        if query_lower in task['taskid'].lower()
        or query_lower in task['status'].lower()
        or query_lower in task['tags'].lower()
        or query_lower in task['file'].lower()
        or query_lower in task['desc'].lower()
        or query_lower in task.get('body', '').lower()
        or query_lower in ' '.join(task.get('depends_on', [])).lower()
    ]
    _print_task_entries(tasks, f'Search expression: {query}')


def deps(path: Path, task_id: str):
    task_id = normalize_task_id(task_id)
    tasks = collect_task_entries(path)
    task = next((entry for entry in tasks if entry['taskid'] == task_id), None)
    if task is None:
        print(f'Task {task_id} not found in {path}')
        return

    body = task.get('body', '')
    desc = task.get('desc', '')
    suffix = '...' if body and body != desc else ''
    print(f"Task: {task['taskid']} {task['status']} {task['tags']} {task['file']} {task['timestamp']} {desc}{suffix}")
    if task.get('depends_on'):
        print(f"Depends on: {', '.join(task['depends_on'])}")
    else:
        print('Depends on: (none)')

    dependents = [entry for entry in tasks if task_id in entry.get('depends_on', [])]
    print('\nDependents:')
    if dependents:
        for entry in dependents:
            body = entry.get('body', '')
            desc = entry.get('desc', '')
            suffix = '...' if body and body != desc else ''
            print(f"{entry['taskid']} {entry['status']} {entry['tags']} {entry['file']} {entry['timestamp']} {desc}{suffix}")
    else:
        print('  (none)')


def stats(path: Path):
    total = 0
    with_id = 0
    without_id = 0
    status_counts = defaultdict(int)
    tag_counts = defaultdict(int)

    for _, text in iter_text_files(path):
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                i += 1
                while (
                    i < len(lines)
                    and lines[i].lstrip().startswith('//')
                    and not LINE_TASK_PATTERN.search(lines[i])
                ):
                    i += 1
                existing_id, status, tags, _, _ = parse_param_tokens(m_line.group('params'))
                total += 1
                if existing_id:
                    with_id += 1
                else:
                    without_id += 1
                status_counts[status or 'new'] += 1
                for tag in tags:
                    tag_counts[tag] += 1
                continue

            if m_block:
                i += 1
                while i < len(lines):
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1
                existing_id, status, tags, _, _ = parse_param_tokens(m_block.group('params'))
                total += 1
                if existing_id:
                    with_id += 1
                else:
                    without_id += 1
                status_counts[status or 'new'] += 1
                for tag in tags:
                    tag_counts[tag] += 1
                continue

            i += 1

    print('TASKS SUMMARY')
    print('-------------')
    print(f'Total tasks: {total}')
    print(f'With ID:    {with_id}')
    print(f'Without ID: {without_id}')
    print('\nBy status:')
    for status, cnt in sorted(status_counts.items(), key=lambda x: (-x[1], x[0])):
        print(f'  {status}: {cnt}')
    print('\nTop tags:')
    if tag_counts:
        for tag, cnt in sorted(tag_counts.items(), key=lambda x: (-x[1], x[0])):
            print(f'  {tag}: {cnt}')
    else:
        print('  (none)')
