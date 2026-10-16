// apps/vibe/src/features/onboarding/store.ts
// The first-run decision: does this install have a provider it can talk to?
//
// This is its own feature module rather than a flag on the settings store
// because the answer has to be known before Settings is ever opened, and a
// failed catalog read must not be mistaken for "nothing is configured".
import { create } from "zustand";
import { api, type ProviderInfo } from "../../lib/api";

/** Built-in provider ids as GET /catalog reports them.
 *
 * A built-in provider is usable only once its key is configured, and that key
 * comes from the environment rather than the GUI. A custom provider may
 * legitimately have no key at all - a local endpoint such as Ollama or LM Studio
 * does not need one - so for those, having at least one model is the signal that
 * the user finished setting it up.
 */
const BUILTIN_IDS = new Set(["openai", "anthropic", "opencode-go"]);

export function hasConfiguredProvider(providers: ProviderInfo[]): boolean {
  return providers.some((p) => p.key_configured || (!BUILTIN_IDS.has(p.id) && p.models.length > 0));
}

/** Whether the first-run guidance should replace the empty chat.
 *
 * The loaded flag is the important half: an empty list means either "the fetch
 * has not finished" or "the fetch failed", and neither is evidence that the user
 * has no provider. Nagging on a network error would be worse than staying quiet.
 */
export function shouldShowFirstRun(providers: ProviderInfo[], loaded: boolean): boolean {
  return loaded && providers.length > 0 && !hasConfiguredProvider(providers);
}

interface FirstRunState {
  providers: ProviderInfo[];
  loaded: boolean;
  refresh: () => Promise<void>;
}

export const useFirstRunStore = create<FirstRunState>((set) => ({
  providers: [],
  loaded: false,
  refresh: async () => {
    try {
      const providers = await api.getCatalog();
      set({ providers, loaded: true });
    } catch {
      // The chat surfaces the real error when the user tries to send; this
      // panel's only job is to decide whether to explain itself.
      set({ providers: [], loaded: false });
    }
  },
}));
