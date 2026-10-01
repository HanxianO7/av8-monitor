# Alta Via 8 rifugio monitor (backup to AV1)

Checks the AV8 huts every hour on GitHub and messages you on Telegram **only** when:
- 🟢 a booking engine (Plose, Firenze) shows rooms for 2 on your night
- 🟡 a hut page adds 2027 booking text (e.g. "bookings open")
- ⚠️ a check fails 3 runs in a row
- 📅 a dated reminder is due (Plose 10 Jan, Firenze 1 Feb 2027)

Never books or pays. Live table in `STATUS.md`. Stops after 30 Jun 2027.

## Setup (same as AV1, ~15 min)
1. **New Telegram bot**: @BotFather → `/newbot` → copy token. Message the bot once, then open
   `https://api.telegram.org/bot<TOKEN>/getUpdates` and copy the `"chat":{"id":` number.
2. **New public repo** `av8-monitor`; upload everything here **including the `.github` folder**.
3. **Secrets** (Settings → Secrets and variables → Actions): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.
4. **Test**: Actions → Run workflow → tick *test alert*. You should get ✅.
5. **First real run**: Run workflow without the tick, then open `STATUS.md` and `state/debug/`.
6. **Hourly trigger** on cron-job.org (GitHub's own schedule drops runs):
   - New fine-grained token: only repo `av8-monitor`, Actions: Read and write, expiry 31 Jul 2027.
   - URL `https://api.github.com/repos/<username>/av8-monitor/actions/workflows/monitor.yml/dispatches`,
     POST, minute 5 every hour, headers `Authorization: Bearer <token>`, `Accept: application/vnd.github+json`,
     body `{"ref":"main"}`. Test run should return **204**.

## First-run checks (do these once)
- `state/debug/plose.txt` and `firenze.txt`: the RoomRaccoon date parameters are a best guess.
  If the text doesn't show 23/27 Jun 2027, send me the file and I'll fix the URL.
- Any hut showing ⚠️ after the first run: send me the error.
