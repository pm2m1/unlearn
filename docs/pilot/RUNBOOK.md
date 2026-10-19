# Pilot runbook

Checklists for setting up the pilot, running a session, and recovering when something breaks. For Parth; the teacher's version is [TEACHER_SHEET.md](TEACHER_SHEET.md). `⟨site⟩` is the live site (`https://unlearn-ejdh.onrender.com`).

## Once, before the first session

- [ ] **Items approved.** Every item to be used is `APPROVED` in [ITEM_REVIEW.md](ITEM_REVIEW.md), and so is the wording block, including a native speaker's check of the Hindi.
- [ ] **Pre-registration committed** (`eval/pilot/PREREGISTRATION.md`) before any real student uses the pilot.
- [ ] **School:** the principal's written permission, and signed opt-in slips ([PARENT_NOTE.md](PARENT_NOTE.md)) collected by the school. Count the signed slips; that is the number of codes.
- [ ] **Neon:** a free project in AWS Asia Pacific (Singapore). Confirm sign-up asked for no card. Copy the connection string (it ends `?sslmode=require`). Never take a manual snapshot: that would keep a copy past deletion.
- [ ] **Render environment** (dashboard → the `unlearn` service → Environment): set `PILOT_DATABASE_URL` to the Neon string and `PILOT_ADMIN_KEY` to a fresh random value (`python -c "import secrets; print(secrets.token_urlsafe(32))"`). Keep both out of git and out of chat.
- [ ] **Deploy:** merge `pilot-mode` into `main`. Render deploys only from `main`. Then check `⟨site⟩/health`: `"pilot": {"configured": true, "ready": true}`, and the demo still works.
- [ ] **Device test with a throwaway class**, before session 1 (record the results in the log at the end):
  - On a laptop, Chrome DevTools → Network: **Slow 4G**, Performance: **4× CPU slowdown**. Open `⟨site⟩/pilot`, enter a test code, answer a full session 1. Note the first load time and the slowest wait after an answer.
  - On **one real, cheap Android phone over mobile data** (not Wi-Fi): the same full session 1. Check that the fractions are readable, the buttons are easy to tap, and the Hindi renders.
  - Delete the test class on the teacher page.
- [ ] **Create the real class** on `⟨site⟩/pilot/teacher` with the admin key and the number of signed slips. Write the **teacher key** on paper at once; it is shown only once.
- [ ] **Print the code slips** (teacher page → Print code slips). Give the teacher the slips, the class code and teacher key (on a separate paper), and the teacher sheet.
- [ ] **Laptop fallback rehearsed once** (below), including installing `cloudflared` (`brew install cloudflared`).

## Session day

**10 minutes before class**
- [ ] **Warm up the server:** on any phone, open `⟨site⟩/pilot` and wait for **● Ready**. A sleeping free service takes about a minute to wake, then about 30 s to start. After a restart it also rebuilds the pilot from the log: about 30 s more per 30 students' session (measured at the free tier's 0.1 CPU). Do this no more than 10 minutes before students start: the service sleeps again after 15 minutes without visitors.
- [ ] Open the teacher page with the class code and key.
- [ ] **Session 2 only:** press **Open session 2**.
- [ ] Slips ready, one per student with a signed parental slip.

**During**
- [ ] **Start row by row, about 30 seconds apart.** Measured at 0.1 CPU with a local database: with 30 students answering about every 15 s, the slowest answer took 0.9 s; with all 30 tapping at the same moment, waits reached about 10 s. Neon adds a network round trip to every answer (not yet measured; the device test will show it).
- [ ] Watch the teacher page (Refresh) to see who is in progress.
- [ ] Note anything unusual (time, what happened, which codes) for the deviation log.

**After**
- [ ] Teacher: the 1–5 "matches your view?" rating and the "I went through the practice topic" tick, any time before the end of the pilot.
- [ ] After session 1: leave session 2 **closed** until its day.
- [ ] After session 2: press **Close session 2**.

## When something goes wrong

