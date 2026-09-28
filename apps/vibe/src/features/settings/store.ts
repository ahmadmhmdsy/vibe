// apps/vibe/src/features/settings/store.ts
import { create } from "zustand";
import { api, type ProviderInfo } from "../../lib/api";

interface SettingsState {
  providers: ProviderInfo[];
  load: () => Promise<void>;
}

export const useSettingsStore = create<SettingsState>((set) => ({
  providers: [],
  load: async () => {
    const providers = await api.getCatalog();
    set({ providers });
  },
}));
