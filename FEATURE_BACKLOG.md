# Feature backlog — 80+ additions

A prioritized backlog of features that can be built on top of the current Agile CodeBoard intelligence layer. Each item is scoped to be demoable, measurable and shippable in a two-week sprint or less.

**Legend**

- **Impact:** H = high, M = medium
- **Effort:** S = < 1 week, M = 1–2 weeks, L = 3–4 weeks
- **Priority:** P0 = must, P1 = should, P2 = stretch
- **Month:** suggested target month in the six-month roadmap

**Build order rule:** queue/worker foundation → embeddings → RAG/copilot → real-time → enterprise. Do not start LLM features before the evaluation harness exists.

---

## 1. ML models and analytics (18)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 1 | Project-level delivery forecast | Monte Carlo across all sprints/projects, not only one sprint | Python, NumPy | H | M | P0 | M1 |
| 2 | Task completion distribution | P10/P50/P90 completion dates per task, not just a binary late risk | Quantile regression | H | M | P0 | M1 |
| 3 | Scope-creep predictor | Probability that sprint scope grows by more than 20% | Gradient boosting | H | M | P1 | M2 |
| 4 | Bug reopen-risk model | Probability a closed bug is reopened | Logistic/GBM | H | M | P1 | M2 |
| 5 | Estimate-bias model | Per-person/project estimation bias; corrected estimate suggestion | Ridge/GBM | H | M | P1 | M2 |
| 6 | Review-latency model | Predict time to first review and time to merge for PRs | Survival analysis | M | M | P1 | M2 |
| 7 | Dependency critical-path risk | Rank dependencies by schedule impact, not just count | Graph + simulation | H | M | P0 | M1 |
| 8 | Capacity-aware scope recommender | Choose the sprint scope that maximizes expected delivery under capacity | Knapsack + forecast | H | L | P0 | M2 |
| 9 | Release readiness score | Combine open risk, bugs, PR state and test signals into one score | Weighted model | H | M | P1 | M3 |
| 10 | Cycle-time anomaly detection | Flag unusual cycle times and throughput drops | Isolation forest | M | S | P1 | M2 |
| 11 | Similarity-based effort estimation | k-NN over past tasks to suggest hours | Embeddings + k-NN | H | M | P1 | M3 |
| 12 | Blocker/negative-sentiment detection | Detect blockers and frustration in comments | NLP classifier | M | M | P2 | M3 |
| 13 | Burnout/overload risk | Privacy-aware overload score from load, overtime and reopen patterns | Aggregated model | H | M | P1 | M4 |
| 14 | Skill inference | Infer skills from completed tasks and tags | Embeddings + clustering | H | M | P1 | M3 |
| 15 | Bug triage priority | Suggest priority/severity for new bugs | Classifier | H | M | P1 | M2 |
| 16 | Duplicate-bug classifier | Embedding similarity + supervised duplicate model | Embeddings + classifier | H | M | P0 | M3 |
| 17 | Time-to-first-response forecast | Predict how long a new issue waits for an owner response | Survival analysis | M | S | P2 | M3 |
| 18 | Escalation-risk model | Predict client/customer escalation risk | GBM | M | M | P2 | M4 |

## 2. LLM and copilot features (14)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 19 | Natural-language issue creation | “Create a high-priority bug for the payments API, due Friday” → structured issue | LLM + JSON schema | H | M | P0 | M3 |
| 20 | Meeting notes → tasks | Extract tasks, decisions and action items from notes | LLM + RAG | H | M | P0 | M3 |
| 21 | Weekly status report | Generate a cited report from risks, forecast, workload and activity | LLM + tools | H | M | P0 | M3 |
| 22 | Retrospective summarizer | Summarize a sprint and propose action items | LLM + RAG | H | M | P1 | M3 |
| 23 | Conversational risk drill-down | “Why is #364 risky, and what would reduce it?” | LLM + SHAP | H | M | P0 | M3 |
| 24 | Conversational what-if planner | “What if we move the deadline and add one developer?” | LLM + forecast tools | H | M | P0 | M3 |
| 25 | PR/commit summary on issue | Summarize linked PR changes for reviewers | LLM + GitHub data | H | M | P1 | M2 |
| 26 | Release-notes generator | Draft release notes from merged PRs and issues | LLM + templates | H | M | P1 | M3 |
| 27 | Acceptance criteria/test cases | Generate acceptance criteria and test ideas from an issue | LLM + issue context | H | M | P1 | M3 |
| 28 | Onboarding copilot | Answer “how does this project/team work?” for new members | RAG over docs | H | M | P1 | M4 |
| 29 | Permission-aware policy/FAQ assistant | Answer from policies without exposing restricted content | RAG + ACL | H | M | P1 | M4 |
| 30 | Multilingual summaries | Translate/summarize issues and comments for distributed teams | LLM | M | S | P1 | M4 |
| 31 | Task decomposition | Break a large task into subtasks with estimates | LLM + estimator | H | M | P0 | M3 |
| 32 | Notification digest summarization | Turn many notifications into one readable digest | LLM | M | S | P2 | M4 |
| 33 | Inline issue rewriting | Improve title/description, preserve links and tags | LLM | M | S | P2 | M3 |

