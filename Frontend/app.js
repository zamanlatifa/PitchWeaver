'use strict';

const INTERVAL_MAP = {
  0:  "Perfect Unison", 1:  "Minor 2nd",  2:  "Major 2nd",
  3:  "Minor 3rd",      4:  "Major 3rd",  5:  "Perfect 4th",
  6:  "Tritone",        7:  "Perfect 5th", 8:  "Minor 6th",
  9:  "Major 6th",     10:  "Minor 7th",  11:  "Major 7th",
};

const AI_MUSICAL_LABELS = {
  COLLECTING_DATA:  { name: "Warming Up",        desc: "Answer a few intervals so I can get to know your ear." },
  STABLE_LEARNING:  { name: "In the Groove",      desc: "You're doing well, so the intervals will get a little harder." },
  FATIGUE_DETECTED: { name: "Time for a Breath",  desc: "You seem to be slowing down, so I've made things a bit easier." },
  RANDOM_GUESSING:  { name: "Finding the Beat",   desc: "These seem tricky right now, so let's go back to easier intervals." },
  SYSTEMATIC_SWAP:  { name: "Pattern Detected",   desc: "You keep mixing up the same intervals, so let's practise those." },
};

const DIFFICULTY_LABELS = {
  1: "Level 1: Foundations",
  2: "Level 2: Expanding",
  3: "Level 3: All 12 Intervals",
};

let currentTarget    = null;
let currentFreqA     = null;
let currentFreqB     = null;
let sessionStart     = Date.now();
let sessionCorrect   = 0;
let sessionTotal     = 0;
let timelineData     = [];
let waitingForAnswer = false;
let roundTarget          = null;
let firstAnswerSubmitted = false;
let practiceRoundActive  = false;
let replayWarningShown   = false;
let lastAiData           = null;
let sessionIntervalStats = {};
let audioCtx         = null;
let analyserNode     = null;
let waveAnimId       = null;
let waveIdleTimer    = null;

async function checkAuth() {
  try {
    const res = await fetch('/api/auth/me');
    if (!res.ok) { window.location.href = '/login'; return null; }
    const user = await res.json();
    setDifficultyLabel(user.current_difficulty || 1);
    return user;
  } catch {
    window.location.href = '/login';
    return null;
  }
}

async function handleLogout() {
  clearSessionState();
  await fetch('/api/auth/logout', { method: 'POST' });
  window.location.href = '/login';
}

function initAudio() {
  if (!audioCtx) {
    audioCtx     = new (window.AudioContext || window.webkitAudioContext)();
    analyserNode = audioCtx.createAnalyser();
    analyserNode.fftSize = 64;
    analyserNode.connect(audioCtx.destination);
  }
  if (audioCtx.state === 'suspended') audioCtx.resume();
}

function playTone(freq, startAt, duration) {
  const osc  = audioCtx.createOscillator();
  const gain = audioCtx.createGain();
  osc.connect(gain);
  gain.connect(analyserNode);
  osc.type = 'triangle';
  osc.frequency.value = freq;
  gain.gain.setValueAtTime(0, startAt);
  gain.gain.linearRampToValueAtTime(0.4, startAt + 0.05);
  gain.gain.linearRampToValueAtTime(0,   startAt + duration);
  osc.start(startAt);
  osc.stop(startAt + duration + 0.1);
}

function playInterval(freqA, freqB) {
  document.getElementById('waveform-idle').style.display = 'none';
  startWaveformAnimation();
  const now = audioCtx.currentTime;
  playTone(freqA, now,       0.9);
  playTone(freqB, now + 1.1, 0.9);
  clearTimeout(waveIdleTimer);
  waveIdleTimer = setTimeout(() => {
    stopWaveformAnimation();
    document.getElementById('waveform-idle').style.display = '';
  }, 2400);
}

