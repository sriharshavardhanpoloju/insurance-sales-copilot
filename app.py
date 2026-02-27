# ============================================================
# app.py — Insurance Agent Sales Co-Pilot  v3  (HACKATHON EDITION)
# ============================================================

import streamlit as st
import streamlit.components.v1 as components
import json
import time

from ai_engine       import analyze_client, get_intent_label, get_persona_label, COACHING_TIPS, OBJECTION_HANDLERS
from policy_engine   import recommend_policy, get_profit_tier, get_bundle_suggestions, calculate_deal_value, build_comparison_matrix, get_performance_grade
from session_manager import load_sessions, save_session, get_performance_stats, clear_sessions, update_deal_status, export_sessions_csv
from speech_engine   import get_speech_widget
from recommender_model import recommend as model_recommend, get_model_info

try:
    from pdf_report import generate_report, REPORTLAB_AVAILABLE
except ImportError:
    REPORTLAB_AVAILABLE = False

st.set_page_config(
    page_title="Insurance Co-Pilot v3",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Page router — runs before any rendering ──────────────
if st.session_state.get("current_page") == "policy_detail":
    policy = st.session_state.get("selected_policy")
    if not policy:
        st.session_state["current_page"] = "main"
        st.rerun()
    else:
        from policy_engine import get_profit_tier, get_bundle_suggestions
        from ai_engine import get_intent_label as _gil

        tier       = get_profit_tier(policy["profit_score"])
        pc         = tier["color"]
        p_name     = policy["name"]
        p_type     = policy.get("type","family")
        p_desc     = policy["description"]
        p_prem     = policy["premium"]
        p_cov      = policy["coverage"]
        p_prof     = policy["profit_score"]
        p_claim    = policy.get("claim_settlement",0)
        p_wait     = policy.get("waiting_period_days",0)
        p_term     = policy.get("policy_term_years",1)
        p_min      = policy.get("min_age",18)
        p_max      = policy.get("max_age",65)
        p_tax      = "✅ Yes" if policy.get("tax_benefit") else "❌ No"
        p_cash     = "✅ Yes" if policy.get("cashless") else "❌ No"
        p_badge    = policy.get("badge","")
        p_ideal    = policy.get("ideal_for","")
        p_hilist   = policy.get("highlights",[])
        smart      = policy.get("smart_score", p_prof)
        monthly    = p_prem // 12
        commission = int(p_prem * 0.15)
        ltv        = commission * p_term
        iinfo      = _gil(p_type)

        st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');
*{margin:0;padding:0;box-sizing:border-box;}
html,body,[class*="css"]{font-family:'Inter',sans-serif;background:linear-gradient(135deg,#07091a,#0a0f1e);color:#e2e8f0;}
.block-container{padding:2rem 3rem;max-width:1100px;margin:0 auto;}
.stButton>button{background:linear-gradient(135deg,#3a4add,#5a2aed);color:white;border:none;border-radius:14px;padding:.6rem 1.4rem;font-weight:600;font-size:.9rem;transition:all .3s;box-shadow:0 4px 15px rgba(74,90,237,.3);}
.stButton>button:hover{background:linear-gradient(135deg,#4a5aed,#6a3afd);transform:translateY(-2px);box-shadow:0 8px 25px rgba(74,90,237,.5);}
#MainMenu,footer,header{visibility:hidden;}
</style>
""", unsafe_allow_html=True)

        # Back button at top
        if st.button("← Back to Analysis", key="back_top"):
            st.session_state["current_page"] = "main"
            st.rerun()

        # Hero card
        badge_h = f'<span style="background:{pc}22;color:{pc};border:1px solid {pc}55;border-radius:30px;padding:5px 14px;font-size:.76rem;font-weight:700;margin-right:8px;">{p_badge}</span>' if p_badge else ""
        type_e  = iinfo["emoji"]
        type_l  = p_type.title()
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#0d1530,#0f1a3a);border-radius:24px;padding:36px 40px;margin-bottom:28px;border:1px solid rgba(74,90,237,0.35);box-shadow:0 20px 60px rgba(0,0,0,0.5);position:relative;overflow:hidden;">
<div style="display:flex;align-items:flex-start;justify-content:space-between;flex-wrap:wrap;gap:16px;">
<div style="flex:1;min-width:260px;">
<div style="margin-bottom:12px;">{badge_h}<span style="background:rgba(74,90,237,0.1);color:#a5b4fc;border:1px solid rgba(74,90,237,0.3);border-radius:30px;padding:5px 14px;font-size:.76rem;font-weight:600;">{type_e} {type_l}</span></div>
<div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2.4rem;font-weight:800;background:linear-gradient(135deg,#fff,#a5b4fc 55%,#64d9f8);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;line-height:1.2;margin-bottom:8px;">{p_name}</div>
<div style="color:#64748b;font-size:1rem;line-height:1.6;">{p_desc}</div>
</div>
<div style="text-align:right;">
<div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1.5px;color:#475569;margin-bottom:4px;">Annual Premium</div>
<div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:2.8rem;font-weight:800;color:#10b981;line-height:1;">${p_prem:,}</div>
<div style="color:#475569;font-size:.8rem;margin-top:4px;">${monthly:,} / month</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

        lc, rc = st.columns([1.1, 1], gap="large")

        with lc:
            # Scores
            st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">📊 Performance Scores</p>', unsafe_allow_html=True)
            st.markdown(f"""
<div style="background:#0c1020;border:1px solid rgba(74,90,237,.15);border-radius:16px;padding:20px 22px;margin-bottom:24px;">
<div style="display:flex;align-items:center;gap:14px;margin-bottom:11px;">
<span style="min-width:100px;font-size:.71rem;text-transform:uppercase;letter-spacing:1px;color:#475569;font-weight:600;">Profit Score</span>
<div style="flex:1;background:#0a0e20;border-radius:30px;height:12px;overflow:hidden;"><div style="width:{p_prof}%;height:100%;background:{pc};border-radius:30px;"></div></div>
<span style="min-width:44px;text-align:right;font-weight:700;font-size:.9rem;color:{pc};">{p_prof}</span>
</div>
<div style="display:flex;align-items:center;gap:14px;margin-bottom:11px;">
<span style="min-width:100px;font-size:.71rem;text-transform:uppercase;letter-spacing:1px;color:#475569;font-weight:600;">Smart Score</span>
<div style="flex:1;background:#0a0e20;border-radius:30px;height:12px;overflow:hidden;"><div style="width:{smart}%;height:100%;background:linear-gradient(90deg,#4a5aed,#64d9f8);border-radius:30px;"></div></div>
<span style="min-width:44px;text-align:right;font-weight:700;font-size:.9rem;color:#64d9f8;">{smart}</span>
</div>
<div style="display:flex;align-items:center;gap:14px;">
<span style="min-width:100px;font-size:.71rem;text-transform:uppercase;letter-spacing:1px;color:#475569;font-weight:600;">Claim Rate</span>
<div style="flex:1;background:#0a0e20;border-radius:30px;height:12px;overflow:hidden;"><div style="width:{p_claim}%;height:100%;background:#10b981;border-radius:30px;"></div></div>
<span style="min-width:44px;text-align:right;font-weight:700;font-size:.9rem;color:#10b981;">{p_claim}%</span>
</div>
</div>
""", unsafe_allow_html=True)

            # Financials
            st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">💰 Financial Breakdown</p>', unsafe_allow_html=True)
            f1, f2 = st.columns(2)
            with f1:
                st.markdown(f'<div style="background:#0c1020;border:1px solid rgba(74,90,237,.15);border-radius:14px;padding:16px 18px;margin-bottom:12px;"><div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1.2px;color:#475569;font-weight:600;margin-bottom:5px;">Annual Premium</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.4rem;font-weight:700;color:#e2e8f0;">${p_prem:,}</div><div style="font-size:.71rem;color:#4a5aed;margin-top:3px;">${monthly:,} per month</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:#0c1020;border:1px solid rgba(16,185,129,.2);border-radius:14px;padding:16px 18px;"><div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1.2px;color:#475569;font-weight:600;margin-bottom:5px;">Your Commission</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.4rem;font-weight:700;color:#10b981;">${commission:,}</div><div style="font-size:.71rem;color:#10b981;opacity:.7;margin-top:3px;">First year · 15%</div></div>', unsafe_allow_html=True)
            with f2:
                st.markdown(f'<div style="background:#0c1020;border:1px solid rgba(74,90,237,.15);border-radius:14px;padding:16px 18px;margin-bottom:12px;"><div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1.2px;color:#475569;font-weight:600;margin-bottom:5px;">Total Coverage</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.4rem;font-weight:700;color:#64d9f8;">${p_cov:,}</div><div style="font-size:.71rem;color:#4a5aed;margin-top:3px;">Full protection</div></div>', unsafe_allow_html=True)
                st.markdown(f'<div style="background:#0c1020;border:1px solid rgba(16,185,129,.2);border-radius:14px;padding:16px 18px;"><div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1.2px;color:#475569;font-weight:600;margin-bottom:5px;">Lifetime Value</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.4rem;font-weight:700;color:#10b981;">${ltv:,}</div><div style="font-size:.71rem;color:#10b981;opacity:.7;margin-top:3px;">Over {p_term} yr term</div></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Specs
            st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">📋 Policy Specifications</p>', unsafe_allow_html=True)
            s1,s2,s3 = st.columns(3)
            specs = [
                ("Policy Term", f"{p_term} yrs"), ("Eligible Age", f"{p_min}–{p_max}"),
                ("Waiting", f"{p_wait}d"), ("Claim Rate", f"{p_claim}%"),
                ("Tax Benefit", p_tax), ("Cashless", p_cash),
            ]
            for col, (lbl, val) in zip([s1,s2,s3,s1,s2,s3], specs):
                with col:
                    st.markdown(f'<div style="background:#0c1020;border:1px solid rgba(74,90,237,.12);border-radius:12px;padding:12px 14px;margin-bottom:10px;"><div style="font-size:.66rem;text-transform:uppercase;letter-spacing:1px;color:#475569;margin-bottom:4px;">{lbl}</div><div style="font-family:Plus Jakarta Sans,sans-serif;font-size:1.1rem;font-weight:700;color:#e2e8f0;">{val}</div></div>', unsafe_allow_html=True)

        with rc:
            # Highlights
            st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">✨ Key Highlights</p>', unsafe_allow_html=True)
            for h in p_hilist:
                st.markdown(f'<div style="display:flex;align-items:center;gap:12px;background:rgba(74,90,237,.05);border:1px solid rgba(74,90,237,.15);border-radius:11px;padding:11px 15px;margin-bottom:8px;"><span style="font-size:1rem;">✅</span><span style="color:#cbd5e1;font-size:.88rem;">{h}</span></div>', unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Best For
            st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">🎯 Best For</p>', unsafe_allow_html=True)
            st.markdown(f'<div style="background:linear-gradient(135deg,rgba(16,185,129,.08),rgba(16,185,129,.03));border:1px solid rgba(16,185,129,.28);border-radius:16px;padding:20px 22px;margin-bottom:22px;"><div style="color:#94a3b8;font-size:.9rem;line-height:1.8;">{p_ideal}</div></div>', unsafe_allow_html=True)

            # Bundles
            bundles = get_bundle_suggestions(p_type)
            if bundles:
                st.markdown('<p style="font-size:.7rem;text-transform:uppercase;letter-spacing:2px;font-weight:700;color:#4a5aed;margin-bottom:12px;padding-bottom:7px;border-bottom:1px solid rgba(74,90,237,.2);">💼 Cross-Sell Opportunities</p>', unsafe_allow_html=True)
                for ik, title, desc in bundles:
                    be = _gil(ik)["emoji"]
                    st.markdown(f'<div style="background:rgba(20,15,0,.6);border:1px solid rgba(245,158,11,.25);border-radius:13px;padding:14px 17px;margin-bottom:9px;"><div style="color:#f59e0b;font-size:.9rem;font-weight:700;margin-bottom:4px;">{be} {title}</div><div style="color:#9ca3af;font-size:.81rem;line-height:1.5;">{desc}</div></div>', unsafe_allow_html=True)

        st.markdown("---")
        if st.button("← Back to Analysis", key="back_bottom"):
            st.session_state["current_page"] = "main"
            st.rerun()

        st.stop()



st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
* { margin:0; padding:0; box-sizing:border-box; }
html,body,[class*="css"] { font-family:'Inter',sans-serif; background:linear-gradient(135deg,#0a0f1e 0%,#0b1120 100%); color:#e2e8f0; }
h1,h2,h3,h4,h5,h6 { font-family:'Plus Jakarta Sans',sans-serif; font-weight:700; letter-spacing:-0.02em; }
.main { background:linear-gradient(135deg,#0a0f1e 0%,#0b1120 100%); }
.block-container { padding:1.5rem 2rem 2rem; max-width:1400px; margin:0 auto; }
[data-testid="stSidebar"] { background:linear-gradient(180deg,#0f1525 0%,#0a0f1e 100%); border-right:1px solid rgba(74,90,237,0.15); }
[data-testid="stSidebar"] .stMarkdown p { color:#94a3b8; font-size:0.85rem; font-weight:500; }
[data-testid="stSidebar"] hr { border-color:rgba(74,90,237,0.2); margin:1.5rem 0; }
[data-testid="stSidebar"] .stTextInput input { background:rgba(10,15,30,0.6)!important; border:1px solid rgba(74,90,237,0.3)!important; border-radius:12px!important; color:#e2e8f0!important; padding:0.75rem 1rem!important; }
.hero { background:linear-gradient(135deg,#0f1a3a 0%,#1a1f3a 50%,#2a1f3a 100%); border:1px solid rgba(74,90,237,0.3); border-radius:24px; padding:32px 40px; margin-bottom:28px; position:relative; overflow:hidden; box-shadow:0 20px 40px -10px rgba(0,0,0,0.5); animation:heroGlow 4s ease-in-out infinite; }
@keyframes heroGlow { 0%,100%{box-shadow:0 20px 40px -10px rgba(74,90,237,0.3)}50%{box-shadow:0 20px 50px -5px rgba(74,90,237,0.5)} }
.hero-title { font-family:'Plus Jakarta Sans',sans-serif; font-size:2.5rem; font-weight:800; background:linear-gradient(135deg,#ffffff 0%,#a5b4fc 50%,#64d9f8 100%); -webkit-background-clip:text; -webkit-text-fill-color:transparent; background-clip:text; margin:0 0 8px; line-height:1.2; }
.hero-sub { color:#94a3b8; font-size:1rem; margin:0 0 16px; }
.chip { display:inline-block; background:rgba(74,90,237,0.1); border:1px solid rgba(74,90,237,0.3); border-radius:30px; padding:6px 16px; color:#a5b4fc; font-size:0.75rem; font-weight:600; margin:2px 4px 2px 0; transition:all 0.3s ease; }
.card { background:rgba(15,23,42,0.6); backdrop-filter:blur(10px); border:1px solid rgba(74,90,237,0.2); border-radius:20px; padding:22px 24px; margin-bottom:16px; transition:all 0.3s cubic-bezier(0.4,0,0.2,1); }
.card:hover { border-color:rgba(74,90,237,0.5); transform:translateY(-4px); box-shadow:0 20px 40px rgba(74,90,237,0.2); }
.card.accent { border-left:4px solid #4a5aed; }
.stitle { font-family:'Plus Jakarta Sans',sans-serif; color:#94a3b8; font-size:0.75rem; text-transform:uppercase; letter-spacing:2px; font-weight:600; margin-bottom:16px; padding-bottom:10px; border-bottom:1px solid rgba(74,90,237,0.2); display:flex; align-items:center; gap:8px; }
.stitle::before { content:''; width:4px; height:16px; background:linear-gradient(135deg,#4a5aed,#64d9f8); border-radius:4px; }
.intent-banner { border-radius:18px; padding:24px 28px; margin-bottom:20px; border-left:5px solid; background:rgba(10,15,30,0.7); backdrop-filter:blur(10px); box-shadow:0 10px 30px rgba(0,0,0,0.3); animation:slideIn 0.5s ease-out; }
@keyframes slideIn { from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)} }
.intent-title { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.3rem; font-weight:700; margin-bottom:8px; }
.intent-sub { font-size:0.88rem; margin-top:8px; opacity:0.8; line-height:1.6; }

/* ── POLICY CARD ── */
.policy-wrap { background:rgba(15,23,42,0.5); backdrop-filter:blur(10px); border-radius:20px; padding:22px 24px; margin-bottom:16px; border:1px solid rgba(74,90,237,0.2); transition:all 0.3s cubic-bezier(0.4,0,0.2,1); position:relative; overflow:hidden; animation:fadeInUp 0.6s ease-out; animation-fill-mode:both; }
.policy-wrap:hover { border-color:#4a5aed; transform:translateY(-4px); box-shadow:0 20px 40px rgba(74,90,237,0.25); background:rgba(20,30,55,0.9); cursor:pointer; }
.policy-wrap.top { border-color:#4a5aed; background:linear-gradient(135deg,rgba(74,90,237,0.15),rgba(20,30,55,0.9)); }
@keyframes fadeInUp { from{opacity:0;transform:translateY(30px)}to{opacity:1;transform:translateY(0)} }
.policy-name { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.2rem; font-weight:700; color:#f1f5f9; margin-bottom:6px; }
.policy-desc { font-size:0.85rem; color:#94a3b8; margin-bottom:16px; line-height:1.6; }

/* ── CLICK HINT ── */
.click-hint { font-size:0.7rem; color:#3a4a7a; text-align:right; margin-top:8px; transition:color 0.2s; }
.policy-wrap:hover .click-hint { color:#4a5aed; }

/* ── POLICY DETAIL MODAL ── */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.75); backdrop-filter:blur(6px); z-index:9998; animation:fadeOverlay 0.2s ease; }
@keyframes fadeOverlay { from{opacity:0}to{opacity:1} }
.modal-box { position:fixed; top:50%; left:50%; transform:translate(-50%,-50%); z-index:9999; width:min(760px,92vw); max-height:88vh; overflow-y:auto; background:linear-gradient(145deg,#0d1530,#0a1020); border:1px solid rgba(74,90,237,0.4); border-radius:24px; padding:32px 36px; box-shadow:0 40px 80px rgba(0,0,0,0.7),0 0 0 1px rgba(74,90,237,0.2); animation:modalIn 0.3s cubic-bezier(0.4,0,0.2,1); }
@keyframes modalIn { from{opacity:0;transform:translate(-50%,-48%) scale(0.96)}to{opacity:1;transform:translate(-50%,-50%) scale(1)} }
.modal-close { position:absolute; top:16px; right:20px; background:rgba(74,90,237,0.15); border:1px solid rgba(74,90,237,0.3); border-radius:50%; width:34px; height:34px; font-size:1rem; cursor:pointer; color:#94a3b8; display:flex; align-items:center; justify-content:center; transition:all 0.2s; }
.modal-close:hover { background:#4a5aed; color:white; transform:scale(1.1); }
.modal-title { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.6rem; font-weight:800; color:#f1f5f9; margin-bottom:4px; }
.modal-subtitle { font-size:0.86rem; color:#64748b; margin-bottom:20px; }
.modal-section { margin-top:20px; }
.modal-section-title { font-size:0.7rem; text-transform:uppercase; letter-spacing:1.8px; color:#4a5aed; font-weight:700; margin-bottom:10px; padding-bottom:6px; border-bottom:1px solid rgba(74,90,237,0.2); }
.modal-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
.modal-stat { background:rgba(10,15,30,0.6); border:1px solid rgba(74,90,237,0.15); border-radius:14px; padding:14px 16px; }
.modal-stat-label { font-size:0.68rem; text-transform:uppercase; letter-spacing:1px; color:#475569; font-weight:600; margin-bottom:4px; }
.modal-stat-value { font-family:'Plus Jakarta Sans',sans-serif; font-size:1.3rem; font-weight:700; color:#e2e8f0; }
.modal-stat-sub { font-size:0.72rem; color:#4a5aed; margin-top:2px; }
.modal-highlight { display:flex; align-items:center; gap:10px; background:rgba(74,90,237,0.06); border:1px solid rgba(74,90,237,0.15); border-radius:10px; padding:10px 14px; margin-bottom:8px; }
.modal-highlight-icon { font-size:1rem; }
.modal-highlight-text { color:#cbd5e1; font-size:0.85rem; }
.modal-score-row { display:flex; align-items:center; gap:12px; margin-bottom:10px; }
.modal-score-label { min-width:90px; font-size:0.72rem; text-transform:uppercase; letter-spacing:1px; color:#475569; font-weight:600; }
.modal-score-track { flex:1; background:rgba(10,15,30,0.8); border-radius:30px; height:10px; overflow:hidden; }
.modal-score-fill { height:100%; border-radius:30px; }
.modal-score-num { min-width:32px; text-align:right; font-weight:700; font-size:0.85rem; }
.modal-badge { display:inline-block; padding:5px 14px; border-radius:30px; font-size:0.75rem; font-weight:700; margin:3px 4px 3px 0; }
.modal-tag { display:inline-block; background:rgba(74,90,237,0.08); border:1px solid rgba(74,90,237,0.25); border-radius:10px; padding:5px 12px; font-size:0.78rem; color:#94a3b8; margin:3px 4px 3px 0; }
.modal-verdict { background:linear-gradient(135deg,rgba(16,185,129,0.08),rgba(16,185,129,0.03)); border:1px solid rgba(16,185,129,0.25); border-radius:16px; padding:18px 20px; margin-top:20px; }
.modal-verdict-title { color:#10b981; font-size:0.7rem; text-transform:uppercase; letter-spacing:1.5px; font-weight:700; margin-bottom:8px; }
.modal-verdict-text { color:#94a3b8; font-size:0.86rem; line-height:1.7; }

.score-bar-track { background:rgba(10,15,30,0.6); border-radius:30px; height:8px; width:100%; overflow:hidden; }
.score-bar-fill { height:100%; border-radius:30px; }
.badge-pill { display:inline-block; padding:4px 12px; border-radius:30px; font-size:0.75rem; font-weight:600; margin:2px 4px 2px 0; }
.hi-pill { display:inline-block; background:rgba(74,90,237,0.08); border:1px solid rgba(74,90,237,0.3); border-radius:12px; padding:4px 12px; font-size:0.75rem; color:#94a3b8; margin:2px 4px 2px 0; }
.commission-box { background:linear-gradient(135deg,rgba(16,185,129,0.1),rgba(16,185,129,0.05)); border:1px solid rgba(16,185,129,0.3); border-radius:20px; padding:24px; text-align:center; margin-top:20px; }
.commission-amount { font-family:'Plus Jakarta Sans',sans-serif; color:#10b981; font-size:2.5rem; font-weight:800; line-height:1.2; }
.commission-sub { color:#6b7280; font-size:0.8rem; margin-top:6px; }
.coach-wrap { background:rgba(10,15,30,0.7); border-left:4px solid #4a5aed; border-radius:0 16px 16px 0; padding:16px 20px; }
.coach-item { color:#cbd5e1; font-size:0.88rem; line-height:1.7; padding:10px 0; border-bottom:1px solid rgba(74,90,237,0.15); }
.coach-item:last-child { border-bottom:none; }
.obj-card { background:rgba(20,10,30,0.7); border-left:4px solid #a855f7; border-radius:0 14px 14px 0; padding:14px 18px; margin:8px 0; }
.obj-q { color:#c084fc; font-size:0.88rem; font-weight:600; margin-bottom:6px; }
.obj-a { color:#94a3b8; font-size:0.84rem; line-height:1.5; }
.bundle-card { background:rgba(20,15,0,0.7); border:1px solid rgba(245,158,11,0.3); border-radius:16px; padding:16px 18px; margin:8px 0; }
.bundle-title { color:#f59e0b; font-size:0.95rem; font-weight:700; margin-bottom:6px; }
.bundle-desc { color:#9ca3af; font-size:0.82rem; line-height:1.5; }
.kpi { background:rgba(15,23,42,0.6); backdrop-filter:blur(10px); border:1px solid rgba(74,90,237,0.2); border-radius:18px; padding:20px 22px; text-align:center; transition:all 0.3s ease; }
.kpi:hover { transform:translateY(-5px); border-color:rgba(74,90,237,0.5); }
.kpi-icon { font-size:1.8rem; margin-bottom:8px; }
.kpi-label { color:#94a3b8; font-size:0.7rem; text-transform:uppercase; letter-spacing:1.5px; font-weight:600; }
.kpi-value { font-family:'Plus Jakarta Sans',sans-serif; color:#f1f5f9; font-size:1.8rem; font-weight:700; margin-top:4px; }
.kpi-sub { color:#4a5aed; font-size:0.75rem; margin-top:4px; }
.sess-card { background:rgba(15,23,42,0.5); border:1px solid rgba(74,90,237,0.2); border-radius:18px; padding:16px 20px; margin-bottom:12px; transition:all 0.3s ease; }
.sess-card:hover { border-color:#4a5aed; transform:translateX(5px); }
.badge-won { display:inline-block; background:rgba(16,185,129,0.1); border:1px solid #10b981; border-radius:30px; padding:4px 14px; font-size:0.7rem; color:#10b981; font-weight:600; }
.badge-lost { display:inline-block; background:rgba(239,68,68,0.1); border:1px solid #ef4444; border-radius:30px; padding:4px 14px; font-size:0.7rem; color:#ef4444; font-weight:600; }
.badge-pend { display:inline-block; background:rgba(245,158,11,0.1); border:1px solid #f59e0b; border-radius:30px; padding:4px 14px; font-size:0.7rem; color:#f59e0b; font-weight:600; }
.badge-ai { display:inline-block; background:linear-gradient(90deg,#4a5aed,#a855f7); border-radius:30px; padding:4px 16px; font-size:0.7rem; font-weight:700; color:white; }
.badge-rule { display:inline-block; background:rgba(15,23,42,0.8); border:1px solid #4a5aed; border-radius:30px; padding:4px 14px; font-size:0.7rem; color:#a5b4fc; font-weight:600; }
.grade-badge { display:inline-block; font-family:'Plus Jakarta Sans',sans-serif; font-size:2.2rem; font-weight:800; width:64px; height:64px; line-height:64px; text-align:center; border-radius:18px; background:linear-gradient(135deg,#0f172a,#1a1f35); border:2px solid; }
.streak-box { background:linear-gradient(135deg,#2d1a0e,#1a0f08); border:1px solid rgba(255,107,53,0.4); border-radius:18px; padding:20px 24px; text-align:center; }
.streak-number { font-family:'Plus Jakarta Sans',sans-serif; font-size:3.5rem; font-weight:800; color:#ff6b35; line-height:1; }
.streak-label { color:#9c6b4a; font-size:0.75rem; text-transform:uppercase; letter-spacing:2px; font-weight:600; margin-top:6px; }
.chat-bubble-agent { background:linear-gradient(135deg,#1a1f35,#0f172a); border:1px solid #4a5aed; border-radius:18px 18px 18px 4px; padding:12px 18px; margin:8px 0; max-width:85%; color:#cbd5e1; font-size:0.88rem; line-height:1.6; }
.chat-bubble-client { background:linear-gradient(135deg,#1a2f1a,#0f1f0f); border:1px solid #10b981; border-radius:18px 18px 4px 18px; padding:12px 18px; margin:8px 0 8px auto; max-width:85%; color:#9ca3af; font-size:0.88rem; line-height:1.6; }
.chat-meta { color:#4a5aed; font-size:0.7rem; font-weight:600; margin-bottom:4px; }
.stTabs [data-baseweb="tab-list"] { background:rgba(15,23,42,0.6); border-radius:16px; gap:4px; padding:6px; border:1px solid rgba(74,90,237,0.2); }
.stTabs [data-baseweb="tab"] { border-radius:12px; color:#94a3b8; font-weight:600; font-size:0.88rem; padding:8px 16px; }
.stTabs [aria-selected="true"] { background:linear-gradient(135deg,#4a5aed,#6a3afd)!important; color:white!important; }
.stButton>button { background:linear-gradient(135deg,#3a4add,#5a2aed); color:white; border:none; border-radius:14px; padding:0.6rem 1.2rem; font-weight:600; font-size:0.88rem; transition:all 0.3s ease; }
.stButton>button:hover { background:linear-gradient(135deg,#4a5aed,#6a3afd); transform:translateY(-3px); box-shadow:0 8px 30px rgba(74,90,237,0.6); }
.stTextArea textarea,.stTextInput input { background:rgba(10,15,30,0.6)!important; border:1px solid rgba(74,90,237,0.3)!important; border-radius:16px!important; color:#e2e8f0!important; font-size:0.88rem!important; padding:0.8rem 1rem!important; }
::-webkit-scrollbar { width:8px; } ::-webkit-scrollbar-track { background:rgba(10,15,30,0.6); border-radius:10px; } ::-webkit-scrollbar-thumb { background:linear-gradient(135deg,#4a5aed,#6a3afd); border-radius:10px; }
#MainMenu,footer,header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### ⚙️ Settings")
    st.markdown("---")
    agent_name = st.text_input("Agent Name", value="Insurance Agent", key="agent_name_input")
    st.markdown("### 🤖 AI Engine")
    api_key = st.text_input("Anthropic API Key", type="password", placeholder="sk-ant-...", help="console.anthropic.com")
    if api_key:
        st.success("✅ Claude AI Active")
    else:
        st.info("⚙️ Rule-based mode")
    st.markdown("---")
    max_policies    = st.slider("Policies to show", 1, 5, 3)
    show_commission = st.toggle("Show commission", value=True)
    show_comparison = st.toggle("Show comparison table", value=True)
    show_bundles    = st.toggle("Show bundle suggestions", value=True)
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    sessions_sb = load_sessions()
    stats_sb    = get_performance_stats(sessions_sb)
    grade_info  = get_performance_grade(stats_sb["total_commission"])
    grade_color  = grade_info["color"]
    grade_letter = grade_info["grade"]
    grade_title  = grade_info["title"]
    sb_comm      = stats_sb["total_commission"]
    st.markdown(f"""
<div style="display:flex;align-items:center;gap:12px;background:#0c1020;border:1px solid #161e35;border-radius:12px;padding:12px 14px;margin-bottom:10px;">
<div class="grade-badge" style="color:{grade_color};border-color:{grade_color}40;">{grade_letter}</div>
<div>
<div style="color:#c0cce8;font-weight:700;font-size:0.9rem;">{grade_title}</div>
<div style="color:#3a4570;font-size:0.72rem;">${sb_comm:,} commission earned</div>
</div>
</div>
""", unsafe_allow_html=True)
    sb_c1, sb_c2 = st.columns(2)
    with sb_c1:
        st.metric("Sessions", stats_sb["total_sessions"])
        st.metric("Win Rate", f"{stats_sb['win_rate']}%")
    with sb_c2:
        st.metric("Today", stats_sb["sessions_today"])
        st.metric("Streak 🔥", f"{stats_sb['daily_streak']}d")
    st.markdown("---")
    st.markdown("### 🧠 Trained Model")
    minfo = get_model_info()
    if minfo["trained"]:
        st.success(f"✅ Model v{minfo['version']} loaded")
        st.caption(f"Trained on: {minfo['trained_on']}")
        m1, m2 = st.columns(2)
        m1.metric("Top-1 Acc", f"{minfo['top1_accuracy']}%")
        m2.metric("Top-3 Acc", f"{minfo['top3_accuracy']}%")
        use_trained_model = st.toggle("Use trained model", value=True)
    else:
        st.warning("⚠️ Model not trained yet")
        st.caption("Run: `python model_trainer.py`")
        use_trained_model = False
    st.session_state["use_trained_model"] = use_trained_model
    st.markdown("---")
    if st.button("🗑️ Clear History", use_container_width=True):
        clear_sessions()
        st.rerun()
    if sessions_sb:
        csv_data = export_sessions_csv(sessions_sb)
        st.download_button("📥 Export CSV", data=csv_data, file_name="sessions.csv", mime="text/csv", use_container_width=True)

# ============================================================
# HERO
# ============================================================
st.markdown("""
<div class="hero">
<div class="hero-title">🛡️ Insurance Sales Co-Pilot</div>
<div class="hero-sub">Your AI-powered wingman for every client conversation</div>
<span class="chip">✨ Claude AI</span>
<span class="chip">🎤 Voice Input</span>
<span class="chip">📊 Smart Scoring</span>
<span class="chip">🔁 Live Chat Sim</span>
<span class="chip">📄 PDF Export</span>
<span class="chip">🏆 Leaderboard</span>
<span class="chip">📈 Win Tracker</span>
</div>
""", unsafe_allow_html=True)

# ============================================================
# TABS
# ============================================================
tab_analyze, tab_chat, tab_history, tab_dashboard = st.tabs([
    "🔍 Analyze Client", "💬 Chat Simulator", "📋 Session History", "📈 Dashboard"
])

# ============================================================
# ── HELPER: Policy Detail Modal ────────────────────────────
# ============================================================



# ============================================================
# ── TAB 1: ANALYZE CLIENT ──────────────────────────────────
# ============================================================
with tab_analyze:

    col_in, col_out = st.columns([1, 1.4], gap="large")

    with col_in:
        st.markdown('<div class="stitle">Client Details</div>', unsafe_allow_html=True)
        client_name    = st.text_input("Name", placeholder="e.g. Rahul Sharma", label_visibility="collapsed")
        client_age_str = st.text_input("Age (optional, improves scoring)", placeholder="e.g. 35", label_visibility="visible")
        client_age     = int(client_age_str) if client_age_str.strip().isdigit() else None

        st.markdown('<div class="stitle" style="margin-top:14px;">🎤 Voice Input</div>', unsafe_allow_html=True)
        show_mic = st.toggle("Enable microphone (Chrome/Edge)", value=False)
        if show_mic:
            components.html(get_speech_widget(), height=120)

        st.markdown('<div class="stitle" style="margin-top:14px;">💬 Conversation Notes</div>', unsafe_allow_html=True)
        client_text = st.text_area(
            "Notes", height=200, label_visibility="collapsed",
            key="notes",
            placeholder='Type or speak using the mic above — transcript goes directly here.'
        )

        analyze_btn = st.button("🔍 Analyze & Recommend", use_container_width=True, type="primary")

        st.markdown('<div class="stitle" style="margin-top:12px;">⚡ Quick Examples</div>', unsafe_allow_html=True)
        e1, e2, e3, e4, e5, e6 = st.columns(6)
        example_text = ""
        examples = {
            "👨‍👩‍👧": "Rahul is 35, married with 2 kids. His wife doesn't work. He's the sole breadwinner. Worried about protecting his family. Budget Rs.1200/month.",
            "🏥": "Client is 42, diabetic, wants health insurance. Recent father had a major surgery. Worried about hospital bills. Needs cashless cover urgently.",
            "📈": "Client is 40, wants to invest Rs.3000/month for retirement. Wants good returns and tax benefits. Planning to retire at 60.",
            "🎓": "Client has a 4-year-old daughter. Very anxious about education costs. Asking specifically about child future plans. Can pay Rs.1000/month.",
            "🏢": "Client owns a 20-person IT firm. Wants to protect the business if key employees leave or something happens to him. Also needs group health.",
            "🛡️": "Client is 28, just started earning. Wants cheapest possible life insurance. Basic cover, low premium. Term plan only.",
        }
        for col, (emoji, txt) in zip([e1,e2,e3,e4,e5,e6], examples.items()):
            with col:
                if st.button(emoji, use_container_width=True, help=txt[:40]):
                    example_text = txt

        if example_text:
            st.session_state["prefill"] = example_text
        if "prefill" in st.session_state:
            client_text = st.session_state["prefill"]
            st.caption("📋 Example loaded — click Analyze above")

    with col_out:
        st.markdown('<div class="stitle">AI Analysis & Recommendations</div>', unsafe_allow_html=True)

        # ── Always run if fresh, or restore from cache after back-navigation ──
        fresh = analyze_btn or ("prefill" in st.session_state)
        has_cache = bool(st.session_state.get("last_analysis"))

        if fresh:
            active_text = client_text.strip() or st.session_state.get("prefill", "")
            if not active_text:
                st.warning("Please enter client notes first.")
            else:
                use_model = st.session_state.get("use_trained_model", False)
                with st.spinner("🧠 Running trained model..." if use_model else "🤖 Analyzing..."):
                    if use_model:
                        model_result = model_recommend(active_text, api_key=api_key or None)
                        analysis     = analyze_client(active_text, api_key=api_key or None)
                        if model_result:
                            analysis["intent"]       = model_result.get("intent", analysis.get("intent"))
                            analysis["model_result"] = model_result
                    else:
                        analysis     = analyze_client(active_text, api_key=api_key or None)

                # Save everything to cache
                intent      = analysis.get("intent", "family")
                if analysis.get("model_result") and analysis["model_result"].get("ranked"):
                    recommended = analysis["model_result"]["ranked"][:max_policies]
                    for p in recommended:
                        if "smart_score" not in p:
                            p["smart_score"] = p.get("fit_score", p.get("profit_score", 0))
                else:
                    recommended = recommend_policy(intent, max_results=max_policies, client_age=client_age)

                st.session_state["last_analysis"]    = analysis
                st.session_state["last_recommended"] = recommended
                st.session_state["last_active_text"] = active_text
                save_session(client_name or "Unknown", active_text, analysis, recommended)
                if "prefill" in st.session_state:
                    del st.session_state["prefill"]

        elif has_cache:
            # Restore from cache — no spinner, instant
            analysis    = st.session_state["last_analysis"]
            recommended = st.session_state["last_recommended"]
            active_text = st.session_state.get("last_active_text", "")
            intent      = analysis.get("intent", "family")

        if (fresh and active_text.strip()) or has_cache:
            analysis    = st.session_state.get("last_analysis", {})
            recommended = st.session_state.get("last_recommended", [])
            intent      = analysis.get("intent", "family")
            mode        = analysis.get("mode", "rule-based")
            confidence  = analysis.get("confidence", "medium")
            conf_pct    = analysis.get("confidence_pct", 0)
            urgency     = analysis.get("urgency", "low")
            urg_score   = analysis.get("urgency_score", 0)
            sentiment   = analysis.get("sentiment", "neutral")
            persona     = analysis.get("persona", "general_client")
            signals     = analysis.get("key_signals", [])
            summary     = analysis.get("summary", "")
            secondary   = analysis.get("secondary_intents", [])

            intent_info  = get_intent_label(intent)
            persona_info = get_persona_label(persona)

            ic = intent_info["color"]
            ig = intent_info["gradient"]
            ie = intent_info["emoji"]
            il = intent_info["label"]

            mode_badge = '<span class="badge-ai">✨ Claude AI</span>' if "claude" in mode else '<span class="badge-rule">⚙️ Rule-based</span>'
            urg_color  = "#e85d4a" if urgency == "high" else "#f5a623" if urgency == "medium" else "#50c878"
            sent_emoji = "😰" if sentiment == "anxious" else "😟" if sentiment == "concerned" else "😊" if sentiment == "positive" else "😐"

            secondary_parts = []
            for s in secondary:
                s_info = get_intent_label(s)
                secondary_parts.append(
                    f'<span class="badge-pill" style="background:rgba(74,90,237,0.08);color:#4a5aed;border:1px solid rgba(74,90,237,0.2);">+ {s_info["emoji"]} {s_info["label"]}</span>'
                )
            secondary_html = "".join(secondary_parts)
            summary_block  = f'<div class="intent-sub">{summary}</div>' if summary else ""
            profile_block  = f'<div style="font-size:0.8rem;margin-top:8px;opacity:0.65;">{analysis["client_profile"]}</div>' if analysis.get("client_profile") else ""

            st.markdown(f"""
<div class="intent-banner" style="background:{ig};border-color:{ic}50;border-left-color:{ic};">
<div class="intent-title" style="color:{ic};">{ie} {il} &nbsp;{mode_badge}</div>
<div class="intent-sub" style="color:{ic}80;">
Confidence: <strong>{confidence.upper()}</strong> {conf_pct}%
&nbsp;·&nbsp; <span style="color:{urg_color};">⚡ {urgency.upper()} urgency ({urg_score}/10)</span>
&nbsp;·&nbsp; {sent_emoji} {sentiment.title()}
</div>
{summary_block}{profile_block}
<div style="margin-top:10px;">{secondary_html}</div>
</div>
""", unsafe_allow_html=True)

            pe = persona_info["emoji"]
            pl = persona_info["label"]
            chips_html = "".join([f'<span class="hi-pill">🔍 {s}</span>' for s in signals])
            st.markdown(f"""
<div style="display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-bottom:18px;">
<span style="background:#0c1528;border:1px solid #1e2a50;border-radius:20px;padding:4px 14px;font-size:0.76rem;color:#6878b8;">{pe} {pl}</span>
{chips_html}
</div>
""", unsafe_allow_html=True)

            # ---- POLICIES ----
            st.markdown('<div class="stitle">Recommended Policies</div>', unsafe_allow_html=True)

            model_res = analysis.get("model_result")
            if model_res and model_res.get("ranked"):
                model_mode_badge = '<span style="background:linear-gradient(90deg,#7b2ff7,#f107a3);color:white;padding:3px 10px;border-radius:12px;font-size:0.7rem;font-weight:700;">🧠 TRAINED MODEL</span>'
                st.markdown(model_mode_badge, unsafe_allow_html=True)
                reasoning = model_res.get("reasoning", "")
                if reasoning:
                    st.markdown(f'<div style="background:#0a0618;border:1px solid #3a1a6a;border-radius:10px;padding:12px 14px;margin:8px 0 12px;color:#b080f0;font-size:0.83rem;line-height:1.6;">💡 {reasoning}</div>', unsafe_allow_html=True)

            if not recommended:
                st.error("No policies found.")
            else:
                rank_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
                for i, policy in enumerate(recommended):
                    tier        = get_profit_tier(policy["profit_score"])
                    smart_score = policy.get("smart_score", policy["profit_score"])
                    wrap_class  = "policy-wrap top" if i == 0 else "policy-wrap"
                    rank_e      = rank_emojis[i] if i < len(rank_emojis) else f"#{i+1}"
                    best_b      = '<span style="background:#0d1440;border:1px solid #2d3561;border-radius:8px;padding:2px 8px;font-size:0.68rem;color:#4a5aed;font-weight:700;margin-left:8px;">BEST PICK</span>' if i == 0 else ""
                    badge_b     = f'<span style="background:#0c1020;border:1px solid {tier["color"]}40;border-radius:8px;padding:2px 8px;font-size:0.68rem;color:{tier["color"]};font-weight:700;">{tier["tier"]}</span>'
                    extra_badge = f'<span style="background:rgba(74,90,237,0.1);border:1px solid rgba(74,90,237,0.25);border-radius:8px;padding:2px 8px;font-size:0.68rem;color:#6878b8;">{policy["badge"]}</span>' if policy.get("badge") else ""
                    tc          = tier["color"]
                    highlights_h = "".join([f'<span class="hi-pill">✓ {h}</span>' for h in policy.get("highlights", [])])
                    ideal_b     = f'<div style="color:#3a4570;font-size:0.76rem;margin-top:8px;">🎯 {policy.get("ideal_for","")}</div>' if policy.get("ideal_for") else ""
                    p_name      = policy["name"]
                    p_desc      = policy["description"]
                    p_premium   = policy["premium"]
                    p_cover     = policy["coverage"]
                    p_profit    = policy["profit_score"]
                    p_claim     = policy.get("claim_settlement", 0)

                    st.markdown(f"""
<div class="{wrap_class}">
<div class="policy-name">{rank_e} {p_name} {best_b}</div>
<div class="policy-desc">{p_desc}</div>
<div style="margin-bottom:10px;">
{badge_b} {extra_badge}
<span class="badge-pill" style="background:rgba(80,200,120,0.08);color:#50c878;border:1px solid rgba(80,200,120,0.2);">💰 ${p_premium:,}/yr</span>
<span class="badge-pill" style="background:rgba(74,90,237,0.08);color:#8090e8;border:1px solid rgba(74,90,237,0.2);">🛡️ ${p_cover:,}</span>
<span class="badge-pill" style="background:rgba(100,217,248,0.08);color:#64d9f8;border:1px solid rgba(100,217,248,0.2);">✅ {p_claim}% claims</span>
</div>
<div style="margin-bottom:10px;">{highlights_h}</div>
<div style="display:flex;gap:16px;margin-top:12px;">
<div style="flex:1;">
<div style="display:flex;justify-content:space-between;margin-bottom:4px;">
<span style="color:#3a4570;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;">PROFIT</span>
<span style="color:#c8d8ff;font-weight:700;font-size:0.82rem;">{p_profit}</span>
</div>
<div class="score-bar-track"><div class="score-bar-fill" style="width:{p_profit}%;background:{tc};"></div></div>
</div>
<div style="flex:1;">
<div style="display:flex;justify-content:space-between;margin-bottom:4px;">
<span style="color:#3a4570;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;">SMART</span>
<span style="color:#64d9f8;font-weight:700;font-size:0.82rem;">{smart_score}</span>
</div>
<div class="score-bar-track"><div class="score-bar-fill" style="width:{smart_score}%;background:linear-gradient(90deg,#4a5aed,#64d9f8);"></div></div>
</div>
</div>
{ideal_b}
</div>
""", unsafe_allow_html=True)

                    def _go_detail(p=policy):
                        st.session_state["selected_policy"] = p
                        st.session_state["current_page"] = "policy_detail"
                    st.button(
                        f"📋 Full Details — {p_name}",
                        key=f"det_{i}_{p_name}",
                        use_container_width=True,
                        on_click=_go_detail
                    )

                # ---- COMPARISON TABLE ----
                if show_comparison and len(recommended) > 1:
                    with st.expander("📊 Side-by-Side Comparison", expanded=False):
                        matrix = build_comparison_matrix(recommended)
                        import pandas as pd
                        df = pd.DataFrame(matrix)
                        df = df.set_index("Policy Name").T
                        st.dataframe(df, use_container_width=True)

                # ---- DEAL VALUE ----
                if show_commission:
                    dv       = calculate_deal_value(recommended)
                    fyc      = dv["first_year_commission"]
                    ltv      = dv["lifetime_value"]
                    tot      = dv["total_annual_premium"]
                    rate     = dv["commission_rate"]
                    avg_term = dv["avg_policy_term"]
                    st.markdown(f"""
<div class="commission-box">
<div style="color:#2a6840;font-size:0.68rem;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:4px;">DEAL VALUE</div>
<div class="commission-amount">${fyc:,}</div>
<div class="commission-sub">First-year commission ({rate}) on ${tot:,} premium</div>
<div style="margin-top:12px;display:flex;justify-content:center;gap:24px;">
<div style="text-align:center;">
<div style="color:#2a6840;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;">Lifetime Value</div>
<div style="color:#50c878;font-weight:700;font-size:1.1rem;">${ltv:,}</div>
</div>
<div style="text-align:center;">
<div style="color:#2a6840;font-size:0.68rem;text-transform:uppercase;letter-spacing:1px;">Avg Term</div>
<div style="color:#50c878;font-weight:700;font-size:1.1rem;">{avg_term} yrs</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)

                # ---- BUNDLES ----
                if show_bundles:
                    bundles = get_bundle_suggestions(intent)
                    if bundles:
                        st.markdown('<div class="stitle" style="margin-top:16px;">💼 Bundle Opportunities</div>', unsafe_allow_html=True)
                        for intent_key, title, desc in bundles:
                            bie = get_intent_label(intent_key)["emoji"]
                            st.markdown(f"""
<div class="bundle-card">
<div class="bundle-title">{bie} {title}</div>
<div class="bundle-desc">{desc}</div>
</div>
""", unsafe_allow_html=True)

            # ---- COACHING ----
            with st.expander("🎓 Live Coaching — What to say", expanded=True):
                ai_tips = analysis.get("coaching_tips", [])
                tips    = ai_tips if ai_tips else COACHING_TIPS.get(intent, [])
                if ai_tips:
                    st.markdown('<span class="badge-ai">✨ AI-Generated Tips</span>', unsafe_allow_html=True)
                    st.markdown("")
                tips_html = "".join([f'<div class="coach-item">{t}</div>' for t in tips])
                st.markdown(f'<div class="coach-wrap">{tips_html}</div>', unsafe_allow_html=True)

                opening = analysis.get("opening_line", "")
                if opening:
                    st.markdown(f"""
<div style="background:#060e1e;border:1px solid #1e2a50;border-radius:12px;padding:14px 16px;margin-top:12px;">
<div style="color:#4a5aed;font-size:0.68rem;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;">✨ Opening Line</div>
<div style="color:#c0cce8;font-size:0.9rem;font-style:italic;">"{opening}"</div>
</div>
""", unsafe_allow_html=True)

                deal_strat = analysis.get("deal_strategy", "")
                if deal_strat:
                    st.markdown(f"""
<div style="background:#060e1e;border:1px solid #1e2a50;border-radius:12px;padding:14px 16px;margin-top:10px;">
<div style="color:#f5a623;font-size:0.68rem;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:6px;">🎯 Deal Strategy</div>
<div style="color:#9090b0;font-size:0.84rem;line-height:1.6;">{deal_strat}</div>
</div>
""", unsafe_allow_html=True)

            # ---- OBJECTIONS ----
            with st.expander("🥊 Objection Handler"):
                obj_list = analysis.get("objections_to_expect", list(OBJECTION_HANDLERS.keys())[:3])
                st.markdown("<p style='color:#3a4570;font-size:0.8rem;margin-bottom:10px;'>Likely objections for this client:</p>", unsafe_allow_html=True)
                for obj in obj_list:
                    obj_str = str(obj)
                    handler = OBJECTION_HANDLERS.get(obj_str.lower(), "Acknowledge, empathize, then pivot to the specific benefit most relevant to this client's situation.")
                    st.markdown(f"""
<div class="obj-card">
<div class="obj-q">❓ "{obj_str.title()}"</div>
<div class="obj-a">→ {handler}</div>
</div>
""", unsafe_allow_html=True)

            # ---- PDF ----
            st.markdown('<div class="stitle" style="margin-top:18px;">📄 Export</div>', unsafe_allow_html=True)
            if REPORTLAB_AVAILABLE:
                pdf_bytes = generate_report(
                    client_name=client_name or "Valued Client",
                    analysis_result=analysis,
                    recommended_policies=recommended,
                    agent_name=agent_name
                )
                if pdf_bytes:
                    safe = (client_name or "client").replace(" ", "_").lower()
                    st.download_button("📥 Download Client Proposal PDF", data=pdf_bytes,
                                       file_name=f"proposal_{safe}.pdf", mime="application/pdf",
                                       use_container_width=True)
            else:
                st.info("Install reportlab for PDF: `pip install reportlab`")

        else:
            st.markdown("""
<div style="text-align:center;padding:80px 20px;">
<div style="font-size:3.5rem;">🤖</div>
<div style="font-family:'Plus Jakarta Sans',sans-serif;color:#a0b0d0;font-size:1.1rem;font-weight:700;margin-top:16px;">Ready to analyze</div>
<div style="color:#2a3560;font-size:0.85rem;margin-top:8px;line-height:1.8;">Enter client notes on the left<br>and click <strong style="color:#4a5aed;">Analyze &amp; Recommend</strong></div>
</div>
""", unsafe_allow_html=True)

# ── TAB 2: CHAT SIMULATOR ──────────────────────────────────
# ============================================================
with tab_chat:
    st.markdown('<div class="stitle">Live Client Conversation Simulator</div>', unsafe_allow_html=True)
    st.markdown("<p style='color:#3a4570;font-size:0.84rem;margin-bottom:16px;'>Simulate a real sales conversation. Type as the client — the AI acts as your co-pilot and tells you what to say next.</p>", unsafe_allow_html=True)

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "chat_analysis" not in st.session_state:
        st.session_state["chat_analysis"] = None

    chat_col, advice_col = st.columns([1.1, 1], gap="large")

    with chat_col:
        st.markdown('<div class="stitle">Conversation</div>', unsafe_allow_html=True)
        chat_display = ""
        for msg in st.session_state["chat_history"]:
            if msg["role"] == "client":
                chat_display += f'<div style="text-align:right;"><div class="chat-meta" style="text-align:right;">Client</div><div class="chat-bubble-client">{msg["text"]}</div></div>'
            else:
                chat_display += f'<div><div class="chat-meta">Co-Pilot suggestion</div><div class="chat-bubble-agent">{msg["text"]}</div></div>'

        if chat_display:
            st.markdown(f'<div style="max-height:340px;overflow-y:auto;padding:4px 0;margin-bottom:14px;">{chat_display}</div>', unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="text-align:center;padding:40px;background:#0c1020;border:1px dashed #161e35;border-radius:14px;margin-bottom:14px;">
<div style="font-size:2rem;">💬</div>
<div style="color:#2a3560;font-size:0.85rem;margin-top:8px;">Start the conversation below</div>
</div>
""", unsafe_allow_html=True)

        chat_input = st.text_input("Client says...", placeholder='e.g. "I have two kids and I\'m worried about the future"', label_visibility="collapsed", key="chat_input_box")
        c_send, c_clear = st.columns([3, 1])
        with c_send:
            send_btn = st.button("➤ Send as Client", use_container_width=True, type="primary")
        with c_clear:
            if st.button("🗑️ Clear", use_container_width=True):
                st.session_state["chat_history"] = []
                st.session_state["chat_analysis"] = None
                st.rerun()

        if send_btn and chat_input.strip():
            st.session_state["chat_history"].append({"role": "client", "text": chat_input.strip()})
            full_convo = " ".join([m["text"] for m in st.session_state["chat_history"] if m["role"] == "client"])
            with st.spinner("🤖 Co-Pilot thinking..."):
                chat_analysis = analyze_client(full_convo, api_key=api_key or None)
                st.session_state["chat_analysis"] = chat_analysis
            intent_chat = chat_analysis.get("intent", "family")
            opening     = chat_analysis.get("opening_line", "")
            tips_chat   = chat_analysis.get("coaching_tips", COACHING_TIPS.get(intent_chat, []))
            if opening and len(st.session_state["chat_history"]) <= 3:
                agent_response = f"💡 Suggested response: {opening}"
            elif tips_chat:
                tip_idx = min(len(st.session_state["chat_history"]) // 2, len(tips_chat) - 1)
                agent_response = f"💡 {tips_chat[tip_idx]}"
            else:
                agent_response = "💡 Listen actively and ask: 'Can you tell me more about what concerns you most?'"
            st.session_state["chat_history"].append({"role": "agent", "text": agent_response})
            st.rerun()

    with advice_col:
        st.markdown('<div class="stitle">Real-Time Intelligence</div>', unsafe_allow_html=True)
        chat_analysis = st.session_state.get("chat_analysis")
        if chat_analysis:
            intent_chat = chat_analysis.get("intent", "family")
            iinfo_chat  = get_intent_label(intent_chat)
            ic2  = iinfo_chat["color"]
            ie2  = iinfo_chat["emoji"]
            il2  = iinfo_chat["label"]
            conf2 = chat_analysis.get("confidence", "medium")
            urg2  = chat_analysis.get("urgency", "low")
            urg_c2 = "#e85d4a" if urg2 == "high" else "#f5a623" if urg2 == "medium" else "#50c878"
            st.markdown(f"""
<div class="card accent" style="margin-bottom:14px;">
<div style="font-family:'Plus Jakarta Sans',sans-serif;font-size:1rem;font-weight:700;color:{ic2};">{ie2} {il2}</div>
<div style="color:#3a4570;font-size:0.78rem;margin-top:4px;">{conf2.upper()} confidence &nbsp;·&nbsp; <span style="color:{urg_c2};">⚡ {urg2.upper()} urgency</span></div>
</div>
""", unsafe_allow_html=True)
            rec_chat = recommend_policy(intent_chat, max_results=2)
            st.markdown('<div class="stitle">Top Policies to Mention</div>', unsafe_allow_html=True)
            for p in rec_chat:
                tier2    = get_profit_tier(p["profit_score"])
                tc2      = tier2["color"]
                cp_name  = p["name"]
                cp_prem  = p["premium"]
                cp_cov   = p["coverage"]
                cp_score = p["profit_score"]
                st.markdown(f"""
<div class="card" style="padding:12px 14px;margin-bottom:8px;">
<div style="font-weight:700;color:#c8d8ff;font-size:0.88rem;">{cp_name}</div>
<div style="color:#3a4570;font-size:0.76rem;margin-top:3px;">${cp_prem:,}/yr · ${cp_cov:,} cover</div>
<div style="display:flex;align-items:center;gap:8px;margin-top:8px;">
<div style="flex:1;background:#0d1228;border-radius:10px;height:4px;">
<div style="width:{cp_score}%;background:{tc2};height:100%;border-radius:10px;"></div>
</div>
<span style="color:{tc2};font-size:0.74rem;font-weight:700;">{cp_score}</span>
</div>
</div>
""", unsafe_allow_html=True)
            objs = chat_analysis.get("objections_to_expect", list(OBJECTION_HANDLERS.keys())[:2])
            if objs:
                st.markdown('<div class="stitle" style="margin-top:12px;">⚠️ Objection Watch</div>', unsafe_allow_html=True)
                for obj in objs[:2]:
                    obj_str = str(obj)
                    st.markdown(f"""
<div style="background:#0e0610;border:1px solid #2a1a30;border-radius:10px;padding:10px 12px;margin-bottom:6px;">
<div style="color:#c070e0;font-size:0.8rem;">❓ "{obj_str.title()}"</div>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="text-align:center;padding:60px 20px;background:#0c1020;border:1px dashed #161e35;border-radius:14px;">
<div style="font-size:2.5rem;">👂</div>
<div style="color:#2a3560;font-size:0.85rem;margin-top:10px;">Start chatting to see live intelligence</div>
</div>
""", unsafe_allow_html=True)


# ============================================================
# ── TAB 3: SESSION HISTORY ─────────────────────────────────
# ============================================================
with tab_history:
    sessions = load_sessions()
    if not sessions:
        st.markdown("""
<div style="text-align:center;padding:70px 20px;">
<div style="font-size:3rem;">📋</div>
<div style="color:#a0b0d0;font-size:1.05rem;margin-top:14px;">No sessions yet</div>
<div style="color:#2a3560;font-size:0.85rem;margin-top:6px;">Analyze a client in the first tab to start.</div>
</div>
""", unsafe_allow_html=True)
    else:
        stats = get_performance_stats(sessions)
        h1, h2, h3, h4 = st.columns(4)
        for col, icon, label, val, sub in [
            (h1, "💰", "Total Commission",  f"${stats['total_commission']:,}",  "earned"),
            (h2, "🏆", "Win Rate",           f"{stats['win_rate']}%",            f"{stats['deals_won']} deals won"),
            (h3, "📊", "Avg Smart Score",    str(stats['avg_smart_score']),      "/ 100"),
            (h4, "🔥", "Current Streak",     f"{stats['daily_streak']} days",    "in a row"),
        ]:
            with col:
                st.markdown(f"""
<div class="kpi">
<div class="kpi-icon">{icon}</div>
<div class="kpi-label">{label}</div>
<div class="kpi-value">{val}</div>
<div class="kpi-sub">{sub}</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        filter_col, sort_col = st.columns([2, 1])
        with filter_col:
            filter_intent = st.selectbox("Filter by intent", ["All", "family", "health", "investment", "child", "business", "term"])
        with sort_col:
            sort_by = st.selectbox("Sort by", ["Newest", "Highest Commission", "Highest Score"])
        filtered = sessions if filter_intent == "All" else [s for s in sessions if s.get("intent") == filter_intent]
        if sort_by == "Highest Commission":
            filtered = sorted(filtered, key=lambda s: s.get("estimated_commission", 0), reverse=True)
        elif sort_by == "Highest Score":
            filtered = sorted(filtered, key=lambda s: s.get("top_profit_score", 0), reverse=True)
        else:
            filtered = list(reversed(filtered))
        st.markdown('<div class="stitle">Sessions</div>', unsafe_allow_html=True)
        for session in filtered:
            iinfo  = get_intent_label(session.get("intent", "family"))
            se     = iinfo["emoji"]
            sl     = iinfo["label"]
            status = session.get("deal_status", "pending")
            status_badge = '<span class="badge-won">✅ WON</span>' if status == "won" else '<span class="badge-lost">❌ LOST</span>' if status == "lost" else '<span class="badge-pend">⏳ PENDING</span>'
            surg   = session.get("urgency", "low")
            urg_c  = "#e85d4a" if surg == "high" else "#f5a623" if surg == "medium" else "#50c878"
            sp       = session["total_premium_value"]
            sc       = session["estimated_commission"]
            s_name   = session["client_name"]
            s_date   = session["date"]
            s_time   = session["time"]
            s_snip   = session["conversation_snippet"]
            s_policy = session["top_policy"]
            st.markdown(f"""
<div class="sess-card">
<div style="display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:8px;">
<div>
<span style="color:#c8d8ff;font-weight:700;font-size:0.95rem;">{se} {s_name}</span>
<span style="color:#2a3560;font-size:0.76rem;margin-left:10px;">{s_date} · {s_time}</span>
</div>
<div>{status_badge}</div>
</div>
<div style="color:#3a4570;font-size:0.8rem;margin-bottom:10px;line-height:1.5;">{s_snip}</div>
<div style="display:flex;gap:6px;flex-wrap:wrap;">
<span class="badge-pill" style="background:rgba(74,90,237,0.08);color:#6878b8;border:1px solid rgba(74,90,237,0.2);">{sl}</span>
<span class="badge-pill" style="background:rgba(80,200,120,0.08);color:#50c878;border:1px solid rgba(80,200,120,0.2);">💰 ${sp:,} premium</span>
<span class="badge-pill" style="background:rgba(80,200,120,0.05);color:#308050;border:1px solid rgba(80,200,120,0.15);">+${sc:,} commission</span>
<span class="badge-pill" style="background:#0e0610;color:{urg_c};border:1px solid {urg_c}30;">⚡ {surg} urgency</span>
<span class="badge-pill" style="background:rgba(245,166,35,0.08);color:#a07020;border:1px solid rgba(245,166,35,0.2);">🏆 {s_policy}</span>
</div>
</div>
""", unsafe_allow_html=True)
            win_col, loss_col, _ = st.columns([1, 1, 4])
            with win_col:
                if st.button("✅ Won", key=f"won_{session['id']}", use_container_width=True):
                    update_deal_status(session["id"], "won")
                    st.rerun()
            with loss_col:
                if st.button("❌ Lost", key=f"lost_{session['id']}", use_container_width=True):
                    update_deal_status(session["id"], "lost")
                    st.rerun()


# ============================================================
# ── TAB 4: DASHBOARD ───────────────────────────────────────
# ============================================================
with tab_dashboard:
    sessions = load_sessions()
    stats    = get_performance_stats(sessions)
    grade    = get_performance_grade(stats["total_commission"])
    if not sessions:
        st.markdown("""
<div style="text-align:center;padding:70px 20px;">
<div style="font-size:3rem;">📈</div>
<div style="color:#a0b0d0;font-size:1.05rem;margin-top:14px;">No data yet</div>
<div style="color:#2a3560;font-size:0.85rem;margin-top:6px;">Analyze some clients to see your stats.</div>
</div>
""", unsafe_allow_html=True)
    else:
        gc  = grade["color"]
        gl  = grade["grade"]
        gt  = grade["title"]
        streak       = stats["daily_streak"]
        d_sessions   = stats["total_sessions"]
        d_commission = stats["total_commission"]
        d_winrate    = stats["win_rate"]
        st.markdown(f"""
<div style="background:linear-gradient(135deg,#080e20,#060a18);border:1px solid {gc}30;border-radius:18px;padding:24px 32px;margin-bottom:22px;display:flex;align-items:center;gap:24px;">
<div style="text-align:center;">
<div class="grade-badge" style="color:{gc};border-color:{gc};font-size:2.5rem;width:72px;height:72px;line-height:72px;">{gl}</div>
</div>
<div>
<div style="font-size:1.5rem;font-weight:800;color:{gc};">{gt}</div>
<div style="color:#3a4570;font-size:0.85rem;margin-top:4px;">{d_sessions} sessions · ${d_commission:,} earned · {d_winrate}% win rate · {streak}🔥 streak</div>
</div>
<div style="margin-left:auto;text-align:center;">
<div class="streak-box">
<div class="streak-number">{streak}</div>
<div class="streak-label">Day Streak</div>
</div>
</div>
</div>
""", unsafe_allow_html=True)
        k1, k2, k3, k4, k5, k6 = st.columns(6)
        for col, icon, label, val in [
            (k1, "📅", "Today",          str(stats["sessions_today"])),
            (k2, "👥", "Total Sessions", str(stats["total_sessions"])),
            (k3, "💵", "Commission",     f"${stats['total_commission']:,}"),
            (k4, "🏆", "Win Rate",       f"{stats['win_rate']}%"),
            (k5, "🎯", "Avg Score",      f"{stats['avg_smart_score']}"),
            (k6, "🔝", "Top Category",   stats["top_intent"].title()),
        ]:
            with col:
                st.markdown(f"""
<div class="kpi">
<div class="kpi-icon">{icon}</div>
<div class="kpi-label">{label}</div>
<div class="kpi-value">{val}</div>
</div>
""", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        dcol1, dcol2 = st.columns([1, 1], gap="large")
        with dcol1:
            st.markdown('<div class="stitle">Intent Distribution</div>', unsafe_allow_html=True)
            breakdown = stats.get("intent_breakdown", {})
            if breakdown:
                import pandas as pd
                st.bar_chart(pd.DataFrame({"Sessions": breakdown}), height=200)
                total_s = stats["total_sessions"]
                for ik, cnt in sorted(breakdown.items(), key=lambda x: x[1], reverse=True):
                    pct      = round((cnt / total_s) * 100)
                    info     = get_intent_label(ik)
                    ic_d     = info["color"]
                    ik_emoji = info["emoji"]
                    ik_name  = ik.title()
                    st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
<span style="min-width:130px;color:#8090b0;font-size:0.82rem;">{ik_emoji} {ik_name}</span>
<div style="flex:1;background:#0d1228;border-radius:10px;height:7px;">
<div style="width:{pct}%;background:{ic_d};height:100%;border-radius:10px;"></div>
</div>
<span style="color:{ic_d};font-size:0.78rem;min-width:60px;">{cnt} ({pct}%)</span>
</div>
""", unsafe_allow_html=True)
            st.markdown('<div class="stitle" style="margin-top:20px;">Deal Status</div>', unsafe_allow_html=True)
            total_d = max(stats["total_sessions"], 1)
            for label_d, cnt_d, color_d in [
                ("Won",     stats["deals_won"],     "#50c878"),
                ("Lost",    stats["deals_lost"],    "#e85d4a"),
                ("Pending", stats["deals_pending"], "#f5a623"),
            ]:
                pct_d = round((cnt_d / total_d) * 100)
                st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
<span style="min-width:70px;color:#8090b0;font-size:0.82rem;">{label_d}</span>
<div style="flex:1;background:#0d1228;border-radius:10px;height:7px;">
<div style="width:{pct_d}%;background:{color_d};height:100%;border-radius:10px;"></div>
</div>
<span style="color:{color_d};font-size:0.78rem;min-width:60px;">{cnt_d} ({pct_d}%)</span>
</div>
""", unsafe_allow_html=True)
        with dcol2:
            st.markdown('<div class="stitle">Recent Sessions</div>', unsafe_allow_html=True)
            for s in list(reversed(sessions))[:8]:
                info_d  = get_intent_label(s.get("intent","family"))
                score_d = s.get("top_smart_score", s.get("top_profit_score", 0))
                comm_d  = s.get("estimated_commission", 0)
                ic_d2   = info_d["color"]
                ds_name   = s["client_name"]
                ds_date   = s["date"]
                ds_policy = s["top_policy"]
                ds_emoji  = info_d["emoji"]
                st.markdown(f"""
<div style="background:#0c1020;border:1px solid #161e35;border-radius:10px;padding:11px 14px;margin-bottom:7px;">
<div style="display:flex;justify-content:space-between;margin-bottom:5px;">
<span style="color:#c8d8ff;font-size:0.86rem;font-weight:700;">{ds_emoji} {ds_name}</span>
<span style="color:#2a3560;font-size:0.74rem;">{ds_date}</span>
</div>
<div style="color:#3a4570;font-size:0.76rem;margin-bottom:6px;">{ds_policy}</div>
<div style="display:flex;align-items:center;gap:8px;">
<div style="flex:1;background:#0d1228;border-radius:8px;height:4px;">
<div style="width:{score_d}%;background:linear-gradient(90deg,#4a5aed,#64d9f8);height:100%;border-radius:8px;"></div>
</div>
<span style="color:#64d9f8;font-size:0.76rem;">{score_d}</span>
<span style="color:#50c878;font-size:0.76rem;">${comm_d:,}</span>
</div>
</div>
""", unsafe_allow_html=True)
