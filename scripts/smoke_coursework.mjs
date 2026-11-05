/** Real API + production UI coursework regression using disposable study data. */
import assert from 'node:assert/strict';
import { createServer, request as httpRequest } from 'node:http';
import { readFile, mkdtemp, mkdir } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { resolve, extname, sep, join } from 'node:path';
import { spawn } from 'node:child_process';
import { chromium, webkit } from 'playwright';

const data = await mkdtemp(join(tmpdir(), 'colloquily-coursework-browser-'));
const root = resolve('frontend/dist');
const pdf = await readFile('tests/frontend/fixtures/reader.pdf');
const policy = JSON.parse(await readFile('src-tauri/tauri.conf.json', 'utf8')).app.security.csp;
const python = process.env.COLLOQUILY_TEST_PYTHON || resolve('.venv/bin/python');
const portServer = createServer();
await new Promise(resolve => portServer.listen(0, '127.0.0.1', resolve));
const backendPort = portServer.address().port;
await new Promise(resolve => portServer.close(resolve));
const backend = spawn(python, ['-m', 'backend.launcher', '--port', String(backendPort), '--data-dir', data], { stdio: ['ignore', 'pipe', 'pipe'] });
let backendLog = '';
backend.stdout.on('data', bytes => { backendLog += bytes; });
backend.stderr.on('data', bytes => { backendLog += bytes; });
const apiOrigin = `http://127.0.0.1:${backendPort}`;
const mime = { '.js':'text/javascript', '.mjs':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml', '.wasm':'application/wasm', '.html':'text/html' };
const server = createServer(async (req, res) => {
  if (req.url.startsWith('/api/')) {
    const upstream = httpRequest(apiOrigin + req.url, { method: req.method, headers: { ...req.headers, host:`127.0.0.1:${backendPort}`, origin:'http://127.0.0.1:5173' } }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res); });
    upstream.on('error', () => res.writeHead(502).end()); req.pipe(upstream); return;
  }
  const pathname = new URL(req.url, 'http://localhost').pathname;
  const path = resolve(root, '.' + (pathname === '/' ? '/index.html' : decodeURIComponent(pathname)));
  if (!path.startsWith(root + sep)) { res.writeHead(404).end(); return; }
  try { res.writeHead(200, { 'Content-Type':mime[extname(path)] || 'application/octet-stream', 'Content-Security-Policy':policy }); res.end(await readFile(path)); }
  catch { res.end(); }
});
try {
  let ready = false;
  for (let attempt = 0; attempt < 100; attempt++) {
    try { ready = (await fetch(apiOrigin + '/api/health')).ok; } catch { /* startup */ }
    if (ready) break;
    await new Promise(resolve => setTimeout(resolve, 200));
  }
  assert.ok(ready, backendLog);
  await mkdir('output/playwright', { recursive:true });
  await mkdir('output/pdf', { recursive:true });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const origin = `http://127.0.0.1:${server.address().port}`;
  for (const [name, type] of [['chromium',chromium],['webkit',webkit]]) {
    const response = await fetch(apiOrigin + '/api/exams', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:`FOLOG ${name}`})});
    const exam = await response.json();
    const browser = await type.launch();
    try {
      const page = await browser.newPage({viewport:{width:1440,height:1080},acceptDownloads:true});
      const errors = [];
      page.on('response', async response => {
        if (response.url().includes('/api/') && response.status() >= 400) console.error('API failure', response.status(), response.url(), await response.text());
      });
      page.on('pageerror', error => errors.push(String(error)));
      await page.addInitScript(({exam}) => { localStorage.setItem('i18nextLng','en'); localStorage.setItem('colloquily.welcomed','true'); localStorage.setItem('colloquily.exam',String(exam)); }, {exam:exam.id});
      await page.route('**/api/**', async route => {
        const path = new URL(route.request().url()).pathname;
        if (path.includes('/models/')) return route.fulfill({json:path.endsWith('/status') ? {ollama:'unavailable',required:[],installed:[],missing:[]} : {state:'ollama_unavailable'}});
        await route.continue();
      });
      await page.goto(origin);
      await page.getByRole('button',{name:'Exercises',exact:true}).click();
      await page.getByLabel('Course name',{exact:true}).fill('FOLOG & Graphs');
      await page.getByLabel('Semester',{exact:true}).fill('WS26/27');
      await page.getByLabel('Name 1',{exact:true}).fill('Ada Müller');
      await page.getByLabel('Matrikelnummer',{exact:true}).fill('001234');
      await page.getByRole('button',{name:'Add partner',exact:true}).click();
      await page.getByLabel('Name 2',{exact:true}).fill('Emmy Noether');
      await page.getByLabel('Matrikelnummer',{exact:true}).nth(1).fill('005678');
      await page.getByRole('button',{name:'Save submission details',exact:true}).click();
      await page.getByLabel('Add exercise sheet (PDF)',{exact:true}).setInputFiles({name:'Exercise 1.pdf',mimeType:'application/pdf',buffer:pdf});
      const editor = page.getByLabel('LaTeX solution',{exact:true});
      const solution = String.raw`\section*{Problem 1}
\begin{proof}
Let $P$ be a permutation matrix. Since $P^T\mathbf{1}_n=\mathbf{1}_n$,
\[
\mu(PX)=\frac{1}{n}(PX)^T\mathbf{1}_n
=\frac{1}{n}X^TP^T\mathbf{1}_n=\mu(X).
\]
Thus $\mu$ is permutation invariant.
\end{proof}
\section*{Problem 2}
\begin{enumerate}
\item The centering operation is permutation equivariant:
\[ F(PX)=PX-\mathbf{1}_n\mu(X)^T=PF(X). \]
\item Therefore the covariance is invariant:
\[ C(PX)=\frac{1}{n}F(X)^TP^TPF(X)=C(X). \]
\end{enumerate}`;
      try { await editor.fill(solution); } catch (error) { console.error(await page.locator('body').innerText()); await page.screenshot({path:`output/playwright/coursework-failure-${name}.png`,fullPage:true}); throw error; }
      await page.getByRole('button',{name:'Materials',exact:true}).click();
      await page.getByRole('button',{name:'Exercises',exact:true}).click();
      await editor.waitFor();
      assert.equal(await editor.inputValue(),solution,'unsaved draft survives navigation');
      await page.getByRole('button',{name:'Save solution',exact:true}).click();
      await page.getByRole('button',{name:'Export .tex',exact:true}).waitFor();
      const texDownload = page.waitForEvent('download');
      await page.getByRole('button',{name:'Export .tex',exact:true}).click();
      await (await texDownload).saveAs(`output/pdf/coursework-${name}.tex`);
      const pdfDownload = page.waitForEvent('download');
      await page.getByRole('button',{name:'Export PDF',exact:true}).click();
      await (await pdfDownload).saveAs(`output/pdf/coursework-${name}.pdf`);
      const exported = page.locator('article').filter({has:page.getByRole('heading',{name:'Exported submission',exact:true})});
      await exported.locator('canvas:visible').waitFor();
      assert.ok(await exported.locator('canvas').evaluate(canvas => {
        const pixels = canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data;
        let ink = 0;
        for (let i = 0; i < pixels.length; i += 4) {
          if (pixels[i] < 180 && pixels[i+1] < 180 && pixels[i+2] < 180 && pixels[i+3] > 0) ink++;
        }
        return ink > 50;
      }), 'exported PDF preview contains rendered content');
      await page.screenshot({path:`output/playwright/coursework-${name}.png`,fullPage:true});
      await page.getByRole('button',{name:'Materials',exact:true}).click();
      await page.getByLabel('Upload lecture script (PDF)',{exact:true}).setInputFiles({name:'script-until-5.pdf',mimeType:'application/pdf',buffer:pdf});
      await page.getByLabel('Upload updated script (PDF)',{exact:true}).waitFor();
      const second = await readFile(`output/pdf/coursework-${name}.pdf`);
      await page.getByLabel('Upload updated script (PDF)',{exact:true}).setInputFiles({name:'script-until-6.pdf',mimeType:'application/pdf',buffer:second});
      await page.getByText('script-until-6.pdf',{exact:true}).first().waitFor();
      assert.equal(await page.locator('.document-grid article').count(),1,'only one active script card');
      await page.screenshot({path:`output/playwright/script-${name}.png`,fullPage:true});
      assert.deepEqual(errors,[]);
      console.log(`${name}: exercise upload, recovery draft, save, .tex/PDF export, PDF canvas and script replacement passed`);
    } finally { await browser.close(); }
    // Keep the next browser's course selection unambiguous.
    await fetch(`${apiOrigin}/api/exams/${exam.id}`,{method:'DELETE'});
  }
} finally {
  server.closeAllConnections(); server.close(); backend.kill('SIGTERM');
}
