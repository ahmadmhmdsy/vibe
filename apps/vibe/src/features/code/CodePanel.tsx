// features/code/CodePanel.tsx — Code editor with the workspace file tree.
// Displays generated files, allows editing, and syncs changes to the backend.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Editor from "@monaco-editor/react";
import { useCodeStore } from "./store";
import {
  Button,
  EmptyState,
  ErrorBanner,
  IconButton,
  Spinner,
  Splitter,
  StatusDot,
  Tree,
  type StatusKind,
  type TreeNode,
} from "../../components/ui";
import { Icon } from "../../components/icons/Icon";
import { detectLanguage } from "../../lib/format";
import { usePolling } from "../../hooks/usePolling";
import type { Theme } from "../../lib/theme";
import "./code.css";

type SaveState = "idle" | "saving" | "saved" | "error";

const TREE_WIDTH = { defaultValue: 220, min: 160, max: 420 } as const;

/** How the save indicator reads. Idle is deliberately silent: a file that has
 *  not been touched has nothing to report. */
const SAVE_STATUS: Record<Exclude<SaveState, "idle">, { status: StatusKind; label: string }> = {
  saving: { status: "running", label: "Saving" },
  saved: { status: "ok", label: "Saved" },
  error: { status: "error", label: "Save failed" },
};

/** One level of the workspace tree, before it is flattened into TreeNode rows. */
type Folder = {
  folders: Map<string, Folder>;
  files: string[];
};

/** Group workspace paths by their "/" segments so the tree mirrors the folder
 *  structure the agent wrote instead of a flat list. */
function buildTree(paths: readonly string[]): TreeNode[] {
  const root: Folder = { folders: new Map(), files: [] };

  for (const path of paths) {
    const segments = path.split("/").filter(Boolean);
    if (segments.length === 0) continue;
    const name = segments.pop() as string;
    let folder = root;
    for (const segment of segments) {
      let next = folder.folders.get(segment);
      if (!next) {
        next = { folders: new Map(), files: [] };
        folder.folders.set(segment, next);
      }
      folder = next;
    }
    folder.files.push(name);
  }

  const convert = (folder: Folder, prefix: string): TreeNode[] => {
    const folders: TreeNode[] = [...folder.folders.entries()].map(([name, child]) => {
      const id = prefix ? `${prefix}/${name}` : name;
      return {
        id,
        name,
        icon: <Icon name="folder" size={14} />,
        children: convert(child, id),
      };
    });
    const files: TreeNode[] = folder.files.map((name) => ({
      id: prefix ? `${prefix}/${name}` : name,
      name,
      icon: <Icon name="fileCode" size={14} />,
    }));

    return [...folders.sort(byName), ...files.sort(byName)];
  };

  return convert(root, "");
}

const byName = (a: TreeNode, b: TreeNode) => a.name.localeCompare(b.name);

