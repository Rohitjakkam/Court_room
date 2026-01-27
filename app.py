"""
Court Case & Judgement Analyzer - Streamlit Application
Complete system for PDF extraction, analysis, and courtroom simulation game
"""

import streamlit as st
import PyPDF2
from io import BytesIO
import json
import os
from typing import Optional

# Import our modules
from schemas import CourtCase, CaseType, CaseMetadata
from extraction_pipeline import CourtCaseExtractor, extract_text_from_pdf_bytes
from agents import create_agents_from_case, AgentRole, CourtPhase
from replay_engine import CourtroomReplayEngine, SimulationConfig, SimulationMode, InteractiveCourtroom
from game_engine import (
    CourtroomGame, PlayerSide, GamePhase, GameAction, ActionType,
    ObjectionType, DynamicEvent
)

# Page configuration
st.set_page_config(
    page_title="Courtroom Advocate - Legal Simulation Game",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        color: #fff;
        text-align: center;
        padding: 1.5rem;
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
        border-radius: 15px;
        margin-bottom: 2rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3);
    }
    .phase-banner {
        background: linear-gradient(90deg, #e94560 0%, #0f3460 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
        font-size: 1.2rem;
        font-weight: bold;
        margin: 1rem 0;
    }
    .player-action-box {
        background-color: #1e3a5f;
        border: 2px solid #4CAF50;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .ai-response-box {
        background-color: #2d2d44;
        border: 2px solid #ffd700;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .judge-box {
        background-color: #3d1e3d;
        border: 2px solid #9c27b0;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .witness-box {
        background-color: #1e3d3d;
        border: 2px solid #00bcd4;
        padding: 1rem;
        border-radius: 10px;
        margin: 0.5rem 0;
    }
    .event-alert {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a5a 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        margin: 1rem 0;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(233, 69, 96, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(233, 69, 96, 0); }
        100% { box-shadow: 0 0 0 0 rgba(233, 69, 96, 0); }
    }
    .score-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1rem;
        border-radius: 10px;
        text-align: center;
    }
    .action-button {
        width: 100%;
        margin: 0.25rem 0;
    }
    .game-log {
        max-height: 400px;
        overflow-y: auto;
        padding: 1rem;
        background-color: #1a1a2e;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)


def init_session_state():
    """Initialize session state variables."""
    defaults = {
        'extracted_text': None,
        'case_data': None,
        'simulation_messages': [],
        'current_phase': None,
        'replay_engine': None,
        'interactive_court': None,
        'game': None,
        'game_started': False,
        'game_messages': [],
        'pending_event': None,
        'player_side': None
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def render_header():
    """Render the main header."""
    st.markdown("""
    <div class="main-header">
        <h1>⚖️ Courtroom Advocate</h1>
        <h3>Legal Simulation Game</h3>
        <p>Step into the shoes of a lawyer. Argue cases, examine witnesses, face surprises!</p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar():
    """Render sidebar with configuration options."""
    with st.sidebar:
        st.header("⚙️ Configuration")

        # Load API key from secrets and set fixed model
        provider = "openai"
        model = "gpt-4o"

        # Load OpenAI API key from secrets.toml
        if "openai" in st.secrets:
            os.environ["OPENAI_API_KEY"] = st.secrets["openai"]
            st.success("✅ API Key loaded")
        else:
            st.error("❌ OpenAI API key not found in secrets.toml")

        # Display locked configuration
        st.info(f"🤖 Model: **{model}**")

        st.divider()

        # Game settings
        st.subheader("🎮 Game Settings")
        difficulty = st.select_slider(
            "Difficulty",
            options=["easy", "medium", "hard"],
            value="medium",
            help="Higher difficulty = more random events and tougher AI"
        )

        st.divider()

        # Simulation settings (for non-game mode)
        st.subheader("📊 Simulation Settings")
        sim_mode = st.selectbox(
            "Mode",
            [e.value for e in SimulationMode],
            help="Choose simulation mode"
        )

        return {
            "provider": provider,
            "model": model,
            "difficulty": difficulty,
            "sim_mode": SimulationMode(sim_mode)
        }


def extract_pdf_text(uploaded_file) -> str:
    """Extract text from uploaded PDF."""
    pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.read()))
    text = ""
    for page_num, page in enumerate(pdf_reader.pages, 1):
        page_text = page.extract_text()
        if page_text:
            text += f"\n--- Page {page_num} ---\n{page_text}\n"
    return text


def render_pdf_upload_tab(config):
    """Render the PDF upload and text extraction tab."""
    st.header("📄 Upload Court Document")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Choose a PDF file (Court Judgment)",
            type="pdf",
            help="Upload a court case judgment PDF to analyze and simulate"
        )

        if uploaded_file:
            if st.button("📖 Extract Text", use_container_width=True):
                with st.spinner("Extracting text from PDF..."):
                    uploaded_file.seek(0)
                    text = extract_pdf_text(uploaded_file)
                    st.session_state.extracted_text = text
                    st.success(f"✅ Extracted text from {uploaded_file.name}")

    with col2:
        st.info("""
        **Supported Documents:**
        - Motor Accident Claims (MACT)
        - Civil Cases
        - Criminal Cases
        - Writ Petitions
        - Appeals
        """)

    if st.session_state.extracted_text:
        st.divider()

        col1, col2 = st.columns(2)

        with col1:
            if st.button("🤖 Extract Case Data (AI)", use_container_width=True):
                try:
                    with st.spinner("AI is analyzing the document..."):
                        extractor = CourtCaseExtractor(
                            provider=config["provider"],
                            model_name=config["model"]
                        )

                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        def progress_callback(section, pct):
                            progress_bar.progress(int(pct))
                            status_text.text(f"Extracting: {section}")

                        case = extractor.extract_full_case(
                            st.session_state.extracted_text,
                            progress_callback=progress_callback
                        )

                        st.session_state.case_data = case
                        progress_bar.progress(100)
                        status_text.text("Extraction complete!")
                        st.success("✅ Case data extracted! Go to the Game tab to play.")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

        with col2:
            if st.button("📥 Load Sample Case", use_container_width=True):
                # Create a sample case for demo
                st.session_state.case_data = create_sample_case()
                st.success("✅ Sample case loaded! Go to the Game tab to play.")

        with st.expander("📜 View Extracted Text", expanded=False):
            st.text_area("PDF Content", st.session_state.extracted_text, height=300)


def create_sample_case() -> CourtCase:
    """Create a sample case for demonstration."""
    from schemas import (
        CaseDates, Petitioner, Respondent, PartyDetails,
        LegalRepresentation, VehicleInvolved, FIRDetails, FactualMatrix,
        ProceduralHistory, IssueFramed, IssuesFramed, OralWitness,
        DocumentaryExhibit, EvidenceDetails, MedicalTreatment,
        DisabilityCertificate, MedicalEvidence, IncomeProof,
        CompensationHead, CompensationComputation, CaseLaw,
        CaseLawCitations, JudicialFindings, FinalOrder,
        PostJudgmentDirections, MachineMetadata,
        LegalStatus, PartyRole, IssueFinding, WitnessType,
        DisabilityType, NegligenceType, JudgmentTone
    )
    from datetime import date

    return CourtCase(
        case_metadata=CaseMetadata(
            case_title="Ramesh Kumar vs. United India Insurance Co. Ltd.",
            main_case_number="MACP No. 245/2023",
            fir_number="FIR No. 123/2022",
            case_type=CaseType.MACT,
            relevant_acts_sections=["Motor Vehicles Act, 1988 - Section 166", "Section 140"],
            court_name="Motor Accident Claims Tribunal, Delhi",
            judge_name="Hon'ble Sh. Rajesh Sharma",
            judge_designation="Presiding Officer, MACT",
            court_location="Tis Hazari Courts, Delhi",
            case_dates=CaseDates(
                institution=date(2022, 6, 15),
                arguments=date(2023, 8, 20),
                judgment=date(2023, 9, 15)
            )
        ),
        party_details=PartyDetails(
            petitioners=[
                Petitioner(
                    full_name="Ramesh Kumar",
                    parentage="S/o Late Shri Mohan Lal",
                    address="H.No. 45, Karol Bagh, New Delhi",
                    legal_status=LegalStatus.INJURED,
                    occupation="Private Employee",
                    income_claimed=35000,
                    income_proved=30000,
                    age=35
                )
            ],
            respondents=[
                Respondent(
                    name="Suresh Singh",
                    role=PartyRole.DRIVER,
                    address="Village Rampur, Haryana",
                    is_ex_parte=True
                ),
                Respondent(
                    name="Mahesh Traders Pvt. Ltd.",
                    role=PartyRole.OWNER,
                    address="Industrial Area, Faridabad"
                ),
                Respondent(
                    name="United India Insurance Co. Ltd.",
                    role=PartyRole.INSURER,
                    representation="Adv. Sanjay Gupta"
                )
            ]
        ),
        legal_representation=LegalRepresentation(
            counsel_for_petitioner=["Adv. Priya Sharma"],
            counsel_for_respondents=["Adv. Sanjay Gupta (for R-3)"],
            written_statement_filed=True
        ),
        factual_matrix=FactualMatrix(
            incident_date=date(2022, 5, 10),
            incident_time="10:30 AM",
            place_of_occurrence="NH-48, near Manesar Toll Plaza",
            vehicles_involved=[
                VehicleInvolved(
                    registration_number="HR-55-AB-1234",
                    vehicle_type="Truck",
                    direction_of_movement="Delhi to Jaipur"
                )
            ],
            alleged_manner_of_accident="The truck was being driven rashly and negligently at high speed. It hit the petitioner who was crossing the road.",
            nature_of_negligence=[NegligenceType.RASH_DRIVING, NegligenceType.OVER_SPEEDING],
            fir_details=FIRDetails(
                fir_date=date(2022, 5, 10),
                police_station="PS Manesar"
            )
        ),
        issues_framed=IssuesFramed(
            issues=[
                IssueFramed(
                    issue_number=1,
                    issue_text="Whether the accident occurred due to rash and negligent driving of the driver of the offending vehicle?",
                    onus_of_proof="OPP",
                    finding=IssueFinding.PROVED
                ),
                IssueFramed(
                    issue_number=2,
                    issue_text="Whether the petitioner is entitled to compensation? If so, how much and from whom?",
                    onus_of_proof="OPP",
                    finding=IssueFinding.PROVED
                ),
                IssueFramed(
                    issue_number=3,
                    issue_text="Whether the insurance company can avoid liability on account of any policy violation?",
                    onus_of_proof="OPR",
                    finding=IssueFinding.NOT_PROVED
                )
            ]
        ),
        evidence_details=EvidenceDetails(
            oral_witnesses=[
                OralWitness(
                    witness_number="PW-1",
                    witness_type=WitnessType.PW,
                    name="Ramesh Kumar (Petitioner)",
                    examination_in_chief_summary="Deposed about the accident, injuries suffered, and medical treatment.",
                    admissions=["Was crossing the road when hit"],
                    contradictions=[]
                ),
                OralWitness(
                    witness_number="PW-2",
                    witness_type=WitnessType.PW,
                    name="Dr. Amit Verma",
                    examination_in_chief_summary="Treating doctor who testified about injuries and disability.",
                    admissions=["Patient had multiple fractures"],
                    contradictions=[]
                ),
                OralWitness(
                    witness_number="RW-1",
                    witness_type=WitnessType.RW,
                    name="Insurance Investigator",
                    examination_in_chief_summary="Testified about policy verification and claim investigation.",
                    admissions=["Policy was valid at time of accident"],
                    contradictions=["Initially claimed policy violation"]
                )
            ],
            documentary_exhibits=[
                DocumentaryExhibit(
                    exhibit_number="Ex.PW1/A",
                    description="FIR Copy",
                    party_relying="Petitioner",
                    court_view="Accepted"
                ),
                DocumentaryExhibit(
                    exhibit_number="Ex.PW1/B",
                    description="Medical Records",
                    party_relying="Petitioner",
                    court_view="Accepted"
                ),
                DocumentaryExhibit(
                    exhibit_number="Ex.PW1/C",
                    description="Disability Certificate",
                    party_relying="Petitioner",
                    court_view="Accepted"
                )
            ]
        ),
        medical_evidence=MedicalEvidence(
            treatments=[
                MedicalTreatment(
                    hospital_name="Safdarjung Hospital, Delhi",
                    admission_date=date(2022, 5, 10),
                    discharge_date=date(2022, 6, 25),
                    nature_of_injuries=["Fracture of right femur", "Head injury", "Multiple abrasions"],
                    surgical_procedures=["Open reduction internal fixation (ORIF)"]
                )
            ],
            disability_certificates=[
                DisabilityCertificate(
                    percentage=25,
                    limb_affected="Right leg",
                    disability_type=DisabilityType.PERMANENT,
                    functional_disability=20
                )
            ],
            total_disability_percentage=25
        ),
        income_proof=IncomeProof(
            employer_name="ABC Pvt. Ltd.",
            job_title="Accountant",
            salary_slips_available=True,
            income_claimed=35000,
            income_accepted_by_court=30000,
            retirement_age_assumed=60,
            remaining_working_years=25
        ),
        compensation=CompensationComputation(
            heads=[
                CompensationHead(head_name="Medical Expenses", amount_claimed=350000, amount_awarded=300000),
                CompensationHead(head_name="Loss of Income during treatment", amount_claimed=105000, amount_awarded=90000),
                CompensationHead(head_name="Future Loss of Income", amount_claimed=1500000, amount_awarded=1080000),
                CompensationHead(head_name="Pain and Suffering", amount_claimed=200000, amount_awarded=150000),
                CompensationHead(head_name="Loss of Amenities", amount_claimed=100000, amount_awarded=75000),
                CompensationHead(head_name="Conveyance", amount_claimed=25000, amount_awarded=20000)
            ],
            multiplier=15,
            total_claimed=2280000,
            total_awarded=1715000
        ),
        case_law=CaseLawCitations(
            citations=[
                CaseLaw(
                    case_name="Sarla Verma vs. DTC",
                    court="Supreme Court of India",
                    year=2009,
                    legal_principle="Multiplier method for calculating future loss of income"
                ),
                CaseLaw(
                    case_name="National Insurance Co. vs. Pranay Sethi",
                    court="Supreme Court of India",
                    year=2017,
                    legal_principle="Conventional heads of compensation"
                )
            ]
        ),
        judicial_findings=JudicialFindings(
            negligence_finding="Rash and negligent driving of truck driver established",
            liability_finding="Insurance company liable to pay compensation",
            standard_of_proof_applied="Preponderance of probability"
        ),
        final_order=FinalOrder(
            total_compensation_awarded=1715000,
            interest_rate=7.5,
            interest_start_date=date(2022, 6, 15),
            liable_party=["United India Insurance Co. Ltd."],
            compliance_time_days=30
        ),
        machine_metadata=MachineMetadata(
            case_category_tags=["MACT", "Motor Accident", "Personal Injury"],
            negligence_types=[NegligenceType.RASH_DRIVING],
            dispute_complexity_level="Medium",
            judgment_tone=JudgmentTone.CLAIMANT_FRIENDLY,
            summary="Motor accident case where petitioner was hit by a truck. Court awarded Rs. 17.15 lakhs compensation."
        )
    )


def render_game_tab(config):
    """Render the main game interface."""
    st.header("🎮 Courtroom Advocate - The Game")

    if not st.session_state.case_data:
        st.warning("⚠️ Please upload a PDF and extract case data first, or load a sample case.")
        if st.button("📥 Load Sample Case to Play", use_container_width=True):
            st.session_state.case_data = create_sample_case()
            st.rerun()
        return

    case: CourtCase = st.session_state.case_data

    # Game not started - show setup screen
    if not st.session_state.game_started:
        render_game_setup(case, config)
    else:
        render_game_play(config)


def render_game_setup(case: CourtCase, config):
    """Render game setup screen."""
    st.markdown("""
    <div class="phase-banner">
        🎯 CASE BRIEFING
    </div>
    """, unsafe_allow_html=True)

    # Case summary
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(f"📋 {case.case_metadata.case_title}")
        st.write(f"**Case No.:** {case.case_metadata.main_case_number}")
        st.write(f"**Court:** {case.case_metadata.court_name}")
        st.write(f"**Case Type:** {case.case_metadata.case_type.value}")

        st.divider()

        st.subheader("📌 Issues to be Decided")
        for issue in case.issues_framed.issues:
            st.write(f"**Issue {issue.issue_number}:** {issue.issue_text}")

    with col2:
        st.subheader("👥 Parties")
        st.write("**Petitioner(s):**")
        for p in case.party_details.petitioners:
            st.write(f"  • {p.full_name}")

        st.write("**Respondent(s):**")
        for r in case.party_details.respondents:
            st.write(f"  • {r.name} ({r.role.value})")

    st.divider()

    # Side selection
    st.subheader("⚖️ Choose Your Side")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
                    padding: 1.5rem; border-radius: 15px; color: white;">
            <h3>👨‍💼 Petitioner's Counsel</h3>
            <p>Fight for the injured victim. Prove negligence and maximize compensation.</p>
            <ul>
                <li>Prove the accident was caused by negligence</li>
                <li>Establish the extent of injuries and losses</li>
                <li>Argue for maximum compensation</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("⚔️ Represent Petitioner", use_container_width=True, key="pet_btn"):
            start_game(case, PlayerSide.PETITIONER, config)

    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
                    padding: 1.5rem; border-radius: 15px; color: white;">
            <h3>👩‍💼 Respondent's Counsel</h3>
            <p>Defend the insurance company. Challenge claims and minimize liability.</p>
            <ul>
                <li>Challenge the negligence allegations</li>
                <li>Question the claimed injuries and losses</li>
                <li>Minimize compensation amount</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        if st.button("🛡️ Represent Respondent", use_container_width=True, key="resp_btn"):
            start_game(case, PlayerSide.RESPONDENT, config)


def start_game(case: CourtCase, side: PlayerSide, config):
    """Initialize and start the game."""
    game = CourtroomGame(
        case=case,
        llm_provider=config["provider"],
        model_name=config["model"],
        difficulty=config["difficulty"]
    )

    with st.spinner("Initializing courtroom... AI agents are preparing..."):
        result = game.start_game(side)

    st.session_state.game = game
    st.session_state.game_started = True
    st.session_state.player_side = side
    # Handle both single message and list of messages
    if "messages" in result:
        st.session_state.game_messages = result["messages"]
    elif "message" in result:
        st.session_state.game_messages = [result["message"]]
    else:
        st.session_state.game_messages = []

    st.rerun()


def render_game_play(config):
    """Render the active game interface."""
    game: CourtroomGame = st.session_state.game

    # Phase banner
    st.markdown(f"""
    <div class="phase-banner">
        📍 {game.state.phase.value.upper()} | Turn {game.state.turn_number}
    </div>
    """, unsafe_allow_html=True)

    # Main game area
    col1, col2 = st.columns([3, 1])

    with col1:
        # Courtroom messages
        render_courtroom_log()

        st.divider()

        # Pending event handling
        if st.session_state.pending_event:
            render_event_response()
        elif game.state.phase == GamePhase.GAME_OVER:
            render_game_over()
        elif game.state.is_player_turn:
            # Player's turn - show action interface
            render_player_actions()
        else:
            # AI's turn - show continue button
            render_ai_turn_prompt()

    with col2:
        # Score and stats
        render_score_panel()

        st.divider()

        # Quick reference
        render_quick_reference()


def render_ai_turn_prompt():
    """Render prompt when waiting for AI to take its turn."""
    game: CourtroomGame = st.session_state.game

    st.info("⏳ **Opposing counsel is preparing...**")
    st.write("The court is waiting for the opposing party to proceed.")

    if st.button("▶️ Continue Proceedings", use_container_width=True, type="primary"):
        with st.spinner("Court proceedings in progress..."):
            # Run AI turn
            messages = game.run_ai_turn()
            st.session_state.game_messages.extend(messages)
        st.rerun()


def render_courtroom_log():
    """Render the courtroom message log."""
    st.subheader("📜 Court Proceedings")

    messages_container = st.container()

    with messages_container:
        for msg in st.session_state.game_messages[-20:]:  # Show last 20 messages
            if hasattr(msg, 'role'):
                if msg.role == AgentRole.JUDGE:
                    st.markdown(f"""
                    <div class="judge-box">
                        <strong>👨‍⚖️ {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                elif msg.role == AgentRole.WITNESS:
                    st.markdown(f"""
                    <div class="witness-box">
                        <strong>🧑 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                elif msg.role == AgentRole.COURT_CLERK:
                    st.markdown(f"""
                    <div style="background-color: #2a2a3a; border: 2px solid #607D8B;
                                padding: 1rem; border-radius: 10px; margin: 0.5rem 0;
                                font-style: italic;">
                        <strong>📋 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                elif "You" in msg.agent_name or "Player" in msg.agent_name:
                    st.markdown(f"""
                    <div class="player-action-box">
                        <strong>👤 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                elif msg.role == AgentRole.PETITIONER_COUNSEL:
                    st.markdown(f"""
                    <div style="background-color: #1e4d1e; border: 2px solid #4CAF50;
                                padding: 1rem; border-radius: 10px; margin: 0.5rem 0;">
                        <strong>👨‍💼 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                elif msg.role == AgentRole.RESPONDENT_COUNSEL:
                    st.markdown(f"""
                    <div style="background-color: #4d1e1e; border: 2px solid #f44336;
                                padding: 1rem; border-radius: 10px; margin: 0.5rem 0;">
                        <strong>👩‍💼 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="ai-response-box">
                        <strong>👨‍💼 {msg.agent_name}</strong><br>
                        {msg.content}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.write(msg)


def render_player_actions():
    """Render player action interface."""
    game: CourtroomGame = st.session_state.game

    st.subheader("🎬 Your Turn")

    # Show phase instructions
    with st.expander("📋 Phase Instructions", expanded=True):
        st.markdown(game._get_phase_instructions())

    # Action type selection
    available_actions = game.get_available_actions()

    # If no actions available, show proceed button
    if not available_actions:
        st.warning("No actions available in this phase. Proceed to the next phase.")
        if st.button("⏭️ Proceed to Next Phase", use_container_width=True, type="primary"):
            with st.spinner("Court proceedings advancing..."):
                result = game.proceed_to_next_phase()
                st.session_state.game_messages.extend(result.get("messages", []))
            st.rerun()
        return

    action_labels = {
        ActionType.MAKE_ARGUMENT: "📢 Make Argument/Statement",
        ActionType.ASK_QUESTION: "❓ Ask Question",
        ActionType.RAISE_OBJECTION: "⚠️ Raise Objection",
        ActionType.PRESENT_EVIDENCE: "📄 Present Evidence",
        ActionType.CITE_CASE_LAW: "📚 Cite Case Law",
        ActionType.NO_QUESTIONS: "✋ No Further Questions"
    }

    selected_action = st.selectbox(
        "Choose Action",
        options=available_actions,
        format_func=lambda x: action_labels.get(x, x.value)
    )

    # Action content based on type
    if selected_action == ActionType.RAISE_OBJECTION:
        objection_type = st.selectbox(
            "Objection Type",
            options=list(ObjectionType),
            format_func=lambda x: x.value
        )
        content = st.text_area("Additional grounds (optional):", height=100)
    elif selected_action == ActionType.NO_QUESTIONS:
        content = ""
        objection_type = None
    else:
        content = st.text_area(
            "Your statement/question:",
            height=150,
            placeholder="Type your argument, question, or statement here..."
        )
        objection_type = None

    # Submit action
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("📤 Submit Action", use_container_width=True, type="primary"):
            if selected_action != ActionType.NO_QUESTIONS and not content.strip():
                st.error("Please enter your statement/question")
            else:
                action = GameAction(
                    action_type=selected_action,
                    content=content,
                    objection_type=objection_type if selected_action == ActionType.RAISE_OBJECTION else None
                )

                with st.spinner("Processing..."):
                    result = game.process_player_action(action)

                # Add messages to log
                st.session_state.game_messages.extend(result["messages"])

                # Handle events
                if result["events"]:
                    st.session_state.pending_event = result["events"][0]

                st.rerun()

    with col2:
        if st.button("⏭️ Next Phase", use_container_width=True):
            with st.spinner("Advancing to next phase..."):
                result = game.proceed_to_next_phase()
                st.session_state.game_messages.extend(result.get("messages", []))
            st.rerun()

    with col3:
        if st.button("🔄 Reset Game", use_container_width=True):
            st.session_state.game_started = False
            st.session_state.game = None
            st.session_state.game_messages = []
            st.rerun()


def render_event_response():
    """Render dynamic event response interface."""
    event: DynamicEvent = st.session_state.pending_event

    st.markdown(f"""
    <div class="event-alert">
        <h3>⚡ {event.event_type.value}!</h3>
        <p>{event.description}</p>
        <p><strong>Impact:</strong> {event.impact}</p>
    </div>
    """, unsafe_allow_html=True)

    if event.requires_response and event.response_options:
        st.subheader("How do you respond?")

        for i, option in enumerate(event.response_options):
            if st.button(f"Option {i+1}: {option}", key=f"event_opt_{i}", use_container_width=True):
                game: CourtroomGame = st.session_state.game
                result = game.handle_event_response(event, i)

                if result["success"]:
                    st.session_state.game_messages.extend(result.get("messages", []))

                st.session_state.pending_event = None
                st.rerun()
    else:
        if st.button("Continue", use_container_width=True):
            st.session_state.pending_event = None
            st.rerun()


def render_score_panel():
    """Render the score and stats panel."""
    game: CourtroomGame = st.session_state.game
    score = game.state.score

    st.markdown("""
    <div class="score-card">
        <h3>📊 Performance</h3>
    </div>
    """, unsafe_allow_html=True)

    st.metric("Total Points", score.total_points)
    st.metric("Judge's Favor", f"{score.judge_favor:.0f}%")

    st.divider()

    st.write("**Statistics:**")
    st.write(f"• Objections: {game.state.objections_sustained}/{game.state.objections_made}")
    st.write(f"• Evidence: {len(game.state.evidence_presented)}")
    st.write(f"• Warnings: {game.state.warnings_received}")
    st.write(f"• Events: {len(game.state.events_occurred)}")


def render_quick_reference():
    """Render quick reference panel."""
    game: CourtroomGame = st.session_state.game
    case = game.case

    with st.expander("📚 Quick Reference", expanded=True):
        st.write("**Your Side:**", f"{'🟢 Petitioner' if st.session_state.player_side == PlayerSide.PETITIONER else '🔴 Respondent'}")

        st.divider()

        # Current witness info
        if game.state.current_witness:
            st.write("**Current Witness:**")
            st.write(f"  {game.state.current_witness.witness_number}: {game.state.current_witness.name}")
            if game.state.current_witness.examination_in_chief_summary:
                st.write(f"  _{game.state.current_witness.examination_in_chief_summary[:100]}..._")

        st.divider()

        st.write("**Issues to Prove:**")
        for issue in case.issues_framed.issues:
            st.write(f"  {issue.issue_number}. {issue.issue_text[:60]}...")

        st.divider()

        st.write("**Petitioner's Witnesses:**")
        for w in case.evidence_details.oral_witnesses:
            if w.witness_type.value == "PW":
                st.write(f"  • {w.witness_number}: {w.name}")

        st.write("**Respondent's Witnesses:**")
        for w in case.evidence_details.oral_witnesses:
            if w.witness_type.value == "RW":
                st.write(f"  • {w.witness_number}: {w.name}")

        st.divider()

        st.write("**Key Evidence:**")
        for doc in case.evidence_details.documentary_exhibits[:5]:
            st.write(f"  • {doc.exhibit_number}: {doc.description}")


def render_game_over():
    """Render game over screen."""
    game: CourtroomGame = st.session_state.game
    summary = game.get_game_summary()

    st.markdown("""
    <div class="phase-banner" style="background: linear-gradient(90deg, #4CAF50 0%, #2E7D32 100%);">
        🏆 JUDGMENT DELIVERED - GAME COMPLETE
    </div>
    """, unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📊 Final Score")
        st.metric("Total Points", summary["score"]["total_points"])
        st.metric("Judge's Favor", f"{summary['score']['judge_favor']:.0f}%")
        st.metric("Overall Performance", f"{summary['score']['weighted_score']:.1f}%")

    with col2:
        st.subheader("📈 Statistics")
        stats = summary["statistics"]
        st.write(f"• Turns played: {summary['total_turns']}")
        st.write(f"• Objections: {stats['objections_sustained']}/{stats['objections_made']} sustained")
        st.write(f"• Evidence presented: {stats['evidence_presented']}")
        st.write(f"• Dynamic events: {stats['events_occurred']}")

    st.divider()

    # Performance breakdown
    st.subheader("📋 Performance Breakdown")
    details = summary["score"]["details"]
    cols = st.columns(3)
    metrics = [
        ("Legal Accuracy", details["legal_accuracy"]),
        ("Persuasiveness", details["persuasiveness"]),
        ("Evidence Handling", details["evidence_handling"]),
        ("Witness Exam", details["witness_examination"]),
        ("Objection Success", details["objection_success"]),
        ("Courtroom Decorum", details["courtroom_decorum"])
    ]
    for i, (name, value) in enumerate(metrics):
        with cols[i % 3]:
            st.metric(name, f"{value:.0f}")

    st.divider()

    if st.button("🔄 Play Again", use_container_width=True, type="primary"):
        st.session_state.game_started = False
        st.session_state.game = None
        st.session_state.game_messages = []
        st.rerun()


def render_case_data_tab():
    """Render the extracted case data tab."""
    st.header("📋 Case Data")

    if not st.session_state.case_data:
        st.info("Upload a PDF and extract case data to view structured information.")
        return

    case: CourtCase = st.session_state.case_data

    # Case overview
    with st.expander("🏛️ Case Metadata", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            st.write(f"**Case Title:** {case.case_metadata.case_title}")
            st.write(f"**Case Number:** {case.case_metadata.main_case_number or 'N/A'}")
            st.write(f"**Case Type:** {case.case_metadata.case_type.value}")
        with col2:
            st.write(f"**Court:** {case.case_metadata.court_name}")
            st.write(f"**Judge:** {case.case_metadata.judge_name or 'N/A'}")

    with st.expander("👥 Parties"):
        st.write("**Petitioners:**")
        for p in case.party_details.petitioners:
            st.write(f"  • {p.full_name} ({p.legal_status.value})")
        st.write("**Respondents:**")
        for r in case.party_details.respondents:
            st.write(f"  • {r.name} ({r.role.value})")

    with st.expander("❓ Issues Framed"):
        for issue in case.issues_framed.issues:
            st.write(f"**Issue {issue.issue_number}:** {issue.issue_text}")
            st.write(f"  Finding: {issue.finding.value}")

    with st.expander("📝 Evidence"):
        for w in case.evidence_details.oral_witnesses:
            st.write(f"**{w.witness_number} - {w.name}**")

    # Export
    if st.button("📥 Export as JSON"):
        json_data = case.model_dump_json(indent=2)
        st.download_button(
            "Download JSON",
            json_data,
            file_name="case_data.json",
            mime="application/json"
        )


def main():
    """Main application entry point."""
    init_session_state()
    render_header()
    config = render_sidebar()

    # Create tabs
    tab1, tab2, tab3 = st.tabs([
        "📄 Upload Case",
        "🎮 Play Game",
        "📋 Case Data"
    ])

    with tab1:
        render_pdf_upload_tab(config)

    with tab2:
        render_game_tab(config)

    with tab3:
        render_case_data_tab()


if __name__ == "__main__":
    main()
