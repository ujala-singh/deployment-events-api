"use strict";

const STATUSES = ["success", "failed", "in_progress", "cancelled", "rolled_back"];
const app = document.getElementById("app");

// Distinct service names, fetched once and reused to populate the filter.
let serviceCache = null;

// ---- API helpers -----------------------------------------------------------

async function api(path) {
  const resp = await fetch(path, { headers: { Accept: "application/json" } });
  const body = await resp.json().catch(() => null);
  if (!resp.ok) {
    const message = body?.error?.message || `Request failed (${resp.status})`;
    throw Object.assign(new Error(message), { status: resp.status });
  }
  return body;
}

async function getServices() {
  if (serviceCache) return serviceCache;
  const { data } = await api("/deployments");
  serviceCache = [...new Set(data.map((d) => d.service))].sort();
  return serviceCache;
}

// ---- Formatting ------------------------------------------------------------

function fmtDuration(seconds) {
  if (!seconds) return "—";
  if (seconds < 60) return `${seconds}s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s ? `${m}m ${s}s` : `${m}m`;
}

function fmtTimestamp(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

function statusBadge(status) {
  return `<span class="badge" data-status="${status}">${status.replace("_", " ")}</span>`;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );
}

// ---- Hash routing ----------------------------------------------------------
// #/d/<id>                       -> detail view
// #/?service=x&status=y  (or #/) -> list view with optional filters

function parseHash() {
  const hash = location.hash.replace(/^#\/?/, ""); // strip "#/" or "#"
  if (hash.startsWith("d/")) {
    return { view: "detail", id: decodeURIComponent(hash.slice(2)) };
  }
  const params = new URLSearchParams(hash.startsWith("?") ? hash.slice(1) : "");
  return {
    view: "list",
    service: params.get("service") || "",
    status: params.get("status") || "",
  };
}

function listHash(service, status) {
  const params = new URLSearchParams();
  if (service) params.set("service", service);
  if (status) params.set("status", status);
  const qs = params.toString();
  return qs ? `#/?${qs}` : "#/";
}

// ---- Views -----------------------------------------------------------------

async function renderList({ service, status }) {
  app.innerHTML = `<p class="loading">Loading…</p>`;

  const query = new URLSearchParams();
  if (service) query.set("service", service);
  if (status) query.set("status", status);

  let result, services;
  try {
    [result, services] = await Promise.all([
      api(`/deployments${query.toString() ? `?${query}` : ""}`),
      getServices(),
    ]);
  } catch (err) {
    app.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
    return;
  }

  const serviceOptions = services
    .map((s) => `<option value="${s}" ${s === service ? "selected" : ""}>${s}</option>`)
    .join("");
  const statusOptions = STATUSES.map(
    (s) => `<option value="${s}" ${s === status ? "selected" : ""}>${s.replace("_", " ")}</option>`
  ).join("");

  const rows = result.data
    .map(
      (d) => `
      <tr>
        <td><a class="id-link" href="#/d/${encodeURIComponent(d.id)}">${escapeHtml(d.id)}</a></td>
        <td>${escapeHtml(d.service)}</td>
        <td>${statusBadge(d.status)}</td>
        <td class="num">${fmtDuration(d.duration)}</td>
        <td>${fmtTimestamp(d.timestamp)}</td>
        <td><span class="commit">${escapeHtml(d.commit_sha)}</span></td>
      </tr>`
    )
    .join("");

  app.innerHTML = `
    <div class="filters">
      <label>Service
        <select id="f-service"><option value="">All services</option>${serviceOptions}</select>
      </label>
      <label>Status
        <select id="f-status"><option value="">All statuses</option>${statusOptions}</select>
      </label>
      <span class="count">${result.count} deployment${result.count === 1 ? "" : "s"}</span>
    </div>
    ${
      result.count === 0
        ? `<p class="empty">No deployments match these filters.</p>`
        : `<table>
            <thead>
              <tr><th>ID</th><th>Service</th><th>Status</th><th>Duration</th><th>Timestamp</th><th>Commit</th></tr>
            </thead>
            <tbody>${rows}</tbody>
          </table>`
    }`;

  const onChange = () => {
    const s = document.getElementById("f-service").value;
    const st = document.getElementById("f-status").value;
    location.hash = listHash(s, st);
  };
  document.getElementById("f-service").addEventListener("change", onChange);
  document.getElementById("f-status").addEventListener("change", onChange);
}

async function renderDetail(id) {
  app.innerHTML = `<p class="loading">Loading…</p>`;
  let d;
  try {
    d = await api(`/deployments/${encodeURIComponent(id)}`);
  } catch (err) {
    const note =
      err.status === 404
        ? `Deployment <code>${escapeHtml(id)}</code> was not found.`
        : escapeHtml(err.message);
    app.innerHTML = `<a class="back" href="#/">← Back to deployments</a><p class="error">${note}</p>`;
    return;
  }

  app.innerHTML = `
    <a class="back" href="#/">← Back to deployments</a>
    <div class="detail-card">
      <h2>${escapeHtml(d.id)}</h2>
      <dl class="detail-grid">
        <dt>Service</dt><dd>${escapeHtml(d.service)}</dd>
        <dt>Status</dt><dd>${statusBadge(d.status)}</dd>
        <dt>Duration</dt><dd>${fmtDuration(d.duration)}</dd>
        <dt>Timestamp</dt><dd>${fmtTimestamp(d.timestamp)}</dd>
        <dt>Commit</dt><dd class="mono">${escapeHtml(d.commit_sha)}</dd>
      </dl>
    </div>`;
}

