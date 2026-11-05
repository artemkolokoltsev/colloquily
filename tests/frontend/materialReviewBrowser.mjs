import assert from "node:assert/strict";

export const materialText =
  "A graph has vertices and edges.\nEach edge connects a pair of vertices.\nMass and energy satisfy $E=mc^2$.\n\n| Symbol | Meaning |\n| --- | --- |\n| V | Vertices |\n| E | Edges |";
export const contentsText =
  "Contents\n1 Primer on Graphs . . . . . . 3\n1.1 Basic Set Notation . . . . . . 4\n1.2 Graphs and Degrees . . . . . . 5";

export function materialFixture(index) {
  return {
    id: index + 1,
    document_id: 1,
    document_title: "Lecture & Übung",
    relative_path: "Lecture & Übung.pdf",
    source_location: `page ${index ? 1 : 2}`,
    source_start: index ? 1 : 2,
    content: index ? materialText : contentsText,
    review_status: "accepted",
    study_problem: index ? null : "outline_without_explanation",
  };
}

/** A thousand available passages must not mount a thousand Markdown trees/PDFs. */
export async function verifyMaterialReview(page, name, requests) {
  const initialSources = requests.sources();
  const initialLegacy = requests.legacy();
  const card = page.locator(".document-grid > article").first();
  await card.locator(":scope > details > summary").click();
  assert.equal(await page.locator(".evidence-snippet").count(), 0);
  await card
    .getByRole("button", { name: "Review content", exact: true })
    .click();
  const review = card.locator(".material-review");
  await review.getByText("1–10 of 1000 passages", { exact: true }).waitFor();
  assert.equal(await page.locator(".evidence-snippet").count(), 10);
  assert.equal(
    requests.sources(),
    initialSources,
    "opening review must not load original PDFs",
  );
  assert.equal(
    requests.legacy(),
    initialLegacy,
    "review must not request the full evidence collection",
  );
  const first = review.locator(".evidence-snippet").first();
  await first.getByText("Table of contents", { exact: true }).waitFor();
  assert.equal(
    await first
      .locator(".source-text p")
      .evaluate((element) => getComputedStyle(element).whiteSpace),
    "pre-wrap",
  );
  assert.ok(
    (await first.locator(".source-text p").innerText()).includes(
      "\n1.1 Basic Set Notation",
    ),
  );
  assert.ok(
    (await review.locator(".katex").count()) > 0,
    "math stays rendered",
  );
  assert.ok(
    (await review.locator("table").count()) > 0,
    "Markdown tables stay structured",
  );
  const pageRequests = requests.pages();
  await page.evaluate(() => window.scrollTo(0, 900));
  const before = await page.evaluate(() => window.scrollY);
  await page.mouse.wheel(0, 350);
  await page.evaluate(
    () =>
      new Promise((resolve) =>
        requestAnimationFrame(() => requestAnimationFrame(resolve)),
      ),
  );
  assert.ok(
    (await page.evaluate(() => window.scrollY)) >= before,
    "scrolling must not jump backwards",
  );
  assert.equal(
    requests.pages(),
    pageRequests,
    "scrolling must not refetch passages",
  );
  assert.equal(
    requests.sources(),
    initialSources,
    "scrolling must not create PDF requests",
  );
  const second = review.locator(".evidence-snippet").nth(1);
  await second
    .getByRole("button", { name: "Correct extracted text", exact: true })
    .click();
  await second
    .getByRole("textbox")
    .fill(materialText + "\nMy unsaved correction.");
  assert.equal(
    await review
      .getByRole("button", { name: "Next passages", exact: true })
      .isDisabled(),
    true,
    "changing pages must protect an edited draft",
  );
  await second
    .getByRole("button", { name: "Cancel editing", exact: true })
    .click();
  await first.locator(".material-source > summary").click();
  await first.locator("canvas:visible").waitFor();
  assert.equal(
    requests.sources(),
    initialSources + 1,
    "only an explicitly opened original page loads its PDF",
  );
  await first.locator(".material-source > summary").click();
  await first.locator("canvas").waitFor({ state: "detached" });
  await review
    .getByRole("button", { name: "Next passages", exact: true })
    .click();
  await review.getByText("11–20 of 1000 passages", { exact: true }).waitFor();
  assert.equal(await review.locator(".evidence-snippet").count(), 10);
  assert.equal(
    await review
      .locator(".evidence-snippet")
      .first()
      .getAttribute("data-unit-id"),
    "11",
  );
  assert.equal(await page.locator("canvas").count(), 0);
  await review
    .getByRole("button", { name: "Previous passages", exact: true })
    .click();
  await review.getByText("1–10 of 1000 passages", { exact: true }).waitFor();
  await page.screenshot({
    path: `output/playwright/material-review-${name}.png`,
    fullPage: true,
  });
  await card.locator(":scope > details > summary").click();
  await page.locator(".material-review").waitFor({ state: "detached" });
  const tools = page
    .locator("details")
    .filter({
      has: page
        .locator("summary")
        .filter({ hasText: "Advanced tools · processing & source review" }),
    });
  await tools.locator(":scope > summary").click();
  await tools.getByText("1–10 of 1000 passages", { exact: true }).waitFor();
  assert.equal(
    await page.locator(".evidence-snippet").count(),
    10,
    "advanced review is also bounded",
  );
  await tools.locator(":scope > summary").click();
  await page.locator(".material-review").waitFor({ state: "detached" });
  assert.equal(requests.sources(), initialSources + 1);
  assert.equal(requests.legacy(), initialLegacy);
  console.log(
    `${name}: thousand-passage review, preserved lines/math/tables, bounded DOM, stable scroll and on-demand PDF passed`,
  );
}
