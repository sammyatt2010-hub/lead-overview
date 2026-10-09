"""
Lead Overview · SY Communications
A read-only dashboard of every email and new Zoho lead created by the three sales apps:
Prospect Engine, Lead Revival, Customer Growth and MY PA.

It reads the same JSON logs those apps already save to GitHub, so it never changes Zoho or the logs.
Secrets: APP_PASSWORD, GITHUB_TOKEN, GITHUB_REPO (see the setup notes at the bottom of this file).
Optional: ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET / ZOHO_REFRESH_TOKEN for opens, clicks and bounces (read-only).
"""
import base64
import hmac
import html as html_lib
import inspect
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import altair as alt
import pandas as pd
import requests
import streamlit as st

APP_NAME = "Lead Overview"
APP_TAGLINE = "SY Communications · sales activity"
UK = ZoneInfo("Europe/London")

# One colour per app, used everywhere (tiles, chart, table). Validated for colour-blind separation on the dark surface.
APPS = {
    "Prospect Engine": "#3987e5",
    "Lead Revival": "#d95926",
    "Customer Growth": "#199e70",
    "MY PA": "#c98500",
}
CAMPAIGN_NAMES = {
    "m01": "Introduce the complete portfolio", "m02": "AI call answering", "m03": "Call Scope analytics and QC",
    "m04": "CRM integration", "m05": "FTTP, SoGEA and Starlink", "m06": "Hosted PBX and modern handsets",
    "m07": "Business Wi-Fi and networks", "m08": "Mobile apps and flexible working",
    "m09": "Microsoft 365, IT support and cyber security", "m10": "Live wallboards and dashboards",
    "m11": "CCTV and site infrastructure", "m12": "Combined services and annual review",
}

st.set_page_config(page_title=APP_NAME, page_icon="📊", layout="wide")


