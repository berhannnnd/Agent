import { ShieldCheck, ShieldX, Wrench } from "lucide-solid";
import type { Accessor } from "solid-js";
import { For, Show } from "solid-js";
import type { ToolApprovalRequest } from "../types";

type Props = {
  requests: Accessor<ToolApprovalRequest[]>;
  busy: Accessor<boolean>;
  decide: (request: ToolApprovalRequest, approved: boolean) => void;
};

export function ToolApprovalPanel(props: Props) {
  return (
    <Show when={props.requests().length > 0}>
      <div class="approval-panel">
        <For each={props.requests()}>{(request) => (
          <article class="approval-row">
            <div class="approval-icon"><Wrench size={15} /></div>
            <div class="approval-copy">
              <strong>{request.toolName}</strong>
              <span>{request.reason || "Tool approval required"}</span>
              <code>{compactArgs(request.arguments)}</code>
            </div>
            <div class="approval-actions">
              <button class="deny-button" disabled={props.busy()} onClick={() => props.decide(request, false)} title="Deny tool">
                <ShieldX size={15} />
              </button>
              <button class="approve-button" disabled={props.busy()} onClick={() => props.decide(request, true)} title="Approve tool">
                <ShieldCheck size={15} />
              </button>
            </div>
          </article>
        )}</For>
      </div>
    </Show>
  );
}

function compactArgs(args: Record<string, unknown>) {
  const text = JSON.stringify(args || {});
  return text.length > 140 ? `${text.slice(0, 137)}...` : text;
}
