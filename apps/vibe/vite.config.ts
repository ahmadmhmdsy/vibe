import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  // Editors/tools that stage writes as locked temp files next to the source
  // (e.g. ".File.tsx.<pid>.<uuid>.tmpdir/File.tsx.tmp") crash the native
  // watcher with EBUSY on Windows. Ignore those patterns so HMR survives.
  server: {
    watch: {
      ignored: ["**/*.tmpdir/**", "**/*.tmp"],
    },
  },
});
