import streamlit as st
from schemas import (
    RoleType, TrialStage, WitnessExamPhase,
    STAGE_DISPLAY, STAGE_ORDER,
)
from case_data import get_case_info, get_characters, get_evidence_list, get_pw_witnesses, get_dw_witnesses
from game_engine import TrialEngine

# ─── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(
    page_title="Court Simulation",
    page_icon="⚖️",
    layout="wide",
)

# ─── CUSTOM CSS ──────────────────────────────────────────────
st.markdown("""
<style>
    .stage-banner {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: #e6c300;
        padding: 12px 24px;
        border-radius: 8px;
        font-size: 1.2em;
        font-weight: bold;
        text-align: center;
        margin-bottom: 16px;
        border-left: 5px solid #e6c300;
    }
    .dialogue-box {
        padding: 10px 16px;
        border-radius: 8px;
        margin-bottom: 8px;
        border-left: 4px solid #ccc;
    }
    .dialogue-judge {
        background-color: #fff8e1;
        border-left-color: #f9a825;
    }
    .dialogue-prosecutor {
        background-color: #fce4ec;
        border-left-color: #c62828;
    }
    .dialogue-defence {
        background-color: #e3f2fd;
        border-left-color: #1565c0;
    }
    .dialogue-accused {
        background-color: #f3e5f5;
        border-left-color: #6a1b9a;
    }
    .dialogue-witness {
        background-color: #e8f5e9;
        border-left-color: #2e7d32;
    }
    .dialogue-clerk {
        background-color: #ede7f6;
        border-left-color: #4527a0;
    }
    .dialogue-player {
        border-right: 4px solid #ff6f00;
        border-left: none;
        background-color: #fff3e0;
    }
    .speaker-name {
        font-weight: bold;
        font-size: 0.85em;
        margin-bottom: 4px;
    }
    .speaker-judge { color: #f9a825; }
    .speaker-prosecutor { color: #c62828; }
    .speaker-defence { color: #1565c0; }
    .speaker-accused { color: #6a1b9a; }
    .speaker-witness { color: #2e7d32; }
    .speaker-clerk { color: #4527a0; }
    .role-card {
        background: #f8f9fa;
        border: 2px solid #dee2e6;
        border-radius: 12px;
        padding: 20px;
        text-align: center;
        cursor: pointer;
        transition: all 0.3s;
    }
    .role-card:hover {
        border-color: #1565c0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .progress-bar {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
    }
    .progress-dot {
        width: 30px;
        height: 30px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7em;
        font-weight: bold;
        color: white;
    }
    .dot-active { background-color: #e6c300; }
    .dot-done { background-color: #2e7d32; }
    .dot-pending { background-color: #9e9e9e; }
    .verdict-box {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        color: white;
        padding: 24px;
        border-radius: 12px;
        text-align: center;
        font-size: 1.1em;
        margin: 20px 0;
    }
</style>
""", unsafe_allow_html=True)


# ─── SESSION STATE ───────────────────────────────────────────
def init_session():
    if "screen" not in st.session_state:
        st.session_state.screen = "welcome"
    if "engine" not in st.session_state:
        st.session_state.engine = None
    if "player_role" not in st.session_state:
        st.session_state.player_role = None
    if "stage_auto_run" not in st.session_state:
        st.session_state.stage_auto_run = False
    if "exam_question_count" not in st.session_state:
        st.session_state.exam_question_count = 0

init_session()


# ─── HELPER: RENDER DIALOGUE ────────────────────────────────
def get_dialogue_class(role: RoleType, is_player: bool) -> tuple[str, str]:
    if is_player:
        return "dialogue-box dialogue-player", "speaker-name"
    mapping = {
        RoleType.JUDGE: ("dialogue-box dialogue-judge", "speaker-name speaker-judge"),
        RoleType.PROSECUTOR: ("dialogue-box dialogue-prosecutor", "speaker-name speaker-prosecutor"),
        RoleType.DEFENCE: ("dialogue-box dialogue-defence", "speaker-name speaker-defence"),
        RoleType.ACCUSED: ("dialogue-box dialogue-accused", "speaker-name speaker-accused"),
        RoleType.WITNESS_PW: ("dialogue-box dialogue-witness", "speaker-name speaker-witness"),
        RoleType.WITNESS_DW: ("dialogue-box dialogue-witness", "speaker-name speaker-witness"),
        RoleType.CLERK: ("dialogue-box dialogue-clerk", "speaker-name speaker-clerk"),
    }
    return mapping.get(role, ("dialogue-box", "speaker-name"))


