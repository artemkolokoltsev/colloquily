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
      let practiceReady = false;
      let practiceSession = {id: 901, subject_id: 1, status: 'created', remaining_seconds: 60, countdown_visible: true, sources: [], current_question: {id: 77, question_text: 'Explain why $E=mc^2$ relates mass and energy.'}};
      let practiceRun = {id: 900, status: 'running', mode: 'random_practice', sessions: [practiceSession]};
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
        if (path === "/preferences") return json({ language });
        if (path === "/models/status")
          return json({
            ollama: "available",
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
        if (path === '/practice') {
          if (request.method() === 'GET') return json([]);
          practiceRun.mode = request.postDataJSON().mode;
          return json(practiceRun);
        }
        if (path === '/sessions/901/begin') { practiceSession.status = 'answering'; return json(practiceSession); }
        if (path === '/sessions/901') return json(practiceSession);
        if (path === '/practice/900') return json(practiceRun);
        if (path === '/practice/900/finish') { practiceSession.status = 'completed'; return json({}); }
        if (path === '/sessions/901/answer') {
          assert.match(request.postDataJSON().answer, /energy/);
          practiceSession.status = 'completed';
          practiceRun.status = 'completed';
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
                    name: "PDF regression",
                    slug: "pdf-regression",
                    exam_duration_minutes: 15,
                  },
                ],
          );
        if (path.endsWith("/models/readiness")) return json({ state: "ready" });
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
          "Exactly three exams with 15 minutes per subject",
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
      await page.getByRole('button', {name:'Start practising', exact:true}).click();
      await page.locator('.session-question .katex').first().waitFor();
      assert.equal(await page.locator('aside').isVisible(), false);
      assert.equal(await page.locator('.window-toolbar').isVisible(), false);
      assert.equal(await page.getByRole('textbox', {name:'Your oral answer'}).count(), 1);
      await page.getByRole('textbox', {name:'Your oral answer'}).fill('Mass is a form of energy.');
      await page.screenshot({path:`output/playwright/practice-ambient-${name}.png`, fullPage:true});
      await page.emulateMedia({colorScheme:'dark'});
      await page.screenshot({path:`output/playwright/practice-ambient-dark-${name}.png`, fullPage:true});
      await page.emulateMedia({colorScheme:'light'});
      await page.getByRole('button', {name:'Submit answer', exact:true}).click();
      await page.getByRole('heading', {name:'A moment to reflect', exact:true}).waitFor();
      assert.equal(await page.locator('.session-question').count(), 0);
      await page.getByRole('button', {name:'Continue', exact:true}).click();
      await page.getByRole('heading', {name:'Session complete', exact:true}).waitFor();
      await page.getByRole('button', {name:'Back to practice modes', exact:true}).click();
      await page.locator('aside').waitFor({state:'visible'});
      assert.equal(await page.locator('aside').isVisible(), true);
      assert.equal(await page.locator('.mode-card').count(), 8);
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
      assert.equal(await page.locator('.app-stamp').innerText(), 'Colloquily v0.1.6');
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
