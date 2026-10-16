// lib/platform.ts — the one place that asks which OS the browser runs on.
//
// Needed for keyboard shortcuts: Cmd+N is the natural binding on macOS, while
// Windows and Linux browsers reserve plain Ctrl+N for the browser itself.

/** True on Apple platforms (macOS, iOS/iPadOS). */
export function isMacPlatform(): boolean {
  if (typeof navigator === "undefined") return false;
  // navigator.platform is deprecated but is still the only synchronous signal
  // available in every browser we support; userAgent covers the empty case.
  const platform = navigator.platform || navigator.userAgent || "";
  return /mac|iphone|ipad|ipod/i.test(platform);
}
