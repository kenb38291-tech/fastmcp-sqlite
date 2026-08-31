#!/usr/bin/env node
/**
 * FastMCP SQLite — Zero-Dependency npx Bridge
 * Automatically resolves uvx / pipx / python3 and spawns fastmcp-sqlite with stdio passthrough.
 */
const { spawn, spawnSync } = require('child_process');

const args = process.argv.slice(2);

function isCommandAvailable(cmd) {
  const checkCmd = process.platform === 'win32' ? 'where' : 'which';
  const result = spawnSync(checkCmd, [cmd], { stdio: 'ignore' });
  return result.status === 0;
}

let runner = '';
let runnerArgs = [];

if (isCommandAvailable('uvx')) {
  runner = 'uvx';
  runnerArgs = ['fastmcp-sqlite', ...args];
} else if (isCommandAvailable('pipx')) {
  runner = 'pipx';
  runnerArgs = ['run', 'fastmcp-sqlite', ...args];
} else if (isCommandAvailable('python3')) {
  runner = 'python3';
  runnerArgs = ['-m', 'fastmcp_sqlite', ...args];
} else if (isCommandAvailable('python')) {
  runner = 'python';
  runnerArgs = ['-m', 'fastmcp_sqlite', ...args];
} else {
  console.error('\n[fastmcp-sqlite] Error: No Python runtime or package runner found.');
  console.error('[fastmcp-sqlite] Please install uv (recommended: https://astral.sh/uv) or Python 3.10+.\n');
  process.exit(1);
}

const child = spawn(runner, runnerArgs, {
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: {
    ...process.env,
    PYTHONUTF8: '1',
    PYTHONUNBUFFERED: '1'
  }
});

child.on('error', (err) => {
  console.error('[fastmcp-sqlite] Execution error:', err.message);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code || 0);
});
