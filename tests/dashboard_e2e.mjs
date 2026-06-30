import assert from "node:assert/strict";
import { mkdir, mkdtemp, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { spawn } from "node:child_process";
import { chromium } from "playwright-core";

const ROOT = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const REPORTS = path.join(ROOT, "reports");

function attr(label, confidence = "high") {
  return { label, confidence, evidence: [`fixture:${label}`] };
}

function makeReport() {
  const clients = ["Codex Desktop", "Cursor", "Codex CLI", "Pi Coding Agent", "Paperclip: SRE", "Paperclip: CEO", "Paperclip: Reviewer"];
  const projects = ["Paperclip", "PA-Agent", "Dreamwidth", "DY Sphere", "STA", "Dinner with Kids", "Overseer"];
  const staff = ["Alex", "Sam", "Riley", "unknown", "Site Reliability Engineer", "CEO", "Reviewer"];
  const tasks = ["feature-dashboard", "test-loop", "repo-index", "paperclip-review", "local-admin", "retry-failure", "cleanup"];
  const models = ["gpt-5.5", "gpt-5.4-mini", "gpt-5.3-codex-spark"];
  const sessions = [];
  for (let i = 0; i < 96; i += 1) {
    const start = new Date(Date.UTC(2026, 5, 24 + (i % 7), i % 24, (i * 7) % 60, 0));
    const outcome = i % 9 === 0 ? "no-op" : i % 4 === 0 ? "exploratory" : i % 3 === 0 ? "neutral" : "productive";
    const edits = outcome === "productive" ? 1 + (i % 3) : 0;
    const tests = outcome === "productive" && i % 2 === 0 ? 1 : 0;
    const commandLabels = i % 8 === 0 ? ["read", "read", "shell"] : i % 7 === 0 ? ["test", "test", "test"] : ["shell"];
    const client = clients[i % clients.length];
    const project = projects[i % projects.length];
    const staffName = staff[i % staff.length];
    const task = tasks[i % tasks.length];
    const totalTokens = 12000 + i * 2311 + (i % 5) * 50000;
    const cost = Number((totalTokens / 100000 * (0.22 + (i % 4) * 0.08)).toFixed(2));
    sessions.push({
      session_id: `session-${String(i).padStart(3, "0")}`,
      path: `/tmp/session-${i}.jsonl`,
      start_time: start.toISOString(),
      end_time: new Date(start.getTime() + (10 + (i % 20)) * 60000).toISOString(),
      cwd: `/work/${project}`,
      workspace_roots: [],
      model: models[i % models.length],
      source: "fixture",
      originator: client,
      thread_source: "local",
      cli_version: "0.1",
      model_provider: "openai",
      usage: {
        input_tokens: totalTokens,
        cached_input_tokens: 0,
        output_tokens: 0,
        reasoning_output_tokens: 0,
        total_tokens: totalTokens
      },
      usage_known: true,
      event_counts: {},
      tool_counts: {},
      tool_sequence: [],
      command_signatures: commandLabels,
      command_labels: commandLabels,
      first_request_hash: `hash-${i}`,
      first_request_features: {},
      file_edit_markers: edits,
      test_markers: tests,
      error_markers: i % 11 === 0 ? 1 : 0,
      warnings: [],
      client: attr(client),
      project: attr(project, i % 10 === 0 ? "medium" : "high"),
      task: attr(task, "medium"),
      paperclip_company: attr(i % 5 === 0 ? "unknown" : i % 2 === 0 ? "Paperclip" : "DY Sphere"),
      paperclip_project: attr(project),
      paperclip_staff: attr(staffName, staffName === "unknown" ? "low" : "high"),
      paperclip_task: attr(task),
      estimate: { credits: cost, cost_usd: cost, confidence: "rate_card_estimate", evidence: [] },
      outcome: attr(outcome, "medium")
    });
  }
  const retryIds = sessions.filter((_, i) => i % 8 === 0).map((s) => s.session_id);
  const testLoopIds = sessions.filter((_, i) => i % 7 === 0).map((s) => s.session_id);
  return {
    run: { session_count: sessions.length, warning_count: 0, confidence_note: "fixture" },
    telemetry: { available: true, live_usage: { windows: [{ usedPercent: 51 }] }, warnings: [] },
    aggregates: {},
    findings: [
      { kind: "retry_loop", title: "Retry loop", confidence: "high", session_ids: retryIds, total_tokens: 1000000, cost_usd: 30, evidence: ["fixture"] },
      { kind: "test_loop", title: "Repeated test loop", confidence: "medium", session_ids: testLoopIds, total_tokens: 800000, cost_usd: 22, evidence: ["fixture"] }
    ],
    reconciliation: [],
    sessions,
    warnings: []
  };
}

function chromePath() {
  const candidates = [
    process.env.CUP_E2E_CHROME,
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium"
  ].filter(Boolean);
  return candidates[0];
}

async function startServer(reportPath) {
  const env = { ...process.env, PYTHONPATH: path.join(ROOT, "src"), PYTHONUNBUFFERED: "1" };
  const child = spawn("python3", ["-m", "codex_usage_profiler.dashboard", "--report", reportPath, "--host", "127.0.0.1", "--port", "0"], {
    cwd: ROOT,
    env,
    stdio: ["ignore", "pipe", "pipe"]
  });
  let stderr = "";
  child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
  const baseUrl = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`dashboard server did not start\n${stderr}`)), 10000);
    child.stdout.on("data", (chunk) => {
      const text = chunk.toString();
      const match = text.match(/http:\/\/127\.0\.0\.1:(\d+)\//);
      if (match) {
        clearTimeout(timer);
        resolve(`http://127.0.0.1:${match[1]}/`);
      }
    });
    child.on("exit", (code) => {
      clearTimeout(timer);
      reject(new Error(`dashboard server exited ${code}\n${stderr}`));
    });
  });
  return { child, baseUrl };
}