function startWaveformAnimation() {
  if (waveAnimId) cancelAnimationFrame(waveAnimId);
  const canvas = document.getElementById('waveform-canvas');
  const ctx2d  = canvas.getContext('2d');
  const draw   = () => {
    waveAnimId    = requestAnimationFrame(draw);
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    const W    = canvas.width, H = canvas.height;
    const data = new Uint8Array(analyserNode.frequencyBinCount);
    analyserNode.getByteFrequencyData(data);
    ctx2d.clearRect(0, 0, W, H);
    const slotW = W / data.length;
    data.forEach((val, i) => {
      const barH = (val / 255) * H * 0.85;
      const hue  = 18 + (i / data.length) * 22;
      ctx2d.fillStyle = `hsla(${hue},92%,55%,0.9)`;
      ctx2d.fillRect(i * slotW, H - barH, slotW - 1, barH);
    });
  };
  draw();
}

function stopWaveformAnimation() {
  if (waveAnimId) { cancelAnimationFrame(waveAnimId); waveAnimId = null; }
  const canvas = document.getElementById('waveform-canvas');
  canvas.getContext('2d').clearRect(0, 0, canvas.width, canvas.height);
}

function buildIntervalButtons() {
  const grid = document.getElementById('interval-grid');
  grid.innerHTML = '';
  Object.entries(INTERVAL_MAP).forEach(([semi, name]) => {
    const btn = document.createElement('button');
    btn.className        = 'btn-interval';
    btn.dataset.semitone = semi;
    btn.textContent      = name;
    btn.disabled         = true;
    btn.onclick          = () => handleAnswer(parseInt(semi));
    grid.appendChild(btn);
  });
}

function setAnswerButtonsEnabled(enabled) {
  document.querySelectorAll('.btn-interval').forEach(b => b.disabled = !enabled);
}

function flashAnswerButton(semitone, cssClass) {
  const btn = document.querySelector(`.btn-interval[data-semitone="${semitone}"]`);
  if (btn) btn.classList.add(cssClass);
}

function clearAnswerHighlights() {
  document.querySelectorAll('.btn-interval').forEach(b => {
    b.classList.remove('btn-correct', 'btn-wrong', 'btn-reveal');
  });
}

async function startExercise(evt) {
  initAudio();

  triggerRipple(evt);
  setPlayBtn(false);
  setReplayBtn(false);
  setMetronome(true);
  setStatus('Getting your next interval…');
  clearAnswerHighlights();
  setAnswerButtonsEnabled(false);

  try {
    const res = await fetch('/api/training/next');
    if (res.status === 401) { window.location.href = '/login'; return; }
    const data = await res.json();

    currentTarget    = data.target_interval;
    currentFreqA     = data.root_hz;
    currentFreqB     = data.target_hz;
    waitingForAnswer = true;
    sessionStart     = Date.now();

    roundTarget          = data.target_interval;
    firstAnswerSubmitted = false;
    practiceRoundActive  = false;

    setDifficultyLabel(data.difficulty_level || 1);
    setMetronome(false);
    setStatus('Listen carefully, then pick the interval you heard');
    setPlayBtn(false);
    setReplayBtn(true);

    playInterval(currentFreqA, currentFreqB);
    setAnswerButtonsEnabled(true);

  } catch (err) {
    setMetronome(false);
    setStatus('Can\'t connect right now. Please try again.');
    setPlayBtn(true, 'Play Interval');
    console.error(err);
  }
}

