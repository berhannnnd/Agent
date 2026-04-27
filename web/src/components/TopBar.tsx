import { Circle, Radio, Settings2, Sparkles, TerminalSquare } from "lucide-solid";
import type { Accessor, Setter } from "solid-js";

type Props = {
  health: Accessor<string>;
  streaming: Accessor<boolean>;
  setStreaming: Setter<boolean>;
  activityCount: Accessor<number>;
  activityOpen: Accessor<boolean>;
  setActivityOpen: Setter<boolean>;
  settingsOpen: Accessor<boolean>;
  setSettingsOpen: Setter<boolean>;
  checkHealth: () => void;
};

export function TopBar(props: Props) {
  return (
    <header class="studio-topbar">
      <div class="brand-block">
        <div class="mark"><Sparkles size={19} /></div>
        <div>
          <h1>Agents</h1>
          <p>Conversation Studio</p>
        </div>
      </div>
      <div class="top-actions">
        <button class="status-pill" onClick={props.checkHealth}>
          <Circle size={10} class={`health-${props.health()}`} />
          <span>{props.health()}</span>
        </button>
        <button class="mode-toggle" classList={{ active: props.streaming() }} onClick={() => props.setStreaming(!props.streaming())}>
          <Radio size={15} />
          <span>{props.streaming() ? "Streaming" : "Single response"}</span>
        </button>
        <button class="plain-button" classList={{ active: props.activityOpen() }} onClick={() => props.setActivityOpen(!props.activityOpen())}>
          <TerminalSquare size={16} />
          <span>Activity {props.activityCount()}</span>
        </button>
        <button class="plain-button" classList={{ active: props.settingsOpen() }} onClick={() => props.setSettingsOpen(true)}>
          <Settings2 size={16} />
          <span>Settings</span>
        </button>
      </div>
    </header>
  );
}
