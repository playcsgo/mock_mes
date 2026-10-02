import re
from datetime import timedelta

from app import repository
from app.config import settings
from app.models import utc_now

WINDOW_MIN = 60
TOP_N = 3
STATION_RE = re.compile(r"^ST-?(\d{1,2})$", re.IGNORECASE)

HELP = "可以輸入：\n・狀態：各站良率\n・ST-03：單站良率與前幾名失敗原因"


def pct(rate: float) -> str:
    return f"{rate:.1%}"


async def answer(db, text: str) -> str:
    text = text.strip()
    if text.lower() in ("狀態", "status"):
        return await _status(db)
    if m := STATION_RE.match(text):
        return await _station(db, f"ST-{int(m.group(1)):02d}")
    return HELP


def _since():
    return utc_now() - timedelta(minutes=WINDOW_MIN)


def _mark(rate: float) -> str:
    return "🔴" if rate < settings.alert_threshold else "🟢"


async def _status(db) -> str:
    since = _since()
    rows = await repository.yield_by_station(db, since=since)
    if not rows:
        return f"最近 {WINDOW_MIN} 分鐘沒有資料。"

    lines = [f"各站良率（最近 {WINDOW_MIN} 分鐘，門檻 {settings.alert_threshold:.0%}）"]
    lines += [
        f"{_mark(r['yield_rate'])} {r['station']}  {pct(r['yield_rate'])}（{r['total']} 筆）"
        for r in rows
    ]
    fails = await repository.top_failures(db, since=since, limit=TOP_N)
    if fails:
        lines.append("\n最常見的失敗：")
        lines += [f"{f['station']} {f['fail_code']} ×{f['count']}" for f in fails]
    return "\n".join(lines)


async def _station(db, station: str) -> str:
    since = _since()
    rows = await repository.yield_by_station(db, since=since)
    row = next((r for r in rows if r["station"] == station), None)
    if row is None:
        return f"{station} 最近 {WINDOW_MIN} 分鐘沒有資料。"

    rate = row["yield_rate"]
    lines = [
        f"{_mark(rate)} {station}（最近 {WINDOW_MIN} 分鐘）",
        f"良率 {pct(rate)}，{row['passed']}/{row['total']} 通過",
    ]
    if rate < settings.alert_threshold:
        lines.append(f"⚠️ 低於門檻 {settings.alert_threshold:.0%}")
    fails = await repository.top_failures(db, station=station, since=since, limit=TOP_N)
    if fails:
        lines.append("\n失敗原因：")
        lines += [f"{f['fail_code']} ×{f['count']}" for f in fails]
    return "\n".join(lines)
