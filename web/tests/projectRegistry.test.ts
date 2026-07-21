import type { Project } from "../src/api";
import type { ProjectEditorState } from "../src/projectRegistry.js";
import {
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

testDirtyNormalRefreshPreservesDraft();
testDirtyForcedRefreshReplacesDraft();
testForcedRefreshWithPreferredProjectSelectsIt();
testMissingPreferredProjectFallsBackToCurrentProject();
testDeleteRefreshDoesNotKeepDeletedProject();

console.log("Project Registry state selection tests passed.");