async function handleAnswer(semitone) {
  if (!waitingForAnswer) return;

  if (practiceRoundActive) { handlePracticeAnswer(semitone); return; }

  waitingForAnswer = false;
  setAnswerButtonsEnabled(false);
  setPlayBtn(false);

  const responseTime = Date.now() - sessionStart;

  try {
    const res = await fetch('/api/training/submit', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({
        guess:            semitone,
        target_interval:  currentTarget,
        response_time_ms: responseTime,
      }),
    });
    if (res.status === 401) { window.location.href = '/login'; return; }

    let data;
    try {
      data = await res.json();
    } catch {
      setStatus('Something went wrong. Please choose your answer again.');
      waitingForAnswer = true;
      setAnswerButtonsEnabled(true);
      return;
    }

    if (!res.ok) {
      const msg = (data.error || 'Server error').split('\n')[0].slice(0, 80);
      setStatus('Something went wrong. Please choose your answer again.');
      waitingForAnswer = true;
      setAnswerButtonsEnabled(true);
      return;
    }

    firstAnswerSubmitted = true;

    const correct = data.is_correct;
    sessionTotal++;
    if (correct) sessionCorrect++;

    if (!sessionIntervalStats[currentTarget]) {
      sessionIntervalStats[currentTarget] = { total: 0, correct: 0, misses: 0 };
    }
    const s = sessionIntervalStats[currentTarget];
    s.total++;
    if (correct) s.correct++;
    else         s.misses++;

    flashAnswerButton(semitone,    correct ? 'btn-correct' : 'btn-wrong');
    if (!correct) flashAnswerButton(currentTarget, 'btn-reveal');

    showFeedbackFlash(correct, correct
      ? `Correct, that was a ${INTERVAL_MAP[currentTarget]}`
      : `That was a ${INTERVAL_MAP[currentTarget]}, not a ${INTERVAL_MAP[semitone]}`
    );
    if (correct) spawnBurstRing();

    updateStats();
    timelineData.push({ correct });
    renderStaff(timelineData);
    updateAiPanel(data);
    lastAiData = data;
    saveSessionState();
    setDifficultyLabel(data.difficulty_level || 1);

    renderSessionAttentionAreas();
    renderSessionProgress();

    currentTarget = null;
    setTimeout(() => {
      clearAnswerHighlights();
      setPlayBtn(true, 'Next Interval');
      setStatus('Press Play for the next interval');
    }, 1400);

  } catch (err) {
    setStatus('Something went wrong. Please choose your answer again.');
    waitingForAnswer = true;
    setAnswerButtonsEnabled(true);
    console.error('Submit error:', err);
  }
}

function handlePracticeAnswer(semitone) {
  waitingForAnswer = false;
  setAnswerButtonsEnabled(false);

  const correct = (semitone === roundTarget);
  flashAnswerButton(semitone, correct ? 'btn-correct' : 'btn-wrong');
  if (!correct) flashAnswerButton(roundTarget, 'btn-reveal');

  showFeedbackFlash(correct, correct
    ? `Correct, that was a ${INTERVAL_MAP[roundTarget]} (practice, not scored)`
    : `That was a ${INTERVAL_MAP[roundTarget]} (practice, not scored)`
  );

  setTimeout(() => {
    clearAnswerHighlights();
    setPlayBtn(true, 'Next Interval');
    setStatus('Press Next Interval, or Replay to practise this one again');
  }, 1400);
}

function handleReplayClick() {
  if (currentFreqA === null || currentFreqB === null) return;

  if (replayWarningShown) { doReplay(); return; }
  replayWarningShown = true;
  showModal({
    title:   'Replay Interval',
    message: 'Only your first answer counts towards your score. You can still replay the notes as many times as you like to practise.',
    buttons: [
      { label: 'Got it', style: 'modal-btn-primary', onClick: doReplay },
    ],
  });
}

function doReplay() {
  hideModal();
  initAudio();
  clearAnswerHighlights();
  playInterval(currentFreqA, currentFreqB);

  if (firstAnswerSubmitted) {
    practiceRoundActive = true;
    waitingForAnswer    = true;
    setPlayBtn(false);
    setAnswerButtonsEnabled(true);
    setStatus('Practice round. This answer won\'t count towards your score.');
  } else {
    setStatus('Listen carefully, then pick the interval you heard');
  }
}

function handleResetClick() {
  showModal({
    title:   'Start Over?',
    message: 'This will clear all of your progress and take you back to Level 1. You can\'t undo this.',
    buttons: [
      { label: 'Cancel', style: 'modal-btn-secondary', onClick: hideModal },
      { label: 'Yes, start over',  style: 'modal-btn-danger',    onClick: doResetSession },
    ],
  });
}

async function doResetSession() {
  hideModal();

  sessionCorrect       = 0;
  sessionTotal         = 0;
  timelineData         = [];
  lastAiData           = null;
  sessionIntervalStats = {};
  clearSessionState();
  updateStats();
  renderStaff(timelineData);
  renderSessionAttentionAreas();
  renderSessionProgress();

  try {
    const res = await fetch('/api/user/reset', { method: 'POST' });
    if (res.status === 401) { window.location.href = '/login'; return; }
    if (!res.ok) throw new Error('Reset failed on the server');
  } catch (err) {
    showFeedbackFlash(false, 'Couldn\'t clear your progress. Please try again.');
    console.error('Reset error:', err);
    return;
  }

  resetAiPanel();
  setDifficultyLabel(1);

  showFeedbackFlash(true, 'Your progress has been cleared');
}

