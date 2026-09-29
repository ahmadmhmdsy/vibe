// apps/vibe/src/lib/format.ts
const EXTENSION_LANGUAGE: Record<string, string> = {
  ts: "typescript",
  tsx: "typescript",
  mts: "typescript",
  cts: "typescript",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  py: "python",
  css: "css",
  scss: "scss",
  less: "less",
  html: "html",
  htm: "html",
  json: "json",
  md: "markdown",
  svg: "xml",
  xml: "xml",
  yml: "yaml",
  yaml: "yaml",
  toml: "toml",
  sh: "shell",
  bash: "shell",
  sql: "sql",
  rs: "rust",
  go: "go",
};

/** Map a filename to a Monaco editor language id. */
export function detectLanguage(filename: string): string {
  const ext = filename.split(".").pop()?.toLowerCase() ?? "";
  return EXTENSION_LANGUAGE[ext] ?? "plaintext";
}
