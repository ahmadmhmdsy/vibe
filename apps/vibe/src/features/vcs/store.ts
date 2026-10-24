// apps/vibe/src/features/vcs/store.ts
//
// One session's source-control state. Keyed by session for the same reason the
// preview store is: the agent writes files continuously and a workspace switch
// must not show the previous session's changes.
import { create } from "zustand";
import { api, type VcsCommit, type VcsFile, type VcsStatus } from "../../lib/api";

export interface VcsView {
  status: VcsStatus | null;
  log: VcsCommit[];
  /** The open diff, or null when none is selected. */
  diff: { path: string; text: string; truncated: boolean } | null;
  loading: boolean;
  error: string | null;
}

const EMPTY: VcsView = { status: null, log: [], diff: null, loading: false, error: null };

interface VcsStore {
  bySession: Record<string, VcsView>;
  /** Status and history together: a commit changes both, and two requests per
   *  poll would double the work for one screenful. */
  load: (sid: string, opts?: { quiet?: boolean }) => Promise<void>;
  select: (sid: string, file: VcsFile | null) => Promise<void>;
  commit: (sid: string, message: string) => Promise<boolean>;
  init: (sid: string) => Promise<void>;
  branch: (sid: string, name: string, create: boolean) => Promise<void>;
}

const patch = (state: VcsStore, sid: string, next: Partial<VcsView>): Partial<VcsStore> => ({
  bySession: { ...state.bySession, [sid]: { ...(state.bySession[sid] ?? EMPTY), ...next } },
});

export const useVcsStore = create<VcsStore>((set, get) => ({
  bySession: {},

  load: async (sid, opts) => {
    // A poll must not flash the loading state: the panel would blink every few
    // seconds while the agent works.
    if (!opts?.quiet) set((s) => patch(s, sid, { loading: true }));
    try {
      const [status, log] = await Promise.all([api.vcsStatus(sid), api.vcsLog(sid)]);
      set((s) => patch(s, sid, { status, log, loading: false, error: null }));
    } catch (e) {
      set((s) =>
        patch(s, sid, {
          loading: false,
          error: e instanceof Error ? e.message : "Failed to read the repository.",
        })
      );
    }
  },

  select: async (sid, file) => {
    if (!file) {
      set((s) => patch(s, sid, { diff: null }));
      return;
    }
    try {
      const { diff, truncated } = await api.vcsDiff(sid, { path: file.path });
      set((s) => patch(s, sid, { diff: { path: file.path, text: diff, truncated } }));
    } catch (e) {
      set((s) =>
        patch(s, sid, {
          diff: null,
          error: e instanceof Error ? e.message : "Failed to read the diff.",
        })
      );
    }
  },

  commit: async (sid, message) => {
    const { committed } = await api.vcsCommit(sid, message);
    // Either way the workspace and the history changed, so both are re-read.
    await get().load(sid, { quiet: true });
    set((s) => patch(s, sid, { diff: null }));
    return committed;
  },

  init: async (sid) => {
    await api.vcsInit(sid);
    await get().load(sid);
  },

  branch: async (sid, name, create) => {
    await api.vcsBranch(sid, name, create);
    await get().load(sid, { quiet: true });
  },
}));

/** Stable empty value, so a selector does not re-subscribe on every render. */
export const emptyVcsView = EMPTY;
