const canvas = document.getElementById("pond");
const ctx = canvas.getContext("2d");
const statusEl = document.getElementById("status");
const speed = document.getElementById("speed");
const speedValue = document.getElementById("speedValue");
const deliberation = document.getElementById("deliberation");
const reset = document.getElementById("reset");
const randomize = document.getElementById("randomize");
const clearSelection = document.getElementById("clearSelection");

const FRAME_POLL_MS = 320;
const STATE_POLL_MS = 2600;
const INTERPOLATION_DELAY_MS = 280;
const TAU = Math.PI * 2;

let latestState = null;
let latestEnvironment = null;
let previousFrame = null;
let currentFrame = null;
let fieldCanvas = document.createElement("canvas");
let fieldSignature = "";
let frameFetchInFlight = false;
let stateFetchInFlight = false;
let hoverFishId = null;
let selectedFishId = null;
let compareFishId = null;
let renderedFish = [];
const historySamples = {
  adults: [],
  eggs: [],
  lineages: [],
  policies: [],
};

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(720, Math.floor(rect.width * ratio));
  canvas.height = Math.max(480, Math.floor(rect.height * ratio));
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();

canvas.addEventListener("mousemove", (event) => {
  const rect = canvas.getBoundingClientRect();
  const x = event.clientX - rect.left;
  const y = event.clientY - rect.top;
  hoverFishId = hitTestFish(x, y);
});

canvas.addEventListener("mouseleave", () => {
  hoverFishId = null;
});

canvas.addEventListener("click", (event) => {
  if (hoverFishId === null) {
    compareFishId = null;
    selectedFishId = null;
    return;
  }
  if (event.ctrlKey || event.metaKey) {
    if (selectedFishId === null || selectedFishId === hoverFishId) {
      selectedFishId = hoverFishId;
      compareFishId = null;
    } else {
      compareFishId = hoverFishId;
    }
  } else {
    selectedFishId = hoverFishId;
    compareFishId = null;
  }
});

