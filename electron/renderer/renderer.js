const canvas = document.getElementById('particleCanvas');
const ctx = canvas.getContext('2d');
const heroCanvas = document.getElementById('spaceHeroCanvas');
const heroCtx = heroCanvas ? heroCanvas.getContext('2d') : null;
const backgroundMusic = document.getElementById('backgroundMusic');
const UI_SCALE = 1;
const HERO_DEFAULT_VIRTUAL_WIDTH = 900;
const shipBodyImage = new Image();
let shipBodyImageReady = false;
shipBodyImage.addEventListener('load', () => {
  shipBodyImageReady = true;
});
shipBodyImage.src = './assets/runtime_visual.png';
const RESULT_PREVIEW_FIELDS = [
  'phone',
  'name',
  'age',
  'gender',
  'state',
  'city',
  'property_value',
  'estimated_equity',
  'equity_percent',
  'occupancy_type_cn',
  'spouse_name',
  'marital_status',
  'company',
  'job_title_cn',
  'school',
  'major',
  'school_years'
];
const RESULT_PREVIEW_LABELS = {
  phone: '电话',
  name: '姓名',
  age: '年龄',
  gender: '性别',
  state: '州',
  city: '城市',
  property_value: '房产估值',
  estimated_equity: '预估净值',
  equity_percent: '净值比例',
  occupancy_type_cn: '居住类型',
  spouse_name: '配偶姓名',
  marital_status: '婚姻状态',
  company: '公司',
  job_title_cn: '职位',
  school: '学校',
  major: '专业',
  school_years: '就读年份'
};

const SOLAR_PLANETS = [
  { name: 'mercury', label: '水星', orbit: 0.16, r: 4, speed: 1.08, color: '#B7C8D8', phase: 0.5 },
  { name: 'venus', label: '金星', orbit: 0.24, r: 6, speed: 0.78, color: '#D9A76D', phase: 2.1 },
  { name: 'earth', label: '地球', orbit: 0.34, r: 11, speed: 0.57, color: '#62C8FF', phase: 3.5, moon: true },
  { name: 'mars', label: '火星', orbit: 0.45, r: 7, speed: 0.45, color: '#FF8B73', phase: 4.6 },
  { name: 'jupiter', label: '木星', orbit: 0.6, r: 15, speed: 0.315, color: '#F0C17D', phase: 1.1 },
  { name: 'saturn', label: '土星', orbit: 0.73, r: 13, speed: 0.24, color: '#C7A6FF', phase: 5.3, ring: true },
  { name: 'uranus', label: '天王星', orbit: 0.84, r: 10, speed: 0.18, color: '#7DE6E8', phase: 0.1 },
  { name: 'neptune', label: '海王星', orbit: 0.95, r: 10, speed: 0.135, color: '#5F8DFF', phase: 2.7 }
];

const state = {
  mouse: { x: window.innerWidth / 2, y: window.innerHeight / 2 },
  particles: [],
  heroStars: [],
  backgroundPlanetTrails: SOLAR_PLANETS.map(() => []),
  heroPlanetTrails: SOLAR_PLANETS.map(() => []),
  runtime: null,
  engineStarted: false,
  demoStarted: false,
  lastResultKind: 'demo',
  lastValidLicense: null,
  appUnlocked: false,
  heroSceneStartMs: null,
  musicStarted: false,
  logRefreshTimer: null,
  metricsRefreshTimer: null,
  runTimer: {
    startedAtMs: 0,
    elapsedMs: 0,
    intervalId: null,
    running: false,
    terminalReason: ''
  },
  selectedTargetSource: 'F',
  confirmedTargetSource: '',
  networkTest: null,
  networkTestInFlight: false,
  networkTestPromise: null,
  modalResolver: null,
  modalTimer: null,
  completionModalShown: false,
  pauseDrainTimer: null,
  runPaused: false,
  pauseInFlight: false,
  closeInProgress: false,
  diagnosticModeEnabled: false,
  animationSuspended: false
};

function $(id) {
  return document.getElementById(id);
}

function setLicenseMessage(message, type = '') {
  const node = $('licenseStatusText');
  node.textContent = message;
  node.className = `status-text ${type}`.trim();
}

function displayLicenseReason(reason, fallback = '授权无效，请输入新的授权码。') {
  const text = String(reason || '').trim();
  if (!text) {
    return fallback;
  }
  if (text.includes('license.dat')) {
    return '未检测到授权码';
  }
  if (
    text.includes('DF8-') ||
    text.includes('不是授权码') ||
    text.includes('有效授权码') ||
    text.includes('无法解析') ||
    text.includes('unsupported license version') ||
    text.includes('license envelope is invalid')
  ) {
    return '授权码无效';
  }
  return text;
}

function setMachineCode(value) {
  const machineCode = String(value || '').trim();
  $('machineCode').textContent = machineCode || 'Python 未获取';
  const copyButton = $('copyMachineCode');
  copyButton.disabled = !machineCode;
  copyButton.dataset.copyValue = machineCode;
}

function formatWindowLimit(status) {
  const count = Number(status?.max_instances || 0);
  return count > 0 ? `${count} 并发` : '未授权';
}

function setWindowLimit(status) {
  const text = formatWindowLimit(status);
  $('licenseWindowLimit').textContent = text;
  if ($('authLimit')) {
    $('authLimit').textContent = text;
  }
}

async function copyMachineCode() {
  const value = $('copyMachineCode').dataset.copyValue || '';
  if (!value) {
    return;
  }
  await window.workspaceRuntime.copyText(value);
  setLicenseMessage('机器码已复制。', 'ok');
}

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const width = window.innerWidth / UI_SCALE;
  const height = window.innerHeight / UI_SCALE;
  canvas.width = Math.floor(width * dpr);
  canvas.height = Math.floor(height * dpr);
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function createParticles() {
  const width = window.innerWidth / UI_SCALE;
  const height = window.innerHeight / UI_SCALE;
  const count = Math.min(210, Math.max(130, Math.floor((width * height) / 6200)));
  state.particles = Array.from({ length: count }, () => ({
    x: Math.random(),
    y: Math.random(),
    r: Math.random() > 0.82 ? 1.9 : 1,
    phase: Math.random() * Math.PI * 2,
    drift: 0.02 + Math.random() * 0.08,
    color: Math.random() > 0.72 ? 'gold' : 'ice'
  }));
  state.backgroundPlanetTrails = SOLAR_PLANETS.map(() => []);
}

function animateParticles(timeMs = 0) {
  if (state.animationSuspended) {
    window.setTimeout(() => animateParticles(performance.now()), 1000);
    return;
  }
  const width = window.innerWidth / UI_SCALE;
  const height = window.innerHeight / UI_SCALE;
  const t = timeMs / 1000;
  ctx.clearRect(0, 0, width, height);
  drawGlobalSpace(width, height, t);
  if (!state.appUnlocked) {
    drawGlobalSolarSystem(width, height, t);
  }
  requestAnimationFrame(animateParticles);
}

