from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "aquagenesys" / "web" / "static"


def test_reef_renderer_module_is_feature_flagged() -> None:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'rendererMode !== "classic"' in app_js
    assert 'rendererMode !== "legacy"' in app_js
    assert "window.AquagenesysReefRenderer.init" in app_js
    assert 'window.aquagenesysReefRenderer = reefRenderer' in app_js
    assert index_html.index("/static/renderer_canvas.js") < index_html.index("/static/app.js")


def test_creature_portrait_module_is_loaded_between_renderer_and_app() -> None:
    app_js = (STATIC / "app.js").read_text(encoding="utf-8")
    index_html = (STATIC / "index.html").read_text(encoding="utf-8")

    assert 'id="creaturePortrait"' in index_html
    assert 'id="fishPortraitPanel"' in index_html
    assert "/static/creature_portrait.js" in index_html
    assert index_html.index("/static/renderer_canvas.js") < index_html.index("/static/creature_portrait.js")
    assert index_html.index("/static/creature_portrait.js") < index_html.index("/static/app.js")
    assert "window.AquagenesysCreaturePortrait.initCreaturePortrait" in app_js
    assert "getCreaturePortraitDebugInfo" in app_js
    assert "lastPortraitSignature" in app_js


def test_creature_portrait_exports_constrained_canvas_grammar() -> None:
    portrait_js = (STATIC / "creature_portrait.js").read_text(encoding="utf-8")

    for export in (
        "initCreaturePortrait",
        "renderCreaturePortrait",
        "buildCreatureVisualDescriptor",
        "chooseCreatureArchetype",
        "getCreaturePortraitDebugInfo",
    ):
        assert export in portrait_js

    for archetype in (
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
    ):
        assert archetype in portrait_js

    for helper in (
        "drawPortraitBackground",
        "drawBodyHull",
        "drawHeadAndMouth",
        "drawEye",
        "drawTail",
        "drawFins",
        "drawRibbonBody",
        "drawFrillCluster",
        "drawBarbels",
        "drawArmorPlates",
        "drawSpines",
        "drawGlowSpots",
        "drawSurfacePattern",
        "drawTranslucentCore",
        "drawConditionOverlay",
    ):
        assert f"function {helper}" in portrait_js


def test_creature_portrait_does_not_introduce_runtime_image_generation_or_build_tooling() -> None:
    portrait_js = (STATIC / "creature_portrait.js").read_text(encoding="utf-8")

    forbidden = ("fetch(", "xmlhttprequest", "openai", "image_generation", "dall", "gpt-image", "http://", "https://")
    for needle in forbidden:
        assert needle not in portrait_js.lower()

    root = ROOT
    for build_file in ("package.json", "package-lock.json", "vite.config.js", "vite.config.ts", "tsconfig.json"):
        assert not (root / build_file).exists()


def test_reef_renderer_exports_bounded_canvas_interface() -> None:
    renderer_js = (STATIC / "renderer_canvas.js").read_text(encoding="utf-8")

    for method in (
        "resize(width, height",
        "updateFrame(framePayload",
        "render(now",
        "hitTest(x, y)",
        "getRenderedFish()",
        "setSelection(",
        "getPerfStats()",
        "destroy()",
    ):
        assert method in renderer_js

    assert "OffscreenCanvas" in renderer_js
    assert "renderSignature(" in renderer_js
    assert "QUALITY_SETTINGS" in renderer_js


def test_reef_background_asset_is_small_and_optional() -> None:
    asset = STATIC / "assets" / "reef-bg.webp"
    renderer_js = (STATIC / "renderer_canvas.js").read_text(encoding="utf-8")

    assert asset.exists()
    assert 1_000 < asset.stat().st_size < 500_000
    assert "/static/assets/reef-bg.webp" in renderer_js
    assert "backgroundFailed" in renderer_js
    assert "drawFallbackBackground" in renderer_js
