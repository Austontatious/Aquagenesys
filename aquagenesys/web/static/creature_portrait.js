(function () {
  "use strict";

  const TAU = Math.PI * 2;
  const PALETTES = [
    { name: "cyan violet", body: "#1355d8", body2: "#18d8ff", accent: "#b767ff", glow: "#6ef4ff", core: "#f0e8ff", warning: "#ff5f9a" },
    { name: "blue magenta", body: "#1434a8", body2: "#2868ff", accent: "#ff5ccf", glow: "#8be7ff", core: "#ffd9ff", warning: "#ff875a" },
    { name: "teal amber", body: "#0a7f9c", body2: "#22e0c1", accent: "#ffc767", glow: "#72ffe5", core: "#fff4bb", warning: "#ff9b52" },
    { name: "violet pink", body: "#4b29cc", body2: "#8f62ff", accent: "#ff78e6", glow: "#80d8ff", core: "#ffe6ff", warning: "#ff5578" },
    { name: "deep blue cyan", body: "#06358f", body2: "#1698ff", accent: "#58fff1", glow: "#54d7ff", core: "#d9fbff", warning: "#ff6d56" },
    { name: "warning orange magenta", body: "#2330a6", body2: "#ff6b6b", accent: "#ff4fd8", glow: "#64f5ff", core: "#ffe3b8", warning: "#ffb347" },
  ];
  const ARCHETYPES = [
    "reef_fish",
    "ribbon_swimmer",
    "jelly_floater",
    "armored_filter_feeder",
    "frilled_symbiont",
    "schooling_minnow",
    "eel_glider",
    "spiral_drifter",
    "spined_crawler",
    "translucent_exotic",
  ];

  function initCreaturePortrait(canvas, options = {}) {
    return new CreaturePortrait(canvas, options);
  }

  class CreaturePortrait {
    constructor(canvas, options = {}) {
      this.canvas = canvas;
      this.ctx = canvas?.getContext ? canvas.getContext("2d") : null;
      this.options = {
        dprCap: 1.8,
        debug: false,
        ...options,
      };
      this.width = 1;
      this.height = 1;
      this.dpr = 1;
      this.lastInfo = null;
      this.renderCount = 0;
      this.lastRenderMs = 0;
      this.resize();
      this.clear();
    }

    resize(width = 0, height = 0, devicePixelRatio = window.devicePixelRatio || 1) {
      if (!this.canvas || !this.ctx) return { width: 0, height: 0, dpr: 1 };
      const rect = this.canvas.getBoundingClientRect ? this.canvas.getBoundingClientRect() : { width: 320, height: 220 };
      this.width = Math.max(1, Math.floor(width || rect.width || 320));
      this.height = Math.max(1, Math.floor(height || rect.height || Math.round(this.width * 0.66)));
      this.dpr = Math.min(devicePixelRatio || 1, this.options.dprCap);
      const nextWidth = Math.max(1, Math.floor(this.width * this.dpr));
      const nextHeight = Math.max(1, Math.floor(this.height * this.dpr));
      if (this.canvas.width !== nextWidth || this.canvas.height !== nextHeight) {
        this.canvas.width = nextWidth;
        this.canvas.height = nextHeight;
      }
      this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);
      return { width: this.width, height: this.height, dpr: this.dpr };
    }

    clear() {
      if (!this.ctx) return;
      this.ctx.clearRect(0, 0, this.width, this.height);
      drawPortraitBackground(this.ctx, placeholderDescriptor(), { width: this.width, height: this.height }, true);
      this.lastInfo = null;
    }

    render(fish, options = {}) {
      if (!this.ctx || !fish) {
        this.clear();
        return null;
      }
      const started = performance.now();
      this.resize(options.width || 0, options.height || 0, options.devicePixelRatio || window.devicePixelRatio || 1);
      const result = renderCreaturePortrait(this.ctx, fish, {
        ...this.options,
        ...options,
        width: this.width,
        height: this.height,
      });
      this.lastRenderMs = performance.now() - started;
      this.renderCount += 1;
      this.lastInfo = { ...result, render_ms: round(this.lastRenderMs, 2), render_count: this.renderCount };
      if (this.options.debug) console.debug("Aquagenesys creature portrait", this.lastInfo);
      return this.lastInfo;
    }

    getDebugInfo() {
      return this.lastInfo;
    }
  }

  function renderCreaturePortrait(canvasOrContext, fish, options = {}) {
    const ctx = canvasOrContext?.getContext ? canvasOrContext.getContext("2d") : canvasOrContext;
    if (!ctx) return null;
    const descriptor = buildCreatureVisualDescriptor(fish);
    descriptor.archetype = chooseCreatureArchetype(descriptor);
    const bounds = {
      width: Math.max(1, options.width || ctx.canvas?.width || 320),
      height: Math.max(1, options.height || ctx.canvas?.height || 220),
    };
    ctx.clearRect(0, 0, bounds.width, bounds.height);
    drawPortraitBackground(ctx, descriptor, bounds, false);
    ctx.save();
    ctx.translate(bounds.width * 0.50, bounds.height * 0.52);
    const scale = Math.min(bounds.width, bounds.height) * 0.34;
    ctx.scale(scale, scale);
    drawCreatureByArchetype(ctx, descriptor);
    ctx.restore();
    drawConditionOverlay(ctx, descriptor, bounds);
    return debugInfoForDescriptor(descriptor);
  }

  function buildCreatureVisualDescriptor(fish = {}) {
    const phenotype = phenotypeFor(fish);
    const morphology = morphologyFor(fish, phenotype);
    const affordances = affordancesFor(fish);
    const seed = [
      fish.id ?? "unknown",
      fish.species_id || fish.species || "species",
      fish.lineage ?? fish.lineage_id ?? 0,
      fish.generation ?? 0,
      morphology.morphology_hash || phenotype.pattern || "",
    ].join("|");
    const size = clamp((Number(fish.radius || 4) - 2.5) / 7, 0, 1);
    const bodyLength = clamp((Number(phenotype.body_length || 1.55) - 1.0) / 1.15 + morphology.body_axis_length * 0.28, 0, 1);
    const bodyDepth = clamp((Number(phenotype.body_depth || 0.72) - 0.38) / 0.72 + morphology.body_axis_depth * 0.24, 0, 1);
    const appendageCount = clamp(Number(morphology.appendage_count || 0) / 14, 0, 1);
    const appendageLength = clamp(Number(morphology.appendage_length || 0), 0, 1);
    const spineDensity = clamp(Number(morphology.spine_density || 0), 0, 1);
    const armorDensity = clamp(Number(morphology.armor_density || 0), 0, 1);
    const softTissue = clamp(Number(morphology.soft_tissue_ratio || 0.45), 0, 1);
    const sensorySurface = clamp(Number(morphology.sensory_surface || 0.38), 0, 1);
    const chemicalMarker = clamp(Number(morphology.chemical_marker || affordances.toxin_payload || 0), 0, 1);
    const translucency = clamp(softTissue * 0.58 + Number(phenotype.iridescence || 0) * 0.30 + chemicalMarker * 0.16, 0, 1);
    const palette = choosePalette(seed, phenotype, morphology, chemicalMarker);
    const descriptor = {
      seed,
      id: fish.id ?? null,
      species_id: fish.species_id || "",
      lineage: fish.lineage ?? fish.lineage_id ?? null,
      generation: fish.generation ?? 0,
      morphology_hash: morphology.morphology_hash || "",
      phenotype,
      morphology,
      affordances,
      palette,
      size,
      bodyLength,
      bodyDepth,
      headScale: clamp(Number(morphology.head_scale || 0.9) / 1.6, 0, 1),
      mouthScale: clamp(Number(morphology.mouth_scale || 0.62), 0, 1),
      tailLength: clamp(Number(phenotype.tail_length || 0.7) / 1.2, 0, 1),
      finSpan: clamp(Number(phenotype.fin_span || 0.6), 0, 1),
      appendageCount,
      rawAppendageCount: Math.max(0, Math.round(Number(morphology.appendage_count || 0))),
      appendageLength,
      appendageFlexibility: clamp(Number(morphology.appendage_flexibility || 0.38), 0, 1),
      appendageStrength: clamp(Number(morphology.appendage_strength || 0.34), 0, 1),
      armorDensity,
      spineDensity,
      softTissue,
      sensorySurface,
      chemicalMarker,
      translucency,
      iridescence: clamp(Number(phenotype.iridescence || 0.18), 0, 1),
      filterRate: clamp(Number(affordances.filter_rate || 0), 0, 1),
      suctionForce: clamp(Number(affordances.suction_force || 0), 0, 1),
      biteForce: clamp(Number(affordances.bite_force || 0), 0, 1),
      reach: clamp(Number(affordances.reach || 0), 0, 1),
      drag: clamp(Number(affordances.drag || 0), 0, 1),
      oxygenCost: clamp(Number(affordances.oxygen_cost || 0), 0, 1),
      locomotion: fish.locomotion || {},
      condition: {
        health: clamp(Number(fish.health ?? 0.86), 0, 1),
        energy: clamp(Number(fish.energy ?? 18) / 30, 0, 1),
        stress: clamp(Number(fish.stress ?? 0), 0, 1),
        hunger: clamp(Number(fish.hunger ?? 0), 0, 1),
      },
    };
    descriptor.pattern = choosePattern(descriptor);
    descriptor.render_signature = renderSignature(descriptor);
    return descriptor;
  }

  function chooseCreatureArchetype(descriptor) {
    const d = descriptor;
    const longBody = d.bodyLength;
    const squatBody = d.bodyDepth * (1 - d.bodyLength * 0.36);
    const wave = clamp(Number(d.locomotion.body_wave || 0.2), 0, 1);
    const small = 1 - d.size;
    const rare = hash01(`${d.seed}|rare`);
    const scores = {
      reef_fish: 0.48 + d.iridescence * 0.18 + d.finSpan * 0.14 + (1 - Math.abs(d.bodyDepth - 0.48)) * 0.10,
      ribbon_swimmer: longBody * 0.56 + d.appendageFlexibility * 0.20 + d.appendageLength * 0.24 + d.appendageCount * 0.18 + d.tailLength * 0.14 + wave * 0.14 - d.armorDensity * 0.24,
      jelly_floater: d.softTissue * 0.54 + d.appendageLength * 0.22 + d.translucency * 0.20 + d.bodyDepth * 0.12 - d.armorDensity * 0.35 - d.chemicalMarker * 0.14,
      armored_filter_feeder: d.armorDensity * 0.50 + d.filterRate * 0.32 + d.suctionForce * 0.20 + squatBody * 0.18,
      frilled_symbiont: d.sensorySurface * 0.42 + d.appendageCount * 0.26 + d.appendageLength * 0.22 + d.chemicalMarker * 0.10,
      schooling_minnow: small * 0.40 + (1 - d.appendageCount) * 0.18 + d.finSpan * 0.16 + (1 - d.armorDensity) * 0.10,
      eel_glider: longBody * 0.52 + (1 - d.bodyDepth) * 0.22 + wave * 0.20 + d.drag * 0.06 - d.appendageCount * 0.18 - d.appendageLength * 0.08,
      spiral_drifter: (rare > 0.86 ? 0.78 : 0.06) + d.softTissue * 0.18 + d.translucency * 0.16 + d.sensorySurface * 0.12,
      spined_crawler: d.spineDensity * 0.48 + d.armorDensity * 0.28 + d.appendageStrength * 0.18 + squatBody * 0.18,
      translucent_exotic: d.translucency * 0.36 + d.iridescence * 0.26 + d.chemicalMarker * 0.20 + d.sensorySurface * 0.14 + (rare > 0.76 ? 0.14 : 0),
    };
    if (d.rawAppendageCount >= 8 && d.appendageLength > 0.42) scores.frilled_symbiont += 0.22;
    if (d.armorDensity > 0.58 && d.spineDensity > 0.32) scores.spined_crawler += 0.20;
    if (d.filterRate > 0.62 && d.armorDensity > 0.34) scores.armored_filter_feeder += 0.16;
    if (d.bodyLength > 0.72 && d.bodyDepth < 0.38) scores.eel_glider += 0.16;
    if (d.softTissue > 0.66 && d.bodyDepth > 0.54) scores.jelly_floater += 0.18;
    if (d.bodyLength > 0.72 && d.appendageLength > 0.30 && d.appendageFlexibility > 0.68) scores.ribbon_swimmer += 0.18;
    if (rare > 0.86 && d.softTissue > 0.72 && d.bodyDepth > 0.50) scores.spiral_drifter += 0.22;
    if (d.chemicalMarker > 0.50 && d.softTissue > 0.70 && d.iridescence > 0.58) scores.translucent_exotic += 0.34;
    let best = "reef_fish";
    let bestScore = scores.reef_fish;
    for (const archetype of ARCHETYPES) {
      if (scores[archetype] > bestScore) {
        best = archetype;
        bestScore = scores[archetype];
      }
    }
    return bestScore < 0.56 ? "reef_fish" : best;
  }

  function getCreaturePortraitDebugInfo(fish) {
    const descriptor = buildCreatureVisualDescriptor(fish);
    descriptor.archetype = chooseCreatureArchetype(descriptor);
    return debugInfoForDescriptor(descriptor);
  }

  function debugInfoForDescriptor(descriptor) {
    return {
      seed: descriptor.seed,
      id: descriptor.id,
      archetype: descriptor.archetype || chooseCreatureArchetype(descriptor),
      palette: descriptor.palette.name,
      pattern: descriptor.pattern,
      render_signature: descriptor.render_signature,
      morphology_hash: descriptor.morphology_hash || "",
      morphology_hints: {
        body_length: round(descriptor.bodyLength, 2),
        body_depth: round(descriptor.bodyDepth, 2),
        appendage_count: descriptor.rawAppendageCount,
        appendage_length: round(descriptor.appendageLength, 2),
        armor_density: round(descriptor.armorDensity, 2),
        spine_density: round(descriptor.spineDensity, 2),
        soft_tissue: round(descriptor.softTissue, 2),
        sensory_surface: round(descriptor.sensorySurface, 2),
        chemical_marker: round(descriptor.chemicalMarker, 2),
      },
    };
  }

  function drawCreatureByArchetype(ctx, descriptor) {
    const d = descriptor;
    if (d.archetype === "ribbon_swimmer") drawRibbonSwimmer(ctx, d);
    else if (d.archetype === "jelly_floater") drawJellyFloater(ctx, d);
    else if (d.archetype === "armored_filter_feeder") drawArmoredFilterFeeder(ctx, d);
    else if (d.archetype === "frilled_symbiont") drawFrilledSymbiont(ctx, d);
    else if (d.archetype === "schooling_minnow") drawSchoolingMinnow(ctx, d);
    else if (d.archetype === "eel_glider") drawEelGlider(ctx, d);
    else if (d.archetype === "spiral_drifter") drawSpiralDrifter(ctx, d);
    else if (d.archetype === "spined_crawler") drawSpinedCrawler(ctx, d);
    else if (d.archetype === "translucent_exotic") drawTranslucentExotic(ctx, d);
    else drawReefFish(ctx, d);
  }

  function drawPortraitBackground(ctx, descriptor, bounds, placeholder = false) {
    const { width, height } = bounds;
    const palette = descriptor.palette;
    const gradient = ctx.createLinearGradient(0, 0, 0, height);
    gradient.addColorStop(0, "#020817");
    gradient.addColorStop(0.48, "#06142b");
    gradient.addColorStop(1, "#02040a");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, width, height);

    const halo = ctx.createRadialGradient(width * 0.50, height * 0.46, 8, width * 0.50, height * 0.48, Math.max(width, height) * 0.62);
    halo.addColorStop(0, rgba(palette.glow, placeholder ? 0.10 : 0.22));
    halo.addColorStop(0.48, rgba(palette.accent, placeholder ? 0.045 : 0.08));
    halo.addColorStop(1, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, width, height);

    ctx.save();
    ctx.globalCompositeOperation = "screen";
    for (let i = 0; i < 38; i += 1) {
      const x = hash01(`${descriptor.seed}|speck-x-${i}`) * width;
      const y = hash01(`${descriptor.seed}|speck-y-${i}`) * height;
      const r = 0.6 + hash01(`${descriptor.seed}|speck-r-${i}`) * 1.6;
      ctx.fillStyle = i % 4 === 0 ? rgba(palette.accent, 0.18) : rgba(palette.glow, 0.13);
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.fill();
    }
    ctx.restore();

    ctx.save();
    ctx.globalAlpha = placeholder ? 0.20 : 0.34;
    for (let i = 0; i < 6; i += 1) {
      const x = width * (0.08 + i * 0.18);
      ctx.strokeStyle = i % 2 ? rgba(palette.accent, 0.14) : rgba(palette.glow, 0.16);
      ctx.lineWidth = 1 + (i % 3);
      ctx.beginPath();
      ctx.moveTo(x, height);
      ctx.bezierCurveTo(x + width * 0.035, height * 0.76, x - width * 0.055, height * 0.62, x + width * 0.02, height * 0.46);
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawReefFish(ctx, d) {
    ctx.save();
    ctx.rotate(-0.04 + (hash01(`${d.seed}|tilt`) - 0.5) * 0.10);
    drawTail(ctx, d, -0.78, 0, 0.55 + d.tailLength * 0.22, 0.45 + d.finSpan * 0.24);
    drawFins(ctx, d, 0.08, 0.32 + d.finSpan * 0.22);
    drawBodyHull(ctx, d, 0, 0, 1.28 + d.bodyLength * 0.34, 0.50 + d.bodyDepth * 0.28);
    drawSurfacePattern(ctx, d, 1.10, 0.42);
    drawGlowSpots(ctx, d, 0.98, 0.34, 6 + Math.round(d.iridescence * 8));
    drawHeadAndMouth(ctx, d, 0.70, 0);
    drawEye(ctx, d, 0.54, -0.14, 0.072);
    drawArmorPlates(ctx, d, 0.80);
    drawSpines(ctx, d, 0.78);
    drawBarbels(ctx, d, 0.66, 0.05);
    ctx.restore();
  }

  function drawRibbonSwimmer(ctx, d) {
    ctx.save();
    ctx.scale(1.08, 0.88);
    drawRibbonBody(ctx, d, 1.55, 0.20 + d.bodyDepth * 0.18, 0.18);
    drawGlowSpots(ctx, d, 1.34, 0.18, 10 + Math.round(d.bodyLength * 6));
    drawFins(ctx, d, -0.05, 0.18);
    drawHeadAndMouth(ctx, d, 0.86, 0.03);
    drawEye(ctx, d, 0.74, -0.08, 0.055);
    drawFrillCluster(ctx, d, -0.65, 0.0, 5, 0.46);
    ctx.restore();
  }

  function drawJellyFloater(ctx, d) {
    ctx.save();
    ctx.translate(0, -0.10);
    const w = 0.92 + d.bodyDepth * 0.24;
    const h = 0.58 + d.softTissue * 0.26;
    ctx.shadowBlur = 0.18;
    ctx.shadowColor = rgba(d.palette.glow, 0.70);
    const fill = ctx.createRadialGradient(0, -0.04, 0.05, 0, -0.02, w * 0.72);
    fill.addColorStop(0, rgba(d.palette.core, 0.52));
    fill.addColorStop(0.42, rgba(d.palette.body2, 0.30 + d.translucency * 0.14));
    fill.addColorStop(1, rgba(d.palette.accent, 0.12));
    ctx.fillStyle = fill;
    ctx.strokeStyle = rgba(d.palette.glow, 0.52);
    ctx.lineWidth = 0.025;
    ctx.beginPath();
    ctx.moveTo(-w * 0.62, 0.02);
    ctx.bezierCurveTo(-w * 0.50, -h * 0.76, -w * 0.15, -h, 0, -h * 0.95);
    ctx.bezierCurveTo(w * 0.34, -h, w * 0.58, -h * 0.70, w * 0.64, 0.02);
    ctx.bezierCurveTo(w * 0.40, h * 0.16, -w * 0.36, h * 0.16, -w * 0.62, 0.02);
    ctx.fill();
    ctx.stroke();
    drawTranslucentCore(ctx, d, 0, -0.20, 0.22);
    drawFrillCluster(ctx, d, -0.12, 0.02, Math.max(8, d.rawAppendageCount || 8), 0.68 + d.appendageLength * 0.40);
    drawBarbels(ctx, d, 0.34, 0.05, 8);
    ctx.restore();
  }

  function drawArmoredFilterFeeder(ctx, d) {
    ctx.save();
    ctx.translate(-0.03, 0.04);
    drawTail(ctx, d, -0.72, 0.02, 0.34, 0.30);
    drawBodyHull(ctx, d, -0.02, 0.02, 1.18, 0.62 + d.bodyDepth * 0.22);
    drawArmorPlates(ctx, d, 1.0, true);
    drawSpines(ctx, d, 0.90);
    ctx.strokeStyle = rgba(d.palette.glow, 0.54);
    ctx.lineWidth = 0.025;
    for (let i = 0; i < 5; i += 1) {
      const y = -0.18 + i * 0.09;
      ctx.beginPath();
      ctx.moveTo(0.68, y);
      ctx.quadraticCurveTo(0.88, y * 0.86, 0.98, y * 0.50);
      ctx.stroke();
    }
    drawEye(ctx, d, 0.50, -0.14, 0.055);
    drawFrillCluster(ctx, d, 0.50, 0.18, 6, 0.34);
    ctx.restore();
  }

  function drawFrilledSymbiont(ctx, d) {
    ctx.save();
    drawFrillCluster(ctx, d, 0, 0.06, 16 + Math.round(d.appendageCount * 10), 0.56 + d.appendageLength * 0.34);
    drawBodyHull(ctx, d, 0, 0.07, 0.72, 0.42 + d.bodyDepth * 0.16);
    drawTranslucentCore(ctx, d, 0, 0.02, 0.18 + d.sensorySurface * 0.10);
    drawGlowSpots(ctx, d, 0.54, 0.24, 10);
    drawEye(ctx, d, 0.24, -0.06, 0.05);
    ctx.restore();
  }

  function drawSchoolingMinnow(ctx, d) {
    ctx.save();
    ctx.scale(0.82, 0.82);
    for (let i = 0; i < 4; i += 1) {
      ctx.save();
      ctx.globalAlpha = 0.13;
      ctx.translate(-0.66 + i * 0.40, -0.42 + (i % 2) * 0.22);
      ctx.scale(0.34, 0.34);
      drawBodyHull(ctx, d, 0, 0, 1.0, 0.36);
      drawTail(ctx, d, -0.54, 0, 0.32, 0.24);
      ctx.restore();
    }
    drawTail(ctx, d, -0.70, 0, 0.45, 0.34);
    drawBodyHull(ctx, d, 0, 0, 1.20, 0.36);
    drawSurfacePattern(ctx, d, 1.0, 0.25);
    drawLateralStripe(ctx, d, 0.95, 0.12);
    drawEye(ctx, d, 0.50, -0.08, 0.052);
    ctx.restore();
  }

  function drawEelGlider(ctx, d) {
    ctx.save();
    ctx.scale(1.18, 0.88);
    drawRibbonBody(ctx, d, 1.76, 0.16 + d.bodyDepth * 0.10, 0.26);
    drawLateralStripe(ctx, d, 1.34, 0.13);
    drawGlowSpots(ctx, d, 1.45, 0.16, 12);
    drawHeadAndMouth(ctx, d, 0.86, 0.02);
    drawEye(ctx, d, 0.74, -0.055, 0.045);
    drawBarbels(ctx, d, 0.78, 0.02, 4);
    ctx.restore();
  }

  function drawSpiralDrifter(ctx, d) {
    ctx.save();
    ctx.translate(-0.08, -0.02);
    ctx.shadowBlur = 0.20;
    ctx.shadowColor = rgba(d.palette.glow, 0.72);
    const shell = ctx.createRadialGradient(0, 0, 0.05, 0, 0, 0.60);
    shell.addColorStop(0, rgba(d.palette.core, 0.58));
    shell.addColorStop(0.42, rgba(d.palette.accent, 0.30));
    shell.addColorStop(1, rgba(d.palette.body, 0.24));
    ctx.fillStyle = shell;
    ctx.strokeStyle = rgba(d.palette.glow, 0.58);
    ctx.lineWidth = 0.026;
    ctx.beginPath();
    ctx.ellipse(0, 0, 0.58, 0.50, 0.12, 0, TAU);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = rgba(d.palette.core, 0.54);
    ctx.lineWidth = 0.028;
    ctx.beginPath();
    for (let t = 0; t < TAU * 2.20; t += 0.18) {
      const r = 0.025 + t * 0.036;
      const x = Math.cos(t) * r;
      const y = Math.sin(t) * r * 0.84;
      if (t === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    drawFrillCluster(ctx, d, 0.36, 0.12, 9, 0.48);
    drawEye(ctx, d, 0.34, -0.08, 0.046);
    ctx.restore();
  }

  function drawSpinedCrawler(ctx, d) {
    ctx.save();
    ctx.translate(-0.02, 0.10);
    drawBodyHull(ctx, d, 0, 0, 1.24, 0.50 + d.bodyDepth * 0.20);
    drawArmorPlates(ctx, d, 1.1, true);
    drawSpines(ctx, d, 1.1, true);
    ctx.strokeStyle = rgba(d.palette.accent, 0.45);
    ctx.lineWidth = 0.032;
    for (let i = 0; i < 8; i += 1) {
      const x = -0.46 + i * 0.13;
      for (const side of [-1, 1]) {
        ctx.beginPath();
        ctx.moveTo(x, side * 0.20);
        ctx.quadraticCurveTo(x - 0.05, side * 0.34, x - 0.12, side * 0.47);
        ctx.stroke();
      }
    }
    drawBarbels(ctx, d, 0.58, 0.0, 6);
    drawEye(ctx, d, 0.46, -0.09, 0.048);
    ctx.restore();
  }

  function drawTranslucentExotic(ctx, d) {
    ctx.save();
    drawFrillCluster(ctx, d, 0.0, 0.02, 10 + Math.round(d.sensorySurface * 10), 0.48 + d.appendageLength * 0.34);
    drawBodyHull(ctx, d, 0, 0, 0.92 + d.bodyLength * 0.20, 0.54 + d.bodyDepth * 0.22, true);
    drawTranslucentCore(ctx, d, 0, -0.02, 0.24 + d.chemicalMarker * 0.12);
    ctx.strokeStyle = rgba(d.palette.glow, 0.42);
    ctx.lineWidth = 0.018;
    for (let i = 0; i < 6; i += 1) {
      const y = -0.20 + i * 0.08;
      ctx.beginPath();
      ctx.moveTo(-0.38, y);
      ctx.quadraticCurveTo(0, -y * 0.42, 0.40, y * 0.72);
      ctx.stroke();
    }
    drawGlowSpots(ctx, d, 0.74, 0.32, 12);
    drawEye(ctx, d, 0.32, -0.09, 0.050);
    ctx.restore();
  }

  function drawBodyHull(ctx, d, x, y, length, depth, translucent = false) {
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowBlur = 0.12 + d.iridescence * 0.12;
    ctx.shadowColor = rgba(d.palette.glow, 0.70);
    const fill = ctx.createLinearGradient(-length * 0.58, -depth, length * 0.58, depth);
    fill.addColorStop(0, rgba(d.palette.body, translucent ? 0.30 : 0.72));
    fill.addColorStop(0.46, rgba(d.palette.body2, translucent ? 0.38 : 0.82));
    fill.addColorStop(1, rgba(d.palette.accent, translucent ? 0.24 : 0.52));
    ctx.fillStyle = fill;
    ctx.strokeStyle = rgba(d.palette.glow, translucent ? 0.46 : 0.58);
    ctx.lineWidth = 0.026;
    ctx.beginPath();
    ctx.moveTo(length * 0.58, 0);
    ctx.bezierCurveTo(length * 0.35, -depth * 0.86, -length * 0.35, -depth * 0.72, -length * 0.58, 0);
    ctx.bezierCurveTo(-length * 0.34, depth * 0.76, length * 0.34, depth * 0.82, length * 0.58, 0);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function drawHeadAndMouth(ctx, d, x, y) {
    const head = 0.18 + d.headScale * 0.16;
    const mouth = 0.05 + d.mouthScale * 0.10;
    ctx.save();
    ctx.translate(x, y);
    ctx.fillStyle = rgba(d.palette.core, 0.14 + d.iridescence * 0.10);
    ctx.strokeStyle = rgba(d.palette.glow, 0.42);
    ctx.lineWidth = 0.018;
    ctx.beginPath();
    ctx.ellipse(0, 0, head, head * 0.72, 0.05, 0, TAU);
    ctx.fill();
    ctx.stroke();
    ctx.strokeStyle = d.biteForce > d.filterRate ? rgba(d.palette.warning, 0.65) : rgba(d.palette.glow, 0.54);
    ctx.lineWidth = 0.020 + d.mouthScale * 0.010;
    ctx.beginPath();
    ctx.moveTo(head * 0.42, -mouth * 0.45);
    ctx.quadraticCurveTo(head * 0.68 + mouth, 0, head * 0.42, mouth * 0.45);
    ctx.stroke();
    ctx.restore();
  }

  function drawEye(ctx, d, x, y, radius) {
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowBlur = 0.10;
    ctx.shadowColor = rgba(d.palette.core, 0.85);
    ctx.fillStyle = rgba(d.palette.core, 0.92);
    ctx.beginPath();
    ctx.arc(0, 0, radius * (0.88 + d.sensorySurface * 0.30), 0, TAU);
    ctx.fill();
    ctx.fillStyle = "#06101d";
    ctx.beginPath();
    ctx.arc(radius * 0.10, radius * 0.04, radius * 0.46, 0, TAU);
    ctx.fill();
    ctx.restore();
  }

  function drawTail(ctx, d, x, y, length, spread) {
    ctx.save();
    ctx.translate(x, y);
    ctx.shadowBlur = 0.12;
    ctx.shadowColor = rgba(d.palette.glow, 0.60);
    ctx.fillStyle = rgba(d.palette.accent, 0.34 + d.iridescence * 0.20);
    ctx.strokeStyle = rgba(d.palette.glow, 0.48);
    ctx.lineWidth = 0.020;
    ctx.beginPath();
    ctx.moveTo(0, 0);
    ctx.lineTo(-length, -spread * 0.52);
    ctx.quadraticCurveTo(-length * 0.72, 0, -length, spread * 0.52);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }

  function drawFins(ctx, d, x, span) {
    ctx.save();
    ctx.fillStyle = rgba(d.palette.accent, 0.22 + d.finSpan * 0.24);
    ctx.strokeStyle = rgba(d.palette.glow, 0.34);
    ctx.lineWidth = 0.016;
    for (const side of [-1, 1]) {
      ctx.beginPath();
      ctx.moveTo(x - 0.18, side * 0.12);
      ctx.quadraticCurveTo(x - 0.08, side * span, x + 0.24, side * 0.18);
      ctx.quadraticCurveTo(x + 0.04, side * 0.16, x - 0.18, side * 0.12);
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawRibbonBody(ctx, d, length, thickness, wave) {
    ctx.save();
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.shadowBlur = 0.15;
    ctx.shadowColor = rgba(d.palette.glow, 0.74);
    const gradient = ctx.createLinearGradient(-length * 0.58, 0, length * 0.58, 0);
    gradient.addColorStop(0, rgba(d.palette.body, 0.50));
    gradient.addColorStop(0.45, rgba(d.palette.body2, 0.78));
    gradient.addColorStop(1, rgba(d.palette.accent, 0.46));
    ctx.strokeStyle = gradient;
    ctx.lineWidth = thickness;
    ctx.beginPath();
    ctx.moveTo(-length * 0.58, 0.02);
    ctx.bezierCurveTo(-length * 0.28, -wave, length * 0.08, wave, length * 0.58, -0.02);
    ctx.stroke();
    ctx.strokeStyle = rgba(d.palette.core, 0.30);
    ctx.lineWidth = Math.max(0.018, thickness * 0.17);
    ctx.beginPath();
    ctx.moveTo(-length * 0.54, 0.01);
    ctx.bezierCurveTo(-length * 0.26, -wave * 0.82, length * 0.10, wave * 0.72, length * 0.54, -0.01);
    ctx.stroke();
    ctx.restore();
  }

  function drawFrillCluster(ctx, d, x, y, count, length) {
    ctx.save();
    ctx.translate(x, y);
    ctx.lineCap = "round";
    for (let i = 0; i < count; i += 1) {
      const t = count <= 1 ? 0.5 : i / (count - 1);
      const angle = -Math.PI * 0.88 + t * Math.PI * 1.76 + (hash01(`${d.seed}|frill-a-${i}`) - 0.5) * 0.30;
      const len = length * (0.62 + hash01(`${d.seed}|frill-l-${i}`) * 0.52);
      const bend = (hash01(`${d.seed}|frill-b-${i}`) - 0.5) * 0.34;
      ctx.strokeStyle = i % 3 === 0 ? rgba(d.palette.accent, 0.58) : rgba(d.palette.glow, 0.52);
      ctx.lineWidth = 0.014 + d.appendageStrength * 0.018;
      ctx.shadowBlur = 0.06;
      ctx.shadowColor = rgba(d.palette.glow, 0.72);
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.quadraticCurveTo(Math.cos(angle + bend) * len * 0.50, Math.sin(angle + bend) * len * 0.50, Math.cos(angle) * len, Math.sin(angle) * len);
      ctx.stroke();
      ctx.fillStyle = rgba(i % 2 ? d.palette.core : d.palette.accent, 0.66);
      ctx.beginPath();
      ctx.arc(Math.cos(angle) * len, Math.sin(angle) * len, 0.024 + d.sensorySurface * 0.014, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawBarbels(ctx, d, x, y, count = 4) {
    if (d.appendageLength < 0.12 && d.sensorySurface < 0.45) return;
    ctx.save();
    ctx.translate(x, y);
    ctx.strokeStyle = rgba(d.palette.glow, 0.50 + d.sensorySurface * 0.24);
    ctx.lineWidth = 0.012 + d.sensorySurface * 0.012;
    ctx.lineCap = "round";
    for (let i = 0; i < count; i += 1) {
      const side = i % 2 ? 1 : -1;
      const offset = (Math.floor(i / 2) + 1) * 0.034;
      const len = 0.28 + d.appendageLength * 0.34 + hash01(`${d.seed}|barb-${i}`) * 0.10;
      ctx.beginPath();
      ctx.moveTo(0, side * offset);
      ctx.quadraticCurveTo(len * 0.42, side * (offset + 0.13), len, side * (offset + 0.16 + d.appendageFlexibility * 0.12));
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawArmorPlates(ctx, d, widthScale = 1, force = false) {
    if (!force && d.armorDensity < 0.24) return;
    const count = 5 + Math.round(d.armorDensity * 8);
    ctx.save();
    ctx.strokeStyle = rgba(d.palette.core, 0.24 + d.armorDensity * 0.34);
    ctx.fillStyle = rgba(d.palette.body, 0.12 + d.armorDensity * 0.18);
    ctx.lineWidth = 0.012 + d.armorDensity * 0.012;
    for (let i = 0; i < count; i += 1) {
      const t = count <= 1 ? 0.5 : i / (count - 1);
      const x = -0.46 * widthScale + t * 0.92 * widthScale;
      const h = 0.20 + Math.sin(t * Math.PI) * 0.10;
      ctx.beginPath();
      ctx.roundRect?.(x - 0.045, -h * 0.62, 0.09, h, 0.025);
      if (!ctx.roundRect) {
        ctx.rect(x - 0.045, -h * 0.62, 0.09, h);
      }
      ctx.fill();
      ctx.stroke();
    }
    ctx.restore();
  }

  function drawSpines(ctx, d, widthScale = 1, force = false) {
    if (!force && d.spineDensity < 0.16) return;
    const count = 4 + Math.round(d.spineDensity * 12);
    ctx.save();
    ctx.fillStyle = rgba(d.palette.warning, 0.34 + d.spineDensity * 0.28);
    ctx.strokeStyle = rgba(d.palette.glow, 0.26);
    ctx.lineWidth = 0.010;
    for (let i = 0; i < count; i += 1) {
      const t = count <= 1 ? 0.5 : i / (count - 1);
      const x = -0.48 * widthScale + t * 0.96 * widthScale;
      for (const side of [-1, 1]) {
        const h = 0.13 + d.spineDensity * 0.14;
        ctx.beginPath();
        ctx.moveTo(x - 0.035, side * 0.21);
        ctx.lineTo(x, side * (0.21 + h));
        ctx.lineTo(x + 0.035, side * 0.21);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
      }
    }
    ctx.restore();
  }

  function drawGlowSpots(ctx, d, length, depth, count) {
    ctx.save();
    ctx.globalCompositeOperation = "screen";
    ctx.shadowBlur = 0.08;
    ctx.shadowColor = rgba(d.palette.glow, 0.82);
    for (let i = 0; i < count; i += 1) {
      const x = -length * 0.42 + hash01(`${d.seed}|spot-x-${i}`) * length * 0.84;
      const y = (hash01(`${d.seed}|spot-y-${i}`) - 0.5) * depth * 1.45;
      const r = 0.018 + hash01(`${d.seed}|spot-r-${i}`) * 0.026;
      ctx.fillStyle = i % 3 === 0 ? rgba(d.palette.accent, 0.62) : rgba(d.palette.glow, 0.58);
      ctx.beginPath();
      ctx.arc(x, y, r, 0, TAU);
      ctx.fill();
    }
    ctx.restore();
  }

  function drawSurfacePattern(ctx, d, length, depth) {
    ctx.save();
    ctx.globalAlpha = 0.62;
    ctx.strokeStyle = rgba(d.palette.core, 0.22 + d.iridescence * 0.18);
    ctx.lineWidth = 0.014;
    const stripes = d.pattern === "stripe" ? 7 : 4;
    if (d.pattern === "stripe" || d.pattern === "lattice") {
      for (let i = 0; i < stripes; i += 1) {
        const x = -length * 0.34 + (i / Math.max(1, stripes - 1)) * length * 0.68;
        ctx.beginPath();
        ctx.moveTo(x, -depth * 0.46);
        ctx.quadraticCurveTo(x + 0.06, 0, x - 0.04, depth * 0.46);
        ctx.stroke();
      }
    }
    if (d.pattern === "mottle" || d.pattern === "lattice") {
      drawGlowSpots(ctx, d, length * 0.78, depth * 0.70, 7);
    }
    ctx.restore();
  }

  function drawLateralStripe(ctx, d, length, depth) {
    ctx.save();
    ctx.shadowBlur = 0.08;
    ctx.shadowColor = rgba(d.palette.glow, 0.64);
    ctx.strokeStyle = rgba(d.palette.glow, 0.58);
    ctx.lineWidth = 0.028;
    ctx.beginPath();
    ctx.moveTo(-length * 0.44, 0);
    ctx.quadraticCurveTo(0, -depth * 0.18, length * 0.46, 0.01);
    ctx.stroke();
    ctx.restore();
  }

  function drawTranslucentCore(ctx, d, x, y, radius) {
    ctx.save();
    ctx.translate(x, y);
    ctx.globalCompositeOperation = "screen";
    ctx.shadowBlur = 0.16;
    ctx.shadowColor = rgba(d.chemicalMarker > 0.35 ? d.palette.warning : d.palette.core, 0.86);
    const core = ctx.createRadialGradient(0, 0, 0.02, 0, 0, radius);
    core.addColorStop(0, rgba(d.palette.core, 0.86));
    core.addColorStop(0.52, rgba(d.palette.accent, 0.40));
    core.addColorStop(1, rgba(d.palette.glow, 0));
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(0, 0, radius, 0, TAU);
    ctx.fill();
    ctx.restore();
  }

  function drawConditionOverlay(ctx, d, bounds) {
    const { width, height } = bounds;
    const lowHealth = clamp((0.54 - d.condition.health) / 0.54, 0, 1);
    const highStress = clamp((d.condition.stress - 0.52) / 0.48, 0, 1);
    const lowEnergy = clamp((0.36 - d.condition.energy) / 0.36, 0, 1);
    if (lowHealth <= 0 && highStress <= 0 && lowEnergy <= 0) return;
    ctx.save();
    if (lowEnergy > 0) {
      ctx.fillStyle = `rgba(0, 0, 0, ${lowEnergy * 0.14})`;
      ctx.fillRect(0, 0, width, height);
    }
    if (highStress > 0) {
      const gradient = ctx.createRadialGradient(width * 0.5, height * 0.5, 10, width * 0.5, height * 0.5, Math.max(width, height) * 0.68);
      gradient.addColorStop(0, "rgba(0, 0, 0, 0)");
      gradient.addColorStop(1, `rgba(255, 74, 132, ${highStress * 0.11})`);
      ctx.fillStyle = gradient;
      ctx.fillRect(0, 0, width, height);
    }
    if (lowHealth > 0) {
      ctx.strokeStyle = `rgba(255, 168, 190, ${lowHealth * 0.34})`;
      ctx.lineWidth = 1.1;
      for (let i = 0; i < 3; i += 1) {
        const x = width * (0.42 + hash01(`${d.seed}|scar-x-${i}`) * 0.18);
        const y = height * (0.45 + hash01(`${d.seed}|scar-y-${i}`) * 0.18);
        ctx.beginPath();
        ctx.moveTo(x - 8, y - 3);
        ctx.lineTo(x + 8, y + 3);
        ctx.stroke();
      }
    }
    ctx.restore();
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
      primary_color: fish.genome?.color || "#206abf",
      accent_color: fish.genome?.accent_color || "#67e8ff",
      ...(fish.phenotype || fish.genome?.phenotype || {}),
    };
  }

  function morphologyFor(fish, phenotype = phenotypeFor(fish)) {
    const stateMorph = fish.morphology || {};
    return {
      schema: "aquagenesys.morphology.v1",
      morphology_hash: fish.genome?.morphology_hash || stateMorph.morphology_hash || "",
      label: stateMorph.labels?.[0] || phenotype.morphology?.label || "generalized aquatic body plan",
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

  function affordancesFor(fish) {
    return fish.affordances || fish.morphology?.affordances || {};
  }

  function choosePalette(seed, phenotype, morphology, chemicalMarker) {
    if (chemicalMarker > 0.58 || Number(morphology.spine_density || 0) > 0.62) return PALETTES[5];
    if (Number(phenotype.iridescence || 0) > 0.48) return PALETTES[1 + Math.floor(hash01(`${seed}|pal-iri`) * 2)];
    if (Number(morphology.soft_tissue_ratio || 0) > 0.68) return PALETTES[0];
    return PALETTES[Math.min(PALETTES.length - 1, Math.floor(hash01(`${seed}|palette`) * PALETTES.length))];
  }

  function choosePattern(descriptor) {
    const value = hash01(`${descriptor.seed}|pattern`);
    if (descriptor.armorDensity > 0.48) return "plates";
    if (descriptor.iridescence > 0.42 && descriptor.sensorySurface > 0.54) return "lattice";
    if (value < 0.34) return "stripe";
    if (value < 0.68) return "mottle";
    return "glow_spots";
  }

  function renderSignature(d) {
    return [
      d.id ?? "-",
      d.species_id,
      d.lineage ?? "-",
      d.generation ?? 0,
      d.morphology_hash,
      d.palette.name,
      d.pattern,
      Math.round(d.bodyLength * 10),
      Math.round(d.bodyDepth * 10),
      Math.round(d.appendageCount * 10),
      Math.round(d.appendageLength * 10),
      Math.round(d.armorDensity * 10),
      Math.round(d.spineDensity * 10),
      Math.round(d.translucency * 10),
      Math.round(d.condition.health * 5),
      Math.round(d.condition.stress * 5),
      Math.round(d.condition.energy * 5),
    ].join("|");
  }

  function placeholderDescriptor() {
    const fish = { id: "placeholder", genome: { color: "#1c78d8", accent_color: "#55eaff" }, phenotype: { iridescence: 0.28 } };
    const descriptor = buildCreatureVisualDescriptor(fish);
    descriptor.archetype = "reef_fish";
    return descriptor;
  }

  function rgba(color, alpha) {
    const rgb = hexToRgb(color);
    if (!rgb) return `rgba(120, 220, 240, ${alpha})`;
    return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`;
  }

  function hexToRgb(color) {
    const raw = String(color || "").replace("#", "");
    if (raw.length !== 6) return null;
    const value = Number.parseInt(raw, 16);
    if (Number.isNaN(value)) return null;
    return { r: (value >> 16) & 255, g: (value >> 8) & 255, b: value & 255 };
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

  function clamp(value, low = 0, high = 1) {
    return Math.max(low, Math.min(high, Number(value) || 0));
  }

  function round(value, digits) {
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
  }

  window.AquagenesysCreaturePortrait = {
    initCreaturePortrait,
    renderCreaturePortrait,
    buildCreatureVisualDescriptor,
    chooseCreatureArchetype,
    getCreaturePortraitDebugInfo,
  };
})();
