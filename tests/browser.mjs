// Minimal deployment qualification. Requires playwright@1.56.1 (installed by CI).
import { chromium } from 'playwright';
import { spawn } from 'node:child_process';

const PORT = 8765;
const origin = 'http://127.0.0.1:' + PORT + '/';
const server = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1',
  '--directory', '_site'], { stdio: 'ignore' });

let browser;
try {
  for (let i = 0; i < 40; i++) {
    try {
      if ((await fetch(origin)).ok) break;
    } catch { /* not ready */ }
    if (i === 39) throw new Error('static test server unavailable');
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  const exceptions = [];
  const consoleMessages = [];
  const failedRequests = [];
  const githubRequests = [];
  const githubResponses = [];
  page.on('pageerror', error => exceptions.push(String(error)));
  page.on('console', msg => { if (['error', 'warning'].includes(msg.type())) consoleMessages.push(msg.text()); });
  page.on('requestfailed', req => failedRequests.push(req.url() + ' -> ' + req.failure()?.errorText));
  page.on('request', req => { if (req.url().includes('github')) githubRequests.push(req.url()); });
  page.on('response', response => {
    if (response.url().startsWith('https://api.github.com/repos/octocat/Hello-World')) {
      githubResponses.push({ url: response.url(), status: response.status(), ok: response.ok() });
    }
  });
  const response = await page.goto(origin, { waitUntil: 'domcontentloaded', timeout: 60000 });
  if (!response?.ok()) throw new Error('workbench document unavailable');
  await page.locator('.monaco-workbench').waitFor({ timeout: 60000 });
  const config = await page.locator('#vscode-workbench-web-configuration')
    .getAttribute('data-settings');
  const settings = JSON.parse(config);
  if (settings.productConfiguration.enableTelemetry !== false) {
    throw new Error('host telemetry enabled');
  }
  if (settings.configurationDefaults['workbench.colorTheme'] !== 'Default Dark+') {
    throw new Error('dark theme not configured');
  }
  if (settings.additionalBuiltinExtensions.length !== 2) {
    throw new Error('expected host and GitHub provider are not preloaded');
  }
  if (settings.workspaceProvider.workspace?.folderUri?.scheme !== 'remotish-github') {
    throw new Error('public GitHub sample workspace not selected');
  }
  await page.locator('.monaco-workbench.vs-dark').waitFor({ timeout: 60000 });
  for (let i = 0; i < 40 && !githubResponses.some(x => x.ok); i++) {
    await new Promise(resolve => setTimeout(resolve, 1000));
  }
  if (!githubResponses.some(x => x.ok)) {
    const view = await page.locator('body').innerText().catch(() => '<body unavailable>');
    const diagnostics = { githubResponses, githubRequests: githubRequests.slice(-30),
      exceptions, consoleMessages: consoleMessages.slice(-30), failedRequests: failedRequests.slice(-30),
      visibleText: view.slice(0, 3000) };
    console.error('Browser diagnostics:', JSON.stringify(diagnostics, null, 2));
    throw new Error('Remotish GitHub provider did not successfully query public GitHub');
  }
  if (exceptions.length) throw new Error('browser exceptions: ' + exceptions.join('\n'));
  console.log('browser qualification passed: workbench, dark theme, builtins, public GitHub');
} finally {
  await browser?.close();
  server.kill('SIGTERM');
}
