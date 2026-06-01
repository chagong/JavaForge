/**
 * Launches VS Code with a CDP remote-debugging port so playwright-cli can attach.
 * If a VS Code instance is already listening on the CDP port, it is reused and
 * no new process is spawned.
 *
 * Usage:
 *   node launch-vscode.js [port]          (default port: 9222)
 *   CDP_PORT=9223 node launch-vscode.js
 *   VSCODE_PATH="C:\..." node launch-vscode.js
 */

const { spawn, execSync } = require('child_process');
const { existsSync } = require('fs');
const path = require('path');
const http = require('http');

const args = process.argv.slice(2);
const USE_INSIDERS = process.env.VSCODE_INSIDERS !== '0' &&
  !args.includes('--stable') && !args.includes('stable');

const portArg = args.find(a => /^\d+$/.test(a));
const PORT = portArg || process.env.CDP_PORT || '9222';

// Optional project folder to open: VSCODE_FOLDER env var or a positional path arg
const folderArg = args.find(a => !/^\d+$/.test(a) && a !== 'stable' && a !== '--stable' && a !== 'insiders' && a !== '--insiders');
const FOLDER = process.env.VSCODE_FOLDER || folderArg || null;

function findSystemVSCode() {
  if (process.env.VSCODE_PATH && existsSync(process.env.VSCODE_PATH)) {
    return process.env.VSCODE_PATH;
  }

  const insidersCandidates = [
    // Windows user install
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Microsoft VS Code Insiders', 'Code - Insiders.exe'),
    // Windows system install
    'C:\\Program Files\\Microsoft VS Code Insiders\\Code - Insiders.exe',
    // macOS
    '/Applications/Visual Studio Code - Insiders.app/Contents/MacOS/Electron',
    // Linux
    '/usr/bin/code-insiders',
    '/snap/bin/code-insiders',
  ];

  const stableCandidates = [
    path.join(process.env.LOCALAPPDATA || '', 'Programs', 'Microsoft VS Code', 'Code.exe'),
    'C:\\Program Files\\Microsoft VS Code\\Code.exe',
    'C:\\Program Files (x86)\\Microsoft VS Code\\Code.exe',
    '/Applications/Visual Studio Code.app/Contents/MacOS/Electron',
    '/usr/bin/code',
    '/snap/bin/code',
  ];

  const ordered = USE_INSIDERS
    ? [...insidersCandidates, ...stableCandidates]
    : [...stableCandidates, ...insidersCandidates];

  for (const p of ordered) {
    if (p && existsSync(p)) return p;
  }

  // Try PATH
  const pathCmds = USE_INSIDERS
    ? ['code-insiders', 'code']
    : ['code', 'code-insiders'];

  for (const cmd of pathCmds) {
    try {
      const which = process.platform === 'win32' ? `where ${cmd}` : `which ${cmd}`;
      const result = execSync(which, { encoding: 'utf8' });
      const first = result.trim().split('\n')[0].trim();
      if (first && existsSync(first)) return first;
    } catch {}
  }

  return null;
}

function isCDPReady(port) {
  return new Promise(resolve => {
    http.get(`http://localhost:${port}/json/version`, res => {
      res.resume();
      resolve(true);
    }).on('error', () => resolve(false));
  });
}

function waitForCDP(port, maxAttempts = 40) {
  return new Promise(resolve => {
    let attempts = 0;
    const check = () => {
      attempts++;
      http.get(`http://localhost:${port}/json/version`, res => {
        let data = '';
        res.on('data', chunk => { data += chunk; });
        res.on('end', () => resolve(true));
      }).on('error', () => {
        if (attempts < maxAttempts) {
          setTimeout(check, 1000);
        } else {
          resolve(false);
        }
      });
    };
    setTimeout(check, 1500); // initial wait for VS Code to start
  });
}

async function main() {
  // Reuse an existing VS Code instance if CDP is already available
  if (await isCDPReady(PORT)) {
    console.log(`\n✓ VS Code already running on CDP port ${PORT} — reusing existing instance`);
    console.log(`  CDP: http://localhost:${PORT}`);
    console.log('\nNext steps:');
    console.log(`  playwright-cli attach --cdp=http://localhost:${PORT}`);
    console.log('  playwright-cli tab-list        # find the main workbench target');
    console.log('  playwright-cli snapshot         # capture initial UI tree');
    return;
  }

  let vscodeExe = findSystemVSCode();

  if (!vscodeExe) {
    const version = USE_INSIDERS ? 'insiders' : 'stable';
    console.log(`System VS Code${USE_INSIDERS ? ' Insiders' : ''} not found — downloading via @vscode/test-electron...`);
    try {
      const { downloadAndUnzipVSCode } = require('@vscode/test-electron');
      vscodeExe = await downloadAndUnzipVSCode(version);
      console.log(`Downloaded: ${vscodeExe}`);
    } catch (e) {
      console.error('Failed to download VS Code:', e.message);
      console.error('Run: npm install  (in .github/skills/vscode-probe)');
      process.exit(1);
    }
  } else {
    console.log(`Found VS Code: ${vscodeExe}`);
  }

  console.log(`Launching with --remote-debugging-port=${PORT} ...`);

  const spawnArgs = [
    `--remote-debugging-port=${PORT}`,
    '--no-sandbox',
    '--no-first-run',
  ];
  if (FOLDER) {
    spawnArgs.push(FOLDER);
    console.log(`Opening folder: ${FOLDER}`);
  }

  const proc = spawn(vscodeExe, spawnArgs, { stdio: 'ignore', detached: true, windowsHide: false });

  proc.unref();
  console.log(`VS Code PID: ${proc.pid}`);
  console.log('Waiting for CDP endpoint...');

  const ready = await waitForCDP(PORT);

  if (ready) {
    console.log('\n✓ VS Code is ready');
    console.log(`  CDP: http://localhost:${PORT}`);
    console.log('\nNext steps:');
    console.log(`  playwright-cli attach --cdp=http://localhost:${PORT}`);
    console.log('  playwright-cli tab-list        # find the main workbench target');
    console.log('  playwright-cli snapshot         # capture initial UI tree');
  } else {
    console.warn('\nCDP not ready after 40 s — VS Code may still be loading.');
    console.log(`Try manually: playwright-cli attach --cdp=http://localhost:${PORT}`);
  }
}

main().catch(e => { console.error(e.message); process.exit(1); });