function resetAiPanel() {
  const info  = AI_MUSICAL_LABELS.COLLECTING_DATA;
  const badge = document.getElementById('ai-state-badge');
  badge.textContent = info.name;
  badge.className   = 'ai-state-badge COLLECTING_DATA';
  document.getElementById('ai-state-label').textContent  = info.desc;
  document.getElementById('ai-action-text').textContent  = '';
  document.getElementById('gauge-fill').style.width      = '50%';
  document.getElementById('gauge-needle').style.left     = '50%';
}

function showModal({ title, message, buttons }) {
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

function hideModal() {
  document.getElementById('modal-overlay').classList.add('hidden');
}

function setReplayBtn(enabled) {
  document.getElementById('btn-replay').disabled = !enabled;
}

function openChangePasswordModal() {
  document.getElementById('pw-form').reset();
  setPwError('');
  document.getElementById('pw-modal-overlay').classList.remove('hidden');
  document.getElementById('pw-current').focus();
}

function closeChangePasswordModal() {
  document.getElementById('pw-modal-overlay').classList.add('hidden');
}

function setPwError(msg) {
  const el = document.getElementById('pw-error');
  el.textContent = msg;
  el.classList.toggle('hidden', !msg);
}

async function submitChangePassword(evt) {
  evt.preventDefault();
  setPwError('');

  const current = document.getElementById('pw-current').value;
  const next    = document.getElementById('pw-new').value;
  const confirm = document.getElementById('pw-confirm').value;

  if (next !== confirm) { setPwError('New passwords do not match.'); return; }

  const btn = document.getElementById('pw-submit');
  btn.disabled    = true;
  btn.textContent = 'Saving…';

  try {
    const res  = await fetch('/api/auth/change-password', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ current_password: current, new_password: next }),
    });
    if (res.status === 401 && !(await res.clone().json()).error) {
      window.location.href = '/login'; return;
    }
    const data = await res.json();
    if (!res.ok) { setPwError(data.error || 'Could not change password.'); return; }

    closeChangePasswordModal();
    showFeedbackFlash(true, 'Password changed');
  } catch {
    setPwError('Can\'t connect right now. Please try again.');
  } finally {
    btn.disabled    = false;
    btn.textContent = 'Change Password';
  }
}

const SESSION_STATE_KEY = 'pw_session_state';

function saveSessionState() {
  try {
    sessionStorage.setItem(SESSION_STATE_KEY, JSON.stringify({
      sessionCorrect,
      sessionTotal,
      timelineData,
      replayWarningShown,
      lastAiData,
      sessionIntervalStats,
    }));
  } catch {  }
}

function restoreSessionState() {
  try {
    const raw = sessionStorage.getItem(SESSION_STATE_KEY);
    if (!raw) return false;
    const s = JSON.parse(raw);
    sessionCorrect       = s.sessionCorrect     || 0;
    sessionTotal         = s.sessionTotal       || 0;
    timelineData         = Array.isArray(s.timelineData) ? s.timelineData : [];
    replayWarningShown   = !!s.replayWarningShown;
    lastAiData           = s.lastAiData || null;
    sessionIntervalStats = s.sessionIntervalStats || {};

    updateStats();
    renderStaff(timelineData);
    if (lastAiData) updateAiPanel(lastAiData);
    renderSessionAttentionAreas();
    renderSessionProgress();
    return true;
  } catch {
    return false;
  }
}

function clearSessionState() {
  try { sessionStorage.removeItem(SESSION_STATE_KEY); } catch {  }
}

