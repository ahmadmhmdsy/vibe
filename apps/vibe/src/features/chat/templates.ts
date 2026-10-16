// features/chat/templates.ts — the prompt template library.
//
// This file is data. Adding a template is one entry in TEMPLATES below and
// nothing else: the composer's Templates menu and the slash-command list both
// read this array. Keep ids lowercase kebab-case, because the id doubles as the
// slash command name (/<id>) and as the React key.

export interface PromptTemplate {
  /** Stable id. Also the slash command name: typing "/" + id selects it. */
  id: string;
  /** Short sentence-case label shown in the menus. */
  label: string;
  /** One line of context, shown in the slash menu. */
  description?: string;
  /** The full prompt inserted into the composer. */
  prompt: string;
}

export const TEMPLATES: readonly PromptTemplate[] = [
  {
    id: "crud-list",
    label: "CRUD list app",
    description: "A list you can add to, edit, complete, and delete.",
    prompt:
      "Build a task list app. Let me add a task with a title and an optional due date, " +
      "edit any task inline, mark it done, and delete it with a short undo. Save everything " +
      "to localStorage so a reload keeps my data. Include filters for all, open, and done, " +
      "a count of open tasks, and an empty state with a clear first action.",
  },
  {
    id: "dashboard",
    label: "Dashboard",
    description: "Charts and totals from a CSV you upload.",
    prompt:
      "Build a dashboard for a CSV of expenses. Let me upload or paste the file, parse the " +
      "columns date, category, description, and amount, and show the total spent, a bar chart " +
      "of spend by category, and a table of the ten largest expenses. Add a month filter that " +
      "defaults to the current month and recalculates every figure. Handle an empty or " +
      "unparseable file with a message that says what to fix.",
  },
  {
    id: "form",
    label: "Multi-step form",
    description: "A validated flow with a review step.",
    prompt:
      "Build a three-step sign-up form. Step one collects name and email, step two collects a " +
      "password with a strength meter, and step three shows a review of the previous answers " +
      "with a link back. Validate each step before it advances, mark invalid fields with text " +
      "as well as colour, and show a success state after submit. Keep the answers in state so " +
      "going back does not lose them.",
  },
  {
    id: "landing-page",
    label: "Landing page",
    description: "A single marketing page with real sections.",
    prompt:
      "Build a single-page landing page for a neighbourhood coffee shop. Include a hero with " +
      "the shop name and one line about it, a menu section with prices, opening hours, a short " +
      "story, and a contact block with address and phone. Make it responsive, use CSS rather " +
      "than image files, and give every section a real heading so the page reads in order.",
  },
  {
    id: "data-viewer",
    label: "Data viewer",
    description: "A sortable table over pasted JSON.",
    prompt:
      "Build a data viewer for JSON. Let me paste or upload a JSON array of objects, then show " +
      "it in a table with search, sortable columns, and pagination. Let me click a row to expand " +
      "its full record. If the input is not a JSON array of objects, show the parse error and " +
      "the position it came from instead of an empty table.",
  },
];
