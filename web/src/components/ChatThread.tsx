import { Bot, Eraser, MessageSquareText, Send, Sparkles } from "lucide-solid";
import type { Accessor, Setter } from "solid-js";
import { For, Show } from "solid-js";
import type { ChatMessage } from "../types";

type Props = {
  messages: Accessor<ChatMessage[]>;
  busy: Accessor<boolean>;
  provider: Accessor<string>;
  model: Accessor<string>;
  latency: Accessor<number | null>;
  toolCount: Accessor<number>;
  input: Accessor<string>;
  setInput: Setter<string>;
  canSend: Accessor<boolean>;
  send: () => void;
  clear: () => void;
};

export function ChatThread(props: Props) {
  return (
    <section class="thread-card">
      <div class="thread-header">
        <div>
          <p class="eyebrow">Live runtime</p>
          <h2>Agent command session</h2>
        </div>
        <button class="icon-button" onClick={props.clear} title="Clear conversation">
          <Eraser size={16} />
        </button>
      </div>

      <div class="thread-body">
        <Show when={props.messages().length > 0} fallback={<EmptyState />}>
          <For each={props.messages()}>{(message) => <MessageBubble message={message} />}</For>
        </Show>
        <Show when={props.busy()}>
          <div class="typing"><span></span><span></span><span></span></div>
        </Show>
      </div>

      <footer class="composer">
        <div class="telemetry">
          <span>{props.provider()}</span>
          <span>{props.model() || "model not set"}</span>
          <span>{props.latency() === null ? "no latency yet" : `${props.latency()} ms`}</span>
          <span>{props.toolCount() ? `${props.toolCount()} tools` : "no tools"}</span>
        </div>
        <div class="composer-row">
          <textarea
            value={props.input()}
            onInput={(event) => props.setInput(event.currentTarget.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) props.send();
            }}
            placeholder="Message the agent..."
          />
          <button class="send-button" disabled={!props.canSend()} onClick={props.send}>
            <Send size={18} />
          </button>
        </div>
      </footer>
    </section>
  );
}

function MessageBubble(props: { message: ChatMessage }) {
  return (
    <article class={`message message-${props.message.role}`}>
      <div class="avatar">{props.message.role === "user" ? <MessageSquareText size={16} /> : <Bot size={16} />}</div>
      <div class="bubble">
        <span>{props.message.role}</span>
        <p>{props.message.content || "..."}</p>
      </div>
    </article>
  );
}

function EmptyState() {
  return (
    <div class="empty-state">
      <Sparkles size={36} />
      <h3>Ready when you are</h3>
      <p>Start with the question that matters.</p>
    </div>
  );
}
