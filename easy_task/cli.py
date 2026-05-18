import argparse
from pathlib import Path

from .commands import deps, edit_task, list_tasks, scan, search_tasks, stats, display_task


def main():
    parser = argparse.ArgumentParser(
        description='easy-task: scan for inline TASK comments'
    )
    subparsers = parser.add_subparsers(dest='command')

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

    search_parser = subparsers.add_parser(
        'search', help='List TASK comments matching a search string'
    )
    search_parser.add_argument(
        'query', help='Search string to filter tasks'
    )
    search_parser.add_argument(
        'path', nargs='?', default='.', help='Directory to scan (default: current directory)'
    )

    deps_parser = subparsers.add_parser(
        'deps', help='Show task dependencies and dependents for a given task ID'
    )
    deps_parser.add_argument(
        'taskId', help='Task ID to inspect, e.g. #123'
    )
    deps_parser.add_argument(
        'path', nargs='?', default='.', help='Directory containing TASK comments (default: current directory)'
    )

    display_parser = subparsers.add_parser(
        'display', help='Display full task metadata and description for a given task ID'
    )
    display_parser.add_argument(
        'taskId', help='Task ID to display, e.g. #123'
    )
    display_parser.add_argument(
        'path', nargs='?', default='.', help='Directory containing TASK comments (default: current directory)'
    )

    edit_parser = subparsers.add_parser(
        'edit', help='Edit the metadata of an existing TASK by ID'
    )
    edit_parser.add_argument(
        'taskId', help='Task ID to edit, e.g. #123'
    )
    edit_parser.add_argument(
        'path', nargs='?', default='.', help='Directory containing TASK comments (default: current directory)'
    )

    args = parser.parse_args()
    if args.command == 'scan':
        scan(Path(args.path))
    elif args.command == 'list':
        list_tasks(Path(args.path))
    elif args.command == 'search':
        search_tasks(Path(args.path), args.query)
    elif args.command == 'stats':
        stats(Path(args.path))
    elif args.command == 'deps':
        deps(Path(args.path), args.taskId)
    elif args.command == 'display':
        display_task(Path(args.path), args.taskId)
    elif args.command == 'edit':
        edit_task(Path(args.path), args.taskId)
    else:
        parser.print_help()
