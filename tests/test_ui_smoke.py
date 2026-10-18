"""Browser smoke tests (skipped unless Playwright and its Chromium are installed locally): a session updates the
graph panel; the Teacher tab survives one failing card; switching student, or a server restart, clears the view."""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright.sync_api")

from unlearn import queries as Q  # noqa: E402
from unlearn import tools as T  # noqa: E402
from unlearn.db import delete_graph, recreate_graph, run, run_batched  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CLASS_ID = "pytest_ui"


@pytest.fixture(scope="module")
def server():
    g = f"class_{CLASS_ID}"
    recreate_graph("class_template", g)
    run_batched(g, Q.LOAD_STUDENTS, [{"id": "s18", "alias": "Rosa"}, {"id": "s01", "alias": "Asha"}, {"id": "s02", "alias": "Ben"}])
    # Asha and Ben share a confident misconception (the same wrong option, twice each): one cohort, one pending regroup.
    (wrong,), _ = run(g, "MATCH (o:Option)-[:INDICATES]->(:Misconception) RETURN o.qid AS qid, o.key AS key ORDER BY qid, key LIMIT 1")
    for sid in ("s01", "s02"):
        T.start_session(CLASS_ID, sid, f"{sid}-seed")
        for _ in range(2):
            T.record_attempt(CLASS_ID, sid, wrong["qid"], wrong["key"], f"{sid}-seed")
    T.propose(CLASS_ID, "p-ui", "regroup", {"group_id": "g-ui"}, ["s01", "s02"])
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


def _page(p, server, path):
    try:
        browser = p.chromium.launch()
    except Exception as e:  # Playwright installed without its browser
        pytest.skip(f"no Chromium for Playwright: {e}")
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.goto(f"{server}{path}")
    page.wait_for_selector("#student-select option", state="attached")
    return browser, page, errors


def test_teacher_tab_shows_cohorts_and_proposals_when_one_card_fails(server):
    """The live regression: one failing request (bridges is the slow one on a 0.1-CPU host) left every Teacher card
    empty, because the four loaded through one Promise.all."""
    with playwright.sync_playwright() as p:
        browser, page, errors = _page(p, server, f"/?class={CLASS_ID}")
        page.route("**/bridges", lambda route: route.fulfill(status=503, content_type="application/json",
                                                            body='{"detail": "query timed out"}'))
        page.click("button[data-view=teacher]")
        page.wait_for_selector("#cohorts .chip")
        assert sorted(page.locator("#cohorts .chip").all_inner_texts()) == ["Asha", "Ben"]
        assert page.locator("#proposals .p-head").count() == 1
        assert "Could not load this: query timed out" in page.inner_text("#bridges")
        assert page.locator("#keystones li").count() > 0
        assert "sessions so far" in page.inner_text("#class-summary")
        browser.close()
        assert errors == []


def test_switching_student_clears_the_session_and_shows_their_recall(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = _page(p, server, f"/?class={CLASS_ID}&student=s18")
        page.click("#start-btn")
        page.wait_for_selector("#question-card:not([hidden]) .option")
        page.wait_for_function("state.cy && state.cy.nodes().length > 0")
        page.select_option("#student-select", "s01")
        page.wait_for_selector("#recall-banner:not([hidden])")  # Asha has shown a misconception twice
        assert page.is_hidden("#question-card") and page.inner_text("#feedback") == ""
        assert page.inner_text("#graph-title") == "Start a session to see the prerequisite graph"
        assert page.evaluate("state.cy.nodes().length") == 0 and page.evaluate("state.session") is None
        page.select_option("#student-select", "s18")  # Rosa has nothing to recall
        page.wait_for_function("document.querySelector('#recall-banner').hidden")
        browser.close()
        assert errors == []


def test_a_server_restart_is_announced_and_clears_the_view(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = _page(p, server, f"/?class={CLASS_ID}&student=s18")
        page.click("#start-btn")
        page.wait_for_selector("#question-card:not([hidden]) .option")

        def restarted(route):
            body = route.fetch().json()
            route.fulfill(json={**body, "server_started_at": body["server_started_at"] + 1})
        page.route(f"**/classes/{CLASS_ID}/students", restarted)
        page.click("button[data-view=teacher]")
        page.wait_for_function("document.querySelector('#toast')?.textContent.includes('restarted')")
        assert page.evaluate("state.session") is None
        browser.close()
        assert errors == []


def test_theme_toggle_restyles_the_graph_and_the_guide_stays_dismissed(server):
    with playwright.sync_playwright() as p:
        browser, page, errors = _page(p, server, f"/?class={CLASS_ID}&student=s18")
        assert page.is_visible("#guide")
        page.click("#start-btn")
        page.wait_for_function("state.cy && state.cy.nodes('.construct').length > 0")
        session = page.evaluate("state.session.id")
        node_bg = "state.cy.nodes('.construct').first().style('background-color')"
        before, theme = page.evaluate(node_bg), page.evaluate("document.documentElement.dataset.theme")
        page.click("#theme-toggle")
        assert page.evaluate("document.documentElement.dataset.theme") != theme
        assert page.evaluate(node_bg) != before and page.evaluate("state.session.id") == session  # restyled in place
        page.click("#guide-dismiss")
        page.reload()
        page.wait_for_selector("#student-select option", state="attached")
        assert page.is_hidden("#guide") and page.evaluate("document.documentElement.dataset.theme") != theme  # both remembered
        browser.close()
        assert errors == []
