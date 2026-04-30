import React from 'react'
import {render} from 'ink'
import {App} from './App.js'

const args = parseArgs(process.argv.slice(2))

render(<App python={args.python} repoRoot={args.repoRoot} bridgeArgs={args.bridgeArgs} />)

function parseArgs(argv: string[]) {
  let python = process.env.AGENTS_PYTHON || '.venv/bin/python'
  let repoRoot = process.env.AGENTS_REPO_ROOT || '..'
  const bridgeArgs: string[] = []
  for (let index = 0; index < argv.length; index += 1) {
    const value = argv[index]
    if (value === '--python') {
      python = argv[++index] ?? python
    } else if (value === '--repo-root') {
      repoRoot = argv[++index] ?? repoRoot
    } else {
      bridgeArgs.push(value)
    }
  }
  return {python, repoRoot, bridgeArgs}
}
