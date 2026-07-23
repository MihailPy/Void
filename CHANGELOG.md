# Changelog

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
