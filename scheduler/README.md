# Daily outreach run — Windows Task Scheduler

`python -m scheduler.run_daily` runs once a day. It reads replies and
bounces first, then:

1. Finds new prospects.
2. Enriches them.
3. Routes each one to email and/or WhatsApp.
4. Sends day 0 messages.
5. Sends due follow-ups (days 2, 3, 7 and 14).
6. Writes the daily report and sends it to Telegram (on Sundays, the
   weekly report too).

The Windows task named `AI_Mentors_Daily_Run` starts it every morning.

All commands below are run from `C:\Users\butik\Documents\Control_Center`.

## 0. Before the first real run

The task does **not** see variables you set in a PowerShell window. Put
these in `Control_Center\.env`, one `NAME=value` per line (the run
loads that file), or set them once with `setx`:

| Purpose | Variables |
|---|---|
| Prospect search | `SERPER_API_KEY` |
| Email (Brevo SMTP) | `SMTP_HOST=smtp-relay.brevo.com`, `SMTP_PORT=587`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM=info@salehhaidar.com` |
| WhatsApp (same Meta account as outreach/) | `WHATSAPP_PHONE_ID`, `WHATSAPP_TOKEN`, `META_GRAPH_VERSION=v22.0` |
| Approved WhatsApp templates | `WHATSAPP_APPROVED_TEMPLATES=alpha_intro_v1_en` (add each name Meta approves, comma separated) |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` |
| Email replies (optional) | `IMAP_HOST`, `IMAP_PORT=993`, `IMAP_USER`, `IMAP_PASSWORD` |
| Defaults (optional) | `ATLAS_LANGUAGE=ar`, `ATLAS_COUNTRY=AE` |

Then try it without sending anything:

```powershell
.\venv\Scripts\python.exe -m scheduler.run_daily --dry-run
```

## 1. Register the task (one command)

```powershell
powershell -ExecutionPolicy Bypass -File .\scheduler\setup_windows_task.ps1
```

- **Time:** daily at 09:00 Dubai time. For another time, add
  `-DubaiTime 08:30`. To see what it would do without registering, add
  `-WhatIf`.
- **"Access is denied":** open PowerShell as Administrator and run it
  again.

## 2. Verify it

```powershell
schtasks /Query /TN AI_Mentors_Daily_Run /V /FO LIST
```

Look at **Next Run Time**, **Last Run Time** and **Last Result** (0 means
it worked). The Scheduler page in the Control Center shows the same
information.

## 3. Run it manually once

```powershell
schtasks /Run /TN AI_Mentors_Daily_Run
```

Or run it in the foreground, with output on screen:

```powershell
.\venv\Scripts\python.exe -m scheduler.run_daily
```

A real run happens once a day. A second real run on the same day is
skipped unless you add `--force`.

## 4. Pause and resume

- **Windows:**
  ```powershell
  schtasks /Change /TN AI_Mentors_Daily_Run /DISABLE
  schtasks /Change /TN AI_Mentors_Daily_Run /ENABLE
  ```
- **Telegram:** send `PAUSE` or `RESUME` to the bot. This creates or
  removes `data\scheduler\paused.flag`, which the run checks at start.
  The Pause and Resume buttons on the Scheduler page do the same.

## 5. Delete it

```powershell
schtasks /Delete /TN AI_Mentors_Daily_Run /F
```

## 6. Where the logs go

| File | What |
|---|---|
| `data\scheduler\run_log.jsonl` | one line per run: steps, results, errors with tracebacks, the run's log |
| `data\scheduler\last_run.log` | the last run's log as plain text |
| `data\reports\daily_YYYYMMDD.json` | the daily report (`_dryrun` for dry runs) |
| `data\reports\weekly_YYYYMMDD.json` | Sunday's weekly report |
| `data\scheduler\routes_YYYYMMDD.json` | the channel decision for each new prospect |
| `data\email\`, `data\whatsapp\` | sent logs, prospect state, suppression lists |

## Notes

- **Restarts:** Task Scheduler's "restart on failure" covers a run that
  fails to *start*. A run that starts but has a failing step records it,
  alerts on Telegram, carries on with the remaining steps, and exits
  with code 1.
- **Meta webhooks:** WhatsApp delivery and read receipts and incoming
  replies arrive as webhooks. Nothing receives them yet. Payloads saved
  as `data\whatsapp\webhooks\*.json` are processed on the next run.
- **Telegram STATUS:** answered when the daily run starts. To get
  answers any time, keep this running:
  `.\venv\Scripts\python.exe -m atlas_services.telegram_reporter --listen`
