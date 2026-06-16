#!/usr/bin/env node
/**
 * XV7 Communication Gauntlet - Browser typing lane
 *
 * Opens the real browser UI and types every prompt like a user.
 *
 * Defaults:
 *   XV7_WEB_URL=http://127.0.0.1:5173
 *   HEADLESS=0
 *   SLOWMO_MS=60
 *   TYPE_DELAY_MS=8
 *   KEEP_OPEN=1
 *
 * Run:
 *   node scripts/run-communication-gauntlet-browser.mjs
 */
import fs from "node:fs/promises";
import path from "node:path";
import { chromium } from "@playwright/test";

const ROOT = process.cwd();
const CASES_PATH = process.env.CASES_PATH || path.join(ROOT, "communication-gauntlet-cases.json");
const WEB_URL = process.env.XV7_WEB_URL || "http://127.0.0.1:5173";
const OUT_DIR = process.env.OUT_DIR || path.join(ROOT, "test-results", "communication-gauntlet");
const HEADLESS = String(process.env.HEADLESS || "0") === "1";
const SLOWMO_MS = Number.parseInt(process.env.SLOWMO_MS || "60", 10);
const TYPE_DELAY_MS = Number.parseInt(process.env.TYPE_DELAY_MS || "8", 10);
const KEEP_OPEN = String(process.env.KEEP_OPEN || "1") !== "0";
const LIMIT = Number.parseInt(process.env.LIMIT || "0", 10);

async function firstVisible(page, selectors) {
  for (const selector of selectors) {
    const loc = page.locator(selector).first();
    try {
      if (await loc.count()) {
        await loc.waitFor({ state: "visible", timeout: 1200 });
        return loc;
      }
    } catch {}
  }
  return null;
}

async function findComposer(page) {
  return await firstVisible(page, [
    "textarea",
    "[contenteditable='true']",
    "[role='textbox']",
    "input[type='text']",
    "[aria-label*='message' i]",
    "[aria-label*='chat' i]",
    "[placeholder*='message' i]",
    "[placeholder*='ask' i]",
    "[placeholder*='type' i]",
  ]);
}

async function clickSendOrPressEnter(page, composer) {
  const send = await firstVisible(page, [
    "button:has-text('Send')",
    "button:has-text('Ask')",
    "button[aria-label*='send' i]",
    "button[type='submit']",
    "[role='button']:has-text('Send')",
  ]);
  if (send) {
    await send.click();
    return "button";
  }
  await composer.press(process.env.SEND_KEY || "Enter");
  return "enter";
}

async function typePrompt(page, prompt) {
  const composer = await findComposer(page);
  if (!composer) {
    throw new Error("Could not find chat composer. Add a stable textarea/contenteditable selector or set the app URL.");
  }
  await composer.click();
  const tagName = await composer.evaluate((el) => el.tagName.toLowerCase()).catch(() => "");
  if (tagName === "textarea" || tagName === "input") {
    await composer.fill("");
  } else {
    await page.keyboard.press(process.platform === "darwin" ? "Meta+A" : "Control+A");
    await page.keyboard.press("Backspace");
  }
  await page.keyboard.type(prompt, { delay: TYPE_DELAY_MS });
  return await clickSendOrPressEnter(page, composer);
}

function scoreBody(bodyText, beforeText, expect = {}) {
  const afterDelta = bodyText.slice(Math.min(beforeText.length, bodyText.length));
  const candidate = afterDelta || bodyText;
  const lower = candidate.toLowerCase();
  const failures = [];
  if (expect.must_include_any?.length && !expect.must_include_any.some(n => lower.includes(String(n).toLowerCase()))) {
    failures.push(`missing_any: ${expect.must_include_any.join(" | ")}`);
  }
  if (expect.must_not_include_any?.length && !expect.must_not_include_any.every(n => !lower.includes(String(n).toLowerCase()))) {
    failures.push(`forbidden_text: ${expect.must_not_include_any.join(" | ")}`);
  }
  if (expect.max_chars && candidate.length > expect.max_chars * 4) {
    failures.push(`possibly_too_long_browser_delta: ${candidate.length}`);
  }
  return { passed: failures.length === 0, failures, candidate: candidate.slice(0, 2500) };
}

