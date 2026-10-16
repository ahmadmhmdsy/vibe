// components/ui/Tree.tsx — an accessible file/entity tree.
//
// Replaces the flat file list in the code panel. Rows are rendered flat and
// depth is conveyed with aria-level, which keeps keyboard navigation a matter
// of moving between visible rows instead of walking a nested DOM.

import { useCallback, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Icon } from "../icons/Icon";

export interface TreeNode {
  id: string;
  name: string;
  children?: readonly TreeNode[];
  /** Overrides the folder/file glyph. */
  icon?: ReactNode;
  /** Right-aligned secondary content, e.g. a modified indicator. */
  meta?: ReactNode;
  /** Accessible description appended to the row name. */
  description?: string;
}

export interface TreeProps {
  nodes: readonly TreeNode[];
  selectedId?: string;
  onSelect: (node: TreeNode) => void;
  expandedIds: ReadonlySet<string>;
  onToggle: (node: TreeNode) => void;
  /** Accessible name for the tree. Required. */
  label: string;
  /** Indent per depth level, in px. */
  indent?: number;
  className?: string;
}

interface FlatRow {
  node: TreeNode;
  depth: number;
  hasChildren: boolean;
  expanded: boolean;
  parentId: string | null;
}

export function Tree({
  nodes,
  selectedId,
  onSelect,
  expandedIds,
  onToggle,
  label,
  indent = 12,
  className,
}: TreeProps) {
  const [focusedId, setFocusedId] = useState<string | undefined>(selectedId);
  const listRef = useRef<HTMLDivElement>(null);

  const rows = useMemo(() => {
    const out: FlatRow[] = [];
    const walk = (list: readonly TreeNode[], depth: number, parentId: string | null) => {
      for (const node of list) {
        const hasChildren = Boolean(node.children && node.children.length > 0);
        const expanded = hasChildren && expandedIds.has(node.id);
        out.push({ node, depth, hasChildren, expanded, parentId });
        if (expanded && node.children) walk(node.children, depth + 1, node.id);
      }
    };
    walk(nodes, 0, null);
    return out;
  }, [nodes, expandedIds]);

  const activeId = rows.some((row) => row.node.id === focusedId)
    ? focusedId
    : rows.some((row) => row.node.id === selectedId)
      ? selectedId
      : rows[0]?.node.id;

  const focusRow = useCallback((id: string) => {
    setFocusedId(id);
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>('[role="treeitem"]');
    if (!buttons) return;
    for (const button of buttons) {
      if (button.dataset.nodeId === id) {
        button.focus();
        return;
      }
    }
  }, []);

  const handleKeyDown = useCallback(
    (event: KeyboardEvent<HTMLElement>, row: FlatRow) => {
      const index = rows.findIndex((candidate) => candidate.node.id === row.node.id);

      const go = (target: FlatRow | undefined) => {
        if (!target) return;
        event.preventDefault();
        focusRow(target.node.id);
      };

      switch (event.key) {
        case "ArrowDown":
          go(rows[index + 1]);
          return;
        case "ArrowUp":
          go(rows[index - 1]);
          return;
        case "Home":
          go(rows[0]);
          return;
        case "End":
          go(rows[rows.length - 1]);
          return;
        case "ArrowRight":
          if (row.hasChildren && !row.expanded) {
            event.preventDefault();
            onToggle(row.node);
          } else if (row.hasChildren) {
            go(rows[index + 1]);
          }
          return;
        case "ArrowLeft": {
          if (row.hasChildren && row.expanded) {
            event.preventDefault();
            onToggle(row.node);
            return;
          }
          const parent = rows.find((candidate) => candidate.node.id === row.parentId);
          go(parent);
          return;
        }
        default:
          return;
      }
    },
    [focusRow, onToggle, rows]
  );

  if (rows.length === 0) return null;

  return (
    <div
      ref={listRef}
      role="tree"
      aria-label={label}
      className={["tree", className].filter(Boolean).join(" ")}
    >
      {rows.map((row) => {
        const selected = row.node.id === selectedId;
        const siblings = rows.filter((candidate) => candidate.parentId === row.parentId);
        return (
          <div key={row.node.id} role="none" className="tree-group">
            <button
              type="button"
              role="treeitem"
              data-node-id={row.node.id}
              aria-level={row.depth + 1}
              aria-posinset={siblings.findIndex((c) => c.node.id === row.node.id) + 1}
              aria-setsize={siblings.length}
              aria-selected={selected}
              aria-expanded={row.hasChildren ? row.expanded : undefined}
              tabIndex={row.node.id === activeId ? 0 : -1}
              className="tree-item"
              style={{ paddingLeft: `${8 + row.depth * indent}px` }}
              onClick={() => {
                setFocusedId(row.node.id);
                onSelect(row.node);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(row.node);
                  return;
                }
                handleKeyDown(event, row);
              }}
            >
              {row.hasChildren ? (
                <span
                  className="tree-twisty"
                  onClick={(event) => {
                    event.stopPropagation();
                    onToggle(row.node);
                  }}
                >
                  <Icon name={row.expanded ? "chevronDown" : "chevronRight"} size={12} />
                </span>
              ) : (
                <span className="tree-twisty-spacer" />
              )}
              {row.node.icon ?? (
                <Icon
                  name={row.hasChildren ? (row.expanded ? "folderOpen" : "folder") : "file"}
                  size={14}
                />
              )}
              <span className="tree-item-name">{row.node.name}</span>
              {row.node.meta ? <span className="tree-item-meta">{row.node.meta}</span> : null}
            </button>
          </div>
        );
      })}
    </div>
  );
}