## 3. Vector embeddings and semantic features (12)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 34 | Embedding duplicate detection | Replace TF-IDF with sentence-transformer similarity | Embeddings, Qdrant | H | M | P0 | M3 |
| 35 | Hybrid semantic search | BM25 + vector + rerank across issues, comments and docs | Qdrant, reranker | H | M | P0 | M3 |
| 36 | Similar-task recommendation | Suggest historical tasks for estimates and planning | Embeddings | H | M | P1 | M3 |
| 37 | RAG over comments/files/docs | Index project knowledge for the copilot | Embeddings, Qdrant | H | L | P0 | M3 |
| 38 | Auto-tagging | Suggest tags from issue text and past tagging patterns | Embeddings + classifier | H | M | P1 | M3 |
| 39 | Related-issue graph | Cluster and link issues by semantic similarity | Embeddings, graph | M | M | P1 | M3 |
| 40 | Semantic tag consolidation | Merge duplicate/overlapping tags | Embeddings | M | S | P2 | M3 |
| 41 | Commit-to-issue linking | Match commits/PRs to issues by semantic intent, not only `#id` | Embeddings | H | M | P1 | M2 |
| 42 | Issue outlier detection | Flag unusual issues/requests for review | Embeddings + anomaly | M | M | P2 | M4 |
| 43 | Cross-project knowledge transfer | Find similar past projects/tasks across workspaces | Embeddings | H | M | P1 | M4 |
| 44 | Vector skill matching | Match tasks to people by semantic skill profiles | Embeddings | H | M | P1 | M4 |
| 45 | Release-note clustering | Group merged PRs into themes for release notes | Embeddings | M | S | P2 | M3 |

## 4. Redis queues, workers and real-time (13)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 46 | Async model training queue | Train without blocking a PHP worker; show progress | Redis, RQ/Celery | H | M | P0 | M1 |
| 47 | Background forecasts/optimizer | Run large sprint/project jobs asynchronously | Redis worker | H | M | P0 | M1 |
| 48 | Webhook ingestion queue | Retry, backoff and dead-letter handling for GitHub events | Redis, worker | H | M | P0 | M1 |
| 49 | Notification fan-out worker | Send in-app/email/Slack notifications reliably | Redis worker | H | M | P1 | M2 |
| 50 | Scheduled digests | Daily/weekly risk, due-date and workload digests | Worker + cron | H | S | P1 | M2 |
| 51 | Redis rate limiting | Token buckets for login, API, assistant and search | Redis | H | M | P0 | M4 |
| 52 | Distributed locks | Prevent duplicate training/optimizer runs | Redis locks | M | S | P1 | M1 |
| 53 | Real-time board events | Publish issue/comment/move events to the browser | Redis pub/sub, Mercure | H | L | P0 | M2 |
| 54 | Presence and typing | Show who is viewing/editing a board | SSE/WebSocket | M | M | P1 | M2 |
| 55 | Job dashboard | Inspect queued/running/failed jobs and retry | Redis + UI | M | M | P1 | M2 |
| 56 | Idempotent outbox processing | Exactly-once-style event delivery | DB outbox + worker | H | M | P0 | M1 |
| 57 | Cache warming | Precompute dashboards/forecasts after updates | Redis worker | H | S | P1 | M5 |
| 58 | Background exports | Generate CSV/PDF/report files in the background | Worker | M | S | P2 | M5 |
| 59 | Model drift alerts | Detect feature/calibration drift and notify admins | Worker + metrics | H | M | P1 | M3 |