async function assertFlowGeometry(page, label) {
  const result = await page.evaluate(() => {
    const flow = document.querySelector("#spend-flow");
    function numbers(d) {
      return d.match(/-?\d+(?:\.\d+)?/g).map(Number);
    }
    function box(id) {
      const node = document.querySelector(`.flow-node[data-node-id="${CSS.escape(id)}"]`);
      return {
        x: parseFloat(node.style.left),
        y: parseFloat(node.style.top),
        width: parseFloat(node.style.width),
        height: parseFloat(node.style.height)
      };
    }
    const nodes = Array.from(document.querySelectorAll(".flow-node")).map((node) => ({
      id: node.dataset.nodeId,
      stage: node.dataset.stage,
      x: parseFloat(node.style.left),
      y: parseFloat(node.style.top),
      width: parseFloat(node.style.width),
      height: parseFloat(node.style.height)
    }));
    const byStage = Object.groupBy ? Object.groupBy(nodes, (node) => node.stage) : nodes.reduce((acc, node) => {
      (acc[node.stage] ||= []).push(node);
      return acc;
    }, {});
    const stages = ["client", "project", "staff", "outcome"];
    const stageGaps = stages.slice(0, -1).map((stage, idx) => byStage[stages[idx + 1]][0].x - (byStage[stage][0].x + byStage[stage][0].width));
    const badLinks = Array.from(document.querySelectorAll(".flow-link")).map((link) => {
      const values = numbers(link.getAttribute("d"));
      const source = box(link.dataset.source);
      const target = box(link.dataset.target);
      return {
        source: link.dataset.source,
        target: link.dataset.target,
        sxDelta: Math.abs(values[0] - (source.x + source.width)),
        txDelta: Math.abs(values[6] - target.x),
        syInside: values[1] >= source.y && values[1] <= source.y + source.height,
        tyInside: values[7] >= target.y && values[7] <= target.y + target.height
      };
    }).filter((link) => link.sxDelta > 2 || link.txDelta > 2 || !link.syInside || !link.tyInside);
    const clippedNodes = nodes.filter((node) => node.y < 0 || node.y + node.height > flow.clientHeight + 1);
    return { nodeCount: nodes.length, linkCount: document.querySelectorAll(".flow-link").length, stageGaps, badLinks, clippedNodes, flowHeight: flow.clientHeight };
  });
  assert.equal(result.badLinks.length, 0, `${label}: bad Sankey link endpoints ${JSON.stringify(result.badLinks.slice(0, 3))}`);
  assert.equal(result.clippedNodes.length, 0, `${label}: clipped Sankey nodes ${JSON.stringify(result.clippedNodes)}`);
  assert(result.stageGaps.every((gap) => gap >= 20), `${label}: stage gaps too small ${JSON.stringify(result.stageGaps)}`);
  assert(result.nodeCount > 10, `${label}: expected many flow nodes`);
  assert(result.linkCount > 10, `${label}: expected many flow links`);
}

