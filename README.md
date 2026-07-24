# SAP BTP Administration Toolkit

A CLI toolkit for SAP BTP administrators that authenticates against a
subaccount's XSUAA tenant, inspects the resulting OAuth token, analyzes
the service key structure, tests connectivity to core platform APIs,
runs an endpoint health sweep, and exports session reports — all from
one interactive menu.

Built as a portfolio project demonstrating SAP BTP platform knowledge
combined with production-style Python (OOP, typing, dataclasses,
centralized logging and error handling).

## Overview

On a trial landscape, the Accounts API will correctly return `403
insufficient_scope` once authenticated — this toolkit treats that as an
expected, handled outcome rather than a failure, and is built to be
useful even when full API scopes aren't available.

## Architecture

**Runtime flow** — every menu action follows this same request path, reusing one token across a session:

![Architecture diagram: Your Script authenticates via XSUAA to get an OAuth token, then uses that Bearer token against SAP BTP Platform APIs, returning JSON that becomes dashboard/CSV/JSON output](docs/architecture-diagram.svg)

**Code layering** — how that flow maps onto the folders in this repo:

```
┌─────────────┐      ┌───────────────┐      ┌────────────────────┐
│   app.py     │─────▶│  api/ layer   │─────▶│  SAP BTP / XSUAA   │
│ (CLI + state)│      │ auth/accounts/│      │  (real HTTP calls) │
│              │      │ entitlements/ │      └────────────────────┘
│              │      │ users         │
│              │      └───────────────┘
│              │      ┌───────────────┐
│              │─────▶│ services/     │  service key analysis, quota
│              │      │ layer         │  alerts, inventory, reports
│              │      └───────────────┘
│              │      ┌───────────────┐
└──────────────┘─────▶│ utils/ layer  │  config, logging, dashboard,
                       │               │  token decoding, exceptions
                       └───────────────┘
```

Each layer only talks to the one below it: `app.py` never touches
`requests` directly, and the `services/` layer never reads `.env`
directly — everything routes through `utils/config.py`.

## Folder Structure

```
btp-explorer/
├── api/
│   ├── auth.py              # OAuth client credentials flow
│   ├── base.py               # Shared HTTP client + result classification
│   ├── accounts.py           # Accounts Service client
│   ├── entitlements.py       # Entitlements Service client
│   └── users.py              # XSUAA SCIM Users client
├── config/
│   └── service_key.example.json   # Template - copy to service_key.json
├── services/
│   ├── service_key_analyzer.py    # Phase 3
│   ├── endpoint_checker.py        # Phase 5
│   └── report_generator.py        # Phase 7
├── utils/
│   ├── config.py              # Phase 8 - .env driven settings
│   ├── logger.py               # Phase 6 - rotating file + console logs
│   ├── dashboard.py            # Phase 4 - live session dashboard
│   ├── token_decoder.py        # Phase 2 - JWT inspector
│   └── exceptions.py           # Shared exception hierarchy
├── reports/                    # Generated JSON/CSV/TXT reports (gitignored)
├── logs/                        # app.log (gitignored)
├── screenshots/                 # For README/demo images
├── app.py                       # Entry point
├── requirements.txt
├── .env.example
└── README.md
```

## Installation

```bash
git clone <your-repo-url>
cd btp-explorer
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
cp config/service_key.example.json config/service_key.json
# then paste your real BTP service key into config/service_key.json
```

Run it:

```bash
python app.py
```

## Configuration

All runtime settings live in `.env` (see `.env.example`):

| Variable            | Purpose                                   | Default                     |
|---------------------|--------------------------------------------|------------------------------|
| `SERVICE_KEY_PATH`  | Path to your real service key JSON          | `config/service_key.json`   |
| `LOG_LEVEL`         | `DEBUG` / `INFO` / `WARNING` / `ERROR`      | `INFO`                       |
| `TIMEOUT`           | HTTP timeout (seconds) for all requests     | `10`                          |

**Never commit `config/service_key.json` or `.env`** — both are
gitignored by default. If you've ever pasted a real service key into a
chat, doc, or commit, rotate it in the BTP cockpit.

## Features

- **Authentication** — OAuth 2.0 client credentials flow against XSUAA
- **JWT Inspector** — decodes and pretty-prints token claims, scopes,
  authorities, lifetime, and expiry status
- **Service Key Analyzer** — parses client ID, identity zone, region,
  XSUAA details, and every listed endpoint — without ever printing the
  client secret
- **API Connectivity Testing** — Accounts, Entitlements, and Users
  (XSUAA SCIM) clients, each returning a classified result
  (Reachable / Forbidden / Unauthorized / Timeout / Network Error)
- **Endpoint Health Checker** — sweeps every endpoint in the service
  key and reports latency + status, colour-coded
- **Report Generator** — exports a session snapshot (auth status, token
  info, endpoint results) as JSON, CSV, and TXT into `reports/`
  (`report_*`) — distinct from the subaccount inventory export below,
  which covers identity + quota + reachability rather than session state
- **Live Dashboard** — refreshes after every action showing auth,
  token, API health, and quota alert count at a glance
- **Quota Alert Checker** — parses Entitlements assignment data and
  flags anything at or above 80% of its entitled amount, the same
  threshold check a BTP admin does manually in the cockpit
- **Subaccount Inventory Export** — a governance-report-style CSV
  combining identity zone details, entitlement/quota status, and
  endpoint reachability in one file (`reports/subaccount_inventory_*.csv`)
- **Colour-coded output throughout** — every table and status line uses
  `rich`, not just `print()` — Reachable/OK renders green, Forbidden/
  over-threshold renders red or yellow
- **Enterprise logging** — rotating `logs/app.log`, every action logged
- **No raw tracebacks** — every failure path resolves to a clear,
  human-readable message

## Cost, Access, and Security Auditing

Three additional checks beyond basic connectivity, each backed by a real SAP BTP API:

| Feature | File | API | Requires |
|---|---|---|---|
| **Cost Tracking** | `services/cost_tracker.py` | Account Budgets Service (`account_budgets_service_url` in the main service key) | Standard entitlement — likely `403` on Trial |
| **Access Auditing** | `services/access_auditor.py` | XSUAA Authorization Management API (`uaa.apiurl/sap/rest/authorization/v2/...`) | XSUAA instance on the `apiaccess` plan — a normal `application`-plan key will `403` here |
| **Security Auditing** | `services/security_auditor.py` | Audit Log Retrieval API (`/auditlog/v2/auditlogrecords`) | Its own `auditlog-management` service instance/key — set `AUDIT_LOG_SERVICE_KEY_PATH` in `.env` |

These are real, correctly-implemented API clients — but on a Trial
landscape or without the extra service instances provisioned, they'll
report `Forbidden`/`Unauthorized` rather than data. That's the toolkit
telling the truth about entitlements, not a bug.

## Roadmap

- [ ] Provisioning / Metadata / Events API clients (currently shown as
      "Not Tested" placeholders on the dashboard)
- [ ] Arrow-key CLI navigation (currently numbered menu)
- [ ] Automated tests (pytest) for the api/ and services/ layers
- [ ] Optional read-only web dashboard (FastAPI + the same service layer)

## License

MIT
