"""Pilot mode: real classrooms, anonymous codes, template wording only, answers kept in an add-only event log.

  items     the approved question set (data/pilot/items.json, gated by docs/pilot/ITEM_REVIEW.md)
  store     the event log (Postgres via PILOT_DATABASE_URL; SQLite for tests and local runs)
  engine    one graph per pilot class, rebuilt from the log; the student flow as a state machine over events
  routes    the HTTP API under /pilot
"""