async function waitForResponse(page, beforeText) {
  const start = Date.now();
  const timeoutMs = Number.parseInt(process.env.RESPONSE_TIMEOUT_MS || "45000", 10);
  let latest = beforeText;
  while (Date.now() - start < timeoutMs) {
    await page.waitForTimeout(750);
    const bodyText = await page.locator("body").innerText({ timeout: 3000 }).catch(() => "");
    if (bodyText.length > beforeText.length + 20 && bodyText !== latest) {
      latest = bodyText;
      // Give streaming responses a moment to settle.
      await page.waitForTimeout(1500);
      return await page.locator("body").innerText({ timeout: 3000 }).catch(() => latest);
    }
  }
  return latest;
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const suite = JSON.parse(await fs.readFile(CASES_PATH, "utf8"));
  const cases = LIMIT > 0 ? suite.cases.slice(0, LIMIT) : suite.cases;

  console.log("XV7 browser typing gauntlet");
  console.log(`URL: ${WEB_URL}`);
  console.log(`Cases: ${cases.length}`);
  console.log(`Headless: ${HEADLESS}`);
  console.log(`SlowMo: ${SLOWMO_MS}`);
  console.log(`Keep open: ${KEEP_OPEN}`);

  const browser = await chromium.launch({ headless: HEADLESS, slowMo: SLOWMO_MS });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
  const page = await context.newPage();
  page.setDefaultTimeout(10000);
  await page.goto(WEB_URL, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  const results = [];
  let pass = 0, fail = 0, error = 0;

  for (const testCase of cases) {
    const result = { id: testCase.id, category: testCase.category, turns: [], passed: true };
    try {
      for (const turn of testCase.turns) {
        console.log(`TYPE ${testCase.id}: ${turn.prompt}`);
        const before = await page.locator("body").innerText().catch(() => "");
        const sendMethod = await typePrompt(page, turn.prompt);
        const after = await waitForResponse(page, before);
        const score = scoreBody(after, before, turn.expect || {});
        if (!score.passed) result.passed = false;
        result.turns.push({
          prompt: turn.prompt,
          sendMethod,
          score,
          bodyDeltaSample: score.candidate,
        });
        await page.screenshot({ path: path.join(OUT_DIR, `${testCase.id}-${result.turns.length}.png`), fullPage: true }).catch(() => {});
      }
      if (result.passed) pass++; else fail++;
      console.log(`${result.passed ? "PASS" : "REVIEW"} ${testCase.id}`);
    } catch (err) {
      error++;
      result.passed = false;
      result.error = String(err?.stack || err);
      console.log(`ERROR ${testCase.id}: ${err.message || err}`);
    }
    results.push(result);
  }

  const summary = {
    webUrl: WEB_URL,
    startedAt: new Date().toISOString(),
    total: results.length,
    pass,
    fail,
    error,
    results,
  };
  await fs.writeFile(path.join(OUT_DIR, "browser-results.json"), JSON.stringify(summary, null, 2), "utf8");

  const md = [
    "# XV7 Communication Gauntlet - Browser Typing Results",
    "",
    `- URL: ${WEB_URL}`,
    `- Total: ${results.length}`,
    `- Pass: ${pass}`,
    `- Review/Fail: ${fail}`,
    `- Error: ${error}`,
    "",
    "Browser scoring is intentionally conservative because UI layouts vary. Use failures as review targets.",
    "",
    "## Review Items",
    "",
    ...results.filter(r => !r.passed).map(r => {
      const turns = (r.turns || []).map((t, idx) => [
        `### Turn ${idx + 1}`,
        `Prompt: ${t.prompt}`,
        `Failures: ${(t.score?.failures || []).join("; ") || r.error || ""}`,
        "",
        "```text",
        String(t.bodyDeltaSample || "").slice(0, 2000),
        "```",
      ].join("\n"));
      return [`## ${r.id} (${r.category})`, r.error ? `Error: ${r.error}` : "", ...turns].join("\n");
    })
  ].join("\n");
  await fs.writeFile(path.join(OUT_DIR, "browser-results.md"), md, "utf8");

  console.log(`Done. Results written to ${OUT_DIR}`);
  if (KEEP_OPEN) {
    console.log("KEEP_OPEN=1: browser will stay open. Close it manually when done.");
    await new Promise(() => {});
  } else {
    await browser.close();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