export function CodePanel({
  sessionId,
  theme = "dark",
  /**
   * Whether the panel is the visible one. Polling for agent-written files runs
   * only while active, so a Code tab behind Preview costs no requests. Optional
   * and defaulting to true so the existing call site keeps its behaviour.
   */
  active = true,
}: {
  sessionId: string;
  /** Editor theme; follows the app theme so a light app is not a dark editor. */
  theme?: Theme;
  active?: boolean;
}) {
  const { files, selectedFile, contents, setSelectedFile, loadFiles, loadFile, saveFile } =
    useCodeStore();
  const saveTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  // Tagged with the file it belongs to, so switching files cannot show a stale
  // error and the effect never needs to reset state synchronously.
  const [fileError, setFileError] = useState<{ path: string; message: string } | null>(null);
  const [saveState, setSaveState] = useState<SaveState>("idle");
  const [treeWidth, setTreeWidth] = useState<number>(TREE_WIDTH.defaultValue);

  const nodes = useMemo(() => buildTree(files), [files]);
  // Folders start expanded. Only the user's own collapses are stored, so a file
  // the agent adds later appears open without re-opening what was closed.
  const [collapsedIds, setCollapsedIds] = useState<ReadonlySet<string>>(() => new Set<string>());
  const folderIds = useMemo(() => collectFolderIds(nodes), [nodes]);
  const expandedIds = useMemo(
    () => new Set(folderIds.filter((id) => !collapsedIds.has(id))),
    [folderIds, collapsedIds]
  );
  const filePaths = useMemo(() => new Set(files), [files]);

  const toggleFolder = useCallback((id: string) => {
    setCollapsedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  // The Tree toggles through its twisty; activating a folder row does the same,
  // so the whole row is a target rather than the 16px caret alone.
  const onSelect = useCallback(
    (node: TreeNode) => {
      if (filePaths.has(node.id)) setSelectedFile(node.id);
      else toggleFolder(node.id);
    },
    [filePaths, setSelectedFile, toggleFolder]
  );

  const refresh = useCallback(() => {
    loadFiles(sessionId)
      .then(() => setError(null))
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load files"));
  }, [sessionId, loadFiles]);

  // Refresh the file list (picks up agent-written files) while the tab is shown.
  usePolling(
    async () => {
      try {
        await loadFiles(sessionId);
        setError(null);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load files");
      }
    },
    { interval: 3000, enabled: active }
  );

  // Initial load
  useEffect(() => {
    loadFiles(sessionId)
      .then(() => setLoading(false))
      .catch((e) => {
        setError(e instanceof Error ? e.message : "Failed to load files");
        setLoading(false);
      });
  }, [sessionId]);

  // Load the selected file's content.
  useEffect(() => {
    if (!selectedFile) return;
    loadFile(sessionId, selectedFile)
      .then(() => {
        setFileError((cur) => (cur?.path === selectedFile ? null : cur));
      })
      .catch((e) => {
        // The store no longer swallows the failure, so say what happened
        // instead of showing an editor that silently rejects every keystroke.
        setFileError({
          path: selectedFile,
          message: e instanceof Error ? e.message : `Could not open ${selectedFile}.`,
        });
      });
  }, [selectedFile, sessionId]);

  const onEdit = (value: string | undefined) => {
    if (!selectedFile || value === undefined) return;
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => {
      setSaveError(null);
      setSaveState("saving");
      saveFile(sessionId, selectedFile, value)
        .then(() => setSaveState("saved"))
        .catch((e) => {
          setSaveState("error");
          setSaveError(e instanceof Error ? `Save failed: ${e.message}` : "Save failed.");
        });
    }, 800);
  };

  const saveStatus = saveState === "idle" ? null : SAVE_STATUS[saveState];

  return (
    <div className="panel panel-code code-panel">
      <div className="panel-header">
        {/* Identity, not a title: the shell's tab strip already says "Code".
            Empty when no file is open, rather than inventing a label. */}
        {selectedFile && (
          <span className="code-file-path" title={selectedFile}>
            {selectedFile}
          </span>
        )}
        <div className="panel-header-spacer" />
        <div className="panel-actions">
          {files.length > 0 && (
            <span className="code-file-count tnum">
              {files.length === 1 ? "1 file" : `${files.length} files`}
            </span>
          )}
          <IconButton
            label="Refresh file list"
            tooltipSide="bottom"
            onClick={refresh}
            disabled={loading}
          >
            <Icon name="retry" size={14} />
          </IconButton>
        </div>
      </div>

      {files.length === 0 && !loading && !error ? (
        <div className="panel-body" data-direction="column">
          <EmptyState
            icon={<Icon name="fileCode" size={24} />}
            title="No files yet"
            body="Files appear here once the agent writes them into this session's workspace."
            action={
              <Button variant="secondary" size="sm" onClick={refresh}>
                Check again
              </Button>
            }
          />
        </div>
      ) : (
        <div className="panel-body" data-direction="row" data-testid="code-layout">
          <div className="code-tree" style={{ flex: `0 0 ${treeWidth}px` }}>
            {loading && files.length === 0 ? (
              <div className="code-tree-status">
                <Spinner size="sm" label="Loading files" />
              </div>
            ) : (
              <Tree
                nodes={nodes}
                selectedId={selectedFile ?? undefined}
                onSelect={onSelect}
                expandedIds={expandedIds}
                onToggle={(node) => toggleFolder(node.id)}
                label="Workspace files"
                className="scroll-region"
              />
            )}
          </div>

          <Splitter
            value={treeWidth}
            min={TREE_WIDTH.min}
            max={TREE_WIDTH.max}
            defaultValue={TREE_WIDTH.defaultValue}
            orientation="vertical"
            label="Resize file tree"
            onChange={setTreeWidth}
          />

          <div className="code-editor">
            {/* The file path lives in the panel header, so this line carries
                only the thing that changes while the file stays open. */}
            <div className="code-editor-header">
              {saveError ? (
                <span className="code-save-error" role="alert">
                  {saveError}
                </span>
              ) : saveStatus ? (
                <span className="code-save-state">
                  <StatusDot status={saveStatus.status} label={saveStatus.label} />
                  <span className="code-save-label">{saveStatus.label}</span>
                </span>
              ) : null}
            </div>

            <div className="code-editor-body">
              {error && (
                <div className="code-editor-alert">
                  <ErrorBanner message={error} onRetry={refresh} />
                </div>
              )}
              {fileError?.path === selectedFile && (
                <div className="code-editor-alert">
                  <ErrorBanner message={fileError.message} onRetry={refresh} />
                </div>
              )}
              {selectedFile ? (
                <Editor
                  path={selectedFile}
                  language={detectLanguage(selectedFile)}
                  theme={theme === "light" ? "light" : "vs-dark"}
                  value={contents[selectedFile] ?? ""}
                  onChange={onEdit}
                />
              ) : (
                <EmptyState
                  icon={<Icon name="code" size={24} />}
                  title="No file open"
                  body="Choose a file from the tree to read or edit it."
                />
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** Every folder id in the tree, so expansion can be derived instead of stored. */
function collectFolderIds(nodes: readonly TreeNode[]): string[] {
  const ids: string[] = [];
  const walk = (list: readonly TreeNode[]) => {
    for (const node of list) {
      if (!node.children || node.children.length === 0) continue;
      ids.push(node.id);
      walk(node.children);
    }
  };
  walk(nodes);
  return ids;
}
