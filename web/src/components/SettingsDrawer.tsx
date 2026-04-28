import { ChevronDown, Cpu, KeyRound, Settings2, ShieldCheck, Wrench, X } from "lucide-solid";
import type { Accessor, Setter } from "solid-js";
import { For, Show } from "solid-js";
import { modelProtocols, type PermissionMode } from "../types";

type Props = {
  open: Accessor<boolean>;
  setOpen: Setter<boolean>;
  baseUrl: Accessor<string>;
  setBaseUrl: Setter<string>;
  token: Accessor<string>;
  setToken: Setter<string>;
  protocol: Accessor<string>;
  setProtocol: Setter<string>;
  model: Accessor<string>;
  setModel: Setter<string>;
  modelBaseUrl: Accessor<string>;
  setModelBaseUrl: Setter<string>;
  apiKey: Accessor<string>;
  setApiKey: Setter<string>;
  enabledTools: Accessor<string>;
  setEnabledTools: Setter<string>;
  permissionMode: Accessor<PermissionMode>;
  setPermissionMode: Setter<PermissionMode>;
  systemPrompt: Accessor<string>;
  setSystemPrompt: Setter<string>;
};

export function SettingsDrawer(props: Props) {
  return (
    <Show when={props.open()}>
      <div class="drawer-backdrop" onClick={() => props.setOpen(false)} />
      <aside class="settings-drawer">
        <div class="drawer-header">
          <div><p class="eyebrow">Runtime</p><h2>Settings</h2></div>
          <button class="icon-button" onClick={() => props.setOpen(false)} title="Close settings"><X size={16} /></button>
        </div>
        <section class="config-section">
          <div class="card-title"><Settings2 size={16} /><span>Server</span></div>
          <Control label="Server URL"><input value={props.baseUrl()} onInput={(event) => props.setBaseUrl(event.currentTarget.value)} /></Control>
          <Control label="Access Token"><input type="password" value={props.token()} onInput={(event) => props.setToken(event.currentTarget.value)} placeholder="optional" /></Control>
        </section>
        <section class="config-section">
          <div class="card-title"><Cpu size={16} /><span>Model</span></div>
          <Control label="Protocol">
            <span class="select-wrap">
              <select value={props.protocol()} onInput={(event) => props.setProtocol(event.currentTarget.value)}>
                <For each={[...modelProtocols]}>{(item) => <option value={item}>{item}</option>}</For>
              </select>
              <ChevronDown size={14} />
            </span>
          </Control>
          <Control label="Model"><input value={props.model()} onInput={(event) => props.setModel(event.currentTarget.value)} placeholder="gpt-4.1, claude..." /></Control>
          <Control label="Base URL"><input value={props.modelBaseUrl()} onInput={(event) => props.setModelBaseUrl(event.currentTarget.value)} /></Control>
          <Control label="API Key"><span class="input-icon"><KeyRound size={14} /><input type="password" value={props.apiKey()} onInput={(event) => props.setApiKey(event.currentTarget.value)} /></span></Control>
        </section>
        <section class="config-section">
          <div class="card-title"><Wrench size={16} /><span>Agent</span></div>
          <Control label="Enabled Tools"><input value={props.enabledTools()} onInput={(event) => props.setEnabledTools(event.currentTarget.value)} placeholder="comma separated" /></Control>
          <Control label="Tool Permission">
            <span class="select-wrap">
              <select value={props.permissionMode()} onInput={(event) => props.setPermissionMode(event.currentTarget.value as PermissionMode)}>
                <option value="ask">ask</option>
                <option value="auto">auto</option>
                <option value="deny">deny</option>
              </select>
              <ShieldCheck size={14} />
            </span>
          </Control>
          <Control label="System Prompt"><textarea value={props.systemPrompt()} onInput={(event) => props.setSystemPrompt(event.currentTarget.value)} /></Control>
        </section>
      </aside>
    </Show>
  );
}

function Control(props: { label: string; children: any }) {
  return <label><span>{props.label}</span>{props.children}</label>;
}
