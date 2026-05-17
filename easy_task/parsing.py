import re
from datetime import datetime
from pathlib import Path


LINE_TASK_PATTERN = re.compile(r'//\s*TASK\((?P<params>[^)]*)\)\s*:?\s*(?P<desc>.*)')
BLOCK_TASK_PATTERN = re.compile(r'/\*\s*TASK\((?P<params>[^)]*)\)\s*:?\s*(?P<desc>.*)')
ID_RE = re.compile(r'^(?:#T|T)?(?P<id>\d+)$')
SKIP_DIRS = {'.git', '__pycache__'}


def iter_text_files(path: Path):
    for file_path in path.rglob('*'):
        if not file_path.is_file():
            continue
        if any(part in SKIP_DIRS for part in file_path.parts):
            continue
        try:
            yield file_path, file_path.read_text(encoding='utf-8')
        except (UnicodeDecodeError, OSError):
            continue


def parse_param_tokens(param_str: str):
    tokens = [t.strip() for t in param_str.split(',') if t.strip()]
    taskid = None
    status = None
    tags = []
    timestamp = None
    for token in tokens:
        m_id = ID_RE.fullmatch(token)
        if m_id and taskid is None:
            taskid = f"#T{m_id.group('id')}"
            continue
        if token.startswith('status:'):
            status = token.split(':', 1)[1]
            continue
        if token.startswith('tags:'):
            inner = token.split(':', 1)[1].strip()
            inner = inner.strip('{}')
            tags = [x.strip() for x in inner.split(',') if x.strip()]
            continue
        if token.startswith('timestamp:'):
            timestamp = token.split(':', 1)[1]
            continue
        if token in ('new', 'open', 'in-progress', 'done') and status is None:
            status = token
            continue
        tags.append(token)
    return taskid, status, tags, timestamp


def current_timestamp():
    return datetime.now().strftime('%Y-%m-%dT%H:%M:%S')


def normalize_task_id(task_id: str):
    m = ID_RE.search(task_id)
    if not m:
        return task_id
    return f"#T{m.group('id')}"


def format_params(taskid: str, status: str, tags: list, timestamp=None):
    if not status:
        status = 'new'
    tags_part = ', '.join(tags) if tags else ''
    if timestamp:
        return f"{taskid}, status:{status}, tags: {{{tags_part}}}, timestamp:{timestamp}"
    return f"{taskid}, status:{status}, tags: {{{tags_part}}}"


def extract_existing_max_id(path: Path):
    max_id = 0
    for _, text in iter_text_files(path):
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            match = LINE_TASK_PATTERN.search(lines[i]) or BLOCK_TASK_PATTERN.search(lines[i])
            if match:
                taskid, _, _, _ = parse_param_tokens(match.group('params'))
                if taskid:
                    try:
                        val = int(ID_RE.fullmatch(taskid).group('id'))
                        if val > max_id:
                            max_id = val
                    except Exception:
                        pass
            i += 1
    return max_id


def collect_task_entries(path: Path):
    entries = []
    for file_path, text in iter_text_files(path):
        lines = text.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            m_line = LINE_TASK_PATTERN.search(line)
            m_block = BLOCK_TASK_PATTERN.search(line)
            if m_line:
                start = i
                i += 1
                while i < len(lines) and lines[i].lstrip().startswith('//'):
                    i += 1

                taskid, status, tags, _ = parse_param_tokens(m_line.group('params'))
                if taskid:
                    file_label = str(file_path.relative_to(path))
                    entries.append({
                        'taskid': taskid,
                        'status': status or 'new',
                        'tags': ', '.join(tags),
                        'file': f"{file_label}:{start + 1}",
                        'desc': m_line.group('desc').strip(),
                    })
                continue

            if m_block:
                start = i
                i += 1
                while i < len(lines):
                    if '*/' in lines[i]:
                        i += 1
                        break
                    i += 1

                taskid, status, tags, _ = parse_param_tokens(m_block.group('params'))
                if taskid:
                    file_label = str(file_path.relative_to(path))
                    entries.append({
                        'taskid': taskid,
                        'status': status or 'new',
                        'tags': ', '.join(tags),
                        'file': f"{file_label}:{start + 1}",
                        'desc': m_block.group('desc').strip(),
                    })
                continue

            i += 1
    return entries


def apply_update_to_file(file_path: Path, lines: list[str], start_idx: int, end_idx: int, replacement_lines: list[str]):
    new_lines = lines[:start_idx] + replacement_lines + lines[end_idx:]
    file_path.write_text('\n'.join(new_lines) + '\n', encoding='utf-8')