// ---- Compare view (path-routed at /d/compare) ------------------------------

function verdictBadge(verdict) {
  return `<span class="verdict" data-verdict="${verdict}">${verdict.replace("_", " ")}</span>`;
}

function signed(value, unit = "") {
  if (value === null || value === undefined) return "—";
  return `${value > 0 ? "+" : ""}${value}${unit}`;
}

function deploymentMini(d) {
  return `
    <dl class="detail-grid">
      <dt>ID</dt><dd class="mono">${escapeHtml(d.id)}</dd>
      <dt>Service</dt><dd>${escapeHtml(d.service)}</dd>
      <dt>Status</dt><dd>${statusBadge(d.status)}</dd>
      <dt>Duration</dt><dd>${fmtDuration(d.duration)}</dd>
      <dt>Commit</dt><dd class="mono">${escapeHtml(d.commit_sha)}</dd>
    </dl>`;
}

function renderComparison(r) {
  const { changes: c, performance: p, service_patterns: sp } = r;
  const st = c.status_transition;
  return `
    <div class="compare-grid">
      <div class="detail-card"><h3>Base (from)</h3>${deploymentMini(r.base)}</div>
      <div class="detail-card"><h3>Target (to)</h3>${deploymentMini(r.target)}</div>
    </div>
    <div class="detail-card">
      <h3>Performance</h3>
      <p>${verdictBadge(p.verdict)} ${escapeHtml(p.reason)}</p>
      <dl class="detail-grid">
        <dt>Duration Δ</dt><dd>${p.duration_delta === null ? "—" : signed(p.duration_delta, "s")}</dd>
        <dt>% change</dt><dd>${p.pct_change === null ? "—" : `${signed(p.pct_change, "%")}`}</dd>
      </dl>
    </div>
    <div class="detail-card">
      <h3>What changed</h3>
      <dl class="detail-grid">
        <dt>Status</dt><dd>${statusBadge(st.from)} → ${statusBadge(st.to)}</dd>
        <dt>Duration Δ</dt><dd>${signed(c.duration_delta, "s")}</dd>
        <dt>Commit</dt><dd>${c.commit_changed ? "changed" : "unchanged"}</dd>
        <dt>Fields</dt><dd>${c.changed_fields.length ? c.changed_fields.map(escapeHtml).join(", ") : "none"}</dd>
      </dl>
    </div>
    <div class="detail-card">
      <h3>Service patterns <span class="muted-note">— between base &amp; target</span></h3>
      <dl class="detail-grid">
        <dt>Deployments</dt><dd>${sp.total_deployments}</dd>
        <dt>Bad release rate</dt><dd>${sp.bad_release_rate_pct}%</dd>
        <dt>Deploy frequency</dt><dd>${sp.deployment_frequency_pct}%</dd>
      </dl>
    </div>`;
}

async function renderCompare() {
  app.innerHTML = `<p class="loading">Loading…</p>`;

  const params = new URLSearchParams(location.search);
  const preFrom = params.get("from") || "";
  const preTo = params.get("to") || "";

  let deployments;
  try {
    ({ data: deployments } = await api("/deployments"));
  } catch (err) {
    app.innerHTML = `<a class="back" href="/">← Back</a><p class="error">${escapeHtml(err.message)}</p>`;
    return;
  }

  const options = (selected) =>
    deployments
      .map(
        (d) =>
          `<option value="${escapeHtml(d.id)}" ${d.id === selected ? "selected" : ""}>` +
          `${escapeHtml(d.id)} · ${escapeHtml(d.service)} · ${d.status}</option>`
      )
      .join("");

  app.innerHTML = `
    <a class="back" href="/">← Back to deployments</a>
    <div class="compare-form">
      <label>Base (from)
        <select id="c-from"><option value="">Select…</option>${options(preFrom)}</select>
      </label>
      <label>Target (to)
        <select id="c-to"><option value="">Select…</option>${options(preTo)}</select>
      </label>
      <button id="c-run" type="button" class="btn">Compare</button>
    </div>
    <div id="compare-result"></div>`;

  const out = document.getElementById("compare-result");

  const run = async () => {
    const from = document.getElementById("c-from").value;
    const to = document.getElementById("c-to").value;
    if (!from || !to) {
      out.innerHTML = `<p class="empty">Pick two deployments to compare.</p>`;
      return;
    }
    // Keep the URL shareable without triggering a re-render.
    history.replaceState(
      null,
      "",
      `/d/compare?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
    );
    out.innerHTML = `<p class="loading">Comparing…</p>`;
    try {
      const result = await api(
        `/compare?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`
      );
      out.innerHTML = renderComparison(result);
    } catch (err) {
      out.innerHTML = `<p class="error">${escapeHtml(err.message)}</p>`;
    }
  };

  document.getElementById("c-run").addEventListener("click", run);
  if (preFrom && preTo) run(); // auto-run a deep link
}

// ---- Bootstrap -------------------------------------------------------------

function route() {
  if (location.pathname === "/d/compare") {
    renderCompare();
    return;
  }
  const r = parseHash();
  if (r.view === "detail") renderDetail(r.id);
  else renderList(r);
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);
route();
