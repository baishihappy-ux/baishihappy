const canvas = document.getElementById('particleCanvas');
const ctx = canvas.getContext('2d');
const heroCanvas = document.getElementById('spaceHeroCanvas');
const heroCtx = heroCanvas ? heroCanvas.getContext('2d') : null;
const backgroundMusic = document.getElementById('backgroundMusic');
const shipImage = new Image();
shipImage.src = './assets/newfeichuan.png';

const state = {
  particles: [],
  heroStars: [],
  unlocked: false,
  engineStarted: false,
  runStartedAt: 0,
  timerId: null,
  selectedTargetSource: 'T',
  lastLicense: null,
  modalResolver: null
};

function $(id) {
  return document.getElementById(id);
}

function parseJson(text, fallback = {}) {
  try {
    return JSON.parse(String(text || '{}'));
  } catch {
    return fallback;
  }
}

function normalizeLicense(result) {
  const payload = parseJson(result?.out, {});
  const licensePayload = payload.payload || payload.license || {};
  const ok = Boolean(payload.ok || payload.valid);
  const maxConcurrency = Number(
    payload.max_concurrency ||
      payload.max_instances ||
      licensePayload.max_concurrency ||
      licensePayload.max_instances ||
      0
  );
  const expiresAt = Number(payload.expires_at || licensePayload.expires_at || 0);
  const remainingDays = expiresAt
    ? Math.max(0, Math.ceil((expiresAt * 1000 - Date.now()) / 86400000))
    : Number(payload.remaining_days || licensePayload.remaining_days || 0);
  return {
    valid: ok,
    reason: payload.reason || result?.err || '',
    machine_code: payload.machine_code || licensePayload.machine_code || '',
    max_instances: maxConcurrency,
    remaining_days: remainingDays,
    raw: payload
  };
}

function setLicenseMessage(message, type = '') {
  const node = $('licenseStatusText');
  if (!node) return;
  node.textContent = message;
  node.className = `status-text ${type}`.trim();
}

function setMachineCode(value) {
  const machineCode = String(value || '').trim();
  $('machineCode').textContent = machineCode || '未获取';
  const button = $('copyMachineCode');
  button.disabled = !machineCode;
  button.dataset.copyValue = machineCode;
}

function setWindowLimit(status) {
  const count = Number(status?.max_instances || 0);
  const text = count > 0 ? `${count} 窗口` : '未授权';
  $('licenseWindowLimit').textContent = text;
  $('authLimit').textContent = text;
}

function displayLicenseReason(reason) {
  const text = String(reason || '').trim();
  if (!text || text.includes('license.dat')) return '未检测到授权码';
  if (text.includes('DF8-') || text.includes('invalid') || text.includes('无法解析')) return '授权码无效';
  return text;
}

async function loadMachineCode() {
  const result = await window.t1Runtime.get_machine_code();
  const code = String(result?.out || '').trim();
  setMachineCode(code);
  return code;
}

async function checkLicense() {
  try {
    const runtime = await window.t1Runtime.get_status();
    $('licenseRoot').textContent = runtime?.runtime_root || '未获取';
    const fallbackMachine = await loadMachineCode();
    const result = await window.t1Runtime.get_license_status();
    const status = normalizeLicense(result);
    setMachineCode(status.machine_code || fallbackMachine);
    setWindowLimit(status);
    if (status.valid) {
      state.lastLicense = status;
      $('enterApp').classList.remove('hidden');
      $('licenseForm').classList.add('hidden');
      setLicenseMessage(`授权有效，已授权 ${status.max_instances || 1} 窗口。请点击“进入主程序”。`, 'ok');
    } else {
      $('licenseForm').classList.remove('hidden');
      $('enterApp').classList.add('hidden');
      setLicenseMessage(displayLicenseReason(status.reason), 'error');
    }
  } catch (error) {
    $('licenseForm').classList.remove('hidden');
    setLicenseMessage(`授权检测异常：${error.message}`, 'error');
  }
}

async function activateLicense(event) {
  event.preventDefault();
  const code = $('licenseCode').value.trim();
  if (!code) {
    setLicenseMessage('请输入授权码。', 'error');
    return;
  }
  setLicenseMessage('正在验证授权码...', '');
  const result = await window.t1Runtime.activate_license(code);
  const status = normalizeLicense(result);
  if (status.valid) {
    state.lastLicense = status;
    setMachineCode(status.machine_code || $('copyMachineCode').dataset.copyValue || '');
    setWindowLimit(status);
    $('enterApp').classList.remove('hidden');
    $('licenseForm').classList.add('hidden');
    setLicenseMessage(`授权成功，已授权 ${status.max_instances || 1} 窗口。请点击“进入主程序”。`, 'ok');
  } else {
    setLicenseMessage(displayLicenseReason(status.reason || result?.err), 'error');
  }
}

