# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: xv7-browser-smoke.spec.mjs >> XV7 browser smoke >> chat routing keeps advice, preview, and trace UI distinct
- Location: e2e\xv7-browser-smoke.spec.mjs:22:3

# Error details

```
Test timeout of 60000ms exceeded.
```

```
Error: expect(locator).toBeEnabled() failed

Locator:  locator('#promptInput')
Expected: enabled
Received: disabled

Call log:
  - Expect "toBeEnabled" with timeout 60000ms
  - waiting for locator('#promptInput')
    122 × locator resolved to <textarea rows="2" disabled id="promptInput" placeholder="Ask xv7 anything… (Enter to send, Shift+Enter for new line)" class="flex-1 resize-none rounded-xl border border-xv7-line bg-xv7-panelSoft px-3 py-2.5 text-sm text-slate-100 outline-none transition focus:border-xv7-glow"></textarea>
        - unexpected value "disabled"

```

```yaml
- textbox "Ask xv7 anything… (Enter to send, Shift+Enter for new line)" [disabled]
```

# Test source

```ts
  1   | import { expect, test } from "@playwright/test";
  2   | 
  3   | const baseURL = process.env.XV7_BROWSER_BASE_URL || "http://localhost:3000";
  4   | 
  5   | async function sendPromptAndGetAssistantCard(page, prompt) {
  6   |   const assistantCards = page.locator(".chat-card-assistant");
  7   |   const previousCount = await assistantCards.count();
  8   | 
> 9   |   await expect(page.locator("#promptInput")).toBeEnabled({ timeout: 60_000 });
      |                                              ^ Error: expect(locator).toBeEnabled() failed
  10  |   await expect(page.locator("#sendButton")).toBeEnabled({ timeout: 60_000 });
  11  |   await page.locator("#promptInput").fill(prompt);
  12  |   await page.locator("#sendButton").click();
  13  | 
  14  |   await expect(assistantCards).toHaveCount(previousCount + 1);
  15  |   await expect(page.locator("#sendButton")).toBeEnabled({ timeout: 60_000 });
  16  |   const latest = assistantCards.last();
  17  |   await expect(latest).toBeVisible();
  18  |   return latest;
  19  | }
  20  | 
  21  | test.describe("XV7 browser smoke", () => {
  22  |   test("chat routing keeps advice, preview, and trace UI distinct", async ({
  23  |     page,
  24  |   }) => {
  25  |     const consoleErrors = [];
  26  |     page.on("console", (message) => {
  27  |       if (message.type() === "error") {
  28  |         consoleErrors.push(message.text());
  29  |       }
  30  |     });
  31  | 
  32  |     await page.goto(baseURL);
  33  |     await expect(page.locator("#chatTimeline")).toBeVisible();
  34  |     await expect(page.locator("#promptInput")).toBeVisible();
  35  |     await expect(page.locator("#sendButton")).toBeEnabled();
  36  | 
  37  |     const greetingCard = await sendPromptAndGetAssistantCard(page, "hello");
  38  |     await expect(greetingCard).toContainText(/hi|hello|assistant|help/i);
  39  | 
  40  |     const focusCard = await sendPromptAndGetAssistantCard(
  41  |       page,
  42  |       "Change your active focus to browser validation lane.",
  43  |     );
  44  |     await expect(focusCard).toContainText(/active focus/i);
  45  |     await expect(focusCard).toContainText(/updating|your active focus/i);
  46  | 
  47  |     const previewCard = await sendPromptAndGetAssistantCard(
  48  |       page,
  49  |       "generate a preview of a modern one-page website for Harrys Hot Dog Cart"
  50  |     );
  51  |     let previewSourceCard = previewCard;
  52  |     let previewSurface = previewCard.locator(".site-bundle-card, .code-artifact-card").first();
  53  |     if ((await previewCard.locator(".site-bundle-card, .code-artifact-card").count()) === 0) {
  54  |       const fallbackPreviewCard = await sendPromptAndGetAssistantCard(
  55  |         page,
  56  |         "Generate an HTML website preview artifact for Harrys Hot Dog Cart with hero, menu, about, and contact sections."
  57  |       );
  58  |       previewSourceCard = fallbackPreviewCard;
  59  |       previewSurface = fallbackPreviewCard.locator(".code-artifact-card, .site-bundle-card").first();
  60  |     }
  61  |     await expect(previewSurface).toBeVisible();
  62  |     await expect(previewSurface.locator("button")).toContainText([
  63  |       "Code",
  64  |       "Preview",
  65  |     ]);
  66  |     const previewDetails = previewSourceCard.locator("details.response-details").first();
  67  |     if (await previewDetails.count()) {
  68  |       await expect(previewDetails).not.toHaveAttribute("open", "");
  69  |     }
  70  | 
  71  |     const bundleCountBeforeCorrection = await page.locator(".site-bundle-card").count();
  72  |     const correctionCard = await sendPromptAndGetAssistantCard(
  73  |       page,
  74  |       "Going forward, preview first, write files only when I say build or export.",
  75  |     );
  76  |     await expect(correctionCard).not.toContainText(/implementation\/repo mutation task/i);
  77  |     await expect(correctionCard).not.toContainText(/protected location|operator mode for repo writes/i);
  78  |     await expect(page.locator(".site-bundle-card")).toHaveCount(bundleCountBeforeCorrection);
  79  | 
  80  |     const bundleCountBeforeAdvice = await page.locator(".site-bundle-card").count();
  81  |     const codeArtifactCountBeforeAdvice = await page.locator(".code-artifact-card").count();
  82  |     const conceptualCard = await sendPromptAndGetAssistantCard(
  83  |       page,
  84  |       "How should a website preview be evaluated?",
  85  |     );
  86  |     await expect(conceptualCard).toContainText(
  87  |       /preview/i
  88  |     );
  89  |     await expect(page.locator(".site-bundle-card")).toHaveCount(bundleCountBeforeAdvice);
  90  |     await expect(page.locator(".code-artifact-card")).toHaveCount(codeArtifactCountBeforeAdvice);
  91  | 
  92  |     const detailsToggle = conceptualCard.locator("details.response-details summary").first();
  93  |     if (await detailsToggle.count()) {
  94  |       await detailsToggle.click();
  95  |       await detailsToggle.click();
  96  |       await expect(page.locator("#promptInput")).toBeVisible();
  97  |       await expect(page.locator("#sendButton")).toBeEnabled();
  98  |     }
  99  | 
  100 |     await expect
  101 |       .poll(() => consoleErrors.filter((text) => /ReferenceError/.test(text)))
  102 |       .toEqual([]);
  103 |   });
  104 | });
  105 | 
```