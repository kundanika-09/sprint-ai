const $ = s => document.querySelector(s);
const PAGE = document.body.dataset.page;
const PL = {1: 'Highest', 2: 'High', 3: 'Medium', 4: 'Low'};
let SPRINT = null, charts = {};
const api = async (u, o = {}) => {
  const r = await fetch(u, {headers: {'Content-Type': 'application/json'}, ...o});
  const d = await r.json(); if (!r.ok) throw new Error(d.error || 'Request failed'); return d;
};
const post = (u, b) => api(u, {method: 'POST', body: JSON.stringify(b)});
const toast = m => { $('#toastMsg').textContent = m; bootstrap.Toast.getOrCreateInstance($('#toast')).show(); };
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]));
const badge = r => `<span class="pill ${r === 'High' ? 'bg-danger-subtle text-danger' : r === 'Medium' ? 'bg-warning-subtle text-warning-emphasis' : 'bg-success-subtle text-success'}">${r}</span>`;
const prio = p => `<span class="pill p${p}">${PL[p] || p}</span>`;
function chart(id, cfg) { if (charts[id]) charts[id].destroy(); charts[id] = new Chart($('#' + id), cfg); }
const COL = {navy: '#0b2545', blue: '#1d5fd1', light: '#8fb4f0', green: '#2e9d5b', amber: '#e0a21b', red: '#d64545', gray: '#aab4c5'};
const opt = {responsive: true, maintainAspectRatio: false, plugins: {legend: {position: 'bottom'}}};

async function initSprints() {
  const d = await api('/api/sprints'), sel = $('#sprintSelect');
  sel.innerHTML = d.sprints.map(s => `<option value="${s}">Sprint ${s}${s === d.active ? ' (active)' : ''}</option>`).join('');
  const saved = localStorage.getItem('sprint');
  SPRINT = saved && d.sprints.includes(+saved) ? saved : d.active;
  sel.value = SPRINT;
  sel.onchange = () => { SPRINT = sel.value; localStorage.setItem('sprint', SPRINT); load(); };
}

/* ---------------- Dashboard ---------------- */
async function dashboard() {
  const k = await api('/api/kpis?sprint=' + SPRINT);
  const cards = [
    ['Total Stories', k.total_stories, ''], ['Active Sprint', 'Sprint ' + k.sprint, ''],
    ['Avg Story Points', k.avg_points, ''], ['Sprint Health', k.health + '%', k.health >= 65 ? 'green' : k.health >= 40 ? 'amber' : 'red'],
    ['High Risk Stories', k.high_risk, k.high_risk ? 'red' : 'green'], ['Team Velocity', k.velocity + ' pts', '']];
  $('#kpis').innerHTML = cards.map(c => `<div class="col-6 col-md-4 col-xl-2"><div class="kpi ${c[2]}"><div class="lbl">${c[0]}</div><div class="val">${c[1]}</div></div></div>`).join('');
  chart('riskChart', {type: 'doughnut', data: {labels: ['Low', 'Medium', 'High'], datasets: [{data: [k.risk.Low, k.risk.Medium, k.risk.High], backgroundColor: [COL.green, COL.amber, COL.red]}]}, options: opt});
  chart('stageChart', {type: 'bar', data: {labels: Object.keys(k.points_by_column), datasets: [{label: 'Story points', data: Object.values(k.points_by_column), backgroundColor: COL.blue}]}, options: {...opt, plugins: {legend: {display: false}}}});
  $('#riskTable').innerHTML = k.high_risk_stories.map(s => `<tr><td>${esc(s.story_key)}</td><td>${esc(s.title)}</td><td>${prio(s.priority)}</td><td>${s.points}</td><td>${s.blocked}</td><td>${s.column_name}</td></tr>`).join('') || '<tr><td colspan="6" class="text-muted">No high-risk stories in this sprint.</td></tr>';
}

