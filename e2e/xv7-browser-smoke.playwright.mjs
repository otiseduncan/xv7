import { expect, test } from "@playwright/test";

const baseURL = process.env.XV7_BROWSER_BASE_URL || "http://localhost:3000";

async function sendPrompt(page, prompt) {
  await page.locator("#promptInput").fill(prompt);
  await page.locator("#sendButton").click();
}

test.describe("XV7 browser smoke", () => {
  test("chat routing keeps advice, preview, and trace UI distinct", async ({
    page,
  }) => {
    const consoleErrors = [];
    page.on("console", (message) => {
      if (message.type() === "error") {
        consoleErrors.push(message.text());
      }
    });

    await page.goto(baseURL);
    await expect(page.locator("#chatTimeline")).toBeVisible();

    await sendPrompt(page, "What makes a good website preview?");
    await expect(page.locator(".chat-card-assistant").last()).toContainText(
      /preview/i
    );
    await expect(page.locator(".site-bundle-card")).toHaveCount(0);

    await sendPrompt(
      page,
      "generate a preview of a modern one-page website for Harrys Hot Dog Cart"
    );
    await expect(page.locator(".site-bundle-card").last()).toBeVisible();
    await expect(
      page.locator("details.response-details").last()
    ).not.toHaveAttribute("open", "");

    await expect
      .poll(() => consoleErrors.filter((text) => /ReferenceError/.test(text)))
      .toEqual([]);
  });
});
