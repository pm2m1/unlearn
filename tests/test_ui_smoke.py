"""Browser smoke test (skipped unless Playwright and its Chromium are installed locally):
load /, start a session, answer one question, and see the graph panel update."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from unlearn import queries as Q  # noqa: E402
from unlearn.db import copy_graph, delete_graph, run_batched  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLASS_ID = "pytest_ui"


@pytest.fixture(scope="module")
def server():
    g = f"class_{CLASS_ID}"
    delete_graph(g)
    copy_graph("class_template", g)
    run_batched(g, Q.LOAD_STUDENTS, [{"id": "s18", "alias": "Rosa"}])
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(ROOT / "api"), str(ROOT)]), "UNLEARN_LLM": "template"}
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "main:app", "--app-dir", "api", "--host", "127.0.0.1",
                             "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    base = f"http://127.0.0.1:{port}"
    import httpx
    for _ in range(120):
        try:
            if httpx.get(f"{base}/health", timeout=1).status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.25)
    yield base
    proc.terminate()
    proc.wait(timeout=10)
    delete_graph(g)


def test_answer_one_question_updates_the_graph(server):
    with playwright.sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as e:  # Playwright installed without its browser
            pytest.skip(f"no Chromium for Playwright: {e}")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"{server}/?class={CLASS_ID}&student=s18")
        page.wait_for_selector("#student-select option", state="attached")
        page.click("#start-btn")
        page.wait_for_selector("#question-card:not([hidden]) .option")
        page.wait_for_function("state.cy && state.cy.nodes('.construct').length > 0")
        asked = page.evaluate("state.cy.nodes('.asked').map(n => n.id())")
        assert len(asked) == 1
        page.click("#q-options .option >> nth=0")
        page.wait_for_function("document.querySelectorAll('#steps > li').length >= 2")
        # The answered construct is now marked attempted (or became a suspect with a misconception shown).
        page.wait_for_function(f"state.cy.getElementById('{asked[0]}').hasClass('attempted') || "
                               f"state.cy.getElementById('{asked[0]}').hasClass('asked') || state.cy.nodes('.mis').length > 0")
        assert page.is_visible("#feedback .tag")
        browser.close()
        assert errors == []
