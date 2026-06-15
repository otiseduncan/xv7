import { expect, test } from "@playwright/test";

const baseURL = process.env.XV7_BROWSER_BASE_URL || "http://localhost:3000";
const smokeResponseTimeoutMs = 180_000;

async function sendPromptAndGetAssistantCard(page, prompt) {
  const assistantCards = page.locator(".chat-card-assistant");
  const previousCount = await assistantCards.count();

  await expect(page.locator("#promptInput")).toBeEnabled({ timeout: smokeResponseTimeoutMs });
  await expect(page.locator("#sendButton")).toBeEnabled({ timeout: smokeResponseTimeoutMs });
  await page.locator("#promptInput").fill(prompt);
  await page.locator("#sendButton").click();

  await expect(assistantCards).toHaveCount(previousCount + 1);
  const latest = assistantCards.last();
  await expect(latest).toBeVisible();
  await expect(latest).not.toHaveClass(/pending-assistant/, { timeout: smokeResponseTimeoutMs });
  await expect(page.locator("#promptInput")).toBeEnabled({ timeout: smokeResponseTimeoutMs });
  await expect(page.locator("#sendButton")).toHaveText("Send", { timeout: smokeResponseTimeoutMs });
  await expect(page.locator("#sendButton")).toBeEnabled({ timeout: smokeResponseTimeoutMs });
  return latest;
}

test.describe("XV7 browser smoke", () => {
  test("chat routing keeps advice, preview, and trace UI distinct", async ({
    page,
  }) => {
    test.setTimeout(240_000);

    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    await page.goto(baseURL);
    await expect(page.locator("#chatTimeline")).toBeVisible();
    await expect(page.locator("#promptInput")).toBeVisible();
    await expect(page.locator("#sendButton")).toBeEnabled();

    const greetingCard = await sendPromptAndGetAssistantCard(page, "hello");
    await expect(greetingCard).toContainText(/hi|hello|assistant|help/i);

    const focusCard = await sendPromptAndGetAssistantCard(
      page,
      "Change your active focus to browser validation lane.",
    );
    await expect(focusCard).toContainText(/active focus/i);
    await expect(focusCard).toContainText(/updating|your active focus/i);

    const previewCard = await sendPromptAndGetAssistantCard(
      page,
      "generate a preview of a modern one-page website for Harrys Hot Dog Cart"
    );
    let previewSourceCard = previewCard;
    let previewSurface = previewCard.locator(".site-bundle-card, .code-artifact-card").first();
    if ((await previewCard.locator(".site-bundle-card, .code-artifact-card").count()) === 0) {
      const fallbackPreviewCard = await sendPromptAndGetAssistantCard(
        page,
        "Generate an HTML website preview artifact for Harrys Hot Dog Cart with hero, menu, about, and contact sections."
      );
      previewSourceCard = fallbackPreviewCard;
      previewSurface = fallbackPreviewCard.locator(".code-artifact-card, .site-bundle-card").first();
    }
    await expect(previewSurface).toBeVisible();
    await expect(previewSurface.locator("button")).toContainText([
      "Code",
      "Preview",
    ]);
    const previewDetails = previewSourceCard.locator("details.response-details").first();
    if (await previewDetails.count()) {
      await expect(previewDetails).not.toHaveAttribute("open", "");
    }

    const bundleCountBeforeCorrection = await page.locator(".site-bundle-card").count();
    const correctionCard = await sendPromptAndGetAssistantCard(
      page,
      "Going forward, preview first, write files only when I say build or export.",
    );
    await expect(correctionCard).not.toContainText(/implementation\/repo mutation task/i);
    await expect(correctionCard).not.toContainText(/protected location|operator mode for repo writes/i);
    await expect(page.locator(".site-bundle-card")).toHaveCount(bundleCountBeforeCorrection);

    const bundleCountBeforeAdvice = await page.locator(".site-bundle-card").count();
    const codeArtifactCountBeforeAdvice = await page.locator(".code-artifact-card").count();
    const conceptualCard = await sendPromptAndGetAssistantCard(
      page,
      "How should a website preview be evaluated?",
    );
    await expect(conceptualCard).toContainText(
      /preview/i
    );
    await expect(page.locator(".site-bundle-card")).toHaveCount(bundleCountBeforeAdvice);
    await expect(page.locator(".code-artifact-card")).toHaveCount(codeArtifactCountBeforeAdvice);

    const detailsToggle = conceptualCard.locator("details.response-details summary").first();
    if (await detailsToggle.count()) {
      await detailsToggle.click();
      await detailsToggle.click();
      await expect(page.locator("#promptInput")).toBeVisible();
      await expect(page.locator("#sendButton")).toBeEnabled();
    }

    await expect
      .poll(() => consoleErrors.filter((text) => /ReferenceError/.test(text)))
      .toEqual([]);
  });
});
