# dhamma.bell

The 10-day Vipassana course timetable (dhamma.org) as gong alarms on your phone.
Offline-first PWA + optional FastAPI Web Push service for bells when the app is closed.

## How it works

- **Offline / app open:** the PWA schedules every bell locally and plays a synthesized
  Burmese gong (Web Audio — no assets, works with no network). Drop a `bell.mp3` in the
  repo root to use a real recording instead (e.g. Pariyatti's official gong download).
- **Online / app closed:** the FastAPI service in `server/` sends a Web Push at each
  timetable event in your timezone, honoring which bells you've silenced. This is the
  only mechanism that reaches a closed app, and the only one iOS supports at all
  (iOS 16.4+, app must be added to the Home Screen).

## Deploy the PWA (GitHub Pages)

Repo → Settings → Pages → Deploy from branch → main. Open the URL on your phone,
Add to Home Screen.

## Deploy the push service (any VPS with Caddy + Docker)

```bash
cd server
python3 gen_vapid_keys.py        # copy output into a .env file
echo "VAPID_SUBJECT=mailto:you@yourdomain.com" >> .env
docker compose up -d --build
curl localhost:8091/health
```

Caddyfile:

```
bell.yourpersonaldomain.com {
    reverse_proxy 127.0.0.1:8091
}
```

Then set one line in `index.html` and push:

```js
const API_BASE = "https://bell.yourpersonaldomain.com";
```

Reopen the app once while online — it subscribes and syncs automatically.
Toggled bells re-sync on every change and whenever you come back online.

## Notes

- Closed-app pushes use the system notification sound (the web platform doesn't allow
  custom push sounds); the gong itself plays whenever the app is open.
- The timetable and tradition belong to dhamma.org / VRI. This is a personal practice aid.