| What you see | What it means | What to do |
| --- | --- | --- |
| A student sees **Try again** after answering | The answer wasn't saved (the database didn't answer, even after 3 retries). Nothing was lost; the answer wasn't counted. | Tap Try again. If it keeps happening for several students, check `⟨site⟩/health`, then the Neon dashboard. |
| **Getting ready** | The server is starting or rebuilding from the log. | Wait a minute and tap Start again. Students continue exactly where they were. |
| "That code didn't work" | Typo, or a deleted code. | Check the slip; codes have no 0, O, 1, I or L. |
| "Too many tries" | 30 wrong codes in a minute, across everyone. | Wait a minute. |
| The site doesn't load at all, or Render is down | Hosting problem. | Switch to the laptop fallback, or reschedule. Don't collect answers on paper: they wouldn't be in the log and the sessions wouldn't match the pre-registration. |
| Anything that changes the protocol (a session cut short, a different gap between sessions, the laptop fallback used) | A deviation. | Log it with the date in the pre-registration's deviations section. |

### Laptop fallback (Render down)

The laptop runs the same app against the same Neon log, so nothing is lost and students continue where they were. **Only one server may be live at a time**: each keeps its own in-memory copy of the class.

1. In the repo on the laptop, `.env` must have `FALKOR_PASSWORD`, `PILOT_DATABASE_URL` (the same Neon string) and `PILOT_ADMIN_KEY`.
2. `docker compose --profile dev up -d --build --wait`. The first boot seeds the graphs (about a minute); later boots take seconds. Wait until `http://localhost:8000/pilot/api/status` shows `"ready": true`.
3. `cloudflared tunnel --url http://localhost:8000`. It prints a `https://….trycloudflare.com` address: write it on the board. Students open `<that address>/pilot` and type the same codes.
4. Keep the laptop awake and online until the session ends. The address changes every time `cloudflared` restarts, and Cloudflare gives no uptime guarantee for it.
5. **Before going back to Render:** stop the laptop (`docker compose --profile dev down`), then restart the Render service (dashboard → Manual Deploy → Restart service) so it reloads the log, including the answers given on the laptop.

## Deleting

- **One student withdraws:** the teacher (or Parth) presses Delete next to the code. Their rows are deleted at once, and the class graph is rebuilt without them.
- **End of the pilot,** after the analysis and no later than the date in the parent note:
  1. Export the two CSVs (codes only) for the analysis. Keep them on an encrypted disk; never share them.
  2. Wipe: `POST ⟨site⟩/pilot/api/admin/wipe` with header `X-Pilot-Admin` and body `{"confirm": "WIPE"}`; or run `PILOT_DATABASE_URL=… python scripts/pilot_wipe.py --yes` and then restart the Render service.
  3. Delete the Neon project, and remove `PILOT_DATABASE_URL` and `PILOT_ADMIN_KEY` from Render.
  4. **Backups:** Neon can restore its database to any point in the last 6 hours (free plan), and a deleted project can be recovered for 7 days. So deleted data may remain recoverable for up to 7 days, as the parent note says. After that it is gone; there are no other copies.

## What "free" means here

- **Render:** the pilot runs inside the demo service, so it uses no extra free hours. The workspace has 750 free hours a month; the demo stayed awake for at least 18 hours straight on Oct 18–19, and around the clock would be 744 hours in a 31-day month. If the hours run out, Render suspends the service until the next month.
- **Neon:** the free plan scales its compute to zero after 5 minutes idle; the first write after that takes a moment, which the retries cover. 0.5–1 GB of storage is far more than the pilot needs (well under 1 MB).

## Log

Device test, sessions and deviations, with dates:

- ⟨date⟩: device test. Laptop Slow 4G + 4× CPU: first load ⟨s⟩, slowest answer ⟨s⟩. Android phone ⟨model, browser⟩ on mobile data: first load ⟨s⟩, slowest answer ⟨s⟩, Hindi renders ⟨yes/no⟩.