async function copyMachineCode() {
  const value = $('copyMachineCode').dataset.copyValue || '';
  if (!value) return;
  await window.t1Runtime.copy_text(value);
  setLicenseMessage('机器码已复制。', 'ok');
}

function unlockApp(status) {
  state.unlocked = true;
  $('licenseLayer').classList.add('hidden');
  $('appShell').classList.remove('locked');
  $('engineState').classList.remove('hidden');
  $('authState').textContent = status.valid ? `有效，剩余 ${status.remaining_days || '--'} 天` : '未授权';
  setWindowLimit(status);
  setTargetSourceSelection('T', true);
  $('engineState').textContent = '授权通过，请确认通道后点击启动采集。';
  startRuntimeMetricsRefresh();
}

function setTargetSourceSelection(value, confirmed = false) {
  const source = ['T', 'F', 'P'].includes(String(value).toUpperCase()) ? String(value).toUpperCase() : 'T';
  state.selectedTargetSource = source;
  document.querySelectorAll('input[name="targetSource"]').forEach((input) => {
    input.checked = input.value === source;
  });
  $('targetSourceStatus').textContent = confirmed ? `当前通道：${source}` : `待确认通道：${source}`;
}

function showAppModal(message, title = '提示') {
  $('appModalTitle').textContent = title;
  $('appModalMessage').textContent = message;
  $('appModalCancel').classList.add('hidden');
  $('appModal').classList.remove('hidden');
}

function showAppConfirm(message, title = '确认') {
  $('appModalTitle').textContent = title;
  $('appModalMessage').textContent = message;
  $('appModalCancel').classList.remove('hidden');
  $('appModal').classList.remove('hidden');
  return new Promise((resolve) => {
    state.modalResolver = resolve;
  });
}

function hideAppModal(value = true) {
  $('appModal').classList.add('hidden');
  if (state.modalResolver) {
    state.modalResolver(Boolean(value));
    state.modalResolver = null;
  }
}

async function confirmTargetSource() {
  const selected = document.querySelector('input[name="targetSource"]:checked')?.value || 'T';
  const result = await window.t1Runtime.set_target_source(selected);
  if (!result?.ok) {
    $('targetSourceStatus').textContent = `通道确认失败：${result?.error || 'unknown'}`;
    return;
  }
  setTargetSourceSelection(result.targetSource || selected, true);
}

async function startEngine() {
  if (state.engineStarted) return;
  $('engineState').textContent = '正在执行启动前检查...';
  const preflight = await window.t1Runtime.preflight();
  if (!preflight.ok) {
    const input = preflight.input || {};
    const lock = preflight.lock || {};
    const message = [
      preflight.license?.ok ? '' : '授权未通过',
      input.exists && input.row_count > 0 ? '' : `未发现可用底料：${input.target_path || ''}`,
      lock.active ? `检测到正在运行的任务 PID=${lock.pid || ''}` : '',
    ].filter(Boolean).join('\n') || '启动前检查未通过。';
    $('engineState').textContent = '启动前检查未通过。';
    showAppModal(message, '启动前检查');
    return;
  }
  $('networkQuality').textContent = '检测中';
  const network = await window.t1Runtime.test_network();
  $('networkQuality').textContent = network.quality || (network.canRun ? '良' : '差');
  $('networkQuality').className = network.canRun ? 'network-good' : 'network-bad';
  if (!network.canRun) {
    $('engineState').textContent = '网络检测未通过。';
    showAppModal(`当前网络${network.quality || '差'}，建议不运行。`, '网络检测');
    return;
  }
  $('engineState').textContent = '正在启动采集...';
  const result = await window.t1Runtime.send_command('start');
  if (result?.ok === false) {
    $('engineState').textContent = '启动失败。';
    const detail = result.preflight ? JSON.stringify(result.preflight, null, 2) : (result.error || result.err || '引擎启动失败。');
    showAppModal(detail, '启动失败');
    return;
  }
  state.engineStarted = true;
  state.runStartedAt = Date.now();
  $('startEngine').disabled = true;
  $('engineState').textContent = '采集已启动。';
  startRunTimer();
  await refreshRuntimeMetrics();
}

