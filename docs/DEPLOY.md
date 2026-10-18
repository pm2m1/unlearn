# Deploy and local setup

[Back to the README](../README.md)

## Local setup

You need Docker with Compose v2 (Docker Desktop, or Docker Engine with the compose plugin) and `git`. Nothing else: Python, FalkorDB, the embedding model and the Eedi data all come from the containers.

```
git clone https://github.com/pm2m1/unlearn.git
cd unlearn
cp .env.example .env
sed -i.bak "s/^FALKOR_PASSWORD=.*/FALKOR_PASSWORD=$(openssl rand -hex 16)/" .env && rm .env.bak
docker compose --profile dev up -d --build --wait
```

Then open **http://localhost:8000**.

- **First run.** `--build` takes a few minutes and bakes the embedding model and the pinned Eedi CSVs into the image. On first boot the API seeds every graph before it reports healthy (under a minute), and `--wait` returns once it has. Later starts take seconds.
- **Check it.** `curl -s localhost:8000/health` lists the graphs (`curriculum`, `class_template`, `class_demo`), their node counts and the FalkorDB version.
- **Fill the teacher view.** Open the Teacher tab and click "Simulate the class", or run `curl -X POST localhost:8000/classes/demo/simulate-all`.
- **The two-student demo scenario.** Run `docker compose exec api python scripts/demo_scenario.py`, then open `http://localhost:8000/?class=demo_video`. Asha and Ben both score 40% and have different root causes; `--verify 10` replays both students 10 times.
- **Stop it.** `docker compose --profile dev down`. The graphs stay in the `falkor-data` volume. Add `-v` to wipe them; the next start re-seeds itself.
- **Optional LLMs.** Put any of `GROQ_API_KEY`, `GEMINI_API_KEY` or `OPENROUTER_API_KEY` in `.env` before starting. Without them, every reply is a template built from the graph's rows.
- **A local model instead (dev profile only).** With [Ollama](https://ollama.com) running on the host, set `OLLAMA_BASE_URL=http://host.docker.internal:11434/v1` (and optionally `OLLAMA_MODEL`) in `.env` and run the `up` command again. The app then tries the local model first. The `prod` profile never passes it.

Both containers bind to `127.0.0.1` in the `dev` profile. `docker compose --profile prod up -d --build --wait` publishes only the API on port 8000; FalkorDB has no published port.

## The live demo (Render free tier)

[`render.yaml`](../render.yaml) deploys [`deploy/Dockerfile.render`](../deploy/Dockerfile.render): one container running FalkorDB v4.20.7 and the API. FalkorDB listens only on a unix socket inside the container, with no TCP port. The free tier has 512 MB of RAM, no disk, and sleeps after 15 minutes idle.
- **Baked graphs.** `curriculum`, `class_template`, `class_demo` and `class_demo_video` are built at image build time and saved as `dump.rdb`, so a cold start loads them in seconds. Nothing is ever saved, so demo state resets on every restart.
- **Restarts reset the demo.** The free tier sleeps after 15 minutes idle and may restart at any time, and each restart loads the baked graphs again. The page notices (`server_started_at` changes), clears what it showed and says so, instead of mixing old numbers with the reset state.
- **Recorded chat answers.** The four example questions under the Teacher chat were answered once by the local model against these baked graphs (`deploy/record_chat.py`), and the answers ship in the image.
  - **Instant answers:** the live site can answer them with model wording even when the free Gemini quota is used up. Each is labelled "recorded answer".
  - **Never stale:** one is served only while re-running its tool calls gives the same rows (timestamps aside) and its text passes the receipt check again. After a visitor changes the class, the question is answered live.
  - **Other questions** are always answered live.
- **A pre-filled Teacher tab.** At build time `scripts/simulate_class.py` runs 2 sessions for each of `class_demo`'s 30 students with template wording, so the live Teacher tab opens with cohorts and pending proposals. `class_demo_video` stays fresh for the video's two students.
- **Measured locally under the free tier's limits** (`docker run --memory=512m --memory-swap=512m --cpus=0.1`):
  - Healthy 19 s after start.
  - `demo_scenario.py --verify 10` correct 10/10.
  - Peak memory 381 MiB, over that run, a full session flow through the API and "Simulate the class".
- **Slow at 0.1 CPU.** `bridges` (betweenness over the curriculum graph) takes about 7 s, so the image raises FalkorDB's query timeout to 30 s. "Simulate the class" (60 sessions) takes about 6 minutes.
- **Protecting the free LLM quota:**
  - `UNLEARN_RATE_LIMIT_PER_IP`: 60 requests per address per 10 minutes on the routes that can call the LLM; over that, a 429.
  - `UNLEARN_LLM_DAILY_CAP`: 40 uncached LLM calls per day for the instance, after which replies are templates. A spoofed `X-Forwarded-For` can get past the per-address limit, but not this cap.
  - `UNLEARN_SIMULATE_TEMPLATE`: simulations never call the LLM.
  - All three are off unless set, so local runs are unaffected.

## Working on the code (host Python)

```
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt
make up      # FalkorDB only, on 127.0.0.1:6379
make seed    # load curriculum, build class_template, create class_demo
make test
make serve   # the API and UI on http://localhost:8000
```

## Notes from the README's "Try it" section

- **Live demo:** [unlearn-ejdh.onrender.com](https://unlearn-ejdh.onrender.com) (free tier: first load can take about 1 minute; demo state resets on restart). The two-student demo (Asha and Ben) is at [`?class=demo_video`](https://unlearn-ejdh.onrender.com/?class=demo_video).
- **Demo video:** <link>
- **Run it locally.** With Docker installed, one command starts it once `.env` exists. Without `.env`, FalkorDB exits on startup because its password is empty. Full steps, including setting a real password, are in [Local setup](#local-setup):

  ```
  cp .env.example .env
  docker compose --profile dev up -d --build --wait
  ```

  Then open **http://localhost:8000**. For the two-student demo (Asha and Ben), run `docker compose exec api python scripts/demo_scenario.py` and open `http://localhost:8000/?class=demo_video`.
- **No API keys needed.** Without them every reply is a template built from the graph's rows. The diagnosis, memory and receipts are the same either way.
- **One-page explainer:** [docs/EXPLAIN.md](EXPLAIN.md) covers the graph model, the root-cause query, the search, the evidence weighting, the recall rule and the known weaknesses.
