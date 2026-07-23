import type { Project } from "../src/api";
import type { ProjectEditorState } from "../src/projectRegistry.js";
import {
  backupPreviewStatus,
  formatBackupSize,
  formatProjectExport,
  importPreviewAliasOwnershipChanges,
  importPreviewAliasRenames,
  importPreviewStatus,
  parseProjectImportJson,
  projectEditorForRefresh,
  projectEditorFromProject,
} from "../src/projectRegistry.js";

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) {
    throw new Error(message);
  }
}

function project(id: string, name = id): Project {
  return {
    id,
    name,
    root_path: `/tmp/${id}`,
  };
}

const persistedCurrent = project("current", "Current Project");
const createdProject = project("created", "Created Project");
const draftEditor: ProjectEditorState = {
  ...projectEditorFromProject(project("draft", "Draft Project")),
  originalId: null,
  id: "draft",
  name: "Unsaved Draft",
};

function selectEditor({
  editorDirty,
  forceEditorRefresh,
  preferredProjectId,
  projects = [persistedCurrent, createdProject],
  currentProject = persistedCurrent,
}: {
  editorDirty: boolean;
  forceEditorRefresh?: boolean;
  preferredProjectId?: string | null;
  projects?: Project[];
  currentProject?: Project;
}) {
  return projectEditorForRefresh({
    currentEditor: draftEditor,
    editorDirty,
    projects,
    currentProject,
    options: {
      forceEditorRefresh,
      preferredProjectId,
    },
  });
}

function testDirtyNormalRefreshPreservesDraft() {
  const editor = selectEditor({ editorDirty: true });

  assert(editor === draftEditor, "dirty normal refresh should preserve draft editor");
  assert(editor.originalId === null, "dirty normal refresh should preserve draft originalId");
}

function testDirtyForcedRefreshReplacesDraft() {
  const editor = selectEditor({ editorDirty: true, forceEditorRefresh: true });

  assert(editor !== draftEditor, "forced refresh should replace draft editor");
  assert(editor.originalId === "current", "forced refresh should use current project by default");
}

function testForcedRefreshWithPreferredProjectSelectsIt() {
  const editor = selectEditor({
    editorDirty: true,
    forceEditorRefresh: true,
    preferredProjectId: "created",
  });

  assert(editor.originalId === "created", "preferred project should be selected");
  assert(editor.name === "Created Project", "preferred project values should be loaded");
}

function testMissingPreferredProjectFallsBackToCurrentProject() {
  const editor = selectEditor({
    editorDirty: true,
    forceEditorRefresh: true,
    preferredProjectId: "missing",
  });

  assert(editor.originalId === "current", "missing preferred project should fall back to current");
  assert(editor.name === "Current Project", "current project values should be loaded");
}

function testDeleteRefreshDoesNotKeepDeletedProject() {
  const deletedProjectId: string = "deleted";
  const remainingProject = project("remaining", "Remaining Project");
  const editor = selectEditor({
    editorDirty: true,
    forceEditorRefresh: true,
    preferredProjectId: null,
    projects: [remainingProject],
    currentProject: remainingProject,
  });

  assert(editor.originalId === "remaining", "delete refresh should select remaining project");
  assert(editor.originalId !== deletedProjectId, "delete refresh should not keep deleted project");
}

function testImportJsonParsingAndExportFormatting() {
  const parsed = parseProjectImportJson('{"version":1,"projects":[{"id":"demo"}]}');
  assert(typeof parsed === "object" && parsed !== null, "import JSON should parse");

  const formatted = formatProjectExport({ version: 1, projects: [project("demo")] });
  assert(formatted.endsWith("\n"), "formatted export should end with newline");
  assert(formatted.includes('"version": 1'), "formatted export should include version");
}

