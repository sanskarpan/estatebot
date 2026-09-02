from pathlib import Path


def test_static_frontend_keeps_resilience_and_accessibility_contracts():
    html = Path("backend/static/index.html").read_text(encoding="utf-8")
    javascript = Path("backend/static/assets/app.js").read_text(encoding="utf-8")
    css = Path("backend/static/assets/style.css").read_text(encoding="utf-8")

    assert 'name="viewport"' in html
    assert 'aria-label="Conversation"' in html
    assert 'aria-live="polite"' in html
    assert 'aria-controls="about-dialog"' in html
    assert '<dialog id="about-dialog"' in html
    assert 'aria-haspopup="menu"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "MAX_VISIBLE_MESSAGES = 100" in javascript
    assert "requestAnimationFrame" in javascript
    assert "startRateLimitCountdown" in javascript
    assert "response was interrupted before verification finished" in javascript
    assert "aboutDialog.showModal()" in javascript
    assert "modelTrigger.focus()" in javascript
    assert "Refresh restored message attribution" in javascript
    assert ":focus-visible" in css
    assert "min-height: 48px" in css
    assert "prefers-reduced-motion" in css
