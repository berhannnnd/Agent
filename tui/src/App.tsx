import React, {useEffect, useMemo, useRef, useState} from 'react'
import {Box, useApp, useInput, useStdin} from 'ink'
import {BridgeClient} from './protocol/bridge.js'
import type {ApprovalDecision, BridgeEvent, ModelProfile, PendingApproval, RuntimeEvent, RuntimeInfo, WorkspaceInfo} from './protocol/types.js'
import {Welcome} from './components/Welcome.js'
import {MessageList, type TranscriptItem} from './components/MessageList.js'
import {PromptInput} from './components/PromptInput.js'
import {ApprovalPrompt} from './components/ApprovalPrompt.js'
import {StatusLine} from './components/StatusLine.js'
import {ModelPicker} from './components/ModelPicker.js'
import {LiveTurn} from './components/LiveTurn.js'
import {runtimeLabel} from './ui/format.js'
import {COMMANDS} from './ui/commands.js'
import {useLiveDraft} from './hooks/useLiveDraft.js'
import {useInputQueue} from './hooks/useInputQueue.js'
import {useToolTimeline} from './hooks/useToolTimeline.js'
import {approvalDecisionText, formatDuration, pendingApprovalFromEvent, retryText} from './ui/runtimeEvents.js'

export function App({python, repoRoot, bridgeArgs}: {python: string; repoRoot: string; bridgeArgs: string[]}) {
  const {exit} = useApp()
  const {isRawModeSupported} = useStdin()
  const [runtime, setRuntime] = useState<RuntimeInfo>()
  const [workspace, setWorkspace] = useState<WorkspaceInfo>()
  const [profile, setProfile] = useState('coding')
  const [permission, setPermission] = useState('guarded')
  const [sandbox, setSandbox] = useState('local')
  const [toolCount, setToolCount] = useState(0)
  const [items, setItems] = useState<TranscriptItem[]>([])
  const [busy, setBusy] = useState(false)
  const [collapsed, setCollapsed] = useState(true)
  const [inputHistory, setInputHistory] = useState<string[]>([])
  const [modelPicker, setModelPicker] = useState<ModelProfile[] | null>(null)
  const [pendingApproval, setPendingApproval] = useState<PendingApproval | null>(null)
  const assistantDraft = useLiveDraft()
  const reasoningDraft = useLiveDraft({trimLive: true})
  const inputQueue = useInputQueue(runInput)
  const toolTimeline = useToolTimeline(setItems)
  const runtimeRef = useRef<RuntimeInfo | undefined>(undefined)
  const activeRunId = useRef('')
  const turnStartedAt = useRef(0)
  const modelPickerRequested = useRef(false)
  const suppressNextModelProfiles = useRef(false)
  const bridge = useMemo(() => new BridgeClient({python, repoRoot, args: bridgeArgs}), [python, repoRoot, bridgeArgs])
  const inputDisabledReason = pendingApproval ? 'approval required · choose below' : modelPicker ? 'picker active · esc to close' : undefined

  useEffect(() => {
    runtimeRef.current = runtime
  }, [runtime])

  useEffect(() => {
    const unsubscribe = bridge.onEvent(event => {
      handleBridgeEvent(event)
    })
    bridge.start()
    return () => {
      unsubscribe()
      bridge.stop()
    }
  }, [bridge])

  useInput((input, key) => {
    if (key.ctrl && input === 'o') {
      setCollapsed(current => !current)
      return
    }
    if (key.ctrl && input === 't') {
      toolTimeline.focusNext(items)
      return
    }
    if (key.ctrl && input === 'd') toolTimeline.toggle()
  }, {isActive: Boolean(!pendingApproval && !modelPicker && isRawModeSupported)})

  function append(item: TranscriptItem) {
    setItems(current => [...current, item])
  }

  function handleBridgeEvent(event: BridgeEvent) {
    if (event.type === 'ready') {
      runtimeRef.current = event.runtime
      setRuntime(event.runtime)
      setWorkspace(event.workspace)
      setProfile(event.profile)
      setPermission(event.permission)
      setSandbox(event.sandbox)
      setToolCount(event.tools.length)
      return
    }
    if (event.type === 'turn_started') {
      setBusy(true)
      activeRunId.current = event.run_id
      turnStartedAt.current = Date.now()
      assistantDraft.clear()
      reasoningDraft.clear()
      toolTimeline.reset()
      append({kind: 'status', label: 'thinking', text: runtimeLabel(runtimeRef.current?.protocol, runtimeRef.current?.model)})
      return
    }
    if (event.type === 'runtime_event') {
      handleRuntimeEvent(event.event)
      return
    }
    if (event.type === 'turn_finished') {
      flushThinking()
      flushAssistant()
      setBusy(false)
      if (event.status === 'awaiting_approval') {
        append({kind: 'status', label: 'approval', text: 'waiting for your decision', level: 'warning'})
      } else {
        append({
          kind: 'status',
          label: event.status === 'finished' ? 'done' : event.status,
          text: turnStartedAt.current ? formatDuration(Date.now() - turnStartedAt.current) : undefined,
          level: event.status === 'error' ? 'error' : 'info'
        })
        runQueuedInput()
      }
      return
    }
    if (event.type === 'model_profiles') {
      if (suppressNextModelProfiles.current) {
        suppressNextModelProfiles.current = false
        return
      }
      if (modelPickerRequested.current) {
        modelPickerRequested.current = false
        setModelPicker(event.profiles)
      } else {
        append({kind: 'models', profiles: event.profiles})
      }
      return
    }
    if (event.type === 'model_switched') {
      runtimeRef.current = event.runtime
      setRuntime(event.runtime)
      append({kind: 'status', label: 'model', text: `switched to ${event.profile} · ${event.runtime.model}`, level: 'success'})
      return
    }
    if (event.type === 'status') appendTable('Status', event.status)
    else if (event.type === 'doctor') appendTable('Doctor', event.doctor)
    else if (event.type === 'context') appendTable('Context', event.context)
    else if (event.type === 'trace') append({kind: 'table', title: 'Context Trace', rows: event.trace})
    else if (event.type === 'workspace') appendTable('Workspace', event.workspace)
    else if (event.type === 'tools') append({kind: 'table', title: 'Tools', rows: event.tools.map(tool => [tool, 'enabled'])})
    else if (event.type === 'commands') append({kind: 'table', title: 'Commands', rows: event.commands.map(command => [command.name, command.action])})
    else if (event.type === 'notice') append({kind: 'status', label: 'notice', text: event.message})
    else if (event.type === 'error') append({kind: 'status', label: 'error', text: event.message, level: 'error'})
    else if (event.type === 'exit') exit()
  }

  function appendTable(title: string, rows: Record<string, unknown>) {
    append({kind: 'table', title, rows: Object.entries(rows).map(([key, value]) => [key, String(value)])})
  }

  function handleRuntimeEvent(event: RuntimeEvent) {
    const payload = event.payload ?? {}
    if (event.type === 'text_delta') {
      assistantDraft.append(String(payload.delta ?? ''))
      return
    }
    if (event.type === 'model_message') {
      flushThinking()
      const finalText = String(payload.content ?? '') || assistantDraft.value()
      assistantDraft.clear()
      if (finalText) append({kind: 'assistant', text: finalText})
      return
    }
    if (event.type === 'reasoning_delta') {
      reasoningDraft.append(String(payload.delta ?? ''))
      return
    }
    if (event.type === 'model_retry') {
      append({kind: 'status', label: 'retry', text: retryText(payload), level: 'warning'})
      return
    }
    if (event.type === 'tool_start') {
      flushThinking()
      flushAssistant()
      toolTimeline.start(event, payload)
      return
    }
    if (event.type === 'tool_result') {
      toolTimeline.finish(event, payload)
      return
    }
    if (event.type === 'tool_approval_required') {
      flushThinking()
      flushAssistant()
      setPendingApproval(pendingApprovalFromEvent(event, activeRunId.current))
      return
    }
    if (event.type === 'tool_approval_decision') {
      const decision = approvalDecisionText(event)
      append({
        kind: 'status',
        label: decision.approved ? 'approved' : 'denied',
        text: decision.text,
        level: decision.approved ? 'success' : 'warning'
      })
      return
    }
    if (event.type === 'error') {
      flushThinking()
      flushAssistant()
      append({kind: 'status', label: 'error', text: String(payload.message ?? 'runtime error'), level: 'error'})
    }
  }

  function flushAssistant() {
    const text = assistantDraft.flush()
    if (!text) return
    append({kind: 'assistant', text})
  }

  function flushThinking() {
    const text = reasoningDraft.flush({trim: true})
    if (!text) return
    append({kind: 'thinking', text})
  }

  function submit(value: string) {
    setInputHistory(current => {
      const next = current.filter(item => item !== value)
      next.push(value)
      return next.slice(-80)
    })
    if (busy && !value.startsWith('/')) {
      inputQueue.enqueue(value)
      append({kind: 'status', label: 'queued', text: value})
      return
    }
    runInput(value)
  }

  function runInput(value: string) {
    append({kind: 'user', text: value})
    if (value === '/help' || value === '?') {
      append({kind: 'table', title: 'Commands', rows: COMMANDS.map(command => [command.name, `${command.description}${command.argumentHint ? ` ${command.argumentHint}` : ''}${command.local ? ' · local' : ''}${command.availability === 'idle' ? ' · idle' : ''}`])})
    } else if (value === '/model' || value === '/models') {
      modelPickerRequested.current = true
      bridge.send({type: 'slash', text: value})
    } else if (value === '/fold') {
      setCollapsed(true)
      append({kind: 'status', label: 'fold', text: 'long blocks collapsed'})
    } else if (value === '/unfold') {
      setCollapsed(false)
      append({kind: 'status', label: 'unfold', text: 'long blocks expanded'})
    } else if (value === '/queue') {
      append({
        kind: 'table',
        title: 'Queued Messages',
        rows: inputQueue.items.length ? inputQueue.items.map((text, index) => [String(index + 1), text]) : [['queue', 'empty']]
      })
    } else if (value === '/cancel') {
      const count = inputQueue.clear()
      append({kind: 'status', label: 'queue', text: count ? `cleared ${count} queued message${count === 1 ? '' : 's'}` : 'empty'})
    } else if (value === '/clear') {
      setItems([])
      bridge.send({type: 'slash', text: value})
    } else if (value.startsWith('/')) bridge.send({type: 'slash', text: value})
    else bridge.send({type: 'user_message', text: value})
  }

  function runQueuedInput() {
    inputQueue.runNext()
  }

  function selectModel(name: string) {
    suppressNextModelProfiles.current = true
    setModelPicker(null)
    append({kind: 'status', label: 'model', text: `switching to ${name}`})
    bridge.send({type: 'slash', text: `/model ${name}`})
  }

  function decideApproval(decision: ApprovalDecision) {
    if (!pendingApproval) return
    const approved = decision !== 'deny'
    append({
      kind: 'status',
      label: approved ? 'approval' : 'denied',
      text: `${pendingApproval.toolName} · ${decision}`,
      level: approved ? 'success' : 'warning'
    })
    bridge.send({
      type: 'approval',
      run_id: pendingApproval.runId,
      approvals: {[pendingApproval.approvalId]: approved},
      approval_scopes: {[pendingApproval.approvalId]: decision}
    })
    setPendingApproval(null)
    setBusy(true)
  }

  function stop() {
    bridge.stop()
    exit()
  }

  return (
    <Box flexDirection="column" paddingX={1}>
      <Welcome runtime={runtime} workspace={workspace} profile={profile} permission={permission} sandbox={sandbox} toolCount={toolCount} />
      <MessageList items={items} collapsed={collapsed} selectedToolId={toolTimeline.selectedToolId} expandedToolIds={toolTimeline.expandedToolIds} onToggleTool={toolTimeline.toggle} />
      {busy ? <LiveTurn assistant={assistantDraft.live} reasoning={reasoningDraft.live} label={runtimeLabel(runtime?.protocol, runtime?.model)} collapsed={collapsed} /> : null}
      {pendingApproval ? <ApprovalPrompt approval={pendingApproval} onDecision={decideApproval} /> : null}
      {modelPicker ? <ModelPicker profiles={modelPicker} onSelect={selectModel} onCancel={() => setModelPicker(null)} /> : null}
      <PromptInput disabled={Boolean(inputDisabledReason)} disabledReason={inputDisabledReason} repoRoot={repoRoot} history={inputHistory} onSubmit={submit} onExit={stop} />
      <StatusLine runtime={runtime} workspace={workspace} permission={permission} sandbox={sandbox} toolCount={toolCount} busy={busy} folded={collapsed} queued={inputQueue.items.length} />
    </Box>
  )
}
