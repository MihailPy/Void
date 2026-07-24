# Changelog

## 1.11.0

### Added

- Project registry snapshots with automatic pre-mutation capture.
- Manual snapshot create, list, validate, diff, restore, delete, and prune tools.
- Snapshot API endpoints and Projects Web UI controls.
- Deterministic structural snapshot diffs, including unknown root and nested fields.

### Safety

- Snapshot writes are local JSON files in a separate snapshot directory from backups.
- Registry mutations now include replayable pre-mutation snapshot IDs in Activity History.
- Restore creates a pre-restore snapshot before replacing the registry.
- Snapshot delete and prune require approval; prune verifies planned file size and hash.

## 1.10.0

### Added

- Project Registry backup, validation, restore, listing, and deletion tools.
- Backup and restore controls in the Projects Web UI.
- Project backup files use a `backup` metadata envelope plus an exact
  `registry` payload so unknown registry fields are preserved.

### Safety

- Restore and delete require approval and revalidate before state changes.
- Backup restore uses one registry save and one Activity History entry.
- Same-second backup filename collisions receive deterministic numeric suffixes,
  and existing backup files are never overwritten.

## 1.9.0

### Added

- Project Workspace.
- Finder, GitHub, browser, and terminal workspace targets.
- Smart iTerm2 workspace reuse.
- Editable Workspace Preferences.
- Atomic preference approval flow.

### Improved

- Project clarification.
- Activity History metadata for workspace workflows.
- Deterministic project workflows.
- Inline approval flow.

### Safety

- Approval is required for workspace-opening actions and configuration writes.
- Invalid workspace preference batches do not partially save.
