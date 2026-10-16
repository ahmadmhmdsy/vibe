// components/icons/Icon.tsx — the product's single icon entry point.
//
// Features never import from the icon library directly. They ask for a
// semantic name ("chevronRight", "retry", "tool") and this module decides
// which glyph, which weight, and which size that maps to. Swapping the icon
// set, or restyling every icon in the product, is then one file.
//
// Icons are imported one module at a time, never from the package root. The
// root barrel statically re-exports all 1512 glyphs plus the whole SSR tree
// (~4800 modules), and Rollup cannot shake that namespace import away — it
// alone accounted for a 697 kB main chunk. A deep import costs one module per
// glyph actually used.
import type { IconWeight } from "@phosphor-icons/react";
import { ArrowClockwise } from "@phosphor-icons/react/ArrowClockwise";
import { ArrowDown } from "@phosphor-icons/react/ArrowDown";
import { ArrowElbowDownLeft } from "@phosphor-icons/react/ArrowElbowDownLeft";
import { ArrowLeft } from "@phosphor-icons/react/ArrowLeft";
import { ArrowRight } from "@phosphor-icons/react/ArrowRight";
import { ArrowSquareOut } from "@phosphor-icons/react/ArrowSquareOut";
import { ArrowUp } from "@phosphor-icons/react/ArrowUp";
import { ArrowsIn } from "@phosphor-icons/react/ArrowsIn";
import { ArrowsOut } from "@phosphor-icons/react/ArrowsOut";
import { Bookmark } from "@phosphor-icons/react/Bookmark";
import { Broadcast } from "@phosphor-icons/react/Broadcast";
import { Broom } from "@phosphor-icons/react/Broom";
import { Bug } from "@phosphor-icons/react/Bug";
import { CaretDoubleRight } from "@phosphor-icons/react/CaretDoubleRight";
import { CaretDown } from "@phosphor-icons/react/CaretDown";
import { CaretLeft } from "@phosphor-icons/react/CaretLeft";
import { CaretRight } from "@phosphor-icons/react/CaretRight";
import { CaretUp } from "@phosphor-icons/react/CaretUp";
import { ChatCircle } from "@phosphor-icons/react/ChatCircle";
import { ChatTeardropText } from "@phosphor-icons/react/ChatTeardropText";
import { Check } from "@phosphor-icons/react/Check";
import { CheckCircle } from "@phosphor-icons/react/CheckCircle";
import { CheckSquare } from "@phosphor-icons/react/CheckSquare";
import { Circle } from "@phosphor-icons/react/Circle";
import { CircleNotch } from "@phosphor-icons/react/CircleNotch";
import { Clock } from "@phosphor-icons/react/Clock";
import { Code } from "@phosphor-icons/react/Code";
import { Columns } from "@phosphor-icons/react/Columns";
import { Command } from "@phosphor-icons/react/Command";
import { Copy } from "@phosphor-icons/react/Copy";
import { CornersIn } from "@phosphor-icons/react/CornersIn";
import { CornersOut } from "@phosphor-icons/react/CornersOut";
import { Cpu } from "@phosphor-icons/react/Cpu";
import { CursorClick } from "@phosphor-icons/react/CursorClick";
import { Database } from "@phosphor-icons/react/Database";
import { DotsThree } from "@phosphor-icons/react/DotsThree";
import { DotsThreeVertical } from "@phosphor-icons/react/DotsThreeVertical";
import { Download } from "@phosphor-icons/react/Download";
import { Eye } from "@phosphor-icons/react/Eye";
import { EyeSlash } from "@phosphor-icons/react/EyeSlash";
import { File } from "@phosphor-icons/react/File";
import { FileCode } from "@phosphor-icons/react/FileCode";
import { FileText } from "@phosphor-icons/react/FileText";
import { Flag } from "@phosphor-icons/react/Flag";
import { FolderOpen } from "@phosphor-icons/react/FolderOpen";
import { FolderSimple } from "@phosphor-icons/react/FolderSimple";
import { Funnel } from "@phosphor-icons/react/Funnel";
import { Gear } from "@phosphor-icons/react/Gear";
import { GitBranch } from "@phosphor-icons/react/GitBranch";
import { Globe } from "@phosphor-icons/react/Globe";
import { Hourglass } from "@phosphor-icons/react/Hourglass";
import { House } from "@phosphor-icons/react/House";
import { Image } from "@phosphor-icons/react/Image";
import { Info } from "@phosphor-icons/react/Info";
import { Key } from "@phosphor-icons/react/Key";
import { Layout } from "@phosphor-icons/react/Layout";
import { Lightning } from "@phosphor-icons/react/Lightning";
import { ListBullets } from "@phosphor-icons/react/ListBullets";
import { ListChecks } from "@phosphor-icons/react/ListChecks";
import { Lock } from "@phosphor-icons/react/Lock";
import { MagicWand } from "@phosphor-icons/react/MagicWand";
import { MagnifyingGlass } from "@phosphor-icons/react/MagnifyingGlass";
import { Monitor } from "@phosphor-icons/react/Monitor";
import { Moon } from "@phosphor-icons/react/Moon";
import { NotePencil } from "@phosphor-icons/react/NotePencil";
import { Package } from "@phosphor-icons/react/Package";
import { Palette } from "@phosphor-icons/react/Palette";
import { Paperclip } from "@phosphor-icons/react/Paperclip";
import { PencilSimple } from "@phosphor-icons/react/PencilSimple";
import { Play } from "@phosphor-icons/react/Play";
import { Plus } from "@phosphor-icons/react/Plus";
import { Pulse } from "@phosphor-icons/react/Pulse";
import { PushPin } from "@phosphor-icons/react/PushPin";
import { Question } from "@phosphor-icons/react/Question";
import { Robot } from "@phosphor-icons/react/Robot";
import { Rows } from "@phosphor-icons/react/Rows";
import { Seal } from "@phosphor-icons/react/Seal";
import { ShieldCheck } from "@phosphor-icons/react/ShieldCheck";
import { Sidebar } from "@phosphor-icons/react/Sidebar";
import { SidebarSimple } from "@phosphor-icons/react/SidebarSimple";
import { SlidersHorizontal } from "@phosphor-icons/react/SlidersHorizontal";
import { Sparkle } from "@phosphor-icons/react/Sparkle";
import { Spinner } from "@phosphor-icons/react/Spinner";
import { Square } from "@phosphor-icons/react/Square";
import { SquaresFour } from "@phosphor-icons/react/SquaresFour";
import { Star } from "@phosphor-icons/react/Star";
import { Stop } from "@phosphor-icons/react/Stop";
import { Sun } from "@phosphor-icons/react/Sun";
import { Table } from "@phosphor-icons/react/Table";
import { Tag } from "@phosphor-icons/react/Tag";
import { Target } from "@phosphor-icons/react/Target";
import { Terminal } from "@phosphor-icons/react/Terminal";
import { TextAa } from "@phosphor-icons/react/TextAa";
import { Timer } from "@phosphor-icons/react/Timer";
import { Trash } from "@phosphor-icons/react/Trash";
import { TreeStructure } from "@phosphor-icons/react/TreeStructure";
import { Upload } from "@phosphor-icons/react/Upload";
import { Warning } from "@phosphor-icons/react/Warning";
import { WarningCircle } from "@phosphor-icons/react/WarningCircle";
import { Wrench } from "@phosphor-icons/react/Wrench";
import { X } from "@phosphor-icons/react/X";
import { XCircle } from "@phosphor-icons/react/XCircle";

