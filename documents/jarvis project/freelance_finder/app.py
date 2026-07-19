import streamlit as st
from db import init_db, get_leads, update_proposal, update_status
from fetch_leads import fetch_all
from proposal_gen import generate_proposal

st.set_page_config(page_title="Freelance Lead Finder", layout="wide")
init_db()

st.title("🎯 Freelance Lead Finder & Proposal Drafter")
st.caption("Runs locally on your machine. Finds leads, drafts proposals — you review and send manually.")

col1, col2 = st.columns([1, 3])
with col1:
    if st.button("🔄 Fetch new leads now"):
        with st.spinner("Fetching from RemoteOK, WeWorkRemotely, Upwork RSS..."):
            n = fetch_all()
        st.success(f"Found {n} new lead(s).")

status_filter = st.selectbox("Show status", ["new", "proposal_drafted", "applied", "ignored", "all"])
leads = get_leads(None if status_filter == "all" else status_filter)

st.write(f"**{len(leads)} lead(s)**")

for lead in leads:
    with st.expander(f"[{lead['source']}] {lead['title']}"):
        st.write(lead["summary"])
        st.markdown(f"[Open original posting]({lead['link']})")

        if lead["proposal"]:
            st.text_area("Draft proposal", lead["proposal"], height=180, key=f"prop_{lead['id']}")
        else:
            if st.button("✍️ Draft proposal with AI", key=f"gen_{lead['id']}"):
                with st.spinner("Generating..."):
                    draft = generate_proposal(lead["title"], lead["summary"])
                update_proposal(lead["id"], draft)
                st.rerun()

        c1, c2, c3 = st.columns(3)
        with c1:
            if st.button("✅ Mark applied", key=f"applied_{lead['id']}"):
                update_status(lead["id"], "applied")
                st.rerun()
        with c2:
            if st.button("🚫 Ignore", key=f"ignore_{lead['id']}"):
                update_status(lead["id"], "ignored")
                st.rerun()
        with c3:
            if lead["proposal"] and st.button("🔁 Regenerate", key=f"regen_{lead['id']}"):
                update_proposal(lead["id"], None)
                st.rerun()

st.divider()
st.caption(
    "Note: This tool does NOT auto-submit proposals — Upwork/Fiverr ban accounts for automated bidding. "
    "You always click send yourself. To fully automate 'fetch new leads', set up a cron job calling "
    "`python fetch_leads.py` every few hours."
)
