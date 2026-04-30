import {spawn, type ChildProcessWithoutNullStreams} from 'node:child_process'
import path from 'node:path'
import {createInterface} from 'node:readline'
import type {BridgeCommand, BridgeEvent} from './types.js'

export type BridgeOptions = {
  python: string
  repoRoot: string
  args: string[]
}

export class BridgeClient {
  private child: ChildProcessWithoutNullStreams | null = null
  private listeners = new Set<(event: BridgeEvent) => void>()

  constructor(private readonly options: BridgeOptions) {}

  onEvent(listener: (event: BridgeEvent) => void): () => void {
    this.listeners.add(listener)
    return () => this.listeners.delete(listener)
  }

  start(): void {
    if (this.child) return
    const repoRoot = path.resolve(this.options.repoRoot)
    const python = path.isAbsolute(this.options.python)
      ? this.options.python
      : path.resolve(repoRoot, this.options.python)
    this.child = spawn(python, ['-m', 'cli.bridge.ndjson', ...this.options.args], {
      cwd: repoRoot,
      env: process.env,
      stdio: ['pipe', 'pipe', 'pipe']
    })
    const lines = createInterface({input: this.child.stdout})
    lines.on('line', line => {
      if (!line.trim()) return
      try {
        this.emit(JSON.parse(line) as BridgeEvent)
      } catch (error) {
        this.emit({type: 'error', message: `invalid bridge event: ${String(error)}`})
      }
    })
    this.child.stderr.on('data', chunk => {
      const message = String(chunk).trim()
      if (message) this.emit({type: 'error', message})
    })
    this.child.on('exit', code => {
      if (code && code !== 0) this.emit({type: 'error', message: `bridge exited with code ${code}`})
      this.emit({type: 'exit'})
    })
  }

  send(command: BridgeCommand): void {
    if (!this.child) return
    this.child.stdin.write(`${JSON.stringify(command)}\n`)
  }

  stop(): void {
    if (!this.child) return
    this.send({type: 'exit'})
    this.child.kill()
    this.child = null
  }

  private emit(event: BridgeEvent): void {
    for (const listener of this.listeners) listener(event)
  }
}
