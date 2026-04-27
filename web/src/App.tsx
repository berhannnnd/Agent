import { createSignal } from "solid-js";
import { ActionTimeline } from "./components/ActionTimeline";
import { ChatThread } from "./components/ChatThread";
import { SettingsDrawer } from "./components/SettingsDrawer";
import { TopBar } from "./components/TopBar";
import { createAgentSession } from "./runtime/agentSession";

export function App() {
  const session = createAgentSession();
  const [settingsOpen, setSettingsOpen] = createSignal(false);
  const [activityOpen, setActivityOpen] = createSignal(false);

  return (
    <div class="studio-shell">
      <TopBar
        health={session.health}
        streaming={session.streaming}
        setStreaming={session.setStreaming}
        activityCount={() => session.activity().length}
        activityOpen={activityOpen}
        setActivityOpen={setActivityOpen}
        settingsOpen={settingsOpen}
        setSettingsOpen={setSettingsOpen}
        checkHealth={session.checkHealth}
      />
      <main class="conversation-stage">
        <ChatThread
          messages={session.messages}
          busy={session.busy}
          provider={session.provider}
          model={session.model}
          latency={session.latency}
          toolCount={() => session.toolList().length}
          input={session.input}
          setInput={session.setInput}
          canSend={session.canSend}
          send={session.send}
          clear={session.clear}
        />
        <ActionTimeline events={session.activity} open={activityOpen} />
      </main>
      <SettingsDrawer
        open={settingsOpen}
        setOpen={setSettingsOpen}
        baseUrl={session.baseUrl}
        setBaseUrl={session.setBaseUrl}
        token={session.token}
        setToken={session.setToken}
        provider={session.provider}
        setProvider={session.setProvider}
        model={session.model}
        setModel={session.setModel}
        modelBaseUrl={session.modelBaseUrl}
        setModelBaseUrl={session.setModelBaseUrl}
        apiKey={session.apiKey}
        setApiKey={session.setApiKey}
        enabledTools={session.enabledTools}
        setEnabledTools={session.setEnabledTools}
        systemPrompt={session.systemPrompt}
        setSystemPrompt={session.setSystemPrompt}
      />
    </div>
  );
}