## 5. JavaScript, UX and product features (16)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 60 | Command palette | Cmd+K search and actions across issues, sprints and views | JS | H | M | P1 | M5 |
| 61 | Keyboard-first navigation | Shortcuts for create, search, move, comment and assign | JS | H | S | P1 | M5 |
| 62 | Drag-and-drop Gantt | Edit dates and dependencies directly on the timeline | JS, DnD | H | L | P1 | M5 |
| 63 | Live presence avatars | See who is on the board/timeline | SSE | M | S | P1 | M2 |
| 64 | Optimistic UI + conflict toasts | Instant updates with a clear 409 recovery flow | JS | H | M | P0 | M2 |
| 65 | Offline-first PWA | Installable app with draft queue and background sync | Service worker | H | L | P1 | M2 |
| 66 | Customizable dashboard widgets | Choose and arrange KPI/risk/workload widgets | JS | H | M | P1 | M5 |
| 67 | Saved filters/views | Save issue/board filters per user/team | JS + DB | H | S | P1 | M5 |
| 68 | Dark mode and density | Theme and compact/comfortable modes | CSS/JS | M | S | P2 | M5 |
| 69 | Accessible charts | Keyboard/screen-reader-friendly charts and tables | JS/ARIA | H | M | P1 | M5 |
| 70 | Inline AI actions | Summarize, explain, rewrite and create subtasks from an issue | JS + LLM | H | M | P0 | M3 |
| 71 | What-if sliders | Interactive deadline/capacity sliders that re-run forecasts | JS + API | H | M | P1 | M3 |
| 72 | Onboarding tour | Guided first-run checklist for admins and users | JS | M | S | P2 | M5 |
| 73 | Mobile board/assistant | Responsive task board, notifications and chat | JS/PWA | H | M | P1 | M5 |
| 74 | Notification grouping | Group by issue/project, filter unread | JS | M | S | P1 | M4 |
| 75 | Bulk AI actions | Summarize/assign/tag selected issues in one action | JS + LLM | H | M | P0 | M3 |

## 6. Platform, integrations and enterprise (14)

| # | Feature | What it adds | Tech | Impact | Effort | Priority | Month |
|---|---|---|---|---|---|---|---|
| 76 | GitHub App | Installation flow, least-privilege tokens, PR checks | GitHub API | H | L | P0 | M2 |
| 77 | GitLab/Bitbucket parity | Same linking/DORA events for other providers | Webhooks | H | M | P1 | M3 |
| 78 | Slack/Teams bot | Risk, assignment and PR notifications in chat | Slack/Teams API | H | M | P1 | M2 |
| 79 | Calendar integration | Sync sprint dates, leave and milestones | Google/Outlook | M | M | P2 | M4 |
| 80 | Email-to-issue | Create/reply to issues via IMAP worker | IMAP + worker | H | M | P1 | M4 |
| 81 | Webhook subscriptions | Let customers subscribe to issue/sprint events | Signed webhooks | H | M | P1 | M4 |
| 82 | Public API v1 + SDKs | Stable OpenAPI spec and typed clients | OpenAPI, JS/Python | H | M | P1 | M4 |
| 83 | Audit log UI | Filter/export privileged actions with hash chain | PHP UI | H | M | P0 | M4 |
| 84 | Multi-workspace tenancy | Workspace-scoped data, roles and settings | DB + auth | H | L | P0 | M4 |
| 85 | SSO/OIDC/SAML + SCIM | Enterprise login and user provisioning | OIDC/SAML/SCIM | H | L | P0 | M4 |
| 86 | 2FA/TOTP + sessions | Admin 2FA, session rotation and token hashing | PHP/auth | H | M | P0 | M4 |
| 87 | Data retention/export/delete | GDPR-style export, retention and delete workflows | PHP/worker | H | M | P1 | M4 |
| 88 | Plugin SDK/marketplace | Extension points for custom automations | PHP SDK | M | L | P2 | M6 |
| 89 | Billing/usage metering | Track seats, API calls and AI usage | Billing API | M | L | P2 | M6 |

---

## Top 20 to build first

1. Async training queue + job dashboard.
2. Background forecast/optimizer jobs.
3. Real-data evaluation and calibration.
4. Project-level delivery forecast.
5. Dependency critical-path risk.
6. Embedding duplicate detection.
7. Hybrid semantic search.
8. RAG index over project knowledge.
9. Natural-language issue creation.
10. Weekly status report with citations.
11. Conversational risk drill-down.
12. Conversational what-if planner.
13. Inline AI actions.
14. Real-time board events.
15. Optimistic UI + conflict toasts.
16. GitHub App + DORA dashboard.
17. Multi-workspace tenancy.
18. SSO/OIDC + 2FA.
19. Audit log UI.
20. Accessibility and mobile polish.

---

## Dependencies and sequencing

```text
Queue/worker + observability
    └── async training/forecast/optimizer
    └── webhook ingestion + notification fan-out
    └── idempotent outbox

Embeddings + Qdrant
    └── duplicate detection + semantic search
    └── RAG + LLM copilot
    └── cross-project knowledge transfer

Real-time transport (Mercure/SSE)
    └── live board + presence
    └── optimistic UI + conflict recovery
    └── offline/PWA queue

Workspaces + RBAC
    └── SSO/SCIM + audit log
    └── per-tenant rate limits and quotas
```

## How to use this backlog

- Pick one P0 per sprint and one P1 that can ship independently.
- Every feature needs a demo, a metric and a test before it counts as done.
- Do not start a feature that depends on missing queue/embedding infrastructure; build the dependency first.
- Re-rank monthly using user-study feedback and production metrics.
- If time slips, keep the P0 list and cut P2 first.

**Backlog prepared for the next semester. Added by Vedant Chalke.**
