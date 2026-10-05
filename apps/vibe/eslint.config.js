// apps/vibe/eslint.config.js
// Flat config (ESLint 9+). The frontend had no linter at all before this
// (audit P3), so the ruleset is deliberately the recommended baseline rather
// than a maximal one: it should catch real mistakes without turning every
// existing file red on the first run.
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // Build output, dependencies, and tool scratch directories are not source.
    ignores: ["dist/**", "node_modules/**", "coverage/**", ".impeccable/**"],
  },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.es2021 },
    },
    plugins: { "react-refresh": reactRefresh },
    rules: {
      "react-refresh/only-export-components": ["warn", { allowConstantExport: true }],

      // --- triaged to "warn" ---------------------------------------------
      // These two rules ship with the React Compiler ruleset in
      // eslint-plugin-react-hooks v7. Every current hit is a *deliberate,
      // working* pattern that the rule would rather see rewritten:
      //
      //   react-hooks/refs                the "latest ref" pattern
      //                                   (useKeyboardShortcut, usePolling)
      //   react-hooks/set-state-in-effect syncing with an external store, or
      //                                   resetting local state when a prop
      //                                   changes (CommandPalette,
      //                                   useMediaQuery, ModelPicker,
      //                                   SessionsPanel)
      //
      // Fixing them properly means useSyncExternalStore / render-phase state
      // adjustment / useEffectEvent - behaviour-affecting refactors of
      // working UI that belong in their own change with their own tests, not
      // in a lint-cleanup commit. Kept visible as warnings so they are not
      // forgotten; see TASKS.md.
      "react-hooks/refs": "warn",
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  {
    // Test files run under vitest and reach into jsdom directly.
    files: ["**/__tests__/**/*.{ts,tsx}", "**/*.test.{ts,tsx}", "vitest.setup.ts"],
    languageOptions: { globals: { ...globals.node } },
  },
);
