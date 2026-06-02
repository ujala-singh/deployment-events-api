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

// ---- Bootstrap -------------------------------------------------------------

function route() {
  const r = parseHash();
  if (r.view === "detail") renderDetail(r.id);
  else renderList(r);
}

window.addEventListener("hashchange", route);
window.addEventListener("DOMContentLoaded", route);
route();
