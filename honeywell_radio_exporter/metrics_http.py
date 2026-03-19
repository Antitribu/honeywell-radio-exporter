"""HTTP server: / -> /ui/, /ui/, /api/devices, /metrics/ (Prometheus from DB on scrape)."""

from __future__ import annotations

import json
import errno
import logging
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable, Dict, List, Optional, Type

from honeywell_radio_exporter.live_events import LiveNotifier
from urllib.parse import parse_qs, urlparse

from prometheus_client import Gauge, generate_latest, REGISTRY
from prometheus_client.exposition import CONTENT_TYPE_LATEST

logger = logging.getLogger(__name__)

_app_started_at: float = 0.0
_py_process_start: float = 0.0

G_MESSAGES_IN_DB = Gauge(
    "honeywell_messages_in_db",
    "Rows in messages table",
)
G_DEVICES_IN_DB = Gauge(
    "honeywell_devices_in_db",
    "Rows in devices table",
)
G_LAST_MESSAGE_UNIX = Gauge(
    "honeywell_last_message_unixtime",
    "Unix time of latest message row",
)


def _format_duration(seconds: float) -> str:
    if seconds is None or seconds < 0:
        return ""
    s = int(seconds)
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m and not d:
        parts.append(f"{m}m")
    if not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


def make_handler(
    creds: Dict[str, Any],
    load_dashboard: Callable[[], Dict[str, Any]],
    metrics_refresh: Callable[[], None],
    get_meta: Callable[[], Dict[str, Any]],
    live_events: Optional[LiveNotifier] = None,
    stop_event: Optional[threading.Event] = None,
) -> Type[BaseHTTPRequestHandler]:
    class H(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:
            logger.debug("%s - %s", self.address_string(), fmt % args)

        def do_GET(self) -> None:
            path = urlparse(self.path).path.rstrip("/") or "/"
            try:
                if path == "/graceful_shutdown":
                    # A clean shutdown endpoint intended for development.
                    # It stops consumer/janitor/watchers via the shared `stop_event`,
                    # and stops this HTTP server loop so the main process can exit.
                    msg = {
                        "status": "ok",
                        "message": "Shutting down gracefully. Server will exit shortly.",
                    }
                    b = json.dumps(msg).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)

                    def _shutdown() -> None:
                        try:
                            if stop_event:
                                stop_event.set()
                        finally:
                            # Stop ThreadingHTTPServer. This will cause serve_forever() to return.
                            try:
                                self.server.shutdown()
                            except Exception:
                                pass

                    # Avoid shutdown from the request thread in case the server waits for it.
                    threading.Thread(target=_shutdown, daemon=True).start()
                    return
                if path == "" or path == "/":
                    self.send_response(302)
                    self.send_header("Location", "/ui/")
                    self.end_headers()
                    return
                # /ui and /ui/ both normalize to /ui via rstrip("/") — serve here (no redirect loop)
                if path == "/ui":
                    body = UI_HTML.encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if path == "/api/devices":
                    metrics_refresh()
                    dash = load_dashboard()
                    if not isinstance(dash, dict):
                        dash = {}
                    devices: List[Any] = dash.get("devices") or []
                    zones = dash.get("zones") or []
                    msg_counts = dash.get("message_code_counts") or []
                    fault_log = dash.get("fault_log") or []
                    puzzle_log = dash.get("puzzle_log") or {}
                    boiler_status = dash.get("boiler_status") or []
                    dhw_status = dash.get("dhw_status") or []
                    recent_warnings = dash.get("recent_warnings") or []
                    meta = get_meta()
                    payload = {
                        "generated_at": meta.get("generated_at"),
                        "device_count": len(devices),
                        "devices": devices,
                        "zones": zones,
                        "zone_count": len(zones),
                        "message_code_counts": msg_counts,
                        "fault_log": fault_log,
                        "puzzle_log": puzzle_log,
                        "boiler_status": boiler_status,
                        "dhw_status": dhw_status,
                        "recent_warnings": recent_warnings,
                        **{k: v for k, v in meta.items() if k != "generated_at"},
                    }
                    b = json.dumps(payload, indent=2, default=str).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                if path == "/api/messages/by_code":
                    from honeywell_radio_exporter.db.connection import connect

                    qs = parse_qs(urlparse(self.path).query)
                    code_q = (qs.get("code") or [""])[0].strip()
                    if not code_q or len(code_q) > 32:
                        self.send_error(400, "query param code required (max 32 chars)")
                        return
                    try:
                        lim = int((qs.get("limit") or ["25"])[0])
                    except ValueError:
                        lim = 25
                    lim = max(1, min(100, lim))
                    try:
                        off = int((qs.get("offset") or ["0"])[0])
                    except ValueError:
                        off = 0
                    off = max(0, off)
                    conn = connect(creds)
                    try:
                        from honeywell_radio_exporter.db.repository import Repository

                        payload = Repository(conn).list_messages_for_api(
                            code=code_q, limit=lim, offset=off
                        )
                    finally:
                        conn.close()
                    b = json.dumps(payload, default=str).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                if path == "/api/messages/by_device":
                    from honeywell_radio_exporter.db.connection import connect

                    qs = parse_qs(urlparse(self.path).query)
                    did = (qs.get("device_id") or [""])[0].strip()
                    if not did or len(did) > 32:
                        self.send_error(
                            400, "query param device_id required (max 32 chars)"
                        )
                        return
                    try:
                        lim = int((qs.get("limit") or ["25"])[0])
                    except ValueError:
                        lim = 25
                    lim = max(1, min(100, lim))
                    try:
                        off = int((qs.get("offset") or ["0"])[0])
                    except ValueError:
                        off = 0
                    off = max(0, off)
                    conn = connect(creds)
                    try:
                        from honeywell_radio_exporter.db.repository import Repository

                        payload = Repository(conn).list_messages_for_api(
                            device_id=did, limit=lim, offset=off
                        )
                    finally:
                        conn.close()
                    b = json.dumps(payload, default=str).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                if path == "/api/messages/by_zone":
                    from honeywell_radio_exporter.db.connection import connect

                    qs = parse_qs(urlparse(self.path).query)
                    z = (qs.get("zone") or [""])[0].strip()
                    if not z or len(z) > 32:
                        self.send_error(400, "query param zone required (max 32 chars)")
                        return
                    try:
                        lim = int((qs.get("limit") or ["25"])[0])
                    except ValueError:
                        lim = 25
                    lim = max(1, min(100, lim))
                    try:
                        off = int((qs.get("offset") or ["0"])[0])
                    except ValueError:
                        off = 0
                    off = max(0, off)
                    conn = connect(creds)
                    try:
                        from honeywell_radio_exporter.db.repository import Repository

                        payload = Repository(conn).list_messages_for_api(
                            zone=z, limit=lim, offset=off
                        )
                    finally:
                        conn.close()
                    b = json.dumps(payload, default=str).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", str(len(b)))
                    self.end_headers()
                    self.wfile.write(b)
                    return
                if path == "/api/events":
                    if not live_events:
                        self.send_error(503, "live events unavailable")
                        return
                    self.send_response(200)
                    self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Connection", "keep-alive")
                    self.send_header("X-Accel-Buffering", "no")
                    self.end_headers()
                    try:
                        seq = live_events.current_seq()
                        self.wfile.write(
                            f"data: {json.dumps({'seq': seq})}\n\n".encode("utf-8")
                        )
                        self.wfile.flush()
                        while True:
                            prev = seq
                            seq = live_events.wait_after(prev, 25.0)
                            if seq > prev:
                                self.wfile.write(
                                    f"data: {json.dumps({'seq': seq})}\n\n".encode(
                                        "utf-8"
                                    )
                                )
                                self.wfile.flush()
                            else:
                                self.wfile.write(b": ping\n\n")
                                self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                    return
                if path == "/metrics" or path == "/metrics/":
                    metrics_refresh()
                    data = generate_latest(REGISTRY)
                    self.send_response(200)
                    self.send_header("Content-Type", CONTENT_TYPE_LATEST)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return
                self.send_error(404)
            except BrokenPipeError:
                pass
            except Exception as e:
                logger.exception("HTTP %s", e)
                try:
                    self.send_error(500, str(e))
                except Exception:
                    pass

    return H


