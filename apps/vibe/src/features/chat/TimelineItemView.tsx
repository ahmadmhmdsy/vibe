// features/chat/TimelineItemView.tsx — dispatch one timeline item to its view.
//
// Every kind the reducer can produce has a renderer. An error is an inline
// block rather than a nested alert: the transcript is role="log", and a second
// live region inside it would announce the same failure twice.

import { Icon } from "../../components/icons/Icon";
import { AssistantMessage } from "./AssistantMessage";
import { ToolRow } from "./ToolRow";
import { UserMessage } from "./UserMessage";
import type { TimelineItem } from "./timeline";

export function TimelineItemView({ item }: { item: TimelineItem }) {
  switch (item.kind) {
    case "user":
      return <UserMessage item={item} />;
    case "assistant":
      return <AssistantMessage item={item} />;
    case "tool":
      return <ToolRow item={item} />;
    case "error":
      return (
        <div className="message-error">
          <span className="message-error-icon" aria-hidden="true">
            <Icon name="warningCircle" size={16} />
          </span>
          <p className="message-error-text">{item.content}</p>
        </div>
      );
    case "notice":
      return (
        <p className="message-notice" data-tone={item.tone}>
          {item.content}
        </p>
      );
  }
}
