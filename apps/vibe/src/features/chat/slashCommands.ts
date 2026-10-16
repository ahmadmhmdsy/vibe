// features/chat/slashCommands.ts — the slash-command list and its text matcher.
//
// Kept out of Composer.tsx so the detection and filtering are testable on their
// own and the component only has to wire keyboard events to them.

import { TEMPLATES } from "./templates";

export interface SlashCommand {
  id: string;
  /** What the user types, including the leading slash. */
  command: string;
  label: string;
  description?: string;
  /** The template to insert, or null for a built-in action (clear). */
  templateId: string | null;
}

export const CLEAR_COMMAND_ID = "clear";

/** Every command, templates first, derived from the one data file. */
export function buildSlashCommands(): readonly SlashCommand[] {
  return [
    ...TEMPLATES.map((template) => ({
      id: `template-${template.id}`,
      command: `/${template.id}`,
      label: template.label,
      description: template.description,
      templateId: template.id,
    })),
    {
      id: CLEAR_COMMAND_ID,
      command: "/clear",
      label: "Clear composer",
      description: "Remove everything in the input.",
      templateId: null,
    },
  ];
}

export interface SlashToken {
  /** Index of the leading "/". */
  start: number;
  /** Caret position the token ends at. */
  end: number;
  /** The text after the "/", lowercased. */
  query: string;
}

/** Find the slash token the caret currently sits inside.
 *
 * A token starts at "/" and runs to the caret with no whitespace, and the "/"
 * must begin the composer or follow whitespace. Anything else - a URL, a
 * directory path, a mid-word slash - returns null, so the menu stays closed.
 */
export function findSlashToken(text: string, caret: number): SlashToken | null {
  const before = text.slice(0, caret);
  let start = before.length;
  while (start > 0 && !/\s/.test(before[start - 1])) start--;
  if (before[start] !== "/") return null;
  if (start > 0 && !/\s/.test(before[start - 1])) return null;
  return { start, end: caret, query: before.slice(start + 1).toLowerCase() };
}

export function filterSlashCommands(
  commands: readonly SlashCommand[],
  query: string
): SlashCommand[] {
  const q = query.trim().toLowerCase();
  if (!q) return [...commands];
  return commands.filter((command) => {
    const haystack = [command.command.slice(1), command.label, command.description ?? ""]
      .join(" ")
      .toLowerCase();
    return haystack.includes(q);
  });
}