async function postControl(payload) {
  const response = await fetch("/api/control", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const state = await response.json();
  applyState(state);
}

speed.addEventListener("input", () => {
  speedValue.textContent = `${speed.value}x`;
});

speed.addEventListener("change", () => {
  postControl({ speed: Number(speed.value) });
});

deliberation.addEventListener("change", () => {
  postControl({ deliberation_enabled: deliberation.checked });
});

reset.addEventListener("click", () => postControl({ action: "reset" }));
randomize.addEventListener("click", () => postControl({ action: "randomize_environment" }));
clearSelection.addEventListener("click", () => {
  selectedFishId = null;
  compareFishId = null;
});

function syncControls(state) {
  speed.value = state.config.speed;
  speedValue.textContent = `${state.config.speed}x`;
  deliberation.checked = Boolean(state.config.deliberation_enabled);
}

async function fetchState() {
  if (stateFetchInFlight) return;
  stateFetchInFlight = true;
  try {
    const response = await fetch("/api/state");
    applyState(await response.json());
    statusEl.textContent = "live";
  } catch (error) {
    statusEl.textContent = "offline";
  } finally {
    stateFetchInFlight = false;
  }
}

async function fetchFrame() {
  if (frameFetchInFlight) return;
  frameFetchInFlight = true;
  try {
    const response = await fetch("/api/frame");
    applyFrame(await response.json());
    statusEl.textContent = "live";
  } catch (error) {
    statusEl.textContent = "offline";
  } finally {
    frameFetchInFlight = false;
  }
}

function applyState(state) {
  latestState = state;
  latestEnvironment = state.environment;
  syncControls(state);
  applyFrame({
    schema: "aquagenesys.frame.from_state",
    tick: state.tick,
    config: state.config,
    environment: { width: state.environment.width, height: state.environment.height, signature: state.environment.signature },
    fish: state.fish || state.organisms || [],
    eggs: state.eggs || [],
    telemetry: state.telemetry,
  });
  updateTelemetry(state.telemetry);
  updateDashboard(state.dashboard, state.telemetry);
}

function applyFrame(frame) {
  if (currentFrame && frame.tick < currentFrame.tick) return;
  previousFrame = currentFrame;
  currentFrame = { ...frame, receivedAt: performance.now() };
  updateTelemetry(frame.telemetry);
}

async function pollState() {
  await fetchState();
  window.setTimeout(pollState, STATE_POLL_MS);
}

async function pollFrame() {
  await fetchFrame();
  window.setTimeout(pollFrame, FRAME_POLL_MS);
}

function updateTelemetry(telemetry) {
  if (!telemetry) return;
  const puddleState = document.getElementById("puddleState");
  puddleState.hidden = telemetry.biosphere_state === "active";
  puddleState.textContent =
    telemetry.biosphere_state === "dormant"
      ? "DORMANT BIOSPHERE - viable egg bank"
      : "DEAD PUDDLE - chemistry still running";
  document.getElementById("tick").textContent = telemetry.tick;
  document.getElementById("population").textContent = telemetry.adult_population ?? telemetry.population;
  document.getElementById("eggCount").textContent = telemetry.egg_count ?? 0;
  document.getElementById("viableEggs").textContent = telemetry.viable_egg_count ?? 0;
  document.getElementById("dormantEggs").textContent = telemetry.dormant_egg_count ?? 0;
  document.getElementById("births").textContent = telemetry.births ?? 0;
  document.getElementById("eggsHatched").textContent = telemetry.eggs_hatched ?? 0;
  document.getElementById("lineages").textContent = telemetry.lineage_count ?? 0;
  document.getElementById("health").textContent = Number(telemetry.average_health || 0).toFixed(2);
  document.getElementById("stress").textContent = Number(telemetry.average_stress || 0).toFixed(2);
  const instruction = telemetry.instruction || {};
  document.getElementById("policyVariants").textContent = instruction.policy_variants_alive ?? 0;
  document.getElementById("teachingEvents").textContent = instruction.teaching_events ?? 0;
  updateAiStatus(telemetry);
  recordHistory(telemetry);
}

function updateAiStatus(telemetry) {
  const node = document.getElementById("aiStatus");
  if (!node) return;
  const model = telemetry?.model || {};
  if (!model.enabled) {
    node.textContent = "AI deliberation unavailable";
    return;
  }
  if ((model.calls || 0) <= 0) {
    node.textContent = "AI deliberation enabled; no calls yet";
    return;
  }
  if ((model.pending || 0) > 0) {
    node.textContent = "AI deliberation enabled; model calls active";
    return;
  }
  if ((model.failures || 0) > 0 && (model.successes || 0) <= 0) {
    node.textContent = "AI deliberation enabled; recent calls failed";
    return;
  }
  node.textContent = "AI deliberation enabled; bounded reflections visible";
}

function recordHistory(telemetry) {
  pushHistory("adults", telemetry.adult_population ?? telemetry.population ?? 0);
  pushHistory("eggs", telemetry.egg_count ?? 0);
  pushHistory("lineages", telemetry.lineage_count ?? 0);
  pushHistory("policies", telemetry.instruction?.policy_variants_alive ?? 0);
  renderSparkline("adultSpark", historySamples.adults);
  renderSparkline("eggSpark", historySamples.eggs);
  renderSparkline("lineageSpark", historySamples.lineages);
  renderSparkline("policySpark", historySamples.policies);
}

function pushHistory(key, value) {
  const series = historySamples[key];
  const numeric = Number(value) || 0;
  if (series[series.length - 1] !== numeric) {
    series.push(numeric);
  }
  while (series.length > 36) series.shift();
}

function renderSparkline(id, values) {
  const node = document.getElementById(id);
  if (!node) return;
  const max = Math.max(1, ...values);
  node.innerHTML = "";
  for (const value of values.slice(-28)) {
    const bar = document.createElement("i");
    bar.style.height = `${Math.max(10, (Number(value) / max) * 100)}%`;
    node.appendChild(bar);
  }
}

function updateDashboard(dashboard, telemetry) {
  if (!dashboard) return;
  const narrator = dashboard.narrator || {};
  document.getElementById("narratorHeadline").textContent = narrator.headline || "Ecology state is still warming up.";
  fillPlainList("narratorPoints", narrator.points || []);
  const population = dashboard.population || {};
  document.getElementById("populationTrend").textContent = labelize(population.trend || "unknown");
  document.getElementById("reproductionPressure").textContent = labelize(population.reproduction_pressure || "unknown");
  document.getElementById("eggBankResilience").textContent = labelize(population.egg_bank_resilience || "none");
  document.getElementById("biosphereState").textContent = labelize(population.biosphere_state || telemetry?.biosphere_state || "unknown");
  updateRecoveryEvidence(dashboard.recovery || {});
  fillList("topLineages", dashboard.lineages?.top || [], (item) => [
    `Lineage ${item.lineage_id}`,
    `${item.adults} adults / ${item.viable_eggs} eggs / ${labelize(item.policy_label)}`,
  ]);
  fillList("topPolicies", dashboard.policies?.families || [], (item) => [
    labelize(item.label),
    `${item.count} adults (${Math.round(Number(item.share || 0) * 100)}%)`,
  ]);
  const teaching = dashboard.teaching || {};
  fillList(
    "teachingSummary",
    [
      ["inheritance deliveries", teaching.inheritance_events ?? 0],
      ["accepted patches", teaching.patches_accepted ?? 0],
      ["rejected patches", teaching.patches_rejected ?? 0],
    ],
    (item) => [labelize(item[0]), item[1]],
  );
  fillTimeline("timeline", dashboard.events || []);
  fillList("gates", dashboard.diagnostics?.gate_failures || [], (item) => [labelize(item.reason), item.count]);
  fillList("instructionRejections", dashboard.diagnostics?.patch_rejections || [], (item) => [labelize(item.reason), item.count]);
  const model = dashboard.diagnostics?.model || {};
  fillList(
    "modelDiagnostics",
    [
      ["model calls", model.calls ?? 0],
      ["pending", model.pending ?? 0],
      ["failures", model.failures ?? 0],
    ],
    (item) => [labelize(item[0]), item[1]],
  );
}

function updateRecoveryEvidence(recovery) {
  document.getElementById("recoveryPhase").textContent = labelize(recovery.phase || "warming");
  document.getElementById("recoveryMechanism").textContent = labelize(recovery.mechanism || "not yet visible");
  document.getElementById("recoveryAdultTrend").textContent = labelize(recovery.adult_trend || "-");
  document.getElementById("recoveryEggTrend").textContent = labelize(recovery.egg_trend || "-");
  document.getElementById("recoveryResource").textContent = labelize(recovery.resource_rebound || "-");
  document.getElementById("recoveryCrowding").textContent = labelize(recovery.crowding_state || "-");
  document.getElementById("recoveryGate").textContent = labelize(recovery.gate_pressure || "none");
  document.getElementById("recoveryPolicy").textContent = labelize(recovery.dominant_policy || "none");
  fillPlainList("recoveryEvidence", recovery.evidence || []);
}

function fillList(id, items, render) {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = "";
  for (const item of items.slice(0, 8)) {
    const [left, right] = render(item);
    const li = document.createElement("li");
    const label = document.createElement("span");
    const value = document.createElement("b");
    label.textContent = left;
    value.textContent = right;
    li.append(label, value);
    node.appendChild(li);
  }
}

function fillPlainList(id, items) {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = "";
  for (const item of items.slice(0, 6)) {
    const li = document.createElement("li");
    const label = document.createElement("span");
    label.textContent = item;
    li.appendChild(label);
    node.appendChild(li);
  }
}

function fillTimeline(id, items) {
  const node = document.getElementById(id);
  if (!node) return;
  node.innerHTML = "";
  for (const item of items.slice(0, 16)) {
    const li = document.createElement("li");
    li.classList.add(item.severity || "info");
    if (item.fish_id) {
      li.dataset.fishId = item.fish_id;
      li.addEventListener("click", () => {
        selectedFishId = Number(item.fish_id);
        compareFishId = null;
      });
    }
    const label = document.createElement("span");
    const title = document.createElement("b");
    const detail = document.createElement("em");
    title.textContent = `${item.tick} ${labelize(item.type)} - ${labelize(item.title)}`;
    detail.textContent = item.detail || (item.lineage_id ? `lineage ${item.lineage_id}` : "");
    label.append(title, detail);
    const value = document.createElement("b");
    value.textContent = item.fish_id ? `#${item.fish_id}` : item.lineage_id ? `L${item.lineage_id}` : "";
    li.append(label, value);
    node.appendChild(li);
  }
}

function labelize(value) {
  return String(value || "-").replaceAll("_", " ").replaceAll("-", " ");
}

function rebuildField(env) {
  if (!env || !env.fields) return;
  const signature = JSON.stringify(env.signature);
  if (signature === fieldSignature) return;
  fieldSignature = signature;
  const viewWidth = env.view_width || env.width;
  const viewHeight = env.view_height || env.height;
  fieldCanvas.width = viewWidth;
  fieldCanvas.height = viewHeight;
  const fctx = fieldCanvas.getContext("2d");
  const image = fctx.createImageData(viewWidth, viewHeight);
  const fields = env.fields;
  let i = 0;
  for (let y = 0; y < viewHeight; y += 1) {
    for (let x = 0; x < viewWidth; x += 1) {
      const depth = fields.depth[y][x];
      const oxygen = fields.oxygen[y][x];
      const temperature = fields.temperature[y][x];
      const food = fields.food[y][x];
      const plankton = fields.plankton[y][x];
      const toxins = fields.toxins[y][x];
      const turbidity = fields.turbidity[y][x];
      const shelter = fields.shelter[y][x];
      const obstacle = fields.obstacle[y][x];
      const pressure = fields.population_pressure[y][x];
      image.data[i++] = Math.min(255, 18 + temperature * 88 + toxins * 122 + shelter * 44 + obstacle * 80);
      image.data[i++] = Math.min(255, 30 + food * 96 + plankton * 90 + oxygen * 74 - turbidity * 28);
      image.data[i++] = Math.min(255, 46 + depth * 134 + oxygen * 42 + pressure * 80);
      image.data[i++] = 255;
    }
  }
  fctx.putImageData(image, 0, 0);
}

function render() {
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  const frame = currentFrame;
  const env = latestEnvironment || frame?.environment;
  if (!frame || !env) {
    requestAnimationFrame(render);
    return;
  }
  rebuildField(latestEnvironment);
  ctx.imageSmoothingEnabled = false;
  if (fieldCanvas.width > 0) {
    ctx.drawImage(fieldCanvas, 0, 0, rect.width, rect.height);
  }
  ctx.imageSmoothingEnabled = true;

  const sx = rect.width / env.width;
  const sy = rect.height / env.height;
  drawShelters(latestEnvironment?.shelter_centers || [], sx, sy);
  const fishList = interpolatedFish(performance.now());
  drawEggs(frame.eggs || [], sx, sy);
  drawFish(fishList, sx, sy);
  updateInspector();
  if (frame.telemetry?.dead_puddle) {
    drawDeadPuddle(rect);
  }
  requestAnimationFrame(render);
}

function interpolatedFish(now) {
  const current = currentFrame;
  if (!current) return [];
  const previous = previousFrame;
  const priorById = new Map((previous?.fish || []).map((fish) => [fish.id, fish]));
  const frameDeltaMs = previous ? Math.max(160, current.receivedAt - previous.receivedAt) : 1000;
  const tickDelta = previous ? Math.max(1, current.tick - previous.tick) : 1;
  const ticksPerMs = tickDelta / frameDeltaMs;
  const renderTime = now - INTERPOLATION_DELAY_MS;
  return current.fish.map((fish) => {
    const prior = priorById.get(fish.id);
    let x = fish.x;
    let y = fish.y;
    if (prior && renderTime >= previous.receivedAt && renderTime <= current.receivedAt) {
      const alpha = clamp((renderTime - previous.receivedAt) / frameDeltaMs, 0, 1);
      x = prior.x + (fish.x - prior.x) * alpha;
      y = prior.y + (fish.y - prior.y) * alpha;
    } else if (renderTime > current.receivedAt) {
      const dtTicks = clamp((renderTime - current.receivedAt) * ticksPerMs, 0, 2.4);
      x = fish.x + fish.vx * dtTicks;
      y = fish.y + fish.vy * dtTicks;
    }
    return { ...fish, renderX: x, renderY: y, locomotion: interpolatedLocomotion(fish, prior, renderTime, frameDeltaMs) };
  });
}

function interpolatedLocomotion(fish, prior, renderTime, frameDeltaMs) {
  const current = locomotionFor(fish);
  if (!prior?.locomotion || !previousFrame) return current;
  const previousMotion = locomotionFor(prior);
  if (renderTime < previousFrame.receivedAt || renderTime > currentFrame.receivedAt) return current;
  const alpha = clamp((renderTime - previousFrame.receivedAt) / frameDeltaMs, 0, 1);
  return {
    heading: interpolateAngle(previousMotion.heading, current.heading, alpha),
    turn_rate: previousMotion.turn_rate + (current.turn_rate - previousMotion.turn_rate) * alpha,
    swim_phase: unwrapPhase(previousMotion.swim_phase, current.swim_phase, alpha),
    tail_beat: previousMotion.tail_beat + (current.tail_beat - previousMotion.tail_beat) * alpha,
    body_wave: previousMotion.body_wave + (current.body_wave - previousMotion.body_wave) * alpha,
    speed: previousMotion.speed + (current.speed - previousMotion.speed) * alpha,
    stride: previousMotion.stride + (current.stride - previousMotion.stride) * alpha,
  };
}

function drawShelters(centers, sx, sy) {
  ctx.save();
  ctx.strokeStyle = "rgba(210, 220, 190, 0.18)";
  ctx.fillStyle = "rgba(28, 34, 28, 0.18)";
  for (const shelter of centers) {
    ctx.beginPath();
    ctx.ellipse(shelter.x * sx, shelter.y * sy, shelter.radius * sx, shelter.radius * sy * 0.7, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function drawFish(fishList, sx, sy) {
  renderedFish = [];
  for (const fish of fishList) {
    const x = fish.renderX * sx;
    const y = fish.renderY * sy;
    const r = Math.max(3.4, fish.radius * Math.min(sx, sy));
    const phenotype = phenotypeFor(fish);
    const locomotion = locomotionFor(fish);
    const bodyLength = r * phenotype.body_length;
    const bodyDepth = r * phenotype.body_depth;
    const tailLength = r * phenotype.tail_length;
    renderedFish.push({ id: fish.id, x, y, r: Math.max(bodyLength + tailLength, bodyDepth) * 1.28, fish });
    const angle = locomotion.heading;
    const pulse = Math.sin(locomotion.swim_phase);
    const bodyBend = pulse * (0.05 + locomotion.body_wave * 0.10);
    const isHover = fish.id === hoverFishId;
    const isSelected = fish.id === selectedFishId;
    const isCompared = fish.id === compareFishId;
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate(angle + pulse * locomotion.body_wave * 0.025);

    const healthAlpha = 0.46 + fish.health * 0.46;
    drawWake(phenotype, locomotion, bodyLength, bodyDepth, tailLength);
    drawTail(phenotype, bodyLength, bodyDepth, tailLength, pulse, healthAlpha);
    drawFins(phenotype, bodyLength, bodyDepth, r, pulse, healthAlpha);

    ctx.globalAlpha = 1;
    ctx.fillStyle = phenotype.primary_color;
    ctx.strokeStyle = stateColor(fish.body_state);
    ctx.lineWidth = Math.max(1, r * 0.12);
    bodyPath(phenotype, bodyLength, bodyDepth, bodyBend);
    ctx.fill();
    ctx.stroke();

    ctx.save();
    bodyPath(phenotype, bodyLength, bodyDepth, bodyBend);
    ctx.clip();
    drawCounterShade(phenotype, bodyLength, bodyDepth);
    drawPattern(phenotype, fish.id, bodyLength, bodyDepth);
    drawIridescence(phenotype, bodyLength, bodyDepth, pulse);
    ctx.restore();

    ctx.fillStyle = "rgba(10, 15, 16, 0.74)";
    ctx.beginPath();
    ctx.arc(bodyLength * 0.37, -bodyDepth * 0.20, Math.max(1.1, r * 0.10 * phenotype.eye_scale), 0, Math.PI * 2);
    ctx.fill();

    if (phenotype.barbel_length > 0.18) {
      drawBarbels(phenotype, bodyLength, bodyDepth, r, pulse);
    }

    if (fish.genome.metabolism === "predator") {
      ctx.fillStyle = "rgba(20, 8, 8, 0.75)";
      ctx.beginPath();
      ctx.moveTo(bodyLength * 0.42, -bodyDepth * 0.26);
      ctx.lineTo(bodyLength * 0.60, 0);
      ctx.lineTo(bodyLength * 0.42, bodyDepth * 0.26);
      ctx.closePath();
      ctx.fill();
    }

    if (fish.decision.source === "model" || fish.active_intent) {
      ctx.strokeStyle = "rgba(255, 239, 150, 0.82)";
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(0, 0, (bodyLength + tailLength) * 0.72, bodyDepth * 1.45, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    if (isHover || isSelected || isCompared) {
      ctx.strokeStyle = isSelected
        ? "rgba(255, 255, 255, 0.95)"
        : isCompared
          ? "rgba(230, 176, 93, 0.94)"
          : "rgba(123, 212, 176, 0.85)";
      ctx.lineWidth = isSelected || isCompared ? 2 : 1;
      ctx.beginPath();
      ctx.ellipse(0, 0, (bodyLength + tailLength) * 0.80, bodyDepth * 1.72, 0, 0, Math.PI * 2);
      ctx.stroke();
    }
    ctx.restore();
  }
}

function drawEggs(eggs, sx, sy) {
  ctx.save();
  for (const egg of eggs) {
    if (egg.state === "dead" || egg.state === "hatched") continue;
    const x = egg.x * sx;
    const y = egg.y * sy;
    const alpha = Math.max(0.18, Math.min(0.72, egg.viability || 0.4));
    const radius = Math.max(1.6, Math.min(4.8, 1.4 + (egg.energy_investment || 4) * 0.12));
    ctx.fillStyle = egg.dormant ? `rgba(205, 178, 124, ${alpha})` : `rgba(220, 230, 170, ${alpha})`;
    ctx.strokeStyle = egg.parthenogenetic ? "rgba(255, 220, 240, 0.62)" : "rgba(40, 35, 24, 0.28)";
    ctx.lineWidth = egg.parthenogenetic ? 1.2 : 0.6;
    ctx.beginPath();
    ctx.ellipse(x, y, radius * 1.25, radius * 0.78, ((egg.egg_id || 1) % 9) * 0.3, 0, TAU);
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}

function locomotionFor(fish) {
  const fallbackHeading = Math.atan2(fish.vy || 0, fish.vx || 0.001);
  return {
    heading: fallbackHeading,
    turn_rate: 0,
    swim_phase: (currentFrame?.tick || 0) * 0.3 + fish.id,
    tail_beat: Math.min(1, Math.hypot(fish.vx || 0, fish.vy || 0)),
    body_wave: 0.2,
    speed: Math.hypot(fish.vx || 0, fish.vy || 0),
    stride: Math.hypot(fish.vx || 0, fish.vy || 0),
    ...(fish.locomotion || {}),
  };
}

function phenotypeFor(fish) {
  return {
    shape: "torpedo",
    pattern: "speckled",
    tail: "rounded",
    fins: "short",
    body_length: 1.55,
    body_depth: 0.72,
    tail_length: 0.70,
    fin_span: 0.60,
    stripe_count: 4,
    spot_count: 7,
    pattern_density: 0.42,
    pattern_contrast: 0.48,
    iridescence: 0.18,
    camouflage: 0.45,
    eye_scale: 0.72,
    barbel_length: 0.0,
    primary_color: fish.genome?.color || "#9ecb8a",
    accent_color: fish.genome?.accent_color || "#203c32",
    ...(fish.phenotype || fish.genome?.phenotype || {}),
  };
}

function bodyPath(phenotype, length, depth, bend = 0) {
  const tailY = -bend * depth * 0.68;
  const midY = bend * depth * 0.30;
  const noseY = -bend * depth * 0.16;
  ctx.beginPath();
  if (phenotype.shape === "ribbon") {
    ctx.moveTo(length * 0.52, noseY);
    ctx.bezierCurveTo(length * 0.22, -depth * 0.52 + midY, -length * 0.44, -depth * 0.34 + tailY, -length * 0.56, tailY);
    ctx.bezierCurveTo(-length * 0.44, depth * 0.34 + tailY, length * 0.22, depth * 0.52 + midY, length * 0.52, noseY);
  } else if (phenotype.shape === "heavy") {
    ctx.moveTo(length * 0.55, noseY);
    ctx.bezierCurveTo(length * 0.20, -depth * 0.98 + midY, -length * 0.54, -depth * 0.82 + tailY, -length * 0.64, tailY);
    ctx.bezierCurveTo(-length * 0.54, depth * 0.82 + tailY, length * 0.20, depth * 0.98 + midY, length * 0.55, noseY);
  } else if (phenotype.shape === "leaf" || phenotype.shape === "deep") {
    ctx.moveTo(length * 0.50, noseY);
    ctx.bezierCurveTo(length * 0.12, -depth * 0.88 + midY, -length * 0.52, -depth * 0.72 + tailY, -length * 0.58, tailY);
    ctx.bezierCurveTo(-length * 0.52, depth * 0.72 + tailY, length * 0.12, depth * 0.88 + midY, length * 0.50, noseY);
  } else {
    ctx.moveTo(length * 0.58, noseY);
    ctx.bezierCurveTo(length * 0.20, -depth * 0.70 + midY, -length * 0.50, -depth * 0.54 + tailY, -length * 0.62, tailY);
    ctx.bezierCurveTo(-length * 0.50, depth * 0.54 + tailY, length * 0.20, depth * 0.70 + midY, length * 0.58, noseY);
  }
  ctx.closePath();
}

function drawTail(phenotype, length, depth, tailLength, pulse, alpha) {
  const root = -length * 0.56;
  const tip = root - tailLength * (1.0 + Math.abs(pulse) * 0.05);
  const spread = depth * (0.54 + phenotype.fin_span * 0.22);
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.fillStyle = mixAlpha(phenotype.accent_color, 0.72);
  ctx.strokeStyle = phenotype.accent_color;
  ctx.lineWidth = Math.max(1, depth * 0.10);
  ctx.beginPath();
  if (phenotype.tail === "forked" || phenotype.tail === "lunate") {
    ctx.moveTo(root, 0);
    ctx.lineTo(tip, -spread);
    ctx.lineTo(tip + tailLength * 0.34, 0);
    ctx.lineTo(tip, spread);
    ctx.closePath();
  } else if (phenotype.tail === "spade" || phenotype.tail === "fan") {
    ctx.moveTo(root, 0);
    ctx.quadraticCurveTo(tip + tailLength * 0.22, -spread * 1.08, tip, 0);
    ctx.quadraticCurveTo(tip + tailLength * 0.22, spread * 1.08, root, 0);
  } else {
    ctx.moveTo(root, 0);
    ctx.quadraticCurveTo(tip + tailLength * 0.12, -spread * 0.86, tip, pulse * depth * 0.08);
    ctx.quadraticCurveTo(tip + tailLength * 0.12, spread * 0.86, root, 0);
  }
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawWake(phenotype, locomotion, length, depth, tailLength) {
  if (locomotion.speed < 0.10 && locomotion.tail_beat < 0.15) return;
  ctx.save();
  ctx.globalAlpha = Math.min(0.26, 0.05 + locomotion.speed * 0.18 + locomotion.tail_beat * 0.06);
  ctx.strokeStyle = "rgba(215, 245, 238, 0.42)";
  ctx.lineWidth = Math.max(1, depth * 0.055);
  const base = -length * 0.55 - tailLength * 0.80;
  for (let i = 0; i < 3; i += 1) {
    const offset = i * tailLength * 0.34;
    const spread = depth * (0.25 + i * 0.13);
    ctx.beginPath();
    ctx.moveTo(base - offset, -spread);
    ctx.quadraticCurveTo(base - offset - tailLength * 0.30, 0, base - offset, spread);
    ctx.stroke();
  }
  ctx.restore();
}

function drawFins(phenotype, length, depth, r, pulse, alpha) {
  const span = depth * phenotype.fin_span;
  const swept = phenotype.fins === "swept" ? 0.36 : phenotype.fins === "spiked" ? -0.16 : 0.10;
  ctx.save();
  ctx.globalAlpha = Math.min(0.78, alpha * (phenotype.fins === "glass" ? 0.44 : 0.70));
  ctx.fillStyle = mixAlpha(phenotype.accent_color, phenotype.fins === "glass" ? 0.28 : 0.48);
  ctx.strokeStyle = phenotype.accent_color;
  ctx.lineWidth = Math.max(1, r * 0.08);
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(-length * 0.04, side * depth * 0.18);
    ctx.lineTo(-length * (0.18 + swept), side * (depth * 0.18 + span * (0.74 + pulse * 0.05)));
    ctx.lineTo(length * 0.16, side * depth * 0.26);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
  }
  ctx.beginPath();
  ctx.moveTo(-length * 0.12, -depth * 0.58);
  ctx.lineTo(-length * 0.26, -depth * (0.58 + phenotype.fin_span * 0.44));
  ctx.lineTo(length * 0.12, -depth * 0.54);
  ctx.closePath();
  ctx.fill();
  ctx.restore();
}

function drawCounterShade(phenotype, length, depth) {
  ctx.fillStyle = "rgba(255, 255, 255, 0.11)";
  ctx.beginPath();
  ctx.ellipse(0, -depth * 0.24, length * 0.50, depth * 0.24, 0, Math.PI, Math.PI * 2);
  ctx.fill();
  if (phenotype.pattern === "countershade") {
    ctx.fillStyle = "rgba(12, 28, 30, 0.18)";
    ctx.fillRect(-length * 0.62, -depth, length * 1.2, depth * 0.92);
  }
}

function drawPattern(phenotype, fishId, length, depth) {
  const contrast = clamp(phenotype.pattern_contrast, 0, 1);
  ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.20 + contrast * 0.58);
  ctx.fillStyle = mixAlpha(phenotype.accent_color, 0.18 + contrast * 0.50);
  ctx.lineWidth = Math.max(1, depth * (0.045 + contrast * 0.035));
  if (phenotype.pattern === "striped" || phenotype.pattern === "banded") {
    const count = phenotype.stripe_count || 5;
    for (let i = 0; i < count; i += 1) {
      const x = -length * 0.43 + (i / Math.max(1, count - 1)) * length * 0.78;
      ctx.beginPath();
      if (phenotype.pattern === "banded") {
        ctx.moveTo(x, -depth * 0.66);
        ctx.lineTo(x + length * 0.07, depth * 0.66);
      } else {
        ctx.moveTo(x, -depth * 0.54);
        ctx.quadraticCurveTo(x + length * 0.04, 0, x - length * 0.02, depth * 0.54);
      }
      ctx.stroke();
    }
    return;
  }
  if (phenotype.pattern === "saddle") {
    for (let i = 0; i < 3; i += 1) {
      const x = -length * 0.32 + i * length * 0.28;
      ctx.beginPath();
      ctx.ellipse(x, -depth * 0.34, length * 0.12, depth * 0.26, -0.24, 0, Math.PI * 2);
      ctx.fill();
    }
    return;
  }
  const count = phenotype.spot_count || 8;
  for (let i = 0; i < count; i += 1) {
    const t = (i + 1) / (count + 1);
    const x = -length * 0.46 + t * length * 0.86;
    const wave = Math.sin(fishId * 1.7 + i * 2.31);
    const y = wave * depth * 0.36;
    const size = depth * (0.055 + ((i + fishId) % 4) * 0.012);
    ctx.beginPath();
    ctx.arc(x, y, size, 0, Math.PI * 2);
    ctx.fill();
  }
}

function drawIridescence(phenotype, length, depth, pulse) {
  const shine = clamp(phenotype.iridescence, 0, 1);
  if (shine <= 0.08) return;
  ctx.strokeStyle = `rgba(210, 245, 255, ${0.08 + shine * 0.18})`;
  ctx.lineWidth = Math.max(1, depth * 0.045);
  ctx.beginPath();
  ctx.moveTo(-length * 0.38, -depth * (0.18 + pulse * 0.02));
  ctx.quadraticCurveTo(0, -depth * 0.42, length * 0.40, -depth * 0.18);
  ctx.stroke();
}

function drawBarbels(phenotype, length, depth, r, pulse) {
  const len = r * phenotype.barbel_length * 1.25;
  ctx.save();
  ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.74);
  ctx.lineWidth = Math.max(1, r * 0.055);
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.moveTo(length * 0.45, side * depth * 0.18);
    ctx.quadraticCurveTo(length * 0.56, side * (depth * 0.26 + pulse * r * 0.06), length * 0.45 + len, side * depth * 0.50);
    ctx.stroke();
  }
  ctx.restore();
}

function mixAlpha(color, alpha) {
  const rgb = hexToRgb(color);
  if (!rgb) return `rgba(170, 210, 180, ${alpha})`;
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
}

function hexToRgb(color) {
  const raw = String(color || "").replace("#", "");
  if (raw.length !== 6) return null;
  const value = Number.parseInt(raw, 16);
  if (Number.isNaN(value)) return null;
  return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
}

function normalizeAngle(angle) {
  let result = angle;
  while (result <= -Math.PI) result += TAU;
  while (result > Math.PI) result -= TAU;
  return result;
}

function interpolateAngle(from, to, alpha) {
  return normalizeAngle(from + normalizeAngle(to - from) * alpha);
}

function unwrapPhase(from, to, alpha) {
  let delta = to - from;
  if (delta < -Math.PI) delta += TAU;
  if (delta > Math.PI) delta -= TAU;
  const value = from + delta * alpha;
  return ((value % TAU) + TAU) % TAU;
}

function hitTestFish(x, y) {
  let best = null;
  let bestDistance = Infinity;
  for (const item of renderedFish) {
    const dx = x - item.x;
    const dy = y - item.y;
    const distance = Math.hypot(dx, dy);
    if (distance <= item.r && distance < bestDistance) {
      best = item.id;
      bestDistance = distance;
    }
  }
  return best;
}

function updateInspector() {
  const fish = findFish(selectedFishId) || findFish(hoverFishId);
  const empty = document.getElementById("emptyInspector");
  const details = document.getElementById("fishInspector");
  if (!fish) {
    empty.hidden = false;
    details.hidden = true;
    updateCompare();
    return;
  }
  empty.hidden = true;
  details.hidden = false;
  document.getElementById("fishId").textContent = `#${fish.id} L${fish.lineage} G${fish.generation}`;
  document.getElementById("fishSpecies").textContent = `${fish.species_id} / ${fish.genome.archetype}`;
  document.getElementById("fishBody").textContent = `${fish.body_state} ${fish.genome.metabolism}`;
  const phenotype = phenotypeFor(fish);
  document.getElementById("fishPhenotype").textContent = `${phenotype.shape} / ${phenotype.tail} / ${phenotype.pattern}`;
  document.getElementById("fishTraits").textContent = `fin ${Number(phenotype.fin_span).toFixed(2)} camo ${Number(phenotype.camouflage).toFixed(2)}`;
  const locomotion = locomotionFor(fish);
  document.getElementById("fishMotion").textContent = `spd ${Number(locomotion.speed).toFixed(2)} turn ${Number(locomotion.turn_rate).toFixed(2)}`;
  const life = fish.life_history || {};
  document.getElementById("fishLifecycle").textContent =
    `${fish.maturity_state || "-"} / ${fish.fertility_state || "-"} clutch ${life.base_clutch_size ?? "-"}`;
  document.getElementById("fishRepro").textContent =
    `cool ${fish.reproduction_cooldown ?? 0} gate ${String(fish.last_reproduction_gate || "-").replaceAll("_", " ")}`;
  document.getElementById("fishEggTraits").textContent =
    `dorm ${Number(life.dormancy_bias || 0).toFixed(2)} parth ${life.parthenogenesis_alleles ?? 0}`;
  const instruction = fish.instruction || fish.instruction_genome || {};
  document.getElementById("fishPolicy").textContent =
    `${instruction.policy_hash_short || "-"} ${instruction.policy_label || ""}`;
  document.getElementById("fishStrategy").textContent =
    `${instruction.risk_posture || "-"} / ${String(instruction.forage_strategy || "-").replaceAll("_", "-")} / ${String(instruction.energy_strategy || "-").replaceAll("_", "-")}`;
  document.getElementById("fishTeaching").textContent =
    `${String(instruction.teaching_style || "-").replaceAll("_", "-")} skills ${instruction.skill_count ?? (fish.taught_skills || []).length ?? 0} acc ${instruction.accepted_patches ?? fish.instruction_lineage?.accepted_patch_ids?.length ?? 0} rej ${instruction.rejected_patches ?? fish.instruction_lineage?.rejected_patch_ids?.length ?? 0}`;
  document.getElementById("fishDecision").textContent = `${fish.decision.source}: ${fish.decision.kind}`;
  document.getElementById("fishIntent").textContent = fish.active_intent
    ? `${fish.active_intent.kind} ttl ${fish.model_intent_ttl}`
    : fish.model_pending
      ? "pending"
      : "none";
  document.getElementById("fishEnergy").textContent = `${Number(fish.energy).toFixed(1)} / h ${Number(fish.hunger).toFixed(2)}`;
  document.getElementById("fishLineageContext").textContent = lineageContextFor(fish);
  document.getElementById("fishExplain").textContent = explainFish(fish);
  updateCompare();
}

function findFish(id) {
  if (id === null || !currentFrame) return null;
  return (currentFrame.fish || []).find((fish) => fish.id === id) || null;
}

function lineageContextFor(fish) {
  const hints = latestState?.dashboard?.focus_hints || {};
  const adults = hints.lineage_adults?.[String(fish.lineage)] ?? "-";
  const eggs = hints.lineage_viable_eggs?.[String(fish.lineage)] ?? 0;
  const nearby = hints.nearby?.[fish.id];
  const neighbor = nearby ? ` near #${nearby.fish_id} (${nearby.distance})` : "";
  return `L${fish.lineage}: ${adults} adults / ${eggs} viable eggs${neighbor}`;
}

function explainFish(fish) {
  const decision = fish.decision || {};
  const gate = fish.last_reproduction_gate ? ` Repro gate: ${labelize(fish.last_reproduction_gate)}.` : "";
  const intent = fish.active_intent ? ` Carrying model intent ${fish.active_intent.kind}.` : "";
  return `${labelize(decision.source)} chose ${labelize(decision.kind)} because ${decision.reason || "local reflex/habit policy"}.${gate}${intent}`;
}

function updateCompare() {
  const panel = document.getElementById("comparePanel");
  const primary = findFish(selectedFishId);
  const secondary = findFish(compareFishId);
  if (!primary || !secondary || primary.id === secondary.id) {
    panel.hidden = true;
    return;
  }
  panel.hidden = false;
  renderCompareSummary(primary, secondary);
  renderCompareDetails("compareA", primary);
  renderCompareDetails("compareB", secondary);
}

function renderCompareSummary(a, b) {
  const node = document.getElementById("compareSummary");
  const rows = compareRelationship(a, b);
  node.innerHTML = "";
  for (const text of rows.slice(0, 5)) {
    const p = document.createElement("p");
    p.textContent = text;
    node.appendChild(p);
  }
}

function renderCompareDetails(id, fish) {
  const node = document.getElementById(id);
  const phenotype = phenotypeFor(fish);
  const instruction = fish.instruction || fish.instruction_genome || {};
  const rows = [
    ["ID", `#${fish.id} L${fish.lineage} G${fish.generation}`],
    ["Body", `${fish.genome.archetype} ${phenotype.shape}`],
    ["Lifecycle", `${fish.maturity_state} / ${fish.fertility_state}`],
    ["State", `E ${Number(fish.energy).toFixed(1)} H ${Number(fish.health).toFixed(2)} S ${Number(fish.stress).toFixed(2)}`],
    ["Policy", `${instruction.policy_hash_short || "-"} ${instruction.policy_label || ""}`],
    ["Strategy", `${labelize(instruction.risk_posture)} / ${labelize(instruction.forage_strategy)} / ${labelize(instruction.energy_strategy)}`],
    ["Action", `${fish.decision.source}: ${fish.decision.kind}`],
  ];
  node.innerHTML = "";
  for (const [label, value] of rows) {
    const wrapper = document.createElement("div");
    const dt = document.createElement("dt");
    const dd = document.createElement("dd");
    dt.textContent = label;
    dd.textContent = value;
    wrapper.append(dt, dd);
    node.appendChild(wrapper);
  }
}

function compareRelationship(a, b) {
  const rows = [];
  const distance = Math.hypot((a.renderX ?? a.x) - (b.renderX ?? b.x), (a.renderY ?? a.y) - (b.renderY ?? b.y));
  if (a.lineage === b.lineage) rows.push(`Same lineage L${a.lineage}; compare inherited policy drift and lifecycle state.`);
  else rows.push(`Different lineages: L${a.lineage} versus L${b.lineage}.`);
  const aInstruction = a.instruction || {};
  const bInstruction = b.instruction || {};
  if (aInstruction.policy_hash_short && aInstruction.policy_hash_short === bInstruction.policy_hash_short) {
    rows.push(`They share policy ${aInstruction.policy_hash_short} (${labelize(aInstruction.policy_label)}).`);
  } else {
    rows.push(`Policy split: ${labelize(aInstruction.policy_label)} versus ${labelize(bInstruction.policy_label)}.`);
  }
  if (a.genome.metabolism !== b.genome.metabolism) {
    rows.push(`Different feeding roles: ${a.genome.metabolism} versus ${b.genome.metabolism}.`);
  } else {
    rows.push(`Both use the ${a.genome.metabolism} feeding role and may compete for similar resources.`);
  }
  if (distance < 8) rows.push(`They are nearby on screen, so schooling, mating, or resource competition may be relevant.`);
  const fertility = `${a.fertility_state}/${b.fertility_state}`;
  rows.push(`Fertility comparison: A/B = ${fertility}.`);
  return rows;
}

function stateColor(state) {
  if (state === "failing") return "rgba(255, 110, 116, 0.86)";
  if (state === "starving") return "rgba(235, 185, 84, 0.82)";
  if (state === "panicked") return "rgba(130, 210, 255, 0.82)";
  if (state === "breeding") return "rgba(228, 168, 235, 0.84)";
  return "rgba(236, 250, 244, 0.58)";
}

function drawDeadPuddle(rect) {
  ctx.save();
  ctx.fillStyle = "rgba(30, 10, 12, 0.22)";
  ctx.fillRect(0, 0, rect.width, rect.height);
  ctx.restore();
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

pollState();
pollFrame();
render();
