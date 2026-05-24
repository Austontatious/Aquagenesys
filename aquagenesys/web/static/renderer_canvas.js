(function () {
  "use strict";

  const TAU = Math.PI * 2;
  const QUALITY = ["minimum", "low", "medium", "high"];
  const QUALITY_SETTINGS = {
    high: { dprCap: 1.8, particles: 54, appendageScale: 1.0, backgroundAlpha: 1.0, simpleDepth: 0.22, frameBudget: 22 },
    medium: { dprCap: 1.5, particles: 32, appendageScale: 0.72, backgroundAlpha: 0.96, simpleDepth: 0.34, frameBudget: 26 },
    low: { dprCap: 1.25, particles: 14, appendageScale: 0.42, backgroundAlpha: 0.90, simpleDepth: 0.52, frameBudget: 31 },
    minimum: { dprCap: 1.0, particles: 0, appendageScale: 0.0, backgroundAlpha: 0.82, simpleDepth: 0.76, frameBudget: 38 },
  };

  function init(canvas, options = {}) {
    return new ReefCanvasRenderer(canvas, options);
  }

  class ReefCanvasRenderer {
    constructor(canvas, options) {
      this.canvas = canvas;
      this.ctx = canvas.getContext("2d");
      this.options = {
        backgroundUrl: "/static/assets/reef-bg.webp",
        cacheEnabled: true,
        adaptiveQuality: true,
        forcedQuality: "",
        debug: false,
        ...options,
      };
      this.width = 1;
      this.height = 1;
      this.dpr = 1;
      this.frame = null;
      this.previousFrame = null;
      this.environment = null;
      this.renderedFish = [];
      this.depthByFish = new Map();
      this.cache = new Map();
      this.cacheHits = 0;
      this.cacheMisses = 0;
      this.selectedId = null;
      this.hoveredId = null;
      this.compareId = null;
      this.frameTimes = [];
      this.rafDeltas = [];
      this.lastRenderAt = 0;
      this.quality = normalizeQuality(this.options.forcedQuality) || "high";
      this.lastQualityChangeAt = 0;
      this.backgroundImage = new Image();
      this.backgroundReady = false;
      this.backgroundFailed = false;
      this.backgroundImage.onload = () => {
        this.backgroundReady = true;
      };
      this.backgroundImage.onerror = () => {
        this.backgroundFailed = true;
      };
      if (this.options.backgroundUrl) {
        this.backgroundImage.src = this.options.backgroundUrl;
      } else {
        this.backgroundFailed = true;
      }
      this.particles = makeParticles(64);
    }

    dprCap() {
      return QUALITY_SETTINGS[this.quality].dprCap;
    }

    resize(width, height, devicePixelRatio = window.devicePixelRatio || 1) {
      this.width = Math.max(1, width);
      this.height = Math.max(1, height);
      this.dpr = Math.min(devicePixelRatio || 1, this.dprCap());
      this.canvas.width = Math.max(720, Math.floor(this.width * this.dpr));
      this.canvas.height = Math.max(480, Math.floor(this.height * this.dpr));
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      return { width: this.width, height: this.height, dpr: this.dpr };
    }

    updateFrame(framePayload, stateLookup = {}) {
      if (this.frame && framePayload.tick < this.frame.tick) return;
      this.previousFrame = this.frame;
      this.frame = { ...framePayload, receivedAt: performance.now() };
      this.environment = stateLookup.environment || this.environment || framePayload.environment || null;
    }

    updateEnvironment(environment) {
      if (environment) this.environment = environment;
    }

    setSelected(id) {
      this.selectedId = id;
    }

    setHovered(id) {
      this.hoveredId = id;
    }

    setCompare(id) {
      this.compareId = id;
    }

    setSelection({ selectedId = null, hoveredId = null, compareId = null } = {}) {
      this.selectedId = selectedId;
      this.hoveredId = hoveredId;
      this.compareId = compareId;
    }

    render(now = performance.now()) {
      const started = performance.now();
      const ctx = this.ctx;
      const frame = this.frame;
      const env = this.environment || frame?.environment;
      ctx.clearRect(0, 0, this.width, this.height);
      if (!frame || !env) {
        this.drawFallbackBackground(now);
        this.finishPerf(started, now);
        return;
      }
      this.drawBackground(env, now);
      this.drawAmbient(env, now);
      this.drawEggs(frame.eggs || [], env, now);
      this.drawFish(frame.fish || [], env, now);
      if (frame.telemetry?.dead_puddle) this.drawDeadOverlay();
      this.finishPerf(started, now);
    }

    hitTest(x, y) {
      let best = null;
      let bestDistance = Infinity;
      for (const item of this.renderedFish) {
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

    getRenderedFish() {
      return this.renderedFish.slice();
    }

    getPerfStats() {
      const frames = this.frameTimes.slice(-90);
      const rafFrames = this.rafDeltas.slice(-90);
      const avg = frames.length ? frames.reduce((sum, value) => sum + value, 0) / frames.length : 0;
      const avgRaf = rafFrames.length ? rafFrames.reduce((sum, value) => sum + value, 0) / rafFrames.length : 0;
      return {
        renderer: "reef-v0",
        quality: this.quality,
        dpr: round(this.dpr, 2),
        fps: avgRaf > 0 ? round(1000 / avgRaf, 1) : 0,
        average_frame_ms: round(avg, 2),
        p95_frame_ms: round(percentile(frames, 0.95), 2),
        average_raf_ms: round(avgRaf, 2),
        p95_raf_ms: round(percentile(rafFrames, 0.95), 2),
        visible_organisms: this.renderedFish.length,
        cache_hits: this.cacheHits,
        cache_misses: this.cacheMisses,
        cache_size: this.cache.size,
        background_ready: this.backgroundReady,
        background_failed: this.backgroundFailed,
      };
    }

    destroy() {
      this.cache.clear();
      this.renderedFish = [];
    }

    drawBackground(env, now) {
      const ctx = this.ctx;
      const settings = QUALITY_SETTINGS[this.quality];
      if (this.backgroundReady && !this.backgroundFailed) {
        drawCoverImage(ctx, this.backgroundImage, this.width, this.height, settings.backgroundAlpha);
      } else {
        this.drawFallbackBackground(now);
      }
      const pulse = this.quality === "minimum" ? 0 : 0.025 + Math.sin(now * 0.00035) * 0.012;
      const gradient = ctx.createRadialGradient(this.width * 0.52, this.height * 0.38, 20, this.width * 0.50, this.height * 0.50, Math.max(this.width, this.height) * 0.72);
      gradient.addColorStop(0, `rgba(75, 230, 210, ${0.045 + pulse})`);
      gradient.addColorStop(0.48, "rgba(30, 42, 88, 0.10)");
      gradient.addColorStop(1, "rgba(0, 3, 12, 0.52)");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, this.width, this.height);
      if (env.fields && this.quality !== "minimum") this.drawFieldVeil(env);
    }

    drawFallbackBackground(now) {
      const ctx = this.ctx;
      const gradient = ctx.createLinearGradient(0, 0, 0, this.height);
      gradient.addColorStop(0, "#03111f");
      gradient.addColorStop(0.46, "#061827");
      gradient.addColorStop(1, "#02050b");
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, this.width, this.height);
      ctx.save();
      ctx.globalAlpha = this.quality === "minimum" ? 0.10 : 0.18;
      ctx.strokeStyle = "rgba(70, 180, 180, 0.22)";
      ctx.lineWidth = 1;
      const spacing = this.quality === "low" || this.quality === "minimum" ? 86 : 58;
      const drift = (now * 0.006) % spacing;
      for (let x = -spacing; x < this.width + spacing; x += spacing) {
        ctx.beginPath();
        ctx.moveTo(x + drift, 0);
        ctx.lineTo(x - drift * 0.25, this.height);
        ctx.stroke();
      }
      for (let y = 0; y < this.height; y += spacing) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(this.width, y + Math.sin(y * 0.03) * 8);
        ctx.stroke();
      }
      ctx.restore();
    }

    drawFieldVeil(env) {
      const fields = env.fields;
      if (!fields?.plankton || !fields?.toxins) return;
      const viewWidth = env.view_width || fields.plankton[0]?.length || 1;
      const viewHeight = env.view_height || fields.plankton.length || 1;
      const cellW = this.width / viewWidth;
      const cellH = this.height / viewHeight;
      const step = this.quality === "high" ? 3 : 5;
      this.ctx.save();
      for (let y = 0; y < viewHeight; y += step) {
        for (let x = 0; x < viewWidth; x += step) {
          const plankton = fields.plankton[y]?.[x] || 0;
          const toxins = fields.toxins[y]?.[x] || 0;
          const oxygen = fields.oxygen?.[y]?.[x] || 0;
          const alpha = Math.max(0, plankton * 0.030 + oxygen * 0.018 - toxins * 0.018);
          if (alpha <= 0.012) continue;
          this.ctx.fillStyle = `rgba(${50 + plankton * 70}, ${145 + oxygen * 75}, ${170 + plankton * 40}, ${alpha})`;
          this.ctx.fillRect(x * cellW, y * cellH, cellW * step, cellH * step);
        }
      }
      this.ctx.restore();
    }

    drawAmbient(env, now) {
      const count = QUALITY_SETTINGS[this.quality].particles;
      if (!count) return;
      this.ctx.save();
      for (let i = 0; i < count; i += 1) {
        const particle = this.particles[i % this.particles.length];
        const x = ((particle.x + Math.sin(now * 0.00007 + particle.phase) * 0.020) % 1) * this.width;
        const y = ((particle.y - now * particle.speed * 0.000005 + 1) % 1) * this.height;
        const size = particle.size * (this.quality === "high" ? 1.0 : 0.72);
        this.ctx.fillStyle = `rgba(125, 240, 226, ${particle.alpha})`;
        this.ctx.beginPath();
        this.ctx.arc(x, y, size, 0, TAU);
        this.ctx.fill();
      }
      this.ctx.restore();
    }

    drawEggs(eggs, env, now) {
      const sx = this.width / env.width;
      const sy = this.height / env.height;
      this.ctx.save();
      for (const egg of eggs) {
        if (egg.state === "dead" || egg.state === "hatched") continue;
        const depth = this.depthFor({ id: `egg-${egg.egg_id}`, species_id: "egg", lineage: egg.lineage || egg.lineage_id || 0, y: egg.y }, env);
        const scale = 0.62 + depth * 0.55;
        const alpha = Math.max(0.16, Math.min(0.68, egg.viability || 0.4)) * (0.40 + depth * 0.58);
        const radius = Math.max(1.2, Math.min(4.4, (1.4 + (egg.energy_investment || 4) * 0.12) * scale));
        this.ctx.fillStyle = egg.dormant ? `rgba(202, 178, 122, ${alpha})` : `rgba(205, 244, 178, ${alpha})`;
        this.ctx.strokeStyle = egg.parthenogenetic ? "rgba(255, 218, 245, 0.62)" : "rgba(94, 220, 190, 0.24)";
        this.ctx.lineWidth = depth > 0.72 ? 1.2 : 0.6;
        this.ctx.beginPath();
        this.ctx.ellipse(egg.x * sx, egg.y * sy, radius * 1.25, radius * 0.78, ((egg.egg_id || 1) % 9) * 0.3 + now * 0.0001, 0, TAU);
        this.ctx.fill();
        this.ctx.stroke();
      }
      this.ctx.restore();
    }

    drawFish(fishList, env, now) {
      const sx = this.width / env.width;
      const sy = this.height / env.height;
      const fish = this.interpolateFish(now).map((item) => ({
        ...item,
        renderDepth: this.depthFor(item, env),
      }));
      fish.sort((a, b) => a.renderDepth - b.renderDepth);
      this.renderedFish = [];
      for (const item of fish) {
        this.drawOrganism(item, sx, sy, now);
      }
    }

    interpolateFish(now) {
      const current = this.frame;
      if (!current) return [];
      const previous = this.previousFrame;
      const priorById = new Map((previous?.fish || []).map((fish) => [fish.id, fish]));
      const frameDeltaMs = previous ? Math.max(160, current.receivedAt - previous.receivedAt) : 1000;
      const tickDelta = previous ? Math.max(1, current.tick - previous.tick) : 1;
      const ticksPerMs = tickDelta / frameDeltaMs;
      const renderTime = now - 280;
      return (current.fish || []).map((fish) => {
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
        return { ...fish, renderX: x, renderY: y, locomotion: this.locomotionFor(fish, prior, renderTime, frameDeltaMs) };
      });
    }

    locomotionFor(fish, prior, renderTime, frameDeltaMs) {
      const fallbackHeading = Math.atan2(fish.vy || 0, fish.vx || 0.001);
      const current = {
        heading: fallbackHeading,
        turn_rate: 0,
        swim_phase: (this.frame?.tick || 0) * 0.3 + fish.id,
        tail_beat: Math.min(1, Math.hypot(fish.vx || 0, fish.vy || 0)),
        body_wave: 0.2,
        speed: Math.hypot(fish.vx || 0, fish.vy || 0),
        stride: Math.hypot(fish.vx || 0, fish.vy || 0),
        ...(fish.locomotion || {}),
      };
      if (!prior?.locomotion || !this.previousFrame) return current;
      if (renderTime < this.previousFrame.receivedAt || renderTime > this.frame.receivedAt) return current;
      const previousMotion = {
        heading: Math.atan2(prior.vy || 0, prior.vx || 0.001),
        turn_rate: 0,
        swim_phase: (this.previousFrame?.tick || 0) * 0.3 + fish.id,
        tail_beat: Math.min(1, Math.hypot(prior.vx || 0, prior.vy || 0)),
        body_wave: 0.2,
        speed: Math.hypot(prior.vx || 0, prior.vy || 0),
        stride: Math.hypot(prior.vx || 0, prior.vy || 0),
        ...(prior.locomotion || {}),
      };
      const alpha = clamp((renderTime - this.previousFrame.receivedAt) / frameDeltaMs, 0, 1);
      return {
        heading: interpolateAngle(previousMotion.heading, current.heading, alpha),
        turn_rate: lerp(previousMotion.turn_rate, current.turn_rate, alpha),
        swim_phase: unwrapPhase(previousMotion.swim_phase, current.swim_phase, alpha),
        tail_beat: lerp(previousMotion.tail_beat, current.tail_beat, alpha),
        body_wave: lerp(previousMotion.body_wave, current.body_wave, alpha),
        speed: lerp(previousMotion.speed, current.speed, alpha),
        stride: lerp(previousMotion.stride, current.stride, alpha),
      };
    }

    depthFor(fish, env) {
      const key = `${fish.id}|${fish.species_id || ""}|${fish.lineage || fish.lineage_id || 0}`;
      if (!this.depthByFish.has(key)) this.depthByFish.set(key, hash01(key));
      const stable = this.depthByFish.get(key);
      const yDepth = clamp((fish.renderY ?? fish.y ?? 0) / Math.max(1, env.height || 1), 0, 1);
      return clamp(stable * 0.55 + yDepth * 0.45, 0, 1);
    }

    drawOrganism(fish, sx, sy, now) {
      const ctx = this.ctx;
      const phenotype = phenotypeFor(fish);
      const morphology = morphologyFor(fish, phenotype);
      const depth = fish.renderDepth;
      const tier = depth < 0.35 ? "background" : depth < 0.75 ? "midwater" : "foreground";
      const quality = QUALITY_SETTINGS[this.quality];
      const x = (fish.renderX ?? fish.x) * sx;
      const y = (fish.renderY ?? fish.y) * sy;
      const baseScale = 0.58 + depth * 0.72;
      const r = Math.max(2.2, fish.radius * Math.min(sx, sy) * baseScale);
      const alpha = clamp((0.30 + depth * 0.68) * (0.60 + (fish.health || 0.7) * 0.42), 0.18, 1);
      const bodyLength = r * phenotype.body_length * (0.94 + morphology.body_axis_length * 0.12);
      const bodyDepth = r * phenotype.body_depth * (0.90 + morphology.body_axis_depth * 0.14);
      const tailLength = r * phenotype.tail_length;
      const hitRadius = Math.max(bodyLength + tailLength, bodyDepth) * (1.12 + depth * 0.22);
      this.renderedFish.push({ id: fish.id, x, y, r: hitRadius, fish, depth, tier });

      if (depth < quality.simpleDepth || this.quality === "minimum") {
        this.drawSimpleOrganism(fish, phenotype, morphology, x, y, r, alpha, tier);
        return;
      }

      const locomotion = fish.locomotion || this.locomotionFor(fish);
      const pulse = Math.sin(locomotion.swim_phase || now * 0.004);
      const angle = locomotion.heading || 0;
      const cacheEntry = this.cachedBody(phenotype, morphology, r, tier);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle + pulse * (locomotion.body_wave || 0.2) * 0.025);
      ctx.globalAlpha = alpha;
      if (tier !== "background") this.drawDynamicTail(phenotype, bodyLength, bodyDepth, tailLength, pulse, depth);
      ctx.drawImage(cacheEntry.canvas, -cacheEntry.width / 2, -cacheEntry.height / 2, cacheEntry.width, cacheEntry.height);
      if (tier === "foreground") this.drawForegroundDetail(phenotype, morphology, bodyLength, bodyDepth, r, pulse);
      this.drawSelectionRing(fish, bodyLength, bodyDepth, tailLength);
      ctx.restore();
    }

    drawSimpleOrganism(fish, phenotype, morphology, x, y, r, alpha, tier) {
      const ctx = this.ctx;
      const locomotion = fish.locomotion || {};
      const angle = locomotion.heading ?? Math.atan2(fish.vy || 0, fish.vx || 0.001);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(angle);
      ctx.globalAlpha = alpha * (tier === "background" ? 0.62 : 0.82);
      ctx.fillStyle = mixAlpha(phenotype.primary_color, tier === "background" ? 0.38 : 0.58);
      ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.34);
      ctx.lineWidth = Math.max(0.7, r * 0.08);
      ctx.beginPath();
      ctx.ellipse(0, 0, r * (0.78 + morphology.body_axis_length * 0.22), r * (0.34 + morphology.body_axis_depth * 0.18), 0, 0, TAU);
      ctx.fill();
      ctx.stroke();
      if (this.selectedId === fish.id || this.hoveredId === fish.id || this.compareId === fish.id) this.drawSelectionRing(fish, r * 1.2, r * 0.7, r * 0.5);
      ctx.restore();
    }

    cachedBody(phenotype, morphology, r, tier) {
      if (!this.options.cacheEnabled) {
        return this.makeBodyCanvas(phenotype, morphology, r, tier);
      }
      const key = renderSignature(phenotype, morphology, tier, Math.round(r * 2) / 2);
      const cached = this.cache.get(key);
      if (cached) {
        this.cacheHits += 1;
        return cached;
      }
      this.cacheMisses += 1;
      const entry = this.makeBodyCanvas(phenotype, morphology, r, tier);
      this.cache.set(key, entry);
      if (this.cache.size > 180) this.cache.delete(this.cache.keys().next().value);
      return entry;
    }

    makeBodyCanvas(phenotype, morphology, r, tier) {
      const bodyLength = r * phenotype.body_length * (0.94 + morphology.body_axis_length * 0.12);
      const bodyDepth = r * phenotype.body_depth * (0.90 + morphology.body_axis_depth * 0.14);
      const margin = r * 3.2;
      const width = Math.ceil(bodyLength * 1.9 + margin);
      const height = Math.ceil(bodyDepth * 3.1 + margin);
      const canvas = createCanvas(width, height);
      const ctx = canvas.getContext("2d");
      ctx.translate(width / 2, height / 2);
      ctx.fillStyle = phenotype.primary_color;
      ctx.strokeStyle = stateColor(morphology.viability_index);
      ctx.lineWidth = Math.max(1, r * 0.12);
      bodyPath(ctx, phenotype, bodyLength, bodyDepth, 0);
      ctx.fill();
      ctx.stroke();
      ctx.save();
      bodyPath(ctx, phenotype, bodyLength, bodyDepth, 0);
      ctx.clip();
      drawStaticPattern(ctx, phenotype, bodyLength, bodyDepth);
      ctx.restore();
      drawHeadAndMouth(ctx, phenotype, morphology, bodyLength, bodyDepth, r);
      if (tier !== "background") drawArmor(ctx, phenotype, morphology, bodyLength, bodyDepth, r);
      if (tier === "foreground" || morphology.chemical_marker > 0.28) drawChemical(ctx, morphology, bodyLength, bodyDepth, r);
      drawEye(ctx, phenotype, morphology, bodyLength, bodyDepth, r);
      if (tier !== "background") drawAppendages(ctx, phenotype, morphology, bodyLength, bodyDepth, r, QUALITY_SETTINGS[this.quality].appendageScale);
      return { canvas, width, height };
    }

    drawDynamicTail(phenotype, length, depth, tailLength, pulse, depthValue) {
      const ctx = this.ctx;
      const root = -length * 0.56;
      const tip = root - tailLength * (1.0 + Math.abs(pulse) * 0.05);
      const spread = depth * (0.48 + phenotype.fin_span * 0.20);
      ctx.save();
      ctx.globalAlpha *= 0.78;
      ctx.fillStyle = mixAlpha(phenotype.accent_color, 0.36 + depthValue * 0.32);
      ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.52 + depthValue * 0.22);
      ctx.lineWidth = Math.max(1, depth * 0.10);
      ctx.beginPath();
      if (phenotype.tail === "forked" || phenotype.tail === "lunate") {
        ctx.moveTo(root, 0);
        ctx.lineTo(tip, -spread);
        ctx.lineTo(tip + tailLength * 0.34, pulse * depth * 0.12);
        ctx.lineTo(tip, spread);
      } else {
        ctx.moveTo(root, 0);
        ctx.quadraticCurveTo(tip + tailLength * 0.18, -spread, tip, pulse * depth * 0.08);
        ctx.quadraticCurveTo(tip + tailLength * 0.18, spread, root, 0);
      }
      ctx.closePath();
      ctx.fill();
      ctx.stroke();
      ctx.restore();
    }

    drawForegroundDetail(phenotype, morphology, length, depth, r, pulse) {
      const ctx = this.ctx;
      if (this.quality === "low" || this.quality === "minimum") return;
      ctx.save();
      ctx.strokeStyle = `rgba(175, 255, 240, ${0.10 + (phenotype.iridescence || 0) * 0.20 + (morphology.sensory_surface || 0) * 0.06})`;
      ctx.lineWidth = Math.max(1, r * 0.045);
      for (let i = 0; i < 2; i += 1) {
        ctx.beginPath();
        ctx.moveTo(-length * 0.38, -depth * (0.24 - i * 0.22 + pulse * 0.025));
        ctx.quadraticCurveTo(0, -depth * (0.44 - i * 0.20), length * 0.40, -depth * (0.18 - i * 0.18));
        ctx.stroke();
      }
      if ((phenotype.barbel_length || 0) > 0.18 || (morphology.sensory_surface || 0) > 0.62) {
        ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.66);
        ctx.lineWidth = Math.max(1, r * 0.05);
        for (const side of [-1, 1]) {
          ctx.beginPath();
          ctx.moveTo(length * 0.45, side * depth * 0.18);
          ctx.quadraticCurveTo(length * 0.57, side * (depth * 0.30 + pulse * r * 0.04), length * (0.55 + morphology.sensory_surface * 0.10), side * depth * 0.54);
          ctx.stroke();
        }
      }
      ctx.restore();
    }

    drawSelectionRing(fish, length, depth, tailLength) {
      const selected = this.selectedId === fish.id;
      const compared = this.compareId === fish.id;
      const hovered = this.hoveredId === fish.id;
      if (!selected && !compared && !hovered) return;
      this.ctx.save();
      this.ctx.globalAlpha = 1;
      this.ctx.strokeStyle = selected ? "rgba(255, 255, 255, 0.96)" : compared ? "rgba(230, 176, 93, 0.96)" : "rgba(112, 245, 214, 0.82)";
      this.ctx.lineWidth = selected || compared ? 2 : 1;
      this.ctx.beginPath();
      this.ctx.ellipse(0, 0, (length + tailLength) * 0.76, depth * 1.64, 0, 0, TAU);
      this.ctx.stroke();
      this.ctx.restore();
    }

    drawDeadOverlay() {
      this.ctx.save();
      this.ctx.fillStyle = "rgba(34, 6, 14, 0.24)";
      this.ctx.fillRect(0, 0, this.width, this.height);
      this.ctx.restore();
    }

    finishPerf(started, now) {
      const elapsed = performance.now() - started;
      this.frameTimes.push(elapsed);
      if (this.frameTimes.length > 180) this.frameTimes.shift();
      if (this.lastRenderAt > 0) {
        this.rafDeltas.push(now - this.lastRenderAt);
        if (this.rafDeltas.length > 180) this.rafDeltas.shift();
      }
      this.adaptQuality(now);
      if (this.options.debug && Math.floor(now / 5000) !== Math.floor(this.lastRenderAt / 5000)) {
        console.debug("Aquagenesys reef renderer", this.getPerfStats());
      }
      this.lastRenderAt = now;
    }

    adaptQuality(now) {
      if (this.options.forcedQuality || !this.options.adaptiveQuality || this.frameTimes.length < 90) return;
      if (now - this.lastQualityChangeAt < 2500) return;
      const p95 = percentile(this.frameTimes.slice(-90), 0.95);
      const currentIndex = QUALITY.indexOf(this.quality);
      const budget = QUALITY_SETTINGS[this.quality].frameBudget;
      if (p95 > budget && currentIndex > 0) {
        this.quality = QUALITY[currentIndex - 1];
        this.lastQualityChangeAt = now;
        this.resize(this.width, this.height, window.devicePixelRatio || 1);
        console.info(`Aquagenesys reef renderer quality -> ${this.quality}`, this.getPerfStats());
      } else if (p95 < 15 && currentIndex < QUALITY.length - 1) {
        this.quality = QUALITY[currentIndex + 1];
        this.lastQualityChangeAt = now;
        this.resize(this.width, this.height, window.devicePixelRatio || 1);
        console.info(`Aquagenesys reef renderer quality -> ${this.quality}`, this.getPerfStats());
      }
    }
  }

  function drawCoverImage(ctx, image, width, height, alpha) {
    const scale = Math.max(width / image.naturalWidth, height / image.naturalHeight);
    const drawWidth = image.naturalWidth * scale;
    const drawHeight = image.naturalHeight * scale;
    ctx.save();
    ctx.globalAlpha = alpha;
    ctx.drawImage(image, (width - drawWidth) / 2, (height - drawHeight) / 2, drawWidth, drawHeight);
    ctx.restore();
  }

  function createCanvas(width, height) {
    if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(width, height);
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    return canvas;
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

  function morphologyFor(fish, phenotype = phenotypeFor(fish)) {
    return {
      schema: "aquagenesys.morphology.v1",
      morphology_hash: fish.genome?.morphology_hash || fish.morphology?.morphology_hash || "",
      label: fish.morphology?.labels?.[0] || phenotype.morphology?.label || "generalized aquatic body plan",
      body_mass: 0.55,
      body_axis_length: 0.55,
      body_axis_depth: 0.55,
      head_scale: 0.9,
      mouth_scale: 0.62,
      mouth_shape: "small",
      appendage_count: 2,
      appendage_length: 0.24,
      appendage_flexibility: 0.38,
      appendage_strength: 0.34,
      armor_density: 0.16,
      spine_density: 0.08,
      soft_tissue_ratio: 0.45,
      chemical_marker: 0.0,
      sensory_surface: 0.38,
      viability_index: 0.72,
      ...(phenotype.morphology || {}),
    };
  }

  function bodyPath(ctx, phenotype, length, depth, bend = 0) {
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

  function drawStaticPattern(ctx, phenotype, length, depth) {
    ctx.fillStyle = "rgba(255, 255, 255, 0.10)";
    ctx.beginPath();
    ctx.ellipse(0, -depth * 0.24, length * 0.50, depth * 0.24, 0, Math.PI, Math.PI * 2);
    ctx.fill();
    const contrast = clamp(phenotype.pattern_contrast, 0, 1);
    ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.18 + contrast * 0.52);
    ctx.fillStyle = mixAlpha(phenotype.accent_color, 0.16 + contrast * 0.42);
    ctx.lineWidth = Math.max(1, depth * (0.04 + contrast * 0.03));
    if (phenotype.pattern === "striped" || phenotype.pattern === "banded") {
      const count = phenotype.stripe_count || 5;
      for (let i = 0; i < count; i += 1) {
        const x = -length * 0.43 + (i / Math.max(1, count - 1)) * length * 0.78;
        ctx.beginPath();
        ctx.moveTo(x, -depth * 0.54);
        ctx.quadraticCurveTo(x + length * 0.04, 0, x - length * 0.02, depth * 0.54);
        ctx.stroke();
      }
      return;
    }
    const count = Math.min(12, phenotype.spot_count || 8);
    for (let i = 0; i < count; i += 1) {
      const t = (i + 1) / (count + 1);
      const x = -length * 0.46 + t * length * 0.86;
      const y = Math.sin(i * 2.31) * depth * 0.36;
      ctx.beginPath();
      ctx.arc(x, y, depth * (0.055 + (i % 4) * 0.012), 0, TAU);
      ctx.fill();
    }
  }

  function drawHeadAndMouth(ctx, phenotype, morphology, length, depth, r) {
    const headScale = Number(morphology.head_scale || 0.9);
    const mouthScale = Number(morphology.mouth_scale || 0.6);
    const headX = length * 0.33;
    ctx.fillStyle = mixAlpha(phenotype.primary_color, 0.82);
    ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.62);
    ctx.lineWidth = Math.max(1, r * 0.06);
    ctx.beginPath();
    ctx.ellipse(headX, 0, depth * (0.25 + headScale * 0.18), depth * (0.34 + headScale * 0.14), 0, 0, TAU);
    ctx.fill();
    ctx.stroke();
    const mouthX = length * (0.49 + mouthScale * 0.04);
    ctx.fillStyle = "rgba(3, 9, 15, 0.82)";
    ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.72);
    ctx.beginPath();
    if (morphology.mouth_shape === "filter_slot") {
      ctx.rect(mouthX - r * 0.02, -depth * mouthScale * 0.22, Math.max(1, r * 0.18), depth * mouthScale * 0.44);
    } else if (morphology.mouth_shape === "suction") {
      ctx.ellipse(mouthX, 0, r * (0.07 + mouthScale * 0.12), r * (0.06 + mouthScale * 0.10), 0, 0, TAU);
    } else if (morphology.mouth_shape === "force_aperture") {
      ctx.moveTo(mouthX - r * 0.02, -depth * mouthScale * 0.25);
      ctx.lineTo(mouthX + r * (0.20 + mouthScale * 0.12), 0);
      ctx.lineTo(mouthX - r * 0.02, depth * mouthScale * 0.25);
      ctx.closePath();
    } else {
      ctx.ellipse(mouthX, 0, r * (0.07 + mouthScale * 0.05), r * 0.045, 0, 0, TAU);
    }
    ctx.fill();
    ctx.stroke();
  }

  function drawArmor(ctx, phenotype, morphology, length, depth, r) {
    const armor = Number(morphology.armor_density || 0);
    const spines = Number(morphology.spine_density || 0);
    if (armor <= 0.16 && spines <= 0.12) return;
    ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.28 + armor * 0.38);
    ctx.lineWidth = Math.max(1, r * (0.03 + armor * 0.04));
    const plates = Math.max(3, Math.min(8, Math.round(3 + armor * 5)));
    for (let i = 0; i < plates; i += 1) {
      const x = -length * 0.42 + (i / Math.max(1, plates - 1)) * length * 0.76;
      ctx.beginPath();
      ctx.moveTo(x, -depth * 0.56);
      ctx.quadraticCurveTo(x + length * 0.04, 0, x, depth * 0.56);
      ctx.stroke();
    }
    const spineCount = Math.min(8, Math.round(spines * 8));
    ctx.fillStyle = mixAlpha(phenotype.accent_color, 0.62);
    for (let i = 0; i < spineCount; i += 1) {
      const t = (i + 1) / (spineCount + 1);
      const x = -length * 0.42 + t * length * 0.80;
      ctx.beginPath();
      ctx.moveTo(x - r * 0.06, -depth * 0.64);
      ctx.lineTo(x + r * 0.05, -depth * (0.82 + spines * 0.16));
      ctx.lineTo(x + r * 0.16, -depth * 0.62);
      ctx.closePath();
      ctx.fill();
    }
  }

  function drawAppendages(ctx, phenotype, morphology, length, depth, r, scale) {
    const count = Math.min(12, Math.max(0, Math.round(Number(morphology.appendage_count || 0) * scale)));
    if (count <= 0 || Number(morphology.appendage_length || 0) <= 0.08) return;
    const len = r * (0.42 + morphology.appendage_length * 1.25);
    const flex = Number(morphology.appendage_flexibility || 0.4);
    const strength = Number(morphology.appendage_strength || 0.4);
    ctx.strokeStyle = mixAlpha(phenotype.accent_color, 0.44 + strength * 0.18);
    ctx.lineWidth = Math.max(1, r * (0.03 + strength * 0.035));
    const slots = Math.max(1, Math.ceil(count / 2));
    let drawn = 0;
    for (let i = 0; i < slots && drawn < count; i += 1) {
      const t = slots === 1 ? 0.0 : i / (slots - 1);
      const anchorX = length * (0.20 - t * 0.64);
      for (const side of [-1, 1]) {
        if (drawn >= count) break;
        drawn += 1;
        const anchorY = side * depth * (0.44 + (i % 2) * 0.06);
        ctx.beginPath();
        ctx.moveTo(anchorX, anchorY);
        ctx.quadraticCurveTo(anchorX - len * 0.16, anchorY + side * len * (0.28 + flex * 0.10), anchorX - len * (0.22 + t * 0.18), anchorY + side * len * (0.58 + flex * 0.28));
        ctx.stroke();
      }
    }
  }

  function drawChemical(ctx, morphology, length, depth, r) {
    const marker = Number(morphology.chemical_marker || 0);
    if (marker <= 0.12) return;
    ctx.fillStyle = `rgba(184, 255, 128, ${Math.min(0.62, 0.18 + marker * 0.42)})`;
    const glands = Math.max(1, Math.min(5, Math.round(marker * 5)));
    for (let i = 0; i < glands; i += 1) {
      const t = (i + 1) / (glands + 1);
      const x = -length * 0.30 + t * length * 0.52;
      const y = depth * 0.26;
      ctx.beginPath();
      ctx.ellipse(x, y, r * (0.05 + marker * 0.08), r * (0.03 + marker * 0.05), 0, 0, TAU);
      ctx.fill();
    }
  }

  function drawEye(ctx, phenotype, morphology, length, depth, r) {
    ctx.fillStyle = "rgba(3, 12, 18, 0.78)";
    ctx.beginPath();
    ctx.arc(length * (0.31 + morphology.head_scale * 0.05), -depth * 0.20, Math.max(1.0, r * 0.09 * phenotype.eye_scale * (0.84 + morphology.sensory_surface * 0.18)), 0, TAU);
    ctx.fill();
  }

  function renderSignature(phenotype, morphology, tier, r) {
    return [
      tier,
      r,
      phenotype.shape,
      phenotype.pattern,
      phenotype.fins,
      phenotype.primary_color,
      phenotype.accent_color,
      phenotype.stripe_count,
      phenotype.spot_count,
      morphology.morphology_hash,
      morphology.mouth_shape,
      Math.round(morphology.armor_density * 10),
      Math.round(morphology.appendage_count),
      Math.round(morphology.chemical_marker * 10),
    ].join("|");
  }

  function makeParticles(count) {
    const rows = [];
    for (let i = 0; i < count; i += 1) {
      const seed = hash01(`particle-${i}`);
      rows.push({
        x: hash01(`x-${i}`),
        y: hash01(`y-${i}`),
        phase: seed * TAU,
        speed: 0.28 + hash01(`s-${i}`) * 0.72,
        size: 0.8 + hash01(`z-${i}`) * 1.8,
        alpha: 0.10 + hash01(`a-${i}`) * 0.20,
      });
    }
    return rows;
  }

  function hash01(value) {
    const text = String(value);
    let hash = 2166136261;
    for (let i = 0; i < text.length; i += 1) {
      hash ^= text.charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return ((hash >>> 0) % 10000) / 10000;
  }

  function stateColor(viability) {
    if (viability < 0.35) return "rgba(255, 116, 138, 0.76)";
    if (viability < 0.55) return "rgba(235, 185, 84, 0.72)";
    return "rgba(205, 255, 242, 0.56)";
  }

  function mixAlpha(color, alpha) {
    const rgb = hexToRgb(color);
    if (!rgb) return `rgba(130, 222, 196, ${alpha})`;
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
    return ((from + delta * alpha) % TAU + TAU) % TAU;
  }

  function percentile(values, fraction) {
    if (!values.length) return 0;
    const sorted = values.slice().sort((a, b) => a - b);
    return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * fraction))];
  }

  function normalizeQuality(value) {
    const quality = String(value || "").toLowerCase();
    return QUALITY.includes(quality) ? quality : "";
  }

  function clamp(value, low = 0, high = 1) {
    return Math.max(low, Math.min(high, Number(value) || 0));
  }

  function lerp(a, b, alpha) {
    return a + (b - a) * alpha;
  }

  function round(value, digits) {
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
  }

  window.AquagenesysReefRenderer = { init };
})();