def refresh_metrics_from_db(creds: Dict[str, Any]) -> None:
    from honeywell_radio_exporter.db.connection import connect
    from honeywell_radio_exporter.db.repository import Repository

    conn = connect(creds)
    try:
        snap = Repository(conn).metrics_snapshot()
        G_MESSAGES_IN_DB.set(snap["messages_total_approx"])
        G_DEVICES_IN_DB.set(snap["devices_total"])
        ts = snap["last_message_time"]
        if ts:
            G_LAST_MESSAGE_UNIX.set(ts)
        else:
            G_LAST_MESSAGE_UNIX.set(0)
    finally:
        conn.close()


UI_HTML = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width"/>
<title>Honeywell RAMSES</title>
<style>
body{font-family:system-ui,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:1rem;}
.sub{color:#94a3b8;font-size:.875rem;} .sub a{color:#38bdf8;}
table{width:100%;border-collapse:collapse;font-size:.875rem;}
th,td{padding:.5rem;border-bottom:1px solid #334155;text-align:left;}
th{background:#1e293b;color:#94a3b8;}
.thbtn{background:transparent;border:0;color:#64748b;cursor:pointer;font:inherit;padding:0;margin-left:.25rem;}
.thbtn:hover{color:#cbd5e1;}
.thbtn.on{color:#38bdf8;}
.mono{font-family:monospace;font-size:.8rem;}
.classcell{vertical-align:middle;line-height:1.25;max-width:22rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.class-inline{color:#94a3b8;font-size:.8125rem;}
h1{font-size:1.25rem;margin:0 0 .5rem;color:#f1f5f9;}
h2{font-size:1.1rem;margin:1.25rem 0 .5rem;color:#cbd5e1;}
.lvl-WARNING{color:#fbbf24;}.lvl-ERROR,.lvl-CRITICAL{color:#f87171;font-weight:600;}
.mt-row{cursor:pointer;user-select:none;}.mt-row:hover{background:#1e293b;}
.mt-row td:first-child::before{content:'▸ ';color:#64748b;display:inline-block;width:1em;}
.mt-row.mt-open td:first-child::before{content:'▾ ';}
.mt-desc td{background:#0c1326;color:#cbd5e1;font-size:.8125rem;line-height:1.45;border-bottom:1px solid #334155;padding:.75rem .75rem .75rem 2rem;}
.mt-subtbl{margin-top:.85rem;width:100%;font-size:.75rem;border-collapse:collapse;}
.mt-subtbl th{background:#1a2332;color:#94a3b8;padding:.4rem .5rem;text-align:left;}
.mt-subtbl td{padding:.4rem .5rem;border-bottom:1px solid #273549;vertical-align:top;}
.mt-subtbl .mono{word-break:break-all;}
.btn{background:#1e293b;color:#e2e8f0;border:1px solid #334155;border-radius:.4rem;padding:.25rem .5rem;font-size:.75rem;cursor:pointer;}
.btn:hover{background:#24324a;}
.temp-above{color:#4ade80;font-weight:600;}
.temp-below{color:#f87171;font-weight:600;}
.temp-at-set{color:#94a3b8;}
.battery-low{color:#f87171;font-weight:700;}
.stale{color:#f87171;font-weight:700;}
.boiler-on{color:#4ade80;font-weight:600;}.boiler-off{color:#64748b;}
</style></head><body>
<p class="sub">Data from Honeywell RAMSES · <a href="/metrics/">Prometheus</a> · <a href="/api/devices">JSON</a><span id="p"></span><span id="e"></span></p>
<h1>Devices</h1>
<p class="sub" style="margin-top:-.25rem">Temp vs setpoint: <span class="temp-above">green</span> = above, <span class="temp-below">red</span> = below, grey = at setpoint or no setpoint to compare.</p>
<table><thead><tr><th>ID</th><th>Class</th><th>Name</th><th>Zone</th><th>Temp</th><th>Zone temp report (zone)</th><th>Setpt</th><th>Heat %</th><th>Window</th><th>Battery</th><th>From msgs</th><th>To msgs</th><th>Last seen from (UTC)</th><th>Last seen to (UTC)</th></tr></thead>
<tbody id="t"></tbody></table>
<h2>Boiler</h2>
<p class="sub"><span class=mono>10:…</span> = OpenTherm bridge (<span class=mono>3EF0</span> flame/CH/DHW, <span class=mono>3200</span>/<span class=mono>3210</span> temps, <span class=mono>22D9</span> target). <span class=mono>13:…</span> = BDR relay-only: <b>CH act.</b> / <b>Mod %</b> from <span class=mono>0008</span> relay_demand (RP) and <span class=mono>3EF0</span> bursts (TPI on/off); no flame or flow temps on RF.</p>
<table><thead><tr><th>Kind</th><th>Device</th><th>Flame</th><th>CH act.</th><th>DHW</th><th>CH en.</th><th>Mod %</th><th>Flow °C</th><th>Return °C</th><th>Target °C</th><th>CH max °C</th><th>Updated (UTC)</th></tr></thead><tbody id="boil"></tbody></table>
<h2>DHW (Hot Water)</h2>
<p class="sub">From <span class=mono>dhw_temp</span>/<span class=mono>dhw_params</span>/<span class=mono>dhw_mode</span> packets (typically controller <span class=mono>01:</span>). Relay boilers do not report cylinder temperature directly; this is controller-centric.</p>
<table><thead><tr><th>DHW</th><th>Active</th><th>Mode</th><th>Temp °C</th><th>Setpt °C</th><th>Diff °C</th><th>Overrun</th><th>Controller</th><th>Updated (UTC)</th></tr></thead><tbody id="dhw"></tbody></table>
<h2>Zones</h2>
<table><thead><tr><th>Zone ID</th><th>Name</th><th>Following schedule</th><th>Setpt (°C)</th><th>Temp (°C)</th><th>Heat demand %</th><th>RQ</th><th>RP</th><th>Other</th><th>Total</th><th>Updated (UTC)</th></tr></thead><tbody id="zt"></tbody></table>
<h2>Message counts by type</h2>
<p class="sub">Click a row to expand a short description of that RAMSES message type.</p>
<table><thead><tr><th>Code</th><th>Type name</th><th>Count</th><th>Last message (UTC)</th></tr></thead><tbody id="mt"></tbody></table>
<h2>Host library &amp; USB gateway</h2>
<p class="sub"><b>ramses_tx</b> = Python stack on this host. <b>Stick (!V)</b> = evofw3 firmware line (queried once at startup if safe). <b>Puzzle table below</b> = engine/parser from RF <span class=mono>7FFF</span> packets (may differ from stick string).</p>
<table><thead><tr><th>Item</th><th>Value</th></tr></thead><tbody id="ver"></tbody></table>
<h2>Gateway puzzle (7FFF) versions</h2>
<p class="sub">ramses_rf <b>engine</b> / <b>parser</b> from signature puzzle packets. One DB row per gateway when versions <b>first appear</b> or <b>change</b> (repeated identical packets are ignored).</p>
<h3 style="margin:1rem 0 .35rem;font-size:.95rem;color:#cbd5e1">Current version per gateway</h3>
<table><thead><tr><th>Gateway (src)</th><th>Engine</th><th>Parser</th><th>Version changes</th><th>Stored events</th><th>First seen (UTC)</th><th>Last change (UTC)</th></tr></thead><tbody id="pg"></tbody></table>
<h3 style="margin:1rem 0 .35rem;font-size:.95rem;color:#cbd5e1">Change history (newest first)</h3>
<table><thead><tr><th>Received (UTC)</th><th>Gateway</th><th>Engine</th><th>Parser</th><th>Note</th></tr></thead><tbody id="pe"></tbody></table>
<h2>Fault log (system_fault / 0418)</h2>
<p class="sub">Controller-reported events; <b>Event time</b> = device log timestamp, <b>Received</b> = when stored.</p>
<table><thead><tr><th>Event time</th><th>State</th><th>Type</th><th>Device</th><th>Log#</th><th>Verb</th><th>Received (UTC)</th><th>Extra</th></tr></thead><tbody id="ft"></tbody></table>
<h2>Recent warnings &amp; errors</h2>
<p class="sub">Last 50 WARNING+ records from this process (lost on restart).</p>
<table><thead><tr><th>Time (UTC)</th><th>Level</th><th>Logger</th><th>Message</th></tr></thead><tbody id="wt"></tbody></table>
<script>
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');}
var _sort={}; // tableId -> {col:int, dir:1|-1}
function _cellText(tr, col){
  var td=tr&&tr.children&&tr.children[col]; if(!td) return '';
  return (td.textContent||'').trim();
}
function _cmp(a,b){return a<b?-1:(a>b?1:0);}
function _parseVal(s){
  if(s==null) return {t:'s',v:''};
  var x=String(s).trim();
  if(x===''||x==='—') return {t:'s',v:''};
  // datetime
  var dt=Date.parse(x);
  if(isFinite(dt)) return {t:'n',v:dt};
  // number (strip %, °C etc.)
  var m=x.replace(/[%°C]/g,'').match(/-?\d+(\.\d+)?/);
  if(m){ var n=parseFloat(m[0]); if(!isNaN(n)) return {t:'n',v:n}; }
  return {t:'s',v:x.toLowerCase()};
}
function _compareRows(trA,trB,col){
  var a=_parseVal(_cellText(trA,col));
  var b=_parseVal(_cellText(trB,col));
  if(a.t===b.t) return _cmp(a.v,b.v);
  // numeric before string
  return a.t==='n'?-1:1;
}
function _applySortToTbody(tbody, pairRows){
  if(!tbody || !tbody.id) return;
  var st=_sort[tbody.id]; if(!st) return;
  var col=st.col, dir=st.dir;
  if(pairRows){
    // mt-row + mt-desc
    var pairs=[];
    for(var i=0;i<tbody.children.length;i++){
      var r=tbody.children[i];
      if(!r.classList || !r.classList.contains('mt-row')) continue;
      var d=tbody.children[i+1];
      pairs.push({r:r,d:(d&&d.classList&&d.classList.contains('mt-desc'))?d:null});
    }
    pairs.sort(function(x,y){ return dir*_compareRows(x.r,y.r,col); });
    pairs.forEach(function(p){ tbody.appendChild(p.r); if(p.d) tbody.appendChild(p.d); });
  }else{
    var rows=[].slice.call(tbody.querySelectorAll('tr'));
    rows.sort(function(a,b){ return dir*_compareRows(a,b,col); });
    rows.forEach(function(r){ tbody.appendChild(r); });
  }
}
function _setSort(tableId,col){
  var st=_sort[tableId]||{col:col,dir:1};
  if(st.col===col){ st.dir = -st.dir; } else { st.col=col; st.dir=1; }
  _sort[tableId]=st;
  // update button states
  var tb=document.getElementById(tableId);
  if(tb && tb.parentNode){
    var table=tb.parentNode;
    var ths=table.querySelectorAll('thead th');
    ths.forEach(function(th,i){
      var b=th.querySelector('button.thbtn');
      if(!b) return;
      var on=(i===st.col);
      b.classList.toggle('on',on);
      b.textContent = on ? (st.dir===1?'↑':'↓') : '↕';
    });
  }
  _applySortToTbody(document.getElementById(tableId), tableId==='t' || tableId==='zt' || tableId==='mt');
}
function makeSortable(tbodyId){
  var tb=document.getElementById(tbodyId); if(!tb||!tb.parentNode) return;
  var table=tb.parentNode;
  var ths=table.querySelectorAll('thead th');
  ths.forEach(function(th,i){
    if(th.querySelector('button.thbtn')) return;
    var b=document.createElement('button');
    b.type='button'; b.className='thbtn'; b.textContent='↕';
    b.addEventListener('click',function(ev){ ev.stopPropagation(); _setSort(tbodyId,i); });
    th.appendChild(b);
  });
}
function initSort(){
  ['t','boil','dhw','zt','mt','ver','pg','pe','ft','wt'].forEach(makeSortable);
}
function tempTd(x){
var t=x.temperature_c,s=x.setpoint_c;
if(t==null||t==='')return '<td class=mono>—</td>';
var ts=typeof t==='number'?String(t):String(t);
if(s==null||s==='')return '<td class=mono>'+esc(ts)+'</td>';
var tn=parseFloat(t),sn=parseFloat(s);
if(isNaN(tn)||isNaN(sn))return '<td class=mono>'+esc(ts)+'</td>';
var cl='temp-at-set',tip='At setpoint';
if(tn>sn){cl='temp-above';tip='Above setpoint ('+sn+'°C)';}
else if(tn<sn){cl='temp-below';tip='Below setpoint ('+sn+'°C)';}
return '<td class=mono><span class="'+cl+'" title="'+esc(tip)+'">'+esc(ts)+'</span></td>';
}
function batTd(x){
var p=x.battery_pct, low=x.battery_low;
var lowH=low?'<span class=battery-low>LOW</span>':'';
if(p!=null&&p!==''&&!isNaN(parseFloat(p))){
var n=Math.round(parseFloat(p)*10)/10;
return '<td class=mono title="1060 device_battery">'+esc(String(n))+'%'+(!lowH?'':' ')+lowH+'</td>';
}
if(low)return '<td class=mono title="Battery low (no % reported)">'+lowH+'</td>';
return '<td class=sub>—</td>';
}
function winTd(x){
var w=x.window_state;
if(w==='open')return '<td class=mono title="12B0 window_state (open)"><span style="color:#38bdf8;font-weight:600">Open</span></td>';
if(w==='closed')return '<td class=mono title="12B0 window_state">Closed</td>';
return '<td class=sub title="No 12B0 yet">—</td>';
}
/** Parse API ISO like 2026-03-18T10:30:45.123456Z (6-digit frac breaks Date.parse in some browsers). */
function parseSeenUtcMs(ts){
if(!ts)return NaN;
var s=String(ts).trim();
var m=s.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(\.\d+)?/);
if(!m)return Date.parse(s);
var frac=0;
if(m[7]) frac=parseFloat(m[7]);
if(isNaN(frac)) frac=0;
var ms=Math.round(frac*1000);
return Date.UTC(+m[1],+m[2]-1,+m[3],+m[4],+m[5],+m[6],ms);
}
function lastSeenTd(iso){
if(!iso)return '<td class="mono sub">—</td>';
var t=parseSeenUtcMs(iso);
var now=Date.now();
var stale=isFinite(t)&&(now-t)>20*60*1000;
var tip='';
if(isFinite(t)){
var ageMin=Math.floor((now-t)/60000);
tip=' title="~'+ageMin+' min ago"';
}
if(stale)
return '<td class="mono"'+tip+' style="color:#f87171;font-weight:700">'+esc(iso)+'</td>';
// Fresh: show green; Unknown/unparseable stays grey via 'sub'.
if(isFinite(t))
return '<td class="mono"'+tip+' style="color:#34d399;font-weight:700">'+esc(iso)+'</td>';
return '<td class="mono sub"'+tip+'>'+esc(iso)+'</td>';
}
var _mtExpanded=new Set();
var _devExpanded=new Set();
var _zoneExpanded=new Set();

// Keep DOM nodes stable to prevent flicker on refresh.
var _devRows=new Map();      // device_id -> <tr>
var _devDescRows=new Map();  // device_id -> <tr class=mt-desc>
var _zoneRows=new Map();     // zone_idx -> <tr>
var _zoneDescRows=new Map(); // zone_idx -> <tr class=mt-desc>
var _mtRows=new Map();       // code -> <tr>
var _mtDescRows=new Map();   // code -> <tr class=mt-desc>

var _refreshTimer=null;
function scheduleRefresh(ms){
if(_refreshTimer!=null)return;
_refreshTimer=setTimeout(function(){_refreshTimer=null;L();},ms||150);
}
function loadMtSamples(trd,code){
var box=trd.querySelector('.mt-samples');if(!box)return;
var lim=25, off=parseInt(trd.getAttribute('data-off')||'0',10)||0;
box.innerHTML='<p class=sub style="margin:.5rem 0 0">Loading…</p>';
fetch('/api/messages/by_code?code='+encodeURIComponent(code)+'&limit='+lim+'&offset='+off).then(function(r){return r.json();}).then(function(j){
var rows=j.messages||[];
var total=j.total||0;
if(!rows.length){box.innerHTML='<p class=sub style="margin:.5rem 0 0">No matching rows in DB.</p>';return;}
var h='<p class=sub style="margin:.75rem 0 .35rem">Messages '+(off+1)+'–'+Math.min(off+lim,total)+' of '+total+'</p>';
h+='<p style="margin:.35rem 0 .5rem"><button class=btn type=button data-act=prev>Prev</button> <button class=btn type=button data-act=next>Next</button></p>';
h+='<table class="mt-subtbl"><thead><tr><th>Received</th><th>Code</th><th>Verb</th><th>Src</th><th>Dst</th><th>Zone</th><th>Payload (preview)</th></tr></thead><tbody>';
rows.forEach(function(x){
var p=esc(x.payload_preview||'—');
h+='<tr><td class=sub>'+esc(x.received_at||'—')+'</td><td class=mono>'+esc(x.code||'—')+'</td><td>'+esc(x.verb||'—')+'</td><td class=mono>'+esc(x.src_id||'—')+'</td><td class=mono>'+esc(x.dst_id||'—')+'</td><td class=mono>'+esc(x.zone||'—')+'</td><td class="mono sub">'+p+'</td></tr>';
});
h+='</tbody></table>';box.innerHTML=h;
box.querySelectorAll('button[data-act]').forEach(function(b){
  b.addEventListener('click',function(){
    var act=b.getAttribute('data-act');
    var noff=off;
    if(act==='prev')noff=Math.max(0,off-lim);
    if(act==='next')noff=Math.min(Math.max(0,total-lim),off+lim);
    trd.setAttribute('data-off',String(noff));
    loadMtSamples(trd,code);
  });
});
}).catch(function(){box.innerHTML='<p class=sub style="margin:.5rem 0 0">Could not load samples.</p>';});
}

function loadDevSamples(trd,deviceId){
var box=trd.querySelector('.dev-samples');if(!box)return;
var lim=25, off=parseInt(trd.getAttribute('data-off')||'0',10)||0;
box.innerHTML='<p class=sub style="margin:.5rem 0 0">Loading…</p>';
fetch('/api/messages/by_device?device_id='+encodeURIComponent(deviceId)+'&limit='+lim+'&offset='+off).then(r=>r.json()).then(j=>{
var rows=j.messages||[], total=j.total||0;
if(!rows.length){box.innerHTML='<p class=sub style="margin:.5rem 0 0">No rows yet.</p>';return;}
var h='<p class=sub style="margin:.75rem 0 .35rem">Messages '+(off+1)+'–'+Math.min(off+lim,total)+' of '+total+'</p>';
h+='<p style="margin:.35rem 0 .5rem"><button class=btn type=button data-act=prev>Prev</button> <button class=btn type=button data-act=next>Next</button></p>';
h+='<table class="mt-subtbl"><thead><tr><th>Received</th><th>Code</th><th>Verb</th><th>Src</th><th>Dst</th><th>Zone</th><th>Payload</th></tr></thead><tbody>';
rows.forEach(x=>{h+='<tr><td class=sub>'+esc(x.received_at||'—')+'</td><td class=mono>'+esc(x.code||'—')+'</td><td>'+esc(x.verb||'—')+'</td><td class=mono>'+esc(x.src_id||'—')+'</td><td class=mono>'+esc(x.dst_id||'—')+'</td><td class=mono>'+esc(x.zone||'—')+'</td><td class=\"mono sub\">'+esc(x.payload_preview||'—')+'</td></tr>';});
h+='</tbody></table>';box.innerHTML=h;
box.querySelectorAll('button[data-act]').forEach(function(b){
  b.addEventListener('click',function(){
    var act=b.getAttribute('data-act');
    var noff=off;
    if(act==='prev')noff=Math.max(0,off-lim);
    if(act==='next')noff=Math.min(Math.max(0,total-lim),off+lim);
    trd.setAttribute('data-off',String(noff));
    loadDevSamples(trd,deviceId);
  });
});
}).catch(()=>{box.innerHTML='<p class=sub style=\"margin:.5rem 0 0\">Could not load messages.</p>';});
}

function loadZoneSamples(trd,zone){
var box=trd.querySelector('.zone-samples');if(!box)return;
var lim=25, off=parseInt(trd.getAttribute('data-off')||'0',10)||0;
box.innerHTML='<p class=sub style="margin:.5rem 0 0">Loading…</p>';
fetch('/api/messages/by_zone?zone='+encodeURIComponent(zone)+'&limit='+lim+'&offset='+off).then(r=>r.json()).then(j=>{
var rows=j.messages||[], total=j.total||0;
if(!rows.length){box.innerHTML='<p class=sub style="margin:.5rem 0 0">No rows yet.</p>';return;}
var h='<p class=sub style="margin:.75rem 0 .35rem">Messages '+(off+1)+'–'+Math.min(off+lim,total)+' of '+total+'</p>';
h+='<p style="margin:.35rem 0 .5rem"><button class=btn type=button data-act=prev>Prev</button> <button class=btn type=button data-act=next>Next</button></p>';
h+='<table class="mt-subtbl"><thead><tr><th>Received</th><th>Code</th><th>Verb</th><th>Src</th><th>Dst</th><th>Zone</th><th>Payload</th></tr></thead><tbody>';
rows.forEach(x=>{h+='<tr><td class=sub>'+esc(x.received_at||'—')+'</td><td class=mono>'+esc(x.code||'—')+'</td><td>'+esc(x.verb||'—')+'</td><td class=mono>'+esc(x.src_id||'—')+'</td><td class=mono>'+esc(x.dst_id||'—')+'</td><td class=mono>'+esc(x.zone||'—')+'</td><td class=\"mono sub\">'+esc(x.payload_preview||'—')+'</td></tr>';});
h+='</tbody></table>';box.innerHTML=h;
box.querySelectorAll('button[data-act]').forEach(function(b){
  b.addEventListener('click',function(){
    var act=b.getAttribute('data-act');
    var noff=off;
    if(act==='prev')noff=Math.max(0,off-lim);
    if(act==='next')noff=Math.min(Math.max(0,total-lim),off+lim);
    trd.setAttribute('data-off',String(noff));
    loadZoneSamples(trd,zone);
  });
});
}).catch(()=>{box.innerHTML='<p class=sub style=\"margin:.5rem 0 0\">Could not load messages.</p>';});
}
function _setTrHtml(tr, html){ if(tr.__h!==html){ tr.__h=html; tr.innerHTML=html; } }
function _setText(el, t){ var s=String(t==null?'':t); if(el.textContent!==s) el.textContent=s; }

function renderDevices(d){
const tb=document.getElementById('t');
const seen=new Set();
(d.devices||[]).forEach(function(x){
const id=String(x.device_id||''); if(!id)return;
seen.add(id);
var tr=_devRows.get(id);
var trd=_devDescRows.get(id);
if(!tr){
tr=document.createElement('tr');tr.className='mt-row';tr.tabIndex=0;
trd=document.createElement('tr');trd.className='mt-desc';trd.style.display='none';trd.setAttribute('data-off','0');
trd.innerHTML='<td colspan=14><div class="mt-desc-p">Recent messages for <span class=mono>'+esc(id)+'</span></div><div class="dev-samples"></div></td>';
(function(k,row,desc){
function toggle(ev){
if(ev)ev.stopPropagation();
const o=desc.style.display!=='none';
if(o){_devExpanded.delete(k);}else{_devExpanded.add(k);desc.setAttribute('data-off','0');loadDevSamples(desc,k);}
desc.style.display=o?'none':'table-row';
row.classList.toggle('mt-open',!o);
}
row.addEventListener('click',toggle);
row.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle(ev);}});
})(id,tr,trd);
tb.appendChild(tr);tb.appendChild(trd);
_devRows.set(id,tr);_devDescRows.set(id,trd);
}
const dc=x.device_class?'<span class=mono>'+esc(x.device_class)+'</span>'+(x.device_class_description?'<span class=class-inline> · '+esc(x.device_class_description)+'</span>':''):'—';
const lsf=x.last_seen_from_iso||null;
const lst=x.last_seen_to_iso||null;
const html='<td class=mono>'+esc(id)+'</td><td class=classcell>'+dc+'</td><td>'+esc(x.name&&x.name!=='unknown'?x.name:'—')+'</td><td>'+esc(x.zone_name||'—')+'</td>'+tempTd(x)+'<td class=mono>'+esc(x.zone_temp_report_c??'—')+'</td><td>'+esc(x.setpoint_c??'—')+'</td><td>'+esc(x.heat_demand_pct!=null&&x.heat_demand_pct!==undefined?x.heat_demand_pct:'—')+'</td>'+winTd(x)+batTd(x)+'<td>'+(x.messages_from)+'</td><td>'+(x.messages_to)+'</td>'+lastSeenTd(lsf)+lastSeenTd(lst);
_setTrHtml(tr, html);
const open=_devExpanded.has(id);
trd.style.display=open?'table-row':'none';
tr.classList.toggle('mt-open',open);
});
Array.from(_devRows.keys()).forEach(function(id){
if(seen.has(id))return;
const tr=_devRows.get(id), trd=_devDescRows.get(id);
if(tr&&tr.parentNode)tr.parentNode.removeChild(tr);
if(trd&&trd.parentNode)trd.parentNode.removeChild(trd);
_devRows.delete(id);_devDescRows.delete(id);_devExpanded.delete(id);
});
_applySortToTbody(tb, true);
}

function renderZones(d){
const zt=document.getElementById('zt');
const zones=d.zones||[];
if(!zones.length){
zt.innerHTML='<tr><td colspan=11 class=sub>No zones in database yet</td></tr>';
_zoneRows.clear();_zoneDescRows.clear();_zoneExpanded.clear();
return;
}
const seen=new Set();
zones.forEach(function(z){
const id=String(z.zone_idx||''); if(!id)return;
seen.add(id);
var tr=_zoneRows.get(id);
var trd=_zoneDescRows.get(id);
if(!tr){
tr=document.createElement('tr');tr.className='mt-row';tr.tabIndex=0;
trd=document.createElement('tr');trd.className='mt-desc';trd.style.display='none';trd.setAttribute('data-off','0');
trd.innerHTML='<td colspan=11><div class="mt-desc-p">Recent messages for zone <span class=mono>'+esc(id)+'</span></div><div class="zone-samples"></div></td>';
(function(k,row,desc){
function toggle(ev){
if(ev)ev.stopPropagation();
const o=desc.style.display!=='none';
if(o){_zoneExpanded.delete(k);}else{_zoneExpanded.add(k);desc.setAttribute('data-off','0');loadZoneSamples(desc,k);}
desc.style.display=o?'none':'table-row';
row.classList.toggle('mt-open',!o);
}
row.addEventListener('click',toggle);
row.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle(ev);}});
})(id,tr,trd);
zt.appendChild(tr);zt.appendChild(trd);
_zoneRows.set(id,tr);_zoneDescRows.set(id,trd);
}
const fs=(z.following_schedule===true)?'Yes':(z.following_schedule===false)?'No':'—';
const sp=z.setpoint_c!=null&&z.setpoint_c!==undefined?String(z.setpoint_c):'—';
const tt=z.temperature_c!=null&&z.temperature_c!==undefined?String(z.temperature_c):'—';
const hd=z.heat_demand_pct!=null&&z.heat_demand_pct!==undefined?String(z.heat_demand_pct):'—';
const rq=z.rq_message_count!=null&&z.rq_message_count!==undefined?String(z.rq_message_count):'—';
const rp=z.rp_message_count!=null&&z.rp_message_count!==undefined?String(z.rp_message_count):'—';
const oth=z.other_message_count!=null&&z.other_message_count!==undefined?String(z.other_message_count):'—';
const total=z.message_count!=null&&z.message_count!==undefined?String(z.message_count):'—';
_setTrHtml(tr,'<td class=mono>'+esc(id)+'</td><td>'+esc(z.name)+'</td><td class=sub>'+esc(fs)+'</td><td class=mono>'+esc(sp)+'</td><td class=mono>'+esc(tt)+'</td><td class=mono>'+esc(hd)+'</td><td class=mono>'+esc(rq)+'</td><td class=mono>'+esc(rp)+'</td><td class=mono>'+esc(oth)+'</td><td class=mono>'+esc(total)+'</td><td class=sub>'+esc(z.updated_at||'—')+'</td>');
const open=_zoneExpanded.has(id);
trd.style.display=open?'table-row':'none';
tr.classList.toggle('mt-open',open);
});
Array.from(_zoneRows.keys()).forEach(function(id){
if(seen.has(id))return;
const tr=_zoneRows.get(id), trd=_zoneDescRows.get(id);
if(tr&&tr.parentNode)tr.parentNode.removeChild(tr);
if(trd&&trd.parentNode)trd.parentNode.removeChild(trd);
_zoneRows.delete(id);_zoneDescRows.delete(id);_zoneExpanded.delete(id);
});
_applySortToTbody(zt, true);
}

function renderMsgCounts(d){
const mt=document.getElementById('mt');
const rows=d.message_code_counts||[];
if(!rows.length){
mt.innerHTML='<tr><td colspan=4 class=sub>No message statistics yet</td></tr>';
_mtRows.clear();_mtDescRows.clear();_mtExpanded.clear();
return;
}
const seen=new Set();
rows.forEach(function(m){
const code=String(m.code||''); if(!code)return;
const key=code.toUpperCase();
seen.add(key);
var tr=_mtRows.get(key);
var trd=_mtDescRows.get(key);
if(!tr){
tr=document.createElement('tr');tr.className='mt-row';tr.tabIndex=0;
trd=document.createElement('tr');trd.className='mt-desc';trd.style.display='none';trd.setAttribute('data-off','0');
const desc=esc(m.type_description||'No description.');
trd.innerHTML='<td colspan=4><div class="mt-desc-p">'+desc+'</div><div class="mt-samples"></div></td>';
(function(k,row,descRow,rawCode){
function toggle(ev){
if(ev)ev.stopPropagation();
const o=descRow.style.display!=='none';
if(o){_mtExpanded.delete(k);}else{_mtExpanded.add(k);descRow.setAttribute('data-off','0');loadMtSamples(descRow,rawCode);}
descRow.style.display=o?'none':'table-row';
row.classList.toggle('mt-open',!o);
}
row.addEventListener('click',toggle);
row.addEventListener('keydown',function(ev){if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle(ev);}});
})(key,tr,trd,code);
mt.appendChild(tr);mt.appendChild(trd);
_mtRows.set(key,tr);_mtDescRows.set(key,trd);
}
_setTrHtml(tr,'<td class=mono>'+esc(code)+'</td><td>'+esc(m.code_name||'—')+'</td><td>'+m.message_count+'</td><td class=sub>'+esc(m.last_message_at||'—')+'</td>');
const open=_mtExpanded.has(key);
trd.style.display=open?'table-row':'none';
tr.classList.toggle('mt-open',open);
});
Array.from(_mtRows.keys()).forEach(function(k){
if(seen.has(k))return;
const tr=_mtRows.get(k), trd=_mtDescRows.get(k);
if(tr&&tr.parentNode)tr.parentNode.removeChild(tr);
if(trd&&trd.parentNode)trd.parentNode.removeChild(trd);
_mtRows.delete(k);_mtDescRows.delete(k);_mtExpanded.delete(k);
});
_applySortToTbody(mt, true);
}

function renderBoiler(d){
const boil=document.getElementById('boil');
const bs=d.boiler_status||[];
var bH='';
function yn(v,on){if(v===true)return '<span class=boiler-on>'+on+'</span>';if(v===false)return '<span class=boiler-off>Off</span>';return '—';}
if(!bs.length){bH='<tr><td colspan=12 class=sub>No boiler rows yet — need <span class=mono>10:</span> (OpenTherm) and/or <span class=mono>13:</span> (BDR relay) traffic.</td></tr>';}
else{bs.forEach(function(b){
var rk=b.boiler_kind==='relay';
var kind=rk?'<span title="BDR relay">Relay</span>':'<span title="OpenTherm bridge">OT</span>';
var fl=rk?'<td class=sub title="Not on RF for relay">—</td>':'<td>'+yn(b.flame_on,'On')+'</td>';
var dhw=rk?'<td class=sub>—</td>':'<td>'+yn(b.dhw_active,'Yes')+'</td>';
var chen=rk?'<td class=sub>—</td>':'<td>'+yn(b.ch_enabled,'Yes')+'</td>';
var flow=rk?'<td class=sub>—</td>':'<td class=mono>'+esc(b.flow_temp_c!=null?b.flow_temp_c:'—')+'</td>';
var ret=rk?'<td class=sub>—</td>':'<td class=mono>'+esc(b.return_temp_c!=null?b.return_temp_c:'—')+'</td>';
var tgt=rk?'<td class=sub>—</td>':'<td class=mono>'+esc(b.target_setpoint_c!=null?b.target_setpoint_c:'—')+'</td>';
var cmax=rk?'<td class=sub>—</td>':'<td class=mono>'+esc(b.ch_setpoint_c!=null?b.ch_setpoint_c:'—')+'</td>';
bH+='<tr><td>'+kind+'</td><td class=mono>'+esc(b.otb_device_id)+'</td>'+fl+'<td>'+yn(b.ch_active,'Yes')+'</td>'+dhw+chen+'<td class=mono title="'+(rk?'TPI / relay duty':'Modulation')+'">'+esc(b.modulation_pct!=null?b.modulation_pct:'—')+'</td>'+flow+ret+tgt+cmax+'<td class=sub>'+esc(b.updated_at||'—')+'</td></tr>';
});}
boil.innerHTML=bH;
_applySortToTbody(boil, false);
}

function renderDhw(d){
const dhw=document.getElementById('dhw');
const ds=d.dhw_status||[];
var h='';
function yn(v,on){if(v===true)return '<span class=boiler-on>'+on+'</span>';if(v===false)return '<span class=boiler-off>Off</span>';return '—';}
if(!ds.length){dhw.innerHTML='<tr><td colspan=9 class=sub>No DHW rows yet (need dhw_temp/dhw_params/dhw_mode).</td></tr>';return;}
ds.forEach(function(x){
h+='<tr>'
+'<td class=mono>'+esc(x.dhw_idx||'—')+'</td>'
+'<td>'+yn(x.active,'On')+'</td>'
+'<td>'+esc(x.mode||'—')+'</td>'
+'<td class=mono>'+esc(x.temperature_c!=null?x.temperature_c:'—')+'</td>'
+'<td class=mono>'+esc(x.setpoint_c!=null?x.setpoint_c:'—')+'</td>'
+'<td class=mono>'+esc(x.differential_c!=null?x.differential_c:'—')+'</td>'
+'<td class=mono>'+esc(x.overrun!=null?x.overrun:'—')+'</td>'
+'<td class=mono>'+esc(x.controller_id||'—')+'</td>'
+'<td class=sub>'+esc(x.updated_at||'—')+'</td>'
+'</tr>';
});
dhw.innerHTML=h;
_applySortToTbody(dhw, false);
}

function renderMetaAndStatic(d){
_setText(document.getElementById('p'), d.python_process_uptime_human?(' · Python up '+d.python_process_uptime_human):'');
_setText(document.getElementById('e'), d.uptime_human?(' · Exporter up '+d.uptime_human):'');
function dash(v){return(v==null||v==='')?'—':String(v);}
var vh='';
vh+='<tr><td>ramses_tx (library)</td><td class=mono>'+esc(d.ramses_tx_version||'—')+'</td></tr>';
vh+='<tr><td>ramses_rf path</td><td class="mono sub" style="word-break:break-all">'+esc(d.ramses_rf_path||'—')+'</td></tr>';
if(d.usb_serial_port){vh+='<tr><td>Serial port</td><td class=mono>'+esc(d.usb_serial_port)+'</td></tr>';
vh+='<tr><td>USB manufacturer</td><td>'+esc(dash(d.usb_manufacturer))+'</td></tr>';
vh+='<tr><td>USB product</td><td>'+esc(dash(d.usb_product))+'</td></tr>';
vh+='<tr><td>VID:PID</td><td class=mono>'+esc((d.usb_vid&&d.usb_pid)?(d.usb_vid+':'+d.usb_pid):'—')+'</td></tr>';
if(d.usb_serial_number)vh+='<tr><td>USB serial #</td><td class=mono>'+esc(d.usb_serial_number)+'</td></tr>';
vh+='<tr><td>Stick firmware (!V)</td><td class=mono>'+esc(d.stick_firmware_line||'— (not probed or N/A)')+'</td></tr>';
}else{vh+='<tr><td>USB gateway</td><td class=sub>— (running without device or no port)</td></tr>';}
document.getElementById('ver').innerHTML=vh;
_applySortToTbody(document.getElementById('ver'), false);
}

function renderPuzzleAndLogs(d){
const pl=d.puzzle_log||{};
const pg=document.getElementById('pg');
const gws=pl.gateways||[];
var pgH='';
if(!gws.length){pgH='<tr><td colspan=7 class=sub>No puzzle version rows yet — need 7FFF packets with engine+parser (gateway startup / signature).</td></tr>';}
else{gws.forEach(function(g){
var ch=g.version_changes_observed||0;
var chHtml=ch>0?'<span style="color:#fbbf24;font-weight:600">'+ch+'</span>':'0';
pgH+='<tr><td class=mono>'+esc(g.src_id)+'</td><td class=mono>'+esc(g.engine)+'</td><td class=mono>'+esc(g.parser)+'</td><td>'+chHtml+'</td><td>'+(g.stored_events||0)+'</td><td class=sub>'+esc(g.first_seen||'—')+'</td><td class=sub>'+esc(g.last_change_at||'—')+'</td></tr>';
});}
pg.innerHTML=pgH;
_applySortToTbody(pg, false);
const pe=document.getElementById('pe');
const pEv=pl.events||[];
var peH='';
if(!pEv.length){peH='<tr><td colspan=5 class=sub>No version-change events recorded yet.</td></tr>';}
else{pEv.forEach(function(e){
peH+='<tr><td class=sub>'+esc(e.received_at||'—')+'</td><td class=mono>'+esc(e.src_id)+'</td><td class=mono>'+esc(e.engine)+'</td><td class=mono>'+esc(e.parser)+'</td><td>'+esc(e.change_note||'—')+'</td></tr>';
});}
pe.innerHTML=peH;
_applySortToTbody(pe, false);
const ft=document.getElementById('ft');ft.innerHTML='';
if((d.fault_log||[]).length===0){ft.innerHTML='<tr><td colspan=8 class=sub>No fault log entries yet (need RP/I system_fault with parsed log)</td></tr>';}
else{(d.fault_log||[]).forEach(f=>{const tr=document.createElement('tr');
const ex=Array.isArray(f.detail)&&f.detail.length?f.detail.map(x=>esc(String(x))).join(' · '):'—';
tr.innerHTML='<td class=sub>'+esc(f.event_timestamp||'—')+'</td><td>'+esc(f.fault_state||'—')+'</td><td>'+esc(f.fault_type||'—')+'</td><td class=mono>'+esc(f.device_id||'—')+'</td><td class=mono>'+esc(f.log_idx||'—')+'</td><td>'+esc(f.verb||'—')+'</td><td class=sub>'+esc(f.received_at||'—')+'</td><td class=sub style=\"max-width:12rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis\" title=\"'+ex+'\">'+ex+'</td>';
ft.appendChild(tr);});}
_applySortToTbody(ft, false);
const wt=document.getElementById('wt');wt.innerHTML='';
if(!(d.recent_warnings||[]).length){wt.innerHTML='<tr><td colspan=4 class=sub>No warnings this session</td></tr>';}
else{(d.recent_warnings||[]).forEach(w=>{const tr=document.createElement('tr');
const lv=esc(w.level||'');
tr.innerHTML='<td class=sub>'+esc(w.time_utc||'—')+'</td><td class=\"'+(w.level==='ERROR'||w.level==='CRITICAL'?'lvl-ERROR':'lvl-WARNING')+'\">'+lv+'</td><td class=mono style=\"font-size:.75rem\">'+esc(w.logger||'—')+'</td><td>'+esc(w.message||'—')+'</td>';
wt.appendChild(tr);});}
_applySortToTbody(wt, false);
}

async function L(){try{const r=await fetch('/api/devices');const d=await r.json();
renderMetaAndStatic(d);
renderDevices(d);
renderBoiler(d);
renderDhw(d);
renderZones(d);
renderMsgCounts(d);
renderPuzzleAndLogs(d);
}catch(e){}}
initSort();
L();
var es=new EventSource('/api/events');
es.onmessage=function(){scheduleRefresh(120);};
es.onopen=function(){scheduleRefresh(120);};
es.onerror=function(){};
setInterval(function(){scheduleRefresh(250);},12000);
</script></body></html>"""


def start_http_server(
    creds: Dict[str, Any],
    port: int,
    load_dashboard_fn: Callable[[], Dict[str, Any]],
    host: str = "0.0.0.0",
    live_events: Optional[LiveNotifier] = None,
    runtime_versions: Optional[Dict[str, Any]] = None,
    stop_event: Optional[threading.Event] = None,
) -> ThreadingHTTPServer:
    global _app_started_at, _py_process_start
    if _app_started_at == 0:
        _app_started_at = time.time()
    if _py_process_start == 0:
        _py_process_start = time.time()

    rv = dict(runtime_versions or {})

    def meta() -> Dict[str, Any]:
        now = time.time()
        m: Dict[str, Any] = {
            "generated_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
            "uptime_seconds": round(now - _app_started_at, 1),
            "uptime_human": _format_duration(now - _app_started_at),
            "python_process_uptime_seconds": round(now - _py_process_start, 1),
            "python_process_uptime_human": _format_duration(now - _py_process_start),
            "python_process_uptime_os_accurate": False,
        }
        m.update(rv)
        return m

    def refresh() -> None:
        refresh_metrics_from_db(creds)

    handler = make_handler(
        creds,
        load_dashboard_fn,
        refresh,
        meta,
        live_events,
        stop_event=stop_event,
    )
    bind = host.strip() or "0.0.0.0"
    try:
        httpd = ThreadingHTTPServer((bind, port), handler)
    except OSError as e:
        # If another process is already bound to the port, fail fast.
        # This is commonly caused by stale dev runs.
        if getattr(e, "errno", None) == errno.EADDRINUSE:
            logger.error(
                "Address already in use on %s:%s (%s); exiting.",
                bind,
                port,
                e,
            )
            sys.exit(1)
        raise
    return httpd
