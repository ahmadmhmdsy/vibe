// apps/vibe/src/features/onboarding/examples.ts
// Kept out of FirstRun.tsx so that file exports a component and nothing else
// (react-refresh can only hot-reload such a module).

/** Starting points that fit in one session and produce something visible.
 *
 * They are written as prompts the user would actually type, not as feature
 * names, so the first-run panel can hand one straight to the composer. */
export const EXAMPLE_PROMPTS = [
  "Build a pomodoro timer with a start/pause button and a task list.",
  "Make a dashboard that charts my monthly expenses from a CSV file.",
  "Build a markdown notes app that saves to local storage and supports search.",
  "Make a kanban board with drag-and-drop columns and a card detail view.",
];
