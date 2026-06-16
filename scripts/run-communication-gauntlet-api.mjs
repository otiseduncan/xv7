#!/usr/bin/env node
/**
 * XV7 Communication Gauntlet - API lane
 *
 * Sends every prompt to the local XV7 FastAPI backend and writes JSON/Markdown reports.
 *
 * Defaults:
 *   XV7_API_BASE=http://127.0.0.1:8000
 *   XV7_API_KEY=test-secret
 *
 * Run:
 *   node scripts/run-communication-gauntlet-api.mjs
 */
import fs from "node:fs/promises";
import path from "node:path";

const ROOT = process.cwd();
const CASES_PATH = process.env.CASES_PATH || path.join(ROOT, "communication-gauntlet-cases.json");
const API_BASE = (process.env.XV7_API_BASE || "http://127.0.0.1:8000").replace(/\/$/, "");
const API_KEY = process.env.XV7_API_KEY || "test-secret";
const OUT_DIR = process.env.OUT_DIR || path.join(ROOT, "test-results", "communication-gauntlet");
const LIMIT = Number.parseInt(process.env.LIMIT || "0", 10);

function includesAny(text, needles = []) {
  const lower = String(text || "").toLowerCase();
  return needles.some((n) => lower.includes(String(n).toLowerCase()));
}

function includesNone(text, needles = []) {
  const lower = String(text || "").toLowerCase();
  return needles.every((n) => !lower.includes(String(n).toLowerCase()));
}

function extractAssistantText(payload) {
  if (!payload || typeof payload !== "object") return String(payload ?? "");
  const candidates = [
    payload.visible_text,
    payload.response,
    payload.answer,
    payload.content,
    payload.text,
    payload.message?.content,
    payload.assistant_message?.content,
    payload.assistant?.content,
    payload.data?.content,
  ].filter(Boolean);
  if (candidates.length) return String(candidates[0]);

  // Fallback: find likely strings in the payload without dumping huge JSON.
  const serialized = JSON.stringify(payload);
  return serialized.length > 5000 ? serialized.slice(0, 5000) : serialized;
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-XV7-API-Key": API_KEY,
    },
    body: JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = { raw: text };
  }
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}: ${text.slice(0, 800)}`);
  }
  return json;
}

async function createSession() {
  const payload = await postJson(`${API_BASE}/sessions`, { current_persona: "default" });
  return payload.session_id || payload.id || payload.session?.id;
}

function scoreTurn(text, expect = {}) {
  const failures = [];
  if (expect.must_include_any?.length && !includesAny(text, expect.must_include_any)) {
    failures.push(`missing_any: ${expect.must_include_any.join(" | ")}`);
  }
  if (expect.must_not_include_any?.length && !includesNone(text, expect.must_not_include_any)) {
    failures.push(`forbidden_text: ${expect.must_not_include_any.join(" | ")}`);
  }
  if (expect.max_chars && String(text).length > expect.max_chars) {
    failures.push(`too_long: ${String(text).length} > ${expect.max_chars}`);
  }
  return { passed: failures.length === 0, failures };
}

async function main() {
  await fs.mkdir(OUT_DIR, { recursive: true });
  const suite = JSON.parse(await fs.readFile(CASES_PATH, "utf8"));
  const cases = LIMIT > 0 ? suite.cases.slice(0, LIMIT) : suite.cases;
  const results = [];
  let pass = 0, fail = 0, error = 0;

  console.log(`XV7 API gauntlet`);
  console.log(`API: ${API_BASE}`);
  console.log(`Cases: ${cases.length}`);
  console.log(`Output: ${OUT_DIR}`);

  for (const testCase of cases) {
    const result = { id: testCase.id, category: testCase.category, turns: [], passed: true };
    let sessionId;
    try {
      sessionId = await createSession();
      for (const turn of testCase.turns) {
        const payload = await postJson(`${API_BASE}/sessions/${sessionId}/messages`, { raw_text: turn.prompt });
        const text = extractAssistantText(payload);
        const score = scoreTurn(text, turn.expect || {});
        if (!score.passed) result.passed = false;
        result.turns.push({ prompt: turn.prompt, text, score, raw: payload });
      }
      if (result.passed) pass++; else fail++;
      console.log(`${result.passed ? "PASS" : "FAIL"} ${testCase.id} ${testCase.category}`);
    } catch (err) {
      error++;
      result.passed = false;
      result.error = String(err?.stack || err);
      console.log(`ERROR ${testCase.id}: ${err.message || err}`);
    }
    results.push(result);
  }

  const summary = {
    apiBase: API_BASE,
    startedAt: new Date().toISOString(),
    total: results.length,
    pass,
    fail,
    error,
    results,
  };

  await fs.writeFile(path.join(OUT_DIR, "api-results.json"), JSON.stringify(summary, null, 2), "utf8");

  const md = [
    "# XV7 Communication Gauntlet - API Results",
    "",
    `- API: ${API_BASE}`,
    `- Total: ${results.length}`,
    `- Pass: ${pass}`,
    `- Fail: ${fail}`,
    `- Error: ${error}`,
    "",
    "## Failures",
    "",
    ...results.filter(r => !r.passed).map(r => {
      const turnLines = (r.turns || []).map((t, idx) => [
        `### ${r.id} turn ${idx + 1}`,
        `Prompt: ${t.prompt}`,
        `Failures: ${(t.score?.failures || []).join("; ") || r.error || ""}`,
        "",
        "```text",
        String(t.text || "").slice(0, 2000),
        "```",
        "",
      ].join("\n"));
      return [`## ${r.id} (${r.category})`, r.error ? `Error: ${r.error}` : "", ...turnLines].join("\n");
    })
  ].join("\n");
  await fs.writeFile(path.join(OUT_DIR, "api-results.md"), md, "utf8");

  console.log(`Done. Results written to ${OUT_DIR}`);
  if (fail || error) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
