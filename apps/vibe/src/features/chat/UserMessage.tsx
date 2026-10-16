// features/chat/UserMessage.tsx — one user turn.
//
// A raised surface, not a coloured bar: the product has one accent and it is
// reserved for actions and focus, so the prompt is separated from the agent's
// reply by elevation (border + background) instead of a second colour.

import type { UserItem } from "./timeline";

export function UserMessage({ item }: { item: UserItem }) {
  return (
    <div className="message message-user">
      <span className="message-role">You</span>
      <div className="message-content">{item.content}</div>
      {item.pending && <span className="message-pending">Sending…</span>}
    </div>
  );
}