/* ---------------- Board ---------------- */
async function board() {
  const d = await api('/api/stories?sprint=' + SPRINT);
  $('#board').innerHTML = d.columns.map(c => {
    const items = d.stories.filter(s => s.column_name === c);
    return `<div class="lane" data-col="${c}"><div class="lane-h">${c}<span>${items.length}</span></div>${items.map(card).join('')}</div>`;
  }).join('');
  document.querySelectorAll('.card-s').forEach(el => {
    el.ondragstart = e => { e.dataTransfer.setData('id', el.dataset.id); el.classList.add('dragging'); };
    el.ondragend = () => el.classList.remove('dragging');
  });
  document.querySelectorAll('.lane').forEach(l => {
    l.ondragover = e => { e.preventDefault(); l.classList.add('over'); };
    l.ondragleave = () => l.classList.remove('over');
    l.ondrop = async e => {
      e.preventDefault(); l.classList.remove('over');
      const id = e.dataTransfer.getData('id');
      await api('/api/stories/' + id, {method: 'PATCH', body: JSON.stringify({column_name: l.dataset.col})});
      toast('Moved to ' + l.dataset.col); board();
    };
  });
}
const card = s => `<div class="card-s" draggable="true" data-id="${s.id}" title="${esc(s.story_key)}">
  <div class="t">${esc(s.title)}</div>
  <div class="m">${prio(s.priority)}<span class="dot ${s.risk}" title="${s.risk} risk"></span><span>${s.risk}</span>
  <span class="pts ${s.points_source === 'dataset' ? '' : 'pred'}" title="${s.points_source === 'dataset' ? 'From dataset' : 'ML-estimated'}">${s.points}</span></div></div>`;
function boardInit() {
  const body = () => ({title: $('#nsTitle').value, description: $('#nsDesc').value, priority: $('#nsPrio').value, issue_type: $('#nsType').value});
  $('#nsPredict').onclick = async () => {
    try { const r = await post('/api/predict/story-points', body());
      $('#nsPts').value = r.story_points; $('#nsPred').textContent = `Estimated ${r.story_points} pts (confidence ${r.confidence}%)`; }
    catch (e) { toast(e.message); }
  };
  $('#nsSave').onclick = async () => {
    try { const r = await post('/api/stories', {...body(), points: $('#nsPts').value, sprint: SPRINT, column_name: 'Product Backlog'});
      bootstrap.Modal.getInstance($('#storyModal')).hide(); toast(`Story created: ${r.points} pts, ${r.risk} risk`); board(); }
    catch (e) { toast(e.message); }
  };
}

/* ---------------- Analytics ---------------- */
async function analytics() {
  const a = await api('/api/analytics'), s = a.sprints, lbl = s.map(x => x.sprint);
  chart('c1', {type: 'bar', data: {labels: Object.keys(a.distribution).map(x => x + ' pts'), datasets: [{label: 'Stories', data: Object.values(a.distribution), backgroundColor: COL.blue}]}, options: {...opt, plugins: {legend: {display: false}}}});
  chart('c2', {type: 'line', data: {labels: lbl, datasets: [
    {label: 'Completed points', data: s.map(x => x.completed_points), borderColor: COL.blue, backgroundColor: '#1d5fd122', fill: true, tension: .3},
    {label: 'Rolling velocity', data: s.map(x => x.team_velocity), borderColor: COL.amber, borderDash: [5, 4], tension: .3, pointRadius: 0}]}, options: opt});
  chart('c3', {type: 'doughnut', data: {labels: ['Low', 'Medium', 'High'], datasets: [{data: [a.risk.Low || 0, a.risk.Medium || 0, a.risk.High || 0], backgroundColor: [COL.green, COL.amber, COL.red]}]}, options: opt});
  chart('c4', {type: 'bar', data: {labels: lbl, datasets: [{label: 'Success probability %', data: s.map(x => x.success_prob), backgroundColor: s.map(x => x.success_prob >= 50 ? COL.green : COL.red)}]}, options: {...opt, plugins: {legend: {display: false}}, scales: {y: {max: 100, beginAtZero: true}}}});
  chart('c5', {type: 'bar', data: {labels: a.team.map(t => t.assignee), datasets: [
    {label: 'Stories', data: a.team.map(t => t.stories), backgroundColor: COL.light}, {label: 'Completed points', data: a.team.map(t => t.done_points), backgroundColor: COL.navy}]}, options: opt});
}

