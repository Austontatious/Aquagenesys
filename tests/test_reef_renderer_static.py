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
