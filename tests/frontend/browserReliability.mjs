import assert from "node:assert/strict";

/** Hold an old exam response until the replacement exam is fully selected. */
export async function verifyExamSwitch(page, origin) {
  const readiness = "**/api/exams/1/models/readiness";
  let pending;
  const requested = new Promise((resolve) => {
    pending = resolve;
  });
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  let settled;
  const delivered = new Promise((resolve) => {
    settled = resolve;
  });
  const handler = async (route) => {
    pending();
    await gate;
    await route.fulfill({ json: { state: "insufficient_storage" } });
    settled();
  };
  const summary = (route) =>
    route.fulfill({ json: { date: null, questions: 3, practised: 0 } });
  const documents = (route) =>
    route.fulfill({ json: { raw: [], documents: [] } });
  await page.route(readiness, handler);
  await page.route("**/api/exams/*/summary", summary);
  await page.route("**/api/exams/2/documents", documents);
  try {
    await page.goto(origin);
    await requested;
    const picker = page.locator(".exam-trigger");
    await picker.click();
    const currentReady = page.waitForResponse((response) =>
      response.url().endsWith("/api/exams/2/models/readiness"),
    );
    await page
      .locator(".exam-options button")
      .filter({ hasText: "Second exam" })
      .click();
    await page.waitForFunction(
      () =>
        document.querySelector(".exam-trigger strong")?.textContent ===
        "Second exam",
    );
    await page.locator(".dashboard .loading").waitFor({ state: "hidden" });
    await currentReady;
    release();
    await delivered;
    await page.unroute(readiness, handler);
    // Flush the response handlers and React's render without an arbitrary sleep.
    await page.evaluate(
      () =>
        new Promise((resolve) =>
          requestAnimationFrame(() => requestAnimationFrame(resolve)),
        ),
    );
    assert.equal(
      await page.getByRole("alert").count(),
      0,
      "an old exam must not surface a storage error in the new exam",
    );
    assert.equal(
      await page.locator(".setup-inline").count(),
      0,
      "stale readiness must not request setup for a ready exam",
    );
    await picker.click();
    await page.keyboard.press("Escape");
    assert.equal(
      await picker.evaluate((element) => element === document.activeElement),
      true,
      "Escape restores picker focus",
    );
    await picker.click();
    await page
      .locator(".exam-options button")
      .filter({ hasText: "Quantum physics" })
      .click();
    assert.equal(
      await picker.evaluate((element) => element === document.activeElement),
      true,
      "selection restores picker focus",
    );
  } finally {
    release();
    await page.unroute(readiness, handler);
    await page.unroute("**/api/exams/*/summary", summary);
    await page.unroute("**/api/exams/2/documents", documents);
  }
}

export async function verifySingleSubmission(page) {
  const url = "**/api/sessions/901/answer";
  let requests = 0;
  let pending;
  const requested = new Promise((resolve) => {
    pending = resolve;
  });
  let release;
  const gate = new Promise((resolve) => {
    release = resolve;
  });
  const handler = async (route) => {
    requests++;
    pending();
    await gate;
    await route.fallback();
  };
  await page.route(url, handler);
  try {
    const submit = page.getByRole("button", {
      name: "Submit answer",
      exact: true,
    });
    await submit.click();
    await requested;
    assert.equal(
      await submit.isDisabled(),
      true,
      "a pending answer disables submission",
    );
    await submit.evaluate((button) => button.click());
    release();
    await page
      .getByRole("heading", { name: "A moment to reflect", exact: true })
      .waitFor();
    assert.equal(requests, 1, "repeated input creates only one answer request");
  } finally {
    release();
    await page.unroute(url, handler);
  }
}

export async function verifyModeKeyboard(page) {
  const trigger = page.locator(".mode-card").first();
  await trigger.focus();
  await page.keyboard.press("Enter");
  const dialog = page.locator("dialog[open]");
  await dialog.waitFor();
  for (const key of ["Tab", "Shift+Tab"]) {
    await page.keyboard.press(key);
    assert.equal(
      await dialog.evaluate((element) =>
        element.contains(document.activeElement),
      ),
      true,
      "modal retains keyboard focus",
    );
  }
  await page.keyboard.press("Escape");
  await dialog.waitFor({ state: "hidden" });
  assert.equal(
    await trigger.evaluate((element) => element === document.activeElement),
    true,
    "Escape restores mode-card focus",
  );
}