function renderStaff(events) {
  const svg      = document.getElementById('staff-svg');
  const emptyMsg = document.getElementById('staff-empty-msg');
  if (!events.length) { svg.style.display = 'none'; emptyMsg.style.display = ''; return; }
  emptyMsg.style.display = 'none';
  svg.style.display = 'block';

  const H = 80, LEFT_PAD = 48, STEP = 36, STAFF_TOP = 14, LINE_GAP = 10;
  const W = LEFT_PAD + events.length * STEP + 24;
  svg.setAttribute('width',   W);
  svg.setAttribute('height',  H);
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

  let html = '';
  for (let i = 0; i < 5; i++) {
    const y = STAFF_TOP + i * LINE_GAP;
    html += `<line x1="${LEFT_PAD-8}" y1="${y}" x2="${W-8}" y2="${y}" stroke="#d6d3d1" stroke-width="1"/>`;
  }
  html += `<text x="8" y="${STAFF_TOP+36}" font-size="48" fill="#ea580c" font-family="serif" opacity="1">𝄞</text>`;

  events.forEach((ev, i) => {
    if (i > 0 && i % 4 === 0) {
      const x = LEFT_PAD + i * STEP;
      html += `<line x1="${x}" y1="${STAFF_TOP}" x2="${x}" y2="${STAFF_TOP+4*LINE_GAP}" stroke="#a8a29e" stroke-width="1.5"/>`;
    }
    const x  = LEFT_PAD + i * STEP + STEP / 2;
    const cy = STAFF_TOP + 2 * LINE_GAP;
    if (ev.correct) {
      html += `<ellipse cx="${x}" cy="${cy}" rx="6" ry="5" fill="#15803d" opacity="1"/>`;
      html += `<line x1="${x+6}" y1="${cy}" x2="${x+6}" y2="${cy-20}" stroke="#15803d" stroke-width="1.5"/>`;
    } else {
      html += `<text x="${x-5}" y="${cy+5}" font-size="18" fill="#b91c1c" font-family="serif" opacity="1">𝄽</text>`;
    }
  });
  svg.innerHTML = html;
}

function updateAiPanel(data) {
  const state = data.ai_state;
  const info  = AI_MUSICAL_LABELS[state] || AI_MUSICAL_LABELS.COLLECTING_DATA;
  const badge = document.getElementById('ai-state-badge');
  badge.textContent = info.name;
  badge.className   = `ai-state-badge ${state in AI_MUSICAL_LABELS ? state : 'COLLECTING_DATA'}`;

  let desc = info.desc;
  const attempts     = data.total_attempts || 0;
  const recentErrors = data.recent_frequent_errors || [];
  const bias         = data.circular_bias_semitones;
  const recentAcc    = data.recent_accuracy;

  if (state === 'COLLECTING_DATA' && attempts <= 5) {
    desc = `Warming up. ${attempts} of 5 intervals done.`;
  } else {
    const insights = [];
    if (recentAcc !== undefined && recentAcc !== null) {
      insights.push(`You got ${Math.round(recentAcc * 100)}% of your last few right.`);
    }
    if (recentErrors.length) {
      const worst = INTERVAL_MAP[recentErrors[0].semitone] || 'a tricky interval';
      insights.push(`The ${worst} has tripped you up ${recentErrors[0].count} times lately.`);
    } else if (bias !== undefined && bias !== null && Math.abs(bias) >= 0.5) {
      insights.push(`You often pick an interval that is a little too ${bias > 0 ? 'wide' : 'narrow'}.`);
    } else if (recentAcc !== undefined && recentAcc !== null && recentAcc >= 0.7) {
      insights.push('No repeated mistakes lately. Nice work!');
    }
    desc = `${info.desc} ${insights.join(' ')}`.trim();
  }
  document.getElementById('ai-state-label').textContent = desc;
  document.getElementById('ai-action-text').textContent =
    data.ai_action ? `What happens next: ${data.ai_action}` : '';

  if (bias !== undefined && bias !== null) {
    const pct = Math.max(4, Math.min(96, Math.round(((bias + 6) / 12) * 100)));
    document.getElementById('gauge-fill').style.width  = `${pct}%`;
    document.getElementById('gauge-needle').style.left = `${pct}%`;
  }
}

function renderSessionAttentionAreas() {
  const areas = Object.entries(sessionIntervalStats)
    .filter(([, s]) => s.misses > 0)
    .map(([semi, s]) => ({
      interval_name: INTERVAL_MAP[semi] || 'Unknown',
      semitone:      parseInt(semi),
      miss_count:    s.misses,
    }))
    .sort((a, b) => b.miss_count - a.miss_count);
  renderAttentionAreas(areas);
}

