# easy-task

`easy-task` is a simple Python CLI tool for finding and managing inline `TASK(...)` comments in source files.

## Features

- Scan a directory tree for `TASK(...)` comments in files
- Assign sequential `#T...` task IDs automatically
- Keep task metadata such as `status`, `tags`, and `timestamp`
- Edit task metadata using a curses-based form
- List tasks in a scrollable terminal
- Print task statistics grouped by status and tags

## Usage

```bash
python3 tasks-app.py scan [path]
python3 tasks-app.py list [path]
python3 tasks-app.py stats [path]
python3 tasks-app.py edit <taskId> [path]
```

### Commands

- `scan [path]`
  - Searches the directory for `TASK(...)` comments
  - Assigns IDs to untagged tasks
  - Adds missing timestamps to existing tasks
  - Prompts for task metadata if needed

- `list [path]`
  - Shows only tasks that already have assigned IDs
  - Displays a curses-based table UI when running in a terminal
  - Falls back to plain text output if curses is unavailable

- `stats [path]`
  - Summarizes total tasks, tasks with IDs, tasks without IDs
  - Groups task counts by status and by tag

- `edit <taskId> [path]`
  - Opens the task metadata editor for an existing task ID
  - Supports `#T123`, `T123`, or `123` as the task identifier

## Task format

Tasks are detected in either line-comment or block-comment form:

```cpp
// TASK(new, tags:{bug}): Fix the login flow
```

```c
/* TASK(status:open, tags:{ui, bug}): Improve form validation */
```

Metadata supports:

- `#T<n>` task ID
- `status:<value>`
- `tags:{tag1, tag2}`
- `timestamp:<ISO timestamp>`

## Tests

Run the unit tests with:

```bash
python3 -m unittest discover -s tests
```

The same test command runs in GitHub Actions on pushes and pull requests.

## Notes

- The tool recursively scans subdirectories by default
- It skips `.git` and `__pycache__`