function drawGlobalSpace(width, height, t) {
  const gradient = ctx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, '#03050a');
  gradient.addColorStop(0.5, '#080d17');
  gradient.addColorStop(1, '#02040a');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, width, height);

  drawCanvasGlow(ctx, width * 0.78 + Math.sin(t * 0.26) * 18, height * 0.24, width * 0.34, 'rgba(88, 119, 255, 0.16)');
  drawCanvasGlow(ctx, width * 0.24, height * 0.72 + Math.cos(t * 0.2) * 18, width * 0.28, 'rgba(116, 217, 255, 0.1)');
  drawCanvasGlow(ctx, width * 0.52, height * 0.42, width * 0.2, 'rgba(246, 198, 109, 0.07)');

  for (const star of state.particles) {
    const x = (star.x * width + t * 16 * star.drift) % width;
    const y = star.y * height;
    const blink = 0.42 + Math.sin(t * 1.7 + star.phase) * 0.25;
    ctx.beginPath();
    ctx.fillStyle = star.color === 'gold'
      ? `rgba(255, 217, 120, ${0.28 + blink})`
      : `rgba(230, 244, 255, ${0.32 + blink})`;
    ctx.arc(x, y, star.r, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawGlobalSolarSystem(width, height, t) {
  const cx = width * 0.08;
  const cy = height * 0.31;
  const maxA = width * 0.98;
  const maxB = height * 0.58;
  const scale = Math.max(0.82, Math.min(width / 1280, height / 760, 1.18));
  drawSolarSystemOnCanvas(ctx, width, height, t, cx, cy, maxA, maxB, scale, state.backgroundPlanetTrails, 0.68);
}

function drawSolarSystemOnCanvas(renderCtx, width, height, t, cx, cy, maxA, maxB, scale, trails, alpha = 1, showLabels = false) {
  renderCtx.save();
  renderCtx.globalAlpha = alpha;

  const sunBreath = 1 + Math.sin(t * 2.2) * 0.105;
  drawCanvasGlow(renderCtx, cx, cy, Math.max(width, height) * 0.18 * scale * sunBreath, 'rgba(255, 198, 83, 0.22)');
  drawCanvasGlow(renderCtx, cx, cy, Math.max(width, height) * 0.09 * scale * sunBreath, 'rgba(255, 117, 38, 0.16)');
  drawSolarSun(renderCtx, cx, cy, scale, sunBreath);

  for (const planet of SOLAR_PLANETS) {
    const [a, b] = getOrbitAxes(planet, maxA, maxB);
    renderCtx.beginPath();
    renderCtx.strokeStyle = 'rgba(116, 217, 255, 0.26)';
    renderCtx.lineWidth = Math.max(1, 1.15 * scale);
    renderCtx.ellipse(cx, cy, a, b, 0, 0, Math.PI * 2);
    renderCtx.stroke();
  }

  SOLAR_PLANETS.forEach((planet, index) => {
    drawSolarPlanet(renderCtx, cx, cy, planet, maxA, maxB, scale, t, trails[index] || (trails[index] = []), {
      index,
      showLabels,
      width,
      height
    });
  });

  renderCtx.restore();
}

function getOrbitAxes(planet, maxA, maxB) {
  const ratio = planet.orbit;
  return [maxA * ratio, maxB * (0.18 + ratio * 0.82)];
}

function drawSolarSun(renderCtx, cx, cy, scale, breath = 1) {
  const haloRadius = 78 * scale * breath;
  const glow = renderCtx.createRadialGradient(cx - 10 * scale, cy - 10 * scale, 2, cx, cy, haloRadius);
  glow.addColorStop(0, '#fff2bd');
  glow.addColorStop(0.36, '#f6c66d');
  glow.addColorStop(0.7, '#8a501a');
  glow.addColorStop(1, 'rgba(87, 44, 12, 0)');
  renderCtx.beginPath();
  renderCtx.fillStyle = glow;
  renderCtx.arc(cx, cy, haloRadius, 0, Math.PI * 2);
  renderCtx.fill();

  const core = 21 * scale * breath;
  renderCtx.beginPath();
  renderCtx.fillStyle = '#f6c66d';
  renderCtx.strokeStyle = '#ffe2a3';
  renderCtx.lineWidth = 2;
  renderCtx.arc(cx, cy, core, 0, Math.PI * 2);
  renderCtx.fill();
  renderCtx.stroke();
}

function drawSolarPlanet(renderCtx, cx, cy, planet, maxA, maxB, scale, t, trail, options = {}) {
  const [a, b] = getOrbitAxes(planet, maxA, maxB);
  const angle = t * planet.speed + planet.phase;
  const x = cx + Math.cos(angle) * a;
  const y = cy + Math.sin(angle) * b;

  trail.push({ x, y });
  if (trail.length > 28) {
    trail.shift();
  }
  trail.forEach((point, index) => {
    const fade = index / Math.max(1, trail.length - 1);
    renderCtx.beginPath();
    renderCtx.fillStyle = `rgba(116, 217, 255, ${0.06 + fade * 0.24})`;
    renderCtx.arc(point.x, point.y, Math.max(1.2, 2.4 * scale * fade), 0, Math.PI * 2);
    renderCtx.fill();
  });

  renderCtx.beginPath();
  renderCtx.strokeStyle = 'rgba(39, 49, 73, 0.62)';
  renderCtx.lineWidth = 1;
  renderCtx.moveTo(cx, cy);
  renderCtx.lineTo(x, y);
  renderCtx.stroke();

  const r = planet.r * scale;
  drawCanvasGlow(renderCtx, x, y, r * 4.4, `${planet.color}22`);
  renderCtx.beginPath();
  renderCtx.fillStyle = 'rgba(17, 24, 39, 0.82)';
  renderCtx.arc(x, y, r + 3 * scale, 0, Math.PI * 2);
  renderCtx.fill();

  renderCtx.beginPath();
  renderCtx.fillStyle = planet.color;
  renderCtx.strokeStyle = 'rgba(247, 251, 255, 0.9)';
  renderCtx.lineWidth = Math.max(1, 1.2 * scale);
  renderCtx.arc(x, y, r, 0, Math.PI * 2);
  renderCtx.fill();
  renderCtx.stroke();

  renderCtx.beginPath();
  renderCtx.fillStyle = 'rgba(255, 255, 255, 0.58)';
  renderCtx.arc(x - r * 0.28, y - r * 0.36, Math.max(1.5, r * 0.22), 0, Math.PI * 2);
  renderCtx.fill();

  if (planet.name === 'earth') {
    renderCtx.beginPath();
    renderCtx.fillStyle = '#47D18C';
    renderCtx.ellipse(x - r * 0.18, y + r * 0.1, r * 0.22, r * 0.34, -0.45, 0, Math.PI * 2);
    renderCtx.fill();
    renderCtx.beginPath();
    renderCtx.ellipse(x + r * 0.24, y - r * 0.24, r * 0.18, r * 0.24, 0.35, 0, Math.PI * 2);
    renderCtx.fill();
  }

  if (planet.ring) {
    renderCtx.beginPath();
    renderCtx.strokeStyle = 'rgba(217, 197, 142, 0.88)';
    renderCtx.lineWidth = Math.max(1.4, 2 * scale);
    renderCtx.ellipse(x, y, r * 1.72, r * 0.58, -0.22, 0, Math.PI * 2);
    renderCtx.stroke();
  }

  if (planet.moon) {
    const moonOrbit = 25 * scale;
    const moonAngle = t * 1.4;
    const moonX = x + Math.cos(moonAngle) * moonOrbit;
    const moonY = y + Math.sin(moonAngle) * moonOrbit * 0.72;
    const moonR = Math.max(2.5, 4 * scale);
    renderCtx.beginPath();
    renderCtx.strokeStyle = 'rgba(82, 98, 124, 0.72)';
    renderCtx.ellipse(x, y, moonOrbit, moonOrbit * 0.72, 0, 0, Math.PI * 2);
    renderCtx.stroke();
    renderCtx.beginPath();
    renderCtx.fillStyle = '#d6d8dd';
    renderCtx.strokeStyle = '#ffffff';
    renderCtx.arc(moonX, moonY, moonR, 0, Math.PI * 2);
    renderCtx.fill();
    renderCtx.stroke();
  }

  if (options.showLabels) {
    const label = `${options.index + 1} ${planet.label}`;
    drawCanvasLabel(
      renderCtx,
      label,
      x + r + 6,
      y - r - 13,
      options.width,
      options.height,
      'rgba(244, 247, 251, 0.92)',
      'rgba(5, 9, 16, 0.68)',
      'rgba(116, 217, 255, 0.32)'
    );
  }
}

function drawCanvasGlow(renderCtx, x, y, radius, color) {
  const glow = renderCtx.createRadialGradient(x, y, 0, x, y, radius);
  glow.addColorStop(0, color);
  glow.addColorStop(1, 'rgba(0, 0, 0, 0)');
  renderCtx.beginPath();
  renderCtx.fillStyle = glow;
  renderCtx.arc(x, y, radius, 0, Math.PI * 2);
  renderCtx.fill();
}

function drawCanvasLabel(renderCtx, text, x, y, width, height, color, background, border) {
  renderCtx.save();
  renderCtx.font = '600 11px "Microsoft YaHei UI", "Microsoft YaHei", sans-serif';
  renderCtx.textBaseline = 'middle';
  renderCtx.textAlign = 'left';
  const paddingX = 5;
  const paddingY = 3;
  const metrics = renderCtx.measureText(text);
  const labelWidth = Math.ceil(metrics.width + paddingX * 2);
  const labelHeight = 18 + paddingY;
  const left = Math.max(4, Math.min(width - labelWidth - 4, x));
  const top = Math.max(4, Math.min(height - labelHeight - 4, y));
  renderCtx.fillStyle = background;
  renderCtx.fillRect(left, top, labelWidth, labelHeight);
  renderCtx.strokeStyle = border;
  renderCtx.lineWidth = 1;
  renderCtx.strokeRect(left + 0.5, top + 0.5, labelWidth - 1, labelHeight - 1);
  renderCtx.fillStyle = color;
  renderCtx.fillText(text, left + paddingX, top + labelHeight / 2);
  renderCtx.restore();
}

function resizeHeroCanvas() {
  if (!heroCanvas || !heroCtx) {
    return;
  }
  const dpr = window.devicePixelRatio || 1;
  const rect = heroCanvas.parentElement?.getBoundingClientRect() || heroCanvas.getBoundingClientRect();
  const virtualWidth = parseFloat(getComputedStyle(heroCanvas).getPropertyValue('--hero-virtual-width')) || HERO_DEFAULT_VIRTUAL_WIDTH;
  const width = Math.max(1, rect.width, virtualWidth);
  const height = Math.max(1, rect.height);
  heroCanvas.width = Math.floor(width * dpr);
  heroCanvas.height = Math.floor(height * dpr);
  heroCanvas.style.width = `${width}px`;
  heroCanvas.style.height = '100%';
  heroCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function createHeroStars() {
  if (!heroCanvas) {
    return;
  }
  const rect = heroCanvas.parentElement?.getBoundingClientRect() || heroCanvas.getBoundingClientRect();
  const virtualWidth = parseFloat(getComputedStyle(heroCanvas).getPropertyValue('--hero-virtual-width')) || HERO_DEFAULT_VIRTUAL_WIDTH;
  const width = Math.max(1, rect.width, virtualWidth);
  const height = Math.max(1, rect.height);
  const count = Math.min(190, Math.max(95, Math.floor((width * height) / 3000)));
  state.heroStars = Array.from({ length: count }, () => ({
    x: Math.random() * width,
    y: Math.random() * height,
    r: Math.random() > 0.86 ? 1.8 : 0.9,
    phase: Math.random() * Math.PI * 2,
    drift: 0.012 + Math.random() * 0.036
  }));
  state.heroPlanetTrails = SOLAR_PLANETS.map(() => []);
}

function animateHeroScene(timeMs = 0) {
  if (!heroCanvas || !heroCtx) {
    return;
  }
  if (state.animationSuspended) {
    window.setTimeout(() => animateHeroScene(performance.now()), 1000);
    return;
  }
  if (!state.appUnlocked) {
    requestAnimationFrame(animateHeroScene);
    return;
  }
  if (state.heroSceneStartMs === null) {
    state.heroSceneStartMs = timeMs;
  }
  const rect = heroCanvas.getBoundingClientRect();
  const width = Math.max(1, rect.width);
  const height = Math.max(1, rect.height);
  const t = Math.max(0, (timeMs - state.heroSceneStartMs) / 1000);
  heroCtx.clearRect(0, 0, width, height);
  drawHeroSpace(width, height, t);
  drawHeroSolarSystem(width, height, t);
  drawBronzeDingShip(width, height, t);
  requestAnimationFrame(animateHeroScene);
}

function drawHeroSpace(width, height, t) {
  const gradient = heroCtx.createLinearGradient(0, 0, width, height);
  gradient.addColorStop(0, '#02040a');
  gradient.addColorStop(0.52, '#07101d');
  gradient.addColorStop(1, '#03050a');
  heroCtx.fillStyle = gradient;
  heroCtx.fillRect(0, 0, width, height);

  drawGlow(width * 0.78, height * 0.16, width * 0.46, 'rgba(88, 119, 255, 0.12)');
  drawGlow(width * 0.42, height * 0.58, width * 0.34, 'rgba(116, 217, 255, 0.08)');

  for (const star of state.heroStars) {
    const x = (star.x + t * 12 * star.drift) % width;
    const blink = 0.42 + Math.sin(t * 1.7 + star.phase) * 0.26;
    heroCtx.beginPath();
    heroCtx.fillStyle = `rgba(230, 244, 255, ${0.32 + blink})`;
    heroCtx.arc(x, star.y, star.r, 0, Math.PI * 2);
    heroCtx.fill();
  }
}

function drawHeroSolarSystem(width, height, t) {
  const sunX = width * 0.08;
  const sunY = height * 0.3;
  const maxA = width * 0.88;
  const maxB = height * 0.54;
  const scale = Math.max(0.92, Math.min(width / 900, height / 330, 1.22));
  drawSolarSystemOnCanvas(heroCtx, width, height, t, sunX, sunY, maxA, maxB, scale, state.heroPlanetTrails, 1, true);
}

function drawBronzeDingShip(width, height, t) {
  const sunX = width * 0.08;
  const sunY = height * 0.3;
  const orbitA = width * 0.9;
  const orbitB = height * 0.56;
  const centerX = sunX;
  const centerY = sunY;
  const dingOrbitSpeed = 0.18;
  const angle = t * dingOrbitSpeed + Math.PI * 0.08;
  const orbitSin = Math.sin(angle);
  const orbitCos = Math.cos(angle);
  const depth = (orbitSin + 1) / 2;
  const x = centerX + Math.cos(angle) * orbitA;
  const y = centerY + Math.sin(angle) * orbitB;
  const solarScale = Math.max(0.92, Math.min(width / 900, height / 330, 1.22));
  const earthElementWidth = 22 * solarScale;
  const dingReferenceWidth = 178;
  const targetWidth = earthElementWidth * (1 + depth);
  const scale = targetWidth / dingReferenceWidth;
  const velocityAngle = Math.atan2(orbitB * orbitCos, -orbitA * orbitSin);
  const bank = Math.sin(t * 1.6) * 0.05 + orbitCos * 0.08;
  const flightRotation = velocityAngle + Math.PI / 2 + bank;
  const thrust = (0.62 + depth * 0.62) + Math.sin(t * 12.0) * 0.18;
  const visibility = 0.64 + depth * 0.36;

  heroCtx.save();
  heroCtx.globalAlpha = 0.76;
  heroCtx.beginPath();
  heroCtx.strokeStyle = 'rgba(255, 217, 120, 0.34)';
  heroCtx.lineWidth = 3.1;
  heroCtx.ellipse(centerX, centerY, orbitA, orbitB, 0, 0, Math.PI * 2);
  heroCtx.stroke();

  heroCtx.globalAlpha = 0.95;
  heroCtx.beginPath();
  heroCtx.strokeStyle = 'rgba(255, 217, 120, 0.74)';
  heroCtx.lineWidth = 4.6;
  heroCtx.ellipse(centerX, centerY, orbitA, orbitB, 0, 0, Math.PI);
  heroCtx.stroke();

  heroCtx.beginPath();
  heroCtx.strokeStyle = `rgba(116, 217, 255, ${0.14 + depth * 0.12})`;
  heroCtx.lineWidth = 1;
  heroCtx.moveTo(sunX, sunY);
  heroCtx.lineTo(x, y);
  heroCtx.stroke();
  heroCtx.restore();

  for (let i = 0; i < 34; i += 1) {
    const trailAngle = angle - i * 0.074;
    const trailDepth = (Math.sin(trailAngle) + 1) / 2;
    const tx = centerX + Math.cos(trailAngle) * orbitA;
    const ty = centerY + Math.sin(trailAngle) * orbitB;
    const trailFade = 1 - i / 34;
    const trailSize = (1.5 + trailDepth * 3.4) * solarScale * trailFade;
    heroCtx.beginPath();
    heroCtx.fillStyle = `rgba(116, 217, 255, ${0.06 + trailDepth * 0.18 * trailFade})`;
    heroCtx.arc(tx, ty, Math.max(1.1, trailSize), 0, Math.PI * 2);
    heroCtx.fill();
  }

  drawGlow(x, y - 12 * scale, 76 * scale, `rgba(255, 217, 120, ${0.08 + depth * 0.18})`);
  drawGlow(x, y + 12 * scale, 66 * scale, `rgba(116, 217, 255, ${0.07 + depth * 0.18})`);
  heroCtx.save();
  heroCtx.globalAlpha = visibility;
  heroCtx.translate(x, y);
  heroCtx.rotate(flightRotation);
  heroCtx.scale(scale, scale);
  drawDingThrust(thrust, t);
  heroCtx.shadowBlur = 12 + depth * 26;
  heroCtx.shadowColor = `rgba(255, 217, 120, ${0.24 + depth * 0.3})`;
  drawFeichuanBody(t);
  heroCtx.shadowBlur = 0;
  heroCtx.restore();

  drawShipAnnotation('V9', x, y, width, height, scale, visibility);
}

function drawFeichuanBody(t) {
  if (!shipBodyImageReady || shipBodyImage.naturalWidth <= 0) {
    drawDingBody(t);
    return;
  }

  const bodySize = 332;
  heroCtx.drawImage(shipBodyImage, -bodySize / 2, -bodySize / 2 - 2, bodySize, bodySize);
}

function drawDingBody(t) {
  drawDingLeg(-42, 50, -18, 104, -0.15);
  drawDingLeg(42, 50, 18, 104, 0.15);
  drawDingLeg(0, 56, 0, 118, 0);
  drawDingEar(-82, -22, -1);
  drawDingEar(82, -22, 1);

  heroCtx.beginPath();
  const body = heroCtx.createLinearGradient(-74, -48, 74, 78);
  body.addColorStop(0, '#5b3a14');
  body.addColorStop(0.16, '#ffd978');
  body.addColorStop(0.34, '#b88925');
  body.addColorStop(0.58, '#7b521c');
  body.addColorStop(0.78, '#f6c66d');
  body.addColorStop(1, '#3a2810');
  heroCtx.fillStyle = body;
  heroCtx.strokeStyle = 'rgba(255, 236, 171, 0.98)';
  heroCtx.lineWidth = 3.6;
  heroCtx.moveTo(-72, -34);
  heroCtx.bezierCurveTo(-62, 52, -42, 84, 0, 88);
  heroCtx.bezierCurveTo(42, 84, 62, 52, 72, -34);
  heroCtx.bezierCurveTo(42, -48, -42, -48, -72, -34);
  heroCtx.closePath();
  heroCtx.fill();
  heroCtx.stroke();

  heroCtx.save();
  heroCtx.beginPath();
  heroCtx.strokeStyle = 'rgba(116, 217, 255, 0.48)';
  heroCtx.lineWidth = 1.8;
  heroCtx.moveTo(-62, -26);
  heroCtx.bezierCurveTo(-52, 42, -34, 70, 0, 74);
  heroCtx.bezierCurveTo(34, 70, 52, 42, 62, -26);
  heroCtx.stroke();
  heroCtx.restore();

  heroCtx.beginPath();
  heroCtx.ellipse(0, -38, 76, 21, 0, 0, Math.PI * 2);
  heroCtx.fillStyle = '#21180f';
  heroCtx.fill();
  heroCtx.strokeStyle = 'rgba(255, 217, 120, 0.72)';
  heroCtx.stroke();

  const corePulse = 0.55 + Math.sin(t * 3.2) * 0.25;
  drawGlow(0, -66, 26, `rgba(116, 217, 255, ${0.22 + corePulse * 0.22})`);
  heroCtx.beginPath();
  heroCtx.fillStyle = `rgba(181, 236, 255, ${0.68 + corePulse * 0.22})`;
  heroCtx.moveTo(0, -70);
  heroCtx.lineTo(-13, -48);
  heroCtx.lineTo(13, -48);
  heroCtx.closePath();
  heroCtx.fill();

  drawGlow(0, -38, 58, `rgba(116, 217, 255, ${0.22 + corePulse * 0.16})`);
  heroCtx.beginPath();
  heroCtx.ellipse(0, -38, 44, 11, 0, 0, Math.PI * 2);
  heroCtx.strokeStyle = `rgba(116, 217, 255, ${0.65 + corePulse * 0.2})`;
  heroCtx.lineWidth = 2;
  heroCtx.stroke();

  drawDingPatterns(t);
  heroCtx.save();
  heroCtx.font = '900 48px "Microsoft YaHei UI", "Microsoft YaHei", sans-serif';
  heroCtx.textAlign = 'center';
  heroCtx.textBaseline = 'middle';
  heroCtx.shadowBlur = 0;
  heroCtx.shadowColor = 'transparent';
  heroCtx.fillStyle = 'rgba(255, 246, 210, 0.96)';
  heroCtx.strokeStyle = '#000000';
  heroCtx.lineWidth = 4;
  heroCtx.strokeText('鼎', 0, 22);
  heroCtx.fillText('鼎', 0, 22);
  heroCtx.shadowBlur = 0;
  heroCtx.restore();

  heroCtx.beginPath();
  heroCtx.fillStyle = 'rgba(255, 236, 171, 0.26)';
  heroCtx.ellipse(-24, -10, 18, 46, -0.45, 0, Math.PI * 2);
  heroCtx.fill();
}

function drawDingEar(x, y, side) {
  heroCtx.save();
  heroCtx.translate(x, y);
  heroCtx.scale(side, 1);
  heroCtx.beginPath();
  heroCtx.strokeStyle = 'rgba(255, 236, 171, 1)';
  heroCtx.lineWidth = 10;
  heroCtx.arc(0, 0, 32, -Math.PI * 0.7, Math.PI * 0.7);
  heroCtx.stroke();
  heroCtx.beginPath();
  heroCtx.strokeStyle = 'rgba(116, 217, 255, 0.78)';
  heroCtx.lineWidth = 3.2;
  heroCtx.arc(0, 0, 24, -Math.PI * 0.64, Math.PI * 0.64);
  heroCtx.stroke();
  heroCtx.restore();
}

function drawDingLeg(topX, topY, bottomX, bottomY, lean) {
  heroCtx.beginPath();
  const leg = heroCtx.createLinearGradient(topX - 10, topY, bottomX + 10, bottomY);
  leg.addColorStop(0, '#5b3a14');
  leg.addColorStop(0.45, '#ffd978');
  leg.addColorStop(1, '#7b521c');
  heroCtx.fillStyle = leg;
  heroCtx.strokeStyle = 'rgba(255, 236, 171, 0.72)';
  heroCtx.lineWidth = 1.8;
  heroCtx.moveTo(topX - 12, topY);
  heroCtx.lineTo(bottomX - 9 + lean * 20, bottomY);
  heroCtx.lineTo(bottomX + 9 + lean * 20, bottomY);
  heroCtx.lineTo(topX + 12, topY);
  heroCtx.closePath();
  heroCtx.fill();
  heroCtx.stroke();
}

function drawDingThrust(thrust, t) {
  const length = (128 + Math.sin(t * 10) * 18) * thrust;
  const width = 48 + Math.sin(t * 13) * 7;
  const flare = 32 + Math.cos(t * 8) * 5;
  const fire = heroCtx.createRadialGradient(0, 116, 8, 0, 116 + length * 0.46, length * 0.78);
  fire.addColorStop(0, 'rgba(255, 255, 225, 1)');
  fire.addColorStop(0.18, 'rgba(255, 220, 92, 0.98)');
  fire.addColorStop(0.46, 'rgba(255, 160, 28, 0.78)');
  fire.addColorStop(0.76, 'rgba(218, 108, 12, 0.34)');
  fire.addColorStop(1, 'rgba(218, 108, 12, 0)');

  drawGlow(0, 146 + length * 0.22, 82 + length * 0.18, 'rgba(255, 189, 47, 0.26)');
  heroCtx.beginPath();
  heroCtx.fillStyle = fire;
  heroCtx.moveTo(-width, 96);
  heroCtx.quadraticCurveTo(-flare, 132 + length * 0.22, -18, 130 + length * 0.46);
  heroCtx.quadraticCurveTo(-8, 156 + length * 0.66, 0, 116 + length);
  heroCtx.quadraticCurveTo(12, 154 + length * 0.62, 20, 130 + length * 0.46);
  heroCtx.quadraticCurveTo(flare, 132 + length * 0.22, width, 96);
  heroCtx.quadraticCurveTo(18, 112, -width, 96);
  heroCtx.closePath();
  heroCtx.fill();

  const core = heroCtx.createLinearGradient(0, 102, 0, 116 + length * 0.78);
  core.addColorStop(0, 'rgba(255, 255, 236, 1)');
  core.addColorStop(0.34, 'rgba(255, 229, 104, 0.92)');
  core.addColorStop(1, 'rgba(255, 153, 31, 0)');
  heroCtx.beginPath();
  heroCtx.fillStyle = core;
  heroCtx.moveTo(-18, 104);
  heroCtx.quadraticCurveTo(-7, 150 + length * 0.22, 0, 116 + length * 0.78);
  heroCtx.quadraticCurveTo(9, 150 + length * 0.22, 18, 104);
  heroCtx.closePath();
  heroCtx.fill();
}

function drawDingPatterns(t) {
  heroCtx.save();
  heroCtx.strokeStyle = `rgba(116, 217, 255, ${0.22 + Math.sin(t * 2.6) * 0.08})`;
  heroCtx.lineWidth = 1.3;
  for (let side = -1; side <= 1; side += 2) {
    heroCtx.beginPath();
    heroCtx.moveTo(side * 14, -12);
    heroCtx.lineTo(side * 42, -12);
    heroCtx.lineTo(side * 42, 14);
    heroCtx.lineTo(side * 24, 14);
    heroCtx.lineTo(side * 24, 38);
    heroCtx.stroke();
    heroCtx.beginPath();
    heroCtx.arc(side * 34, 42, 8, 0, Math.PI * 2);
    heroCtx.stroke();
  }
  heroCtx.beginPath();
  heroCtx.arc(0, 20, 16, 0, Math.PI * 2);
  heroCtx.stroke();
  heroCtx.restore();
}

function drawShipAnnotation(text, shipX, shipY, width, height, scale, alpha) {
  heroCtx.save();
  heroCtx.globalAlpha = alpha;
  heroCtx.font = '700 13px "Microsoft YaHei UI", "Microsoft YaHei", sans-serif';
  heroCtx.textBaseline = 'middle';
  heroCtx.textAlign = 'left';

  const paddingX = 7;
  const paddingY = 4;
  const labelWidth = Math.ceil(heroCtx.measureText(text).width + paddingX * 2);
  const labelHeight = 24;
  const safeScale = Math.max(0.35, scale);
  const preferredLeft = shipX + 34 * safeScale;
  const left = Math.max(6, Math.min(width - labelWidth - 6, preferredLeft));
  const top = Math.max(6, Math.min(height - labelHeight - 6, shipY - labelHeight - 54 * safeScale));

  heroCtx.fillStyle = 'rgba(3, 5, 10, 0.78)';
  heroCtx.strokeStyle = 'rgba(255, 217, 120, 0.72)';
  heroCtx.lineWidth = 1;
  heroCtx.beginPath();
  heroCtx.moveTo(left + 6, top);
  heroCtx.lineTo(left + labelWidth - 6, top);
  heroCtx.quadraticCurveTo(left + labelWidth, top, left + labelWidth, top + 6);
  heroCtx.lineTo(left + labelWidth, top + labelHeight - 6);
  heroCtx.quadraticCurveTo(left + labelWidth, top + labelHeight, left + labelWidth - 6, top + labelHeight);
  heroCtx.lineTo(left + 6, top + labelHeight);
  heroCtx.quadraticCurveTo(left, top + labelHeight, left, top + labelHeight - 6);
  heroCtx.lineTo(left, top + 6);
  heroCtx.quadraticCurveTo(left, top, left + 6, top);
  heroCtx.closePath();
  heroCtx.fill();
  heroCtx.stroke();

  heroCtx.fillStyle = 'rgba(255, 246, 210, 0.96)';
  heroCtx.fillText(text, left + paddingX, top + labelHeight / 2);
  heroCtx.restore();
}

function drawGlow(x, y, radius, color) {
  drawCanvasGlow(heroCtx, x, y, radius, color);
}

function startBackgroundMusic() {
  if (!backgroundMusic || state.musicStarted) {
    return;
  }
  backgroundMusic.volume = 1.0;
  const promise = backgroundMusic.play();
  if (!promise) {
    state.musicStarted = true;
    return;
  }
  promise
    .then(() => {
      state.musicStarted = true;
    })
    .catch(() => {
      state.musicStarted = false;
    });
}

async function refreshLog() {
  const logNode = $('runtimeLog');
  if (!logNode) {
    return '';
  }
  const log = await window.workspaceRuntime.tailLog(180);
  logNode.textContent = log || '暂无日志。';
  logNode.scrollTop = logNode.scrollHeight;
  return log;
}

function parseCsvLine(line = '') {
  const values = [];
  let current = '';
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if (char === ',' && !quoted) {
      values.push(current);
      current = '';
      continue;
    }
    current += char;
  }
  values.push(current);
  return values;
}

function formatResultPreview(preview = '') {
  const lines = String(preview || '').split(/\r?\n/).filter((line) => line.trim());
  if (!lines.length) {
    return '';
  }
  const header = parseCsvLine(lines[0]).map((field) => field.replace(/^\uFEFF/, '').trim());
  const indexByField = new Map(header.map((field, index) => [field, index]));
  const hasExpectedHeader = RESULT_PREVIEW_FIELDS.some((field) => indexByField.has(field));
  if (!hasExpectedHeader) {
    return preview;
  }
  const translatedHeader = RESULT_PREVIEW_FIELDS.map((field) => RESULT_PREVIEW_LABELS[field] || field).join('，');
  const rows = lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    return RESULT_PREVIEW_FIELDS
      .map((field) => {
        const index = indexByField.get(field);
        return index === undefined ? '' : String(values[index] || '').trim();
      })
      .join('，');
  });
  return [translatedHeader, ...rows].join('\n');
}

