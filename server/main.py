"""
dhamma.bell push service
Sends a Web Push notification at each Vipassana timetable event,
respecting each subscriber's timezone and silenced bells.

Env vars required:
  VAPID_PUBLIC_KEY   (base64url)
  VAPID_PRIVATE_KEY  (base64url)
  VAPID_SUBJECT      e.g. mailto:you@example.com
Optional:
  DB_PATH            default /data/dhammabell.db
  CORS_ORIGINS       comma-separated, default *
"""
import asyncio, json, os, sqlite3
from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from pywebpush import webpush, WebPushException

VAPID_PUBLIC = os.environ["VAPID_PUBLIC_KEY"]
VAPID_PRIVATE = os.environ["VAPID_PRIVATE_KEY"]
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "mailto:admin@example.com")
DB_PATH = os.environ.get("DB_PATH", "/data/dhammabell.db")

# The official 10-day course timetable (dhamma.org)
EVENTS = {
    "04:00": "Morning wake-up bell",
    "04:30": "Meditate — hall or room",
    "06:30": "Breakfast break",
    "08:00": "Group meditation in the hall",
    "09:00": "Meditate as instructed",
    "11:00": "Lunch break",
    "12:00": "Rest and teacher interviews",
    "13:00": "Meditate — hall or room",
    "14:30": "Group meditation in the hall",
    "15:30": "Meditate as instructed",
    "17:00": "Tea break",
    "18:00": "Group meditation in the hall",
    "19:00": "Discourse in the hall",
    "20:15": "Group meditation in the hall",
    "21:00": "Question time in the hall",
    "21:30": "Lights out",
}


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS subs (
             endpoint TEXT PRIMARY KEY,
             sub_json TEXT NOT NULL,
             tz       TEXT NOT NULL DEFAULT 'UTC',
             enabled  TEXT NOT NULL DEFAULT '{}',
             created  TEXT NOT NULL
           )"""
    )
    return conn


class SubscribeBody(BaseModel):
    subscription: dict
    tz: str = "UTC"
    enabled: dict[str, bool] = {}


def _send(sub_json: str, payload: dict) -> bool:
    """Blocking push send. Returns False if the subscription is dead."""
    try:
        webpush(
            subscription_info=json.loads(sub_json),
            data=json.dumps(payload),
            vapid_private_key=VAPID_PRIVATE,
            vapid_claims={"sub": VAPID_SUBJECT},
            ttl=120,
        )
        return True
    except WebPushException as ex:
        code = getattr(ex.response, "status_code", None)
        return code not in (404, 410)  # gone -> prune
    except Exception:
        return True  # transient; keep subscription


async def bell_loop():
    sent: set[str] = set()
    while True:
        try:
            conn = db()
            rows = conn.execute("SELECT endpoint, sub_json, tz, enabled FROM subs").fetchall()
            conn.close()
            dead = []
            for endpoint, sub_json, tz, enabled_json in rows:
                try:
                    now = datetime.now(ZoneInfo(tz))
                except Exception:
                    now = datetime.now(ZoneInfo("UTC"))
                hhmm = now.strftime("%H:%M")
                if hhmm not in EVENTS:
                    continue
                enabled = json.loads(enabled_json or "{}")
                if enabled.get(hhmm) is False:
                    continue
                dedupe = f"{endpoint}|{now.date()}|{hhmm}"
                if dedupe in sent:
                    continue
                sent.add(dedupe)
                name = EVENTS[hhmm]
                h = now.hour % 12 or 12
                ap = "am" if now.hour < 12 else "pm"
                payload = {"title": name, "body": f"{h}:{now.minute:02d} {ap} — the gong has sounded."}
                ok = await asyncio.to_thread(_send, sub_json, payload)
                if not ok:
                    dead.append(endpoint)
            if dead:
                conn = db()
                conn.executemany("DELETE FROM subs WHERE endpoint = ?", [(e,) for e in dead])
                conn.commit()
                conn.close()
            if len(sent) > 20000:
                sent.clear()
        except Exception:
            pass
        await asyncio.sleep(20)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    task = asyncio.create_task(bell_loop())
    yield
    task.cancel()


app = FastAPI(title="dhamma.bell push service", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/vapid-public-key")
def vapid_key():
    return {"key": VAPID_PUBLIC}


@app.post("/subscribe")
def subscribe(body: SubscribeBody):
    endpoint = body.subscription.get("endpoint")
    if not endpoint:
        raise HTTPException(400, "subscription.endpoint missing")
    conn = db()
    conn.execute(
        """INSERT INTO subs (endpoint, sub_json, tz, enabled, created)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(endpoint) DO UPDATE SET
             sub_json = excluded.sub_json, tz = excluded.tz, enabled = excluded.enabled""",
        (endpoint, json.dumps(body.subscription), body.tz,
         json.dumps(body.enabled), datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()
    return {"ok": True}


@app.delete("/subscribe")
def unsubscribe(body: SubscribeBody):
    endpoint = body.subscription.get("endpoint")
    conn = db()
    conn.execute("DELETE FROM subs WHERE endpoint = ?", (endpoint,))
    conn.commit()
    conn.close()
    return {"ok": True}


@app.get("/health")
def health():
    conn = db()
    n = conn.execute("SELECT COUNT(*) FROM subs").fetchone()[0]
    conn.close()
    return {"ok": True, "subscribers": n}
