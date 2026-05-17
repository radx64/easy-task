import argparse
from pathlib import Path

from .commands import edit_task, list_tasks, scan, search_tasks, stats


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
    elif args.command == 'search':
        search_tasks(Path(args.path), args.query)
    elif args.command == 'stats':
        stats(Path(args.path))
    elif args.command == 'edit':
        edit_task(Path(args.path), args.taskId)
    else:
        parser.print_help()
