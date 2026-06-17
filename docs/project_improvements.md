# Project Improvements & Feature Suggestions

> Original analysis: 2026-06-09
> Last updated: 2026-06-15 (re-audited against current `main`)

---

## Progress Since Last Audit

Several items from the 2026-06-09 list have shipped:

| #   | Item                            | Status                                                                      |
| --- | ------------------------------- | --------------------------------------------------------------------------- |
| 1   | OAuth state memory leak         | ✅ **Fixed** — moved to `oauth_states` DB table with 10-min TTL              |
| 3   | Silent stubs in catalog         | ✅ **Fixed** — Slack/Document actions now raise `NotImplementedError`        |
| 6   | Variable resolution brittleness | ✅ **Fixed** — dotted paths + fail-loud + `{{x \| "default"}}` syntax done |
| 7   | Retry logic on Prefect tasks    | ✅ **Fixed** — `retries=2, retry_delay_seconds=30` on all four Gmail tasks   |
| 2   | Gmail Pub/Sub race condition    | ✅ **Fixed** — defer-and-drain replaces the dropped-notification path        |
| 2b  | Stub actions in catalog         | ✅ **Fixed** — `status: "coming_soon"` gated out of `catalog_introspector`   |
| 8   | Schedule trigger                | 🟡 **Partial** — wired into deployment (`CronSchedule`); no dedicated UI    |
| 4   | WebSocket real-time updates     | 🟡 **Partial** — wired, but 5-s polling, not per-node events                |
| 11  | Condition node power-up         | 🟡 **Partial** — 5 operators + ANY/ALL match; no nested groups              |
| 3   | Flow swallows node errors       | ✅ **Fixed** — `node_failed` WS event + persisted `workflow_runs` audit      |
| 5   | Persistent execution audit log  | 🟡 **Partial** — `workflow_runs` table + per-node results; no history UI yet |

**New since last audit:** the test suite now collects **178 tests** across `tests/unit`, `tests/integration` (auth, gmail, workflow, orchestration). The "no tests" gap is closed.

---

## Bugs to Fix First

### ~~1. Gmail Notification Drop — `gmail/services/gmail_service.py`~~ ✅ Done
The drop is fixed with **defer-and-drain**. When a notification arrives mid-sync it no
longer returns — it sets a `sync_pending` flag and bumps `latest_observed_history_id`
(new columns on `connected_accounts`). The owning sync runs a drain loop: after each
cumulative fetch it re-checks `sync_pending` under the row lock and, if set, fetches once
more from the (now-advanced) baseline. Because `history.list` is cumulative and
`ProcessedMessages` dedups, one extra pass catches everything that landed during the
window. The `OperationalError`/NOWAIT path retries with a blocking lock so a colliding
newcomer still records its flag instead of being dropped. Baseline advances to the
high-water mark, not the owner's single id. Covered by `tests/unit/gmail/handle_gmail_update_test.py`.

### ~~2. Stub Actions Still in Catalog — `utils/catalog_introspector.py`~~ ✅ Done
`SendSlackMessageAction` and `CreateDocumentAction` carry `json_schema_extra["status"] =
"coming_soon"` (`workflow/schemas/action.py`), and `_build_node_definitions` now skips any
node tagged `coming_soon`. The two stubs no longer reach the catalog, so they can't be
dragged onto the canvas. The `raise NotImplementedError()` in `master_flow.py` stays as a
runtime backstop for any pre-existing workflow that still references them. Guarded by
`tests/unit/test_catalog_introspector.py::test_coming_soon_actions_gated`.

### ~~3. Flow Swallows Node Errors — `orchestration/flows/master_flow.py`~~ ✅ Done
The flow no longer swallows node errors. Each failed condition/action is logged to
the Prefect run logger, recorded in `failed_nodes`, downstream children are pruned,
and the run raises `RuntimeError` at the end (Prefect marks it Failed). On top of
that, the flow now **persists** a per-node audit record and **emits** a
`node_failed` WebSocket event:
- New `workflow_runs` table (`workflow/models/workflow_run_record.py`,
  `WorkflowRunService`) stores `{ node_id: { output, status, error } }`, overall
  `status` (`success`/`partial`/`failed`), `duration_ms`, `prefect_run_id`,
  `trigger_data`. This also delivers the persistence half of #5.
- The worker runs in a separate process from the in-memory WS manager, so it
  persists the failure and the existing WS poll loop
  (`workflow_router.py`) reads undelivered failures, broadcasts
  `{type: "node_failed", node_id, error, ...}`, and marks them notified.
- Frontend (`dashboard/+layout.svelte`) shows a per-step error toast.
Covered by `tests/unit/orchestration/flows/test_build_run_audit.py` and
`tests/integration/workflow/test_workflow_run_service.py`.

---

## High-Impact Improvements

### 4. WebSocket: Move From Polling to Event Push
`core/websocket_manager.py` is wired now — `workflow_router.py:274` opens `/ws/workflows/{user_id}` and broadcasts. **But** it polls Prefect every 5 s (`get_latest_runs_status` + `asyncio.sleep(5)`) and only sends coarse run-level state. There are still no per-node events.

**What to add:**
- Emit from inside `master_flow` as each node runs: `node_started`, `node_completed`, `node_failed`, `flow_finished`
- Drop the 5-s poll loop in favor of push (or keep poll only as reconnect fallback)
- Frontend lights up individual nodes in real time, not just the run row