function renderSessionProgress() {
  const rows = Object.entries(sessionIntervalStats)
    .map(([semi, s]) => ({
      interval: INTERVAL_MAP[semi] || 'Unknown',
      semitone: parseInt(semi),
      total:    s.total,
      correct:  s.correct,
      misses:   s.misses,
      accuracy: s.total > 0 ? Math.round((s.correct / s.total) * 1000) / 10 : 0,
    }))
    .sort((a, b) => a.semitone - b.semitone);
  renderProgress(rows);
}

async function fetchAttentionAreas() {
  try {
    const res  = await fetch('/api/user/attention-areas');
    if (!res.ok) return;
    renderAttentionAreas(await res.json());
  } catch {  }
}

function renderAttentionAreas(areas) {
  const c = document.getElementById('attention-list');
  if (!areas.length) { c.innerHTML = '<p class="attention-empty">No tricky intervals yet. Keep going!</p>'; return; }
  c.innerHTML = areas.slice(0, 4).map(a => `
    <div class="attention-item">
      <div class="attention-interval-name">${a.interval_name}</div>
      <div class="attention-miss-count">Missed ${a.miss_count} ${a.miss_count === 1 ? 'time' : 'times'}</div>
    </div>
  `).join('');
}

async function fetchProgress() {
  try {
    const res  = await fetch('/api/user/progress');
    if (!res.ok) return;
    renderProgress(await res.json());
  } catch {  }
}

function renderProgress(rows) {
  const c = document.getElementById('progress-rows');
  if (!rows.length) { c.innerHTML = '<p class="attention-empty">Play a few rounds to see how you are doing.</p>'; return; }
  c.innerHTML = rows.map(r => `
    <div class="progress-row">
      <span class="pr-name">${r.interval}</span>
      <div class="pr-bar-wrap"><div class="pr-bar-fill" style="width:${r.accuracy}%"></div></div>
      <span class="pr-pct">${r.accuracy}%</span>
    </div>
  `).join('');
}

function updateStats() {
  document.getElementById('stat-total').textContent   = sessionTotal;
  document.getElementById('stat-correct').textContent = sessionCorrect;
  const pct = sessionTotal > 0 ? `${Math.round((sessionCorrect / sessionTotal) * 100)}%` : '0%';
  document.getElementById('stat-accuracy').textContent = pct;
}

function showFeedbackFlash(correct, msg) {
  const el = document.getElementById('feedback-flash');
  el.textContent = msg;
  el.className   = `${correct ? 'correct' : 'wrong'} show`;
  setTimeout(() => { el.className = correct ? 'correct' : 'wrong'; }, 1600);
}

function spawnBurstRing() {
  const ring = document.createElement('div');
  ring.className = 'burst-ring';
  ring.style.left = '50%';
  ring.style.top  = '45%';
  document.body.appendChild(ring);
  setTimeout(() => ring.remove(), 600);
}

function triggerRipple(evt) {
  const btn  = document.getElementById('btn-play');
  const rect = btn.getBoundingClientRect();
  const rpl  = document.createElement('span');
  rpl.className = 'ripple-circle';
  rpl.style.left = `${(evt?.clientX || rect.left + rect.width/2) - rect.left}px`;
  rpl.style.top  = `${(evt?.clientY || rect.top  + rect.height/2) - rect.top}px`;
  btn.appendChild(rpl);
  setTimeout(() => rpl.remove(), 600);
}

function setMetronome(visible) {
  document.getElementById('metronome-loader').classList.toggle('visible', visible);
}

function setPlayBtn(enabled, label) {
  const btn = document.getElementById('btn-play');
  btn.disabled = !enabled;
  if (label !== undefined) {
    btn.textContent = label;
  }
}

function setStatus(msg) { document.getElementById('status-text').textContent = msg; }
function setDifficultyLabel(lvl) {
  document.getElementById('difficulty-label').textContent = DIFFICULTY_LABELS[lvl] || `Level ${lvl}`;
}

(async () => {
  const user = await checkAuth();
  if (!user) return;
  buildIntervalButtons();

  const hadSession = restoreSessionState();

  if (!hadSession) {
    renderAttentionAreas([]);
    renderProgress([]);
  }
})();