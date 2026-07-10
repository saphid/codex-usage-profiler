(function (root) {
  "use strict";

  var CONFIDENCE = { unknown: 0, low: 25, medium: 60, high: 90, exact_current: 100, rate_card_estimate: 70 };
  var FIELD_IDS = {
    clients: "client-filter",
    projects: "project-filter",
    companies: "company-filter",
    staff: "staff-filter",
    tasks: "task-filter",
    models: "model-filter",
    outcomes: "outcome-filter"
  };
  var TABLE_COLUMNS = [
    ["start_time", "Start Time"],
    ["session_id", "Session ID"],
    ["client", "Client / Tool"],
    ["project", "Project"],
    ["staff", "Staff"],
    ["task", "Task"],
    ["model", "Model"],
    ["tokens", "Tokens"],
    ["cost", "Rate-card Cost"],
    ["outcome", "Outcome"],
    ["waste", "Review Pattern"],
    ["confidence", "Confidence"]
  ];
  var DEFAULT_COLUMNS = TABLE_COLUMNS.map(function (column) { return column[0]; });
  var DIMENSION_FILTERS = {
    client: "clients",
    project: "projects",
    staff: "staff",
    outcome: "outcomes"
  };
  var INFO_CONTENT = {
    source: "Shows whether this dashboard is reading a local report, CodexBar telemetry, and live quota data. Live quota is current-window telemetry, not historical allocation.",
    sessions: "Sessions are Codex log sessions included by the active filters. Selecting a row updates the Session Details drawer.",
    tokens: "Tokens include reported input, cached input, output, and reasoning output where the local log provides them.",
    cost: "Rate-card cost is a directional replacement-cost estimate from known model rates and CodexBar pricing caches. It is not billing-grade spend.",
    quota: "Live quota now is the current CodexBar window when available. It is not apportioned across historical filters.",
    useful: "Durable-output spend is usage with observable work signals such as edits, tests, commits, PRs, or productive outcome classification. It does not prove user value.",
    waste: "Review candidates are sessions flagged by repeated commands, no durable output, retry-like patterns, or waste outcome classification. They may overlap with durable-output sessions.",
    "spend-flow": "This is a Sankey/alluvial flow. Link width represents spend or tokens moving from client to project to staff to outcome. Click a node or band to filter.",
    timeline: "Hourly stacked usage chart. Drag the mini brush window or handles to select an absolute time range; click a bar to select that hour.",
    heatmap: "Day/hour heatmap. Brighter cells indicate higher usage for that weekday and hour.",
    "waste-drivers": "Ranked recurring review candidates. Click a row to filter the session table to that pattern. Candidate rows can overlap.",
    coverage: "Attribution coverage shows how much filtered usage can be tied to client, project, staff, and task. Click unknown buckets to investigate gaps.",
    confidence: "Confidence is the weakest key attribution signal across client, project, staff, and task. Lower confidence means the profiler needs better attribution evidence.",
    "company-spend": "Paperclip company spend groups filtered sessions by Paperclip company and day. Projected cost uses the filtered observed span, so treat it as directional plan-selection evidence.",
    projection: "Cleanup projection estimates directional savings from de-duplicated sessions in the top review-candidate drivers.",
    notifications: "Notification hooks are not enabled in this local-only dashboard yet.",
    settings: "Settings will hold report paths, privacy defaults, and quota assumptions in a later version."
  };

  function createState() {
    return {
      filters: {
        preset: "all",
        search: "",
        clients: [],
        projects: [],
        companies: [],
        staff: [],
        tasks: [],
        models: [],
        outcomes: [],
        outcomeBucket: "",
        attributionCoverage: "",
        sessionIds: [],
        waste: "all",
        wasteKind: "",
        weekdays: [],
        minConfidence: 0,
        hourStart: "",
        hourEnd: "",
        brushStartTime: "",
        brushEndTime: ""
      },
      sort: { key: "tokens", dir: "desc" },
      metric: "cost",
      density: "compact",
      compareMode: false,
      drawerOpen: true,
      selectedSessionId: null,
      selectedSessionIds: [],
      page: 1,
      pageSize: 50,
      visibleColumns: DEFAULT_COLUMNS.slice(),
      drawerTab: "evidence",
      hiddenOutcomes: []
    };
  }

  function attrLabel(value) {
    if (!value) return "unknown";
    if (typeof value === "string") return value || "unknown";
    return value.label || "unknown";
  }

  function attrConfidence(value) {
    if (!value) return "unknown";
    if (typeof value === "string") return "unknown";
    return value.confidence || "unknown";
  }

  function confidenceScore(value) {
    var label = typeof value === "string" ? value : attrConfidence(value);
    return CONFIDENCE[label] == null ? 0 : CONFIDENCE[label];
  }

  function sessionConfidence(session) {
    var scores = [
      confidenceScore(session.client),
      confidenceScore(session.project),
      confidenceScore(session.paperclip_staff),
      confidenceScore(session.paperclip_task && attrLabel(session.paperclip_task) !== "unknown" ? session.paperclip_task : session.task)
    ];
    return Math.min.apply(Math, scores);
  }

  function tokens(session) {
    return Number((session.usage && session.usage.total_tokens) || 0);
  }

  function cost(session) {
    return Number((session.estimate && session.estimate.cost_usd) || 0);
  }

  function credits(session) {
    return Number((session.estimate && session.estimate.credits) || cost(session) || 0);
  }

  function startDate(session) {
    if (!session || !session.start_time) return null;
    var date = new Date(session.start_time);
    return isNaN(date.getTime()) ? null : date;
  }

  function shortId(value) {
    if (!value) return "unknown";
    return String(value).length > 15 ? String(value).slice(0, 8) + "..." + String(value).slice(-4) : String(value);
  }

  function formatNumber(value) {
    return new Intl.NumberFormat("en-US").format(Math.round(Number(value) || 0));
  }

  function formatTokens(value) {
    value = Number(value) || 0;
    if (value >= 1000000000) return (value / 1000000000).toFixed(2) + "B";
    if (value >= 1000000) return (value / 1000000).toFixed(1) + "M";
    if (value >= 1000) return (value / 1000).toFixed(1) + "K";
    return String(Math.round(value));
  }

  function formatCost(value) {
    return "$" + (Number(value) || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function formatPercent(value) {
    if (value == null || isNaN(value)) return "n/a";
    return (Number(value) || 0).toFixed(1) + "%";
  }

  function formatDate(value) {
    var date = typeof value === "string" ? new Date(value) : value;
    if (!date || isNaN(date.getTime())) return "unknown";
    return date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  function isoFromMs(value) {
    return new Date(value).toISOString();
  }

  function timeMs(session) {
    var date = startDate(session);
    return date ? date.getTime() : null;
  }

  function timeExtent(sessions) {
    var min = Infinity;
    var max = -Infinity;
    (sessions || []).forEach(function (session) {
      var ms = timeMs(session);
      if (ms == null) return;
      min = Math.min(min, ms);
      max = Math.max(max, ms);
    });
    if (!isFinite(min) || !isFinite(max)) return null;
    return { min: min, max: max };
  }

  function cloneFilters(filters) {
    var copy = {};
    Object.keys(filters).forEach(function (key) {
      copy[key] = Array.isArray(filters[key]) ? filters[key].slice() : filters[key];
    });
    return copy;
  }

  function filterKeyForDimension(dimension) {
    return DIMENSION_FILTERS[dimension] || null;
  }

  function sameArrayValues(left, right) {
    left = (left || []).map(String).sort();
    right = (right || []).map(String).sort();
    if (left.length !== right.length) return false;
    for (var i = 0; i < left.length; i += 1) {
      if (left[i] !== right[i]) return false;
    }
    return true;
  }

  function commitFilterChange(scrollToTable) {
    app.state.page = 1;
    syncControls(app.state, app.options);
    renderApp();
    if (scrollToTable) document.getElementById("session-table").scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function outcomeClass(label) {
    label = String(label || "unknown").toLowerCase();
    if (label.indexOf("useful") >= 0 || label.indexOf("productive") >= 0 || label.indexOf("durable") >= 0 || label.indexOf("edited") >= 0) return "useful";
    if (label.indexOf("waste") >= 0 || label.indexOf("failed") >= 0 || label.indexOf("retry") >= 0 || label.indexOf("dead") >= 0) return "waste";
    return "neutral";
  }

  function buildFindingIndex(report) {
    var index = {};
    (report.findings || []).forEach(function (finding) {
      (finding.session_ids || []).forEach(function (id) {
        if (!index[id]) index[id] = [];
        index[id].push(finding);
      });
    });
    return index;
  }

  function wastePattern(session, findingIndex) {
    var hits = (findingIndex && findingIndex[session.session_id]) || [];
    if (hits.length) return hits[0].kind || hits[0].title || "waste_signal";
    var labels = (session.command_labels || []).join(" ").toLowerCase();
    if (labels.indexOf("test") >= 0 && !session.file_edit_markers && tokens(session) > 20000) return "test_loop";
    if (labels.indexOf("read") >= 0 && !session.file_edit_markers && tokens(session) > 100000) return "repo_indexing";
    if (!session.file_edit_markers && !session.test_markers && tokens(session) > 50000) return "no_durable_output";
    if (outcomeClass(attrLabel(session.outcome)) === "waste") return "low_value_outcome";
    return "none";
  }

  function isUseful(session) {
    if (outcomeClass(attrLabel(session.outcome)) === "useful") return true;
    return Number(session.file_edit_markers || 0) > 0 || Number(session.test_markers || 0) > 0;
  }

  function isWaste(session, findingIndex) {
    if (outcomeClass(attrLabel(session.outcome)) === "waste") return true;
    return wastePattern(session, findingIndex) !== "none";
  }

  function hasUnknownAttribution(session) {
    return [session.client, session.project, session.paperclip_company, session.paperclip_staff, session.paperclip_task, session.task].some(function (item) {
      return attrLabel(item) === "unknown" || confidenceScore(item) < 25;
    });
  }

  function attributionCoverageBucket(session) {
    var pieces = [session.client, session.project, session.paperclip_staff, session.task].map(function (item) { return attrLabel(item) !== "unknown"; });
    var count = pieces.filter(Boolean).length;
    if (count === pieces.length) return "full";
    if (count > 0) return "partial";
    return "unknown";
  }

  function sessionProject(session) {
    var paperclip = attrLabel(session.paperclip_project);
    return paperclip !== "unknown" ? paperclip : attrLabel(session.project);
  }

  function sessionTask(session) {
    var paperclip = attrLabel(session.paperclip_task);
    return paperclip !== "unknown" ? paperclip : attrLabel(session.task);
  }

  function normalizeSession(session, report) {
    var findingIndex = report ? buildFindingIndex(report) : {};
    return {
      start_time: session.start_time || "",
      session_id: session.session_id || "",
      client: attrLabel(session.client),
      project: sessionProject(session),
      company: attrLabel(session.paperclip_company),
      staff: attrLabel(session.paperclip_staff),
      task: sessionTask(session),
      model: session.model || "unknown",
      tokens: tokens(session),
      cost: cost(session),
      credits: credits(session),
      outcome: attrLabel(session.outcome),
      waste: wastePattern(session, findingIndex),
      confidence: sessionConfidence(session)
    };
  }

  function uniqueSorted(values) {
    var seen = {};
    values.forEach(function (value) {
      value = value || "unknown";
      seen[value] = true;
    });
    return Object.keys(seen).sort(function (a, b) {
      if (a === "unknown") return 1;
      if (b === "unknown") return -1;
      return a.localeCompare(b);
    });
  }

  function topOptions(sessions, getter, limit) {
    var map = {};
    (sessions || []).forEach(function (session) {
      var value = getter(session) || "unknown";
      if (!map[value]) map[value] = { label: value, tokens: 0, sessions: 0 };
      map[value].tokens += tokens(session);
      map[value].sessions += 1;
    });
    var rows = Object.keys(map).map(function (key) { return map[key]; }).sort(function (a, b) {
      if (a.label === "unknown") return 1;
      if (b.label === "unknown") return -1;
      return b.tokens - a.tokens || b.sessions - a.sessions || a.label.localeCompare(b.label);
    });
    return rows.slice(0, limit).map(function (row) { return row.label; });
  }

  function buildOptions(report) {
    var sessions = report.sessions || [];
    return {
      clients: uniqueSorted(sessions.map(function (s) { return attrLabel(s.client); })),
      projects: uniqueSorted(sessions.map(sessionProject)),
      companies: uniqueSorted(sessions.map(function (s) { return attrLabel(s.paperclip_company); })),
      staff: uniqueSorted(sessions.map(function (s) { return attrLabel(s.paperclip_staff); })),
      tasks: topOptions(sessions, sessionTask, 500),
      models: uniqueSorted(sessions.map(function (s) { return s.model || "unknown"; })),
      outcomes: uniqueSorted(sessions.map(function (s) { return attrLabel(s.outcome); }))
    };
  }

  function maxSessionTime(sessions) {
    return sessions.reduce(function (max, session) {
      var date = startDate(session);
      return date && date.getTime() > max ? date.getTime() : max;
    }, 0);
  }

  function matchesDatePreset(session, filters, allSessions) {
    var date = startDate(session);
    if (!date) return filters.preset === "all";
    var hour = date.getHours();
    if (filters.preset === "overnight" && !(hour >= 18 || hour < 6)) return false;
    if (filters.preset === "last24" || filters.preset === "last7") {
      var max = maxSessionTime(allSessions);
      var span = filters.preset === "last24" ? 24 * 60 * 60 * 1000 : 7 * 24 * 60 * 60 * 1000;
      if (max && date.getTime() < max - span) return false;
    }
    return true;
  }

  function matchesHour(session, filters) {
    if (filters.hourStart === "" && filters.hourEnd === "") return true;
    var date = startDate(session);
    if (!date) return false;
    var hour = date.getHours();
    var start = filters.hourStart === "" ? 0 : Number(filters.hourStart);
    var end = filters.hourEnd === "" ? 23 : Number(filters.hourEnd);
    if (start <= end) return hour >= start && hour <= end;
    return hour >= start || hour <= end;
  }

  function matchesWeekday(session, filters) {
    if (!filters.weekdays || !filters.weekdays.length) return true;
    var date = startDate(session);
    if (!date) return false;
    return filters.weekdays.indexOf(String(date.getDay())) >= 0;
  }

  function matchesBrush(session, filters) {
    if (!filters.brushStartTime && !filters.brushEndTime) return true;
    var ms = timeMs(session);
    if (ms == null) return false;
    var start = filters.brushStartTime ? new Date(filters.brushStartTime).getTime() : -Infinity;
    var end = filters.brushEndTime ? new Date(filters.brushEndTime).getTime() : Infinity;
    return ms >= start && ms <= end;
  }

  function hasSelected(selected, value) {
    return !selected || !selected.length || selected.indexOf(value || "unknown") >= 0;
  }

  function matchesSearch(session, search) {
    if (!search) return true;
    var haystack = [
      session.session_id,
      session.cwd,
      session.path,
      session.model,
      attrLabel(session.client),
      attrLabel(session.project),
      attrLabel(session.paperclip_company),
      attrLabel(session.paperclip_project),
      attrLabel(session.paperclip_staff),
      attrLabel(session.paperclip_task),
      attrLabel(session.task),
      attrLabel(session.outcome),
      (session.command_labels || []).join(" ")
    ].join(" ").toLowerCase();
    return haystack.indexOf(String(search).toLowerCase()) >= 0;
  }

  function matchesWaste(session, filters, findingIndex) {
    var pattern = wastePattern(session, findingIndex);
    if (filters.wasteKind && pattern !== filters.wasteKind) return false;
    if (filters.waste === "all") return true;
    if (filters.waste === "any") return pattern !== "none";
    if (filters.waste === "useful-only") return isUseful(session);
    if (filters.waste === "unknown-attribution") return hasUnknownAttribution(session);
    if (filters.waste === "retry") return pattern.indexOf("retry") >= 0 || pattern.indexOf("rework") >= 0 || pattern.indexOf("repeated_command") >= 0;
    if (filters.waste === "no-edit") return pattern === "no_durable_output" || (!session.file_edit_markers && !isUseful(session));
    if (filters.waste === "test-loop") return pattern.indexOf("test") >= 0;
    if (filters.waste === "indexing") return pattern.indexOf("index") >= 0;
    if (filters.waste === "startup") return pattern.indexOf("startup") >= 0 || pattern.indexOf("context") >= 0;
    return true;
  }

  function applyFilters(sessions, filters, report) {
    var findingIndex = buildFindingIndex(report || {});
    sessions = sessions || [];
    return sessions.filter(function (session) {
      if (filters.sessionIds && filters.sessionIds.length && filters.sessionIds.indexOf(session.session_id) < 0) return false;
      if (!matchesDatePreset(session, filters, sessions)) return false;
      if (!matchesHour(session, filters)) return false;
      if (!matchesWeekday(session, filters)) return false;
      if (!matchesBrush(session, filters)) return false;
      if (!matchesSearch(session, filters.search)) return false;
      if (!hasSelected(filters.clients, attrLabel(session.client))) return false;
      if (!hasSelected(filters.projects, sessionProject(session))) return false;
      if (!hasSelected(filters.companies, attrLabel(session.paperclip_company))) return false;
      if (!hasSelected(filters.staff, attrLabel(session.paperclip_staff))) return false;
      if (!hasSelected(filters.tasks, sessionTask(session))) return false;
      if (!hasSelected(filters.models, session.model || "unknown")) return false;
      if (!hasSelected(filters.outcomes, attrLabel(session.outcome))) return false;
      if (filters.outcomeBucket && outcomeBucket(session, findingIndex) !== filters.outcomeBucket) return false;
      if (filters.attributionCoverage === "unknown-staff" && attrLabel(session.paperclip_staff) !== "unknown") return false;
      else if (filters.attributionCoverage === "unknown-task" && sessionTask(session) !== "unknown") return false;
      else if (filters.attributionCoverage && filters.attributionCoverage.indexOf("unknown-") !== 0 && attributionCoverageBucket(session) !== filters.attributionCoverage) return false;
      if (sessionConfidence(session) < Number(filters.minConfidence || 0)) return false;
      if (!matchesWaste(session, filters, findingIndex)) return false;
      return true;
    });
  }

  function summarize(sessions, report) {
    var findingIndex = buildFindingIndex(report || {});
    var allTokens = (report.sessions || []).reduce(function (sum, session) { return sum + tokens(session); }, 0);
    var livePercent = liveQuotaPercent(report);
    var summary = sessions.reduce(function (acc, session) {
      var t = tokens(session);
      var c = cost(session);
      acc.sessions += 1;
      acc.tokens += t;
      acc.cost += c;
      acc.credits += credits(session);
      if (isWaste(session, findingIndex)) {
        acc.wasteTokens += t;
        acc.wasteCost += c;
      }
      if (isUseful(session)) {
        acc.usefulTokens += t;
        acc.usefulCost += c;
      }
      if (!isUseful(session) && !isWaste(session, findingIndex)) {
        acc.neutralTokens += t;
        acc.neutralCost += c;
      }
      return acc;
    }, {
      sessions: 0,
      tokens: 0,
      cost: 0,
      credits: 0,
      usefulTokens: 0,
      usefulCost: 0,
      wasteTokens: 0,
      wasteCost: 0,
      neutralTokens: 0,
      neutralCost: 0,
      quotaPercent: null
    });
    summary.quotaPercent = livePercent;
    summary.observedSharePercent = allTokens > 0 ? summary.tokens / allTokens * 100 : 0;
    return summary;
  }

  function liveQuotaPercent(report) {
    var telemetry = report.telemetry || {};
    var usage = telemetry.live_usage || {};
    var windows = Array.isArray(usage.windows) ? usage.windows : [];
    for (var i = 0; i < windows.length; i += 1) {
      if (windows[i] && windows[i].usedPercent != null) return Number(windows[i].usedPercent);
    }
    return null;
  }

  function groupBy(sessions, getter) {
    var map = {};
    sessions.forEach(function (session) {
      var key = getter(session) || "unknown";
      if (!map[key]) map[key] = { label: key, sessions: 0, tokens: 0, cost: 0 };
      map[key].sessions += 1;
      map[key].tokens += tokens(session);
      map[key].cost += cost(session);
    });
    return Object.keys(map).map(function (key) { return map[key]; }).sort(function (a, b) { return b.tokens - a.tokens; });
  }

  function dayString(session) {
    var date = startDate(session);
    return date ? date.toISOString().slice(0, 10) : "unknown";
  }

  function dateSpanDays(days) {
    days = (days || []).filter(function (day) { return day !== "unknown"; }).sort();
    if (!days.length) return 1;
    var first = new Date(days[0] + "T00:00:00Z").getTime();
    var last = new Date(days[days.length - 1] + "T00:00:00Z").getTime();
    if (!isFinite(first) || !isFinite(last)) return 1;
    return Math.max(1, Math.round((last - first) / 86400000) + 1);
  }

  function companySpendModel(sessions, report, metric) {
    var valueFor = metric === "tokens" ? tokens : cost;
    var projectionDays = Number((report.plan_analysis && report.plan_analysis.projection_days) || (report.paperclip_spend && report.paperclip_spend.projection_days) || 30);
    var totals = {};
    var days = {};
    var dayCompany = {};
    (sessions || []).forEach(function (session) {
      var company = attrLabel(session.paperclip_company);
      if (company === "unknown") return;
      var day = dayString(session);
      var value = valueFor(session);
      if (!totals[company]) totals[company] = { company: company, sessions: 0, tokens: 0, cost: 0, days: {} };
      totals[company].sessions += 1;
      totals[company].tokens += tokens(session);
      totals[company].cost += cost(session);
      totals[company].days[day] = true;
      days[day] = true;
      var key = day + "|" + company;
      if (!dayCompany[key]) dayCompany[key] = { day: day, company: company, sessions: 0, tokens: 0, cost: 0, value: 0 };
      dayCompany[key].sessions += 1;
      dayCompany[key].tokens += tokens(session);
      dayCompany[key].cost += cost(session);
      dayCompany[key].value += value;
    });
    var totalRows = Object.keys(totals).map(function (company) {
      var row = totals[company];
      var activeDays = Object.keys(row.days).length;
      var span = dateSpanDays(Object.keys(row.days));
      row.activeDays = activeDays;
      row.observedSpanDays = span;
      row.projectedCost = span ? row.cost / span * projectionDays : 0;
      row.projectedTokens = span ? row.tokens / span * projectionDays : 0;
      return row;
    }).sort(function (a, b) { return b[metric] - a[metric]; });
    var topCompanies = {};
    totalRows.slice(0, 5).forEach(function (row) { topCompanies[row.company] = true; });
    var dayRows = Object.keys(days).sort().slice(-14).map(function (day) {
      var companies = {};
      var total = 0;
      Object.keys(dayCompany).forEach(function (key) {
        var row = dayCompany[key];
        if (row.day !== day) return;
        var label = topCompanies[row.company] ? row.company : "Other";
        companies[label] = (companies[label] || 0) + row.value;
        total += row.value;
      });
      return { day: day, companies: companies, total: total };
    });
    return { metric: metric, projectionDays: projectionDays, totals: totalRows, days: dayRows };
  }

  function outcomeBucket(session, findingIndex) {
    if (isWaste(session, findingIndex || {})) return "Waste";
    if (isUseful(session)) return "Useful";
    return "Neutral";
  }

  function buildFlowModel(sessions, report, metric) {
    var findingIndex = buildFindingIndex(report || {});
    var stages = [
      { id: "client", label: "Client", get: function (s) { return attrLabel(s.client); } },
      { id: "project", label: "Project", get: sessionProject },
      { id: "staff", label: "Staff", get: function (s) { return attrLabel(s.paperclip_staff); } },
      { id: "outcome", label: "Outcome", get: function (s) { return outcomeBucket(s, findingIndex); } }
    ];
    var valueFor = metric === "tokens" ? tokens : cost;
    var total = sessions.reduce(function (sum, session) { return sum + valueFor(session); }, 0);
    function groupStage(getter) {
      var map = {};
      sessions.forEach(function (session) {
        var key = getter(session) || "unknown";
        if (!map[key]) map[key] = { label: key, value: 0 };
        map[key].value += valueFor(session);
      });
      return Object.keys(map).map(function (key) { return map[key]; }).sort(function (a, b) { return b.value - a.value; });
    }
    var topByStage = {};
    stages.forEach(function (stage) {
      var grouped = groupStage(stage.get);
      topByStage[stage.id] = {};
      grouped.slice(0, stage.id === "outcome" ? 10 : 5).forEach(function (row) {
        topByStage[stage.id][row.label] = true;
      });
    });
    function bucketLabel(stage, raw) {
      if (stage.id === "outcome") return raw;
      if (topByStage[stage.id][raw]) return raw;
      if (raw === "unknown") return "Unknown";
      return "Other / Unknown";
    }
    var nodeMap = {};
    var linkMap = {};
    sessions.forEach(function (session) {
      var value = valueFor(session);
      var labels = stages.map(function (stage) { return bucketLabel(stage, stage.get(session) || "unknown"); });
      labels.forEach(function (label, idx) {
        var stage = stages[idx];
        var id = stage.id + "|" + label;
        if (!nodeMap[id]) nodeMap[id] = { id: id, stage: stage.id, stageLabel: stage.label, label: label, value: 0, tokens: 0, cost: 0, sessions: 0, sessionIds: {} };
        nodeMap[id].value += value;
        nodeMap[id].tokens += tokens(session);
        nodeMap[id].cost += cost(session);
        nodeMap[id].sessions += 1;
        nodeMap[id].sessionIds[session.session_id] = true;
      });
      for (var i = 0; i < stages.length - 1; i += 1) {
        var source = stages[i].id + "|" + labels[i];
        var target = stages[i + 1].id + "|" + labels[i + 1];
        var linkId = source + "->" + target;
        if (!linkMap[linkId]) linkMap[linkId] = { id: linkId, source: source, target: target, sourceStage: stages[i].id, targetStage: stages[i + 1].id, value: 0, tokens: 0, cost: 0, sessions: 0, sessionIds: {}, outcome: labels[labels.length - 1] };
        linkMap[linkId].value += value;
        linkMap[linkId].tokens += tokens(session);
        linkMap[linkId].cost += cost(session);
        linkMap[linkId].sessions += 1;
        linkMap[linkId].sessionIds[session.session_id] = true;
      }
    });
    var columns = stages.map(function (stage) {
      var nodes = Object.keys(nodeMap).map(function (key) { return nodeMap[key]; }).filter(function (node) { return node.stage === stage.id; }).sort(function (a, b) { return b.value - a.value; });
      nodes.forEach(function (node) {
        node.share = total ? node.value / total * 100 : 0;
        node.sessionIds = Object.keys(node.sessionIds);
      });
      return { id: stage.id, label: stage.label, nodes: nodes };
    });
    var links = Object.keys(linkMap).map(function (key) {
      var link = linkMap[key];
      link.share = total ? link.value / total * 100 : 0;
      link.sessionIds = Object.keys(link.sessionIds);
      return link;
    }).sort(function (a, b) { return b.value - a.value; });
    return { metric: metric, total: total, columns: columns, links: links };
  }

  function layoutFlowModel(model, width, height) {
    width = Math.max(300, Number(width) || 520);
    var maxNodes = model.columns.reduce(function (max, column) { return Math.max(max, column.nodes.length); }, 0);
    var requiredHeight = 46 + maxNodes * 36 + Math.max(0, maxNodes - 1) * 8;
    height = Math.max(220, Number(height) || 300, requiredHeight);
    var nodeWidth = Math.min(144, Math.max(68, width * 0.17));
    var stageGap = model.columns.length > 1 ? (width - nodeWidth) / (model.columns.length - 1) : 0;
    var topPad = 34;
    var bottomPad = 12;
    function positionColumns(currentHeight) {
      var positions = {};
      var maxBottom = 0;
      model.columns.forEach(function (column, colIndex) {
        var x = colIndex * stageGap;
        var available = Math.max(80, currentHeight - topPad - bottomPad);
        var totalValue = Math.max(1, column.nodes.reduce(function (sum, node) { return sum + node.value; }, 0));
        var gap = 8;
        var minH = 30;
        var gapTotal = gap * Math.max(0, column.nodes.length - 1);
        var nodeSpace = Math.max(column.nodes.length * minH, available - gapTotal);
        var remaining = Math.max(0, nodeSpace - column.nodes.length * minH);
        var y = topPad;
        column.nodes.forEach(function (node, idx) {
          var h = minH + remaining * (node.value / totalValue);
          positions[node.id] = { x: x, y: y, width: nodeWidth, height: h, node: node };
          y += h + gap;
        });
        maxBottom = Math.max(maxBottom, y - gap + bottomPad);
      });
      return { positions: positions, maxBottom: maxBottom };
    }
    var positioned = positionColumns(height);
    for (var grow = 0; grow < 4 && positioned.maxBottom > height + 1; grow += 1) {
      height = Math.ceil(positioned.maxBottom);
      positioned = positionColumns(height);
    }
    var nodePositions = positioned.positions;
    var incoming = {};
    var outgoing = {};
    model.links.forEach(function (link) {
      if (!outgoing[link.source]) outgoing[link.source] = [];
      if (!incoming[link.target]) incoming[link.target] = [];
      outgoing[link.source].push(link);
      incoming[link.target].push(link);
    });
    function linkOrder(a, b) {
      var at = nodePositions[a.target] || nodePositions[a.source] || { y: 0 };
      var bt = nodePositions[b.target] || nodePositions[b.source] || { y: 0 };
      return at.y - bt.y || b.value - a.value;
    }
    Object.keys(outgoing).forEach(function (id) { outgoing[id].sort(linkOrder); });
    Object.keys(incoming).forEach(function (id) {
      incoming[id].sort(function (a, b) {
        var as = nodePositions[a.source] || { y: 0 };
        var bs = nodePositions[b.source] || { y: 0 };
        return as.y - bs.y || b.value - a.value;
      });
    });
    function slotCenter(pos, links, link) {
      if (!links || links.length <= 1) return pos.y + pos.height / 2;
      var totalValue = Math.max(1, links.reduce(function (sum, item) { return sum + item.value; }, 0));
      var pad = Math.min(10, Math.max(3, pos.height * 0.08));
      var usable = Math.max(1, pos.height - pad * 2);
      var cursor = 0;
      for (var i = 0; i < links.length; i += 1) {
        var item = links[i];
        var share = item.value / totalValue;
        var center = pos.y + pad + (cursor + share / 2) * usable;
        if (item.id === link.id) return center;
        cursor += share;
      }
      return pos.y + pos.height / 2;
    }
    var linkLayouts = model.links.map(function (link) {
      var source = nodePositions[link.source];
      var target = nodePositions[link.target];
      if (!source || !target) return null;
      var sx = source.x + source.width;
      var sy = slotCenter(source, outgoing[link.source], link);
      var tx = target.x;
      var ty = slotCenter(target, incoming[link.target], link);
      var mid = sx + (tx - sx) * 0.5;
      return {
        id: link.id,
        link: link,
        source: link.source,
        target: link.target,
        sx: sx,
        sy: sy,
        tx: tx,
        ty: ty,
        strokeWidth: Math.max(2, link.value / Math.max(1, model.total) * 34),
        d: "M " + sx + " " + sy + " C " + mid + " " + sy + " " + mid + " " + ty + " " + tx + " " + ty
      };
    }).filter(Boolean);
    return { width: width, height: height, nodeWidth: nodeWidth, stageGap: stageGap, nodePositions: nodePositions, linkLayouts: linkLayouts };
  }

  function wasteDrivers(sessions, report) {
    var allowed = {};
    var byId = {};
    sessions.forEach(function (session) {
      allowed[session.session_id] = true;
      byId[session.session_id] = session;
    });
    return (report.findings || []).map(function (finding) {
      var matched = (finding.session_ids || []).filter(function (id) { return allowed[id]; });
      if (!matched.length) return null;
      return {
        title: finding.title || finding.kind || "waste",
        kind: finding.kind || "waste",
        sessions: matched.length,
        sessionIds: matched,
        tokens: matched.reduce(function (sum, id) { return sum + tokens(byId[id]); }, 0),
        cost: matched.reduce(function (sum, id) { return sum + cost(byId[id]); }, 0),
        confidence: finding.confidence || "unknown"
      };
    }).filter(Boolean).sort(function (a, b) { return b.cost - a.cost || b.tokens - a.tokens; });
  }

  function coverageStats(sessions) {
    var full = 0;
    var partial = 0;
    var unknown = 0;
    var unknownStaff = 0;
    var unknownTask = 0;
    sessions.forEach(function (session) {
      var t = tokens(session);
      var pieces = [session.client, session.project, session.paperclip_staff, session.task].map(function (item) { return attrLabel(item) !== "unknown"; });
      var count = pieces.filter(Boolean).length;
      if (count === pieces.length) full += t;
      else if (count > 0) partial += t;
      else unknown += t;
      if (attrLabel(session.paperclip_staff) === "unknown") unknownStaff += t;
      if (sessionTask(session) === "unknown") unknownTask += t;
    });
    var total = full + partial + unknown;
    return {
      full: total ? full / total * 100 : 0,
      partial: total ? partial / total * 100 : 0,
      unknown: total ? unknown / total * 100 : 0,
      unknownStaff: total ? unknownStaff / total * 100 : 0,
      unknownTask: total ? unknownTask / total * 100 : 0
    };
  }

  function hourlyBuckets(sessions, report, metric) {
    var findingIndex = buildFindingIndex(report || {});
    var valueFor = metric === "cost" ? cost : tokens;
    var map = {};
    sessions.forEach(function (session) {
      var date = startDate(session);
      if (!date) return;
      var key = date.toISOString().slice(0, 13);
      if (!map[key]) map[key] = { key: key, date: date, useful: 0, waste: 0, neutral: 0, unknown: 0 };
      var value = valueFor(session);
      var outcome = outcomeClass(attrLabel(session.outcome));
      if (isWaste(session, findingIndex)) map[key].waste += value;
      else if (isUseful(session) || outcome === "useful") map[key].useful += value;
      else if (outcome === "neutral") map[key].neutral += value;
      else map[key].unknown += value;
    });
    return Object.keys(map).map(function (key) {
      map[key].total = map[key].useful + map[key].waste + map[key].neutral + map[key].unknown;
      return map[key];
    }).sort(function (a, b) { return a.date - b.date; });
  }

  function visibleBrushExtent(report, sessions) {
    var baseFilters = cloneFilters(app.state.filters);
    baseFilters.brushStartTime = "";
    baseFilters.brushEndTime = "";
    var baseSessions = applyFilters((report && report.sessions) || sessions || [], baseFilters, report);
    var buckets = hourlyBuckets(baseSessions, report, "tokens").slice(-120);
    if (!buckets.length) return null;
    return { min: buckets[0].date.getTime(), max: buckets[buckets.length - 1].date.getTime() + 60 * 60 * 1000 - 1 };
  }

  function heatmapCells(sessions) {
    var cells = {};
    sessions.forEach(function (session) {
      var date = startDate(session);
      if (!date) return;
      var day = date.getDay();
      var hour = date.getHours();
      var key = day + ":" + hour;
      cells[key] = (cells[key] || 0) + tokens(session);
    });
    return cells;
  }

  function sortSessions(sessions, sort, report) {
    var copy = (sessions || []).slice();
    var dir = sort.dir === "asc" ? 1 : -1;
    var findingIndex = buildFindingIndex(report || {});
    copy.sort(function (a, b) {
      var av = valueForSort(a, sort.key, findingIndex);
      var bv = valueForSort(b, sort.key, findingIndex);
      if (typeof av === "number" || typeof bv === "number") return ((Number(av) || 0) - (Number(bv) || 0)) * dir;
      return String(av || "").localeCompare(String(bv || "")) * dir;
    });
    return copy;
  }

  function valueForSort(session, key, findingIndex) {
    if (key === "tokens") return tokens(session);
    if (key === "cost") return cost(session);
    if (key === "confidence") return sessionConfidence(session);
    if (key === "client") return attrLabel(session.client);
    if (key === "project") return sessionProject(session);
    if (key === "staff") return attrLabel(session.paperclip_staff);
    if (key === "task") return sessionTask(session);
    if (key === "outcome") return attrLabel(session.outcome);
    if (key === "waste") return wastePattern(session, findingIndex);
    return session[key] || "";
  }

  function toCsv(sessions, report) {
    var findingIndex = buildFindingIndex(report || {});
    var rows = [[
      "start_time",
      "session_id",
      "client",
      "project",
      "paperclip_company",
      "staff",
      "task",
      "model",
      "tokens",
      "estimated_cost_usd",
      "estimated_credits",
      "outcome",
      "waste_pattern",
      "confidence"
    ]];
    sessions.forEach(function (session) {
      rows.push([
        session.start_time || "",
        session.session_id || "",
        attrLabel(session.client),
        sessionProject(session),
        attrLabel(session.paperclip_company),
        attrLabel(session.paperclip_staff),
        sessionTask(session),
        session.model || "unknown",
        tokens(session),
        cost(session),
        credits(session),
        attrLabel(session.outcome),
        wastePattern(session, findingIndex),
        sessionConfidence(session)
      ]);
    });
    return rows.map(function (row) {
      return row.map(function (value) {
        value = String(value == null ? "" : value);
        return /[",\n]/.test(value) ? '"' + value.replace(/"/g, '""') + '"' : value;
      }).join(",");
    }).join("\n") + "\n";
  }

  function encodeFilters(state) {
    var params = new URLSearchParams();
    Object.keys(state.filters).forEach(function (key) {
      var value = state.filters[key];
      if (Array.isArray(value) && value.length) params.set(key, value.join("|"));
      else if (!Array.isArray(value) && value !== "" && value !== "all" && value !== 0) params.set(key, value);
    });
    params.set("sort", state.sort.key + ":" + state.sort.dir);
    if (state.metric !== "cost") params.set("metric", state.metric);
    if (state.compareMode) params.set("compare", "1");
    if (!state.drawerOpen) params.set("drawer", "closed");
    if (state.selectedSessionId) params.set("session", state.selectedSessionId);
    if (state.page > 1) params.set("page", String(state.page));
    if (state.density !== "compact") params.set("density", state.density);
    if (state.drawerTab !== "evidence") params.set("drawerTab", state.drawerTab);
    if (state.visibleColumns.length !== DEFAULT_COLUMNS.length) params.set("columns", state.visibleColumns.join("|"));
    if (state.hiddenOutcomes.length) params.set("hiddenOutcomes", state.hiddenOutcomes.join("|"));
    return params.toString();
  }

  function decodeFilters(query) {
    var state = createState();
    var params = new URLSearchParams(query || "");
    Object.keys(state.filters).forEach(function (key) {
      if (!params.has(key)) return;
      if (Array.isArray(state.filters[key])) state.filters[key] = params.get(key).split("|").filter(Boolean);
      else if (key === "minConfidence") state.filters[key] = Number(params.get(key) || 0);
      else state.filters[key] = params.get(key);
    });
    if (params.has("sort")) {
      var parts = params.get("sort").split(":");
      state.sort = { key: parts[0] || "tokens", dir: parts[1] || "desc" };
    }
    if (params.has("metric")) state.metric = params.get("metric");
    if (params.has("compare")) state.compareMode = params.get("compare") === "1";
    if (params.get("drawer") === "closed") state.drawerOpen = false;
    if (params.has("session")) state.selectedSessionId = params.get("session");
    if (params.has("page")) state.page = Math.max(1, Number(params.get("page") || 1));
    if (params.has("density")) state.density = params.get("density");
    if (params.has("drawerTab")) state.drawerTab = params.get("drawerTab");
    if (params.has("columns")) state.visibleColumns = params.get("columns").split("|").filter(Boolean);
    if (params.has("hiddenOutcomes")) state.hiddenOutcomes = params.get("hiddenOutcomes").split("|").filter(Boolean);
    return state;
  }

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    attrs = attrs || {};
    Object.keys(attrs).forEach(function (key) {
      if (key === "class") node.className = attrs[key];
      else if (key === "style") node.setAttribute("style", attrs[key]);
      else if (key.indexOf("aria-") === 0 || key.indexOf("data-") === 0 || key === "role" || key === "tabindex" || key === "title") node.setAttribute(key, attrs[key]);
      else node[key] = attrs[key];
    });
    (children || []).forEach(function (child) {
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    });
    return node;
  }

  function setText(id, text) {
    var node = document.getElementById(id);
    if (node) node.textContent = text;
  }

  function clear(node) {
    if (!node) return;
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function fillSelect(id, values, selected) {
    var select = document.getElementById(id);
    if (!select) return;
    clear(select);
    select.appendChild(el("option", { value: "" }, ["All"]));
    var merged = (values || []).slice();
    (selected || []).forEach(function (value) {
      if (merged.indexOf(value) < 0) merged.push(value);
    });
    merged.forEach(function (value) {
      var option = el("option", { value: value }, [value]);
      if ((selected || []).indexOf(value) >= 0) option.selected = true;
      select.appendChild(option);
    });
  }

  function selectedValues(id) {
    var select = document.getElementById(id);
    if (!select) return [];
    return Array.prototype.slice.call(select.selectedOptions).map(function (option) { return option.value; }).filter(Boolean);
  }

  function updateTimeButtons(state) {
    var preset = "all";
    if (state.filters.hourStart === "6" && state.filters.hourEnd === "17") preset = "day";
    if (state.filters.hourStart === "18" && state.filters.hourEnd === "5") preset = "night";
    Array.prototype.slice.call(document.querySelectorAll(".time-button")).forEach(function (button) {
      button.classList.toggle("active", button.getAttribute("data-time-preset") === preset);
    });
  }

  function syncControls(state, options) {
    document.getElementById("date-preset").value = state.filters.preset;
    document.getElementById("search-input").value = state.filters.search;
    document.getElementById("waste-filter").value = state.filters.waste;
    document.getElementById("confidence-filter").value = state.filters.minConfidence;
    document.getElementById("hour-start").value = state.filters.hourStart;
    document.getElementById("hour-end").value = state.filters.hourEnd;
    document.getElementById("metric-toggle").value = state.metric;
    document.getElementById("compare-mode").checked = Boolean(state.compareMode);
    document.getElementById("density-select").value = state.density;
    Object.keys(FIELD_IDS).forEach(function (key) {
      fillSelect(FIELD_IDS[key], options[key] || [], state.filters[key]);
    });
    setText("confidence-value", state.filters.minConfidence + "%");
    updateTimeButtons(state);
  }

  function readControls(state) {
    state.filters.preset = document.getElementById("date-preset").value;
    state.filters.search = document.getElementById("search-input").value.trim();
    state.filters.waste = document.getElementById("waste-filter").value;
    state.filters.minConfidence = Number(document.getElementById("confidence-filter").value || 0);
    state.filters.hourStart = document.getElementById("hour-start").value;
    state.filters.hourEnd = document.getElementById("hour-end").value;
    state.metric = document.getElementById("metric-toggle").value;
    state.compareMode = document.getElementById("compare-mode").checked;
    state.density = document.getElementById("density-select").value;
    Object.keys(FIELD_IDS).forEach(function (key) {
      state.filters[key] = selectedValues(FIELD_IDS[key]);
    });
    setText("confidence-value", state.filters.minConfidence + "%");
    updateTimeButtons(state);
  }

  function renderKpis(summary) {
    var strip = document.getElementById("kpi-strip");
    clear(strip);
    var rows = [
      ["sessions", "Sessions", formatNumber(summary.sessions), formatPercent(summary.observedSharePercent) + " of observed sessions"],
      ["tokens", "Tokens", formatTokens(summary.tokens), formatNumber(summary.tokens) + " raw tokens"],
      ["cost", "Rate-card Cost", formatCost(summary.cost), "Directional replacement-cost estimate"],
      ["quota", "Live Quota Now", formatPercent(summary.quotaPercent), "Current CodexBar window, not filter-apportioned"],
      ["useful", "Durable Output", formatCost(summary.usefulCost), formatTokens(summary.usefulTokens) + " tokens with output signals"],
      ["waste", "Review Candidates", formatCost(summary.wasteCost), formatTokens(summary.wasteTokens) + " tokens to inspect"]
    ];
    rows.forEach(function (row) {
      var interactive = row[0] === "useful" || row[0] === "waste";
      var active = row[0] === "useful" ? app.state.filters.waste === "useful-only" : row[0] === "waste" && app.state.filters.waste === "any" && !app.state.filters.wasteKind;
      var attrs = { class: "kpi " + row[0] + (active ? " active" : "") };
      if (interactive) {
        attrs.role = "button";
        attrs.tabindex = "0";
        attrs["aria-pressed"] = active ? "true" : "false";
        attrs["aria-label"] = (active ? "Clear " : "Filter to ") + row[1] + " sessions";
      }
      var card = el("article", attrs, [
        el("div", { class: "label" }, [row[1], el("button", { type: "button", class: "info-button", "data-info": row[0], "aria-label": "About " + row[1] }, ["i"])]),
        el("div", { class: "value" }, [row[2]]),
        el("div", { class: "sub" }, [row[3]])
      ]);
      if (interactive) {
        card.addEventListener("click", function (event) {
          if (event.target.closest(".info-button")) return;
          toggleKpiFilter(row[0]);
        });
        card.addEventListener("keydown", function (event) {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            toggleKpiFilter(row[0]);
          }
        });
      }
      strip.appendChild(card);
    });
  }

  function toggleKpiFilter(kind) {
    if (kind === "useful") {
      app.state.filters.waste = app.state.filters.waste === "useful-only" ? "all" : "useful-only";
      app.state.filters.wasteKind = "";
    } else if (kind === "waste") {
      if (app.state.filters.waste === "any" && !app.state.filters.wasteKind) app.state.filters.waste = "all";
      else {
        app.state.filters.waste = "any";
        app.state.filters.wasteKind = "";
      }
    }
    commitFilterChange();
  }

  function isCardFilterActive(kind) {
    var filters = app.state.filters;
    if (kind === "flow") {
      return Boolean(
        filters.clients.length ||
        filters.projects.length ||
        filters.staff.length ||
        filters.outcomes.length ||
        filters.outcomeBucket ||
        filters.sessionIds.length
      );
    }
    if (kind === "timeline") return Boolean(filters.brushStartTime || filters.brushEndTime || app.state.hiddenOutcomes.length);
    if (kind === "company") return Boolean(filters.companies.length || filters.brushStartTime || filters.brushEndTime);
    if (kind === "heatmap") return Boolean(filters.weekdays.length || filters.hourStart !== "" || filters.hourEnd !== "");
    if (kind === "waste") return Boolean(filters.waste !== "all" || filters.wasteKind);
    if (kind === "coverage") return Boolean(filters.attributionCoverage);
    if (kind === "projection") return Boolean(filters.waste === "any" && !filters.wasteKind);
    return false;
  }

  function resetCardFilter(kind) {
    var filters = app.state.filters;
    if (kind === "flow") {
      var hadOutcomeBucket = Boolean(filters.outcomeBucket);
      filters.clients = [];
      filters.projects = [];
      filters.staff = [];
      filters.outcomes = [];
      filters.outcomeBucket = "";
      filters.sessionIds = [];
      if (hadOutcomeBucket && filters.waste === "any" && !filters.wasteKind) filters.waste = "all";
    } else if (kind === "timeline") {
      filters.brushStartTime = "";
      filters.brushEndTime = "";
      app.state.hiddenOutcomes = [];
    } else if (kind === "company") {
      filters.companies = [];
      filters.brushStartTime = "";
      filters.brushEndTime = "";
    } else if (kind === "heatmap") {
      filters.weekdays = [];
      filters.hourStart = "";
      filters.hourEnd = "";
    } else if (kind === "waste") {
      filters.waste = "all";
      filters.wasteKind = "";
    } else if (kind === "coverage") {
      filters.attributionCoverage = "";
    } else if (kind === "projection") {
      if (filters.waste === "any" && !filters.wasteKind) filters.waste = "all";
    }
    commitFilterChange();
  }

  function updateCardResetButtons() {
    Array.prototype.slice.call(document.querySelectorAll(".card-reset[data-reset-card]")).forEach(function (button) {
      var kind = button.getAttribute("data-reset-card");
      var active = isCardFilterActive(kind);
      button.disabled = !active;
      button.classList.toggle("active", active);
      button.setAttribute("aria-disabled", active ? "false" : "true");
    });
  }

  function renderFlow(sessions, state) {
    var container = document.getElementById("spend-flow");
    clear(container);
    container.className = "flow-sankey";
    var metric = state.metric === "tokens" ? "tokens" : "cost";
    var model = buildFlowModel(sessions, app.report || {}, metric);
    if (!model.total) {
      container.appendChild(el("p", { class: "muted" }, ["No flow data in this filter."]));
      return;
    }
    var layout = layoutFlowModel(model, container.clientWidth || 520, container.clientHeight || 300);
    container.style.height = layout.height + "px";
    var nodePositions = layout.nodePositions;
    var svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "flow-svg");
    svg.setAttribute("viewBox", "0 0 " + layout.width + " " + layout.height);
    svg.setAttribute("role", "group");
    svg.setAttribute("aria-label", "Spend flow links");
    layout.linkLayouts.forEach(function (linkLayout) {
      var link = linkLayout.link;
      var path = document.createElementNS("http://www.w3.org/2000/svg", "path");
      path.setAttribute("d", linkLayout.d);
      path.setAttribute("class", "flow-link outcome-" + outcomeClass(link.outcome) + (sameArrayValues(state.filters.sessionIds, link.sessionIds) ? " active" : ""));
      path.setAttribute("stroke-width", String(linkLayout.strokeWidth));
      path.setAttribute("data-source", link.source);
      path.setAttribute("data-target", link.target);
      path.setAttribute("tabindex", "0");
      path.setAttribute("role", "button");
      path.setAttribute("aria-pressed", sameArrayValues(state.filters.sessionIds, link.sessionIds) ? "true" : "false");
      path.setAttribute("aria-label", (sameArrayValues(state.filters.sessionIds, link.sessionIds) ? "Clear flow link filter " : "Filter flow link ") + link.source.split("|")[1] + " to " + link.target.split("|")[1] + ", " + formatFlowValue(link, metric));
      path.addEventListener("click", function () { applyFlowLinkFilter(link); });
      path.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          applyFlowLinkFilter(link);
        }
      });
      path.addEventListener("mouseenter", function () { highlightFlow(link.source, link.target); });
      path.addEventListener("focus", function () { highlightFlow(link.source, link.target); });
      path.addEventListener("mouseleave", clearFlowHighlight);
      path.addEventListener("blur", clearFlowHighlight);
      svg.appendChild(path);
    });
    container.appendChild(svg);
    var layer = el("div", { class: "flow-node-layer" });
    model.columns.forEach(function (column) {
      var first = column.nodes[0] && nodePositions[column.nodes[0].id];
      if (first) layer.appendChild(el("div", { class: "flow-stage-label", style: "left:" + first.x + "px; top:8px; width:" + layout.nodeWidth + "px" }, [column.label]));
      column.nodes.forEach(function (node) {
        var pos = nodePositions[node.id];
        var active = flowNodeActive(node);
        var button = el("button", {
          type: "button",
          class: "flow-node outcome-" + outcomeClass(node.label) + (active ? " active" : ""),
          style: "left:" + pos.x + "px; top:" + pos.y + "px; width:" + pos.width + "px; height:" + pos.height + "px; --bar:100%",
          "data-node-id": node.id,
          "data-stage": node.stage,
          "aria-pressed": active ? "true" : "false",
          "aria-label": (active ? "Clear " : "Filter to ") + node.stageLabel + " " + node.label + ", " + formatFlowValue(node, metric),
          title: node.label + " " + formatFlowValue(node, metric)
        }, [
          el("strong", {}, [node.label]),
          el("span", {}, [formatFlowValue(node, metric)])
        ]);
        button.addEventListener("click", function () { applyFlowNodeFilter(node); });
        button.addEventListener("mouseenter", function () { highlightFlow(node.id, null); });
        button.addEventListener("focus", function () { highlightFlow(node.id, null); });
        button.addEventListener("mouseleave", clearFlowHighlight);
        button.addEventListener("blur", clearFlowHighlight);
        layer.appendChild(button);
      });
    });
    container.appendChild(layer);
  }

  function formatFlowValue(row, metric) {
    var value = metric === "tokens" ? formatTokens(row.tokens || row.value) : formatCost(row.cost || row.value);
    return value + " (" + formatPercent(row.share) + ")";
  }

  function flowNodeActive(node) {
    var key = filterKeyForDimension(node.stage);
    if (!key) return false;
    if (node.stage === "outcome") return app.state.filters.outcomeBucket === node.label;
    if (node.label === "Other / Unknown" || node.label === "Unknown") return sameArrayValues(app.state.filters.sessionIds, node.sessionIds);
    return sameArrayValues(app.state.filters[key], [node.label]);
  }

  function applyFlowNodeFilter(node) {
    var key = filterKeyForDimension(node.stage);
    if (!key) return;
    var active = flowNodeActive(node);
    if (node.stage === "outcome") {
      app.state.filters.sessionIds = [];
      if (active) clearOutcomeBucketFilter();
      else setOutcomeBucketFilter(node.label);
    } else if (node.label === "Other / Unknown" || node.label === "Unknown") {
      app.state.filters.sessionIds = active ? [] : node.sessionIds.slice();
    } else {
      app.state.filters.sessionIds = [];
      app.state.filters[key] = active ? [] : [node.label];
    }
    commitFilterChange();
  }

  function applyFlowLinkFilter(link) {
    app.state.filters.sessionIds = sameArrayValues(app.state.filters.sessionIds, link.sessionIds) ? [] : link.sessionIds.slice();
    commitFilterChange();
  }

  function setOutcomeBucketFilter(label) {
    app.state.filters.outcomeBucket = label;
    app.state.filters.outcomes = [];
    app.state.filters.waste = label === "Waste" ? "any" : "all";
  }

  function clearOutcomeBucketFilter() {
    app.state.filters.outcomeBucket = "";
    app.state.filters.outcomes = [];
    if (app.state.filters.waste === "any") app.state.filters.waste = "all";
  }

  function highlightFlow(sourceId, targetId) {
    var container = document.getElementById("spend-flow");
    if (!container) return;
    container.classList.add("flow-has-highlight");
    Array.prototype.slice.call(container.querySelectorAll(".flow-link")).forEach(function (link) {
      var connected = link.getAttribute("data-source") === sourceId || link.getAttribute("data-target") === sourceId || link.getAttribute("data-source") === targetId || link.getAttribute("data-target") === targetId;
      link.classList.toggle("flow-highlight", connected);
    });
    Array.prototype.slice.call(container.querySelectorAll(".flow-node")).forEach(function (node) {
      var id = node.getAttribute("data-node-id");
      var connected = id === sourceId || id === targetId;
      if (!connected) {
        connected = Array.prototype.slice.call(container.querySelectorAll(".flow-link.flow-highlight")).some(function (link) {
          return link.getAttribute("data-source") === id || link.getAttribute("data-target") === id;
        });
      }
      node.classList.toggle("flow-highlight", connected);
    });
  }

  function clearFlowHighlight() {
    var container = document.getElementById("spend-flow");
    if (!container) return;
    container.classList.remove("flow-has-highlight");
    Array.prototype.slice.call(container.querySelectorAll(".flow-highlight")).forEach(function (node) { node.classList.remove("flow-highlight"); });
  }

  function renderTimeline(sessions, report) {
    var container = document.getElementById("hourly-chart");
    var mini = document.getElementById("mini-brush");
    var selection = document.getElementById("brush-selection");
    var metricSelect = document.getElementById("timeline-metric");
    var metric = metricSelect ? metricSelect.value : "tokens";
    var visibleKeys = ["useful", "neutral", "waste", "unknown"].filter(function (key) {
      return app.state.hiddenOutcomes.indexOf(key) < 0;
    });
    clear(container);
    clear(mini);
    var baseFilters = cloneFilters(app.state.filters);
    baseFilters.brushStartTime = "";
    baseFilters.brushEndTime = "";
    var baseSessions = applyFilters((report && report.sessions) || sessions, baseFilters, report);
    var buckets = hourlyBuckets(baseSessions, report, metric).slice(-120);
    var extent = buckets.length ? { min: buckets[0].date.getTime(), max: buckets[buckets.length - 1].date.getTime() + 60 * 60 * 1000 - 1 } : null;
    var max = Math.max.apply(Math, buckets.map(function (bucket) { return visibleKeys.reduce(function (sum, key) { return sum + bucket[key]; }, 0); }).concat([1]));
    buckets.forEach(function (bucket) {
      var visibleTotal = visibleKeys.reduce(function (sum, key) { return sum + bucket[key]; }, 0);
      var bucketStart = bucket.date.getTime();
      var bucketEnd = bucketStart + 60 * 60 * 1000 - 1;
      var active = app.state.filters.brushStartTime && app.state.filters.brushEndTime && new Date(app.state.filters.brushStartTime).getTime() === bucketStart && new Date(app.state.filters.brushEndTime).getTime() === bucketEnd;
      var bar = el("div", {
        class: "hour-bar" + (active ? " active" : ""),
        role: "button",
        tabindex: "0",
        "aria-pressed": active ? "true" : "false",
        "aria-label": (active ? "Clear hour " : "Select hour ") + bucket.key + " with " + formatMetricValue(visibleTotal, metric),
        title: bucket.key + " " + formatMetricValue(visibleTotal, metric),
        style: "--height:" + Math.max(2, visibleTotal / max * 100).toFixed(1) + "%"
      });
      bar.addEventListener("click", function () {
        if (active) {
          app.state.filters.brushStartTime = "";
          app.state.filters.brushEndTime = "";
        } else {
          app.state.filters.brushStartTime = isoFromMs(bucketStart);
          app.state.filters.brushEndTime = isoFromMs(bucketEnd);
        }
        commitFilterChange();
      });
      bar.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          bar.click();
        }
      });
      visibleKeys.forEach(function (key) {
        if (!bucket[key]) return;
        bar.appendChild(el("div", { class: "hour-segment seg-" + key, style: "height:" + (bucket[key] / Math.max(1, visibleTotal) * 100).toFixed(1) + "%" }));
      });
      container.appendChild(bar);
      if (mini) {
        mini.appendChild(el("span", { style: "height:" + Math.max(2, visibleTotal / max * 100).toFixed(1) + "%" }));
      }
    });
    updateLegendState();
    updateBrushSelection(selection, extent, app.state.filters);
    if (buckets.length) {
      var selectedStart = app.state.filters.brushStartTime ? new Date(app.state.filters.brushStartTime) : buckets[0].date;
      var selectedEnd = app.state.filters.brushEndTime ? new Date(app.state.filters.brushEndTime) : buckets[buckets.length - 1].date;
      setText("brush-summary", "Brush to zoom - Selected: " + formatDate(selectedStart) + " - " + formatDate(selectedEnd) + " (" + formatNumber(sessions.length) + " sessions)");
    } else {
      setText("brush-summary", "No matching hours");
    }
  }

  function formatMetricValue(value, metric) {
    return metric === "cost" ? formatCost(value) : formatTokens(value);
  }

  function toggleLegendOutcome(item) {
    var key = (item.className || "").replace("legend-", "").split(" ")[0];
    if (!key) return;
    var index = app.state.hiddenOutcomes.indexOf(key);
    if (index >= 0) app.state.hiddenOutcomes.splice(index, 1);
    else app.state.hiddenOutcomes.push(key);
    renderApp();
  }

  function updateLegendState() {
    Array.prototype.slice.call(document.querySelectorAll(".legend span")).forEach(function (item) {
      var key = (item.className || "").replace("legend-", "").split(" ")[0];
      var hidden = app.state.hiddenOutcomes.indexOf(key) >= 0;
      item.classList.toggle("inactive", hidden);
      item.setAttribute("aria-pressed", hidden ? "false" : "true");
      item.setAttribute("aria-label", (hidden ? "Show " : "Hide ") + key + " timeline layer");
    });
  }

  function updateBrushSelection(selection, extent, filters) {
    if (!selection || !extent || extent.max <= extent.min) return;
    var start = filters.brushStartTime ? new Date(filters.brushStartTime).getTime() : extent.min;
    var end = filters.brushEndTime ? new Date(filters.brushEndTime).getTime() : extent.max;
    start = Math.max(extent.min, Math.min(start, extent.max));
    end = Math.max(start, Math.min(end, extent.max));
    var left = (start - extent.min) / (extent.max - extent.min) * 100;
    var right = 100 - (end - extent.min) / (extent.max - extent.min) * 100;
    selection.style.left = left.toFixed(2) + "%";
    selection.style.right = right.toFixed(2) + "%";
    selection.setAttribute("aria-valuenow", String(Math.round(100 - right)));
    if (!selection.querySelector(".brush-handle-left")) {
      selection.appendChild(el("span", { class: "brush-handle brush-handle-left", "aria-hidden": "true" }));
      selection.appendChild(el("span", { class: "brush-handle brush-handle-right", "aria-hidden": "true" }));
    }
  }

  function setBrushFromFractions(startFrac, endFrac) {
    var extent = visibleBrushExtent(app.report, []);
    if (!extent || extent.max <= extent.min) return;
    startFrac = Math.max(0, Math.min(startFrac, 0.99));
    endFrac = Math.max(startFrac + 0.01, Math.min(endFrac, 1));
    app.state.filters.brushStartTime = isoFromMs(extent.min + (extent.max - extent.min) * startFrac);
    app.state.filters.brushEndTime = isoFromMs(extent.min + (extent.max - extent.min) * endFrac);
    app.state.page = 1;
    syncControls(app.state, app.options);
    renderApp();
  }

  function renderHeatmap(sessions) {
    var container = document.getElementById("heatmap");
    clear(container);
    var cells = heatmapCells(sessions);
    var max = Math.max.apply(Math, Object.keys(cells).map(function (key) { return cells[key]; }).concat([1]));
    var labels = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
    container.appendChild(el("div", { class: "heat-label" }, [""]));
    for (var hourHead = 0; hourHead < 24; hourHead += 1) {
      container.appendChild(el("div", { class: "heat-label", title: hourHead + ":00" }, [hourHead % 6 === 0 ? String(hourHead) : ""]));
    }
    labels.forEach(function (label, day) {
      container.appendChild(el("div", { class: "heat-label" }, [label]));
      for (var hour = 0; hour < 24; hour += 1) {
        var value = cells[day + ":" + hour] || 0;
        var alpha = value ? 0.12 + (value / max * 0.78) : 0.04;
        var active = sameArrayValues(app.state.filters.weekdays, [String(day)]) && app.state.filters.hourStart === String(hour) && app.state.filters.hourEnd === String(hour);
        var cell = el("button", {
          type: "button",
          class: "heat-cell" + (active ? " active" : ""),
          title: label + " " + hour + ":00 " + formatTokens(value),
          "aria-pressed": active ? "true" : "false",
          "aria-label": (active ? "Clear " : "Filter to ") + label + " " + hour + ":00, " + formatTokens(value),
          style: "--alpha:" + alpha.toFixed(2)
        });
        (function (selectedDay, selectedHour) {
          cell.addEventListener("click", function () {
            if (sameArrayValues(app.state.filters.weekdays, [String(selectedDay)]) && app.state.filters.hourStart === String(selectedHour) && app.state.filters.hourEnd === String(selectedHour)) {
              app.state.filters.weekdays = [];
              app.state.filters.hourStart = "";
              app.state.filters.hourEnd = "";
            } else {
              app.state.filters.weekdays = [String(selectedDay)];
              app.state.filters.hourStart = String(selectedHour);
              app.state.filters.hourEnd = String(selectedHour);
            }
            commitFilterChange();
          });
        })(day, hour);
        container.appendChild(cell);
      }
    });
  }

  function renderRankings(sessions, state) {
    var container = document.getElementById("rankings");
    clear(container);
    var metric = state.metric === "tokens" ? "tokens" : "cost";
    [
      ["Clients", groupBy(sessions, function (s) { return attrLabel(s.client); })],
      ["Projects", groupBy(sessions, sessionProject)],
      ["Staff", groupBy(sessions, function (s) { return attrLabel(s.paperclip_staff); })]
    ].forEach(function (group) {
      var rows = group[1].slice(0, 4);
      var max = Math.max.apply(Math, rows.map(function (row) { return row[metric]; }).concat([1]));
      var wrap = el("div", { class: "rank-group" }, [el("h3", {}, [group[0]])]);
      rows.forEach(function (row) {
        wrap.appendChild(el("div", { class: "rank-row", style: "--bar:" + Math.max(3, row[metric] / max * 100).toFixed(1) + "%" }, [
          el("strong", { title: row.label }, [row.label]),
          el("span", {}, [(metric === "tokens" ? formatTokens(row.tokens) : formatCost(row.cost)) + " / " + row.sessions + " sessions"])
        ]));
      });
      container.appendChild(wrap);
    });
  }

  function renderCompanySpend(sessions, report, state) {
    var container = document.getElementById("company-spend");
    clear(container);
    var metric = state.metric === "tokens" ? "tokens" : "cost";
    var model = companySpendModel(sessions, report || {}, metric);
    if (!model.totals.length) {
      container.appendChild(el("p", { class: "muted" }, ["No Paperclip company sessions in this filter."]));
      return;
    }
    var maxDay = Math.max.apply(Math, model.days.map(function (row) { return row.total; }).concat([1]));
    var maxTotal = Math.max.apply(Math, model.totals.slice(0, 5).map(function (row) { return row[metric]; }).concat([1]));
    var planPrice = Number((report.plan_analysis && report.plan_analysis.monthly_plan_price_usd) || 0);
    var topWrap = el("div", { class: "company-spend-top" });
    model.totals.slice(0, 5).forEach(function (row) {
      var projected = metric === "tokens" ? row.projectedTokens : row.projectedCost;
      var value = metric === "tokens" ? row.tokens : row.cost;
      var button = el("button", {
        type: "button",
        class: sameArrayValues(app.state.filters.companies, [row.company]) ? "active" : "",
        style: "--bar:" + Math.max(4, value / maxTotal * 100).toFixed(1) + "%",
        "aria-pressed": sameArrayValues(app.state.filters.companies, [row.company]) ? "true" : "false",
        "aria-label": "Filter Paperclip company " + row.company
      }, [
        el("strong", { title: row.company }, [row.company]),
        el("span", {}, [formatMetricValue(value, metric) + " observed"]),
        el("span", {}, [formatMetricValue(projected, metric) + " projected " + model.projectionDays + "d"])
      ]);
      button.addEventListener("click", function () {
        app.state.filters.companies = sameArrayValues(app.state.filters.companies, [row.company]) ? [] : [row.company];
        commitFilterChange();
      });
      topWrap.appendChild(button);
    });
    container.appendChild(topWrap);
    var dayWrap = el("div", { class: "company-day-bars" });
    model.days.forEach(function (row) {
      var activeDay = app.state.filters.brushStartTime === row.day + "T00:00:00.000Z" && app.state.filters.brushEndTime === row.day + "T23:59:59.999Z";
      var day = el("button", {
        type: "button",
        class: "company-day" + (activeDay ? " active" : ""),
        title: row.day + " " + formatMetricValue(row.total, metric),
        "aria-pressed": activeDay ? "true" : "false",
        "aria-label": (activeDay ? "Clear day " : "Filter day ") + row.day
      }, [
        el("span", { class: "day-label" }, [row.day.slice(5)])
      ]);
      var stack = el("span", { class: "day-stack", style: "--height:" + Math.max(3, row.total / maxDay * 100).toFixed(1) + "%" });
      Object.keys(row.companies).sort(function (a, b) { return row.companies[b] - row.companies[a]; }).forEach(function (company, idx) {
        stack.appendChild(el("span", {
          class: "company-segment seg-" + (idx % 6),
          style: "height:" + (row.companies[company] / Math.max(1, row.total) * 100).toFixed(1) + "%",
          title: company + " " + formatMetricValue(row.companies[company], metric)
        }));
      });
      day.addEventListener("click", function () {
        if (activeDay) {
          app.state.filters.brushStartTime = "";
          app.state.filters.brushEndTime = "";
        } else {
          app.state.filters.brushStartTime = row.day + "T00:00:00.000Z";
          app.state.filters.brushEndTime = row.day + "T23:59:59.999Z";
        }
        commitFilterChange();
      });
      day.appendChild(stack);
      dayWrap.appendChild(day);
    });
    container.appendChild(dayWrap);
    if (planPrice) {
      var projectedCost = model.totals.reduce(function (sum, row) { return sum + row.projectedCost; }, 0);
      container.appendChild(el("p", { class: "company-plan-note" }, [
        "Filtered projected rate-card cost " + formatCost(projectedCost) + " vs plan price " + formatCost(planPrice) + " (" + formatPercent(planPrice ? projectedCost / planPrice * 100 : null) + ")."
      ]));
    }
  }

  function renderWasteDrivers(sessions, report) {
    var container = document.getElementById("waste-drivers");
    clear(container);
    var rows = wasteDrivers(sessions, report).slice(0, 7);
    var max = Math.max.apply(Math, rows.map(function (row) { return row.cost || row.tokens; }).concat([1]));
    if (!rows.length) {
      container.appendChild(el("p", { class: "muted" }, ["No review candidates in this filter."]));
      return;
    }
    rows.forEach(function (row) {
      var value = row.cost || row.tokens;
      var active = app.state.filters.wasteKind === row.kind;
      var item = el("button", {
        type: "button",
        class: "driver-row" + (active ? " active" : ""),
        style: "--bar:" + Math.max(3, value / max * 100).toFixed(1) + "%",
        "aria-pressed": active ? "true" : "false",
        "aria-label": (active ? "Clear review candidate " : "Filter to review candidate ") + row.kind.replace(/_/g, " ")
      }, [
        el("strong", { title: row.title }, [row.kind.replace(/_/g, " ")]),
        el("span", {}, [formatNumber(row.sessions)]),
        el("span", {}, [formatCost(row.cost)])
      ]);
      item.addEventListener("click", function () {
        if (app.state.filters.wasteKind === row.kind) {
          app.state.filters.wasteKind = "";
          if (app.state.filters.waste === "any") app.state.filters.waste = "all";
        } else {
          app.state.filters.waste = "any";
          app.state.filters.wasteKind = row.kind;
        }
        commitFilterChange();
      });
      container.appendChild(item);
    });
  }

  function renderCoverage(sessions) {
    var container = document.getElementById("coverage-chart");
    clear(container);
    var stats = coverageStats(sessions);
    var partialEnd = stats.full + stats.partial;
    var donutActive = app.state.filters.attributionCoverage === "full";
    var donut = el("button", { type: "button", class: "donut" + (donutActive ? " active" : ""), style: "--full:" + stats.full.toFixed(1) + "%; --partial:" + partialEnd.toFixed(1) + "%", "aria-pressed": donutActive ? "true" : "false", "aria-label": donutActive ? "Clear fully attributed sessions filter" : "Filter to fully attributed sessions" }, [
      el("span", {}, [formatPercent(stats.full) + "\nfull"])
    ]);
    donut.addEventListener("click", function () {
      app.state.filters.attributionCoverage = app.state.filters.attributionCoverage === "full" ? "" : "full";
      commitFilterChange();
    });
    container.appendChild(donut);
    container.appendChild(el("div", { class: "coverage-list" }, [
      coverageButton("Fully attributed", formatPercent(stats.full), "full"),
      coverageButton("Partial", formatPercent(stats.partial), "partial"),
      coverageButton("Unknown staff", formatPercent(stats.unknownStaff), "unknown-staff"),
      coverageButton("Unknown task", formatPercent(stats.unknownTask), "unknown-task")
    ]));
  }

  function coverageButton(label, value, coverageFilter) {
    var active = app.state.filters.attributionCoverage === coverageFilter;
    var button = el("button", { type: "button", class: active ? "active" : "", "aria-pressed": active ? "true" : "false", "aria-label": (active ? "Clear coverage bucket " : "Filter coverage bucket ") + label }, [el("span", {}, [label]), el("strong", {}, [value])]);
    button.addEventListener("click", function () {
      app.state.filters.attributionCoverage = app.state.filters.attributionCoverage === coverageFilter ? "" : coverageFilter;
      commitFilterChange();
    });
    return button;
  }

  function renderProjection(sessions, report) {
    var container = document.getElementById("cleanup-projection");
    clear(container);
    var reduction = Number(document.getElementById("reduction-select").value || 50);
    var drivers = wasteDrivers(sessions, report).slice(0, 5);
    var driverSessionIds = {};
    drivers.forEach(function (driver) {
      (driver.sessionIds || []).forEach(function (id) { driverSessionIds[id] = true; });
    });
    var selected = sessions.filter(function (session) { return driverSessionIds[session.session_id]; });
    var wasteCost = selected.reduce(function (sum, session) { return sum + cost(session); }, 0);
    var saved = wasteCost * reduction / 100;
    var totalCost = summarize(sessions, report).cost;
    container.appendChild(el("strong", {}, [formatCost(saved)]));
    container.appendChild(el("div", {}, [el("span", {}, ["Possible reduction"]), el("span", {}, [reduction + "% of unique top-driver sessions"])]));
    container.appendChild(el("div", {}, [el("span", {}, ["Remaining candidate cost"]), el("span", {}, [formatCost(Math.max(0, wasteCost - saved))])]));
    container.appendChild(el("div", {}, [el("span", {}, ["Unique sessions"]), el("span", {}, [formatNumber(selected.length)])]));
    container.appendChild(el("div", {}, [el("span", {}, ["Share of filtered cost"]), el("span", {}, [formatPercent(totalCost ? saved / totalCost * 100 : 0)])]));
    var active = app.state.filters.waste === "any" && !app.state.filters.wasteKind;
    var action = el("button", { type: "button", class: "projection-action" + (active ? " active" : ""), "aria-pressed": active ? "true" : "false" }, [active ? "Clear review candidates" : "Inspect review candidates"]);
    action.addEventListener("click", function () {
      if (app.state.filters.waste === "any" && !app.state.filters.wasteKind) app.state.filters.waste = "all";
      else {
        app.state.filters.waste = "any";
        app.state.filters.wasteKind = "";
      }
      commitFilterChange(true);
    });
    container.appendChild(action);
  }

  function renderChips(state) {
    var chips = document.getElementById("active-chips");
    clear(chips);
    var filter = state.filters;
    var entries = [];
    if (filter.preset !== "all") entries.push(["date", filter.preset, function () { filter.preset = "all"; }]);
    if (filter.search) entries.push(["search", filter.search, function () { filter.search = ""; }]);
    Object.keys(FIELD_IDS).forEach(function (key) {
      filter[key].forEach(function (value) {
        entries.push([key, value, function () { filter[key] = filter[key].filter(function (item) { return item !== value; }); }]);
      });
    });
    Array.prototype.slice.call(document.querySelectorAll(".panel-link")).forEach(function (link) {
      link.onclick = function (event) {
        var text = link.textContent.toLowerCase();
        if (text.indexOf("waste") >= 0 || text.indexOf("review") >= 0) {
          event.preventDefault();
          if (app.state.filters.waste === "any" && !app.state.filters.wasteKind) app.state.filters.waste = "all";
          else {
            app.state.filters.waste = "any";
            app.state.filters.wasteKind = "";
          }
          commitFilterChange(true);
        } else if (text.indexOf("unknown") >= 0) {
          event.preventDefault();
          app.state.filters.attributionCoverage = app.state.filters.attributionCoverage === "unknown" ? "" : "unknown";
          commitFilterChange(true);
        } else if (text.indexOf("projection") >= 0) {
          event.preventDefault();
          openInfo(document.querySelector("[data-info='projection']"));
        }
      };
    });
    if (filter.waste !== "all") entries.push(["waste", filter.waste, function () { filter.waste = "all"; }]);
    if (filter.wasteKind) entries.push(["driver", filter.wasteKind.replace(/_/g, " "), function () { filter.wasteKind = ""; }]);
    if (filter.outcomeBucket) entries.push(["outcome bucket", filter.outcomeBucket, function () { filter.outcomeBucket = ""; }]);
    if (filter.attributionCoverage) entries.push(["coverage", filter.attributionCoverage, function () { filter.attributionCoverage = ""; }]);
    if (filter.sessionIds && filter.sessionIds.length) entries.push(["flow selection", formatNumber(filter.sessionIds.length) + " sessions", function () { filter.sessionIds = []; }]);
    if (filter.weekdays && filter.weekdays.length) entries.push(["weekday", filter.weekdays.map(function (day) { return ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"][Number(day)] || day; }).join(", "), function () { filter.weekdays = []; }]);
    if (filter.minConfidence) entries.push(["confidence", filter.minConfidence + "%", function () { filter.minConfidence = 0; }]);
    if (filter.hourStart !== "" || filter.hourEnd !== "") entries.push(["time", (filter.hourStart || "0") + "-" + (filter.hourEnd || "23"), function () { filter.hourStart = ""; filter.hourEnd = ""; }]);
    if (filter.brushStartTime || filter.brushEndTime) entries.push(["time range", formatDate(filter.brushStartTime) + " - " + formatDate(filter.brushEndTime), function () { filter.brushStartTime = ""; filter.brushEndTime = ""; }]);
    var title = document.getElementById("active-title");
    if (title) title.textContent = "Active filters (" + entries.length + ")";
    if (!entries.length) {
      chips.appendChild(el("span", { class: "muted" }, ["None"]));
      return;
    }
    entries.forEach(function (entry) {
      var remove = el("button", { type: "button", "aria-label": "Remove filter " + entry[0] }, ["x"]);
      remove.addEventListener("click", function () {
        entry[2]();
        app.state.page = 1;
        syncControls(app.state, app.options);
        renderApp();
      });
      chips.appendChild(el("span", { class: "chip" }, [entry[0] + ": " + entry[1], remove]));
    });
  }

  function renderTable(sessions, state, report) {
    var table = document.getElementById("session-table");
    var thead = table.querySelector("thead");
    var tbody = table.querySelector("tbody");
    clear(thead);
    clear(tbody);
    var sortedAll = sortSessions(sessions, state.sort, report);
    renderSessionTitle(sessions.length);
    var maxPage = Math.max(1, Math.ceil(sessions.length / state.pageSize));
    state.page = Math.max(1, Math.min(state.page, maxPage));
    var startIndex = (state.page - 1) * state.pageSize;
    var endIndex = Math.min(sessions.length, startIndex + state.pageSize);
    var sorted = sortedAll.slice(startIndex, endIndex);
    setText("page-range", (sessions.length ? startIndex + 1 : 0) + "-" + endIndex + " of " + formatNumber(sessions.length));
    setText("current-page", String(state.page));
    var prev = document.getElementById("prev-page");
    var next = document.getElementById("next-page");
    if (prev) prev.disabled = state.page <= 1;
    if (next) next.disabled = state.page >= maxPage;
    var headerRow = el("tr");
    var pageIds = sorted.map(function (session) { return session.session_id; });
    var selectAll = el("input", { type: "checkbox", "aria-label": "Select all visible sessions", checked: pageIds.length > 0 && pageIds.every(function (id) { return state.selectedSessionIds.indexOf(id) >= 0; }) });
    selectAll.addEventListener("change", function () {
      if (selectAll.checked) {
        pageIds.forEach(function (id) {
          if (state.selectedSessionIds.indexOf(id) < 0) state.selectedSessionIds.push(id);
        });
      } else {
        state.selectedSessionIds = state.selectedSessionIds.filter(function (id) { return pageIds.indexOf(id) < 0; });
      }
      renderTable(sessions, state, report);
      toast(formatNumber(state.selectedSessionIds.length) + " sessions selected");
    });
    headerRow.appendChild(el("th", {}, [selectAll]));
    TABLE_COLUMNS.filter(function (column) { return state.visibleColumns.indexOf(column[0]) >= 0; }).forEach(function (column) {
      var button = el("button", { type: "button" }, [column[1] + (state.sort.key === column[0] ? (state.sort.dir === "asc" ? " up" : " down") : "")]);
      button.addEventListener("click", function () {
        if (state.sort.key === column[0]) state.sort.dir = state.sort.dir === "asc" ? "desc" : "asc";
        else state.sort = { key: column[0], dir: column[0] === "start_time" ? "desc" : "asc" };
        state.page = 1;
        renderApp();
      });
      headerRow.appendChild(el("th", { "aria-sort": state.sort.key === column[0] ? (state.sort.dir === "asc" ? "ascending" : "descending") : "none" }, [button]));
    });
    thead.appendChild(headerRow);
    if (state.drawerOpen && !state.selectedSessionId && sorted[0]) state.selectedSessionId = sorted[0].session_id;
    sorted.forEach(function (session) {
      var norm = normalizeSession(session, report);
      var row = el("tr", { tabindex: "0" });
      if (session.session_id === state.selectedSessionId) row.className = "selected";
      row.addEventListener("click", function () {
        state.selectedSessionId = session.session_id;
        state.drawerOpen = true;
        document.body.classList.remove("drawer-hidden");
        document.getElementById("evidence-drawer").classList.remove("drawer-closed");
        renderApp();
      });
      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          state.selectedSessionId = session.session_id;
          state.drawerOpen = true;
          document.body.classList.remove("drawer-hidden");
          document.getElementById("evidence-drawer").classList.remove("drawer-closed");
          renderApp();
        }
      });
      var values = {
        start_time: formatDate(norm.start_time),
        session_id: shortId(norm.session_id),
        client: norm.client,
        project: norm.project,
        staff: norm.staff,
        task: norm.task,
        model: norm.model,
        tokens: formatTokens(norm.tokens),
        cost: formatCost(norm.cost),
        outcome: norm.outcome,
        waste: norm.waste.replace(/_/g, " "),
        confidence: norm.confidence + "%"
      };
      TABLE_COLUMNS.filter(function (column) { return state.visibleColumns.indexOf(column[0]) >= 0; }).forEach(function (column) {
        var value = values[column[0]];
        var cell;
        if (column[0] === "outcome") {
          var activeOutcome = sameArrayValues(app.state.filters.outcomes, [value]);
          var pill = el("button", { type: "button", class: "outcome-pill outcome-" + outcomeClass(value) + (activeOutcome ? " active" : ""), "aria-pressed": activeOutcome ? "true" : "false", "aria-label": (activeOutcome ? "Clear outcome " : "Filter outcome ") + value }, [value]);
          pill.addEventListener("click", function (event) {
            event.stopPropagation();
            if (sameArrayValues(app.state.filters.outcomes, [value])) app.state.filters.outcomes = [];
            else {
              app.state.filters.outcomeBucket = "";
              app.state.filters.outcomes = [value];
            }
            commitFilterChange();
          });
          cell = el("td", {}, [pill]);
        } else if (column[0] === "confidence") {
          var confidence = el("button", { type: "button", class: "confidence-button", "data-info": "confidence", "aria-label": "About confidence " + value }, [String(value)]);
          confidence.addEventListener("click", function (event) {
            event.stopPropagation();
            openInfo(confidence);
          });
          cell = el("td", {}, [confidence]);
        } else {
          cell = el("td", { class: ["client", "project", "staff", "task", "model"].indexOf(column[0]) >= 0 ? "truncate" : "", title: String(value) }, [String(value)]);
        }
        row.appendChild(cell);
      });
      var checkbox = el("input", { type: "checkbox", "aria-label": "Select session " + shortId(norm.session_id), checked: state.selectedSessionIds.indexOf(session.session_id) >= 0 });
      checkbox.addEventListener("click", function (event) { event.stopPropagation(); });
      checkbox.addEventListener("change", function () {
        if (checkbox.checked && state.selectedSessionIds.indexOf(session.session_id) < 0) state.selectedSessionIds.push(session.session_id);
        if (!checkbox.checked) state.selectedSessionIds = state.selectedSessionIds.filter(function (id) { return id !== session.session_id; });
        toast(formatNumber(state.selectedSessionIds.length) + " sessions selected");
        renderTable(sessions, state, report);
      });
      row.insertBefore(el("td", {}, [checkbox]), row.firstChild);
      tbody.appendChild(row);
    });
  }

  function renderSessionTitle(count) {
    var title = document.getElementById("session-count");
    clear(title);
    title.appendChild(document.createTextNode("Sessions (" + formatNumber(count) + ") "));
    title.appendChild(el("button", { class: "info-button", type: "button", "data-info": "sessions", "aria-label": "About Sessions table" }, ["i"]));
  }

  function evidenceList(title, items) {
    items = (items || []).filter(Boolean).slice(0, 10);
    return el("section", { class: "evidence-box" }, [
      el("h3", {}, [title]),
      items.length ? el("ul", {}, items.map(function (item) { return el("li", {}, [String(item)]); })) : el("p", { class: "muted" }, ["None recorded"])
    ]);
  }

  function renderDrawer(sessions, state, report) {
    var container = document.getElementById("drawer-content");
    clear(container);
    if (!state.drawerOpen) {
      document.body.classList.add("drawer-hidden");
      document.getElementById("evidence-drawer").classList.add("drawer-closed");
      return;
    }
    var findingIndex = buildFindingIndex(report || {});
    var session = sessions.filter(function (item) { return item.session_id === state.selectedSessionId; })[0] || sessions[0];
    if (!session) {
      container.appendChild(el("p", { class: "muted" }, ["No matching sessions."]));
      return;
    }
    document.body.classList.remove("drawer-hidden");
    document.getElementById("evidence-drawer").classList.remove("drawer-closed");
    state.selectedSessionId = session.session_id;
    var findings = findingIndex[session.session_id] || [];
    var details = [
      ["Session ID", session.session_id || "unknown"],
      ["Start Time", formatDate(session.start_time)],
      ["Duration", session.end_time && session.start_time ? duration(session.start_time, session.end_time) : "unknown"],
      ["Client / Tool", attrLabel(session.client) + " (" + attrConfidence(session.client) + ")"],
      ["Project", sessionProject(session) + " (" + attrConfidence(session.project) + ")"],
      ["Staff", attrLabel(session.paperclip_staff)],
      ["Task", sessionTask(session)],
      ["Model", session.model || "unknown"]
    ];
    container.appendChild(el("div", { class: "detail-grid" }, details.map(function (row) {
      return el("div", { class: "detail-row" }, [el("span", {}, [row[0]]), el("span", {}, [row[1]])]);
    })));
    container.appendChild(el("div", { class: "impact-strip" }, [
      el("div", {}, [el("span", {}, [formatNumber(tokens(session)) + " tokens"]), el("span", {}, ["usage"])]),
      el("div", {}, [el("span", {}, [formatCost(cost(session))]), el("span", {}, ["est. cost"])])
    ]));
    container.appendChild(el("div", { class: "drawer-split" }, [
      el("div", {}, [el("span", {}, ["Outcome"]), el("strong", { class: "outcome-pill outcome-" + outcomeClass(attrLabel(session.outcome)) }, [attrLabel(session.outcome)])]),
      el("div", {}, [el("span", {}, ["Confidence"]), el("strong", {}, [sessionConfidence(session) + "%"])]),
      el("div", {}, [el("span", {}, ["Review Pattern"]), el("strong", {}, [wastePattern(session, findingIndex).replace(/_/g, " ")])])
    ]));
    container.appendChild(el("div", { class: "drawer-tabs", role: "tablist" }, [
      drawerTabButton("evidence", "Evidence"),
      drawerTabButton("commands", "Commands (" + (session.command_labels || []).length + ")"),
      drawerTabButton("linked", "Linked (" + findings.length + ")")
    ]));
    renderDrawerTabContent(container, session, findings);
  }

  function drawerTabButton(tab, label) {
    var button = el("button", { type: "button", class: app.state.drawerTab === tab ? "active" : "", role: "tab", "aria-selected": app.state.drawerTab === tab ? "true" : "false" }, [label]);
    button.addEventListener("click", function () {
      app.state.drawerTab = tab;
      renderApp();
    });
    return button;
  }

  function renderDrawerTabContent(container, session, findings) {
    if (app.state.drawerTab === "commands") {
      container.appendChild(evidenceList("Commands", session.command_labels || []));
      container.appendChild(evidenceList("Command Signatures", session.command_signatures || []));
      return;
    }
    if (app.state.drawerTab === "linked") {
      container.appendChild(evidenceList("Linked Sessions", findings.map(function (finding) {
        return (finding.kind || "waste") + ": " + (finding.title || "") + " (" + formatCost(finding.cost_usd || 0) + ")";
      })));
      return;
    }
    container.appendChild(el("section", { class: "evidence-actions" }, [
      evidenceAction("Edits", (session.file_edit_markers || 0) + " markers", function () { filterDurable("edits"); }),
      evidenceAction("Tests", (session.test_markers || 0) + " markers", function () { filterDurable("tests"); }),
      evidenceAction("Commits", commitSignal(session), function () { app.state.drawerTab = "commands"; renderApp(); }),
      evidenceAction("Pull Requests", prSignal(session), function () { app.state.drawerTab = "commands"; renderApp(); })
    ]));
    container.appendChild(evidenceList("Privacy-Safe Evidence", [].concat(
      (session.client && session.client.evidence) || [],
      (session.project && session.project.evidence) || [],
      (session.task && session.task.evidence) || [],
      (session.paperclip_staff && session.paperclip_staff.evidence) || [],
      (session.paperclip_task && session.paperclip_task.evidence) || []
    ).slice(0, 6)));
  }

  function evidenceAction(label, value, onClick) {
    var button = el("button", { class: "evidence-action", type: "button" }, [
      el("span", {}, [label]),
      el("strong", {}, [value]),
      el("span", { "aria-hidden": "true" }, [">"])
    ]);
    if (onClick) button.addEventListener("click", onClick);
    return button;
  }

  function filterDurable(kind) {
    app.state.filters.waste = kind === "edits" || kind === "tests" ? "useful-only" : app.state.filters.waste;
    app.state.page = 1;
    syncControls(app.state, app.options);
    renderApp();
  }

  function commitSignal(session) {
    var labels = (session.command_labels || []).join(" ").toLowerCase();
    if (labels.indexOf("git") >= 0 || labels.indexOf("commit") >= 0) return "signal seen";
    return "none";
  }

  function prSignal(session) {
    var labels = (session.command_labels || []).join(" ").toLowerCase();
    if (labels.indexOf("pr") >= 0 || labels.indexOf("pull") >= 0) return "signal seen";
    return "none";
  }

  function duration(start, end) {
    var ms = new Date(end).getTime() - new Date(start).getTime();
    if (!isFinite(ms) || ms < 0) return "unknown";
    var minutes = Math.round(ms / 60000);
    if (minutes < 60) return minutes + "m";
    return Math.floor(minutes / 60) + "h " + (minutes % 60) + "m";
  }

  function downloadText(filename, text, type) {
    var blob = new Blob([text], { type: type || "text/plain" });
    var url = URL.createObjectURL(blob);
    var link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function toast(message) {
    var node = document.getElementById("toast");
    node.textContent = message;
    node.classList.add("visible");
    setTimeout(function () { node.classList.remove("visible"); }, 1600);
  }

  var app = {
    report: null,
    state: createState(),
    options: null,
    filtered: [],
    resizeTimer: null
  };

  function renderApp() {
    if (!app.report) return;
    readControls(app.state);
    document.body.classList.toggle("comfortable", app.state.density === "comfortable");
    document.body.classList.toggle("compare-mode", app.state.compareMode);
    app.filtered = applyFilters(app.report.sessions || [], app.state.filters, app.report);
    var summary = summarize(app.filtered, app.report);
    var flowSessions = app.filtered;
    if (app.state.filters.sessionIds && app.state.filters.sessionIds.length) {
      var flowFilters = cloneFilters(app.state.filters);
      flowFilters.sessionIds = [];
      flowSessions = applyFilters(app.report.sessions || [], flowFilters, app.report);
    }
    renderKpis(summary);
    renderFlow(flowSessions, app.state);
    renderTimeline(app.filtered, app.report);
    renderCompanySpend(app.filtered, app.report, app.state);
    renderHeatmap(app.filtered);
    renderWasteDrivers(app.filtered, app.report);
    renderCoverage(app.filtered);
    renderProjection(app.filtered, app.report);
    renderChips(app.state);
    updateCardResetButtons();
    renderTable(app.filtered, app.state, app.report);
    renderDrawer(app.filtered, app.state, app.report);
    var query = encodeFilters(app.state);
    history.replaceState(null, "", query ? "?" + query : location.pathname);
  }

  function bindEvents() {
    ["filter-form", "quick-form"].forEach(function (id) {
      var form = document.getElementById(id);
      form.addEventListener("input", renderApp);
      form.addEventListener("change", renderApp);
      form.addEventListener("submit", function (event) { event.preventDefault(); });
    });
    document.getElementById("metric-toggle").addEventListener("change", renderApp);
    document.getElementById("timeline-metric").addEventListener("change", renderApp);
    document.getElementById("timeline-menu").addEventListener("click", toggleMoreMenu);
    document.getElementById("compare-mode").addEventListener("change", function () {
      app.state.compareMode = document.getElementById("compare-mode").checked;
      toast(app.state.compareMode ? "Compare mode enabled" : "Compare mode off");
      renderApp();
    });
    document.getElementById("density-select").addEventListener("change", renderApp);
    document.getElementById("reduction-select").addEventListener("change", renderApp);
    window.addEventListener("resize", function () {
      if (!app.report) return;
      clearTimeout(app.resizeTimer);
      app.resizeTimer = setTimeout(renderApp, 50);
    });
    Array.prototype.slice.call(document.querySelectorAll(".card-reset[data-reset-card]")).forEach(function (button) {
      button.addEventListener("click", function () {
        if (button.disabled) return;
        resetCardFilter(button.getAttribute("data-reset-card"));
      });
    });
    bindBrushEvents();
    document.getElementById("prev-page").addEventListener("click", function () {
      app.state.page = Math.max(1, app.state.page - 1);
      renderApp();
    });
    document.getElementById("next-page").addEventListener("click", function () {
      app.state.page += 1;
      renderApp();
    });
    document.getElementById("column-chooser").addEventListener("click", toggleColumnChooser);
    document.getElementById("more-menu").addEventListener("click", toggleMoreMenu);
    document.getElementById("open-json").addEventListener("click", function () { window.open("/api/report", "_blank"); });
    document.getElementById("copy-spec-link").addEventListener("click", function () {
      copyText("/Users/saphid/Documents/codex-usage-profiler/docs/dashboard-final-interaction-contract.md");
    });
    document.getElementById("reset-brush").addEventListener("click", function () {
      app.state.filters.brushStartTime = "";
      app.state.filters.brushEndTime = "";
      app.state.page = 1;
      renderApp();
    });
    document.getElementById("info-close").addEventListener("click", closeInfo);
    Array.prototype.slice.call(document.querySelectorAll(".legend span")).forEach(function (item) {
      item.setAttribute("role", "button");
      item.setAttribute("tabindex", "0");
      item.addEventListener("click", function () { toggleLegendOutcome(item); });
      item.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggleLegendOutcome(item);
        }
      });
    });
    document.addEventListener("click", function (event) {
      if (event.target.closest(".info-button") || event.target.closest(".source-button")) {
        openInfo(event.target.closest(".info-button") || event.target.closest(".source-button"));
        return;
      }
      if (!event.target.closest("#info-popover")) closeInfo();
      if (!event.target.closest("#more-menu") && !event.target.closest("#more-popover")) {
        document.getElementById("more-popover").hidden = true;
        document.getElementById("more-menu").setAttribute("aria-expanded", "false");
      }
      if (!event.target.closest("#column-chooser") && !event.target.closest("#column-popover")) {
        document.getElementById("column-popover").hidden = true;
        document.getElementById("column-chooser").setAttribute("aria-expanded", "false");
      }
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        closeInfo();
        document.getElementById("more-popover").hidden = true;
        document.getElementById("column-popover").hidden = true;
        document.getElementById("more-menu").setAttribute("aria-expanded", "false");
        document.getElementById("column-chooser").setAttribute("aria-expanded", "false");
      }
    });
    Array.prototype.slice.call(document.querySelectorAll(".time-button")).forEach(function (button) {
      button.addEventListener("click", function () {
        var preset = button.getAttribute("data-time-preset");
        if (preset === "day") {
          document.getElementById("hour-start").value = "6";
          document.getElementById("hour-end").value = "17";
        } else if (preset === "night") {
          document.getElementById("hour-start").value = "18";
          document.getElementById("hour-end").value = "5";
        } else {
          document.getElementById("hour-start").value = "";
          document.getElementById("hour-end").value = "";
        }
        renderApp();
      });
    });
    document.getElementById("reset-filters").addEventListener("click", function () {
      app.state = createState();
      syncControls(app.state, app.options);
      renderApp();
    });
    document.getElementById("clear-active").addEventListener("click", function () {
      app.state = createState();
      syncControls(app.state, app.options);
      renderApp();
    });
    document.getElementById("hide-filters").addEventListener("click", function () {
      document.body.classList.add("filters-hidden");
      renderApp();
    });
    document.getElementById("show-filters").addEventListener("click", function () {
      document.body.classList.remove("filters-hidden");
      renderApp();
    });
    document.getElementById("export-csv").addEventListener("click", function () {
      downloadText("codex-usage-filtered-sessions.csv", toCsv(app.filtered, app.report), "text/csv");
      toast("CSV exported");
    });
    document.getElementById("copy-link").addEventListener("click", function () {
      var url = location.origin + location.pathname + "?" + encodeFilters(app.state);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(url).then(function () { toast("Permalink copied"); }, function () { toast(url); });
      } else {
        toast(url);
      }
    });
    document.getElementById("close-drawer").addEventListener("click", function () {
      app.state.drawerOpen = false;
      document.getElementById("evidence-drawer").classList.add("drawer-closed");
      document.body.classList.add("drawer-hidden");
      renderApp();
    });
  }

  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () { toast("Copied"); }, function () { toast(text); });
    } else {
      toast(text);
    }
  }

  function openInfo(button) {
    var key = button.getAttribute("data-info") || "";
    var popover = document.getElementById("info-popover");
    setText("info-title", button.getAttribute("aria-label") || "Details");
    setText("info-body", INFO_CONTENT[key] || "No details are available yet.");
    button.setAttribute("aria-expanded", "true");
    popover.hidden = false;
    var rect = button.getBoundingClientRect();
    popover.style.left = Math.min(window.innerWidth - 330, Math.max(12, rect.left - 120)) + "px";
    popover.style.top = Math.min(window.innerHeight - 170, rect.bottom + 8) + "px";
  }

  function closeInfo() {
    var popover = document.getElementById("info-popover");
    if (popover) popover.hidden = true;
    Array.prototype.slice.call(document.querySelectorAll(".info-button[aria-expanded='true'], .source-button[aria-expanded='true']")).forEach(function (button) {
      button.setAttribute("aria-expanded", "false");
    });
  }

  function toggleMoreMenu(event) {
    event.stopPropagation();
    var menu = document.getElementById("more-popover");
    menu.hidden = !menu.hidden;
    event.currentTarget.setAttribute("aria-expanded", menu.hidden ? "false" : "true");
    var rect = event.currentTarget.getBoundingClientRect();
    menu.style.left = Math.max(12, rect.right - 190) + "px";
    menu.style.top = rect.bottom + 8 + "px";
  }

  function toggleColumnChooser(event) {
    event.stopPropagation();
    var popover = document.getElementById("column-popover");
    if (popover.hidden) renderColumnChooser();
    popover.hidden = !popover.hidden;
    event.currentTarget.setAttribute("aria-expanded", popover.hidden ? "false" : "true");
    var rect = event.currentTarget.getBoundingClientRect();
    popover.style.left = Math.max(12, rect.left - 40) + "px";
    popover.style.top = rect.bottom + 8 + "px";
  }

  function renderColumnChooser() {
    var popover = document.getElementById("column-popover");
    clear(popover);
    TABLE_COLUMNS.forEach(function (column) {
      var id = "col-" + column[0];
      var input = el("input", { id: id, type: "checkbox", checked: app.state.visibleColumns.indexOf(column[0]) >= 0 });
      input.addEventListener("change", function () {
        if (input.checked && app.state.visibleColumns.indexOf(column[0]) < 0) app.state.visibleColumns.push(column[0]);
        if (!input.checked && app.state.visibleColumns.length > 3) app.state.visibleColumns = app.state.visibleColumns.filter(function (item) { return item !== column[0]; });
        renderApp();
        renderColumnChooser();
      });
      popover.appendChild(el("label", {}, [input, column[1]]));
    });
  }

  function bindBrushEvents() {
    var brush = document.getElementById("brush-selection");
    var mini = document.getElementById("mini-brush");
    if (!brush || !mini) return;
    var drag = null;
    function fractionsFromState() {
      var extent = visibleBrushExtent(app.report, []);
      if (!extent || extent.max <= extent.min) return { start: 0, end: 1 };
      var start = app.state.filters.brushStartTime ? new Date(app.state.filters.brushStartTime).getTime() : extent.min;
      var end = app.state.filters.brushEndTime ? new Date(app.state.filters.brushEndTime).getTime() : extent.max;
      return { start: (start - extent.min) / (extent.max - extent.min), end: (end - extent.min) / (extent.max - extent.min) };
    }
    function pointerFraction(event) {
      var rect = mini.getBoundingClientRect();
      return Math.max(0, Math.min(1, (event.clientX - rect.left) / Math.max(1, rect.width)));
    }
    function startBrushDrag(event) {
      event.preventDefault();
      var current = fractionsFromState();
      var at = pointerFraction(event);
      var mode = "move";
      if (event.target.classList && event.target.classList.contains("brush-handle-left")) mode = "start";
      else if (event.target.classList && event.target.classList.contains("brush-handle-right")) mode = "end";
      else if (Math.abs(at - current.start) < 0.05) mode = "start";
      else if (Math.abs(at - current.end) < 0.05) mode = "end";
      else if (current.end - current.start > 0.98) {
        var defaultSpan = 0.25;
        current.start = Math.max(0, Math.min(1 - defaultSpan, at - defaultSpan / 2));
        current.end = current.start + defaultSpan;
      }
      else if (at < current.start || at > current.end) {
        var span = Math.max(0.08, current.end - current.start);
        current.start = Math.max(0, Math.min(1 - span, at - span / 2));
        current.end = current.start + span;
        setBrushFromFractions(current.start, current.end);
        return;
      }
      drag = { mode: mode, start: current.start, end: current.end, origin: at, target: event.currentTarget };
      try { event.currentTarget.setPointerCapture(event.pointerId); } catch (_) {}
    }
    function moveBrush(event) {
      if (!drag) return;
      var at = pointerFraction(event);
      var delta = at - drag.origin;
      var start = drag.start;
      var end = drag.end;
      if (drag.mode === "start") start = Math.min(end - 0.01, Math.max(0, at));
      else if (drag.mode === "end") end = Math.max(start + 0.01, Math.min(1, at));
      else {
        var span = end - start;
        start = Math.max(0, Math.min(1 - span, drag.start + delta));
        end = start + span;
      }
      brush.style.left = (start * 100).toFixed(2) + "%";
      brush.style.right = ((1 - end) * 100).toFixed(2) + "%";
    }
    function endBrush(event) {
      if (!drag) return;
      var left = parseFloat(brush.style.left || "0") / 100;
      var right = 1 - parseFloat(brush.style.right || "0") / 100;
      var target = drag.target;
      drag = null;
      try { target.releasePointerCapture(event.pointerId); } catch (_) {}
      setBrushFromFractions(left, right);
    }
    mini.addEventListener("pointerdown", startBrushDrag);
    mini.addEventListener("pointermove", moveBrush);
    mini.addEventListener("pointerup", endBrush);
    brush.addEventListener("pointerdown", startBrushDrag);
    brush.addEventListener("pointermove", moveBrush);
    brush.addEventListener("pointerup", endBrush);
    brush.addEventListener("keydown", function (event) {
      var current = fractionsFromState();
      var span = current.end - current.start;
      if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        var step = event.shiftKey ? 0.05 : 0.01;
        var dir = event.key === "ArrowLeft" ? -step : step;
        var start = Math.max(0, Math.min(1 - span, current.start + dir));
        setBrushFromFractions(start, start + span);
      }
      if (event.key === "Home") {
        event.preventDefault();
        setBrushFromFractions(0, span);
      }
      if (event.key === "End") {
        event.preventDefault();
        setBrushFromFractions(1 - span, 1);
      }
      if (event.key === "Escape") {
        event.preventDefault();
        app.state.filters.brushStartTime = "";
        app.state.filters.brushEndTime = "";
        app.state.page = 1;
        syncControls(app.state, app.options);
        renderApp();
      }
    });
  }

  function init() {
    app.state = decodeFilters(location.search);
    fetch("/api/report", { cache: "no-store" })
      .then(function (response) {
        if (!response.ok) throw new Error("Report fetch failed: " + response.status);
        return response.json();
      })
      .then(function (report) {
        app.report = report;
        app.options = buildOptions(report);
        syncControls(app.state, app.options);
        bindEvents();
        var telemetry = report.telemetry || {};
        var live = liveQuotaPercent(report);
        setText("source-status", telemetry.available ? "Source: CodexBar/local" : "Source: local report");
        setText("live-status", live == null ? "No live quota" : "Live quota " + formatPercent(live));
        renderApp();
      })
      .catch(function (error) {
        setText("source-status", error.message);
      });
  }

  root.CUPDashboard = {
    createState: createState,
    attrLabel: attrLabel,
    buildFindingIndex: buildFindingIndex,
    wastePattern: wastePattern,
    attributionCoverageBucket: attributionCoverageBucket,
    outcomeBucket: outcomeBucket,
    buildFlowModel: buildFlowModel,
    layoutFlowModel: layoutFlowModel,
    buildOptions: buildOptions,
    applyFilters: applyFilters,
    summarize: summarize,
    groupBy: groupBy,
    wasteDrivers: wasteDrivers,
    coverageStats: coverageStats,
    hourlyBuckets: hourlyBuckets,
    companySpendModel: companySpendModel,
    timeExtent: timeExtent,
    sortSessions: sortSessions,
    normalizeSession: normalizeSession,
    toCsv: toCsv,
    encodeFilters: encodeFilters,
    decodeFilters: decodeFilters,
    formatTokens: formatTokens,
    formatCost: formatCost
  };

  if (typeof module !== "undefined" && module.exports) {
    module.exports = root.CUPDashboard;
  }

  if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", init);
  }
})(typeof window !== "undefined" ? window : globalThis);