async function refreshResults(kind = 'main') {
  state.lastResultKind = kind;
  const result = await window.workspaceRuntime.readResults(kind, 80);
  const target = kind === 'demo' ? $('demoOutput') : $('resultPreview');
  const pathTarget = kind === 'demo' ? null : $('resultPath');
  if (pathTarget) {
    pathTarget.textContent = '';
  }
  if (!target) {
    return result;
  }
  if (!result.exists) {
    target.textContent = '暂无结果文件。';
    return result;
  }
  target.textContent = `数据行：${result.dataRows}\n\n${formatResultPreview(result.preview)}`;
  target.scrollTop = 0;
  return result;
}

function setMetricText(id, value) {
  const node = $(id);
  if (node) {
    node.textContent = value;
  }
}

function setMetricLevel(id, level = '') {
  const node = $(id);
  const card = node ? node.closest('.runtime-metric-card') : null;
  if (!card) {
    return;
  }
  card.classList.remove('metric-good', 'metric-warn', 'metric-bad');
  if (level) {
    card.classList.add(`metric-${level}`);
  }
}

function formatRunElapsed(ms = 0) {
  const totalSeconds = Math.max(0, Math.floor(Number(ms || 0) / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':');
}

function updateRuntimeTimerDisplay() {
  const timerNode = $('runtimeTimer');
  if (!timerNode) {
    return;
  }
  const elapsedMs = state.runTimer.running
    ? Date.now() - state.runTimer.startedAtMs
    : state.runTimer.elapsedMs;
  timerNode.textContent = formatRunElapsed(elapsedMs);
}

function setRuntimeTimerCardState(reason = '') {
  const card = $('runtimeTimer')?.closest('.runtime-timer-card');
  if (!card) {
    return;
  }
  card.classList.remove('timer-stopped', 'timer-circuit');
  if (reason === 'circuit_breaker') {
    card.classList.add('timer-circuit');
  } else if (reason) {
    card.classList.add('timer-stopped');
  }
}

function startRunTimer() {
  state.runTimer.startedAtMs = Date.now();
  state.runTimer.elapsedMs = 0;
  state.runTimer.running = true;
  state.runTimer.terminalReason = '';
  state.completionModalShown = false;
  setRuntimeTimerCardState('');
  updateRuntimeTimerDisplay();
  if (state.runTimer.intervalId) {
    window.clearInterval(state.runTimer.intervalId);
  }
  state.runTimer.intervalId = window.setInterval(updateRuntimeTimerDisplay, 10000);
}

function stopRunTimer(reason = 'completed') {
  if (!state.runTimer.running && state.runTimer.terminalReason) {
    return;
  }
  if (state.runTimer.running) {
    state.runTimer.elapsedMs = Date.now() - state.runTimer.startedAtMs;
  }
  state.runTimer.running = false;
  state.runTimer.terminalReason = reason;
  if (state.runTimer.intervalId) {
    window.clearInterval(state.runTimer.intervalId);
    state.runTimer.intervalId = null;
  }
  setRuntimeTimerCardState(reason);
  updateRuntimeTimerDisplay();
}

function setAnimationSuspended(suspended) {
  state.animationSuspended = Boolean(suspended);
}

function showCompletionModal(metrics = {}) {
  if (state.completionModalShown) {
    return;
  }
  state.completionModalShown = true;
  const raw = metrics.raw || {};
  const values = metrics.values || {};
  const saved = raw.savedTotal ?? values.savedTotal ?? '0';
  const completed = raw.completedTotal ?? values.completedTotal ?? '0';
  const elapsed = formatRunElapsed(state.runTimer.elapsedMs);
  showAppModal(
    `恭喜！\n本次鼎鼎已经为您保存 ${saved} 条。\n总共跑了 ${completed} 条底料。\n本次用时 ${elapsed}。`,
    '采集完成',
    { variant: 'completion', logo: true }
  );
}

function applyRuntimeTerminalReason(reason = '', metrics = {}) {
  if (!reason || !state.runTimer.running) {
    return;
  }
  stopRunTimer(reason);
  state.engineStarted = false;
  setAnimationSuspended(false);
  const startButton = $('startEngine');
  if (startButton) {
    startButton.disabled = false;
  }
  if (reason === 'circuit_breaker') {
    $('engineState').textContent = '已触发连续502熔断，采集已暂停，计时器已停止。';
    return;
  }
  if (reason === 'completed') {
    $('engineState').textContent = '采集已完成，计时器已停止。';
    showCompletionModal(metrics);
    return;
  }
  if (reason === 'failed') {
    $('engineState').textContent = '采集异常停止，计时器已停止。';
  }
}

function updateRuntimeMetricsBoard(metrics = {}) {
  const values = metrics.values || {};
  const levels = metrics.levels || {};
  if (metrics.raw && Object.prototype.hasOwnProperty.call(metrics.raw, 'diagnosticMode')) {
    state.diagnosticModeEnabled = Boolean(metrics.raw.diagnosticMode);
    updateDiagnosticModeButton();
  }
  setMetricText('metricRequestRate', values.requestRate || '0/min');
  setMetricText('metricSaveRate', values.saveRate || '0/min');
  setMetricText('metricAccessSuccessRate', values.accessSuccessRate || '--');
  setMetricText('metric502Rate', values.bad502Rate || '0%');
  setMetricText('metricDoInflight', values.doInflight || '0/0');
  setMetricText('metricRemaining', values.remaining || '0');
  setMetricText('metricSavedTotal', values.savedTotal || '0');
  setMetricText('metricCompletedTotal', values.completedTotal || '0');
  setMetricText('metricCreditCostTotal', values.creditCostTotal || '0');
  setMetricText('metric502RetryTotal', values.http502RetryTotal || '0/0');
  setMetricText('metricWarmExpiredTotal', values.warmExpiredTotal || '0');
  setMetricText('metricLocalWaitSplit', values.localWaitSplit || '0/0ms');
  setMetricText('metricRequestLatency', values.requestLatency || '0/0ms');
  setMetricText('metricOutboundLatency', values.outboundLatency || '0ms');
  setMetricText('metricPageLatencySplit', values.pageLatencySplit || '0/0ms');
  setMetricText('metricRuntimeState', values.runtimeState || '待启动');
  setMetricLevel('metricAccessSuccessRate', levels.accessSuccessRate || '');
  setMetricLevel('metric502Rate', levels.bad502Rate || '');
  setMetricLevel('metricRuntimeState', levels.runtimeState || '');
  applyRuntimeTerminalReason(metrics.terminalReason || '', metrics);
}

function setDiagnosticCardsVisible(visible) {
  document.querySelectorAll('.runtime-diagnostic-card').forEach((card) => {
    card.classList.toggle('hidden', !visible);
  });
}

function updateDiagnosticModeButton() {
  const button = $('toggleDiagnosticMode');
  if (!button) {
    return;
  }
  button.textContent = state.diagnosticModeEnabled ? '调试开' : '调试关';
  button.classList.toggle('pause-active', Boolean(state.diagnosticModeEnabled));
  setDiagnosticCardsVisible(state.diagnosticModeEnabled);
}

function activeWorkCountFromMetrics(metrics = {}) {
  const raw = metrics.raw || {};
  const activeChains = Number(raw.activeChains || raw.status?.active_chain_sessions_current || 0);
  const doCurrent = Number(raw.doCurrent || raw.status?.do_inflight_current || 0);
  const schedulerAliveWorkers = Number(raw.schedulerAliveWorkers || raw.status?.scheduler_alive_workers || 0);
  return Math.max(
    0,
    Number.isFinite(activeChains) ? Math.trunc(activeChains) : 0,
    Number.isFinite(schedulerAliveWorkers) ? Math.trunc(schedulerAliveWorkers) : 0,
    Number.isFinite(doCurrent) ? Math.trunc(doCurrent) : 0
  );
}

function appModalVisible() {
  const modal = $('appModal');
  return Boolean(modal && !modal.classList.contains('hidden'));
}

function setAppModalText(message, title = '') {
  if (title && $('appModalTitle')) {
    $('appModalTitle').textContent = title;
  }
  if ($('appModalMessage')) {
    $('appModalMessage').textContent = message;
  }
}

function pauseDrainMessage(activeCount) {
  return activeCount > 0
    ? `还有 ${activeCount} 底料跑在半路，请让我把半路的继续跑完...`
    : '已暂停';
}

async function refreshPauseDrainStatus() {
  const metrics = await refreshRuntimeMetrics();
  const activeCount = activeWorkCountFromMetrics(metrics || {});
  if (appModalVisible()) {
    setAppModalText(pauseDrainMessage(activeCount), activeCount > 0 ? '正在暂停' : '已暂停');
  }
  if (activeCount <= 0) {
    if (state.pauseDrainTimer) {
      window.clearInterval(state.pauseDrainTimer);
      state.pauseDrainTimer = null;
    }
    state.pauseInFlight = false;
    state.runPaused = true;
    updatePauseButton();
  }
  return activeCount;
}

function startPauseDrainWatcher(initialMetrics = null) {
  const activeCount = activeWorkCountFromMetrics(initialMetrics || {});
  showAppModal(pauseDrainMessage(activeCount), activeCount > 0 ? '正在暂停' : '已暂停');
  if (state.pauseDrainTimer) {
    window.clearInterval(state.pauseDrainTimer);
  }
  if (activeCount <= 0) {
    state.pauseInFlight = false;
    state.runPaused = true;
    updatePauseButton();
    return;
  }
  state.pauseDrainTimer = window.setInterval(refreshPauseDrainStatus, 2000);
}

function stopPauseDrainWatcher() {
  if (state.pauseDrainTimer) {
    window.clearInterval(state.pauseDrainTimer);
    state.pauseDrainTimer = null;
  }
}

async function refreshRuntimeMetrics() {
  if (!window.workspaceRuntime.runtimeMetrics) {
    return null;
  }
  try {
    const metrics = await window.workspaceRuntime.runtimeMetrics();
    updateRuntimeMetricsBoard(metrics);
    return metrics;
  } catch (error) {
    updateRuntimeMetricsBoard({
      values: {
        runtimeState: '监控异常',
      },
      levels: {
        runtimeState: 'bad',
      },
    });
    return null;
  }
}

function startRuntimeMetricsRefresh() {
  refreshRuntimeMetrics();
  if (state.metricsRefreshTimer) {
    return;
  }
    state.metricsRefreshTimer = window.setInterval(refreshRuntimeMetrics, 10000);
}

function updateInputStatus(status = {}) {
  const rowCount = Number(status.row_count || 0);
  const importedRows = Number(status.imported_rows || 0);
  const totalRows = Number(status.total_rows || rowCount || 0);
  const tDualA = Number(status.t_dual_a_row_count || 0);
  const tDualB = Number(status.t_dual_b_row_count || 0);
  const tDualTotal = Number(status.t_dual_total_rows || (tDualA + tDualB) || 0);
  if (state.selectedTargetSource === 'T' && tDualTotal > 0) {
    $('inputImportStatus').textContent = `T通道双底料：A ${tDualA} 行，B ${tDualB} 行，总共 ${tDualTotal} 行`;
    return;
  }
  $('inputImportStatus').textContent = `普通底料：本次导入 ${importedRows} 行，总共 ${totalRows} 行`;
}

function hasUsableInputForSelectedSource(status = {}) {
  const normalTotal = Number(status.total_rows || status.row_count || 0);
  const tDualTotal = Number(status.t_dual_total_rows || 0);
  if (state.confirmedTargetSource === 'T' || state.selectedTargetSource === 'T') {
    return normalTotal > 0 || tDualTotal > 0;
  }
  return normalTotal > 0;
}

function resetAppModalVisual() {
  const panel = document.querySelector('.app-modal-panel');
  if (panel) {
    panel.classList.remove('network-ok', 'network-bad', 'completion');
  }
  const icon = $('appModalIcon');
  if (icon) {
    icon.textContent = '';
    icon.classList.remove('logo-icon');
    icon.classList.add('hidden');
  }
  if (state.modalTimer) {
    clearTimeout(state.modalTimer);
    state.modalTimer = null;
  }
}

function showAppModal(message, title = '提示', options = {}) {
  const modal = $('appModal');
  if (!modal) {
    window.alert(message);
    return;
  }
  resetAppModalVisual();
  state.modalResolver = null;
  const panel = document.querySelector('.app-modal-panel');
  if (panel && options.variant) {
    panel.classList.add(options.variant);
  }
  const icon = $('appModalIcon');
  if (icon && options.icon) {
    icon.textContent = options.icon;
    icon.classList.remove('hidden');
  }
  if (icon && options.logo) {
    icon.textContent = '';
    icon.classList.add('logo-icon');
    icon.classList.remove('hidden');
  }
  $('appModalTitle').textContent = title;
  $('appModalMessage').textContent = message;
  $('appModalCancel').classList.add('hidden');
  $('appModalClose').textContent = '确认';
  modal.classList.remove('hidden');
  $('appModalClose').focus();
  if (options.autoCloseMs) {
    state.modalTimer = setTimeout(() => hideAppModal(true), options.autoCloseMs);
  }
}

function showAppConfirm(message, title = '提示') {
  const modal = $('appModal');
  if (!modal) {
    return Promise.resolve(window.confirm(message));
  }
  resetAppModalVisual();
  $('appModalTitle').textContent = title;
  $('appModalMessage').textContent = message;
  $('appModalCancel').classList.remove('hidden');
  $('appModalCancel').textContent = '否';
  $('appModalClose').textContent = '是';
  modal.classList.remove('hidden');
  $('appModalClose').focus();
  return new Promise((resolve) => {
    state.modalResolver = resolve;
  });
}

function hideAppModal(result = false) {
  const modal = $('appModal');
  resetAppModalVisual();
  if (modal) {
    modal.classList.add('hidden');
  }
  $('appModalCancel').classList.add('hidden');
  $('appModalClose').textContent = '确认';
  if (state.modalResolver) {
    const resolve = state.modalResolver;
    state.modalResolver = null;
    resolve(Boolean(result));
  }
}

function updatePauseButton() {
  const button = $('pauseEngine');
  if (!button) {
    return;
  }
  button.textContent = state.pauseInFlight ? '正在暂停' : state.runPaused ? '恢复采集' : '暂停采集';
  button.disabled = Boolean(state.pauseInFlight);
  button.classList.toggle('pause-active', Boolean(state.runPaused));
}

function updateNetworkStatus(result, checking = false) {
  const qualityNode = $('networkQuality');
  const statusNode = $('networkTestStatus');
  if (qualityNode) {
    qualityNode.classList.remove('network-good', 'network-warn', 'network-bad');
    if (checking) {
      qualityNode.textContent = '检测中';
    } else if (result?.quality) {
      qualityNode.textContent = result.quality;
      qualityNode.classList.add(
        result.quality === '优' ? 'network-good' : result.quality === '良' ? 'network-warn' : 'network-bad'
      );
    } else {
      qualityNode.textContent = '未检测';
    }
  }
  if (!statusNode) {
    return;
  }
  if (checking) {
    statusNode.textContent = '正在进行并发网络压力检测...';
    return;
  }
  if (!result) {
    statusNode.textContent = '启动前会自动进行并发网络压力检测，良或差建议不运行。';
    return;
  }
  const latencyText = result.avgLatencyMs === null || result.avgLatencyMs === undefined
    ? ''
    : `平均延迟 ${result.avgLatencyMs}ms，`;
  const p95Text = result.p95LatencyMs === null || result.p95LatencyMs === undefined
    ? ''
    : `P95 ${result.p95LatencyMs}ms，`;
  const reachabilityText = Number.isFinite(result.successCount) && Number.isFinite(result.totalCount)
    ? `并发 ${result.successCount}/${result.totalCount} 成功，`
    : '';
  const timeoutText = Number.isFinite(result.timeoutCount)
    ? `超时 ${result.timeoutCount}，`
    : '';
  statusNode.textContent = `${reachabilityText}${timeoutText}${latencyText}${p95Text}${result.recommendation || '良或差建议不运行。'}`;
}

function showNetworkResultModal(result) {
  if (result?.canRun) {
    showAppModal('当前网络优秀，符合运行条件。', '网络检测', {
      variant: 'network-ok',
      autoCloseMs: 3600
    });
    return;
  }
  showAppModal('当前网络差，不符合运行条件。', '网络检测', {
    variant: 'network-bad',
    icon: '😭'
  });
}

async function testNetworkQuality({ silent = false } = {}) {
  if (state.networkTestInFlight) {
    return state.networkTestPromise || state.networkTest;
  }
  state.networkTestInFlight = true;
  updateNetworkStatus(state.networkTest, true);
  state.networkTestPromise = window.workspaceRuntime.testNetwork();
  try {
    const result = await state.networkTestPromise;
    state.networkTest = result;
    updateNetworkStatus(result, false);
    if (!silent) {
      showNetworkResultModal(result);
    }
    return result;
  } catch (error) {
    const result = {
      ok: false,
      quality: '差',
      canRun: false,
      avgLatencyMs: null,
      p95LatencyMs: null,
      successCount: 0,
      totalCount: 0,
      timeoutCount: 0,
      recommendation: `网络检测失败：${error.message}。建议不运行。`
    };
    state.networkTest = result;
    updateNetworkStatus(result, false);
    if (!silent) {
      showNetworkResultModal(result);
    }
    return result;
  } finally {
    state.networkTestInFlight = false;
    state.networkTestPromise = null;
  }
}

function normalizeTargetSource(value) {
  const raw = String(value || 'F').trim().toUpperCase();
  if (raw === 'T') {
    return 'T';
  }
  if (raw === 'P') {
    return 'P';
  }
  return 'F';
}

function setTargetSourceSelection(value, confirmed = false) {
  const targetSource = normalizeTargetSource(value);
  state.selectedTargetSource = targetSource;
  if (confirmed) {
    state.confirmedTargetSource = targetSource;
  }
  document.querySelectorAll('input[name="targetSource"]').forEach((input) => {
    input.checked = input.value === targetSource;
  });
  const status = $('targetSourceStatus');
  if (status) {
    status.textContent = confirmed ? `当前通道：${targetSource}` : `待确认通道：${targetSource}`;
  }
  updateInputStatus(state.runtime?.inputStatus || {});
}

async function confirmTargetSource() {
  const selected = document.querySelector('input[name="targetSource"]:checked')?.value || state.selectedTargetSource || 'F';
  const targetSource = normalizeTargetSource(selected);
  const result = await window.workspaceRuntime.setTargetSource(targetSource);
  if (!result.ok) {
    $('targetSourceStatus').textContent = `通道确认失败：${result.error || 'unknown'}`;
    return;
  }
  setTargetSourceSelection(result.targetSource || targetSource, true);
}

async function importInputFile() {
  const button = $('importInput');
  button.disabled = true;
  $('inputImportStatus').textContent = '正在导入底料...';
  try {
    const result = await window.workspaceRuntime.importInputFile();
    if (result.input_status) {
      state.runtime = state.runtime || {};
      state.runtime.inputStatus = result.input_status;
      updateInputStatus(result.input_status);
    }
    if (result.canceled) {
      $('inputImportStatus').textContent = '已取消导入。';
      return;
    }
    if (!result.ok) {
      $('inputImportStatus').textContent = `导入失败：${result.error || '未知错误'}`;
      return;
    }
    updateInputStatus(result.input_status || {});
  } finally {
    button.disabled = false;
  }
}

async function startEngine(auto = false) {
  if (state.engineStarted) {
    return;
  }
  if (!state.confirmedTargetSource || state.selectedTargetSource !== state.confirmedTargetSource) {
    $('targetSourceStatus').textContent = `请先确认通道：${state.selectedTargetSource}`;
    showAppModal('请选择通道T、通道F或通道P，选择后点击确认。通道建议每日轮换，让通道休息有利于减少风控。');
    return;
  }
  if (window.workspaceRuntime.activeRunLock) {
    const lock = await window.workspaceRuntime.activeRunLock();
    if (lock?.active) {
      $('engineState').textContent = '业务引擎已在运行';
      showAppModal('本窗口已经打开，请勿重复打开。', '重复启动');
      startRuntimeMetricsRefresh();
      return;
    }
  }
  const networkResult = await testNetworkQuality({ silent: true });
  if (!networkResult?.canRun) {
    showNetworkResultModal(networkResult);
    return;
  }
  showNetworkResultModal(networkResult);
  const inputStatus = state.runtime?.inputStatus || {};
  if (!auto && !hasUsableInputForSelectedSource(inputStatus)) {
    updateInputStatus(inputStatus);
    if (state.confirmedTargetSource === 'T') {
      showAppModal('T通道未发现可用底料。请把号码放入“号码补齐父级input.txt”或“裂变关联人父级input.txt”，也可以使用普通 input.txt。');
    } else {
      showAppModal('请在“自动分发”文件夹放入TXT，并运行“自动去重自动合并导入底料.cmd”程序后启动采集。');
    }
    return;
  }
  const result = await window.workspaceRuntime.startEngine(state.confirmedTargetSource);
  if (result.alreadyRunning) {
    state.engineStarted = false;
    $('engineState').textContent = '业务引擎已在运行';
    showAppModal(result.message || '本窗口已经打开，请勿重复打开。', '重复启动');
    startRuntimeMetricsRefresh();
    return;
  }
  if (!result.started) {
    state.engineStarted = false;
    $('engineState').textContent = '引擎启动失败。';
    showAppModal(result.error || '引擎启动失败。', '启动失败');
    return;
  }
  state.engineStarted = true;
  if (state.engineStarted) {
    state.runPaused = false;
    setAnimationSuspended(true);
    startRunTimer();
    updatePauseButton();
  }
  $('engineState').textContent = result.alreadyRunning
    ? '业务引擎已在运行'
    : result.console
      ? '引擎已启动，Worker 控制台已打开。'
      : '引擎已启动。';
  $('startEngine').disabled = true;
  if (!auto) {
    await refreshLog();
  }
  startRuntimeMetricsRefresh();
}

async function togglePauseEngine() {
  if (state.pauseInFlight) {
    return;
  }
  if (!state.runPaused) {
    const confirmed = await showAppConfirm(
      '暂停后系统会停止领取新的底料，已经在执行中的任务会继续自然结束。是否确认暂停？',
      '确认暂停采集'
    );
    if (!confirmed) {
      return;
    }
  }

  state.pauseInFlight = true;
  updatePauseButton();
  let keepPauseInFlight = false;
  try {
    const willPause = !state.runPaused;
    const result = state.runPaused
      ? await window.workspaceRuntime.resumeEngine()
      : await window.workspaceRuntime.pauseEngine();
    const ok = Boolean(result.ok && (result.data?.ok !== false) && result.pauseVerified !== false);
    if (!ok) {
      const pauseState = result.pauseState || {};
      const detail = [
        result.error || result.stderr || result.data?.error || '操作失败',
        pauseState.root ? `运行目录：${pauseState.root}` : '',
        pauseState.poolPath ? `底料池：${pauseState.poolPath}` : '',
        Number.isFinite(Number(pauseState.totalAvailable)) ? `可领取：${pauseState.totalAvailable}` : '',
        Number.isFinite(Number(pauseState.totalPausedByUser)) ? `已暂停：${pauseState.totalPausedByUser}` : '',
        typeof pauseState.pauseRequested === 'boolean' ? `暂停标记：${pauseState.pauseRequested ? '是' : '否'}` : '',
      ].filter(Boolean).join('\n');
      showAppModal(detail, state.runPaused ? '恢复失败' : '暂停失败');
      return;
    }
    state.runPaused = willPause;
    if (willPause) {
      $('engineState').textContent = '正在暂停，半路任务会自然跑完。';
      const metrics = await refreshRuntimeMetrics();
      startPauseDrainWatcher(metrics);
      keepPauseInFlight = Boolean(activeWorkCountFromMetrics(metrics || {}) > 0);
      return;
    }
    stopPauseDrainWatcher();
    $('engineState').textContent = state.runPaused
      ? '已暂停领取新底料，运行中的任务会自然结束。'
      : '已恢复采集，可继续领取底料。';
    if (!state.runPaused && state.engineStarted) {
      $('engineState').textContent = '已恢复采集。';
    }
    await refreshRuntimeMetrics();
  } finally {
    if (!keepPauseInFlight) {
      state.pauseInFlight = false;
    }
    updatePauseButton();
  }
}

async function openRuntimeMonitor() {
  if (!window.workspaceRuntime.openRuntimeMonitor) {
    return;
  }
  const result = await window.workspaceRuntime.openRuntimeMonitor();
  if (!result || result.ok === false) {
    showAppModal(result?.error || '看板小窗打开失败。', '运行看板');
  }
}

async function refreshDiagnosticModeStatus() {
  if (!window.workspaceRuntime.diagnosticStatus || !$('toggleDiagnosticMode')) {
    return;
  }
  const result = await window.workspaceRuntime.diagnosticStatus();
  state.diagnosticModeEnabled = Boolean(result.enabled);
  updateDiagnosticModeButton();
}

async function resetDiagnosticModeDefaultOff() {
  state.diagnosticModeEnabled = false;
  updateDiagnosticModeButton();
  if (!window.workspaceRuntime.setDiagnosticEnabled || !$('toggleDiagnosticMode')) {
    return;
  }
  const result = await window.workspaceRuntime.setDiagnosticEnabled(false);
  if (!result.ok) {
    console.warn('diagnostic mode default-off reset failed:', result.error || 'unknown');
  }
  state.diagnosticModeEnabled = false;
  updateDiagnosticModeButton();
}

async function toggleDiagnosticMode() {
  if (!window.workspaceRuntime.setDiagnosticEnabled) {
    return;
  }
  const result = await window.workspaceRuntime.setDiagnosticEnabled(!state.diagnosticModeEnabled);
  if (!result.ok) {
    showAppModal(result.error || '调试模式开关写入失败。', '调试模式');
    return;
  }
  state.diagnosticModeEnabled = Boolean(result.enabled);
  updateDiagnosticModeButton();
  await refreshRuntimeMetrics();
}

async function handleAppCloseRequest() {
  if (state.closeInProgress) {
    return;
  }
  const confirmed = await showAppConfirm('是否关闭本窗口？', '关闭确认');
  if (!confirmed) {
    if (window.workspaceRuntime.cancelCloseRequest) {
      await window.workspaceRuntime.cancelCloseRequest();
    }
    return;
  }
  state.closeInProgress = true;
  if (state.pauseDrainTimer) {
    stopPauseDrainWatcher();
  }
  $('engineState').textContent = '正在关闭。';
  try {
    await window.workspaceRuntime.gracefulClose();
  } catch (error) {
    state.closeInProgress = false;
    if (window.workspaceRuntime.cancelCloseRequest) {
      await window.workspaceRuntime.cancelCloseRequest();
    }
    showAppModal(`关闭失败：${error.message || error}`, '关闭失败');
  }
}

async function startDemo() {
  if (state.engineStarted) {
    return;
  }
  state.demoStarted = true;
  const result = await window.workspaceRuntime.startDemo();
  state.engineStarted = result.started || result.alreadyRunning;
  $('demoOutput').textContent = result.alreadyRunning
    ? '已有引擎正在运行。'
    : '本地演示已启动，等待 Python 输出...';
  if ($('engineState')) {
    $('engineState').textContent = result.alreadyRunning ? '业务引擎已在运行' : '本地演示已启动。';
  }
  await refreshResults('demo');
}

function unlockApp(status) {
  if (state.appUnlocked) {
    return;
  }
  state.appUnlocked = true;
  state.lastValidLicense = status;
  $('licenseLayer').classList.add('hidden');
  $('appShell').classList.remove('locked');
  state.heroSceneStartMs = performance.now();
  resizeHeroCanvas();
  createHeroStars();
  startBackgroundMusic();
  $('authState').textContent = status.valid
    ? `有效，剩余 ${status.remaining_days} 天`
    : '未授权';
  setWindowLimit(status);
  setTargetSourceSelection(state.runtime?.data?.target_source || state.runtime?.data?.runtime?.target_source || 'F', false);
  updateInputStatus(state.runtime?.inputStatus || {});
  $('engineState').textContent = '授权通过，请确认通道后点击启动采集。';
  updatePauseButton();
  refreshDiagnosticModeStatus();
  startRuntimeMetricsRefresh();
  testNetworkQuality({ silent: true });
}

function showCompletionModalPreview() {
  unlockApp({ valid: true, remaining_days: 30, max_instances: 1 });
  state.runTimer.elapsedMs = (1 * 3600 + 23 * 60 + 45) * 1000;
  state.runTimer.running = false;
  updateRuntimeTimerDisplay();
  showCompletionModal({
    raw: {
      savedTotal: 8868,
      completedTotal: 10000,
    },
  });
}

async function checkLicense() {
  try {
    state.runtime = await window.workspaceRuntime.runtimeInfo();
    if (state.runtime?.data?.preview_completion_modal) {
      showCompletionModalPreview();
      return;
    }
    $('licenseRoot').textContent = state.runtime?.instanceRoot || state.runtime?.data?.root || '未获取';
    const runtimeMachineCode = state.runtime?.data?.machine_code || '';
    setMachineCode(runtimeMachineCode);

    const result = await window.workspaceRuntime.licenseStatus();
    const status = result.data || {};
    setMachineCode(status.machine_code || runtimeMachineCode);
    setWindowLimit(status);
    if (!result.data) {
      const detail = result.error || result.stderr || 'Electron 未收到 Python 授权状态';
      setLicenseMessage(`授权检测失败：${detail}`, 'error');
      $('licenseForm').classList.remove('hidden');
      return;
    }

    if (status.valid) {
      state.lastValidLicense = status;
      $('enterApp').classList.remove('hidden');
      setLicenseMessage(`授权有效，已授权 ${status.max_instances || 1} 并发。请点击“进入主程序”。`, 'ok');
      return;
    }

    setLicenseMessage(displayLicenseReason(status.reason), 'error');
    $('licenseForm').classList.remove('hidden');
  } catch (error) {
    setLicenseMessage(`授权检测异常：${error.message}`, 'error');
    $('licenseForm').classList.remove('hidden');
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
  const result = await window.workspaceRuntime.activateLicense(code);
  const status = result.data || {};
  setMachineCode(status.machine_code || $('copyMachineCode').dataset.copyValue || '');
  setWindowLimit(status);
  if (status.valid) {
    state.lastValidLicense = status;
    $('enterApp').classList.remove('hidden');
    $('licenseForm').classList.add('hidden');
    setLicenseMessage(`授权成功，已授权 ${status.max_instances || 1} 并发。请点击“进入主程序”。`, 'ok');
  } else {
    setLicenseMessage(displayLicenseReason(status.reason, '授权码无效'), 'error');
  }
}

window.addEventListener('resize', () => {
  resizeCanvas();
  createParticles();
  resizeHeroCanvas();
  createHeroStars();
});

window.addEventListener('mousemove', (event) => {
  state.mouse.x = event.clientX / UI_SCALE;
  state.mouse.y = event.clientY / UI_SCALE;
});

window.addEventListener('pointerdown', startBackgroundMusic);
window.addEventListener('keydown', startBackgroundMusic);

$('licenseForm').addEventListener('submit', activateLicense);
$('copyMachineCode').addEventListener('click', copyMachineCode);
$('enterApp').addEventListener('click', () => {
  if (state.lastValidLicense) {
    unlockApp(state.lastValidLicense);
  }
});
if ($('importInput')) {
  $('importInput').addEventListener('click', importInputFile);
}
$('confirmTargetSource').addEventListener('click', confirmTargetSource);
document.querySelectorAll('input[name="targetSource"]').forEach((input) => {
  input.addEventListener('change', () => setTargetSourceSelection(input.value, false));
});
$('appModalClose').addEventListener('click', () => hideAppModal(true));
$('appModalCancel').addEventListener('click', () => hideAppModal(false));
$('appModal').addEventListener('click', (event) => {
  if (event.target === $('appModal')) {
    hideAppModal(false);
  }
});
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') {
    hideAppModal(false);
  }
});
$('startEngine').addEventListener('click', () => startEngine(false));
if ($('pauseEngine')) {
  $('pauseEngine').addEventListener('click', togglePauseEngine);
  updatePauseButton();
}
if ($('openRuntimeMonitor')) {
  $('openRuntimeMonitor').addEventListener('click', openRuntimeMonitor);
}
if ($('toggleDiagnosticMode')) {
  $('toggleDiagnosticMode').addEventListener('click', toggleDiagnosticMode);
  resetDiagnosticModeDefaultOff();
}
$('startDemo').addEventListener('click', startDemo);
$('refreshDemoResults').addEventListener('click', () => refreshResults('demo'));