function testImportPreviewStatus() {
  assert(importPreviewStatus(null) === "Preview", "missing preview should be preview");
  assert(
    importPreviewStatus({
      ok: false,
      version: 1,
      resolution: "skip",
      counts: { projects: 1, creates: 0, updates: 0, skips: 0 },
      creates: [],
      replaces: [],
      skips: [],
      warnings: [],
      errors: ["bad"],
    }) === "Preview has validation errors",
    "errors should be surfaced",
  );
  assert(
    importPreviewStatus({
      ok: true,
      version: 1,
      resolution: "skip",
      counts: { projects: 1, creates: 1, updates: 0, skips: 0 },
      creates: [project("demo")],
      replaces: [],
      skips: [],
      warnings: [],
      errors: [],
    }) === "Preview ready for approval",
    "valid preview should be ready",
  );
}

function testImportPreviewAliasOwnershipChanges() {
  const changes = importPreviewAliasOwnershipChanges({
    ok: true,
    version: 1,
    resolution: "replace",
    counts: { projects: 1, creates: 1, updates: 0, skips: 0 },
    creates: [project("beta")],
    replaces: [],
    skips: [],
    alias_updates: [
      {
        project_id: "alpha",
        remove_aliases: ["shared"],
        import_project_id: "beta",
        assign_aliases: ["shared"],
      },
    ],
    warnings: [],
    errors: [],
  });

  assert(changes.length === 1, "alias ownership change should render one row");
  assert(
    changes[0].text === 'Remove alias "shared" from alpha; assign to beta',
    "alias ownership change should describe source and recipient",
  );
}

function testImportPreviewAliasRenames() {
  const changes = importPreviewAliasRenames({
    ok: true,
    version: 1,
    resolution: "rename",
    counts: { projects: 1, creates: 1, updates: 0, skips: 0 },
    creates: [project("beta-import")],
    replaces: [],
    skips: [],
    alias_renames: [
      {
        project_id: "beta-import",
        from_alias: "beta",
        to_alias: "beta-beta-import",
      },
    ],
    warnings: [],
    errors: [],
  });

  assert(changes.length === 1, "alias rename should render one row");
  assert(
    changes[0].text === "Alias renamed: beta -> beta-beta-import",
    "alias rename should describe final persisted alias",
  );
}

function testBackupPreviewStatusAndErrors() {
  assert(backupPreviewStatus(null) === "Preview", "missing backup preview should be preview");
  assert(
    backupPreviewStatus({
      ok: false,
      filename: "backup.json",
      created_at: "2026-07-23T12:00:00",
      project_count: 0,
      current_project: "",
      projects: [],
      warnings: [],
      errors: ["Invalid JSON"],
    }) === "Preview has validation errors",
    "backup validation errors should be surfaced",
  );
  assert(
    backupPreviewStatus({
      ok: true,
      filename: "backup.json",
      created_at: "2026-07-23T12:00:00",
      project_count: 1,
      current_project: "void",
      projects: [{ id: "void", name: "Void" }],
      warnings: [],
      errors: [],
    }) === "Preview ready for approval",
    "valid backup preview should be ready",
  );
}

function testBackupSizeFormatting() {
  assert(formatBackupSize(42) === "42 B", "small backup size should render bytes");
  assert(formatBackupSize(2048) === "2.0 KB", "large backup size should render KB");
  assert(formatBackupSize(null) === "unknown", "missing backup size should be unknown");
}

testDirtyNormalRefreshPreservesDraft();
testDirtyForcedRefreshReplacesDraft();
testForcedRefreshWithPreferredProjectSelectsIt();
testMissingPreferredProjectFallsBackToCurrentProject();
testDeleteRefreshDoesNotKeepDeletedProject();
testImportJsonParsingAndExportFormatting();
testImportPreviewStatus();
testImportPreviewAliasOwnershipChanges();
testImportPreviewAliasRenames();
testBackupPreviewStatusAndErrors();
testBackupSizeFormatting();

console.log("Project Registry state selection tests passed.");