async function togglePauseEngine() {
  const button = $('pauseEngine');
  const paused = button.classList.contains('pause-active');
  if (!paused) {
    const confirmed = await showAppConfirm('暂停后系统会停止领取新的底料，已经在执行中的任务会继续自然结束。是否确认暂停？', '确认暂停采集');
    if (!confirmed) return;
  }
  const command = paused ? 'resume' : 'pause';
  const result = await window.t1Runtime.send_command(command);
  if (result?.ok === false) {
    showAppModal(result.error || '操作失败。', paused ? '恢复失败' : '暂停失败');
    return;
  }
  button.classList.toggle('pause-active', !paused);
  button.textContent = paused ? '暂停采集' : '恢复采集';
  $('engineState').textContent = paused ? '已恢复采集。' : '已暂停领取新底料，运行中的任务会自然结束。';
  await refreshRuntimeMetrics();
}

function numberValue(value, fallback = 0) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function runtimeStateText(rawStatus) {
  const raw = String(rawStatus || '').toLowerCase();
  if (raw.includes('running')) return { text: '标准运行', level: 'good' };
  if (raw.includes('pause')) return { text: '已暂停', level: 'warn' };
  if (raw.includes('finish') || raw.includes('completed')) return { text: '已完成', level: 'good' };
  if (raw.includes('fail') || raw.includes('error')) return { text: '异常停止', level: 'bad' };
  return { text: '待启动', level: 'warn' };
}

async function refreshRuntimeMetrics() {
  const snapshot = await window.t1Runtime.get_status();
  const status = snapshot?.status || {};
  const requestRate = Math.round(numberValue(status.provider_request_rate_per_minute || status.claim_rate_per_minute, 0));
  const saveRate = Math.round(numberValue(status.rate_per_minute || status.throughput_rate, 0));
  const doCurrent = Math.round(numberValue(status.do_inflight_current || status.scheduler_do_inflight_current, 0));
  const doLimit = Math.round(numberValue(status.do_inflight_hard_limit || status.do_inflight_target || status.authorized_concurrency, 0));
  const requestCount = numberValue(status.provider_request_30s_count || status.provider_request_count, 0);
  const bad502 = numberValue(status.provider_502_30s_count || status.error_502_count, 0);
  const successRate = requestCount ? Math.max(0, ((requestCount - bad502) / requestCount) * 100) : NaN;
  const badRate = requestCount ? (bad502 / requestCount) * 100 : 0;
  const stateInfo = runtimeStateText(status.status);

  setText('metricRequestRate', `${requestRate}/min`);
  setText('metricSaveRate', `${saveRate}/min`);
  setText('metricAccessSuccessRate', Number.isFinite(successRate) ? `${successRate.toFixed(1)}%` : '--');
  setText('metric502Rate', `${badRate.toFixed(1)}%`);
  setText('metricDoInflight', `${doCurrent}/${doLimit}`);
  setText('metricRemaining', String(Math.max(0, Math.trunc(numberValue(status.remaining_work || status.remaining, 0)))));
  setText('metricSavedTotal', String(Math.trunc(numberValue(status.saved || status.saved_total, 0))));
  setText('metricCompletedTotal', String(Math.trunc(numberValue(status.customer_completed_seeds || status.completed || status.processed, 0))));
  setText('metricWarmExpiredTotal', String(Math.trunc(numberValue(status.warm_pool_factory_expired_total, 0))));
  setText('metricLocalWaitSplit', `${Math.trunc(numberValue(status.provider_stage_wait_avg_ms, 0))}/${Math.trunc(numberValue(status.provider_do_wait_avg_ms, 0))}ms`);
  setText('metricRequestLatency', `${Math.trunc(numberValue(status.provider_elapsed_avg_ms, 0))}/${Math.trunc(numberValue(status.provider_elapsed_p95_ms, 0))}ms`);
  setText('metricOutboundLatency', `${Math.trunc(numberValue(status.provider_outbound_elapsed_avg_ms, 0))}ms`);
  setText('metricPageLatencySplit', `${Math.trunc(numberValue(status.provider_warmup_elapsed_avg_ms, 0))}/${Math.trunc(numberValue(status.provider_resultphone_elapsed_avg_ms, 0))}ms`);
  setText('metricRuntimeState', stateInfo.text);
  $('metricRuntimeState').parentElement.className = `runtime-metric-card metric-state metric-${stateInfo.level}`;
  $('metricAccessSuccessRate').parentElement.className = `runtime-metric-card metric-success metric-${Number.isFinite(successRate) && successRate >= 95 ? 'good' : 'warn'}`;
  $('metric502Rate').parentElement.className = `runtime-metric-card metric-risk metric-${badRate < 5 ? 'good' : badRate < 10 ? 'warn' : 'bad'}`;
  $('networkQuality').textContent = '稳定';
  $('networkQuality').className = 'network-good';
  return status;
}