### 5. Persistent Execution Audit Log — 🟡 Partial
The `workflow_runs` DB table now exists (`WorkflowRunRecord` /
`WorkflowRunService`, written by the master flow on every run) and stores
per-node results, overall status, duration, `prefect_run_id` and `trigger_data` —
shipped alongside #3. **Still missing:** a history/inspection UI that reads this
table (the data is persisted but the history page still reads Prefect
introspection only).

Run history currently comes from **Prefect flow-run introspection** (`DeploymentService.get_history` / `get_workflow_history` → `WorkflowRun` Pydantic schema). The history page works, but there is **no record of per-node results or which `{{variables}}` were substituted** — only Prefect's run name/state/duration.

**The `workflow_runs` DB table** (distinct from the Prefect-derived schema), now implemented:
```
workflow_id     UUID FK
triggered_at    TIMESTAMP
trigger_data    JSONB
node_results    JSONB   -- { node_id: { output, status, error } }
status          ENUM    -- success | partial | failed
duration_ms     INT
```
Gives users the "what value did this node actually see" view that Prefect alone can't, and backs the `node_failed` surfacing from #3.

### ~~6. Variable Resolution — Add Default Values — `utils/resolve_variables.py` ✅ Done~~
Dotted-path traversal (`{{node_id.body.from.email}}`), fail-loud-on-missing, **and**
default/fallback syntax (`{{node_id.subject | "No Subject"}}`) are all done. Defaults
accept double/single-quoted or bare literals; a missing path with no default still raises.
The recursive resolver and object/dict traversal are solid. Nothing outstanding.

### ~~7. Add `retry_delay_seconds` to Tasks — `orchestration/tasks/gmail_tasks.py`~~ ✅ Done
All four Gmail tasks now carry `@task(retries=2, retry_delay_seconds=30, ...)` — backoff
prevents hammering a rate-limited Gmail API on retry. Nothing outstanding.

---

## Missing Features Worth Building

### 8. Complete Trigger Executors
All four trigger schemas exist (`manual`, `email_received`, `new_sheet_row`, `schedule`). Execution coverage:

| Trigger | Status | Effort |
|---|---|---|
| `EmailReceivedTrigger` | ✅ Functional | — |
| `ManualTrigger` | ✅ `/workflow/run` endpoint exists | — |
| `ScheduleTrigger` | 🟡 Deployment sets `CronSchedule`; no UI to enter cron | Low |
| `NewSheetRowTrigger` | ❌ Schema only, no executor / polling | Medium |
| Webhook (generic HTTP) | ❌ Not defined anywhere | Medium |

Priority: **Schedule UI → Webhook → Google Sheets**. Schedule is nearly there — just surface the cron field in the editor.

### 9. Error Handling Node
Still absent. A failed Gmail task is caught and `print`ed (#3) with no fallback path. No way to model "if this fails, do X."
**Options:** `OnError` edge type (route on failure) or `TryCatch` node (wrap a subgraph). Required for production-grade reliability.

### 10. Workflow Templates
Still absent. AI can generate workflows but there are no starting points (cold-start).
**Built-in seeds:** auto-label newsletters, out-of-office reply, forward to Slack, archive by sender, draft follow-up reply. Low backend cost (hardcoded JSON), high activation value.

### 11. Condition Node — Nested Logic — `utils/evaluate_condition.py`
Now supports operators `equals`, `contains`, `exists`, `greater_than`, `less_than` and a flat `match_type` of `ANY`/`ALL` ✅. Still missing:
- Nested AND/OR rule **groups** (only one flat level today)
- More operators: `starts_with`, `ends_with`, `regex`
- Multi-output branching (still just true/false handles)

Extend `IfConditionConfig.rules` into a recursive group schema, then update the evaluator.

---

## Smaller Wins

| Issue | Status | Fix |
|---|---|---|
| `user_settings` table unused | ❌ Model + relationship exist, no routes/UI | Add UI for notification prefs, default label colors |
| No workflow export/import | ❌ | `GET /workflow/{id}/export` → JSON download |
| No workflow versioning | 🟡 `version` column exists (always 1) | Increment + snapshot `config` before each update |
| Gmail watch expiry (7 days) | ❌ Only set on connect | Scheduled job to renew `watch()` before expiry |
| No manual trigger UI | 🟡 `/run` endpoint exists | Add dashboard button with mock trigger payload |
| No OpenAPI docs UI in prod | ❌ | Enable `/docs` behind auth gate |

---

## Priority Order

### Do Now
_All "Do Now" items shipped._

> ~~Gmail notification-drop bug (#1)~~ ✅ shipped · ~~Gate stub actions (#2)~~ ✅ shipped · ~~`retry_delay_seconds` (#7)~~ ✅ shipped · ~~Variable default-value syntax (#6)~~ ✅ shipped

### Do Next (high impact)
5. Per-node WebSocket events — replace 5-s poll (#4); `node_failed` now rides the
   poll loop, but `node_started`/`node_completed` + true push are still open
6. ~~Persistent audit log with `node_results` (#5)~~ ✅ table shipped — history UI remains
7. ~~Surface node failures to the user (#3)~~ ✅ shipped (`node_failed` event + audit row)

### Do Later (new features)
8. Schedule trigger UI (cron field)
9. Error handling node (#9)
10. Condition rule groups + regex (#11)
11. Workflow templates (#10)
12. Generic webhook + Google Sheets triggers (#8)