window.workspaceRuntime.onEngineStdout((value) => {
  const logNode = $('runtimeLog');
  if (logNode) {
    logNode.textContent += value;
    logNode.scrollTop = logNode.scrollHeight;
  }
  if (state.demoStarted) {
    $('demoOutput').textContent += value;
    $('demoOutput').scrollTop = $('demoOutput').scrollHeight;
  }
});
window.workspaceRuntime.onEngineStderr((value) => {
  const logNode = $('runtimeLog');
  if (logNode) {
    logNode.textContent += value;
    logNode.scrollTop = logNode.scrollHeight;
  }
  if (state.demoStarted) {
    $('demoOutput').textContent += value;
    $('demoOutput').scrollTop = $('demoOutput').scrollHeight;
  }
});
window.workspaceRuntime.onEngineExit((event) => {
  setAnimationSuspended(false);
  stopRunTimer(event?.code === 0 ? 'completed' : 'failed');
  $('engineState').textContent = event?.code === 0
    ? '业务引擎已完成，客户端保持打开，计时器已停止。'
    : `业务引擎已退出，退出码 ${event.code}。客户端保持打开，计时器已停止。`;
  $('startEngine').disabled = false;
  state.engineStarted = false;
  refreshLog();
  refreshResults(state.demoStarted ? 'demo' : 'main');
  refreshRuntimeMetrics().then((metrics) => {
    if (event?.code === 0) {
      showCompletionModal(metrics || {});
    }
  });
});
if (window.workspaceRuntime.onAppCloseRequest) {
  window.workspaceRuntime.onAppCloseRequest(handleAppCloseRequest);
}

resizeCanvas();
createParticles();
resizeHeroCanvas();
createHeroStars();
animateParticles();
animateHeroScene();
checkLicense();
refreshResults('demo');