async function clickAndExpectFilter(page, selector, expectedQueryKey) {
  await page.locator(selector).click();
  await page.waitForTimeout(100);
  const params = new URL(page.url()).searchParams;
  assert(params.has(expectedQueryKey), `${selector} did not set ${expectedQueryKey}`);
}

async function expectNoFilter(page, queryKey, label) {
  await page.waitForTimeout(100);
  const params = new URL(page.url()).searchParams;
  assert(!params.has(queryKey), `${label} did not clear ${queryKey}`);
}

async function run() {
  await mkdir(REPORTS, { recursive: true });
  const work = await mkdtemp(path.join(tmpdir(), "cup-e2e-"));
  const reportPath = path.join(work, "report.json");
  await writeFile(reportPath, JSON.stringify(makeReport()), "utf8");
  const { child, baseUrl } = await startServer(reportPath);
  const errors = [];
  let browser;
  try {
    browser = await chromium.launch({ executablePath: chromePath(), headless: true });
    const context = await browser.newContext({ acceptDownloads: true, viewport: { width: 1440, height: 1000 } });
    const page = await context.newPage();
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("pageerror", (err) => errors.push(err.message));
    await page.goto(baseUrl);
    await page.waitForSelector(".flow-node");
    await assertFlowGeometry(page, "initial");

    for (const size of [{ width: 1120, height: 900 }, { width: 1728, height: 1117 }, { width: 1280, height: 900 }]) {
      await page.setViewportSize(size);
      await page.waitForTimeout(100);
      await assertFlowGeometry(page, `viewport ${size.width}`);
    }
    await page.locator("#hide-filters").click();
    await page.locator("#close-drawer").click();
    await page.waitForTimeout(100);
    await assertFlowGeometry(page, "filters and drawer hidden");
    const widenedFlow = await page.locator("#spend-flow").evaluate((node) => node.clientWidth);
    assert(widenedFlow > 500, `combined hidden layout collapsed flow to ${widenedFlow}px`);
    await page.goto(baseUrl);
    await page.waitForSelector(".flow-node");

    const nodeCount = await page.locator(".flow-node").count();
    for (let i = 0; i < nodeCount; i += 1) {
      await page.locator(".flow-node").nth(i).hover();
      const highlight = await page.evaluate(() => ({
        links: document.querySelectorAll(".flow-link.flow-highlight").length,
        nodes: document.querySelectorAll(".flow-node.flow-highlight").length,
        active: document.querySelector("#spend-flow").classList.contains("flow-has-highlight")
      }));
      assert(highlight.active && highlight.nodes >= 1 && highlight.links >= 1, `node hover ${i} failed`);
    }
    const linkCount = await page.locator(".flow-link").count();
    for (let i = 0; i < linkCount; i += 1) {
      await page.locator(".flow-link").nth(i).hover({ force: true });
      const highlight = await page.evaluate(() => ({
        links: document.querySelectorAll(".flow-link.flow-highlight").length,
        nodes: document.querySelectorAll(".flow-node.flow-highlight").length,
        active: document.querySelector("#spend-flow").classList.contains("flow-has-highlight")
      }));
      assert(highlight.active && highlight.nodes >= 2 && highlight.links >= 1, `link hover ${i} failed`);
    }

    const infoCount = await page.locator(".info-button, .source-button").count();
    for (let i = 0; i < infoCount; i += 1) {
      await page.locator(".info-button, .source-button").nth(i).click();
      await page.waitForSelector("#info-popover:not([hidden])");
      await page.keyboard.press("Escape");
    }

    await page.locator("#client-filter").selectOption("Codex Desktop");
    await page.locator("#project-filter").selectOption("PA-Agent");
    await page.locator("#staff-filter").selectOption("Alex");
    await page.locator("#search-input").fill("feature");
    await page.locator("#date-preset").selectOption("last7");
    await page.locator("#waste-filter").selectOption("any");
    await page.evaluate(() => {
      const input = document.querySelector("#confidence-filter");
      input.value = "50";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    });
    assert((await page.locator("#active-chips .chip").count()) >= 5, "filters did not create chips");
    await page.locator("#reset-filters").click();
    await page.waitForTimeout(100);

    await page.locator(".kpi.useful").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "useful-only", "useful KPI did not filter");
    assert.equal(await page.locator(".kpi.useful").getAttribute("aria-pressed"), "true", "useful KPI was not marked active");
    await page.locator(".kpi.useful").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "all", "second useful KPI click did not clear");
    await page.locator(".kpi.waste").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "any", "waste KPI did not filter");
    await page.locator(".kpi.waste").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "all", "second waste KPI click did not clear");

    const clientNode = '.flow-node[data-node-id="client|Codex Desktop"]';
    await clickAndExpectFilter(page, clientNode, "clients");
    assert.equal(await page.locator(clientNode).getAttribute("aria-pressed"), "true", "active flow node was not marked pressed");
    await page.locator(clientNode).click();
    await expectNoFilter(page, "clients", "second flow node click");
    await page.locator("#reset-filters").click();
    await page.waitForTimeout(100);
    await page.locator(".flow-link").first().click({ force: true });
    assert(new URL(page.url()).searchParams.has("sessionIds"), "flow link did not filter");
    assert(await page.locator(".flow-link.active").count(), "active flow link was not marked");
    await page.locator(".flow-link.active").first().click({ force: true });
    await expectNoFilter(page, "sessionIds", "second flow link click");
    await page.locator("#reset-filters").click();
    await page.waitForTimeout(100);
    const otherNode = page.locator('.flow-node[data-node-id="client|Other / Unknown"]');
    if (await otherNode.count()) {
      await otherNode.click();
      assert(new URL(page.url()).searchParams.has("sessionIds"), "grouped flow node did not use exact session ids");
      assert(await page.locator('.flow-node.active[data-node-id="client|Other / Unknown"]').count(), "grouped flow node did not stay available as active");
      await page.locator('.flow-node.active[data-node-id="client|Other / Unknown"]').click();
      await expectNoFilter(page, "sessionIds", "second grouped flow node click");
    }
    await page.locator("#reset-filters").click();

    const brush = await page.locator(".brush-wrap").boundingBox();
    assert(brush, "brush missing");
    await page.evaluate(({ startX, endX, y }) => {
      const target = document.querySelector("#mini-brush");
      target.dispatchEvent(new PointerEvent("pointerdown", { bubbles: true, clientX: startX, clientY: y, pointerId: 1, pointerType: "mouse" }));
      target.dispatchEvent(new PointerEvent("pointermove", { bubbles: true, clientX: endX, clientY: y, pointerId: 1, pointerType: "mouse" }));
      target.dispatchEvent(new PointerEvent("pointerup", { bubbles: true, clientX: endX, clientY: y, pointerId: 1, pointerType: "mouse" }));
    }, { startX: brush.x + brush.width * 0.2, endX: brush.x + brush.width * 0.65, y: brush.y + brush.height / 2 });
    assert(new URL(page.url()).searchParams.has("brushStartTime"), "brush drag did not set range");
    await page.locator("#reset-filters").click();

    await page.locator(".legend-useful").click();
    assert(await page.locator(".legend-useful.inactive").count(), "legend did not toggle");
    await page.locator(".legend-useful").click();
    await page.locator(".hour-bar").first().click();
    assert(new URL(page.url()).searchParams.has("brushStartTime"), "timeline hour did not filter");
    assert(await page.locator(".hour-bar.active").count(), "active timeline hour was not marked");
    await page.locator(".hour-bar.active").first().click();
    await expectNoFilter(page, "brushStartTime", "second timeline hour click");
    await page.locator(".heat-cell").nth(20).click();
    assert(new URL(page.url()).searchParams.has("weekdays"), "heatmap cell did not filter");
    assert(await page.locator(".heat-cell.active").count(), "active heatmap cell was not marked");
    await page.locator(".heat-cell.active").click();
    await expectNoFilter(page, "weekdays", "second heatmap cell click");
    await page.locator("#reset-filters").click();
    await page.locator(".driver-row").first().click();
    assert(new URL(page.url()).searchParams.has("wasteKind"), "waste row did not filter");
    assert(await page.locator(".driver-row.active").count(), "active waste row was not marked");
    await page.locator(".driver-row.active").click();
    await expectNoFilter(page, "wasteKind", "second waste row click");
    await page.locator("#reset-filters").click();
    await page.locator(".coverage-list button").last().click();
    assert(new URL(page.url()).searchParams.has("attributionCoverage"), "coverage row did not filter");
    assert(await page.locator(".coverage-list button.active").count(), "active coverage row was not marked");
    await page.locator(".coverage-list button.active").click();
    await expectNoFilter(page, "attributionCoverage", "second coverage row click");
    await page.locator("#reset-filters").click();
    await page.locator("#reduction-select").selectOption("75");
    await page.locator(".projection-action").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "any");
    assert(await page.locator(".projection-action.active").count(), "projection action was not marked active");
    await page.locator(".projection-action.active").click();
    assert.equal(await page.locator("#waste-filter").inputValue(), "all");
    await page.locator("#reset-filters").click();

    await page.locator("#hide-filters").click();
    assert(await page.locator("#show-filters").isVisible(), "show filters was not visible after hide");
    await page.locator("#show-filters").click();
    await page.locator("#compare-mode").check();
    assert(await page.evaluate(() => document.body.classList.contains("compare-mode")), "compare mode class missing");
    await page.locator("#more-menu").click();
    assert(await page.locator("#more-popover:not([hidden])").count(), "more menu did not open");
    await page.keyboard.press("Escape");
    await page.locator("#timeline-menu").click();
    assert(await page.locator("#more-popover:not([hidden])").count(), "timeline menu did not open");
    await page.keyboard.press("Escape");

    await page.locator("#session-table thead button", { hasText: "Tokens" }).click();
    await page.locator("#next-page").click();
    assert((await page.locator("#page-range").textContent()).includes("51-"), "next page did not advance");
    await page.locator("#prev-page").click();
    await page.locator("#column-chooser").click();
    await page.locator("#col-model").uncheck();
    assert(!(await page.locator("#session-table thead").textContent()).includes("Model"), "column chooser did not hide model");
    await page.locator("#density-select").selectOption("comfortable");
    assert(await page.evaluate(() => document.body.classList.contains("comfortable")), "comfortable density missing");
    await page.locator("#session-table tbody tr").first().click();
    await page.locator(".drawer-tabs button", { hasText: "Commands" }).click();
    assert((await page.locator("#drawer-content").textContent()).includes("Commands"), "drawer commands tab did not render");
    await page.locator(".drawer-tabs button", { hasText: "Linked" }).click();
    assert((await page.locator("#drawer-content").textContent()).includes("Linked Sessions"), "drawer linked tab did not render");
    await page.locator("#close-drawer").click();
    assert(await page.evaluate(() => document.querySelector("#evidence-drawer").classList.contains("drawer-closed")), "drawer did not close");

    const downloadPromise = page.waitForEvent("download");
    await page.locator("#export-csv").click();
    await downloadPromise;
    await page.locator("#copy-link").click();

    await page.screenshot({ path: path.join(REPORTS, "dashboard-e2e.png"), fullPage: true });
    await assertFlowGeometry(page, "final");
    assert.equal(errors.length, 0, `browser console errors: ${errors.join("\n")}`);
    console.log(JSON.stringify({ ok: true, baseUrl, nodeCount, linkCount, infoCount, screenshot: path.join(REPORTS, "dashboard-e2e.png") }, null, 2));
  } finally {
    if (browser) await browser.close();
    child.kill();
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
