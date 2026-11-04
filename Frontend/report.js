'use strict';

async function fetchReportData() {
  const res = await fetch('/api/user/report');
  if (res.status === 401) { window.location.href = '/login'; return null; }
  if (!res.ok) throw new Error('Could not load report data');
  return res.json();
}

function showSaveReportDialog() {
  rptShowModal({
    title:   'Save Your Report',
    message: 'Pick PDF to print or share it, or CSV to open it in a spreadsheet.',
    buttons: [
      { label: 'PDF',    style: 'modal-btn-primary',   onClick: () => { rptHideModal(); saveReportPDF(); } },
      { label: 'CSV',    style: 'modal-btn-primary',   onClick: () => { rptHideModal(); saveReportCSV(); } },
      { label: 'Cancel', style: 'modal-btn-secondary', onClick: rptHideModal },
    ],
  });
}

function rptShowModal({ title, message, buttons }) {
  document.getElementById('modal-title').textContent   = title;
  document.getElementById('modal-message').textContent = message;
  const actions = document.getElementById('modal-actions');
  actions.innerHTML = '';
  buttons.forEach(({ label, style, onClick }) => {
    const btn = document.createElement('button');
    btn.className   = `modal-btn ${style}`;
    btn.textContent = label;
    btn.onclick     = onClick;
    actions.appendChild(btn);
  });
  document.getElementById('modal-overlay').classList.remove('hidden');
}

function rptHideModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

async function saveReportCSV() {
  let r;
  try { r = await fetchReportData(); } catch (e) { alert(e.message); return; }
  if (!r) return;

  const esc  = (v) => `"${String(v).replace(/"/g, '""')}"`;
  const rows = [];

  rows.push(['PitchWeaver Progress Report']);
  rows.push(['Student', r.user_name]);
  rows.push(['Generated', r.generated_at]);
  rows.push([]);
  rows.push(['SUMMARY']);
  rows.push(['Intervals played',      r.overall.total_attempts]);
  rows.push(['Correct',               r.overall.correct]);
  rows.push(['Score (%)',             r.overall.accuracy]);
  rows.push(['Average answer time (seconds)', (r.overall.avg_response_ms / 1000).toFixed(1)]);
  rows.push(['Current level',         r.overall.difficulty_level]);
  rows.push([]);
  rows.push(['INTERVAL BY INTERVAL']);
  rows.push(['Interval', 'Played', 'Right', 'Wrong', 'Score (%)']);
  r.intervals.forEach(i => rows.push([i.interval, i.total, i.correct, i.misses, i.accuracy]));
  rows.push([]);
  rows.push(['TIPS']);
  rows.push([r.feedback.headline]);
  r.feedback.points.forEach(p => rows.push([p]));

  const csv  = rows.map(row => row.map(esc).join(',')).join('\r\n');
  const blob = new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8;' });
  const a    = document.createElement('a');
  a.href     = URL.createObjectURL(blob);
  a.download = `pitchweaver-report-${new Date().toISOString().slice(0, 10)}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(a.href);
}

async function saveReportPDF() {
  let r;
  try { r = await fetchReportData(); } catch (e) { alert(e.message); return; }
  if (!r) return;

  const escHtml = (s) => String(s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

  const intervalRows = r.intervals.map(i => `
      <tr>
        <td>${escHtml(i.interval)}</td>
        <td>${i.total}</td><td>${i.correct}</td><td>${i.misses}</td>
        <td>${i.accuracy}%</td>
      </tr>`).join('');

  const feedbackItems = r.feedback.points.map(p => `<li>${escHtml(p)}</li>`).join('');

  const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>PitchWeaver Report · ${escHtml(r.user_name)}</title>
<style>
  body   { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1f2937; margin: 40px; }
  h1     { color: #c2410c; border-bottom: 3px solid #f97316; padding-bottom: 8px; }
  h2     { color: #c2410c; margin-top: 28px; }
  .meta  { color: #6b7280; font-size: 0.9rem; }
  .stats { display: flex; gap: 16px; flex-wrap: wrap; margin: 16px 0; }
  .stat  { border: 1px solid #fdba74; border-radius: 10px; padding: 10px 18px; text-align: center; }
  .stat b{ display: block; font-size: 1.4rem; color: #c2410c; }
  table  { border-collapse: collapse; width: 100%; margin-top: 10px; }
  th, td { border: 1px solid #f2e2d2; padding: 6px 12px; text-align: left; font-size: 0.9rem; }
  th     { background: #fff4ea; color: #c2410c; }
  .headline { font-size: 1.05rem; font-weight: bold; margin-bottom: 8px; }
  li     { margin-bottom: 6px; line-height: 1.5; }
  @media print { body { margin: 16px; } }
</style>
</head>
<body>
  <h1>𝄞 PitchWeaver Progress Report</h1>
  <div class="meta">Student: ${escHtml(r.user_name)} · Generated: ${new Date(r.generated_at).toLocaleString()}</div>

  <h2>Summary</h2>
  <div class="stats">
    <div class="stat"><b>${r.overall.total_attempts}</b>Intervals Played</div>
    <div class="stat"><b>${r.overall.correct}</b>Correct</div>
    <div class="stat"><b>${r.overall.accuracy}%</b>Score</div>
    <div class="stat"><b>${(r.overall.avg_response_ms / 1000).toFixed(1)}s</b>Average Answer Time</div>
    <div class="stat"><b>Level ${r.overall.difficulty_level}</b>Current Level</div>
  </div>

  <h2>Interval by Interval</h2>
  <table>
    <thead><tr><th>Interval</th><th>Played</th><th>Right</th><th>Wrong</th><th>Score</th></tr></thead>
    <tbody>${intervalRows || '<tr><td colspan="5">No data yet</td></tr>'}</tbody>
  </table>

  <h2>Tips</h2>
  <div class="headline">${escHtml(r.feedback.headline)}</div>
  <ul>${feedbackItems}</ul>

  <script>window.onload = () => setTimeout(() => window.print(), 300);<\/script>
</body>
</html>`;

  const win = window.open('', '_blank');
  if (!win) { alert('Please allow pop-ups to save the PDF report.'); return; }
  win.document.write(html);
  win.document.close();
}