def render_dialogues():
    engine = st.session_state.engine
    if not engine:
        return
    for d in engine.state.dialogues:
        box_cls, name_cls = get_dialogue_class(d.role, d.is_player)
        label = f"🎯 YOU ({d.speaker})" if d.is_player else d.speaker
        role_badge = d.role.value
        st.markdown(
            f'<div class="{box_cls}">'
            f'<div class="{name_cls}">{label} — <em>{role_badge}</em></div>'
            f'<div>{d.text}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


STAGE_SHORT_LABELS = {
    TrialStage.PRE_TRIAL: "Pre-Trial",
    TrialStage.COGNIZANCE: "Cognizance",
    TrialStage.CHARGE: "Charge",
    TrialStage.PROSECUTION_OPENING: "Prosecution",
    TrialStage.WITNESS_EXAMINATION: "Witnesses",
    TrialStage.ACCUSED_STATEMENT: "Accused",
    TrialStage.DEFENCE_EVIDENCE: "Defence",
    TrialStage.FINAL_ARGUMENTS: "Arguments",
    TrialStage.JUDGMENT: "Judgment",
}


def render_stage_progress():
    engine = st.session_state.engine
    if not engine:
        return
    current_idx = STAGE_ORDER.index(engine.state.current_stage)
    cols = st.columns(9)
    for i, stage in enumerate(STAGE_ORDER):
        with cols[i]:
            if i < current_idx:
                cls = "dot-done"
            elif i == current_idx:
                cls = "dot-active"
            else:
                cls = "dot-pending"
            label = STAGE_SHORT_LABELS.get(stage, "")
            st.markdown(
                f'<div style="text-align:center">'
                f'<div class="progress-dot {cls}" style="margin:0 auto">{i+1}</div>'
                f'<div style="font-size:0.6em;margin-top:4px">{label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ─── SCREENS ─────────────────────────────────────────────────

def welcome_screen():
    st.markdown("# ⚖️ Court Simulation")
    st.markdown("### Indian Criminal Trial Procedure")
    st.markdown("---")

    case = get_case_info()
    st.markdown(f"**Case:** {case.title}")
    st.markdown(f"**Case No.:** {case.case_number}")
    st.markdown(f"**Court:** {case.court}")
    st.markdown(f"**Sections:** {', '.join(case.sections)}")
    st.markdown(f"**FIR:** {case.fir_number} dated {case.fir_date}")

    st.markdown("---")
    st.markdown("#### Case Summary")
    st.info(case.incident_summary)

    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**Prosecution's Version:**")
        st.warning(case.prosecution_story)
    with col2:
        st.markdown("**Defence's Version:**")
        st.success(case.defence_story)

    st.markdown("---")
    st.markdown("#### The trial follows 9 stages:")
    for i, stage in enumerate(STAGE_ORDER):
        st.markdown(f"{i+1}. {STAGE_DISPLAY[stage]}")

    st.markdown("---")
    if st.button("🚀 Start Simulation — Choose Your Role", type="primary", use_container_width=True):
        st.session_state.screen = "role_select"
        st.rerun()


def role_select_screen():
    st.markdown("# Choose Your Role")
    st.markdown("Select the courtroom role you want to play. All other roles will be AI-controlled.")
    st.markdown("---")

    characters = get_characters()
    roles = [
        (RoleType.JUDGE, "⚖️", "Judge", "Preside over the trial, frame charges, examine the accused, and deliver the verdict."),
        (RoleType.PROSECUTOR, "🔴", "Public Prosecutor", "Represent the State. Examine prosecution witnesses, present evidence, and argue guilt."),
        (RoleType.DEFENCE, "🔵", "Defence Counsel", "Defend the accused. Cross-examine witnesses, raise objections, and argue for acquittal."),
        (RoleType.ACCUSED, "👤", "Accused", "You are Rajesh Kumar Sharma. Maintain your innocence and respond to the Judge's questions."),
    ]

    cols = st.columns(2)
    for i, (role, icon, title, desc) in enumerate(roles):
        with cols[i % 2]:
            char = None
            for c in characters:
                if c.role == role:
                    char = c
                    break
            st.markdown(f"### {icon} {title}")
            if char:
                st.markdown(f"**Character:** {char.name}")
            st.markdown(desc)
            if st.button(f"Play as {title}", key=f"role_{role.value}", use_container_width=True):
                st.session_state.player_role = role
                st.session_state.engine = TrialEngine(role)
                st.session_state.screen = "trial"
                st.session_state.stage_auto_run = False
                st.session_state.exam_question_count = 0
                st.rerun()


def render_sidebar():
    engine = st.session_state.engine
    if not engine:
        return

    with st.sidebar:
        st.markdown("### ⚖️ Court Simulation")
        st.markdown(f"**Role:** {engine.state.player_role.value}")
        st.markdown(f"**Stage:** {engine.get_stage_label()}")
        st.markdown("---")

        # Case info
        st.markdown("#### 📋 Case Info")
        case = engine.case_info
        st.markdown(f"**{case.title}**")
        st.markdown(f"Case No. {case.case_number}")
        st.markdown(f"Sections: {', '.join(case.sections)}")

        st.markdown("---")
        st.markdown("#### 📁 Evidence")
        for e in engine.state.evidence_list:
            icon = "📄" if e.evidence_type == "documentary" else "🔧" if e.evidence_type == "physical" else "🗣️"
            st.markdown(f"{icon} **{e.id}:** {e.name}")

        st.markdown("---")
        st.markdown("#### 👥 Witnesses")
        st.markdown("**Prosecution:**")
        for pw in engine.pw_witnesses:
            st.markdown(f"- {pw.designation}: {pw.name}")
        st.markdown("**Defence:**")
        for dw in engine.dw_witnesses:
            st.markdown(f"- {dw.designation}: {dw.name}")

        if engine.state.current_stage == TrialStage.WITNESS_EXAMINATION:
            st.markdown("---")
            wi = engine.state.current_witness_index
            if wi < len(engine.pw_witnesses):
                pw = engine.pw_witnesses[wi]
                st.markdown(f"#### 🔍 Current Witness")
                st.markdown(f"**{pw.designation}:** {pw.name}")
                st.markdown(f"**Phase:** {engine.state.current_exam_phase.value}")

        if engine.state.current_stage == TrialStage.DEFENCE_EVIDENCE:
            st.markdown("---")
            dwi = engine.state.dw_index
            if dwi < len(engine.dw_witnesses):
                dw = engine.dw_witnesses[dwi]
                st.markdown(f"#### 🔍 Current Witness")
                st.markdown(f"**{dw.designation}:** {dw.name}")
                st.markdown(f"**Phase:** {engine.state.dw_exam_phase.value}")


def trial_screen():
    engine = st.session_state.engine
    if not engine:
        return

    render_sidebar()
    render_stage_progress()

    # Stage banner
    st.markdown(
        f'<div class="stage-banner">{engine.get_stage_label()}</div>',
        unsafe_allow_html=True,
    )

    stage = engine.state.current_stage

    # Auto-run stage logic if not yet run
    if not st.session_state.stage_auto_run:
        stage_done = run_current_stage(engine, stage)
        st.session_state.stage_auto_run = True
        if stage_done and not engine.state.waiting_for_player:
            # Auto-advance for quick stages
            if stage in [TrialStage.PRE_TRIAL, TrialStage.COGNIZANCE, TrialStage.PROSECUTION_OPENING]:
                pass  # Will show "Continue" button

    # Render all dialogue so far
    render_dialogues()

    # ─── PLAYER INPUT / STAGE CONTROLS ───────────────────────
    if engine.state.current_stage == TrialStage.JUDGMENT and engine.state.verdict:
        st.markdown(
            f'<div class="verdict-box"><h2>⚖️ VERDICT</h2><p>{engine.state.verdict}</p></div>',
            unsafe_allow_html=True,
        )
        st.balloons()
        return

    if engine.state.waiting_for_player:
        render_player_input(engine, stage)
    else:
        # Show continue button to advance stages
        render_continue_controls(engine, stage)


def run_current_stage(engine, stage):
    """Run the current stage logic and return True if stage is complete."""
    if stage == TrialStage.PRE_TRIAL:
        return engine.run_pre_trial()
    elif stage == TrialStage.COGNIZANCE:
        return engine.run_cognizance()
    elif stage == TrialStage.CHARGE:
        return engine.run_charge_stage()
    elif stage == TrialStage.PROSECUTION_OPENING:
        return engine.run_prosecution_opening()
    elif stage == TrialStage.WITNESS_EXAMINATION:
        return engine.run_witness_examination()
    elif stage == TrialStage.ACCUSED_STATEMENT:
        return engine.run_accused_statement()
    elif stage == TrialStage.DEFENCE_EVIDENCE:
        return engine.run_defence_evidence()
    elif stage == TrialStage.FINAL_ARGUMENTS:
        return engine.run_final_arguments()
    elif stage == TrialStage.JUDGMENT:
        return engine.run_judgment()
    return False


def render_player_input(engine, stage):
    """Render the player input area based on current stage."""
    st.markdown("---")
    player_role = engine.state.player_role

    # Context-specific prompts
    if stage == TrialStage.COGNIZANCE:
        if player_role == RoleType.PROSECUTOR:
            st.info("📢 **Your turn (Public Prosecutor):** Confirm that documents have been supplied to the accused.")
        elif player_role == RoleType.DEFENCE:
            st.info("📢 **Your turn (Defence Counsel):** Confirm receipt of documents.")

    elif stage == TrialStage.CHARGE:
        if player_role == RoleType.PROSECUTOR and engine.state.sub_step == 0:
            st.info("📢 **Your turn (Public Prosecutor):** Argue why charges should be framed.")
        elif player_role == RoleType.DEFENCE and engine.state.sub_step == 1:
            st.info("📢 **Your turn (Defence Counsel):** Argue for discharge of the accused.")
        elif player_role == RoleType.JUDGE and engine.state.sub_step == 10:
            st.info("📢 **Your turn (Judge):** Frame charges and ask the accused to plead.")
        elif player_role == RoleType.ACCUSED and engine.state.sub_step == 20:
            st.info("📢 **Your turn (Accused):** Enter your plea (guilty / not guilty).")

    elif stage == TrialStage.PROSECUTION_OPENING:
        st.info("📢 **Your turn (Public Prosecutor):** Open the prosecution's case. Explain the story and list witnesses.")

    elif stage == TrialStage.WITNESS_EXAMINATION:
        wi = engine.state.current_witness_index
        if wi < len(engine.pw_witnesses):
            pw = engine.pw_witnesses[wi]
            phase = engine.state.current_exam_phase
            if phase == WitnessExamPhase.CHIEF and engine.is_player(RoleType.PROSECUTOR):
                st.info(f"📢 **Examination-in-Chief:** Ask {pw.name} ({pw.designation}) an open question (no leading questions).")
            elif phase == WitnessExamPhase.CROSS and engine.is_player(RoleType.DEFENCE):
                st.info(f"📢 **Cross-Examination:** Question {pw.name} ({pw.designation}). Find contradictions.")
            elif phase == WitnessExamPhase.RE_EXAMINATION and engine.is_player(RoleType.PROSECUTOR):
                st.info(f"📢 **Re-Examination:** Clarify any points from cross-examination with {pw.name}.")
            else:
                st.info(f"📢 **Your turn:** Respond or interact during {phase.value} of {pw.designation}.")

    elif stage == TrialStage.ACCUSED_STATEMENT:
        if player_role == RoleType.JUDGE:
            st.info("📢 **Your turn (Judge):** Ask the accused a question based on evidence. (No cross-examination allowed)")
        elif player_role == RoleType.ACCUSED:
            st.info("📢 **Your turn (Accused):** Answer the Judge's question.")

    elif stage == TrialStage.DEFENCE_EVIDENCE:
        dwi = engine.state.dw_index
        if dwi < len(engine.dw_witnesses):
            dw = engine.dw_witnesses[dwi]
            phase = engine.state.dw_exam_phase
            st.info(f"📢 **{phase.value}** of {dw.designation} — {dw.name}")

    elif stage == TrialStage.FINAL_ARGUMENTS:
        if engine.state.final_arg_turn == "prosecution" and player_role == RoleType.PROSECUTOR:
            st.info("📢 **Your turn (Public Prosecutor):** Deliver your final argument. Argue guilt beyond reasonable doubt.")
        elif engine.state.final_arg_turn == "defence" and player_role == RoleType.DEFENCE:
            st.info("📢 **Your turn (Defence Counsel):** Deliver your final argument. Argue for acquittal.")

    elif stage == TrialStage.JUDGMENT:
        if player_role == RoleType.JUDGE:
            st.info("📢 **Your turn (Judge):** Deliver the judgment. Pronounce acquittal or conviction with reasoning.")

    # Text input
    col1, col2 = st.columns([5, 1])
    with col1:
        player_input = st.text_area(
            "Your response:",
            key=f"player_input_{stage.value}_{engine.state.sub_step}_{len(engine.state.dialogues)}",
            height=100,
            placeholder="Type your courtroom response here...",
        )
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        submit = st.button("📤 Submit", type="primary", use_container_width=True)

        # Quick action buttons for witness exam
        if stage == TrialStage.WITNESS_EXAMINATION:
            if st.button("⏭️ No More Questions", use_container_width=True, key="no_q_pw"):
                engine.advance_exam_phase()
                st.session_state.exam_question_count = 0
                st.rerun()

        if stage == TrialStage.DEFENCE_EVIDENCE:
            if st.button("⏭️ No More Questions", use_container_width=True, key="no_q_dw"):
                engine.advance_dw_exam_phase()
                st.session_state.exam_question_count = 0
                st.rerun()

    if submit and player_input.strip():
        handle_player_submit(engine, stage, player_input.strip())
        st.rerun()


def handle_player_submit(engine, stage, player_input):
    """Route player input to the correct handler."""
    if stage == TrialStage.COGNIZANCE:
        engine.handle_cognizance_input(player_input)
    elif stage == TrialStage.CHARGE:
        engine.handle_charge_input(player_input)
    elif stage == TrialStage.PROSECUTION_OPENING:
        engine.handle_prosecution_opening_input(player_input)
    elif stage == TrialStage.WITNESS_EXAMINATION:
        engine.handle_witness_exam_input(player_input)
        st.session_state.exam_question_count += 1
    elif stage == TrialStage.ACCUSED_STATEMENT:
        engine.handle_accused_statement_input(player_input)
    elif stage == TrialStage.DEFENCE_EVIDENCE:
        engine.handle_dw_exam_input(player_input)
        st.session_state.exam_question_count += 1
    elif stage == TrialStage.FINAL_ARGUMENTS:
        engine.handle_final_args_input(player_input)
    elif stage == TrialStage.JUDGMENT:
        engine.handle_judgment_input(player_input)


def render_continue_controls(engine, stage):
    """Render buttons to advance or auto-play."""
    st.markdown("---")

    # For witness examination, offer auto-play or manual advance
    if stage == TrialStage.WITNESS_EXAMINATION:
        wi = engine.state.current_witness_index
        if wi < len(engine.pw_witnesses):
            pw = engine.pw_witnesses[wi]
            phase = engine.state.current_exam_phase

            examiner_role = RoleType.PROSECUTOR if phase != WitnessExamPhase.CROSS else RoleType.DEFENCE

            if not engine.is_player(examiner_role) and not engine.is_player(RoleType.WITNESS_PW):
                # Both sides are AI — auto-play
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"▶️ Next Q&A ({phase.value})", use_container_width=True, key="auto_qa"):
                        engine.auto_witness_exchange()
                        st.rerun()
                with col2:
                    if st.button(f"⏭️ End {phase.value}", use_container_width=True, key="end_phase"):
                        engine.advance_exam_phase()
                        st.session_state.stage_auto_run = False
                        st.rerun()
                return
            else:
                # Player is examiner or witness
                engine.state.waiting_for_player = True
                st.rerun()
                return
        else:
            # All PW done
            pass

    if stage == TrialStage.DEFENCE_EVIDENCE:
        dwi = engine.state.dw_index
        if dwi < len(engine.dw_witnesses):
            dw = engine.dw_witnesses[dwi]
            phase = engine.state.dw_exam_phase
            examiner_role = RoleType.DEFENCE if phase != WitnessExamPhase.CROSS else RoleType.PROSECUTOR

            if not engine.is_player(examiner_role) and not engine.is_player(RoleType.WITNESS_DW):
                col1, col2 = st.columns(2)
                with col1:
                    if st.button(f"▶️ Next Q&A ({phase.value})", use_container_width=True, key="auto_dw_qa"):
                        engine.auto_dw_exchange()
                        st.rerun()
                with col2:
                    if st.button(f"⏭️ End {phase.value}", use_container_width=True, key="end_dw_phase"):
                        engine.advance_dw_exam_phase()
                        st.session_state.stage_auto_run = False
                        st.rerun()
                return

    if stage == TrialStage.ACCUSED_STATEMENT:
        if engine.state.sub_step < 3:
            if st.button("▶️ Continue Examination", use_container_width=True, key="continue_accused"):
                st.session_state.stage_auto_run = False
                st.rerun()
            return

    # Generic "Next Stage" button
    current_idx = STAGE_ORDER.index(stage)
    if current_idx < len(STAGE_ORDER) - 1:
        next_stage = STAGE_DISPLAY[STAGE_ORDER[current_idx + 1]]
        if st.button(f"➡️ Proceed to {next_stage}", type="primary", use_container_width=True):
            engine.advance_stage()
            st.session_state.stage_auto_run = False
            st.session_state.exam_question_count = 0
            st.rerun()


# ─── MAIN ────────────────────────────────────────────────────
def main():
    screen = st.session_state.screen

    if screen == "welcome":
        welcome_screen()
    elif screen == "role_select":
        role_select_screen()
    elif screen == "trial":
        trial_screen()


if __name__ == "__main__":
    main()
