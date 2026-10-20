/** Exercise the built reader under the exact desktop CSP, never a dev server. */
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { readFile } from "node:fs/promises";
import { resolve, extname, sep } from "node:path";
import { chromium, webkit } from "playwright";

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
          window.__TAURI_INTERNALS__ = {
            invoke: async (command) =>
              command === "backend_connection" ? { url: origin, token } : null,
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
        if (path === "/preferences") return json({ language: "en" });
        if (path === "/exams")
          return json([
            {
              id: 1,
              name: "PDF regression",
              slug: "pdf-regression",
              exam_duration_minutes: 15,
            },
          ]);
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
          return json({ job: null, questions: 0 });
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