/** Semantic name → glyph. Names describe meaning, not shape, so the glyph
 *  underneath can change without touching a single call site. */
export const ICONS = {
  // actions
  add: Plus,
  search: MagnifyingGlass,
  settings: Gear,
  close: X,
  check: Check,
  select: CheckSquare,
  copy: Copy,
  edit: PencilSimple,
  trash: Trash,
  download: Download,
  upload: Upload,
  retry: ArrowClockwise,
  external: ArrowSquareOut,
  attach: Paperclip,
  more: DotsThree,
  moreVertical: DotsThreeVertical,
  filter: Funnel,
  sliders: SlidersHorizontal,
  clean: Broom,
  pin: PushPin,
  resize: CornersOut,
  resizeSmall: CornersIn,

  // navigation
  chevronRight: CaretRight,
  chevronDown: CaretDown,
  chevronLeft: CaretLeft,
  chevronUp: CaretUp,
  enter: ArrowElbowDownLeft,
  skip: CaretDoubleRight,
  arrowUp: ArrowUp,
  arrowDown: ArrowDown,
  arrowLeft: ArrowLeft,
  arrowRight: ArrowRight,
  expand: ArrowsOut,
  collapse: ArrowsIn,
  panelLeft: SidebarSimple,
  panelRight: Sidebar,
  home: House,

  // status
  info: Info,
  success: CheckCircle,
  warning: Warning,
  warningCircle: WarningCircle,
  error: XCircle,
  question: Question,
  verified: Seal,
  shield: ShieldCheck,
  pulse: Pulse,
  clock: Clock,
  timer: Timer,
  hourglass: Hourglass,
  spinner: CircleNotch,
  spinnerDots: Spinner,
  circle: Circle,
  square: Square,

  // product
  chat: ChatCircle,
  message: ChatTeardropText,
  note: NotePencil,
  code: Code,
  terminal: Terminal,
  file: File,
  fileCode: FileCode,
  fileText: FileText,
  folder: FolderSimple,
  folderOpen: FolderOpen,
  tree: TreeStructure,
  table: Table,
  layout: Layout,
  grid: SquaresFour,
  rows: Rows,
  columns: Columns,
  type: TextAa,
  list: ListBullets,
  tasks: ListChecks,
  branch: GitBranch,
  package: Package,
  database: Database,
  globe: Globe,
  lock: Lock,
  key: Key,
  bookmark: Bookmark,
  star: Star,
  tag: Tag,
  flag: Flag,
  target: Target,
  bug: Bug,
  palette: Palette,
  cursor: CursorClick,
  robot: Robot,
  wand: MagicWand,
  sparkle: Sparkle,
  bolt: Lightning,
  cpu: Cpu,
  broadcast: Broadcast,
  play: Play,
  stop: Stop,
  eye: Eye,
  eyeOff: EyeSlash,
  image: Image,
  tool: Wrench,
  command: Command,
  theme: Sun,
  themeLight: Sun,
  themeDark: Moon,
  themeSystem: Monitor,
} as const;

export type IconName = keyof typeof ICONS;

export interface IconProps {
  name: IconName;
  /** Square size in px. Defaults to 16, the size the interface is drawn at. */
  size?: number;
  /** Phosphor weight. The product uses "regular" for navigation and
   *  "bold"/"fill" only where an icon must survive on a coloured surface. */
  weight?: IconWeight;
  className?: string;
  /** Only for an icon that is the sole carrier of meaning. */
  label?: string;
}

export function Icon({ name, size = 16, weight = "regular", className, label }: IconProps) {
  const Glyph = ICONS[name];
  return (
    <Glyph
      size={size}
      weight={weight}
      className={className ? `icon ${className}` : "icon"}
      aria-hidden={label ? undefined : true}
      role={label ? "img" : undefined}
      aria-label={label}
    />
  );
}
