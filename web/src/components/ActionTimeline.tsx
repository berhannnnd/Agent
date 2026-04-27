import { Activity, AlertTriangle, CheckCircle2, Code2, Globe2, Loader2, Search, ShieldCheck, TerminalSquare, Wrench } from "lucide-solid";
import type { Accessor } from "solid-js";
import { For } from "solid-js";
import type { RuntimeEvent, RuntimeEventKind } from "../types";

type Props = {
  events: Accessor<RuntimeEvent[]>;
  open: Accessor<boolean>;
};

export function ActionTimeline(props: Props) {
  return (
    <aside class="action-rail" classList={{ "action-rail-open": props.open() }}>
      <div class="action-rail-header">
        <div>
          <p class="eyebrow">Visible execution</p>
          <h2>Agent activity</h2>
        </div>
        <Activity size={18} />
      </div>
      <div class="action-stream">
        <For each={props.events()}>{(event) => <ActionRow event={event} />}</For>
      </div>
      <div class="action-legend">
        <span><Search size={13} />Web search</span>
        <span><Wrench size={13} />Tool call</span>
        <span><Code2 size={13} />Code execution</span>
      </div>
    </aside>
  );
}

function ActionRow(props: { event: RuntimeEvent }) {
  const Icon = () => iconFor(props.event.kind);
  return (
    <article class={`action-row action-${props.event.kind} action-${props.event.status}`}>
      <div class="action-node"><Icon /></div>
      <div class="action-copy">
        <div class="action-meta">
          <strong>{props.event.title}</strong>
          <span>{props.event.time}</span>
        </div>
        <p>{props.event.detail}</p>
      </div>
      <StatusIcon status={props.event.status} />
    </article>
  );
}

function iconFor(kind: RuntimeEventKind) {
  if (kind === "tool") return <Wrench size={15} />;
  if (kind === "approval") return <ShieldCheck size={15} />;
  if (kind === "code") return <Code2 size={15} />;
  if (kind === "search") return <Search size={15} />;
  if (kind === "browser") return <Globe2 size={15} />;
  if (kind === "error") return <AlertTriangle size={15} />;
  return <TerminalSquare size={15} />;
}

function StatusIcon(props: { status: string }) {
  if (props.status === "running") return <Loader2 class="spin" size={15} />;
  if (props.status === "error") return <AlertTriangle size={15} />;
  if (props.status === "done") return <CheckCircle2 size={15} />;
  return <span class="queued-dot" />;
}