/* ---------------- AI Insights ---------------- */
const num = id => +$(id).value;
async function recs() {
  const cap = $('#capIn').value, k = await api(`/api/recommendations?sprint=${SPRINT}${cap ? '&capacity=' + cap : ''}`);
  if (!$('#capIn').value) $('#capIn').value = k.capacity;
  $('#recOut').innerHTML = `<div class="small text-muted mb-2">Sprint ${k.sprint}: ${k.open_stories} open stories &middot; committed ${k.committed} / capacity ${k.capacity} pts</div>` +
    (k.recommendations.map(r => `<div class="rec ${r.severity}"><i class="bi bi-check2-circle"></i><div>${esc(r.action)}<small>${esc(r.key)} &middot; ${esc(r.reason)}</small></div></div>`).join('')
    || '<div class="text-muted">No changes recommended - sprint plan looks balanced.</div>');
}
async function insights() {
  recs();
  const m = await api('/api/meta'), sp = m.story_point_metrics, ss = m.sprint_success_metrics, rk = m.risk_metrics;
  $('#mlTable').innerHTML = `<thead><tr><th>Model</th><th>Algorithm</th><th>Key metrics (hold-out)</th></tr></thead><tbody>
   <tr><td>Story Points</td><td>Random Forest Regressor + TF-IDF</td><td>MAE ${sp.MAE} (median baseline ${sp.baseline_MAE_median}) &middot; 5-fold CV MAE ${sp.CV_MAE_5fold} &middot; R&sup2; ${sp.R2} &middot; n=${sp.train_size + sp.test_size}</td></tr>
   <tr><td>Sprint Success</td><td>Random Forest Classifier</td><td>Accuracy ${ss.accuracy} &middot; F1 ${ss.f1} &middot; ${ss.sprints} sprints</td></tr>
   <tr><td>Risk Detection</td><td>Decision Tree Classifier</td><td>Accuracy ${rk.accuracy} &middot; macro-F1 ${rk.f1_macro}</td></tr></tbody>`;
  $('#mlNote').textContent = 'Small dataset (75 unique issues, 61 sprints): estimates are indicative. Sprint-success and risk labels are derived from documented rules because the dataset has no ground-truth columns for them.';
  $('#capIn').onchange = recs;
  $('#spBtn').onclick = async () => {
    try { const r = await post('/api/predict/story-points', {title: $('#spTitle').value, description: $('#spDesc').value, priority: $('#spPrio').value, issue_type: $('#spType').value});
      $('#spOut').innerHTML = `<div class="res-box"><div class="small text-muted">Predicted Story Points</div><div class="big">${r.story_points}</div>
        <div class="progress mt-2" style="height:6px"><div class="progress-bar" style="width:${r.confidence}%"></div></div><div class="small mt-1">Estimation confidence ${r.confidence}% &middot; raw estimate ${r.raw_estimate}</div></div>`; }
    catch (e) { toast(e.message); }
  };
  $('#ssLoad').onclick = async () => { const k = await api('/api/kpis?sprint=' + SPRINT), rows = (await api('/api/stories?sprint=' + SPRINT)).stories;
    $('#ss1').value = k.total_stories; $('#ss2').value = k.total_points; $('#ss3').value = k.velocity;
    $('#ss4').value = rows.filter(r => r.blocked > 0).length; $('#ss5').value = rows.filter(r => r.column_name !== 'Done').length; };
  $('#ssBtn').onclick = async () => {
    try { const r = await post('/api/predict/sprint-success', {total_stories: num('#ss1'), total_points: num('#ss2'), team_velocity: num('#ss3'), blocked_stories: num('#ss4'), pending_tasks: num('#ss5')});
      const c = r.success ? 'success' : 'danger';
      $('#ssOut').innerHTML = `<div class="res-box"><div class="small text-muted">Success Probability</div><div class="big">${r.probability}%</div>
        <div class="progress my-2" style="height:8px"><div class="progress-bar bg-${c}" style="width:${r.probability}%"></div></div>
        <span class="badge text-bg-${c}">${r.label}</span><ul class="small mt-2 mb-0">${r.drivers.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>`; }
    catch (e) { toast(e.message); }
  };
  $('#rkBtn').onclick = async () => {
    try { const r = await post('/api/predict/risk', {story_points: num('#rk1'), priority: $('#rk2').value, blocked_issues: num('#rk3'), dependency_count: num('#rk4'), sprint_workload: num('#rk5')});
      $('#rkOut').innerHTML = `<div class="res-box"><div class="d-flex align-items-center gap-2 mb-2"><span class="dot ${r.risk_level}"></span><b>${r.label}</b></div>
        <div class="small text-muted">Reasons</div><ul class="small mb-0">${r.reasons.map(d => `<li>${esc(d)}</li>`).join('')}</ul></div>`; }
    catch (e) { toast(e.message); }
  };
}

const PAGES = {dashboard, board, analytics, insights};
const load = () => PAGES[PAGE]().catch(e => toast(e.message));
initSprints().then(() => { if (PAGE === 'board') boardInit(); load(); });
