/** Exercise the built reader under the exact desktop CSP, never a dev server. */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile, mkdir } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { chromium, webkit } from "playwright";

await mkdir("output/playwright", { recursive: true });
const root = resolve("frontend/dist");
const policy = JSON.parse(await readFile("src-tauri/tauri.conf.json", "utf8"))
  .app.security.csp;
const pdf = await readFile("tests/frontend/fixtures/reader.pdf");
const token = "disposable-pdf-regression-token";
const mime = {
  ".js": "text/javascript",
  ".mjs": "text/javascript",
  ".css": "text/css",
  ".svg": "image/svg+xml",
  ".wasm": "application/wasm",
  ".html": "text/html",
};
const server = createServer(async (req, res) => {
  const path = resolve(
    root,
    "." +
      decodeURIComponent(
        new URL(req.url, "http://localhost").pathname === "/"
          ? "/index.html"
          : new URL(req.url, "http://localhost").pathname,
      ),
  );
  if (!path.startsWith(root + sep)) {
    res.writeHead(404).end();
    return;
  }
  try {
    const bytes = await readFile(path);
    res.writeHead(200, {
      "Content-Type": mime[extname(path)] || "application/octet-stream",
      "Content-Security-Policy": policy,
    });
    res.end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = `http://127.0.0.1:${server.address().port}`;
try {
  for (const [name, type] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    if (process.env.PDF_BROWSER && process.env.PDF_BROWSER !== name) continue;
    const browser = await type.launch();
    try {
      const page = await browser.newPage();
      const crashes = [];
      page.on("pageerror", (e) => crashes.push(String(e)));
      await page.addInitScript(
        ({ origin, token }) => {
          window.learningReferencesOpened = [];
          window.__TAURI_INTERNALS__ = {
            invoke: async (command, args) => {
              if (command === "backend_connection")
                return { url: origin, token };
              if (command === "open_learning_reference")
                window.learningReferencesOpened.push(args.reference);
              return null;
            },
          };
          window.pdfPolicyViolations = [];
          document.addEventListener("securitypolicyviolation", (e) =>
            window.pdfPolicyViolations.push(
              e.violatedDirective + ": " + e.blockedURI,
            ),
          );
        },
        { origin, token },
      );
      let failSource = false,
        failNotes = false,
        sourceRequests = 0;
      let emptyWorkspace = false;
      let language = "en";
      let modelSettings = {
        task_models: Object.fromEntries(
          [
            "cleaning",
            "topic_extraction",
            "question_generation",
            "answer_evaluation",
            "answering",
            "examiner_follow_up",
          ].map((task) => [task, "qwen3:4b"]),
        ),
        embedding_config: { model: "embeddinggemma:latest" },
      };
      let runtimeState = 'available';
      let modelsReady = true;
      let setupDownloads = 0;
      let practiceReady = false;
      let practiceSession = {id: 901, subject_id: 1, status: 'created', remaining_seconds: 60, countdown_visible: true, sources: [{id:1,document_title:'Lecture',relative_path:'Lecture & Übung.pdf',source_start:2,source_location:'page 2',content:'Mass and energy are related by $E=mc^2$.'}], current_question: {id: 77, question_text: 'Explain why $E=mc^2$ relates mass and energy.'}};
      let practiceRun = {id: 900, status: 'running', mode: 'random_practice', sessions: [practiceSession]};
      const chatHistory = [];
      const notes = { 1: "Saved first-page note" };
      await page.route("**/api/**", async (route) => {
        const request = route.request();
        const path = decodeURIComponent(
          new URL(request.url()).pathname.slice(4),
        );
        if (path !== "/health")
          assert.equal(
            request.headers()["x-colloquily-token"],
            token,
            "PDF transport must retain the desktop launch token",
          );
        const json = (value) => route.fulfill({ json: value });
        if (path === "/health") return json({ status: "ready" });
        if (path === "/preferences") {
          if (request.method() === 'PATCH') language = request.postDataJSON().language;
          return json({language});
        }
        if (path === '/settings') return json({values:{},data_directory:'/local/Colloquily',sections:[]});
        if (path === "/models/status")
          return json({
            ollama: runtimeState,
            installed: ["qwen3:4b", "gemma3:4b"],
            required: [],
            missing: [],
          });
        if (path === "/system/storage")
          return json({ free_bytes: 30 * 1024 ** 3 });
        if (path === "/exams/1/models") {
          if (request.method() === "PATCH") {
            const body = request.postDataJSON();
            modelSettings = {
              task_models: body.task_models,
              embedding_config: { model: body.embedding_model },
            };
          }
          return json(modelSettings);
        }
        if (path === '/exams/1/history') return json([...chatHistory].reverse());
        if (path === '/exams/1/ask') {
          const body = request.postDataJSON();
          assert.deepEqual(body.history_ids, chatHistory.slice(-4).map(turn => turn.id));
          chatHistory.push({id:chatHistory.length+1,input_text:body.question,output_text:'Mass and energy are related by $E=mc^2$.',sources:[]});
          return json({id:'chat-job',status:'completed',result:{}});
        }
        if (path === '/practice') {
          if (request.method() === 'GET') return json(practiceRun.status === 'running' ? [{id:900,status:'running'}] : []);
          practiceSession.status = 'created';
          practiceRun.status = 'running';
          practiceRun.mode = request.postDataJSON().mode;
          assert.ok([300,600,900,1800,2700,3600,5400].includes(request.postDataJSON().session_duration_seconds));
          const selected = request.postDataJSON().subject_ids;
          assert.equal(selected.length, practiceRun.mode === 'full_colloquium' ? 3 : practiceRun.mode === 'multi_subject' ? 2 : 1);
          return json(practiceRun);
        }
        if (path === '/sessions/901/begin') { practiceSession.status = 'answering'; return json(practiceSession); }
        if (path === '/sessions/901') return json(practiceSession);
        if (path === '/practice/900') return json(practiceRun);
        if (path === '/practice/900/finish') { practiceSession.status = 'completed'; practiceRun.status = 'completed'; return json({}); }
        if (path === '/sessions/901/answer') {
          assert.match(request.postDataJSON().answer, /energy/);
          practiceSession.status = 'completed';
          practiceRun.status = 'completed';
          practiceRun.evaluation_status = 'completed';
          const point = 'Explain the relationship between mass and energy.';
          practiceSession.attempts = [
            {id:1,question_text:'Explain mass and energy.',answer_text:request.postDataJSON().answer,evaluation:{status:'evaluated',score:1,missing:[{text:point}],expected_core_points:[{text:point}],better_oral_answer:point,sources:practiceSession.sources,subject_id:1}},
            {id:2,question_text:'Define a physical quantity.',answer_text:'My second submitted answer.',evaluation:{status:'evaluated',score:4,correct:[{text:'A supported definition.'}]}},
            {id:3,question_text:'Skipped question.',answer_text:'',evaluation:{status:'skipped',score:0}},
            {id:4,question_text:'Uncertain question.',answer_text:'My uncertain answer.',evaluation:{status:'needs_review',score:0}},
          ];
          return json({id: 'practice-answer-job', status: 'completed', result: {session: practiceSession, evaluation: {status:'evaluated', score:1, correct:[{text:'Mass and energy are related.'}], missing:[], incorrect:[], sources:[]}}});
        }
        if (path === "/exams" && request.method() === "POST") {
          assert.equal(request.postDataJSON().name, "Quantum physics");
          emptyWorkspace = false;
          return json({
            id: 1,
            name: "Quantum physics",
            slug: "quantum-physics",
            exam_duration_minutes: 15,
          });
        }
        if (path === "/exams")
          return json(
            emptyWorkspace
              ? []
              : [
                  {
                    id: 1,
                    name: "Quantum physics",
                    slug: "pdf-regression",
                    exam_duration_minutes: 15,
                  },
                  {id:2,name:"Second exam",slug:"second",exam_duration_minutes:15},
                  {id:3,name:"Third exam",slug:"third",exam_duration_minutes:15},
                ],
          );
        if (path.endsWith('/models/readiness')) return json({state: runtimeState !== 'available' ? 'ollama_unavailable' : modelsReady ? 'ready' : 'models_missing'});
        if (path.endsWith('/models/recommendation')) return json({task_models:modelSettings.task_models, missing:modelsReady ? [] : ['qwen3:4b','embeddinggemma:latest'],download_bytes_estimate:modelsReady ? 0 : 5 * 1024**3,disk_ok:true,limited_hardware:false,hardware:{ram_bytes:16*1024**3,free_bytes:30*1024**3,architecture:'arm64'}});
        if (path === '/models/start') {runtimeState='available';return json({id:'start',status:'completed',result:{ready:true}});}
        if (path.endsWith('/models/prepare')) {setupDownloads++;modelsReady=true;return json({id:'prepare',status:'completed',result:{}});}
        if (path.endsWith('/models/verify')) return json({id:'verify',status:'completed',completed:1,total:2,result:{ready:true,response_seconds:2.5,slow:false}});
        if (path.endsWith("/learning"))
          return json({
            goal: { exam_date: null, repetitions: 3, questions_per_session: 5 },
            plan: {
              eligible_questions: 0,
              total: 0,
              completed: 0,
              remaining: 0,
              schedule: [],
              days_left: null,
            },
            topics: [],
            activity: [],
            today_target: 0,
            today_completed: 0,
            streak: 0,
            practised_questions: 0,
            average_score: null,
          });
        if (path.endsWith("/preparation"))
          return json({ job: null, questions: practiceReady ? 3 : 0 });
        if (path === "/exams/1/documents")
          return json({
            raw: ["Lecture & Übung.pdf"],
            documents: [
              {
                id: 1,
                title: "Lecture & Übung",
                relative_path: "Lecture & Übung.pdf",
                created_at: "2026-10-20",
                processing_status: "raw",
                extraction: { pages_total: 2 },
              },
            ],
          });
        if (path === "/exams/1/sources/Lecture & Übung.pdf") {
          sourceRequests++;
          if (failSource) {
            failSource = false;
            return route.fulfill({
              status: 503,
              body: "Temporary source failure",
            });
          }
          return route.fulfill({ contentType: "application/pdf", body: pdf });
        }
        if (path === "/exams/1/documents/1/notes") {
          if (failNotes) {
            failNotes = false;
            return route.fulfill({
              status: 503,
              body: "Temporary notes failure",
            });
          }
          return json(
            Object.entries(notes).map(([page, content]) => ({
              page: Number(page),
              content,
            })),
          );
        }
        const notePage = path.match(/^\/exams\/1\/documents\/1\/notes\/(\d+)$/);
        if (notePage && request.method() === "PUT") {
          notes[notePage[1]] = request.postDataJSON().content;
          return json({ saved: true });
        }
        throw new Error("Unexpected regression request: " + path);
      });
      await page.goto(origin);
      await page
        .getByRole("navigation", { name: "Your learning" })
        .getByRole("button", { name: "Materials", exact: true })
        .click();
      const open = () =>
        page.getByRole("button", { name: "Open PDF", exact: true }).click();
      const rendered = async () => {
        await page.waitForFunction(() => {
          const c = document.querySelector("canvas");
          if (!c || c.width <= 300) return false;
          const bytes = c
            .getContext("2d")
            .getImageData(0, 0, c.width, c.height).data;
          let black = 0;
          for (let i = 0; i < bytes.length; i += 4)
            if (
              bytes[i] < 180 &&
              bytes[i + 1] < 180 &&
              bytes[i + 2] < 180 &&
              bytes[i + 3] > 0
            )
              black++;
          return black > 50;
        });
      };
      const close = () =>
        page.getByRole("button", { name: "Close source", exact: true }).click();
      await open();
      await rendered();
      for (const width of [390, 750, 850, 1280, 1920, 2560, 3440]) {
        await page.setViewportSize({ width, height: 1000 });
        const layout = await page.evaluate(() => {
          const main = document.querySelector(".shell > main");
          const rect = main.getBoundingClientRect();
          const sidebar = document
            .querySelector(".shell > aside")
            .getBoundingClientRect();
          const section = main.querySelector("section").getBoundingClientRect();
          const style = getComputedStyle(main);
          return {
            overflow: document.documentElement.scrollWidth - innerWidth,
            leftGap: rect.left - (innerWidth > 750 ? sidebar.right : 0),
            rightGap: innerWidth - rect.right,
            sectionWidth: section.width,
            contentWidth:
              rect.width -
              parseFloat(style.paddingLeft) -
              parseFloat(style.paddingRight),
          };
        });
        assert.ok(
          layout.overflow <= 1,
          `${name}: horizontal overflow at ${width}px: ${JSON.stringify(layout)}`,
        );
        assert.ok(
          Math.abs(layout.leftGap - layout.rightGap) <= 1,
          `${name}: workspace is not centered at ${width}px`,
        );
        assert.ok(
          Math.abs(layout.sectionWidth - layout.contentWidth) <= 1,
          `${name}: page does not fill workspace at ${width}px`,
        );
      }
      await page.setViewportSize({ width: 1280, height: 1000 });
      assert.equal(await page.getByRole("alert").count(), 0);
      await page.locator(".page-notes textarea:not(:disabled)").waitFor();
      assert.equal(
        await page.locator(".page-notes textarea").inputValue(),
        notes[1],
      );
      await page
        .getByRole("button", { name: "Next page", exact: true })
        .click();
      await page
        .getByRole("textbox", { name: "Your notes · page 2", exact: true })
        .fill("Page-two note");
      await close();
      await open();
      await rendered();
      await page.locator(".page-notes textarea:not(:disabled)").waitFor();
      assert.equal(
        await page
          .getByRole("spinbutton", { name: "Page", exact: true })
          .inputValue(),
        "2",
      );
      assert.equal(
        await page.locator(".page-notes textarea").inputValue(),
        "Page-two note",
      );
      await page.locator(".page-notes textarea").fill(String.raw`# Formula notes

Inline $x^2$ and display:

$$
\frac{a}{b}
$$

| Quantity | Value |
| --- | --- |
| Energy | $mc^2$ |

<script>window.untrustedMath = true</script>`);
      await page.locator(".page-notes .katex-display").waitFor();
      assert.equal(
        await page.locator(".page-notes .study-text table").count(),
        1,
      );
      assert.equal(await page.evaluate(() => window.untrustedMath), undefined);
      await page.screenshot({
        path: `output/playwright/math-notes-${name}.png`,
        fullPage: true,
      });
      const [download] = await Promise.all([
        page.waitForEvent("download"),
        page
          .getByRole("button", {
            name: "Export notes as Markdown",
            exact: true,
          })
          .click(),
      ]);
      assert.equal(download.suggestedFilename(), "study-notes.md");
      await close();
      failSource = true;
      const attempts = sourceRequests;
      await open();
      await page
        .getByRole("button", { name: "Retry opening PDF", exact: true })
        .waitFor();
      await page
        .getByRole("button", { name: "Retry opening PDF", exact: true })
        .click();
      await rendered();
      assert.equal(
        sourceRequests,
        attempts + 2,
        "Retry must reload the PDF, not just clear its error",
      );
      await close();
      failNotes = true;
      await open();
      await rendered();
      await page
        .getByRole("button", { name: "Retry notes", exact: true })
        .waitFor();
      assert.equal(
        await page
          .getByRole("button", { name: "Retry opening PDF", exact: true })
          .count(),
        0,
        "A notes error must not mark the PDF as damaged",
      );
      await page
        .getByRole("button", { name: "Retry notes", exact: true })
        .click();
      await page.locator(".page-notes textarea:not(:disabled)").waitFor();
      assert.deepEqual(
        await page.evaluate(() => window.pdfPolicyViolations),
        [],
      );
      await close();
      practiceReady = true;
      await page.getByRole("navigation", { name: "Your learning" }).getByRole("button", { name: "Practice", exact: true }).click();
      await page.locator(".mode-card").first().waitFor();
      assert.equal(await page.locator(".mode-card").count(), 8);
      await page.screenshot({
        path: `output/playwright/practice-modes-${name}.png`,
        fullPage: true,
      });
      await page
        .getByRole("button", { name: /One question, then detailed feedback/ })
        .click();
      assert.equal(
        await page.locator('.mode-card[aria-pressed="true"]').count(),
        1,
      );
      const guide = page.locator("#practice-mode-guide");
      await guide
        .getByText("Why this can help · learning research", { exact: true })
        .click();
      await guide.getByRole("link", { name: /Roediger & Karpicke/ }).click();
      await page.waitForFunction(
        () => window.learningReferencesOpened.length === 1,
      );
      assert.deepEqual(
        await page.evaluate(() => window.learningReferencesOpened),
        ["retrieval"],
      );
      assert.equal(
        await guide.getByRole("link", { name: /Bisra/ }).getAttribute("href"),
        "https://doi.org/10.1007/s10648-018-9434-x",
      );
      assert.ok((await guide.innerText()).includes("speech is not assessed"));
      const modeNames = [
        "Single question",
        "Random practice",
        "Weak topic",
        "Oral exam simulation",
        "Rapid practice",
        "Subject simulation",
        "Multiple subjects",
        "Full colloquium",
      ];
      for (const title of modeNames) {
        await page.getByRole("button", { name: "Close mode setup" }).click();
        await page
          .locator(".mode-card")
          .filter({
            has: page.locator("strong", { hasText: new RegExp(`^${title}$`) }),
          })
          .click();
        assert.equal(
          await guide.getByRole("heading", { level: 3 }).innerText(),
          title,
        );
        assert.equal(await guide.locator("dt").count(), 3);
        assert.ok((await guide.innerText()).includes("After practice:"));
      }
      assert.ok(
        (await guide.innerText()).includes(
          "Exactly three exams. Default: 15 minutes per subject",
        ),
      );
      await page.getByRole("button", { name: "Close mode setup" }).click();
      await page
        .locator(".mode-card")
        .filter({ hasText: "Random practice" })
        .click();
      await guide
        .getByText("Why this can help · learning research", { exact: true })
        .click();
      assert.ok(
        (await guide.innerText()).includes(
          "random order is not automatically interleaving",
        ),
      );
      await guide.screenshot({
        path: `output/playwright/practice-learning-${name}.png`,
      });
      await page.setViewportSize({ width: 390, height: 900 });
      assert.ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth - innerWidth <= 1,
        ),
      );
      await page.setViewportSize({ width: 1280, height: 1000 });
      assert.equal(await page.getByText('Previous runs', {exact:true}).count(), 0);
      assert.equal(await page.locator('.timer-cards button').count(),7);
      await page.locator('.timer-cards button').filter({has:page.locator('strong',{hasText:/^90$/})}).click();
      assert.equal(await page.locator('.timer-cards button[aria-pressed="true"] strong').innerText(),'90');
      await page.screenshot({path:`output/playwright/practice-timers-${name}.png`,fullPage:true});
      await page.getByRole('button', {name:'Start practising', exact:true}).click();
      await page.locator('.session-question .katex').first().waitFor();
      assert.equal(await page.locator('aside').isVisible(), false);
      assert.equal(await page.locator('.window-toolbar').isVisible(), false);
      assert.equal(await page.getByRole('textbox', {name:'Your oral answer'}).count(), 1);
      await page.locator('.session-reference > summary').click();
      await page.locator('.insight-pdf canvas').waitFor({state:'visible'});
      await page.getByText('Page 2 / 2',{exact:true}).waitFor();
      assert.equal(await page.locator('.source-insight iframe').count(),0);
      await page.screenshot({path:`output/playwright/insight-source-${name}.png`,fullPage:true});
      await page.locator('.session-reference > summary').click();
      failSource=true;
      await page.locator('.session-reference > summary').click();
      await page.getByRole('button',{name:'Retry preview',exact:true}).waitFor();
      await page.getByRole('button',{name:'Retry preview',exact:true}).click();
      await page.locator('.insight-pdf canvas').waitFor({state:'visible'});
      await page.locator('.session-reference > summary').click();
      await page.getByRole('textbox', {name:'Your oral answer'}).fill('Mass is a form of energy.');
      await page.screenshot({path:`output/playwright/practice-ambient-${name}.png`, fullPage:true});
      await page.emulateMedia({colorScheme:'dark'});
      await page.screenshot({path:`output/playwright/practice-ambient-dark-${name}.png`, fullPage:true});
      await page.emulateMedia({colorScheme:'light'});
      await page.getByRole('button', {name:'Submit answer', exact:true}).click();
      await page.getByRole('heading', {name:'A moment to reflect', exact:true}).waitFor();
      assert.equal(await page.locator('.session-question').count(), 0);
      assert.ok((await page.locator('.submitted-answer').innerText()).includes('Mass is a form of energy.'));
      await page.getByRole('button', {name:'Continue', exact:true}).click();
      await page.getByRole('heading', {name:'Session complete', exact:true}).waitFor();
      await page.locator('.result-chart-row').first().waitFor();
      assert.equal(await page.locator('.result-chart-row').count(),4);
      assert.equal(await page.locator('.result-detail').getByText('Explain the relationship between mass and energy.',{exact:true}).count(),1);
      assert.ok((await page.locator('.result-detail .submitted-answer').innerText()).includes('Mass is a form of energy.'));
      await page.getByRole('button',{name:'Next answer',exact:true}).click();
      assert.ok((await page.locator('.result-detail .submitted-answer').innerText()).includes('My second submitted answer.'));
      await page.getByRole('button',{name:'Previous answer',exact:true}).click();
      await page.screenshot({path:`output/playwright/session-analysis-${name}.png`,fullPage:true});
      await page.emulateMedia({colorScheme:'dark'});
      await page.screenshot({path:`output/playwright/session-analysis-dark-${name}.png`,fullPage:true});
      await page.emulateMedia({colorScheme:'light'});
      await page.getByRole('button', {name:'Back to practice modes', exact:true}).click();
      await page.locator('aside').waitFor({state:'visible'});
      assert.equal(await page.locator('aside').isVisible(), true);
      assert.equal(await page.locator('.mode-card').count(), 8);
      await page.mouse.move(0, 0);
      await page.screenshot({path:`output/playwright/practice-modes-ready-${name}.png`,fullPage:true,animations:'disabled'});
      for (const title of modeNames) {
        await page.locator('.mode-card').filter({has:page.locator('strong',{hasText:new RegExp(`^${title}$`)})}).click();
        if (['Multiple subjects','Full colloquium'].includes(title)) {
          await page.getByRole('checkbox',{name:'Second exam',exact:true}).check();
          if (title === 'Full colloquium') await page.getByRole('checkbox',{name:'Third exam',exact:true}).check();
        }
        await page.getByRole('button',{name:'Start practising',exact:true}).click();
        await page.locator('.session-question').waitFor();
        await page.getByRole('button',{name:'End session',exact:true}).click();
        await page.locator('.mode-card').first().waitFor();
        await page.waitForTimeout(1100);
        assert.equal(await page.locator('.session-question').count(),0);
        assert.equal(await page.locator('aside').isVisible(),true);
      }
      await page.getByRole('navigation', {name:'Your learning'}).getByRole('button', {name:'Chat',exact:true}).click();
      await page.locator('.chat-composer textarea').fill('Explain mass and energy.');
      await page.locator('.chat-composer textarea').press('Enter');
      await page.locator('.chat-assistant .katex').first().waitFor();
      await page.locator('.chat-composer textarea').fill('Can you give an example?');
      await page.locator('.chat-composer textarea').press('Enter');
      await page.waitForFunction(() => document.querySelectorAll('.chat-assistant').length === 2);
      assert.equal(chatHistory.length, 2);
      await page.screenshot({path:`output/playwright/chat-${name}.png`,fullPage:true});
      assert.equal(await page.locator('main > .update-notice').count(),0);
      await page.getByRole('navigation',{name:'Your learning'}).getByRole('button',{name:'Settings',exact:true}).click();
      await page.getByRole('button',{name:'Deutsch DE',exact:true}).click();
      await page.getByRole('heading',{name:'Einstellungen',exact:true}).waitFor();
      assert.equal(language,'de');
      await page.getByRole('button',{name:'English EN',exact:true}).click();
      await page.getByRole('heading',{name:'Settings',exact:true}).waitFor();
      assert.equal(language,'en');
      await page.emulateMedia({colorScheme:'dark'});
      await page.screenshot({path:`output/playwright/settings-refined-${name}.png`,fullPage:true});
      await page.locator('.sidebar-footer button').click();
      await page.locator('.about-dialog[open] .update-notice').waitFor();
      await page.getByRole('button',{name:'Check for updates',exact:true}).waitFor();
      await page.screenshot({path:`output/playwright/about-${name}.png`,fullPage:true});
      await page.getByRole('button',{name:'Close About',exact:true}).click();
      assert.equal(await page.locator('.update-notice').count(),0);
      await page.emulateMedia({colorScheme:'light'});
      language = "de";
      await page.reload();
      await page.getByRole("navigation", { name: "Your learning" }).getByRole("button", { name: "Üben", exact: true }).click();
      await page.locator(".mode-card").filter({ hasText: "Zufällige Übung" }).click();
      await guide
        .getByRole("heading", { name: "Zufällige Übung", exact: true })
        .waitFor();
      assert.ok((await guide.innerText()).includes("So übst du"));
      language = "en";
      await page.reload();
      await page.locator(".advanced-nav > summary").click();
      await page.getByRole("navigation", { name: "Advanced tools" }).getByRole("button", { name: "AI setup", exact: true }).click();
      await page.getByText("Advanced · model library and settings", {exact:true}).click();
      await page.locator(".model-library article").first().waitFor();
      await page
        .locator(".model-library article")
        .filter({
          has: page.getByRole("heading", { name: "gemma3:4b", exact: true }),
        })
        .getByRole("button")
        .click();
      await page
        .getByRole("status")
        .filter({ hasText: "Practice model saved" })
        .waitFor();
      assert.equal(modelSettings.task_models.answer_evaluation, "gemma3:4b");
      assert.equal(modelSettings.task_models.answering, "qwen3:4b");
      assert.equal(
        modelSettings.embedding_config.model,
        "embeddinggemma:latest",
      );
      runtimeState = 'not_running'; modelsReady = false;
      await page.reload();
      await page.locator('.advanced-nav > summary').click();
      await page.getByRole('navigation', {name:'Advanced tools'}).getByRole('button', {name:'AI setup',exact:true}).click();
      await page.getByRole('button', {name:'Start local AI',exact:true}).waitFor();
      assert.equal(setupDownloads,0,'No implicit model download on launch or navigation');
      await page.getByText(/Detected: 16.0 GB RAM/).waitFor();
      await page.getByRole('button', {name:'Start local AI',exact:true}).click();
      await page.getByRole('button', {name:'Download and prepare local AI',exact:true}).click();
      await page.getByRole('button', {name:'Test local AI',exact:true}).click();
      await page.getByText('Local AI responded in 2.5 seconds; document embeddings also work.',{exact:true}).waitFor();
      assert.equal(setupDownloads,1);
      assert.equal(await page.locator('.progress progress').count(),0);
      assert.equal(await page.getByText('50% · 1 / 2',{exact:true}).count(),0);
      await page.screenshot({path:`output/playwright/ai-setup-${name}.png`,fullPage:true});
      await page.getByRole('button',{name:'Continue to materials',exact:true}).click();
      emptyWorkspace = true;
      await page.reload();
      await page
        .getByRole("textbox", { name: "New exam name" })
        .fill("Quantum physics");
      await page
        .getByRole("button", { name: "Create exam & add PDFs →" })
        .click();
      await page
        .getByRole("button", { name: "Open PDF", exact: true })
        .waitFor();
      assert.equal(await page.locator('.setup-steps').count(), 0);
      assert.equal(await page.getByRole('navigation', {name: 'Your learning'}).getByRole('button', {name:'Materials', exact:true}).getAttribute('aria-current'), 'page');
      assert.match(await page.locator('aside .sidebar-footer').innerText(), /Colloquily v0\.1\.9/);
      assert.ok((await page.locator('aside .sidebar-footer').innerText()).includes(`© ${new Date().getFullYear()} Colloquily. All rights reserved.`));
      assert.equal(await page.locator('.app-stamp').count(), 0);
      assert.deepEqual(crashes, []);
      console.log(
        `${name}: production-CSP render, authenticated Unicode filename, navigation, notes, reopen, PDF retry and isolated notes retry passed`,
      );
    } finally {
      await browser.close();
    }
  }
} finally {
  await new Promise((resolve) => server.close(resolve));
}
