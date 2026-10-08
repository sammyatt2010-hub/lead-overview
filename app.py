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
    }


def _week_eng(eng: Optional[pd.DataFrame], start: date, end: date) -> Optional[Dict[str, Any]]:
    if eng is None or eng.empty or start < datetime.now(UK).date() - timedelta(days=ENG_DAYS - 1):
        return None
    days = eng["Sent"].apply(lambda x: x.date())
    r = eng_rates(eng[(days >= start) & (days <= end)])
    return r if r["sent"] else None


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


def weekly_pdf(ws: Dict[str, Any]) -> bytes:
    from fpdf import FPDF
    T = _pdf_txt
    navy, ink, grey, light, accent = (17, 24, 39), (30, 34, 48), (100, 108, 125), (244, 246, 250), (91, 99, 230)
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(False)
    pdf.add_page()
    W, L = 210, 14
    CW = W - 2 * L
    # Header
    pdf.set_fill_color(*navy)
    pdf.rect(0, 0, W, 36, "F")
    pdf.set_fill_color(*accent)
    pdf.rect(0, 36, W, 1.4, "F")
    pdf.set_xy(L, 9)
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(140, 152, 176)
    pdf.cell(0, 4, T(f"{_secret('REPORT_COMPANY', 'SY COMMUNICATIONS').upper()}  |  SALES AUTOMATION"))
    pdf.set_xy(L, 14)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, "Weekly summary")
    pdf.set_xy(L, 24)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(200, 206, 220)
    pdf.cell(0, 5, T(_rng(ws) + "  |  Prospect Engine, Lead Revival, Customer Growth & MY PA"))

    # Three headline boxes
    y = 46
    gap = 5
    bw = (CW - 2 * gap) / 3
    via_pct = f"{round(ws['via_zoho'] / ws['emails'] * 100)}%" if ws["emails"] else "-"
    boxes = [
        (f"{ws['emails']:,}", "Emails sent", _change(ws["emails"], ws["emails_prev"])),
        (f"{ws['leads']:,}", "New leads added to Zoho", _change(ws["leads"], ws["leads_prev"])),
        (via_pct, "Sent straight from Zoho", "Logged on every record"),
    ]
    for i, (big, label, sub) in enumerate(boxes):
        x = L + i * (bw + gap)
        pdf.set_fill_color(*light)
        pdf.rect(x, y, bw, 30, "F")
        pdf.set_fill_color(*accent)
        pdf.rect(x, y, bw, 1.2, "F")
        pdf.set_xy(x + 5, y + 5)
        pdf.set_font("Helvetica", "B", 22)
        pdf.set_text_color(*ink)
        pdf.cell(bw - 10, 10, T(big))
        pdf.set_xy(x + 5, y + 16)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(bw - 10, 5, T(label))
        pdf.set_xy(x + 5, y + 22)
        pdf.set_font("Helvetica", "", 8)
        good = sub.startswith("+") or sub.startswith("new")
        pdf.set_text_color(*((22, 140, 90) if good else grey))
        pdf.cell(bw - 10, 4, T(sub))

    def heading(text: str, yy: float) -> float:
        pdf.set_xy(L, yy)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*accent)
        pdf.cell(0, 5, T(text.upper()))
        return yy + 8

    # Per-app table
    y = heading("By app", y + 40)
    cols = [("App", 70), ("This week", 30), ("Previous week", 32), ("Change", 26), ("All time", 24)]
    pdf.set_font("Helvetica", "B", 8.5)
    pdf.set_text_color(*grey)
    x = L
    for name, w in cols:
        pdf.set_xy(x, y)
        pdf.cell(w, 6, name, align="L" if name == "App" else "R")
        x += w
    y += 7
    for a in ws["per_app"]:
        pdf.set_draw_color(225, 228, 236)
        pdf.line(L, y, L + sum(w for _, w in cols), y)
        pdf.set_fill_color(*_rgb(APPS[a["app"]]))
        pdf.rect(L, y + 2.3, 3, 3, "F")
        ch = a["week"] - a["prev"]
        vals = [a["app"], f"{a['week']:,}", f"{a['prev']:,}", (f"+{ch}" if ch > 0 else str(ch)) if a["prev"] or a["week"] else "-",
                f"{a['all']:,}"]
        x = L
        for (name, w), v in zip(cols, vals):
            pdf.set_xy(x + (5 if name == "App" else 0), y + 1)
            pdf.set_font("Helvetica", "B" if name in ("App", "This week") else "", 9.5)
            pdf.set_text_color(*ink)
            pdf.cell(w - (5 if name == "App" else 0), 6, T(v), align="L" if name == "App" else "R")
            x += w
        y += 8
    y += 4

    # Daily chart (stacked bars)
    y = heading("Emails per day", y)
    ch_h, base = 48, y + 52
    days = list(ws["daily"])
    top = max([sum(ws["daily"][d].values()) for d in days] + [1])
    slot = CW / 7
    bar_w = slot * 0.55
    pdf.set_draw_color(225, 228, 236)
    pdf.line(L, base, L + CW, base)
    for i, day in enumerate(days):
        x = L + i * slot + (slot - bar_w) / 2
        yy = base
        total = 0
        for app in APPS:
            n = ws["daily"][day][app]
            if not n:
                continue
            h = ch_h * n / top
            pdf.set_fill_color(*_rgb(APPS[app]))
            pdf.rect(x, yy - h, bar_w, h, "F")
            yy -= h
            total += n
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(*ink)
        pdf.set_xy(x - 3, yy - 5)
        pdf.cell(bar_w + 6, 4, str(total) if total else "", align="C")
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*grey)
        pdf.set_xy(L + i * slot, base + 1.5)
        pdf.cell(slot, 4, T(day.strftime("%a %d")), align="C")
    # Legend
    lx = L
    ly = base + 8
    for app, col in APPS.items():
        pdf.set_fill_color(*_rgb(col))
        pdf.rect(lx, ly + 1, 3, 3, "F")
        pdf.set_xy(lx + 4.5, ly)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*ink)
        pdf.cell(40, 5, T(app))
        lx += pdf.get_string_width(T(app)) + 14
    y = ly + 12

    # Highlights
    y = heading("Highlights", y)
    bullets = []
    if ws["busiest"]:
        bullets.append(f"Busiest day was {ws['busiest'].strftime('%A')}, with {ws['busiest_n']:,} emails sent.")
    bullets.append(f"Emails went out on {ws['active_days']} of the last 7 days.")
    if ws["sectors"]:
        bullets.append("Top sectors pitched: " + ", ".join(f"{k} ({v})" for k, v in ws["sectors"]) + ".")
    if ws["campaigns"]:
        bullets.append("Customer campaigns sent: " + ", ".join(f"{k} ({v})" for k, v in ws["campaigns"]) + ".")
    if ws.get("eng"):
        bullets.append(eng_sentence(ws["eng"]))
    if ws["trials"]:
        bullets.append(f"{ws['trials']:,} businesses offered a free 1-week MY PA Connect trial.")
    bullets.append(f"All time: {ws['emails_all']:,} emails sent and {ws['leads_all']:,} new leads added to Zoho.")
    for b in bullets:
        if y > 268:
            break
        pdf.set_fill_color(*accent)
        pdf.rect(L, y + 2, 1.6, 1.6, "F")
        pdf.set_xy(L + 4, y)
        pdf.set_font("Helvetica", "", 9.5)
        pdf.set_text_color(*ink)
        pdf.multi_cell(CW - 4, 5, T(b))
        y = pdf.get_y() + 2

    # Footer
    pdf.set_fill_color(*navy)
    pdf.rect(0, 284, W, 13, "F")
    pdf.set_xy(L, 288)
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(160, 170, 190)
    pdf.cell(0, 4, T(f"Generated from Lead Overview on {datetime.now(UK).strftime('%d %b %Y %H:%M')}. Counts emails"
                     " sent and new Zoho leads; no individual companies are named."))
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
                            help="Re-reads the latest opens, clicks and bounces from Zoho straight away.")
        sends = engagement_sends(logs, datetime.now(UK) - timedelta(days=ENG_DAYS))
        capped = len(sends) > ENG_MAX
        sends = sends[:ENG_MAX]
        bar = st.empty()

        def _prog(frac: float, text: str) -> None:
            bar.progress(min(frac, 1.0), text=text)

        with st.spinner("Reading email tracking from Zoho…"):
            eng_emails, eng_err = load_engagement(sends, force=recheck, progress=_prog)
        bar.empty()
        key_problem = bool(eng_err and "KEY: " in eng_err)
        if eng_err:
            (st.error if key_problem else st.warning)(eng_err.replace("KEY: ", ""))
        # Set up or renew this app's own Zoho key; opens by itself when the key is the problem
        with st.expander("🔑  Zoho key: set up or renew", expanded=key_problem):
            render_zoho_connect()
        eng_df = build_engagement(sends, eng_emails)
        if not sends:
            st.info("No emails sent from Zoho in the last 30 days yet. Only emails sent with the apps' **Send via Zoho**"
                    " button are tracked; drafts opened in Outlook aren't.")
        elif eng_df.empty:
            st.info("Nothing read from Zoho yet. Click **Check Zoho now**.")
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