# ==========================================
# Look & feel (same design as Prospect Engine)
# ==========================================
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
:root{--bg:#0A0E1A;--surface:#111827;--surface-2:#161F33;--surface-3:#1C2740;--border:rgba(148,163,184,.14);--border-strong:rgba(148,163,184,.26);--text:#E7EAF3;--muted:#8C98B0;--faint:#5E6A82;--accent:#7C83FF;--accent-2:#38D6F5;--accent-soft:rgba(124,131,255,.14);--good:#34D399;--warn:#FBBF24;--bad:#F87171;--radius:14px;--grad:linear-gradient(135deg,#7C83FF 0%,#38D6F5 100%);}
html,body,[class*="css"],.stApp,button,input,textarea,select{font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif!important}
.stApp{background:radial-gradient(1200px 500px at 85% -10%,rgba(56,214,245,.07),transparent 60%),radial-gradient(900px 500px at 10% -20%,rgba(124,131,255,.10),transparent 60%),var(--bg)}
[data-testid="stHeader"]{background:transparent}[data-testid="stDecoration"]{display:none}footer{visibility:hidden}
.block-container{padding-top:1.6rem!important;padding-bottom:3rem!important;max-width:1500px}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#0D1322 0%,#0A0E1A 100%);border-right:1px solid var(--border)}
[data-testid="stWidgetLabel"] p{font-size:.76rem!important;font-weight:600!important;color:var(--muted)!important;text-transform:uppercase;letter-spacing:.06em}
[data-testid="stCaptionContainer"]{color:var(--muted)!important}
.st-key-card-chart,.st-key-card-eng,.st-key-card-table,.st-key-card-week,.st-key-card-login,.st-key-card-empty{background:linear-gradient(180deg,rgba(22,31,51,.85) 0%,rgba(17,24,39,.85) 100%);border:1px solid var(--border)!important;border-radius:var(--radius);padding:22px 22px 18px;box-shadow:0 1px 0 rgba(255,255,255,.03) inset,0 20px 40px -24px rgba(0,0,0,.6);margin-bottom:18px}
[data-baseweb="input"],[data-baseweb="select"]>div,[data-baseweb="textarea"]{background:var(--surface)!important;border:1px solid var(--border-strong)!important;border-radius:10px!important}
[data-baseweb="input"]:focus-within,[data-baseweb="select"]>div:focus-within{border-color:var(--accent)!important;box-shadow:0 0 0 3px var(--accent-soft)!important}
[data-baseweb="input"]>div,[data-baseweb="base-input"]{background:transparent!important}
.stButton button,.stDownloadButton button,.stFormSubmitButton button{border-radius:10px!important;font-weight:600!important;border:1px solid var(--border-strong)!important;background:var(--surface-2)!important;color:var(--text)!important;transition:all .15s ease}
.stButton button:hover,.stDownloadButton button:hover{border-color:var(--accent)!important;transform:translateY(-1px)}
.stButton button[kind="primary"],.stFormSubmitButton button,[data-testid="stBaseButton-primary"]{background:var(--grad)!important;border:none!important;color:#0A0E1A!important;box-shadow:0 8px 24px -10px rgba(124,131,255,.8)}
.stButton button[kind="primary"] p,[data-testid="stBaseButton-primary"] p,.stFormSubmitButton button p{color:#0A0E1A!important;font-weight:700!important}
[data-testid="stDataFrame"]{border:1px solid var(--border);border-radius:12px;overflow:hidden}
[data-testid="stExpander"] details{background:var(--surface);border:1px solid var(--border)!important;border-radius:12px!important}
[data-testid="stAlert"]{border-radius:12px!important}
.pe-hero{display:flex;align-items:center;justify-content:space-between;gap:24px;flex-wrap:wrap;padding:6px 2px 22px;margin-bottom:18px;border-bottom:1px solid var(--border)}
.pe-eyebrow{display:inline-flex;align-items:center;gap:8px;font-size:.72rem;font-weight:700;letter-spacing:.14em;text-transform:uppercase;color:var(--accent-2);margin-bottom:8px}
.pe-eyebrow .dot{width:7px;height:7px;border-radius:50%;background:var(--good);box-shadow:0 0 0 4px rgba(52,211,153,.15)}
.pe-title{font-size:2.05rem;font-weight:800;letter-spacing:-.035em;line-height:1.1;color:var(--text)}
.pe-title span{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.pe-sub{color:var(--muted);font-size:.95rem;margin-top:8px;max-width:620px}
.pe-stepper{display:flex;align-items:center;gap:6px;background:var(--surface);border:1px solid var(--border);border-radius:999px;padding:6px}
.pe-step{display:flex;align-items:center;gap:8px;padding:7px 14px 7px 7px;border-radius:999px;font-size:.82rem;font-weight:600;color:var(--muted);white-space:nowrap}
.pe-step .num{min-width:24px;height:24px;padding:0 6px;border-radius:999px;display:grid;place-items:center;font-size:.72rem;font-weight:700;border:1px solid var(--border-strong);color:var(--text)}
.pe-step.active{background:var(--surface-3);color:var(--text)}.pe-step.active .num{background:var(--grad);border:none;color:#0A0E1A}
.pe-step-sep{width:14px;height:1px;background:var(--border-strong)}
.pe-section{display:flex;align-items:center;gap:12px;margin-bottom:16px}
.pe-section .badge{width:34px;height:34px;border-radius:10px;display:grid;place-items:center;background:var(--accent-soft);color:var(--accent);font-weight:800;font-size:.85rem;border:1px solid rgba(124,131,255,.3)}
.pe-section .t{font-size:1.08rem;font-weight:700;color:var(--text)}.pe-section .s{font-size:.82rem;color:var(--muted);margin-top:2px}
.pe-logo{width:40px;height:40px;border-radius:12px;background:var(--grad);display:grid;place-items:center;color:#0A0E1A;box-shadow:0 10px 24px -10px rgba(124,131,255,.9)}
.pe-login-head{text-align:center;margin:8vh 0 22px}.pe-login-head .pe-logo{width:54px;height:54px;margin:0 auto 16px;border-radius:16px}
.pe-login-head .t{font-size:1.6rem;font-weight:800;letter-spacing:-.03em;color:var(--text)}.pe-login-head .s{color:var(--muted);font-size:.92rem;margin-top:6px}
.pe-brand{display:flex;align-items:center;gap:12px;padding:4px 0 18px;border-bottom:1px solid var(--border);margin-bottom:16px}
.pe-brand .n{font-weight:800;color:var(--text);letter-spacing:-.02em}.pe-brand .s{font-size:.74rem;color:var(--muted)}
.pe-side-h{font-size:.7rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin:18px 0 8px}
.pe-status{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:.84rem;color:var(--text);padding:6px 0}
.pe-status .st{font-size:.74rem;font-weight:600;display:inline-flex;align-items:center;gap:6px;white-space:nowrap;flex-shrink:0}
.pe-status .st::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor}
.pe-status .ok{color:var(--good)}.pe-status .idle{color:var(--faint)}.pe-status .off{color:var(--bad)}
/* KPI tiles: coloured top edge = the app */
.lo-totals{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-bottom:14px}
@media (max-width:900px){.lo-totals{grid-template-columns:1fr}}
.lo-total{background:linear-gradient(135deg,rgba(124,131,255,.16) 0%,rgba(56,214,245,.08) 100%);border:1px solid rgba(124,131,255,.32);border-radius:16px;padding:18px 22px;display:flex;align-items:center;gap:26px;flex-wrap:wrap}
.lo-total .t{font-size:.74rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:#B9BDFF;min-width:150px}
.lo-total .t b{display:block;font-size:1.05rem;letter-spacing:-.01em;text-transform:none;color:var(--text);margin-top:4px}
.lo-total .n{display:flex;flex-direction:column}.lo-total .n .v{font-size:2.3rem;font-weight:800;letter-spacing:-.03em;color:var(--text);line-height:1}
.lo-total .n .k{font-size:.7rem;color:var(--muted);margin-top:6px;font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.lo-total .n.main .v{font-size:2.8rem;background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.lo-week{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:14px}
@media (max-width:900px){.lo-week{grid-template-columns:repeat(2,minmax(0,1fr))}}
.lo-week div.c{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:12px 14px}
.lo-week .v{font-size:1.5rem;font-weight:800;color:var(--text)}.lo-week .l{font-size:.78rem;color:var(--muted);margin-top:2px}
.lo-week .d{font-size:.74rem;margin-top:6px;font-weight:600}.lo-week .d.up{color:var(--good)}.lo-week .d.flat{color:var(--muted)}
.lo-kpis{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:14px;margin-bottom:18px}
@media (max-width:1400px){.lo-kpis{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media (max-width:1100px){.lo-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:640px){.lo-kpis{grid-template-columns:1fr}}
.lo-kpi{background:linear-gradient(180deg,rgba(22,31,51,.9) 0%,rgba(17,24,39,.9) 100%);border:1px solid var(--border);border-top:3px solid var(--c);border-radius:14px;padding:16px 18px 14px}
.lo-kpi .app{display:flex;align-items:center;gap:8px;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
.lo-kpi .app i{width:9px;height:9px;border-radius:3px;background:var(--c);display:inline-block}
.lo-kpi .l{font-size:.95rem;font-weight:700;color:var(--text);margin-top:8px}
.lo-kpi .row{display:flex;align-items:flex-end;gap:22px;margin-top:10px}
.lo-kpi .v{font-size:2rem;font-weight:800;letter-spacing:-.03em;color:var(--text);line-height:1}
.lo-kpi .k{font-size:.72rem;color:var(--muted);margin-top:6px;font-weight:600;text-transform:uppercase;letter-spacing:.06em}
.lo-kpi .v.big{font-size:2.3rem}
.lo-kpi .foot{font-size:.78rem;color:var(--muted);margin-top:12px;padding-top:10px;border-top:1px solid var(--border)}
.pe-empty{text-align:center;padding:30px 10px}.pe-empty .t{font-weight:700;color:var(--text);font-size:1.1rem;margin-top:14px}
.pe-empty .s{color:var(--muted);margin-top:6px}.pe-empty ol{text-align:left;display:inline-block;color:var(--muted);margin-top:12px}
</style>
"""


def esc(v: Any) -> str:
    return html_lib.escape(str(v if v is not None else ""), quote=True)


def render_html(markup: str, target=None) -> None:
    (target or st).markdown("".join(line.strip() for line in markup.splitlines()), unsafe_allow_html=True)


def section_header(num: str, title: str, subtitle: str = "") -> None:
    render_html(f'<div class="pe-section"><div class="badge">{num}</div><div><div class="t">{esc(title)}</div>'
                + (f'<div class="s">{esc(subtitle)}</div>' if subtitle else "") + "</div></div>")


def _full_width() -> Dict[str, Any]:
    try:
        if "width" in inspect.signature(st.button).parameters:
            return {"width": "stretch"}
    except (TypeError, ValueError):
        pass
    return {"use_container_width": True}


FULL_WIDTH = _full_width()


def columns(spec, **kw):
    try:
        return st.columns(spec, vertical_alignment="bottom", **kw)
    except TypeError:
        return st.columns(spec, **kw)


ICON_CHART = ('<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" '
              'stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-4 3 3 5-6"/></svg>')

render_html(CSS)


def _secret(name: str, default: str = "") -> str:
    try:
        v = st.secrets.get(name, default)
    except Exception:
        v = default
    return str(v or default).strip()


# ==========================================
# Sign in (fails closed: no APP_PASSWORD, no entry)
# ==========================================
def check_password() -> bool:
    configured = _secret("APP_PASSWORD")
    if not configured:
        render_html(f'<div class="pe-login-head"><div class="pe-logo">{ICON_CHART}</div><div class="t">App locked</div>'
                    '<div class="s">APP_PASSWORD isn\'t set in Streamlit Secrets, so access is blocked.</div></div>')
        return False
    if st.session_state.get("password_ok"):
        return True

    def _check():
        st.session_state["password_ok"] = hmac.compare_digest(
            st.session_state.get("pw", "").encode("utf-8"), configured.encode("utf-8"))
        st.session_state["pw_tried"] = True
        st.session_state.pop("pw", None)

    _, mid, _ = st.columns([1, 1.4, 1])
    with mid:
        render_html(f'<div class="pe-login-head"><div class="pe-logo">{ICON_CHART}</div><div class="t">{APP_NAME}</div>'
                    f'<div class="s">{APP_TAGLINE} · Authorised users only</div></div>')
        with st.container(key="card-login"):
            with st.form("login", border=False):
                st.text_input("Access password", type="password", key="pw", placeholder="Enter your password")
                st.form_submit_button("Sign in", on_click=_check, type="primary", **FULL_WIDTH)
            if st.session_state.get("pw_tried") and not st.session_state.get("password_ok"):
                st.error("Incorrect password. Please try again.")
    return False


if not check_password():
    st.stop()


# ==========================================
# Reading the apps' logs from GitHub (read only)
# ==========================================
def source_list() -> List[Dict[str, str]]:
    """Where each app keeps its log. Same secret names as the apps, so overrides carry across."""
    default_repo, default_tok = _secret("GITHUB_REPO"), "GITHUB_TOKEN"
    pe = _secret("PE_GITHUB_REPO", default_repo)
    lr = _secret("LR_GITHUB_REPO", default_repo)
    cg = _secret("CG_GITHUB_REPO", default_repo)
    mp = _secret("MP_GITHUB_REPO", lr)  # MY PA saves alongside Lead Revival unless told otherwise
    # Each app can have its own token (e.g. paste each app's own GITHUB_TOKEN); falls back to GITHUB_TOKEN
    pe_t = "PE_GITHUB_TOKEN" if _secret("PE_GITHUB_TOKEN") else default_tok
    lr_t = "LR_GITHUB_TOKEN" if _secret("LR_GITHUB_TOKEN") else default_tok
    cg_t = "CG_GITHUB_TOKEN" if _secret("CG_GITHUB_TOKEN") else default_tok
    mp_t = "MP_GITHUB_TOKEN" if _secret("MP_GITHUB_TOKEN") else lr_t
    return [
        {"key": "pe_sent", "app": "Prospect Engine", "label": "Prospect emails", "repo": pe, "tok": pe_t,
         "path": _secret("GITHUB_LOG_PATH", "sent_log.json")},
        {"key": "pe_zoho", "app": "Prospect Engine", "label": "Prospects added to Zoho", "repo": pe, "tok": pe_t,
         "path": _secret("GITHUB_ZOHO_LEADS_PATH", "zoho_leads.json")},
        {"key": "lr_sent", "app": "Lead Revival", "label": "Lead Revival emails", "repo": lr, "tok": lr_t,
         "path": _secret("GITHUB_CRM_LOG_PATH", "crm_sent_log.json")},
        {"key": "cg_sent", "app": "Customer Growth", "label": "Upsell emails", "repo": cg, "tok": cg_t,
         "path": _secret("GITHUB_CG_LOG_PATH", "cg_sent_log.json")},
        {"key": "cg_camp", "app": "Customer Growth", "label": "Campaign emails", "repo": cg, "tok": cg_t,
         "path": _secret("GITHUB_CG_CAMPAIGN_PATH", "cg_campaign_log.json")},
        {"key": "mp_sent", "app": "MY PA", "label": "MY PA trial emails", "repo": mp, "tok": mp_t,
         "path": _secret("GITHUB_MYPA_LOG_PATH", "mypa_sent_log.json")},
    ]


def _clean_token(raw: str) -> str:
    """Forgives copy-paste slips: stray quotes, spaces, 'Bearer ' or 'token ' in front."""
    t = (raw or "").strip().strip('"').strip("'").strip()
    for prefix in ("Bearer ", "bearer ", "token ", "Token "):
        if t.startswith(prefix):
            t = t[len(prefix):].strip()
    return t


def fetch_log(repo: str, path: str, branch: str, token_secret: str = "GITHUB_TOKEN") -> Tuple[Dict[str, Any], str]:
    """Tries the app's own token first, then the main GITHUB_TOKEN if that one is rejected."""
    tried = []
    result: Tuple[Dict[str, Any], str] = ({}, "GITHUB_TOKEN / GITHUB_REPO not set")
    for name in dict.fromkeys([token_secret, "GITHUB_TOKEN"]):
        token = _clean_token(_secret(name))
        if not token or token in tried:
            continue
        tried.append(token)
        result = _fetch_log(repo, path, branch, token)
        if result[1] not in ("token rejected (401)", "no_access"):
            return result
    return result


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_log(repo: str, path: str, branch: str, token: str) -> Tuple[Dict[str, Any], str]:
    """(data, status). status: 'ok', 'missing' (file not created yet), 'no_access' (repo not visible to this token)
    or an error message. Cached 5 minutes."""
    if not (token and repo):
        return {}, "GITHUB_TOKEN / GITHUB_REPO not set"
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        resp = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
        if resp.status_code == 404:
            # Is it the file that's missing, or can this token not see the repo at all?
            repo_resp = requests.get(f"https://api.github.com/repos/{repo}", headers=headers, timeout=15)
            return {}, ("missing" if repo_resp.status_code == 200 else "no_access")
        if resp.status_code != 200:
            return {}, {401: "token rejected (401)", 403: "no permission (403)"}.get(resp.status_code, f"error {resp.status_code}")
        payload = resp.json()
        if payload.get("encoding") == "none" or (not payload.get("content") and payload.get("size", 0) > 0):
            raw = requests.get(url, headers={**headers, "Accept": "application/vnd.github.raw+json"},
                               params={"ref": branch}, timeout=30)
            text = raw.content.decode("utf-8-sig") if raw.status_code == 200 else ""
        else:
            text = base64.b64decode(payload.get("content") or b"").decode("utf-8-sig")
        text = text.strip()
        if not text or text in ("[]", "null"):
            return {}, "ok"
        data = json.loads(text)
        return (data if isinstance(data, dict) else {}), "ok"
    except (requests.exceptions.RequestException, ValueError) as exc:
        return {}, f"couldn't read ({exc.__class__.__name__})"


def zoho_url(module: str, record_id: Any) -> str:
    rid = str(record_id or "").strip()
    if not rid.isdigit():
        return ""
    base = _secret("ZOHO_CRM_URL", "https://crm.zoho.eu").rstrip("/")
    org = _secret("ZOHO_ORG").strip("/")
    return f"{base}/crm/{org}/tab/{module}/{rid}" if org else f"{base}/crm/tab/{module}/{rid}"


def parse_when(value: Any) -> Optional[datetime]:
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d.replace(tzinfo=UK) if d.tzinfo is None else d.astimezone(UK)


def is_email(rec: Dict[str, Any]) -> bool:
    """A real email (sent from Zoho or as a draft), not a call outcome or a 'handled, no email' tick."""
    status = str(rec.get("status") or "")
    if status.startswith("Called"):
        return False
    return bool(rec.get("to")) or rec.get("via") == "zoho"


def how_sent(rec: Dict[str, Any]) -> str:
    return "Sent from Zoho" if rec.get("via") == "zoho" else "Email draft / marked sent"


def build_events(logs: Dict[str, Dict[str, Any]]) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    zoho_leads = logs.get("pe_zoho", {})

    # Prospect Engine: new leads created in Zoho
    for cn, r in zoho_leads.items():
        if not isinstance(r, dict) or r.get("status") != "created":
            continue
        rows.append({"When": parse_when(r.get("at")), "App": "Prospect Engine", "Activity": "Added to Zoho", "Sector": "",
                     "Firm": r.get("firm") or cn, "Contact": "", "Email": "", "Detail": "New lead created",
                     "By": r.get("by") or "", "How": "Zoho", "Zoho": zoho_url("Leads", r.get("id"))})

    # Prospect Engine: pitches emailed
    for cn, r in logs.get("pe_sent", {}).items():
        if not isinstance(r, dict) or not is_email(r):
            continue
        z = zoho_leads.get(cn) or {}
        link = zoho_url("Accounts" if z.get("status") == "customer" else "Leads", z.get("id"))
        rows.append({"When": parse_when(r.get("sent_at")), "App": "Prospect Engine", "Activity": "Emailed", "Sector": r.get("vertical") or "",
                     "Firm": r.get("company_name") or cn, "Contact": r.get("contact") or "", "Email": r.get("to") or "",
                     "Detail": r.get("subject") or r.get("vertical") or "", "By": r.get("sent_by") or "",
                     "How": how_sent(r), "Zoho": link})

    # Lead Revival: keyed by the Zoho lead id
    for key, r in logs.get("lr_sent", {}).items():
        if not isinstance(r, dict) or not is_email(r):
            continue
        rows.append({"When": parse_when(r.get("sent_at")), "App": "Lead Revival", "Activity": "Emailed", "Sector": r.get("vertical") or "",
                     "Firm": r.get("company_name") or key, "Contact": r.get("contact") or "", "Email": r.get("to") or "",
                     "Detail": r.get("subject") or "", "By": r.get("sent_by") or "", "How": how_sent(r),
                     "Zoho": zoho_url("Leads", key)})

    # Customer Growth: upsell emails, keyed by the Zoho account id
    for key, r in logs.get("cg_sent", {}).items():
        if not isinstance(r, dict) or not (r.get("to") or r.get("via") == "zoho"):
            continue
        offers = ", ".join(r.get("offers") or [])
        rows.append({"When": parse_when(r.get("sent_at")), "App": "Customer Growth", "Activity": "Upsell email", "Sector": "",
                     "Firm": r.get("company_name") or key, "Contact": r.get("contact") or "", "Email": r.get("to") or "",
                     "Detail": (r.get("subject") or "") + (f" · {offers}" if offers else ""), "By": r.get("sent_by") or "",
                     "How": how_sent(r), "Zoho": zoho_url("Accounts", key)})

    # Customer Growth: monthly campaigns, keyed "m01|contact id"
    for key, r in logs.get("cg_camp", {}).items():
        if not isinstance(r, dict):
            continue
        cid = str(r.get("campaign") or key.split("|")[0])
        name = CAMPAIGN_NAMES.get(cid, cid)
        rows.append({"When": parse_when(r.get("sent_at")), "App": "Customer Growth", "Activity": "Campaign email", "Sector": "",
                     "Firm": r.get("account") or "", "Contact": r.get("contact") or "", "Email": r.get("to") or "",
                     "Detail": f"Campaign {cid[1:]}: {name}", "By": r.get("sent_by") or "", "How": "Sent from Zoho",
                     "Zoho": zoho_url("Accounts", r.get("account_id"))})

    # MY PA: free 1-week trial emails, keyed by the Zoho lead id
    for key, r in logs.get("mp_sent", {}).items():
        if not isinstance(r, dict) or not is_email(r):
            continue
        rows.append({"When": parse_when(r.get("sent_at")), "App": "MY PA", "Activity": "Trial offered", "Sector": r.get("vertical") or "",
                     "Firm": r.get("company_name") or key, "Contact": r.get("contact") or "", "Email": r.get("to") or "",
                     "Detail": r.get("subject") or "", "By": r.get("sent_by") or "", "How": how_sent(r),
                     "Zoho": zoho_url("Leads", key)})

    cols = ["When", "App", "Activity", "Sector", "Firm", "Contact", "Email", "Detail", "By", "How", "Zoho"]
    df = pd.DataFrame(rows, columns=cols)
    if not df.empty:
        df = df.sort_values("When", ascending=False, na_position="last").reset_index(drop=True)
    return df


# ==========================================
# Weekly summary (last 7 days): numbers, a one-page PDF and a copy-ready email text
# ==========================================
def week_stats(ev: pd.DataFrame, end: date, eng: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
    """Highlights for the 7 days ending `end` (inclusive), compared with the 7 days before. No firm names.
    `eng` (opens/clicks/bounces from Zoho) adds engagement rates when that week has been checked."""
    start, prev_start = end - timedelta(days=6), end - timedelta(days=13)
    d = ev[ev["When"].notna()].copy()
    d["Day"] = d["When"].apply(lambda x: x.date())
    cur = d[(d["Day"] >= start) & (d["Day"] <= end)]
    prev = d[(d["Day"] >= prev_start) & (d["Day"] < start)]
    em_cur, em_prev = cur[cur["Activity"].isin(EMAIL_ACTS)], prev[prev["Activity"].isin(EMAIL_ACTS)]
    em_all = ev[ev["Activity"].isin(EMAIL_ACTS)]
    per_app = []
    for app in APPS:
        per_app.append({
            "app": app,
            "week": int((em_cur["App"] == app).sum()),
            "prev": int((em_prev["App"] == app).sum()),
            "all": int((em_all["App"] == app).sum()),
        })
    days = [start + timedelta(days=i) for i in range(7)]
    daily = {day: {app: int(((em_cur["Day"] == day) & (em_cur["App"] == app)).sum()) for app in APPS} for day in days}
    busiest = max(days, key=lambda x: sum(daily[x].values())) if len(em_cur) else None
    sectors = (em_cur[em_cur["Sector"].astype(bool)]["Sector"].value_counts().head(4)
               if "Sector" in em_cur else pd.Series(dtype=int))
    camps = em_cur[em_cur["Activity"] == "Campaign email"]["Detail"].value_counts().head(3)
    return {
        "start": start, "end": end,
        "emails": len(em_cur), "emails_prev": len(em_prev), "emails_all": len(em_all),
        "leads": int((cur["Activity"] == "Added to Zoho").sum()),
        "leads_prev": int((prev["Activity"] == "Added to Zoho").sum()),
        "leads_all": int((ev["Activity"] == "Added to Zoho").sum()),
        "via_zoho": int((em_cur["How"] == "Sent from Zoho").sum()),
        "trials": int((em_cur["Activity"] == "Trial offered").sum()),
        "per_app": per_app, "daily": daily, "busiest": busiest,
        "busiest_n": sum(daily[busiest].values()) if busiest else 0,
        "sectors": [(k, int(v)) for k, v in sectors.items()],
        "campaigns": [(k, int(v)) for k, v in camps.items()],
        "active_days": sum(1 for x in days if sum(daily[x].values())),
        "eng": _week_eng(eng, start, end),
        "eng_detail": _week_eng_detail(eng, start, end),
    }


def _week_eng(eng: Optional[pd.DataFrame], start: date, end: date) -> Optional[Dict[str, Any]]:
    d = _week_eng_detail(eng, start, end)
    return d["cur"] if d else None


def _week_eng_detail(eng: Optional[pd.DataFrame], start: date, end: date) -> Optional[Dict[str, Any]]:
    """Engagement for one week (by send day): rates, last week's rates, by app and brand, opens/clicks per day."""
    if eng is None or eng.empty or start < datetime.now(UK).date() - timedelta(days=ENG_DAYS - 1):
        return None
    days = eng["Sent"].apply(lambda x: x.date())
    wk = eng[(days >= start) & (days <= end)]
    cur = eng_rates(wk)
    if not cur["sent"]:
        return None
    p0 = start - timedelta(days=7)
    prev = eng_rates(eng[(days >= p0) & (days < start)]) if p0 >= datetime.now(UK).date() - timedelta(days=ENG_DAYS - 1) else None
    per_app = [(a, eng_rates(wk[wk["App"] == a])) for a in APPS]
    per_brand = [(b, eng_rates(wk[wk["Brand"] == b])) for b in sorted(wk["Brand"].dropna().unique(), key=str.lower)]
    daily = {start + timedelta(days=i): {"Opened": 0, "Clicked": 0} for i in range(7)}
    for _, r in eng.iterrows():
        for col, key in (("First open", "Opened"), ("Last click", "Clicked")):
            t = r[col]
            if t is not None and not pd.isna(t) and t.date() in daily:
                daily[t.date()][key] += 1
    seen = eng["Last seen"].apply(lambda x: x.date() if x is not None and not pd.isna(x) else None)
    hot = eng[seen.apply(lambda x: bool(x) and start <= x <= end) & ~eng["Bounced"]]["Record"].nunique()
    return {"cur": cur, "prev": prev, "per_app": [(a, r) for a, r in per_app if r["sent"]],
            "per_brand": [(b, r) for b, r in per_brand if r["sent"]], "daily": daily, "hot": int(hot),
            "bounces": cur["bounced"]}


def eng_sentence(r: Dict[str, Any]) -> str:
    return (f"Of {r['sent']:,} emails sent from Zoho, {pct(r['open_rate'])} were opened and {pct(r['click_rate'])} clicked;"
            f" {r['bounced']:,} bounced ({pct(r['bounce_rate'])}).")


def _change(now_v: int, before: int) -> str:
    if before == 0:
        return "new this week" if now_v else "no change"
    pct = round((now_v - before) / before * 100)
    return f"{'+' if pct >= 0 else ''}{pct}% vs previous week"


def _rng(ws: Dict[str, Any]) -> str:
    return f"{ws['start'].strftime('%a %d %b')} - {ws['end'].strftime('%a %d %b %Y')}"


def weekly_text(ws: Dict[str, Any]) -> str:
    lines = [f"Sales automation: weekly summary ({_rng(ws)})", ""]
    lines.append(f"- {ws['emails']:,} emails sent across the suite ({_change(ws['emails'], ws['emails_prev'])})")
    lines.append(f"- {ws['leads']:,} new leads added to Zoho by Prospect Engine ({_change(ws['leads'], ws['leads_prev'])})")
    if ws["emails"]:
        lines.append(f"- {round(ws['via_zoho'] / ws['emails'] * 100)}% sent straight from Zoho, so every one is logged on the record")
    if ws["busiest"]:
        lines.append(f"- Busiest day: {ws['busiest'].strftime('%A')} with {ws['busiest_n']:,} emails")
    if ws.get("eng"):
        lines.append("- " + eng_sentence(ws["eng"]))
    lines += ["", "By app (this week / previous week / all time):"]
    for a in ws["per_app"]:
        lines.append(f"- {a['app']}: {a['week']:,} / {a['prev']:,} / {a['all']:,}")
    if ws["sectors"]:
        lines += ["", "Top sectors pitched: " + ", ".join(f"{k} ({v})" for k, v in ws["sectors"])]
    if ws["campaigns"]:
        lines.append("Customer campaigns sent: " + ", ".join(f"{k} ({v})" for k, v in ws["campaigns"]))
    lines += ["", f"All time: {ws['emails_all']:,} emails sent and {ws['leads_all']:,} new leads added to Zoho."]
    return "\n".join(lines)


def _pdf_txt(t: str) -> str:
    rep = {"–": "-", "—": "-", "‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
           "·": "-", "→": "->"}
    for k, v in rep.items():
        t = t.replace(k, v)
    return t.encode("latin-1", "replace").decode("latin-1")


def _rgb(hex_: str) -> Tuple[int, int, int]:
    h = hex_.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


# Inter (400, 600, 800), cut down to the characters the PDF uses, so the summary matches the page's typeface
_INTER_B64 = {
    400: (
        "AAEAAAAPAIAAAwBwR0RFRgIMAhUAADDwAAAAQEdQT1OpNICgAAAxMAAAIqhHU1VCN/w2UwAAU9gAAAC2T1MvMnEZFSUAAAF4AAAAYFNUQVRWpE"
        "HxAABUkAAAAF5jbWFwkjST7AAABCgAAAEaZ2FzcAAAABAAADDoAAAACGdseWa62tHyAAAGcAAAKDxoZWFkMGVA3wAAAPwAAAA2aGhlYQ+pDLsA"
        "AAE0AAAAJGhtdHiJPFBoAAAB2AAAAlBsb2NhSqE/eAAABUQAAAEqbWF4cACgAJwAAAFYAAAAIG5hbWU0qFRDAAAurAAAAhpwb3N0/qcAjAAAMM"
        "gAAAAgAAEAAAAEAEKVKrbaXw889QADCAAAAAAA4naHkAAAAADm7m5D/+b+IAgAB7IAAAADAAIAAAAAAAAAAQAAB8D+EgAACAD/5v4VCAAIAAAA"
        "AAAAAAAAAAAAAAAAAJQAAQAAAJQAWgAFAEAAAwABAAAAAAAAAAAAAAAAAAMAAQAEBSoBkAAFAAAFMwTNAAAAmgUzBM0AAALNAIwCnwAAAgAFAw"
        "AAAAIABIAAAAMAAAAiAAAAAAAAAABSU01TAMAAICGTB8D+EgAACN0ClAAAAAEAAAAABF4F0gAAACAADAVAAUgFhQA0BTwAtAXYAHoFxgC0BM8A"
        "tAS5ALQF+AB6BfIAtAImALQEkQBkBWAAtASGALQHOgC0BgcAtAYeAHoFHAC0Bh4AegUmALQFIgB0BSoAYgX0ALQFhQA0B+IANAV1ADkFbgA0BQ"
        "gAegR+AFoE5gCeBJIAaATmAGgEqgBoAvYAFAToAGgEuwCeAfAAfAHwAJ4B8P/mAfD/5gRkAJ4B8ACeBwIAngS6AJ4EzABoBOYAngTmAGgDAwCe"
        "BDkAbAKeABQEuwCeBH8ANgaMAEYEXgBBBH8ANgRrAH4FIgB0BOMAbgVVADQFDAB6A0EAYAThAJoE8QB9BSsAeAS/AIAE9gB6BIcAYgTzAHoE9g"
        "B6BTAAjgUwAOEFMAC9BTAAlgUwAHkFMACyBTAAlwUwALYFMACYBTAAlwImAGwCJgCQAiYAkAImAGwDIAD/AyAAcAMgAFIDIABwAyABIgMgAHAF"
        "MAFOBTAAvwUwAL4FMADUBTAAtAUwAMMFMADDBTAAvwUwAJcFMAEGAiYAAAUnAGgCTQCgBBcAUgLrANoC6wBgAusA4gLrAHsDaQCQA2kAewe6AH"
        "oFEQAiAuIALgKpAQYC4gAuA64AkAQAAAAIAAAABIABAAIWAKACFgCgAmYA0gO6ANIDhgCgA4YAoAJOAIACTgCgBuoAoAJOAKACagCAAk4AoAVL"
        "AK4FSwDtBUsA4gVLAMMFSwDSBUsA0gVLAM4FSwCmA6YAAAPFAFIEAgByA6UAggfbAOYClQCWAAAAlgJAAAAGrADKBqwAygAAAHoAAAACAAAAAw"
        "AAABQAAwABAAAAFAAEAQYAAAAsACAABAAMAC8AOQBAAFoAYABpAHoAfgCjALEAtwDXAPcgFCAZIB0gIiAmIKwhkSGT//8AAAAgADAAOgBBAFsA"
        "YQBqAHsAowCwALcA1wD3IBMgGCAcICIgJiCsIZEhk///AAAACgAA/8AAAP+6/7wAAP+VAAD/yf+u/4/gX+Bd4F3gUuBX343fAN7/AAEALAAAAE"
        "gAAABSAAAAAABYAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQAGQAeABtADcAjQBjAHcAZgBnAIsAhAB7AHEAfABuAH4AfwCBAIMAggBl"
        "AGwAaABwAGkAigCJAI4AagBvAGsAiACMAIcAAAAAAAAAKABlAJ8AyADfAPQBMwFKAVgBdQGaAakB+AIrAmMCiQLNAv8DSQNbA4ADoQPpBCUESQ"
        "R1BMcFAgU7BXYFtQXcBioGUAZbBmcGfwaKBqYGtAbzBxkHTQeJB8UH5QgnCE0IcgiSCNcJCgk8CVQJvwoDClgKjgqiCtMLHQs8C3cLwwvWDDIM"
        "fwy1DM0M1QzdDOUM7Qz1DP0NBQ0NDRYNHg0qDTcNPw1HDYoNyQ3RDdkN4g3qDfIN+g4CDgoOEg4aDiIOKw4rDpwOug7+DyAPQg9UD2YPqQ/oEG"
        "sQpBC0EMIQ0RDeEOsQ+BEVESMRMRE/EUsRVxFjEWwRghGSEZ4RqxG0EckR4BH0EgwSLhJcEnsSqBK0EskS8hMkE4cTjxOeE54T0xQIFB4AAAAC"
        "ADQAAAVRBdIABwASAAAzATMBIwMhAwEDJicmJwYHBgcDNAId3AIkyJX9mpACu2wdJiAsKyAoGmkF0vouAaD+YAJGAS5Se2WUlmd9TP7SAAMAtA"
        "AABMgF0gATAB0AJwAAMxEhMhYWFRQGBgcVHgIVFAYGIyUhMjY1NCYmIyE1ITI2NjU0JiMhtAIQnMtjRG9BRotdZ9yw/p0BXq6TTItg/pgBSFCC"
        "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"
        "AAAQDK/+gF4gXSAB0AAAkCNxcWFhcWFyYnJiY1ETMRFAYHBgc2Nz4CNzcF4v10/XR00jNxNB4ZBgUICaYJBwUHDhAlU1Mm0gJ0/XQCjHTTM4NB"
        "JSEgISlTKQQU++wpUykgIRMULmRdJ9MAAAEAegUVAXUGAwALAAATIiY1NDYzMhYVFAb3M0pKMzRKSgUVRjEyRUUyMUYAAAAMAJYAAwABBAkAAA"
        "CQAAAAAwABBAkAAQAKAJAAAwABBAkAAgAOAJoAAwABBAkAAwAwAKgAAwABBAkABAAaANgAAwABBAkABQA2APIAAwABBAkABgAaASgAAwABBAkB"
        "AQAMAUIAAwABBAkBOAAYAU4AAwABBAkBOQAIAWYAAwABBAkBQAAMAW4AAwABBAkBQQAKAXoAQwBvAHAAeQByAGkAZwBoAHQAIAAyADAAMQA2AC"
        "AAVABoAGUAIABJAG4AdABlAHIAIABQAHIAbwBqAGUAYwB0ACAAQQB1AHQAaABvAHIAcwAgACgAaAB0AHQAcABzADoALwAvAGcAaQB0AGgAdQBi"
        "AC4AYwBvAG0ALwByAHMAbQBzAC8AaQBuAHQAZQByACkASQBuAHQAZQByAFIAZQBnAHUAbABhAHIANAAuADAAMAAxADsAUgBTAE0AUwA7AEkAbg"
        "B0AGUAcgAtAFIAZQBnAHUAbABhAHIASQBuAHQAZQByACAAUgBlAGcAdQBsAGEAcgBWAGUAcgBzAGkAbwBuACAANAAuADAAMAAxADsAZwBpAHQA"
        "LQA2ADYANgA0ADcAYwAwAGIAYgBJAG4AdABlAHIALQBSAGUAZwB1AGwAYQByAFcAZQBpAGcAaAB0AE8AcAB0AGkAYwBhAGwAIABTAGkAegBlAD"
        "EANABwAHQASQB0AGEAbABpAGMAUgBvAG0AYQBuAAAAAwAAAAAAAP6kAIwAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAH//wAPAAEAAAAMAAAAAAAA"
        "AAIACAABACMAAQAnADcAAQA6ADoAAQA8AD0AAQBEAEQAAQBGAEcAAQBWAFcAAQBoAGkAAQABAAAACgA8AF4ABERGTFQAGmN5cmwAJmdyZWsAJm"
        "xhdG4AJgAEAAAAAP//AAEAAQAEAAAAAP//AAEAAAACa2VybgAOa2VybgAWAAAAAgABAAAAAAAEAAEAAAABAAAAAgAGACoACQAIAAMADAAUABwA"
        "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"
        "AAEANwBWABMAAAAAAA4AEAAXABEADwAAAA4AFQAUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAADQAAAAwAAAAMAAAADAAGAAAAFgADABIAAQAAAAAABAAKAAgACQAJAAoACAAHAAcABwAFAAUAAQAAAAAAAgABAAQA"
        "AQACAAEAAAALAAsACwABAEQABAAAAB0AvgC+AIIA2gCQAJoAvgCwAL4AxADaAOAA9gEAAQoBIAEqATABNgE8AUwBRgFMAVoBeAGGAZQBrgG0AA"
        "EAHQADAAQABgAKAAsADAAPABAAEQAUABUAFgAXABgAGQAaACAAJwAwADEAMgAzADUAYwBwAIAAggCFAIkAAwB8/7sAff9SAIn/uwACAID/owCB"
        "/3UABQBx/5gAgP+AAIj/rwCL/68AjP+jAAMAY/+7AHz/uwB9/zsAAQCJ/68ABQBj/7sAbv+YAH3/UgCB/14Aif+MAAEAif+YAAUAY/+YAGz/uw"
        "CA/68Agf9pAIn/XgACAGP/mACB/2kAAgCA/6MAgf+MAAUAY/+AAH3/OwCA/5gAgf8vAIX/owACAID/uwCB/4AAAQCJ/+MAAQCB/1IAAQCB/8YA"
        "AgCB/68Aif+7AAEAY/+7AAMAff9pAIH/uwCJ/14ABwAU/4wAFv+AABf/rwAZ/2kAMv+7ADP/uwA1/7sAAwAU/68AMv+YADX/mAADABb/rwAY/6"
        "MAGf+YAAYAFP9eABb/aQAX/2kAGP+MABn/RgAa/4AAAQAU/4wACgAD/68AB/+vAA//rwAR/68AFP+MABX/rwAW/14AJgDFADL/XgA1/14AAQAw"
        "AAQAAAATAFoAcgByAHIAcgBgAGYAbAByAHIAcgByAHgAfgCEAI4AlACaAKAAAQATAAEACAAJAA0ADgAUABcAGAAeACMAJgAoAC4APwBwAIAAgg"
        "CIAIkAAQCBAAAAAQCA/14AAQCA/7sAAQCI/7oAAQCJAAAAAQCB/68AAQAwAAAAAgAW/5wAF/+MAAEAFP9eAAEAAQAAAAEAGP+6ABUAAgBFAAQA"
        "RQAFAEUABgBFAAgARQAJAEUACwBFAAwARQANAEUADgBFABAARQASAEUAHABFACIARQAjAEUAJwBFACgARQApAEUAKgBFACwARQAuAEUAAhUeAA"
        "QAABVeFnwANwAxAAAAAAAAAAAAAAAAAB4AAAAAAAAACgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/7sAAAAUAAAAAP/YAAD/Uv9gAAAAAAAAAAD/xgAAAAAAAP/iAAD/mP/SAAD/2/"
        "+YAAAAAAAAAAD/zv/i/4AAAAAA/+kAAAAAAAD/uwAA/5gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+IAAP9p/3QAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAP+YAAAAAAAA/5gAAAAAAAAAAP/YAAD/owAAAAAAAAAAAAAAAP+vAAD/mAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/4"
        "z/mP+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAB0AAP+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/7sAAAAAAAAAAAAA"
        "/7oAAAAAAAAAAAAAAAD/u//DAAAAAAAAAAD/ugAAAAAAAAAAAAD/uwAAAAAAAAAAAAD/pgAAAAAAAAAA/7sAAAAAAAAAAAAAAAAAAAAA/7sAAA"
        "AAAAD/rwAAAAAAAAAA/7oAHv/YAAAAAP/Y/3UAAP9p/1L/uwAL/5gAAAAAAAD/uwAAAAAAAP90AAAAAP91/4z/ugAAAAAAAP8v/17+9f9eAAAA"
        "AP+AAAAAAP+7AAD/dAAAAAAAAAAoAAAAAP/sAAAAAAAAAAAACgAAAAAAKP/s/+D/u//YAAAAAAAAAAAAAP/pAAAAAAAU/+wAAAAAAB7/7AAAAA"
        "AAAP/OAAAAAP+vAAAAAAAAAAAAAP/jAAAAAP/sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2AAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+MAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAg/94AIAAA/68AIAAAAAAAAAAgAAAAAP+M/68AFAAAAAAAAAAgAAD/uwAAACAAAAAgAAAAEQAAAAD/gP+MACAAIAAA/68AAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAD/uwAAAAr/2AAAAAD/dQAe//YAAAAAAAAAAP+7/7v/rwAA/68AAAAAAAoAAAAAAAAAAAAAAAAAAAAAAAAAAP+m/4AAHg"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+MAAAAAP9j/7D/u/9pAAD/b/+vAAAAAP91AAAAKP9e/8b/OwAAAAAAAP+vAAAAAAAAAAAA"
        "AP+AAAAAAP+7/7v/uwAAAAAAAAAAAAAAAAAAAAAAAP91AAAAAAAAAAAAAAAAAAAAAAAA/2D/jP/D/1L/L/9q/2kAAP+A/2kAKAAA/2kAAP+7AA"
        "AAAAAA/7sAAP+jAAAAAP+A/7v/gAAA/8P/u/9GAAAAAAAAAAAAAAAAAAAAAP+7/3UAAAAAAAAAAAAA/17/XgAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAP9p/2kAAAAAAAAAAAAAAAAAAAAAAAAAAP+jAAAAAAAA/7sAAAAAAAAAAAAAAAD/mAAAAAAAAAAAAAAAAAAAAAD/owAAAAAAAAAAAAAAAA"
        "AAAAAAAP+7AAAAAAAAAAAAAAAA/17/aQAAAAAAAAAA/7oAAAAAAAAAAAAA/5j/0gAAAAD/mAAAAAD/owAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAA/5gAAAAAAAAAAP+vAAD/O/+jAAAAAAAAAAD/mAAAAAAAAAAAAAD/df+7AAAAAP+AAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA//YAAAAAAAAAAP/sAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/jAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+IAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AP+7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/4gAAAA"
        "AAAAAA//YAAAAAAAAAAP/PAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/eAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/3gAA"
        "AAAAAAAAAAAAAP+vAAD/uwAAAAAAAP+7AAD/rwAAAAAAAP8jACD/u//sAAAAAP+7AAAAAAAAAAAAAAAA/4AAAP+7AAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAA/+wAAAAAAAAAAAAA/9IAAAAAAAAAAAAAAAAAAAAAAAAAAP+M/6MAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAA/6MAAAAAAAAAAAAAAAAAAAAAAAD/xgAA/7oAAAAA/4wAAAAAAAAAAAAA/6//ugAA/5j/7AAAAAD/owAAAA"
        "AAAAAAAAAAAAAAAAD/ugAAAAAAAAAAAAAAAAAAAAAAAAAA/7r/rwAA/9gAAP/s/9gAAAAAAAAAAAAAAAAAAP/YAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAA//UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/GAAD/0g"
        "AAAAAAAP91AAD/u/87/1IAAAAAAAAAAAAA/7sAAAAAAAD/dQAAAAAAAAAA/8YAAAAAAAD/sP9G/1L+9QAAAAAAAAAAAAD/owAA/3UAAAAAAAAA"
        "AAAAAAAAAAAAAAD/uwAAAAAAAAAAAAAAAP+j/7sAAAAAAAAAAP+jAAAAAAAAAAAAAP+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/mAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9IAAAAAAAAAAAAAAAD/0v/DAAAAAAAAAAD/9QAAAAAAAAAAAAD/0g"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9IAAAAAAAAAAAAAAAAAAAAA/7sAAAAAAAAAAAAAAAAAAAAAAAD/rwAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/uwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/EAAAAAP+7/7r/4AAAAA"
        "AAAP/SABQAAP/GAAAAAAAAAAAAAP/SAAAAAAAAAAAAAAAAAB4AAAAA/4z/gP+wAAAAAAAAAAAAAAAAAAAAAP+AAAAAAAAAAAAAAAAA/8YAAAAA"
        "/9IAAAAAAAAAKAAAAAAAAAAAAAAAAP+A/9IAAP+7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACgAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAD/2wAAAAD/dQAAAAAAAAAAAAAAAAAA/5gAAAAAAAAAAAAAAAAAAP+7AAAAAAAAAAAAAAAAAAAAAP9p/4wAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+Y/7oAAP+MAAD/mAAAAAAAAP+7AAAAAP+YAAD/gAAAAAAAAAAAAAAAAAAAAAAAAP+YAA"
        "AAMgAA/zv/gAAAAAAAAAAAAAAAAAAAAAAAAP+7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAHgAAAAAAAAAKAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/mAAA/7v/dAAA/5gAAAAAAAD/ow"
        "AAAAD/mAAA/4AAAAAAAAD/rwAAAAAAAAAeAAD/gAAAAAD/u/87/zsAAAAAAAAAAAAAAAAAAAAA/+z/uwAAAAAAHgAAAAAAAP+cAAAAAP/1AAAA"
        "AP9pAAAAAAAAAAAAAAAAAAAAAP+jAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/6//OwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+7AAAAAAAAAAAAAAAAAAAAAAAAAAD/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/6YAAAAAAAAAAAAAAAAAAP+7/7sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/ugAe/9gAAAAA/9j/dQAA/2n/UgAAAAsAAAAAAAAAAAAAAAAA"
        "AAAA/3QAAAAA/3X/jAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/6//xAAA/0YAAP/O/7sAAP+7AAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAP+7AAAAAAAAAAAAAAAAAAD/r/91AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/gP/V/4z+6AAd"
        "/4z/rwAAAB3/YwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAP/iAAAAAP9eAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD+rwAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/7oAAAAAAAAAAAAAAAD/u//DAAAAAAAAAAD/ugAAAAAAAAAAAAD/uwAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/sAAAAAD/OwAAAAAAAAAAAAD/2AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAA/tIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/6f9eAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/OwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+kAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADoAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAeAAAAAAAAAAAAAP+7AAAAAAAAAAAAAP+6AA"
        "AAAAAAAAAAAP/sAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAP/2AAAAAAAAAAD/7AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAD/mP+YAAD/IwAA/6MAAAAAAAD/rwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/zsAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/OAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAD/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAKAAEAIwAAACYANwAjADoAOwA1AD0APgA3AEEAQwA5AGUAbAA8AG4AcQ"
        "BEAHQAgABIAIMAiABVAIoAjABbAAEAAQCMAAUAEgAYAAQABwAoABwAAAAAAAgAFQAZAAAAAAAEACQABAAUABEADQAIACMAIQAXAAwAHQACAAEA"
        "AQAAAAEAHgAbAAIACQAAAAAACQAWAAAAAgACAAEAAQAbAAoADgAGAAMACwAgAB8ACwATADQAAAAAADIAIgAAADAAMwAAAAAANQAwADIAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMQAuAC8ALgAvAC4ALwArAAAANgAi"
        "ACcADwAAAAAAGgAsACkAKgAqACwAKQAmACYAJgAlACUADwAAAAAAEAAPABoADwAQAA8AAAAtAC0ALQABAAEAjAAFAAEABAABAAEAAQAEAAEAAQ"
        "AfAAEAAQABAAEABAABAAQAAQARAA0ACQAYABwAEgAMABUABwABAAIAAgACACAAAgABAA8AAAAAABcAAQABAAMAAwACAAMAAgADAAsABgAIAAoA"
        "GwAZAAoAFgAtAAAAAAAoACoAAAArACkAAAAoAC8ALgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAACcAJQAmACUAJgAlACYAHQAAADAAEwAsAA4AAAAAABQAIwAhACIAIgAjACEAHgAeAB4AGgAaAA4AAAAAABAADgAU"
        "AA4AEAAOAAAAJAAkACQAAQAAAAoAJAAyAAJERkxUAA5sYXRuAA4ABAAAAAD//wABAAAAAXRudW0ACAAAAAEAAAABAAQAAQAAAAEACAACAEQAHw"
        "BEAEUARgBHAEgASQBKAEsATABNAFIAUwBWAFcAVABVAFgATgBPAFAAUQBZAFoAWwBcAF0AXgBfAGAAYQBiAAIACAA6AEMAAABmAGsACgBxAHEA"
        "EAB7AHwAEQB+AH8AEwCBAIgAFQCLAIsAHQCQAJAAHgAAAAEAAQAIAAMAAAAUAAMAAAAsAAJvcHN6ATgAAHdnaHQBAQABaXRhbAFAAAIABgASAC"
        "IAAQAAAAIBOQAOAAAAAwABAAIAAgGQAAACvAAAAAMAAgACAUEAAAAAAAEAAAAA"
    ),
    600: (
        "AAEAAAAPAIAAAwBwR0RFRgIMAhUAADEwAAAAQEdQT1OSc5G9AAAxcAAAIq5HU1VCN/w2UwAAVCAAAAC2T1MvMnHhFV4AAAF4AAAAYFNUQVRX0j"
        "/5AABU2AAAAFpjbWFwkjST7AAABCgAAAEaZ2FzcAAAABAAADEoAAAACGdseWYG3toYAAAGcAAAKGJoZWFkMFNA3wAAAPwAAAA2aGhlYQ+ZDKoA"
        "AAE0AAAAJGhtdHiZrkbmAAAB2AAAAlBsb2NhT7JEgwAABUQAAAEqbWF4cACgAJwAAAFYAAAAIG5hbWU3wlmpAAAu1AAAAjJwb3N0/rgArQAAMQ"
        "gAAAAgAAEAAAAEAEL1oIPcXw889QABCAAAAAAA4naHkAAAAADm7m5D/9b+IAgAB7IAAAADAAIAAAAAAAAAAQAAB8D+EgAACCn/1v3bCAAIAAAA"
        "AAAAAAAAAAAAAAAAAJQAAQAAAJQAWgAFAEAAAwABAAAAAAAAAAAAAAAAAAMAAQAEBUICWAAFAAAFMwTNAAAAmgUzBM0AAALNAK0CnwAAAgAFAw"
        "AAAAIABIAAAAMAAAAiAAAAAAAAAABSU01TAMAAICGTB8D+EgAACN0ClAAAAAEAAAAABF4F0gAAACAADAVAAUgF0gAyBUYAlgXlAGcFxwCWBNgA"
        "lgS0AJYF/gBnBfcAlgI3AJYEowBOBaAAlgSGAJYHYQCWBhMAlgYmAGcFKQCWBi8AZwU4AJYFNABfBUgAUwXjAJYF0gAyCCkAMgXCADUFtQAyBT"
        "gAdASYAEwE/gCKBKkAWQT+AFkEuwBZAxwAFAUBAFkE5gCKAhgAdQIYAIoCGP/WAhj/1gSOAIoCGACKBzQAigTlAIoE3wBZBP4AigT+AFkDLQCK"
        "BGUAWALTABQE5gCKBLIAJwa3ACwEjQAyBLUAJwSHAHoFNABfBQkAYwVuADgFRwBnA2IAXgT8AH4FFwBrBVQAawTmAGkFHgBnBJwAUwUfAGcFHg"
        "BnBS0AbQUtAMEFLQCWBS0AcQUtAFQFLQCHBS0AbwUtAJsFLQBuBS0AbwImAEoCJgB1AiYAdQImAEoDIADEAyAAZgMgAC4DIABmAyAA8AMgAGYF"
        "LQFGBS0ApQUtAKQFLQC0BS0AnwUtAJwFLQCpBS0ApQUtAIIFLQD9AiYAAAVNAFkCkgCmBFkAUAL8ALoC/ABNAvwAxAL8AG0DowCNA6MAbQf+AG"
        "cFJgAaAwgAIgLfAPYDCAAiA7kAjQQAAAAIAAAABAcAxAJaAKQCWgCkApsAzQQvAM0EDgCkBAMApAKNAHoCjQCmB6YApgKNAKYCogB6Ao0ApgVi"
        "AKkFYgDYBWIAzwViALsFYgC4BWIAxAViAMAFYgCdA8EAAAPaAEkEUQCRA6oAeAgJAMgCzwCdAAAAnQIEAAAHDQDKBw0AygAAAH8AAAACAAAAAw"
        "AAABQAAwABAAAAFAAEAQYAAAAsACAABAAMAC8AOQBAAFoAYABpAHoAfgCjALEAtwDXAPcgFCAZIB0gIiAmIKwhkSGT//8AAAAgADAAOgBBAFsA"
        "YQBqAHsAowCwALcA1wD3IBMgGCAcICIgJiCsIZEhk///AAAACgAA/8AAAP+6/7wAAP+VAAD/yf+u/4/gX+Bd4F3gUuBX343fAN7/AAEALAAAAE"
        "gAAABSAAAAAABYAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQAGQAeABtADcAjQBjAHcAZgBnAIsAhAB7AHEAfABuAH4AfwCBAIMAggBl"
        "AGwAaABwAGkAigCJAI4AagBvAGsAiACMAIcAAAAAAAAAKABlAJ8AxgDdAPIBMAFJAVcBdgGcAasB+gIvAmUCiwLPAv4DSQNcA4IDpAPuBCsEUA"
        "R8BM4FCgVDBX8FvgXlBjMGWwZmBnMGiwaWBrQGwgcCBykHXQeZB9YH9gg4CF8IhginCO0JIglVCW0J2gofCnQKqQq9Cu4LOQtZC5UL4gv1DFEM"
        "nwzTDOsM8wz7DQMNCw0TDRsNIw0rDTQNPA1IDVUNXQ1lDaYN4g3qDfIN+w4DDgsOEw4bDiMOKw4zDjsOQw5DDrQO0w8XDzkPWw9tD38PwA/4EH"
        "oQsxDDENEQ4BDtEPoRBxEkETIRQRFQEVwRaBF0EX0RkxGjEa8RvBHFEdsR8xIHEh8SQRJwEo8SvBLIEt0TBBM2E5kToROwE7AT5RQaFDEAAAAC"
        "ADIAAAWhBdIABwASAAAzASEBIQMhAwEnJicmJwYHBgcHMgIIAVMCFP7bfv3SegJeQScqHiMhHSkkPwXS+i4Bcf6PAki+eJhsgYNtmXS+AAMAlg"
        "AABOsF0gATAB0AJwAAMxEhMhYWFRQGBgcVHgIVFAYGIyUhMjY1NCYmIyE1ITI2NjU0JiMhlgI6odZqRnVJT5JdcOGr/rIBJJSDQnlT/tMBDUdw"
        "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"
        "bhAzACvf1DlOE1jEQTEg4QM2wv/EUDuy9sMxAPAwMxa2Mm4QAAAQDK/+UGQwXSAB0AAAkCNxcWFhcWFyYnJiY1ETMRFAYHBgc2Nz4CNzcGQ/1D"
        "/USU4TVzNA8OAwMKDdcNCQQDAwMkVVQm4QKi/UMCvZThNYxEFBMQETNsLgO7/EUubDMRDwMEMGtjJuEAAAEAfwT8Aa4GGQALAAABIiY1NDYzMh"
        "YVFAYBFj5ZWT4/WVkE/FQ6PFNTOztUAAAAAAAADQCiAAMAAQQJAAAAkAAAAAMAAQQJAAEAHACQAAMAAQQJAAIADgCsAAMAAQQJAAMAMgC6AAMA"
        "AQQJAAQAHACQAAMAAQQJAAUANgDsAAMAAQQJAAYAHAEiAAMAAQQJAQEADAE+AAMAAQQJATQAEAFKAAMAAQQJATgAGAFaAAMAAQQJATkACAFyAA"
        "MAAQQJAUAADAF6AAMAAQQJAUEACgGGAEMAbwBwAHkAcgBpAGcAaAB0ACAAMgAwADEANgAgAFQAaABlACAASQBuAHQAZQByACAAUAByAG8AagBl"
        "AGMAdAAgAEEAdQB0AGgAbwByAHMAIAAoAGgAdAB0AHAAcwA6AC8ALwBnAGkAdABoAHUAYgAuAGMAbwBtAC8AcgBzAG0AcwAvAGkAbgB0AGUAcg"
        "ApAEkAbgB0AGUAcgAgAFMAZQBtAGkAQgBvAGwAZABSAGUAZwB1AGwAYQByADQALgAwADAAMQA7AFIAUwBNAFMAOwBJAG4AdABlAHIALQBTAGUA"
        "bQBpAEIAbwBsAGQAVgBlAHIAcwBpAG8AbgAgADQALgAwADAAMQA7AGcAaQB0AC0ANgA2ADYANAA3AGMAMABiAGIASQBuAHQAZQByAC0AUwBlAG"
        "0AaQBCAG8AbABkAFcAZQBpAGcAaAB0AFMAZQBtAGkAQgBvAGwAZABPAHAAdABpAGMAYQBsACAAUwBpAHoAZQAxADQAcAB0AEkAdABhAGwAaQBj"
        "AFIAbwBtAGEAbgAAAAMAAAAAAAD+tQCtAAAAAAAAAAAAAAAAAAAAAAAAAAAAAQAB//8ADwABAAAADAAAAAAAAAACAAgAAQAjAAEAJwA3AAEAOg"
        "A6AAEAPAA9AAEARABEAAEARgBHAAEAVgBXAAEAaABpAAEAAQAAAAoAPABeAARERkxUABpjeXJsACZncmVrACZsYXRuACYABAAAAAD//wABAAEA"
        "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"
        "AAAAFAADAAYAAAAAAAAAAgAKAAcACAAIAAoABwAFAAUABQAEAAQAAAAAAAAAAQAAAAIAAAABAAAAAAALAAsACwABADcAVgATAAAAAAAOABAAFw"
        "ARAA8AAAAOABUAFAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA0A"
        "AAAMAAAADAAAAAwABgAAABYAAwASAAEAAAAAAAQACgAIAAkACQAKAAgABwAHAAcABQAFAAEAAAAAAAIAAQAEAAEAAgABAAAACwALAAsAAQBEAA"
        "QAAAAdAL4AvgCCANoAkACaAL4AsAC+AMQA2gDgAPYBAAEKASABKgEwATYBPAFMAUYBTAFaAXgBhgGUAa4BtAABAB0AAwAEAAYACgALAAwADwAQ"
        "ABEAFAAVABYAFwAYABkAGgAgACcAMAAxADIAMwA1AGMAcACAAIIAhQCJAAMAfP+7AH3/UgCJ/7sAAgCA/6MAgf91AAUAcf+YAID/gACI/68Ai/"
        "+vAIz/owADAGP/uwB8/7sAff87AAEAif+vAAUAY/+7AG7/mAB9/1IAgf9eAIn/jAABAIn/mAAFAGP/mABs/7sAgP+vAIH/aQCJ/14AAgBj/5gA"
        "gf9pAAIAgP+jAIH/jAAFAGP/gAB9/zsAgP+YAIH/LwCF/6MAAgCA/7sAgf+AAAEAif/jAAEAgf9SAAEAgf/GAAIAgf+vAIn/uwABAGP/uwADAH"
        "3/aQCB/7sAif9eAAcAFP+MABb/gAAX/68AGf9pADL/uwAz/7sANf+7AAMAFP+vADL/mAA1/5gAAwAW/68AGP+jABn/mAAGABT/XgAW/2kAF/9p"
        "ABj/jAAZ/0YAGv+AAAEAFP+MAAoAA/+vAAf/rwAP/68AEf+vABT/jAAV/68AFv9eACYAxQAy/14ANf9eAAEAMAAEAAAAEwBaAHgAeAB4AHgAYA"
        "BmAGwAeAByAHIAeAB+AIQAigCUAJoAoACmAAEAEwABAAgACQANAA4AFAAXABgAHgAjACYAKAAuAD8AcACAAIIAiACJAAEAgf/MAAEAgP9eAAEA"
        "gP+7AAEAiP+6AAEAiQAAAAEAiQAZAAEAgf+vAAEAMAAAAAIAFv+cABf/iwABABT/XgABAAH/zAABABj/sgAVAAIARQAEAEUABQBFAAYARQAIAE"
        "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"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/4wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAD/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/bAAAAAAAAAAAAAAAAAAAAAAAAAAD/uwAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/+YAAAAAAAAAAP/2AAAAAAAA"
        "AAD/yAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/2gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9oAAAAAAAAAAAAAAAD/rw"
        "AA/7IAAAAAAAD/uwAA/68AAAAAAAD/TQAU/7v/7AAAAAD/uwAAAAAAAAAAAAAAAP+AAAD/sgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AP/sAAAAAAAAAAAAAP/SAAAAAAAAAAAAAAAAAAAACgAAAAD/jP+SAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAP+jAAAAAAAAAAAAAAAAAAAAAAAA/8YAAP+hAAAAAP+MAAAAAAAAAAAAAP+v/7IAAP+Y/+gAAAAA/6MAAAAAAAAAAAAAAAAAAAAA"
        "/6EAAAAAAAAAAAAAAAAAAAAAAAAAAP+2/68AAP/UAAD/6P/UAAAAAAAAAAAAAAAAAAD/zQAAAAAAAAAAAAgAAAAAAAAAAAAAAAAAAP/oAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/xgAA/9IAAAAAAAD/dQAA/3P/"
        "Qv9rAAAAAAAAAAAAAP+7AAAAAAAA/2gAAAAAAAD/zv/GAAAAAAAA/2j/Rv9S/vUAAAAAAAAAAAAA/6MAAP9oAAAAAAAAAAAAAAAAAAAAAAAA/7"
        "sAAAAAAAAAAAAAAAD/o/+7AAAAAAAAAAD/owAAAAAAAAAAAAD/rwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "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"
        "AAAAAAAAAAAAAAAAAAAA/zsAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAGf/xABkAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAlAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIgAAAAAAAAAAAAD/uwAAAAAAAAAAAAD/tgAAAAAAAAAAAAD/1gAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP/rAAAAAAAAAAAA"
        "AAAAAAD/8gAAAAAAAAAA/+gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/5"
        "j/mAAA/yMAAP+jAAAAAAAA/68AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP87AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAD/zgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAKAAAAAAAAAAoAAAAA/4AAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAIACgABACMAAAAmADcAIwA6ADsANQA9AD4ANwBBAEMAOQBlAGwAPABuAHEARAB0AIAASACDAIgA"
        "VQCKAIwAWwABAAEAjAAFABIAGAAEAAcAKAAcAAAAAAAIABUAGQAAAAAABAAkAAQAFAARAA0ACAAjACEAFwAMAB0AAgABAAEAAAABAB4AGwACAA"
        "kAAAAAAAkAFgAAAAIAAgABAAEAGwAKAA4ABgADAAsAIAAfAAsAEwA0AAAAAAAyACIAAAAwADMAAAAAADUAMAAyAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADEALgAvAC4ALwAuAC8AKwAAADYAIgAnAA8AAAAAABoALA"
        "ApACoAKgAsACkAJgAmACYAJQAlAA8AAAAAABAADwAaAA8AEAAPAAAALQAtAC0AAQABAIwABQABAAQAAQABAAEABAABAAEAHwABAAEAAQABAAQA"
        "AQAEAAEAEQANAAkAGAAcABIADAAVAAcAAQACAAIAAgAgAAIAAQAPAAAAAAAXAAEAAQADAAMAAgADAAIAAwALAAYACAAKABsAGQAKABYALQAAAA"
        "AAKAAqAAAAKwApAAAAKAAvAC4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAnACUAJgAlACYAJQAmAB0AAAAwABMALAAOAAAAAAAUACMAIQAiACIAIwAhAB4AHgAeABoAGgAOAAAAAAAQAA4AFAAOABAADgAAACQAJA"
        "AkAAAAAQAAAAoAJAAyAAJERkxUAA5sYXRuAA4ABAAAAAD//wABAAAAAXRudW0ACAAAAAEAAAABAAQAAQAAAAEACAACAEQAHwBEAEUARgBHAEgA"
        "SQBKAEsATABNAFIAUwBWAFcAVABVAFgATgBPAFAAUQBZAFoAWwBcAF0AXgBfAGAAYQBiAAIACAA6AEMAAABmAGsACgBxAHEAEAB7AHwAEQB+AH"
        "8AEwCBAIgAFQCLAIsAHQCQAJAAHgAAAAEAAQAIAAMAAAAUAAMAAAAsAAJvcHN6ATgAAHdnaHQBAQABaXRhbAFAAAIABgASAB4AAQAAAAIBOQAO"
        "AAAAAQABAAABNAJYAAAAAwACAAIBQQAAAAAAAQAAAAA="
    ),
    800: (
        "AAEAAAAPAIAAAwBwR0RFRgIMAhUAADFMAAAAQEdQT1OPaY2LAAAxjAAAIq5HU1VCN/w2UwAAVDwAAAC2T1MvMnKpFawAAAF4AAAAYFNUQVRX1E"
        "DBAABU9AAAAFpjbWFwkjST7AAABCgAAAEaZ2FzcAAAABAAADFEAAAACGdseWYEAVGtAAAGcAAAKHhoZWFkMItA3wAAAPwAAAA2aGhlYQ/RDLkA"
        "AAE0AAAAJGhtdHisCzw3AAAB2AAAAlBsb2NhUqFHZAAABUQAAAEqbWF4cACgAJwAAAFYAAAAIG5hbWU5W1osAAAu6AAAAjpwb3N0/soA0gAAMS"
        "QAAAAgAAEAAAAEAELRDag+Xw889QABCAAAAAAA4naHkAAAAADm7m5D/8X+IAhJB7IAAAADAAIAAAAAAAAAAQAAB8D+EgAACHj/xf2bCEkIAAAA"
        "AAAAAAAAAAAAAAAAAJQAAQAAAJQAWgAFAEAAAwABAAAAAAAAAAAAAAAAAAMAAQAEBWsDIAAFAAAFMwTNAAAAmgUzBM0AAALNANICnwAAAgAFAw"
        "AAAAIABIAAAAMAAAAiAAAAAAAAAABSU01TAMAAICGTB8D+EgAACN0ClAAAAAEAAAAABF4F0gAAACAADAVAAUgGKAAvBVEAdAXzAFIFyAB0BOEA"
        "dASvAHQGBQBSBf0AdAJJAHQEuAA2BegAdASGAHQHjAB0BiAAdAYvAFIFNwB0BkEAUgVMAHQFSABIBWoAQgXRAHQGKAAvCHgALwYXADEGBAAvBW"
        "4AbAS1ADwFGgBzBMMASAUaAEgEzgBIA0cAFAUdAEgFFQBzAkQAbQJEAHMCRP/FAkT/xQS+AHMCRABzB2sAcwUVAHME9ABIBRoAcwUaAEgDXABz"
        "BJYAQQMOABQFFQBzBOwAFgbnAA8EwQAhBPIAFgSmAHUFSABIBTMAVwWJAD0FiQBSA4gAWwUaAFsFQQBYBYIAXQUSAE8FSwBSBLQAQgVQAFIFSw"
        "BSBSoASAUqAJ4FKgBnBSoASAUqACsFKgBYBSoAQgUqAH0FKgA/BSoAQgImACQCJgBXAiYAVwImACQDIACDAyAAWwMgAAcDIABbAyAAuAMgAFsF"
        "KgE9BSoAiAUqAIgFKgCQBSoAiAUqAHEFKgCMBSoAiAUqAGoFKgD0AiYAAAV3AEgC3gCsBKIATQMPAJYDDwA3Aw8ApAMPAF0D5ACLA+QAXQhKAF"
        "IFPgARAzMAFAMaAOUDMwAUA8UAiwQAAAAIAAAAA4EAgAKmAKgCpgCoAtYAxwSxAMcEpQCoBI4AqALSAHQC0gCsCHcArALSAKwC4QB0AtIArAV8"
        "AKMFfADABXwAuQV8ALIFfACbBXwAtQV8ALEFfACUA+AAAAPyAEAEqQCzA7AAbQg8AKgDDwClAAAApQHAAAAHeQDKB3kAygAAAIUAAAACAAAAAw"
        "AAABQAAwABAAAAFAAEAQYAAAAsACAABAAMAC8AOQBAAFoAYABpAHoAfgCjALEAtwDXAPcgFCAZIB0gIiAmIKwhkSGT//8AAAAgADAAOgBBAFsA"
        "YQBqAHsAowCwALcA1wD3IBMgGCAcICIgJiCsIZEhk///AAAACgAA/8AAAP+6/7wAAP+VAAD/yf+u/4/gX+Bd4F3gUuBX343fAN7/AAEALAAAAE"
        "gAAABSAAAAAABYAAAAXAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACQAGQAeABtADcAjQBjAHcAZgBnAIsAhAB7AHEAfABuAH4AfwCBAIMAggBl"
        "AGwAaABwAGkAigCJAI4AagBvAGsAiACMAIcAAAAAAAAAKABjAJ0AxADdAPMBMgFLAVkBeAGeAa4B+gIvAmUCiwLPAvwDSQNdA4MDpAPuBCoETg"
        "R8BM8FCwVFBYEFwQXpBjgGYAZrBngGkAabBrkGxwcIBzAHZAefB9sH/Ag/CGcIjgivCPYJKwleCXcJ5AooCn0KswrICvkLRQtlC6IL8AwEDGEM"
        "rwzlDP4NBg0ODRYNHg0mDS4NNg0+DUcNTw1bDWgNcA14DbIN7A30DfwOBQ4NDhUOHQ4lDi0ONQ49DkUOTQ5NDrsO2g8eD0EPZA93D4oPxA/+EI"
        "EQvhDOENwQ7BD6EQgRFhEzEUERUBFfEWsRdxGDEYwRohGyEb4RyxHUEeoSAhIYEjISVBKDEqMS0RLeEvQTGRNLE64TthPFE8UT9RQlFDwAAAAC"
        "AC8AAAX5BdIABwASAAAzASEBIQMhAwEnJicmJwYHBgcHLwHxAdkCAP50Zf4QYQH7FDIuGxoZGCovFAXS+i4BPf7DAktAo7hnbW1ouKJAAAMAdA"
        "AABREF0gATAB0AJwAAMxEhMhYWFRQGBgcVHgIVFAYGIwEzMjY1NCYmIyM1MzI2NjU0JiMjdAJqpuJxR31RWZldeeam/snkd3E2ZUbrzTtdNWxb"
        "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"
        "EhETQ3NjcGBwYGBwfKAvMC8rfyNjs7MwsICf7zCQgLGh0rVyXyAv0C8/0NufI3S0pHOj5ENfyoA1g1RD46JCY6aiXyAAABAMr/4gavBdIAGQAA"
        "CQI3FxYXFhcmJyY1ESERFAcGBzY3NjY3Nwav/Q39DrfyNzw6MgsICQENCQkLGx4rVibxAtX9DQLzufI3S0lGOj1DNQNY/Kg1Q0A7JSg5aiXyAA"
        "ABAIUE4QHuBjEACwAAASImNTQ2MzIWFRQGATlKampKS2pqBOFjRUZiYUdGYgAAAAANAKIAAwABBAkAAACQAAAAAwABBAkAAQAeAJAAAwABBAkA"
        "AgAOAK4AAwABBAkAAwA0ALwAAwABBAkABAAeAJAAAwABBAkABQA2APAAAwABBAkABgAeASYAAwABBAkBAQAMAUQAAwABBAkBNgASAVAAAwABBA"
        "kBOAAYAWIAAwABBAkBOQAIAXoAAwABBAkBQAAMAYIAAwABBAkBQQAKAY4AQwBvAHAAeQByAGkAZwBoAHQAIAAyADAAMQA2ACAAVABoAGUAIABJ"
        "AG4AdABlAHIAIABQAHIAbwBqAGUAYwB0ACAAQQB1AHQAaABvAHIAcwAgACgAaAB0AHQAcABzADoALwAvAGcAaQB0AGgAdQBiAC4AYwBvAG0ALw"
        "ByAHMAbQBzAC8AaQBuAHQAZQByACkASQBuAHQAZQByACAARQB4AHQAcgBhAEIAbwBsAGQAUgBlAGcAdQBsAGEAcgA0AC4AMAAwADEAOwBSAFMA"
        "TQBTADsASQBuAHQAZQByAC0ARQB4AHQAcgBhAEIAbwBsAGQAVgBlAHIAcwBpAG8AbgAgADQALgAwADAAMQA7AGcAaQB0AC0ANgA2ADYANAA3AG"
        "MAMABiAGIASQBuAHQAZQByAC0ARQB4AHQAcgBhAEIAbwBsAGQAVwBlAGkAZwBoAHQARQB4AHQAcgBhAEIAbwBsAGQATwBwAHQAaQBjAGEAbAAg"
        "AFMAaQB6AGUAMQA0AHAAdABJAHQAYQBsAGkAYwBSAG8AbQBhAG4AAAADAAAAAAAA/scA0gAAAAAAAAAAAAAAAAAAAAAAAAAAAAEAAf//AA8AAQ"
        "AAAAwAAAAAAAAAAgAIAAEAIwABACcANwABADoAOgABADwAPQABAEQARAABAEYARwABAFYAVwABAGgAaQABAAEAAAAKADwAXgAEREZMVAAaY3ly"
        "bAAmZ3JlawAmbGF0bgAmAAQAAAAA//8AAQABAAQAAAAA//8AAQAAAAJrZXJuAA5rZXJuABYAAAACAAEAAAAAAAQAAQAAAAEAAAACAAYAKgAJAA"
        "gAAwAMABQAHAABAAIAAAfKAAEAAgAACaAAAQACAAAKlAACAAgAAwAMAUwB6gABADIABAAAABQAeAB4AF4AeAB+AJQAmgCyALgArACsALIAuADO"
        "ANQA5gEkASQBJAEuAAEAFAA6AEAAQQBDAGMAbABwAHUAdgB3AHgAeQB6AIAAggCJAIoAiwCMAI0ABgA//+wAQ//sAGP/owBt/4wAgf9GAIn+uw"
        "ABAIn/owAFAHD/gAB1/0YAd/+7AHj/uwB5/0YAAQCJ/68ABAB1/6kAdv+MAHn/qQB6/4wAAQBj/7sAAQBj/4AABQBj/3UAbf8AAIH/OwCI/6MA"
        "if+vAAEAcP+vAAQAQf9pAHD/aQB1/zsAef87AA8AOv+jADv/IwA9/6MAPv+MAD//owBA/6MAQv+jAEP/owBs/68AcP9eAHX/rwB5/68Aiv91AI"
        "v/dQCM/3UAAgBj/7sAif91AAQAdf+AAHb/dQB5/4AAev91AAEAIAAEAAAACwA6AHYARABiAHAAdgB8AIYAhgCGAJgAAQALADkAOwA/AEAAQQBv"
        "AHAAewB8AH0AiQACADoAAABAAAAABwA7AAAAe//UAHz/1AB9/9QAiv/xAIv/8QCM//EAAwB7/8YAfP/GAH3/xgABAI0AAAABAIkANAACAHD/nA"
        "CB/5IABAA///kAQ//hAGT/3QCQ/6gAAQBvAEUAAgQwAAQAAARkBRYAFgAYAAAAAAAAAAAAAAAAAAAAAAAAAAD/4QAAAAAAAAAAAAAAAP/6/6kA"
        "AAAA/8EAAP/eAAAAAAAAAAAAAAAAAAAAAAAAAAD/jAAAAAAAAAAAAAAAAAAA/3UAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAA/68AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAD/owAAAAAAAAAAAAAAAAAA/4AAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/6YAAP8e/ycAAAAAAAD/TP/BAAD/RP/UAAAAAP/B/8IAAA"
        "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"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP87AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD"
        "T/+gA0AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/0AAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAD/gAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACYAAAAAAAAAAAAA"
        "/7sAAAAAAAAAAAAA/7IAAAAAAAAAAAAA/74AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAD/1AAAAAAAAAAAAAAAAAAA/+4AAAAAAAAAAP/kAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP+Y/5gAAP8jAAD/owAAAAAAAP+vAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAD/OwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/84AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAFgAAAAAAAAAWAAAAAP+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAAoAAQAjAAAAJgA3ACMAOgA7ADUAPQA+ADcA"
        "QQBDADkAZQBsADwAbgBxAEQAdACAAEgAgwCIAFUAigCMAFsAAQABAIwABQASABgABAAHACgAHAAAAAAACAAVABkAAAAAAAQAJAAEABQAEQANAA"
        "gAIwAhABcADAAdAAIAAQABAAAAAQAeABsAAgAJAAAAAAAJABYAAAACAAIAAQABABsACgAOAAYAAwALACAAHwALABMANAAAAAAAMgAiAAAAMAAz"
        "AAAAAAA1ADAAMgAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAxAC4ALw"
        "AuAC8ALgAvACsAAAA2ACIAJwAPAAAAAAAaACwAKQAqACoALAApACYAJgAmACUAJQAPAAAAAAAQAA8AGgAPABAADwAAAC0ALQAtAAEAAQCMAAUA"
        "AQAEAAEAAQABAAQAAQABAB8AAQABAAEAAQAEAAEABAABABEADQAJABgAHAASAAwAFQAHAAEAAgACAAIAIAACAAEADwAAAAAAFwABAAEAAwADAA"
        "IAAwACAAMACwAGAAgACgAbABkACgAWAC0AAAAAACgAKgAAACsAKQAAACgALwAuAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAJwAlACYAJQAmACUAJgAdAAAAMAATACwADgAAAAAAFAAjACEAIgAiACMAIQAeAB4AHg"
        "AaABoADgAAAAAAEAAOABQADgAQAA4AAAAkACQAJAAAAAEAAAAKACQAMgACREZMVAAObGF0bgAOAAQAAAAA//8AAQAAAAF0bnVtAAgAAAABAAAA"
        "AQAEAAEAAAABAAgAAgBEAB8ARABFAEYARwBIAEkASgBLAEwATQBSAFMAVgBXAFQAVQBYAE4ATwBQAFEAWQBaAFsAXABdAF4AXwBgAGEAYgACAA"
        "gAOgBDAAAAZgBrAAoAcQBxABAAewB8ABEAfgB/ABMAgQCIABUAiwCLAB0AkACQAB4AAAABAAEACAADAAAAFAADAAAALAACb3BzegE4AAB3Z2h0"
        "AQEAAWl0YWwBQAACAAYAEgAeAAEAAAACATkADgAAAAEAAQAAATYDIAAAAAMAAgACAUEAAAAAAAEAAAAA"
    ),
}


def _pdf_fonts(pdf) -> str:
    """Registers Inter on the PDF (regular, B = semibold, I = extra bold). Returns the family to use."""
    import os
    import tempfile
    try:
        folder = os.path.join(tempfile.gettempdir(), "lead_overview_fonts")
        os.makedirs(folder, exist_ok=True)
        for weight, style in ((400, ""), (600, "B"), (800, "I")):
            path = os.path.join(folder, f"inter{weight}.ttf")
            if not os.path.exists(path):
                with open(path, "wb") as fh:
                    fh.write(base64.b64decode("".join(_INTER_B64[weight])))
            pdf.add_font("Inter", style, path)
        return "Inter"
    except Exception:
        return "Helvetica"


def _pdf_safe(t: str) -> str:
    """Characters Inter (as cut down) doesn't have."""
    for k, v in {"→": "-", "←": "-", "✓": "", "🔥": "", "↩️": "", "⬇": ""}.items():
        t = t.replace(k, v)
    return t


def weekly_pdf(ws: Dict[str, Any]) -> bytes:
    """Two-page A4 summary styled like the dashboard: midnight background, gradient accents, Inter, rounded cards.
    Page 1: activity (totals, apps, emails per day, highlights). Page 2: engagement from Zoho (if checked)."""
    from fpdf import FPDF

    # ---- palette (same tokens as the page CSS) ----
    BG, SURF, SURF2, SURF3 = (10, 14, 26), (17, 24, 39), (22, 31, 51), (28, 39, 64)
    BORDER, BORDER2 = (33, 42, 60), (46, 57, 80)
    TEXT, MUTED, FAINT = (231, 234, 243), (140, 152, 176), (94, 106, 130)
    ACC, ACC2, GOOD, BAD = (124, 131, 255), (56, 214, 245), (52, 211, 153), (248, 113, 113)
    ACC_SOFT = (29, 33, 64)
    W, H, L = 210, 297, 12
    CW = W - 2 * L

    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(False)
    pdf.set_margins(0, 0, 0)
    F = _pdf_fonts(pdf)  # "Inter" if it loaded, else Helvetica
    T = _pdf_txt if F == "Helvetica" else _pdf_safe

    def font(weight: str, size: float, color=TEXT, spacing: float = 0) -> None:
        if F == "Helvetica":
            pdf.set_font("Helvetica", "B" if weight in ("B", "X") else "", size)
        else:
            pdf.set_font("Inter", {"": "", "B": "B", "X": "I"}[weight], size)  # I = the 800 weight
        pdf.set_text_color(*color)
        pdf.set_char_spacing(spacing)

    def text(x: float, y: float, s: str, w: float = 0, h: float = 5, align: str = "L") -> None:
        pdf.set_xy(x, y)
        pdf.cell(w, h, T(s), align=align)

    def tw(s: str) -> float:
        return pdf.get_string_width(T(s))

    def box(x, y, w, h, fill, r=3.2, stroke=None, corners=True) -> None:
        pdf.set_fill_color(1, 2, 3)  # Forces the colour to be written again after a gradient
        pdf.set_fill_color(*fill)
        if stroke:
            pdf.set_draw_color(*stroke)
            pdf.set_line_width(0.25)
        pdf.rect(x, y, w, h, "DF" if stroke else "F", round_corners=corners if r else False, corner_radius=r)

    def grad_box(x, y, w, h, c1, c2, r=3.2, vertical=False) -> None:
        try:
            from fpdf.pattern import LinearGradient
            g = LinearGradient(x, y, x if vertical else x + w, y + h if vertical else y, [c1, c2])
            with pdf.use_pattern(g):
                pdf.rect(x, y, w, h, "F", round_corners=bool(r), corner_radius=r)
        except Exception:  # Older fpdf2: plain colour instead of the gradient
            box(x, y, w, h, c1, r)

    def page_bg() -> None:
        pdf.add_page()
        pdf.set_fill_color(*BG)
        pdf.rect(0, 0, W, H, "F")
        try:  # Soft glows, like the page background
            from fpdf.pattern import RadialGradient
            with pdf.use_pattern(RadialGradient(170, -20, 0, 170, -20, 150, [(20, 30, 56), BG], extend_after=True)):
                pdf.rect(0, 0, W, H, "F")
        except Exception:
            pass

    def card(y: float, h: float) -> None:
        grad_box(L, y, CW, h, SURF2, SURF, r=3.6, vertical=True)
        pdf.set_draw_color(*BORDER)
        pdf.set_line_width(0.25)
        pdf.rect(L, y, CW, h, "D", round_corners=True, corner_radius=3.6)

    def section(num: str, title: str, sub: str, y: float) -> float:
        box(L + 6, y, 9, 9, ACC_SOFT, r=2.4, stroke=(52, 57, 110))
        font("X", 8, ACC)
        text(L + 6, y + 2, num, 9, 5, "C")
        font("B", 11.5, TEXT)
        text(L + 18, y + 0.2, title)
        font("", 7.8, MUTED)
        text(L + 18, y + 5.2, sub)
        return y + 14

    def chip(x: float, y: float, s: str, good: Optional[bool]) -> None:
        col = GOOD if good else (BAD if good is False else MUTED)
        font("B", 7, col)
        text(x, y, s)

    def change_txt(now_v: int, before: int) -> Tuple[str, Optional[bool]]:
        s = _change(now_v, before).replace(" vs previous week", " vs last week")
        return (("↑ " if s.startswith(("+", "new")) and s != "+0% vs last week" else "↓ " if s.startswith("-") else "") + s,
                True if s.startswith(("+", "new")) and not s.startswith("+0%") else (None if not s.startswith("-") else False))

    def logo(x: float, y: float, s: float) -> None:
        grad_box(x, y, s, s, ACC, ACC2, r=s * 0.28)
        pdf.set_draw_color(*BG)
        pdf.set_line_width(s * 0.07)
        k = s / 24
        pdf.polyline([(x + 5 * k, y + 5 * k), (x + 5 * k, y + 19 * k), (x + 19 * k, y + 19 * k)])
        pdf.polyline([(x + 8 * k, y + 15 * k), (x + 11.5 * k, y + 11 * k), (x + 14 * k, y + 13.5 * k), (x + 18 * k, y + 8 * k)])

    def footer(page: int) -> None:
        pdf.set_draw_color(*BORDER)
        pdf.set_line_width(0.25)
        pdf.line(L, H - 13, W - L, H - 13)
        font("", 6.8, FAINT)
        text(L, H - 11, f"Generated from Lead Overview on {datetime.now(UK).strftime('%d %b %Y, %H:%M')}."
                        " Totals and rates only; no individual companies are named.")
        text(W - L - 20, H - 11, f"Page {page} of {2 if ws.get('eng_detail') else 1}", 20, 5, "R")

    apps_order = list(APPS)

    # ================= PAGE 1: activity =================
    page_bg()
    logo(L, 13, 11)
    font("B", 6.8, ACC2, 0.9)
    pdf.set_fill_color(*GOOD)
    pdf.ellipse(L + 15, 14.6, 1.8, 1.8, "F")
    text(L + 18.5, 12.6, f"{_secret('REPORT_COMPANY', 'SY Communications').upper()} · SALES AUTOMATION")
    font("X", 21, TEXT, -0.3)
    text(L + 15, 18.6, "Weekly")
    x_sum = L + 15 + tw("Weekly ") + 0.5
    font("X", 21, (150, 158, 255), -0.3)
    text(x_sum, 18.6, "summary")
    font("", 8.4, MUTED)
    text(L, 29.5, _rng(ws).replace(" - ", " – ") + "   ·   Prospect Engine, Lead Revival, Customer Growth & MY PA")

    # Stepper pill (top right), like the page header
    pills = [(f"{ws['emails']:,}", "Emails", True), (f"{ws['leads']:,}", "New leads", False),
             (f"{ws['trials']:,}", "Trials", False)]
    font("B", 7.2)
    widths = []
    for v, lab, _a in pills:
        font("B", 7.2)
        widths.append(max(7, tw(v) + 4) + 2 + tw(lab) + 5)
    pw = sum(widths) + 2 * (len(pills) - 1) + 3
    px, py = W - L - pw, 13
    box(px, py, pw, 10, SURF, r=5, stroke=BORDER)
    xx = px + 1.5
    for (v, lab, act), wdt in zip(pills, widths):
        if act:
            box(xx, py + 1.3, wdt, 7.4, SURF3, r=3.7)
        font("B", 7.2)
        nw = max(7, tw(v) + 4)
        if act:
            grad_box(xx + 1, py + 2.2, nw, 5.6, ACC, ACC2, r=2.8)
        else:
            box(xx + 1, py + 2.2, nw, 5.6, SURF, r=2.8, stroke=BORDER2)
        font("X", 7, BG if act else TEXT)
        text(xx + 1, py + 2.5, v, nw, 5, "C")
        font("B", 7.2, TEXT if act else MUTED)
        text(xx + 2 + nw + 1, py + 2.5, lab)
        xx += wdt + 2

    pdf.set_draw_color(*BORDER)
    pdf.set_line_width(0.25)
    pdf.line(L, 38, W - L, 38)

    # Totals band: emails and new leads
    y = 43
    tw2 = (CW - 5) / 2
    for i, (title, now_v, prev_v, all_v) in enumerate([
            ("Emails sent", ws["emails"], ws["emails_prev"], ws["emails_all"]),
            ("New leads added to Zoho", ws["leads"], ws["leads_prev"], ws["leads_all"])]):
        x = L + i * (tw2 + 5)
        grad_box(x, y, tw2, 34, (30, 36, 72), (17, 34, 50), r=3.6)
        pdf.set_draw_color(58, 64, 120)
        pdf.set_line_width(0.3)
        pdf.rect(x, y, tw2, 34, "D", round_corners=True, corner_radius=3.6)
        font("B", 6.4, (185, 189, 255), 0.7)
        text(x + 6, y + 4.5, "ALL APPS")
        font("B", 10, TEXT)
        text(x + 6, y + 8.6, title)
        s, good = change_txt(now_v, prev_v)
        font("B", 7, MUTED)
        chip(x + tw2 - 6 - tw(s), y + 5, s, good)
        cx = x + 6
        for v, lab, main in [(f"{now_v:,}", "THIS WEEK", True), (f"{prev_v:,}", "LAST WEEK", False),
                             (f"{all_v:,}", "ALL TIME", False)]:
            font("X", 19 if main else 13, (170, 176, 255) if main else TEXT, -0.3)
            vw = tw(v)
            text(cx, y + (16 if main else 18.6), v, vw + 2, 8, "L")
            font("B", 5.6, MUTED, 0.5)
            lw = tw(lab)
            text(cx, y + 26.5, lab, lw + 2, 4, "L")
            cx += max(vw, lw) + 12
    y += 40

    # App tiles: coloured top edge = the app
    gap = 4
    aw = (CW - 3 * gap) / 4
    labels = {"Prospect Engine": "New prospects emailed", "Lead Revival": "Old leads re-contacted",
              "Customer Growth": "Customer emails", "MY PA": "Free trials offered"}
    for i, a in enumerate(ws["per_app"]):
        x = L + i * (aw + gap)
        col = _rgb(APPS[a["app"]])
        box(x, y, aw, 33, SURF, r=3.2, stroke=BORDER)
        box(x, y, aw, 1.6, col, r=0.8, corners=("TOP_LEFT", "TOP_RIGHT"))
        box(x + 5, y + 5.4, 2.4, 2.4, col, r=0.6)
        font("B", 6, MUTED, 0.5)
        text(x + 9, y + 4.6, a["app"].upper())
        font("B", 8.4, TEXT)
        text(x + 5, y + 9.4, labels.get(a["app"], ""))
        font("X", 19, TEXT, -0.4)
        text(x + 5, y + 15.5, f"{a['week']:,}")
        font("", 6.6, MUTED)
        s, good = change_txt(a["week"], a["prev"])
        chip(x + 5, y + 25.5, s, good)
        font("", 6.6, MUTED)
        text(x + aw - 25, y + 19.5, f"{a['all']:,} all time", 20, 4, "R")
    y += 39

    # Card 01: emails per day (stacked, rounded tops, surface gaps), like the dashboard chart
    card(y, 92)
    y0 = section("01", "Emails per day", "This week, by app. The number above each bar is the day's total.", y + 6)
    lx = L + CW - 6
    for app in reversed(apps_order):  # Legend, top right
        font("", 7.2, TEXT)
        wl = tw(app)
        lx -= wl
        text(lx, y + 7, app)
        box(lx - 4, y + 8.3, 2.6, 2.6, _rgb(APPS[app]), r=0.7)
        lx -= 9
    days = list(ws["daily"])
    top = max([sum(ws["daily"][d].values()) for d in days] + [1])
    step = max(1, int(round(top / 4 + 0.49)))
    nice_top = step * 4
    ch_x, ch_w, ch_top, ch_h = L + 16, CW - 24, y0 + 4, 52
    base = ch_top + ch_h
    for k in range(5):  # Gridlines + y labels
        yy = base - ch_h * k / 4
        pdf.set_draw_color(*(BORDER2 if k == 0 else (30, 40, 62)))
        pdf.set_line_width(0.3 if k == 0 else 0.2)
        pdf.line(ch_x, yy, ch_x + ch_w, yy)
        font("", 6.6, MUTED)
        text(ch_x - 10, yy - 2.5, f"{step * k:,}", 8, 5, "R")
    slot = ch_w / 7
    bw = slot * 0.5
    for i, d in enumerate(days):
        x = ch_x + i * slot + (slot - bw) / 2
        yy = base
        segs = [(app, ws["daily"][d][app]) for app in apps_order if ws["daily"][d][app]]
        for j, (app, n) in enumerate(segs):
            hh = ch_h * n / nice_top
            last = j == len(segs) - 1
            inner = max(hh - (0.5 if not last else 0), 0.4)  # 0.5mm surface gap between segments
            box(x, yy - hh + (0 if last else 0.5), bw, inner, _rgb(APPS[app]), r=1.3 if last else 0,
                corners=("TOP_LEFT", "TOP_RIGHT"))
            yy -= hh
        total = sum(n for _, n in segs)
        if total:
            font("B", 7.4, TEXT)
            text(x - 4, yy - 5, f"{total:,}", bw + 8, 4, "C")
        font("B" if d == ws.get("busiest") else "", 7, TEXT if d == ws.get("busiest") else MUTED)
        text(ch_x + i * slot, base + 2, d.strftime("%a %d"), slot, 4, "C")
    font("", 7, MUTED)
    if ws["busiest"]:
        text(L + 6, base + 9.5, f"Busiest day: {ws['busiest'].strftime('%A')} ({ws['busiest_n']:,} emails). "
                                f"Emails went out on {ws['active_days']} of the 7 days.")
    y += 98

    # Card 03 (page 1): highlights
    bullets = []
    if ws["emails"]:
        bullets.append(f"{round(ws['via_zoho'] / ws['emails'] * 100)}% of emails were sent straight from Zoho, so each one"
                       " is logged on the record.")
    if ws["sectors"]:
        bullets.append("Top sectors pitched: " + ", ".join(f"{k} ({v})" for k, v in ws["sectors"]) + ".")
    if ws["campaigns"]:
        bullets.append("Customer campaigns sent: " + ", ".join(f"{k} ({v})" for k, v in ws["campaigns"]) + ".")
    if ws["trials"]:
        bullets.append(f"{ws['trials']:,} businesses offered a free 1-week MY PA Connect trial.")
    if ws.get("eng"):
        bullets.append(eng_sentence(ws["eng"]))
    if not bullets:
        bullets.append("A quiet week: no emails went out.")
    ch = H - 18 - y
    card(y, ch)
    yb = section("02", "Highlights", "The week in a few lines.", y + 6)
    for b in bullets:
        if yb > y + ch - 8:
            break
        grad_box(L + 7, yb + 1.6, 1.8, 1.8, ACC, ACC2, r=0.9)
        font("", 8.4, TEXT)
        pdf.set_xy(L + 12, yb)
        pdf.multi_cell(CW - 20, 4.6, T(b), align="L")
        yb = pdf.get_y() + 2.2
    footer(1)

    # ================= PAGE 2: engagement =================
    ed = ws.get("eng_detail")
    if ed:
        page_bg()
        logo(L, 13, 9)
        font("B", 6.8, ACC2, 0.9)
        text(L + 12, 12.4, "ENGAGEMENT · FROM ZOHO EMAIL TRACKING")
        font("X", 15, TEXT, -0.2)
        text(L + 12, 17.6, "Opens, clicks & bounces")
        font("", 8, MUTED)
        text(L, 27, f"Emails sent from Zoho, {_rng(ws).replace(' - ', ' – ')}. Open and click rates are out of delivered emails.")
        pdf.set_draw_color(*BORDER)
        pdf.line(L, 34, W - L, 34)
        cur, prev = ed["cur"], ed.get("prev")

        def pts(a: Optional[float], b: Optional[float], lower_better: bool = False) -> Tuple[str, Optional[bool]]:
            if a is None or b is None or not prev or not prev["sent"]:
                return "", None
            diff = round((a - b) * 100)
            good = (diff < 0) if lower_better else (diff > 0)
            return (("↑ " if diff > 0 else "↓ " if diff < 0 else "") + f"{'+' if diff > 0 else ''}{diff} pts vs last week",
                    None if diff == 0 else good)

        y = 39
        tiles = [
            (f"{cur['sent']:,}", "Emails tracked", (f"{cur['delivered']:,} delivered", None), None),
            (pct(cur["open_rate"]), f"Open rate · {cur['opened']:,} opened", pts(cur["open_rate"], prev and prev["open_rate"]), OPEN_COL),
            (pct(cur["click_rate"]), f"Click rate · {cur['clicked']:,} clicked", pts(cur["click_rate"], prev and prev["click_rate"]), CLICK_COL),
            (pct(cur["bounce_rate"]), f"Bounce rate · {cur['bounced']:,} bounced",
             pts(cur["bounce_rate"], prev and prev["bounce_rate"], lower_better=True), None),
        ]
        tw4 = (CW - 3 * 4) / 4
        for i, (big, lab, (chg, good), col) in enumerate(tiles):
            x = L + i * (tw4 + 4)
            box(x, y, tw4, 27, SURF, r=3.2, stroke=BORDER)
            if col:
                box(x, y, tw4, 1.6, _rgb(col), r=0.8, corners=("TOP_LEFT", "TOP_RIGHT"))
            font("X", 19, TEXT, -0.4)
            text(x + 5, y + 4.5, big)
            font("", 7, MUTED)
            text(x + 5, y + 14, lab)
            if chg:
                chip(x + 5, y + 19.5, chg, good)
        y += 33

        # Two compact tables: by app, by brand
        def mini_table(x: float, yy: float, w: float, title: str, rows: List[Tuple[str, Dict[str, Any], Optional[str]]]) -> float:
            h = 15 + 7 * max(len(rows), 1) + 3
            box(x, yy, w, h, SURF, r=3.2, stroke=BORDER)
            font("B", 8.6, TEXT)
            text(x + 5, yy + 4, title)
            cols = [("Tracked", 15), ("Opened", 15), ("Clicked", 15), ("Bounced", 16)]
            hx = x + w - 5 - sum(c[1] for c in cols)
            font("B", 6, MUTED, 0.4)
            cx = hx
            for name, cwid in cols:
                text(cx, yy + 10, name.upper(), cwid, 4, "R")
                cx += cwid
            ry = yy + 15
            for name, r, col in rows:
                pdf.set_draw_color(*BORDER)
                pdf.set_line_width(0.2)
                pdf.line(x + 5, ry, x + w - 5, ry)
                if col:
                    pdf.set_fill_color(*_rgb(col))
                    pdf.ellipse(x + 5, ry + 2.4, 2.2, 2.2, "F")
                font("B", 7.8, TEXT)
                text(x + (9 if col else 5), ry + 1.2, name)
                vals = [f"{r['sent']:,}", pct(r["open_rate"]), pct(r["click_rate"]), f"{r['bounced']:,}"]
                cx = hx
                for (cname, cwid), v in zip(cols, vals):
                    font("B" if cname in ("Opened", "Clicked") else "", 7.8, TEXT)
                    text(cx, ry + 1.2, v, cwid, 5, "R")
                    cx += cwid
                ry += 7
            if not rows:
                font("", 7.5, MUTED)
                text(x + 5, ry + 1.2, "Nothing sent from Zoho this week.")
            return h

        half = (CW - 4) / 2
        h1 = mini_table(L, y, half, "By app", [(a, r, APPS[a]) for a, r in ed["per_app"]])
        h2 = mini_table(L + half + 4, y, half, "By brand", [(b, r, None) for b, r in ed["per_brand"]])
        y += max(h1, h2) + 6

        # Card: opens & clicks per day (lines with ringed markers)
        card(y, 84)
        y0 = section("03", "Opens and clicks per day", "By the day they happened, this week.", y + 6)
        lx = L + CW - 6
        for name, col in (("Clicked", CLICK_COL), ("Opened", OPEN_COL)):
            font("", 7.2, TEXT)
            lx -= tw(name)
            text(lx, y + 7, name)
            pdf.set_fill_color(*_rgb(col))
            pdf.ellipse(lx - 4, y + 8.3, 2.6, 2.6, "F")
            lx -= 9
        ddays = list(ed["daily"])
        dtop = max([max(v.values()) for v in ed["daily"].values()] + [1])
        dstep = max(1, int(round(dtop / 4 + 0.49)))
        dmax = dstep * 4
        ch_x, ch_w, ch_top, ch_h = L + 16, CW - 24, y0 + 4, 46
        base = ch_top + ch_h
        for k in range(5):
            yy = base - ch_h * k / 4
            pdf.set_draw_color(*(BORDER2 if k == 0 else (30, 40, 62)))
            pdf.set_line_width(0.3 if k == 0 else 0.2)
            pdf.line(ch_x, yy, ch_x + ch_w, yy)
            font("", 6.6, MUTED)
            text(ch_x - 10, yy - 2.5, f"{dstep * k:,}", 8, 5, "R")
        slot = ch_w / max(len(ddays), 1)
        for name, col in (("Opened", OPEN_COL), ("Clicked", CLICK_COL)):
            ptsl = [(ch_x + slot * (i + 0.5), base - ch_h * ed["daily"][d][name] / dmax) for i, d in enumerate(ddays)]
            pdf.set_draw_color(*_rgb(col))
            pdf.set_line_width(0.7)
            pdf.polyline(ptsl)
            for (px_, py_), d in zip(ptsl, ddays):
                pdf.set_fill_color(*SURF)
                pdf.ellipse(px_ - 1.6, py_ - 1.6, 3.2, 3.2, "F")
                pdf.set_fill_color(*_rgb(col))
                pdf.ellipse(px_ - 1.05, py_ - 1.05, 2.1, 2.1, "F")
        for i, d in enumerate(ddays):
            font("", 7, MUTED)
            text(ch_x + slot * i, base + 2, d.strftime("%a %d"), slot, 4, "C")
            n_o, n_c = ed["daily"][d]["Opened"], ed["daily"][d]["Clicked"]
            if n_o:
                font("B", 6.8, TEXT)
                text(ch_x + slot * (i + 0.5) - 6, base - ch_h * n_o / dmax - 6.2, f"{n_o}", 12, 4, "C")
        y += 90

        # Two call-outs: who to call, what to clean up
        for i, (big, lab, sub, col) in enumerate([
                (f"{ed['hot']:,}", "Hot leads to call", "Opened or clicked this week. Names and links are on the dashboard.", ACC),
                (f"{ed['bounces']:,}", "Bounced addresses", "Worth correcting in Zoho. The list is on the dashboard.", BAD)]):
            x = L + i * (half + 4)
            box(x, y, half, 24, SURF, r=3.2, stroke=BORDER)
            box(x + 4.5, y + 4.5, 1.3, 15, col, r=0.65)
            font("X", 20, TEXT, -0.4)
            text(x + 9, y + 4.5, big)
            bwid = tw(big)
            font("B", 9, TEXT)
            text(x + 12 + bwid, y + 6.5, lab)
            font("", 7.2, MUTED)
            pdf.set_xy(x + 9, y + 14.5)
            pdf.multi_cell(half - 14, 3.8, T(sub), align="L")
        y += 30
        font("", 7, FAINT)
        pdf.set_xy(L, y)
        pdf.multi_cell(CW, 3.8, T("Opens are a guide, not exact: some email apps load images automatically and others block"
                                  " them. Only emails sent with Send via Zoho are tracked. Figures come from the last"
                                  " Zoho check on the dashboard."), align="L")
        footer(2)

    out = pdf.output()
    return bytes(out) if not isinstance(out, str) else out.encode("latin-1", "replace")


# ==========================================
# Engagement: opens, clicks and bounces from Zoho's own email tracking (read only)
# ==========================================
ZOHO_SCOPE = ("ZohoCRM.modules.leads.READ,ZohoCRM.modules.contacts.READ,ZohoCRM.modules.accounts.READ,"
              "ZohoCRM.modules.emails.READ")
ENG_DAYS = 30    # sends from the last 30 days are checked
ENG_MAX = 1500   # newest sends checked per refresh, to go easy on Zoho's daily API allowance
OPEN_COL, CLICK_COL = "#9085e9", "#d55181"  # validated pair on the dark surface; not used for any app
# Brand names match Customer Growth's brands; anything else shows its email domain
BRAND_DOMAINS = (("syplus", "SY Plus"), ("southwales", "South Wales Comms"), ("swcomms", "South Wales Comms"),
                 ("sycomms", "SY Communications"), ("novalink", "Novalink"), ("mypaglobal", "MY PA"))


class ZohoError(RuntimeError):
    pass


@st.cache_resource
def _zoho_state_for(key: str) -> Dict[str, Any]:
    """Shared by everyone using the app: the sign-in and each record's emails (so Zoho is asked as little as possible).
    Keyed on the Zoho secrets, so changing them in Secrets starts afresh."""
    return {"token": "", "exp": 0.0, "api": "", "lock": threading.Lock(), "emails": {}}


_ZKEY = str(hash((_secret("ZOHO_CLIENT_ID"), _secret("ZOHO_REFRESH_TOKEN"))))


def _zoho_state() -> Dict[str, Any]:
    return _zoho_state_for(_ZKEY)


def zoho_configured() -> bool:
    return all(_secret(k) for k in ("ZOHO_CLIENT_ID", "ZOHO_CLIENT_SECRET", "ZOHO_REFRESH_TOKEN"))


def _accounts_url() -> str:
    return _secret("ZOHO_ACCOUNTS_URL", "https://accounts.zoho.eu").rstrip("/")


def zoho_token(force: bool = False, stt: Optional[Dict[str, Any]] = None) -> str:
    stt = stt or _zoho_state()
    with stt["lock"]:
        if stt["token"] and not force and stt["exp"] > time.time() + 60:
            return stt["token"]
        try:
            if not stt.get("creds"):  # Read on the page's own thread first; the background checks reuse it
                stt["creds"] = {"url": _accounts_url(), "refresh_token": _secret("ZOHO_REFRESH_TOKEN"),
                                "client_id": _secret("ZOHO_CLIENT_ID"), "client_secret": _secret("ZOHO_CLIENT_SECRET"),
                                "api": _secret("ZOHO_API_DOMAIN", "https://www.zohoapis.eu").rstrip("/")}
            cr = stt["creds"]
            resp = requests.post(f"{cr['url']}/oauth/v2/token", timeout=12, params={
                "refresh_token": cr["refresh_token"], "client_id": cr["client_id"],
                "client_secret": cr["client_secret"], "grant_type": "refresh_token"})
            data = resp.json()
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise ZohoError(f"Couldn't reach Zoho to sign in ({exc.__class__.__name__}).")
        if "access_token" not in data:
            raise ZohoError(f"KEY: Zoho sign-in failed ({data.get('error', 'unknown error')}). Check ZOHO_CLIENT_ID and"
                            " ZOHO_CLIENT_SECRET match Lead Revival's, then make a fresh key with the setup steps below.")
        stt["token"], stt["exp"] = data["access_token"], time.time() + int(data.get("expires_in", 3600))
        stt["api"] = str(data.get("api_domain") or cr["api"]).rstrip("/")
        return stt["token"]


def zoho_exchange_code(code: str) -> Dict[str, str]:
    """One-off setup: swaps a Self Client code for a refresh token. {'refresh_token': ...} or {'error': ...}."""
    try:
        resp = requests.post(f"{_accounts_url()}/oauth/v2/token", timeout=15, data={
            "grant_type": "authorization_code", "client_id": _secret("ZOHO_CLIENT_ID"),
            "client_secret": _secret("ZOHO_CLIENT_SECRET"), "code": code.strip()})
        data = resp.json()
    except (requests.exceptions.RequestException, ValueError) as exc:
        return {"error": f"Couldn't reach Zoho ({exc.__class__.__name__}). Try again in a moment."}
    if data.get("refresh_token"):
        return {"refresh_token": data["refresh_token"]}
    err = str(data.get("error") or f"HTTP {resp.status_code}")
    hint = {"invalid_code": "The code expired or was already used. Generate a fresh one and paste it straight in.",
            "invalid_client": "Zoho doesn't recognise ZOHO_CLIENT_ID. Copy it again from the Self Client.",
            "invalid_client_secret": "ZOHO_CLIENT_SECRET doesn't match the client ID. Copy it again."}.get(
        err, "Generate a fresh code and try again.")
    return {"error": f"Zoho said: {err}. {hint}"}


def record_emails(module: str, rid: str, stt: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Emails Zoho holds for one record (for an Account: those sent to any of its contacts).
    `stt` is passed in by the background checks, which can't reach the page's caches themselves."""
    stt = stt or _zoho_state()
    params: Dict[str, Any] = {"type": "all_contacts_sent_crm_emails"} if module == "Accounts" else {}
    out: List[Dict[str, Any]] = []
    for _page in range(5):  # 10 emails a page; 50 is plenty for one record
        resp = None
        for attempt in range(3):
            api = stt["api"] or (stt.get("creds") or {}).get("api") or "https://www.zohoapis.eu"
            try:
                resp = requests.get(f"{api}/crm/v8/{module}/{rid}/Emails", params=params, timeout=20,
                                    headers={"Authorization": f"Zoho-oauthtoken {zoho_token(attempt > 0 and resp is not None and resp.status_code == 401, stt)}"})
            except requests.exceptions.RequestException as exc:
                raise ZohoError(f"Couldn't reach Zoho CRM ({exc.__class__.__name__}).")
            if resp.status_code == 429:  # Too many at once: wait and try again
                time.sleep(2 + attempt * 2)
                continue
            if resp.status_code != 401:
                break
        if resp is None or resp.status_code == 204:
            break
        try:
            body = resp.json()
        except ValueError:
            body = {}
        if resp.status_code >= 400:
            code = str(body.get("code") or "")
            if code == "OAUTH_SCOPE_MISMATCH":
                raise ZohoError("KEY: This Zoho key can't read email tracking. It's probably the key copied from another"
                                " app. This app needs its own key: follow the setup steps below.")
            if code in ("NO_PERMISSION", "INVALID_TOKEN", "AUTHENTICATION_FAILURE"):
                raise ZohoError(f"KEY: Zoho turned the key down ({code}). Make this app its own key with the setup steps below.")
            if resp.status_code in (400, 404) and code in ("INVALID_DATA", "INVALID_URL_PATTERN", "NO_CONTENT", ""):
                return out  # Record deleted or merged since the email went out
            raise ZohoError(f"Zoho CRM error ({code or resp.status_code}): {body.get('message', '')}".strip())
        out += body.get("Emails") or body.get("email_related_list") or []
        info = body.get("info") or {}
        if not info.get("more_records") or not info.get("next_index"):
            break
        params = {**params, "index": info["next_index"]}
    return out


def engagement_sends(logs: Dict[str, Dict[str, Any]], since: datetime) -> List[Dict[str, Any]]:
    """Every email sent FROM ZOHO (so it's tracked) since `since`, with the Zoho record it was sent on."""
    out: List[Dict[str, Any]] = []

    def add(app: str, module: str, rid: Any, r: Dict[str, Any], firm: str) -> None:
        when = parse_when(r.get("sent_at"))
        rid = str(rid or "").strip()
        if not when or when < since or not rid.isdigit():
            return
        out.append({"app": app, "module": module, "id": rid, "sent": when, "firm": firm, "contact": r.get("contact") or "",
                    "to": str(r.get("to") or "").strip().lower(), "subject": r.get("subject") or "",
                    "brand": r.get("brand") or "", "from": str(r.get("from_address") or "").lower()})

    zl = logs.get("pe_zoho", {})
    for cn, r in logs.get("pe_sent", {}).items():
        if isinstance(r, dict) and r.get("via") == "zoho":
            z = zl.get(cn) or {}
            if z.get("status") != "customer":
                add("Prospect Engine", "Leads", z.get("id"), r, r.get("company_name") or cn)
    for key, r in logs.get("lr_sent", {}).items():
        if isinstance(r, dict) and r.get("via") == "zoho":
            add("Lead Revival", "Leads", key, r, r.get("company_name") or key)
    for key, r in logs.get("mp_sent", {}).items():
        if isinstance(r, dict) and r.get("via") == "zoho":
            add("MY PA", "Leads", key, r, r.get("company_name") or key)
    for key, r in logs.get("cg_sent", {}).items():
        if isinstance(r, dict) and r.get("via") == "zoho":
            add("Customer Growth", "Accounts", key, r, r.get("company_name") or key)
    for key, r in logs.get("cg_camp", {}).items():
        if isinstance(r, dict) and "|" in str(key):
            add("Customer Growth", "Contacts", str(key).split("|", 1)[1], r, r.get("account") or "")
    out.sort(key=lambda x: x["sent"], reverse=True)
    return out


def load_engagement(sends: List[Dict[str, Any]], force: bool = False, progress=None) -> Tuple[Dict[Tuple[str, str], List[Dict[str, Any]]], Optional[str]]:
    """Each record's emails from Zoho. Recent sends are re-checked every 20 minutes, older ones every 3 hours."""
    stt = _zoho_state()
    cache = stt["emails"]
    now_t = time.time()
    need: Dict[Tuple[str, str], float] = {}
    for s in sends:
        age_h = (datetime.now(UK) - s["sent"]).total_seconds() / 3600
        ttl = 1200 if age_h < 72 else 10800
        k = (s["module"], s["id"])
        need[k] = min(need.get(k, ttl), ttl)
    todo = [k for k, ttl in need.items() if force or k not in cache or now_t - cache[k][0] > ttl]
    err: Optional[str] = None
    if todo:
        try:
            zoho_token()
            first = todo[0]  # One on its own first: a permission problem then stops everything straight away
            cache[first] = (time.time(), record_emails(*first, stt=stt))
        except ZohoError as exc:
            return {k: cache[k][1] for k in need if k in cache}, str(exc)
        stop = threading.Event()
        failures: List[str] = []

        def one(k: Tuple[str, str]) -> Tuple[Tuple[str, str], Optional[List[Dict[str, Any]]], Optional[str]]:
            if stop.is_set():
                return k, None, None
            try:
                return k, record_emails(*k, stt=stt), None
            except ZohoError as exc:
                return k, None, str(exc)

        rest = todo[1:]
        with ThreadPoolExecutor(max_workers=6) as pool:
            for n, (k, emails, e) in enumerate(pool.map(one, rest), 1):
                if emails is not None:
                    cache[k] = (time.time(), emails)
                elif e:
                    failures.append(e)
                    if len(failures) >= 10:
                        stop.set()
                if progress and (n % 10 == 0 or n == len(rest)):
                    progress(n / max(len(rest), 1), f"Checking Zoho · {n:,} of {len(rest):,} records")
        if failures:
            err = f"{len(failures):,} records couldn't be checked. Last error: {failures[-1]}"
    return {k: cache[k][1] for k in need if k in cache}, err


# ---- Saved engagement: the last Zoho check is kept in GitHub, so the page never has to ask Zoho on load ----
def _eng_store() -> Tuple[str, str, str]:
    repo = _secret("ENG_GITHUB_REPO", _secret("GITHUB_REPO"))
    token = _clean_token(_secret("ENG_GITHUB_TOKEN") or _secret("GITHUB_TOKEN"))
    return repo, _secret("GITHUB_ENGAGEMENT_PATH", "engagement_cache.json"), token


def load_saved_engagement() -> Tuple[Dict[str, Any], str]:
    """(saved data, status) from GitHub. Data: {"checked_at", "checked_by", "records": {"Leads/123": {"t", "emails"}}}."""
    if "eng_saved" in st.session_state:  # Just saved in this visit: use it straight away
        return st.session_state["eng_saved"], "ok"
    repo, path, token = _eng_store()
    return _fetch_log(repo, path, _secret("GITHUB_BRANCH", "main"), token)


def _slim(e: Dict[str, Any]) -> Dict[str, Any]:
    """Only what the dashboard needs from each Zoho email, to keep the saved file small."""
    return {"subject": e.get("subject") or "", "time": e.get("time") or e.get("sent_time") or "",
            "to": [{"email": str(x.get("email") or "")} for x in (e.get("to") or []) if isinstance(x, dict)],
            "from": {"email": str(((e.get("from") or {}) if isinstance(e.get("from"), dict) else {}).get("email") or "")},
            "status": [x for x in (e.get("status") or []) if isinstance(x, dict)]}


def save_engagement(data: Dict[str, Any]) -> Optional[str]:
    """Writes the saved check to GitHub. Returns None, or a plain-English error."""
    repo, path, token = _eng_store()
    if not (repo and token):
        return "GITHUB_REPO / GITHUB_TOKEN aren't set, so the check can't be saved."
    url = f"https://api.github.com/repos/{repo}/contents/{path}"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    branch = _secret("GITHUB_BRANCH", "main")
    content = base64.b64encode(json.dumps(data, separators=(",", ":")).encode("utf-8")).decode("ascii")
    try:
        for _attempt in range(3):
            cur = requests.get(url, headers=headers, params={"ref": branch}, timeout=15)
            body = {"message": f"Lead Overview: engagement checked ({data.get('checked_at', '')[:16]})",
                    "content": content, "branch": branch}
            if cur.status_code == 200:
                body["sha"] = cur.json().get("sha")
            resp = requests.put(url, headers=headers, json=body, timeout=30)
            if resp.status_code in (200, 201):
                return None
            if resp.status_code not in (409, 422):  # 409/422: someone saved at the same moment; try again
                break
    except requests.exceptions.RequestException as exc:
        return f"Couldn't reach GitHub ({exc.__class__.__name__})."
    return {401: "GitHub rejected the token (401).",
            403: "The GitHub token can only read. Give it Contents: Read and write on the repo (or add ENG_GITHUB_TOKEN)",
            404: "GitHub can't see that repo with this token (404)."}.get(resp.status_code, f"GitHub error {resp.status_code}.")


def _norm(t: Any) -> str:
    return " ".join(str(t or "").lower().split())


def match_email(send: Dict[str, Any], emails: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """The Zoho email that is this send: same recipient, then same subject, then nearest in time (within 3 days)."""
    to = send["to"]
    pool = [e for e in emails if any(str((x or {}).get("email", "")).lower() == to for x in (e.get("to") or []))] if to else []
    if not pool and send["module"] != "Accounts":
        pool = emails
    subj = _norm(send["subject"])
    best, best_score = None, None
    for e in pool:
        et = parse_when(e.get("time") or e.get("sent_time"))
        gap = abs((et - send["sent"]).total_seconds()) if et else 10 ** 9
        same = bool(subj) and _norm(e.get("subject")) == subj
        if not same and gap > 3 * 86400:
            continue
        score = (0 if same else 1, gap)
        if best_score is None or score < best_score:
            best, best_score = e, score
    return best


def email_signals(e: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    out = {"Opened": False, "Opens": 0, "First open": None, "Last open": None, "Clicked": False, "Clicks": 0,
           "Last click": None, "Bounced": False, "Bounced at": None, "Reason": ""}
    for s in (e or {}).get("status") or []:
        if not isinstance(s, dict):
            continue
        typ = str(s.get("type", "")).lower()
        times = [parse_when(v) for k, v in s.items() if k != "type" and isinstance(v, str) and
                 any(w in k for w in ("time", "open", "click"))]
        times = [t for t in times if t]
        cnt = int(s["count"]) if str(s.get("count", "")).isdigit() else 0
        if "open" in typ and "unopen" not in typ:
            out["Opened"], out["Opens"] = True, max(out["Opens"], cnt or 1)
            out["First open"] = parse_when(s.get("first_open")) or (min(times) if times else None)
            out["Last open"] = parse_when(s.get("last_open")) or (max(times) if times else None)
        elif "click" in typ:
            out["Clicked"], out["Clicks"] = True, max(out["Clicks"], cnt or 1)
            out["Last click"] = max(times) if times else None
        elif "bounce" in typ:
            out["Bounced"] = True
            out["Bounced at"] = parse_when(s.get("bounced_time")) or (max(times) if times else None)
            out["Reason"] = " · ".join(str(x) for x in (s.get("category"), s.get("bounced_reason")) if x)
    if out["Clicked"] and not out["Opened"]:  # A click means it was opened, even if the image didn't load
        out["Opened"], out["Opens"] = True, 1
    return out


def brand_of(send: Dict[str, Any], e: Optional[Dict[str, Any]]) -> str:
    if send["app"] == "MY PA":
        return "MY PA"
    if send.get("brand"):
        return str(send["brand"])
    addr = send.get("from") or str(((e or {}).get("from") or {}).get("email") or "").lower()
    dom = addr.split("@")[-1] if "@" in addr else ""
    return next((name for word, name in BRAND_DOMAINS if word in dom), dom or "Unknown")


def build_engagement(sends: List[Dict[str, Any]], emails: Dict[Tuple[str, str], List[Dict[str, Any]]]) -> pd.DataFrame:
    rows = []
    for s in sends:
        k = (s["module"], s["id"])
        if k not in emails:
            continue  # Not checked (yet)
        e = match_email(s, emails[k])
        sig = email_signals(e)
        seen = [t for t in (sig["Last open"], sig["Last click"]) if t]
        rows.append({"Sent": s["sent"], "App": s["app"], "Brand": brand_of(s, e), "Firm": s["firm"], "Contact": s["contact"],
                     "Email": s["to"], "Subject": s["subject"], "Found": e is not None, "Last seen": max(seen) if seen else None,
                     "Zoho": zoho_url(s["module"], s["id"]), "Record": f"{s['module']}/{s['id']}", **sig})
    cols = ["Sent", "App", "Brand", "Firm", "Contact", "Email", "Subject", "Found", "Opened", "Opens", "First open",
            "Last open", "Clicked", "Clicks", "Last click", "Bounced", "Bounced at", "Reason", "Last seen", "Zoho", "Record"]
    return pd.DataFrame(rows, columns=cols)


def eng_rates(df: pd.DataFrame) -> Dict[str, Any]:
    """Rates over the emails found in Zoho. Opens and clicks are out of delivered (sent minus bounced)."""
    found = df[df["Found"]] if not df.empty else df
    n = len(found)
    b = int(found["Bounced"].sum()) if n else 0
    o = int(found["Opened"].sum()) if n else 0
    c = int(found["Clicked"].sum()) if n else 0
    delivered = n - b
    return {"sent": n, "opened": o, "clicked": c, "bounced": b, "delivered": delivered,
            "open_rate": o / delivered if delivered else None, "click_rate": c / delivered if delivered else None,
            "bounce_rate": b / n if n else None}


def pct(v: Optional[float]) -> str:
    return "–" if v is None else (f"{v * 100:.1f}%" if 0 < v < 0.1 else f"{round(v * 100)}%")



# ==========================================
# Load
# ==========================================
hero_slot = st.empty()
branch = _secret("GITHUB_BRANCH", "main")
sources = source_list()
logs: Dict[str, Dict[str, Any]] = {}
status: Dict[str, str] = {}
with st.spinner("Reading the apps' logs…"):
    for s in sources:
        logs[s["key"]], status[s["key"]] = fetch_log(s["repo"], s["path"], branch, s["tok"])
events = build_events(logs)

now = datetime.now(UK)
today = now.date()


def on_day(d: Optional[datetime], day: date) -> bool:
    return bool(d) and d.date() == day


def count(app: str, activities: List[str], day: Optional[date] = None) -> int:
    if events.empty:
        return 0
    m = (events["App"] == app) & (events["Activity"].isin(activities))
    if day:
        m &= events["When"].apply(lambda d: on_day(d, day))
    return int(m.sum())


EMAIL_ACTS = ["Emailed", "Upsell email", "Campaign email", "Trial offered"]

# ---------------- Sidebar ----------------
with st.sidebar:
    render_html(f'<div class="pe-brand"><div class="pe-logo">{ICON_CHART}</div>'
                f'<div><div class="n">{APP_NAME}</div><div class="s">{APP_TAGLINE}</div></div></div>')
    render_html('<div class="pe-side-h">Data sources</div>')
    rows_html = []
    for s in sources:
        stt = status[s["key"]]
        n = len(logs[s["key"]])
        if stt == "ok":
            badge = f'<span class="st ok">{n:,} records</span>'
        elif stt == "missing":
            badge = '<span class="st idle">Nothing yet</span>'
        elif stt == "no_access":
            badge = '<span class="st off">Can\'t see repo</span>'
        else:
            badge = f'<span class="st off">{esc(stt)}</span>'
        rows_html.append(f'<div class="pe-status"><span>{esc(s["label"])}</span>{badge}</div>')
    render_html("".join(rows_html))
    blocked = [s for s in sources if status[s["key"]] == "no_access"]
    if blocked:
        apps_b = sorted({s["app"] for s in blocked})
        st.caption("⚠️ The token can't see the repo for " + " and ".join(apps_b) + ". Either add that app's repo with "
                   + ", ".join({"Prospect Engine": "PE_GITHUB_REPO", "Lead Revival": "LR_GITHUB_REPO",
                                "Customer Growth": "CG_GITHUB_REPO"}[a] for a in apps_b)
                   + " (and its token with the matching _GITHUB_TOKEN), or give this token access to that repo.")
    errors = [s for s in sources if status[s["key"]] not in ("ok", "missing", "no_access")]
    if errors:
        st.caption("⚠️ Check the GitHub token and repo in Secrets for: " + ", ".join(sorted({s['app'] for s in errors})))
    if any(status[s["key"]] == "missing" for s in sources):
        st.caption("'Nothing yet': the repo is fine but that app hasn't saved that file there yet. Check the app has"
                   " GITHUB_TOKEN and GITHUB_REPO in its own Secrets, and that it's the same repo shown here.")
    st.caption(f"Updated {now.strftime('%H:%M')}. Refreshes every 5 minutes.")
    if st.button("↻ Refresh now", **FULL_WIDTH):
        _fetch_log.clear()
        st.session_state.pop("eng_saved", None)
        st.rerun()
    if not _secret("ZOHO_ORG"):
        st.caption("💡 Add ZOHO_ORG to Secrets (the bit after /crm/ in your Zoho address, e.g. org20123456) so Zoho links"
                   " always open in the right organisation.")
    st.write("")
    if st.button("Log out", **FULL_WIDTH):
        st.session_state.clear()
        st.rerun()

# ---------------- Hero ----------------
emails_today = int((events["Activity"].isin(EMAIL_ACTS) & events["When"].apply(lambda d: on_day(d, today))).sum()) if not events.empty else 0
week_start = today - timedelta(days=today.weekday())
emails_week = int((events["Activity"].isin(EMAIL_ACTS) & events["When"].apply(lambda d: bool(d) and d.date() >= week_start)).sum()) if not events.empty else 0
emails_all = int(events["Activity"].isin(EMAIL_ACTS).sum()) if not events.empty else 0
pills = [(emails_today, "Emails today", "active"), (emails_week, "This week", ""), (emails_all, "All time", "")]
render_html(
    '<div class="pe-hero"><div>'
    f'<div class="pe-eyebrow"><span class="dot"></span>Live from all four apps · {esc(now.strftime("%A %d %B"))}</div>'
    '<div class="pe-title">Lead <span>overview</span></div>'
    '<div class="pe-sub">Every new lead and email from Prospect Engine, Lead Revival, Customer Growth and MY PA, in one place.'
    ' Click any row\'s Zoho link to open the record.</div></div>'
    '<div class="pe-stepper">'
    + '<div class="pe-step-sep"></div>'.join(f'<div class="pe-step {c}"><span class="num">{v:,}</span>{esc(t)}</div>' for v, t, c in pills)
    + "</div></div>",
    target=hero_slot,
)

# ---------------- KPI tiles ----------------
pe_added_total, pe_added_today = count("Prospect Engine", ["Added to Zoho"]), count("Prospect Engine", ["Added to Zoho"], today)
pe_em_total, pe_em_today = count("Prospect Engine", ["Emailed"]), count("Prospect Engine", ["Emailed"], today)
lr_total, lr_today = count("Lead Revival", ["Emailed"]), count("Lead Revival", ["Emailed"], today)
cg_up, cg_camp = count("Customer Growth", ["Upsell email"]), count("Customer Growth", ["Campaign email"])
cg_total, cg_today = cg_up + cg_camp, count("Customer Growth", ["Upsell email", "Campaign email"], today)
mp_total, mp_today = count("MY PA", ["Trial offered"]), count("MY PA", ["Trial offered"], today)


def kpi(app: str, label: str, today_v: int, total_v: int, foot: str, single: bool = False) -> str:
    body = (f'<div class="row"><div><div class="v big">{today_v:,}</div><div class="k">Today</div></div>'
            f'<div><div class="v">{total_v:,}</div><div class="k">Total</div></div></div>')
    return (f'<div class="lo-kpi" style="--c:{APPS[app]}"><div class="app"><i></i>{esc(app)}</div>'
            f'<div class="l">{esc(label)}</div>{body}<div class="foot">{esc(foot)}</div></div>')


_all_em = events[events["Activity"].isin(EMAIL_ACTS)] if not events.empty else events
_all_new = events[events["Activity"] == "Added to Zoho"] if not events.empty else events
_last7 = today - timedelta(days=6)


def _n(df_: pd.DataFrame, since: Optional[date] = None, only_day: Optional[date] = None) -> int:
    if df_.empty:
        return 0
    dd = df_["When"].apply(lambda x: x.date() if x else None)
    if only_day:
        return int((dd == only_day).sum())
    if since:
        return int(dd.apply(lambda x: bool(x) and x >= since).sum())
    return len(df_)


def total_card(title: str, sub: str, df_: pd.DataFrame) -> str:
    return (f'<div class="lo-total"><div class="t">{esc(title)}<b>{esc(sub)}</b></div>'
            f'<div class="n"><div class="v">{_n(df_, only_day=today):,}</div><div class="k">Today</div></div>'
            f'<div class="n"><div class="v">{_n(df_, since=_last7):,}</div><div class="k">Last 7 days</div></div>'
            f'<div class="n main"><div class="v">{_n(df_):,}</div><div class="k">All time</div></div></div>')


render_html('<div class="lo-totals">'
            + total_card("All apps", "Emails sent", _all_em)
            + total_card("All apps", "New leads added to Zoho", _all_new)
            + "</div>")

render_html(
    '<div class="lo-kpis">'
    + kpi("Prospect Engine", "New prospects added to Zoho", pe_added_today, pe_added_total,
          "New leads only. Firms already in Zoho aren't counted.")
    + kpi("Prospect Engine", "New prospects emailed", pe_em_today, pe_em_total, "Pitch emails to new firms")
    + kpi("Lead Revival", "Lead revivals emailed", lr_today, lr_total, "Old Zoho leads re-contacted")
    + kpi("Customer Growth", "Customer growth emails", cg_today, cg_total, f"{cg_up:,} upsell · {cg_camp:,} campaign")
    + kpi("MY PA", "Free trials offered", mp_today, mp_total, "MY PA Connect free 1-week trial emails")
    + "</div>"
)

if events.empty:
    with st.container(key="card-empty"):
        render_html(
            f'<div class="pe-empty"><div style="color:var(--accent-2);display:inline-block;padding:18px;border-radius:20px;'
            f'background:rgba(56,214,245,.1);border:1px solid rgba(56,214,245,.3)">{ICON_CHART}</div>'
            '<div class="t">No activity found yet</div>'
            '<div class="s">The dashboard fills up as soon as the apps save their first emails to GitHub.</div>'
            "<ol><li>Add GITHUB_TOKEN and GITHUB_REPO to this app's Secrets</li>"
            "<li>Use the same repos the apps save to</li><li>Hit Refresh now in the sidebar</li></ol></div>")
    st.stop()

# ---------------- Chart: emails per day ----------------
with st.container(key="card-chart"):
    section_header("01", "Emails per day", "Last 14 days, by app. Hover a bar for the numbers.")
    start = today - timedelta(days=13)
    em = events[events["Activity"].isin(EMAIL_ACTS) & events["When"].notna()].copy()
    em["Day"] = em["When"].apply(lambda d: d.date())
    em = em[em["Day"] >= start]
    grid = pd.MultiIndex.from_product([[start + timedelta(days=i) for i in range(14)], list(APPS)], names=["Day", "App"])
    daily = em.groupby(["Day", "App"]).size().reindex(grid, fill_value=0).reset_index(name="Emails")
    daily["Date"] = pd.to_datetime(daily["Day"])
    daily["Label"] = daily["Date"].dt.strftime("%a %d %b")
    chart = (
        alt.Chart(daily)
        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, stroke="#111827", strokeWidth=2)
        .encode(
            x=alt.X("Label:N", sort=list(daily.drop_duplicates("Label")["Label"]), title=None,
                    axis=alt.Axis(labelAngle=0, labelColor="#8C98B0", labelFontSize=11, domainColor="#2A3550", ticks=False,
                                  labelExpr="split(datum.label, ' ')[0] + ' ' + split(datum.label, ' ')[1]")),
            y=alt.Y("Emails:Q", title=None, stack="zero",
                    axis=alt.Axis(labelColor="#8C98B0", gridColor="#1F2A40", domain=False, ticks=False, tickMinStep=1)),
            color=alt.Color("App:N", scale=alt.Scale(domain=list(APPS), range=list(APPS.values())),
                            legend=alt.Legend(orient="top", title=None, labelColor="#E7EAF3", symbolType="square")),
            order=alt.Order("App:N"),
            tooltip=[alt.Tooltip("Label:N", title="Day"), alt.Tooltip("App:N"), alt.Tooltip("Emails:Q")],
        )
        .properties(height=240, background="transparent")
        .configure_view(strokeWidth=0)
        .configure(font="Inter")
    )
    try:
        st.altair_chart(chart, width="stretch")
    except Exception:
        st.altair_chart(chart, use_container_width=True)

# ---------------- Engagement: opens, clicks, bounces ----------------
eng_df: Optional[pd.DataFrame] = None


def _table(df_: pd.DataFrame, **kw) -> None:
    try:
        st.dataframe(df_, width="stretch", hide_index=True, **kw)
    except Exception:
        st.dataframe(df_, use_container_width=True, hide_index=True, **kw)


def _when(d: Any) -> str:
    if d is None or (isinstance(d, float) and pd.isna(d)) or pd.isna(d):
        return ""
    return d.strftime("Today %H:%M") if d.date() == today else d.strftime("%a %d %b %H:%M")


def render_zoho_connect() -> None:
    have_client = bool(_secret("ZOHO_CLIENT_ID") and _secret("ZOHO_CLIENT_SECRET"))
    render_html('<div style="font-size:.9rem;line-height:1.6;color:var(--muted)">'
                "See who opened, clicked or bounced, straight from Zoho's own email tracking (the same data behind"
                " Zoho Signals). One-off setup, read-only: this app can't change anything in Zoho.</div>")
    if not have_client:
        st.info("Add **ZOHO_CLIENT_ID** and **ZOHO_CLIENT_SECRET** to this app's Secrets (copy them from Lead Revival's"
                " Secrets), save, then come back here to finish connecting.")
        return
    render_html('<div style="font-size:.86rem;line-height:1.6;color:var(--muted);margin-top:8px">'
                "<b>1.</b> In <b>api-console.zoho.eu</b>, open the Self Client and go to <b>Generate Code</b>.<br>"
                "<b>2.</b> Paste the scope below, pick <b>10 minutes</b>, add any description and click <b>Create</b>.<br>"
                "<b>3.</b> Copy the code (starts <b>1000.</b>), paste it here and click Connect. Be quick: codes expire.</div>")
    st.code(ZOHO_SCOPE, language=None)
    with st.form("zoho_setup", border=False):
        z1, z2 = columns([2.2, 1])
        code = z1.text_input("Code from Zoho", type="password", placeholder="1000.xxxxxxxx…")
        go = z2.form_submit_button("Connect Zoho", type="primary", **FULL_WIDTH)
    if go:
        if not code.strip():
            st.warning("Paste the code from Zoho first.")
        else:
            with st.spinner("Asking Zoho for a permanent key…"):
                st.session_state["zoho_setup_result"] = zoho_exchange_code(code)
    res = st.session_state.get("zoho_setup_result") or {}
    if res.get("error"):
        st.error(res["error"])
    elif res.get("refresh_token"):
        st.success("Connected. Last step: copy this line into this app's Streamlit Secrets, save, then reboot the app.")
        st.code(f'ZOHO_REFRESH_TOKEN = "{res["refresh_token"]}"', language=None)
        st.caption("It's shown only here and isn't saved anywhere else, so don't share it in emails or chats.")


with st.container(key="card-eng"):
    section_header("02", "Engagement", "Opens, clicks and bounces on emails sent from Zoho, with who to call first.")
    if not zoho_configured():
        render_zoho_connect()
    else:
        e1, e2, e3 = columns([1.3, 1.6, 1])
        eng_period = e1.radio("Period", ["Last 7 days", "Last 30 days"], horizontal=True, key="eng_period")
        pick_eng_apps = e2.multiselect("App", list(APPS), default=[], placeholder="All apps", key="eng_apps")
        recheck = e3.button("↻  Check Zoho now", key="eng_recheck", **FULL_WIDTH,
                            help="Reads the latest opens, clicks and bounces from Zoho and saves them for everyone."
                                 " Takes a minute or so.")
        sends = engagement_sends(logs, datetime.now(UK) - timedelta(days=ENG_DAYS))
        capped = len(sends) > ENG_MAX
        sends = sends[:ENG_MAX]
        saved, saved_status = load_saved_engagement()
        records: Dict[str, Any] = dict(saved.get("records") or {})
        eng_err: Optional[str] = None
        if recheck:  # Only ever asks Zoho when the button is clicked
            bar = st.empty()

            def _prog(frac: float, text: str) -> None:
                bar.progress(min(frac, 1.0), text=text)

            with st.spinner(f"Checking {len({(x['module'], x['id']) for x in sends}):,} records in Zoho…"):
                fresh, eng_err = load_engagement(sends, force=True, progress=_prog)
            bar.empty()
            if fresh:
                stamp = time.time()
                for (m, i), em in fresh.items():
                    records[f"{m}/{i}"] = {"t": stamp, "emails": [_slim(e) for e in em]}
                keep = {f"{x['module']}/{x['id']}" for x in sends}  # Drop records older than the 30 days
                records = {k: v for k, v in records.items() if k in keep}
                new_saved = {"checked_at": datetime.now(UK).isoformat(timespec="seconds"),
                             "checked_by": st.session_state.get("eng_who", ""), "records": records}
                st.session_state["eng_saved"] = new_saved
                save_err = save_engagement(new_saved)
                _fetch_log.clear()
                if save_err:
                    st.warning(f"Checked, but not saved to GitHub: {save_err}. It shows until you leave the page.")
                else:
                    st.success(f"Checked {len(fresh):,} records in Zoho and saved for everyone.")
                saved = new_saved
        key_problem = bool(eng_err and "KEY: " in eng_err)
        if eng_err:
            (st.error if key_problem else st.warning)(eng_err.replace("KEY: ", ""))
        # Set up or renew this app's own Zoho key; opens by itself when the key is the problem
        with st.expander("🔑  Zoho key: set up or renew", expanded=key_problem):
            render_zoho_connect()
        eng_emails = {tuple(k.split("/", 1)): v.get("emails") or [] for k, v in records.items()
                      if isinstance(v, dict) and "/" in k}
        eng_df = build_engagement(sends, eng_emails)
        checked_at = parse_when(saved.get("checked_at"))
        unchecked = len({(x["module"], x["id"]) for x in sends} - set(eng_emails))
        if saved_status not in ("ok", "missing"):
            st.caption(f"⚠️ Couldn't read the saved check from GitHub ({saved_status}).")
        if checked_at:
            st.caption(f"Last checked in Zoho: {_when(checked_at)}"
                       + (f" · {unchecked:,} newer send{'s' if unchecked != 1 else ''} not checked yet."
                          " Click Check Zoho now to include them." if unchecked else " · up to date with every send."))
        if not sends:
            st.info("No emails sent from Zoho in the last 30 days yet. Only emails sent with the apps' **Send via Zoho**"
                    " button are tracked; drafts opened in Outlook aren't.")
        elif eng_df.empty:
            st.info("Not checked yet. Click **Check Zoho now** to read opens, clicks and bounces from Zoho. It takes a"
                    " minute or so, then it's saved, so the page opens instantly after that.")
        else:
            span = 7 if eng_period == "Last 7 days" else 30
            p_start = today - timedelta(days=span - 1)
            view_e = eng_df[eng_df["App"].isin(pick_eng_apps)] if pick_eng_apps else eng_df
            sent_day = view_e["Sent"].apply(lambda x: x.date())
            cur_e = view_e[sent_day >= p_start]
            r = eng_rates(cur_e)
            prev_r = eng_rates(view_e[(sent_day < p_start) & (sent_day >= p_start - timedelta(days=7))]) if span == 7 else None

            def _cmp(now_v: Optional[float], before: Optional[float], lower_better: bool = False) -> str:
                if prev_r is None or now_v is None or before is None or not prev_r["sent"]:
                    return '<div class="d flat">&nbsp;</div>'
                diff = round((now_v - before) * 100)
                good = (diff < 0) if lower_better else (diff > 0)
                return (f'<div class="d {"up" if good else "flat"}">{"+" if diff >= 0 else ""}{diff} pts vs previous week</div>')

            render_html(
                '<div class="lo-week">'
                f'<div class="c"><div class="v">{r["sent"]:,}</div><div class="l">Emails tracked</div>'
                f'<div class="d flat">{r["delivered"]:,} delivered</div></div>'
                f'<div class="c"><div class="v">{pct(r["open_rate"])}</div><div class="l">Open rate · {r["opened"]:,} opened</div>'
                f'{_cmp(r["open_rate"], prev_r and prev_r["open_rate"])}</div>'
                f'<div class="c"><div class="v">{pct(r["click_rate"])}</div><div class="l">Click rate · {r["clicked"]:,} clicked</div>'
                f'{_cmp(r["click_rate"], prev_r and prev_r["click_rate"])}</div>'
                f'<div class="c"><div class="v">{pct(r["bounce_rate"])}</div><div class="l">Bounce rate · {r["bounced"]:,} bounced</div>'
                f'{_cmp(r["bounce_rate"], prev_r and prev_r["bounce_rate"], lower_better=True)}</div>'
                "</div>"
            )
            missing = int((~cur_e["Found"]).sum())
            st.caption(f"{eng_period}, by the day each email was sent. Open and click rates are out of delivered emails."
                       " Opens are a guide, not exact: some email apps open images automatically, others block them."
                       + (f" {missing:,} send{'s' if missing != 1 else ''} couldn't be matched in Zoho (record deleted or merged), so"
                          + (" they're" if missing != 1 else " it's") + " left out." if missing else "")
                       + (f" Only the newest {ENG_MAX:,} sends are checked." if capped else ""))

            # By app and by brand
            def _breakdown(col: str, order: Optional[List[str]] = None) -> pd.DataFrame:
                out = []
                keys = order or sorted(cur_e[col].dropna().unique(), key=str.lower)
                for k in keys:
                    rr = eng_rates(cur_e[cur_e[col] == k])
                    if rr["sent"]:
                        out.append({col: k, "Tracked": rr["sent"], "Opened": pct(rr["open_rate"]),
                                    "Clicked": pct(rr["click_rate"]), "Bounced": f'{rr["bounced"]:,} ({pct(rr["bounce_rate"])})'})
                return pd.DataFrame(out, columns=[col, "Tracked", "Opened", "Clicked", "Bounced"])

            b1, b2 = st.columns(2)
            with b1:
                st.markdown("**By app**")
                by_app = _breakdown("App", list(APPS))
                by_app["App"] = by_app["App"].map({"Prospect Engine": "🔵 Prospect Engine", "Lead Revival": "🟠 Lead Revival",
                                                   "Customer Growth": "🟢 Customer Growth", "MY PA": "🟡 MY PA"})
                _table(by_app)
            with b2:
                st.markdown("**By brand** (the From address)")
                _table(_breakdown("Brand"))

            # Trend: first opens and clicks per day
            st.markdown(f"**Opens and clicks per day** · {eng_period.lower()}, by the day they happened")
            days = [p_start + timedelta(days=i) for i in range(span)]
            ev_rows = []
            for _, row in view_e.iterrows():
                if row["First open"] is not None and not pd.isna(row["First open"]):
                    ev_rows.append({"Day": row["First open"].date(), "Signal": "Opened"})
                if row["Last click"] is not None and not pd.isna(row["Last click"]):
                    ev_rows.append({"Day": row["Last click"].date(), "Signal": "Clicked"})
            evd = pd.DataFrame(ev_rows, columns=["Day", "Signal"])
            grid = pd.MultiIndex.from_product([days, ["Opened", "Clicked"]], names=["Day", "Signal"])
            trend = evd.groupby(["Day", "Signal"]).size().reindex(grid, fill_value=0).reset_index(name="Emails")
            trend["Label"] = pd.to_datetime(trend["Day"]).dt.strftime("%a %d %b")
            base = alt.Chart(trend).encode(
                x=alt.X("Label:N", sort=[d.strftime("%a %d %b") for d in days], title=None,
                        axis=alt.Axis(labelAngle=0, labelColor="#8C98B0", labelFontSize=11, domainColor="#2A3550", ticks=False,
                                      labelOverlap=True,
                                      labelExpr="split(datum.label, ' ')[0] + ' ' + split(datum.label, ' ')[1]")),
                y=alt.Y("Emails:Q", title=None, axis=alt.Axis(labelColor="#8C98B0", gridColor="#1F2A40", domain=False,
                                                              ticks=False, tickMinStep=1)),
                color=alt.Color("Signal:N", scale=alt.Scale(domain=["Opened", "Clicked"], range=[OPEN_COL, CLICK_COL]),
                                legend=alt.Legend(orient="top", title=None, labelColor="#E7EAF3", symbolType="circle")),
                tooltip=[alt.Tooltip("Label:N", title="Day"), alt.Tooltip("Signal:N"), alt.Tooltip("Emails:Q")],
            )
            tchart = (alt.layer(base.mark_line(strokeWidth=2, interpolate="monotone"),
                                base.mark_point(size=70, filled=True, stroke="#111827", strokeWidth=2))
                      .properties(height=200, background="transparent").configure_view(strokeWidth=0).configure(font="Inter"))
            try:
                st.altair_chart(tchart, width="stretch")
            except Exception:
                st.altair_chart(tchart, use_container_width=True)

            # Hot leads: opened or clicked recently, one row per record
            seen_day = view_e["Last seen"].apply(lambda x: x.date() if x is not None and not pd.isna(x) else None)
            hot = view_e[seen_day.apply(lambda d: bool(d) and d >= p_start) & ~view_e["Bounced"]]
            if not hot.empty:
                hot = (hot.sort_values("Last seen", ascending=False)
                       .groupby("Record", sort=False)
                       .agg({"Last seen": "max", "Firm": "first", "Contact": "first", "Email": "first", "Opens": "sum",
                             "Clicks": "sum", "Clicked": "max", "App": lambda a: ", ".join(dict.fromkeys(a)),
                             "Subject": "first", "Zoho": "first"})
                       .reset_index())
                hot["Signal"] = hot.apply(lambda x: f"🔥 Clicked ×{x['Clicks']}" if x["Clicked"] else
                                          (f"Opened ×{x['Opens']}" if x["Opens"] > 1 else "Opened"), axis=1)
                hot = hot.sort_values(["Clicked", "Opens", "Last seen"], ascending=[False, False, False])
            st.markdown(f"**🔥 Hot leads · who to call first** · {len(hot):,} opened or clicked in the {eng_period.lower()}")
            if hot.empty:
                st.caption("No opens or clicks in this period yet.")
            else:
                show_h = hot.copy()
                show_h["Last seen"] = show_h["Last seen"].apply(_when)
                _table(show_h, height=min(38 + 35 * len(show_h), 420),
                       column_order=["Signal", "Last seen", "Firm", "Contact", "Email", "App", "Subject", "Zoho"],
                       column_config={
                           "Signal": st.column_config.TextColumn("Signal", width=120),
                           "Last seen": st.column_config.TextColumn("Last opened / clicked", width=150),
                           "Firm": st.column_config.TextColumn("Firm / customer", width="medium"),
                           "Subject": st.column_config.TextColumn("Email subject", width="large"),
                           "Zoho": st.column_config.LinkColumn("Zoho", width="small", display_text="Open ↗")})
                hx = hot[["Signal", "Last seen", "Firm", "Contact", "Email", "App", "Subject", "Zoho"]].copy()
                hx["Last seen"] = hx["Last seen"].apply(lambda d: d.strftime("%Y-%m-%d %H:%M"))
                h1, _ = columns([1, 3])
                h1.download_button("⬇  Hot leads (.csv)", data=hx.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"hot_leads_{today.isoformat()}.csv", mime="text/csv", key="dl_hot", **FULL_WIDTH)

            # Bounces: addresses to clean up in Zoho
            bounced = cur_e[cur_e["Bounced"]].sort_values("Sent", ascending=False)
            st.markdown(f"**↩️ Bounced · clean these up in Zoho** · {len(bounced):,} in the {eng_period.lower()}")
            if bounced.empty:
                st.caption("No bounces in this period.")
            else:
                show_b = bounced.copy()
                show_b["Bounced at"] = show_b.apply(lambda x: _when(x["Bounced at"]) or _when(x["Sent"]), axis=1)
                _table(show_b, height=min(38 + 35 * len(show_b), 360),
                       column_order=["Bounced at", "Email", "Firm", "Contact", "Reason", "App", "Zoho"],
                       column_config={
                           "Bounced at": st.column_config.TextColumn("Bounced", width=130),
                           "Email": st.column_config.TextColumn("Email address", width="medium"),
                           "Firm": st.column_config.TextColumn("Firm / customer", width="medium"),
                           "Reason": st.column_config.TextColumn("Why", width="large"),
                           "Zoho": st.column_config.LinkColumn("Zoho", width="small", display_text="Open ↗")})
                bx = bounced[["Sent", "Email", "Firm", "Contact", "Reason", "App", "Zoho"]].copy()
                bx["Sent"] = bx["Sent"].apply(lambda d: d.strftime("%Y-%m-%d %H:%M"))
                g1, _ = columns([1, 3])
                g1.download_button("⬇  Bounces (.csv)", data=bx.to_csv(index=False).encode("utf-8-sig"),
                                   file_name=f"bounces_{today.isoformat()}.csv", mime="text/csv", key="dl_bounce", **FULL_WIDTH)

# ---------------- Weekly summary ----------------
with st.container(key="card-week"):
    section_header("03", "Last 7 days summary", "Highlights only, no company names. Download the PDF or copy the text"
                   " into an email for the team.")
    _wc, _ = st.columns([1, 3])
    wk_end = _wc.date_input("Week ending", value=today, max_value=today, format="DD/MM/YYYY", key="wk_end",
                           help="Defaults to today, covering the last 7 days. Pick an earlier date for a past week.")
    ws = week_stats(events, wk_end, eng_df)

    def _delta(now_v: int, before: int) -> str:
        txt = _change(now_v, before)
        return f'<div class="d {"up" if txt.startswith(("+", "new")) else "flat"}">{esc(txt)}</div>'

    render_html(
        '<div class="lo-week">'
        f'<div class="c"><div class="v">{ws["emails"]:,}</div><div class="l">Emails sent</div>{_delta(ws["emails"], ws["emails_prev"])}</div>'
        f'<div class="c"><div class="v">{ws["leads"]:,}</div><div class="l">New leads added to Zoho</div>{_delta(ws["leads"], ws["leads_prev"])}</div>'
        f'<div class="c"><div class="v">{(str(round(ws["via_zoho"] / ws["emails"] * 100)) + "%") if ws["emails"] else "–"}</div>'
        '<div class="l">Sent straight from Zoho</div><div class="d flat">Logged on every record</div></div>'
        f'<div class="c"><div class="v">{ws["busiest"].strftime("%a") if ws["busiest"] else "–"}</div><div class="l">Busiest day</div>'
        f'<div class="d flat">{ws["busiest_n"]:,} emails</div></div>'
        "</div>"
    )
    w1, w2 = st.columns([1, 2])
    with w1:
        try:
            pdf_bytes = weekly_pdf(ws)
            st.download_button("⬇  Download weekly summary (PDF)", data=pdf_bytes, type="primary",
                               file_name=f"Sales_automation_summary_{ws['start'].isoformat()}_to_{ws['end'].isoformat()}.pdf",
                               mime="application/pdf", **FULL_WIDTH)
        except Exception as exc:
            st.error(f"Couldn't build the PDF ({exc.__class__.__name__}).")
        st.caption(f"Covers {_rng(ws)}.")
    with w2:
        with st.expander("📋  Copy as text for an email", expanded=False):
            st.code(weekly_text(ws), language=None)

# ---------------- Table ----------------
with st.container(key="card-table"):
    section_header("04", "All activity", "Newest first. Filter, search, then open any record in Zoho.")
    f1, f2, f3, f4 = st.columns([1, 1.3, 1.3, 1.4])
    with f1:
        period = st.selectbox("Period", ["Today", "Last 7 days", "Last 30 days", "This month", "All time"], index=4)
    with f2:
        pick_apps = st.multiselect("App", list(APPS), default=[], placeholder="All apps")
    with f3:
        acts = sorted(events["Activity"].unique())
        pick_acts = st.multiselect("Activity", acts, default=[], placeholder="All activity")
    with f4:
        q = st.text_input("Search", placeholder="Firm, contact, email or subject").strip().lower()

    view = events.copy()
    day_of = view["When"].apply(lambda d: d.date() if d else None)
    if period == "Today":
        view = view[day_of == today]
    elif period == "Last 7 days":
        view = view[day_of.apply(lambda d: bool(d) and d >= today - timedelta(days=6))]
    elif period == "Last 30 days":
        view = view[day_of.apply(lambda d: bool(d) and d >= today - timedelta(days=29))]
    elif period == "This month":
        view = view[day_of.apply(lambda d: bool(d) and d.year == today.year and d.month == today.month)]
    if pick_apps:
        view = view[view["App"].isin(pick_apps)]
    if pick_acts:
        view = view[view["Activity"].isin(pick_acts)]
    if q:
        hay = (view["Firm"] + " " + view["Contact"] + " " + view["Email"] + " " + view["Detail"] + " " + view["By"]).str.lower()
        view = view[hay.str.contains(q, regex=False)]

    st.caption(f"Showing {len(view):,} of {len(events):,} records.")
    show = view.copy()
    show["When"] = show["When"].apply(
        lambda d: "" if not d else d.strftime("Today %H:%M") if d.date() == today
        else d.strftime("%a %d %b %H:%M") if d.year == today.year else d.strftime("%d %b %Y"))
    show["App"] = show["App"].map({"Prospect Engine": "🔵 Prospect Engine", "Lead Revival": "🟠 Lead Revival",
                                   "Customer Growth": "🟢 Customer Growth", "MY PA": "🟡 MY PA"})
    table_kwargs = dict(
        hide_index=True, height=min(38 + 35 * max(len(show), 1), 620),
        column_order=["When", "App", "Activity", "Firm", "Contact", "Email", "Detail", "By", "How", "Zoho"],
        column_config={
            "When": st.column_config.TextColumn("When", width=128),
            "App": st.column_config.TextColumn("App", width=165),
            "Activity": st.column_config.TextColumn("Activity", width=125),
            "Firm": st.column_config.TextColumn("Firm / customer", width="medium"),
            "Contact": st.column_config.TextColumn("Contact", width="small"),
            "Email": st.column_config.TextColumn("Email", width="medium"),
            "Detail": st.column_config.TextColumn("Subject / detail", width="large"),
            "By": st.column_config.TextColumn("By", width="small"),
            "How": st.column_config.TextColumn("How", width=150),
            "Zoho": st.column_config.LinkColumn("Zoho", width="small", display_text="Open ↗"),
        },
    )
    try:
        st.dataframe(show, width="stretch", **table_kwargs)
    except Exception:
        st.dataframe(show, use_container_width=True, **table_kwargs)
    d1, _ = columns([1, 3])
    with d1:
        export = view.copy()
        export["When"] = export["When"].apply(lambda d: d.strftime("%Y-%m-%d %H:%M") if d else "")
        st.download_button("⬇  Download these rows (.csv)", data=export.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"lead_overview_{today.isoformat()}.csv", mime="text/csv", **FULL_WIDTH)

# ==========================================
# SETUP (Streamlit Secrets)
#   APP_PASSWORD   = "choose-a-password"
#   GITHUB_TOKEN   = "github_pat_..."     # read access to the repo(s) the apps save to
#   GITHUB_REPO    = "sammyatt2010-hub/prospect-engine-data"
# Optional:
#   ZOHO_ORG       = "org20123456"        # from your Zoho address: crm.zoho.eu/crm/<this>/...
#   ZOHO_CLIENT_ID / ZOHO_CLIENT_SECRET   # same as Lead Revival; turns on the Engagement section
#   ZOHO_REFRESH_TOKEN                     # this app's own read-only key, from the one-off setup box
#   PE_GITHUB_REPO / LR_GITHUB_REPO / CG_GITHUB_REPO      # only if an app saves to a different repo
#   PE_GITHUB_TOKEN / LR_GITHUB_TOKEN / CG_GITHUB_TOKEN   # that app's own token, if GITHUB_TOKEN can't see its repo
#   GITHUB_LOG_PATH, GITHUB_ZOHO_LEADS_PATH, GITHUB_CRM_LOG_PATH, GITHUB_CG_LOG_PATH, GITHUB_CG_CAMPAIGN_PATH
#                                          # only if you changed a file name in one of the apps
# ==========================================
