// components/ui/index.ts — the public surface of the UI kit.
//
// Features import from here, not from individual files, so the kit can be
// reorganised without touching call sites.

export { Badge, type BadgeProps, type BadgeTone } from "./Badge";
export { Button, type ButtonProps } from "./Button";
export { CommandPalette } from "./CommandPalette";
export { ConfirmDialog } from "./ConfirmDialog";
export { ConnectionBanner } from "./ConnectionBanner";
export { EmptyState, type EmptyStateProps } from "./EmptyState";
export { ErrorBanner } from "./ErrorBanner";
export { ErrorBoundary } from "./ErrorBoundary";
export { IconButton, type IconButtonProps } from "./IconButton";
export { Kbd, type KbdProps } from "./Kbd";
export { Loading } from "./Loading";
export { Menu, type MenuEntry, type MenuItemDef, type MenuProps } from "./Menu";
export { Modal, type ModalProps } from "./Modal";
export { ScrollArea, type ScrollAreaProps } from "./ScrollArea";
export { SearchField, type SearchFieldProps } from "./SearchField";
export { ShortcutsHelp } from "./ShortcutsHelp";
export { Skeleton, type SkeletonProps } from "./Skeleton";
export { Spinner } from "./Spinner";
export { Splitter, type SplitterProps } from "./Splitter";
export { StatusDot, type StatusDotProps, type StatusKind } from "./StatusDot";
export { TabPanel, Tabs, type TabItem, type TabsProps } from "./Tabs";
export { ToastProvider, useToast } from "./Toast";
export { Tooltip, type TooltipProps, type TooltipSide } from "./Tooltip";
export { Tree, type TreeNode, type TreeProps } from "./Tree";
