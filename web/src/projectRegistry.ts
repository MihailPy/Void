import type {
  Project,
  ProjectBackupPreview,
  ProjectExportPayload,
  ProjectImportPreview,
} from "./api";

export type WorkspacePreferenceForm = {
  terminalApp: string;
  terminalCommand: string;
  terminalReuseExisting: string;
  terminalOpenMode: string;
  terminalProfile: string;
  terminalWindowBounds: string;
  browserApp: string;
  fileManagerApp: string;
};

export type ProjectCommandRow = {
  id: string;
  key: string;
  command: string;
};

export type ProjectEditorState = {
  originalId: string | null;
  duplicateSourceId: string | null;
  id: string;
  name: string;
  rootPath: string;
  repoUrl: string;
  aliases: string[];
  commands: ProjectCommandRow[];
  workspace: WorkspacePreferenceForm;
};

export const emptyWorkspacePreferenceForm: WorkspacePreferenceForm = {
  terminalApp: "",
  terminalCommand: "",
  terminalReuseExisting: "",
  terminalOpenMode: "",
  terminalProfile: "",
  terminalWindowBounds: "",
  browserApp: "",
  fileManagerApp: "",
};

export function emptyProjectEditorState(): ProjectEditorState {
  return {
    originalId: null,
    duplicateSourceId: null,
    id: "",
    name: "",
    rootPath: ".",
    repoUrl: "",
    aliases: [],
    commands: [],
    workspace: emptyWorkspacePreferenceForm,
  };
}

function stringFromUnknown(value: unknown) {
  return typeof value === "string" ? value : value == null ? "" : String(value);
}

export function workspaceFormFromPreferences(
  preferences: Record<string, Record<string, unknown>>,
): WorkspacePreferenceForm {
  const terminal = preferences.terminal ?? {};
  const browser = preferences.browser ?? {};
  const fileManager = preferences.file_manager ?? {};
  return {
    terminalApp: stringFromUnknown(terminal.app),
    terminalCommand: stringFromUnknown(terminal.command),
    terminalReuseExisting: stringFromUnknown(terminal.reuse_existing),
    terminalOpenMode: stringFromUnknown(terminal.open_mode),
    terminalProfile: stringFromUnknown(terminal.profile),
    terminalWindowBounds: stringFromUnknown(terminal.window_bounds),
    browserApp: stringFromUnknown(browser.app),
    fileManagerApp: stringFromUnknown(fileManager.app),
  };
}

export function workspaceFromForm(form: WorkspacePreferenceForm) {
  const workspace: Record<string, Record<string, string>> = {};
  const terminal: Record<string, string> = {};
  if (form.terminalApp) terminal.app = form.terminalApp;
  if (form.terminalCommand) terminal.command = form.terminalCommand;
  if (form.terminalReuseExisting) terminal.reuse_existing = form.terminalReuseExisting;
  if (form.terminalOpenMode) terminal.open_mode = form.terminalOpenMode;
  if (form.terminalProfile) terminal.profile = form.terminalProfile;
  if (form.terminalWindowBounds) terminal.window_bounds = form.terminalWindowBounds;
  if (Object.keys(terminal).length > 0) workspace.terminal = terminal;
  if (form.browserApp) workspace.browser = { app: form.browserApp };
  if (form.fileManagerApp) workspace.file_manager = { app: form.fileManagerApp };
  return workspace;
}

export function projectEditorFromProject(
  project: Project,
  duplicateSourceId: string | null = null,
): ProjectEditorState {
  return {
    originalId: duplicateSourceId ? null : project.id ?? null,
    duplicateSourceId,
    id: project.id ?? "",
    name: project.name ?? "",
    rootPath: project.root_path ?? ".",
    repoUrl: project.repo_url ?? "",
    aliases: [...(project.aliases ?? [])],
    commands: Object.entries(project.commands ?? {}).map(([key, command], index) => ({
      id: `${key || "command"}-${index}`,
      key,
      command,
    })),
    workspace: workspaceFormFromPreferences(project.workspace ?? {}),
  };
}

export function projectPayloadFromEditor(editor: ProjectEditorState): Project {
  return {
    id: editor.id.trim(),
    name: editor.name.trim(),
    root_path: editor.rootPath.trim(),
    repo_url: editor.repoUrl.trim(),
    aliases: editor.aliases.map((alias) => alias.trim()).filter(Boolean),
    commands: editor.commands.reduce<Record<string, string>>((payload, row) => {
      payload[row.key.trim()] = row.command;
      return payload;
    }, {}),
    workspace: workspaceFromForm(editor.workspace),
  };
}

export type ProjectEditorRefreshOptions = {
  forceEditorRefresh?: boolean;
  preferredProjectId?: string | null;
};

export function projectEditorForRefresh({
  currentEditor,
  editorDirty,
  projects,
  currentProject,
  options,
}: {
  currentEditor: ProjectEditorState;
  editorDirty: boolean;
  projects: Project[];
  currentProject: Project;
  options?: ProjectEditorRefreshOptions;
}) {
  if (editorDirty && !options?.forceEditorRefresh) {
    return currentEditor;
  }

  const selectedProject = options?.preferredProjectId
    ? projects.find((project) => project.id === options.preferredProjectId)
    : null;

  return projectEditorFromProject(selectedProject ?? currentProject);
}

export function parseProjectImportJson(input: string): unknown {
  const cleanInput = input.trim();
  if (!cleanInput) {
    throw new Error("Import JSON is required.");
  }
  return JSON.parse(cleanInput) as unknown;
}

export function formatProjectExport(exportPayload: ProjectExportPayload): string {
  return `${JSON.stringify(exportPayload, null, 2)}\n`;
}

export function importPreviewStatus(preview: ProjectImportPreview | null) {
  if (!preview) {
    return "Preview";
  }
  if (preview.errors.length > 0) {
    return "Preview has validation errors";
  }
  return "Preview ready for approval";
}

export function importPreviewAliasOwnershipChanges(preview: ProjectImportPreview | null) {
  return (preview?.alias_updates ?? []).flatMap((update) =>
    update.remove_aliases.map((alias) => ({
      key: `${update.project_id}-${update.import_project_id}-${alias}`,
      text: `Remove alias "${alias}" from ${update.project_id}; assign to ${update.import_project_id}`,
    })),
  );
}

export function importPreviewAliasRenames(preview: ProjectImportPreview | null) {
  return (preview?.alias_renames ?? []).map((rename) => ({
    key: `${rename.project_id}-${rename.from_alias}-${rename.to_alias}`,
    text: `Alias renamed: ${rename.from_alias} -> ${rename.to_alias}`,
  }));
}

export function backupPreviewStatus(preview: ProjectBackupPreview | null) {
  if (!preview) {
    return "Preview";
  }
  if (preview.errors.length > 0) {
    return "Preview has validation errors";
  }
  return "Preview ready for approval";
}

export function formatBackupSize(size: number | null | undefined) {
  if (!Number.isFinite(size ?? Number.NaN)) {
    return "unknown";
  }
  const bytes = Number(size);
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  return `${(bytes / 1024).toFixed(1)} KB`;
}