function setText(id, value) {
  const node = $(id);
  if (node) node.textContent = value;
}

function startRuntimeMetricsRefresh() {
  refreshRuntimeMetrics();
  window.setInterval(refreshRuntimeMetrics, 1000);
}

function startRunTimer() {
  if (state.timerId) window.clearInterval(state.timerId);
  state.timerId = window.setInterval(updateRunTimer, 1000);
  updateRunTimer();
}

function updateRunTimer() {
  const elapsed = state.runStartedAt ? Date.now() - state.runStartedAt : 0;
  const totalSeconds = Math.floor(elapsed / 1000);
  const hours = String(Math.floor(totalSeconds / 3600)).padStart(2, '0');
  const minutes = String(Math.floor((totalSeconds % 3600) / 60)).padStart(2, '0');
  const seconds = String(totalSeconds % 60).padStart(2, '0');
  setText('runtimeTimer', `${hours}:${minutes}:${seconds}`);
}

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = Math.floor(window.innerWidth * dpr);
  canvas.height = Math.floor(window.innerHeight * dpr);
  canvas.style.width = `${window.innerWidth}px`;
  canvas.style.height = `${window.innerHeight}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function createParticles() {
  const count = Math.min(180, Math.max(100, Math.floor((window.innerWidth * window.innerHeight) / 7000)));
  state.particles = Array.from({ length: count }, () => ({
    x: Math.random() * window.innerWidth,
    y: Math.random() * window.innerHeight,
    r: Math.random() > 0.84 ? 1.8 : 0.9,
    speed: 0.08 + Math.random() * 0.28,
    phase: Math.random() * Math.PI * 2,
    gold: Math.random() > 0.72
  }));
}

function animateParticles(time = 0) {
  ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
  const gradient = ctx.createLinearGradient(0, 0, window.innerWidth, window.innerHeight);
  gradient.addColorStop(0, '#03050a');
  gradient.addColorStop(0.5, '#080d17');
  gradient.addColorStop(1, '#02040a');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
  for (const star of state.particles) {
    const alpha = 0.38 + Math.sin(time / 900 + star.phase) * 0.22;
    star.x = (star.x + star.speed) % window.innerWidth;
    ctx.beginPath();
    ctx.fillStyle = star.gold ? `rgba(255,217,120,${alpha})` : `rgba(230,244,255,${alpha})`;
    ctx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
    ctx.fill();
  }
  requestAnimationFrame(animateParticles);
}

function resizeHeroCanvas() {
  if (!heroCanvas || !heroCtx) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = heroCanvas.parentElement.getBoundingClientRect();
  heroCanvas.width = Math.floor(rect.width * dpr);
  heroCanvas.height = Math.floor(rect.height * dpr);
  heroCanvas.style.width = `${rect.width}px`;
  heroCanvas.style.height = `${rect.height}px`;
  heroCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  state.heroStars = Array.from({ length: 120 }, () => ({
    x: Math.random() * rect.width,
    y: Math.random() * rect.height,
    r: Math.random() > 0.88 ? 1.7 : 0.8
  }));
}

function animateHero(time = 0) {
  if (!heroCanvas || !heroCtx) return;
  const rect = heroCanvas.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;
  heroCtx.clearRect(0, 0, width, height);
  heroCtx.fillStyle = '#02040a';
  heroCtx.fillRect(0, 0, width, height);
  for (const star of state.heroStars) {
    heroCtx.beginPath();
    heroCtx.fillStyle = 'rgba(230,244,255,.62)';
    heroCtx.arc(star.x, star.y, star.r, 0, Math.PI * 2);
    heroCtx.fill();
  }
  drawSolar(width, height, time / 1000);
  drawShip(width, height, time / 1000);
  requestAnimationFrame(animateHero);
}

function drawSolar(width, height, t) {
  const cx = width * 0.09;
  const cy = height * 0.32;
  const planets = [
    ['#B7C8D8', 0.18, 4, 1.1],
    ['#D9A76D', 0.27, 6, 0.8],
    ['#62C8FF', 0.38, 10, 0.58],
    ['#FF8B73', 0.5, 7, 0.46],
    ['#F0C17D', 0.66, 14, 0.32],
    ['#C7A6FF', 0.8, 12, 0.24]
  ];
  const sun = heroCtx.createRadialGradient(cx, cy, 2, cx, cy, 70);
  sun.addColorStop(0, '#fff2bd');
  sun.addColorStop(0.48, '#f6c66d');
  sun.addColorStop(1, 'rgba(246,198,109,0)');
  heroCtx.fillStyle = sun;
  heroCtx.beginPath();
  heroCtx.arc(cx, cy, 70, 0, Math.PI * 2);
  heroCtx.fill();
  planets.forEach((planet, index) => {
    const [color, orbit, radius, speed] = planet;
    const a = width * orbit;
    const b = height * orbit * 0.54;
    heroCtx.strokeStyle = 'rgba(116,217,255,.22)';
    heroCtx.beginPath();
    heroCtx.ellipse(cx, cy, a, b, 0, 0, Math.PI * 2);
    heroCtx.stroke();
    const angle = t * speed + index;
    const x = cx + Math.cos(angle) * a;
    const y = cy + Math.sin(angle) * b;
    heroCtx.fillStyle = color;
    heroCtx.beginPath();
    heroCtx.arc(x, y, radius, 0, Math.PI * 2);
    heroCtx.fill();
  });
}

function drawShip(width, height, t) {
  const x = width * 0.62 + Math.sin(t * 0.7) * 34;
  const y = height * 0.52 + Math.cos(t * 0.55) * 18;
  const w = Math.min(210, width * 0.24);
  if (shipImage.complete) {
    heroCtx.save();
    heroCtx.globalAlpha = 0.92;
    heroCtx.translate(x, y);
    heroCtx.rotate(Math.sin(t * 0.9) * 0.04);
    heroCtx.drawImage(shipImage, -w / 2, -w * 0.32, w, w * 0.64);
    heroCtx.restore();
  }
}

function startBackgroundMusic() {
  if (!backgroundMusic) return;
  backgroundMusic.volume = 0.16;
  backgroundMusic.play().catch(() => {});
}

window.addEventListener('resize', () => {
  resizeCanvas();
  createParticles();
  resizeHeroCanvas();
});
window.addEventListener('pointerdown', startBackgroundMusic);
window.addEventListener('keydown', startBackgroundMusic);

$('licenseForm').addEventListener('submit', activateLicense);
$('copyMachineCode').addEventListener('click', copyMachineCode);
$('enterApp').addEventListener('click', () => unlockApp(state.lastLicense || { valid: true }));
$('confirmTargetSource').addEventListener('click', confirmTargetSource);
document.querySelectorAll('input[name="targetSource"]').forEach((input) => {
  input.addEventListener('change', () => setTargetSourceSelection(input.value, false));
});
$('startEngine').addEventListener('click', startEngine);
$('pauseEngine').addEventListener('click', togglePauseEngine);
$('toggleRuntimeTuning').addEventListener('click', () => showAppModal('热调参已默认关闭，当前版本以 app_config.json 固定参数为准。', '热调参'));
$('openRuntimeTuner').addEventListener('click', () => showAppModal('当前重建版不启用外接热调参。', '调参器'));
$('openRuntimeMonitor').addEventListener('click', async () => {
  const result = await window.t1Runtime.open_monitor();
  if (!result || result.ok === false) {
    showAppModal(result?.error || '看板小窗打开失败。', '运行看板');
  }
});
$('toggleDiagnosticMode').addEventListener('click', () => {
  document.querySelectorAll('.runtime-diagnostic-card').forEach((card) => card.classList.toggle('hidden'));
  $('toggleDiagnosticMode').classList.toggle('pause-active');
  $('toggleDiagnosticMode').textContent = $('toggleDiagnosticMode').classList.contains('pause-active') ? '调试开' : '调试关';
});
$('appModalClose').addEventListener('click', () => hideAppModal(true));
$('appModalCancel').addEventListener('click', () => hideAppModal(false));
$('appModal').addEventListener('click', (event) => {
  if (event.target === $('appModal')) hideAppModal(false);
});
$('startDemo').addEventListener('click', () => {
  $('demoOutput').textContent = '正式采集请点击“启动采集”。本地演示入口不参与正式运行。';
});
$('refreshDemoResults').addEventListener('click', async () => {
  const result = await window.t1Runtime.get_results('main', 80);
  $('demoOutput').textContent = result.exists
    ? `结果文件：${result.path}\n数据行：${result.dataRows}\n\n${result.preview}`
    : `暂无结果文件：${result.path}`;
});

resizeCanvas();
createParticles();
resizeHeroCanvas();
animateParticles();
animateHero();
checkLicense();
