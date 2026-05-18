from pathlib import Path

from .parsing import BLOCK_TASK_PATTERN, LINE_TASK_PATTERN, current_timestamp, normalize_task_id, parse_param_tokens


def _prompt_field(label: str, default: str) -> str | None:
    value = input(f"{label} [{default}]: ").strip()
    if value.lower() in {'q', 'quit', 'skip'}:
        return None
    return value or default


def text_edit_dialog(file_path: Path, default_taskid, default_status, default_tags, default_timestamp, default_desc, default_depends_on):
    print(f"Editing TASK in: {file_path}")
    if default_desc:
        print("Description:")
        for line in default_desc.splitlines():
            print(f"  {line}")
    print("Enter new values or press Enter to keep the default. Type 'q' to cancel.")

    taskid = _prompt_field('Task ID', default_taskid)
    if taskid is None:
        return None

    status = _prompt_field('Status', default_status)
    if status is None:
        return None

    tags_s = _prompt_field('Tags (comma separated)', ', '.join(default_tags))
    if tags_s is None:
        return None

    depends_s = _prompt_field('Depends on (comma separated)', ', '.join(default_depends_on))
    if depends_s is None:
        return None

    timestamp = _prompt_field('Timestamp', default_timestamp)
    if timestamp is None:
        return None

    tags = [t.strip() for t in tags_s.split(',') if t.strip()]
    depends_on = [normalize_task_id(t.strip()) for t in depends_s.split(',') if t.strip()]
    return taskid, status, tags, default_desc, timestamp, depends_on


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

    taskid, status, tags, timestamp, depends_on = parse_param_tokens(params)
    if not taskid:
        taskid = f'#{next_id}'
    if not timestamp:
        timestamp = current_timestamp()

    return text_edit_dialog(file_path, taskid, status or 'new', tags, timestamp, desc, depends_on)
