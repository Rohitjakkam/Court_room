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
    ObjectionType, DynamicEvent, EvidenceCategory, EvidenceStatus,
    EvidenceObjectionType, EvidenceItem, EvidenceLocker,
    QuestioningStyle, WitnessReaction, WitnessStats, WitnessState,
    JudgePersonalityType, JudgeMood, JudgePersonality, JudgeState,
    PreparationCategory, PreparationTask, PreparationState,
    PressureLevel, ConfidenceState, TimePressureState, ConfidenceMeter,
    LegalResearchCategory, ResearchRelevance, CaseLawResult, LegalResearchState,
    SidebarRequestType, SidebarOutcome, AdjournmentReason, SidebarState,
    SIDEBAR_REQUEST_OPTIONS, ADJOURNMENT_DURATIONS,
    MistakeCategory, LegalPrincipleLevel, LegalPrinciple, LearningMoment,
    EducationProgress, EducationState, LEGAL_PRINCIPLES_DATABASE,
    TurningPointType, AnalysisCategory, GameAnalysis, AnalysisState
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
        'player_side': None,
        'game_step': 'upload',  # 'upload', 'select_side', 'preparation', 'playing'
        'uploaded_file_name': None,
        'last_etiquette_feedback': None,  # Store last etiquette feedback for display
        'preparation_initialized': False,  # Track if preparation phase is set up
        'pending_learning_moment': False  # Track if there's a learning moment to show
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def safe_extend_messages(new_messages):
    """Safely extend game_messages, ensuring it's always a list."""
    # Ensure game_messages is a list
    if not isinstance(st.session_state.get('game_messages'), list):
        st.session_state.game_messages = []

    # Handle different types of new_messages
    if new_messages is None:
        return
    elif isinstance(new_messages, list):
        st.session_state.game_messages.extend(new_messages)
    elif isinstance(new_messages, dict):
        # If it's a dict with 'messages' key, use that
        if 'messages' in new_messages:
            safe_extend_messages(new_messages['messages'])
        else:
            # Otherwise, skip (it's not a message)
            pass
    else:
        # Single message object
        st.session_state.game_messages.append(new_messages)


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

        # Pressure system toggle
        pressure_enabled = st.checkbox(
            "⏱️ Enable Time Pressure",
            value=True,
            help="Enable thinking time limits and confidence tracking. Disable for a relaxed experience."
        )

        # Store pressure setting in session state
        if 'pressure_enabled' not in st.session_state:
            st.session_state.pressure_enabled = pressure_enabled
        else:
            st.session_state.pressure_enabled = pressure_enabled

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
            "sim_mode": SimulationMode(sim_mode),
            "pressure_enabled": pressure_enabled
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

    # Import phase limits for display
    from game_engine import PHASE_LIMITS

    # Get phase timing info
    phase_limit = PHASE_LIMITS.get(game.state.phase)
    phase_turn = game.state.phase_turn_number
    max_turns = phase_limit.max_turns if phase_limit else "∞"

    # Determine Judge status indicator
    if phase_limit and phase_turn >= phase_limit.warning_at:
        if game.state.extension_granted:
            judge_status = "🔶 Extension Granted"
        else:
            judge_status = "⚠️ Judge: Wrap up"
    else:
        judge_status = "🟢 Judge: Proceeding"

    # Phase banner with Judge control info
    st.markdown(f"""
    <div class="phase-banner">
        📍 {game.state.phase.value.upper()} | Phase Turn: {phase_turn}/{max_turns} | {judge_status}
    </div>
    """, unsafe_allow_html=True)

    # Main game area
    col1, col2 = st.columns([3, 1])

    with col1:
        # Courtroom messages
        render_courtroom_log()

        st.divider()

        # Learning moment popup (takes priority to show educational content)
        if game.state.pending_learning_moment:
            render_learning_moment_popup()

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
            safe_extend_messages(messages)
        st.rerun()


def render_courtroom_log():
    """Render the courtroom message log."""
    st.subheader("📜 Court Proceedings")

    messages_container = st.container()

    # Safely get messages as a list
    messages = st.session_state.get('game_messages', [])
    if not isinstance(messages, list):
        messages = list(messages) if messages else []

    with messages_container:
        for msg in messages[-20:]:  # Show last 20 messages
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

    # If no actions available, inform player that Judge controls proceedings
    if not available_actions:
        st.info("⏳ **Awaiting Court Direction**")
        st.write("The Judge will direct the next stage of proceedings.")
        if st.button("🙋 Request Judge to Proceed", use_container_width=True, type="secondary"):
            with st.spinner("Requesting court direction..."):
                result = game.request_next_phase()
                safe_extend_messages(result.get("messages", []))
            st.rerun()
        return

    # Show last etiquette feedback if any (helps player learn)
    if st.session_state.last_etiquette_feedback:
        with st.expander("💡 Etiquette Feedback from Last Action", expanded=True):
            st.warning(st.session_state.last_etiquette_feedback)
            if st.button("✓ Got it", key="dismiss_etiquette"):
                st.session_state.last_etiquette_feedback = None
                st.rerun()

    action_labels = {
        ActionType.MAKE_ARGUMENT: "📢 Make Argument/Statement",
        ActionType.ASK_QUESTION: "❓ Ask Question",
        ActionType.RAISE_OBJECTION: "⚠️ Raise Objection",
        ActionType.PRESENT_EVIDENCE: "📄 Present Evidence",
        ActionType.CITE_CASE_LAW: "📚 Cite Case Law",
        ActionType.NO_QUESTIONS: "✋ No Further Questions",
        ActionType.REST_CASE: "⚖️ Conclude / Rest Case",
        # Evidence actions
        ActionType.MARK_FOR_IDENTIFICATION: "📋 Mark Evidence for ID",
        ActionType.MOVE_TO_ADMIT: "📤 Move to Admit Evidence",
        ActionType.OBJECT_TO_EVIDENCE: "🚫 Object to Evidence",
        ActionType.CHALLENGE_AUTHENTICITY: "❓ Challenge Authenticity"
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
    elif selected_action in [ActionType.NO_QUESTIONS, ActionType.REST_CASE]:
        content = ""
        objection_type = None
        if selected_action == ActionType.REST_CASE:
            st.info("💡 **Tip:** Use this when you've completed your submissions. The Judge will then decide to move to the next phase.")
    elif selected_action == ActionType.PRESENT_EVIDENCE:
        # Show evidence selection for presenting
        game_ref: CourtroomGame = st.session_state.game
        player_evidence = game_ref.get_player_evidence()
        available_evidence = [e for e in player_evidence if e.status in [EvidenceStatus.NOT_INTRODUCED, EvidenceStatus.MARKED_FOR_ID]]

        if available_evidence:
            selected_evidence = st.selectbox(
                "Select Evidence to Present",
                options=available_evidence,
                format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}..."
            )
            content = st.text_area(
                "Foundation/Context for this evidence:",
                height=100,
                placeholder="Explain how this evidence relates to your case..."
            )
            st.session_state.selected_evidence_id = selected_evidence.evidence_id if selected_evidence else None
        else:
            st.warning("No evidence available to present. Check the Evidence Locker.")
            content = ""
        objection_type = None
    elif selected_action == ActionType.OBJECT_TO_EVIDENCE:
        # Show opponent's offered evidence for objection
        game_ref: CourtroomGame = st.session_state.game
        opponent_evidence = game_ref.get_opponent_evidence()
        objectionable = [e for e in opponent_evidence if e.status == EvidenceStatus.OFFERED]

        if objectionable:
            selected_evidence = st.selectbox(
                "Select Evidence to Object To",
                options=objectionable,
                format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}..."
            )
            evidence_objection_type = st.selectbox(
                "Grounds for Objection",
                options=list(EvidenceObjectionType),
                format_func=lambda x: x.value
            )
            content = st.text_area("Additional grounds:", height=80)
            st.session_state.selected_evidence_id = selected_evidence.evidence_id if selected_evidence else None
            st.session_state.evidence_objection_type = evidence_objection_type
        else:
            st.info("No opponent evidence currently offered for admission.")
            content = ""
        objection_type = None

    elif selected_action == ActionType.MARK_FOR_IDENTIFICATION:
        # Show player's evidence not yet introduced
        game_ref: CourtroomGame = st.session_state.game
        player_evidence = game_ref.get_player_evidence()
        available = [e for e in player_evidence if e.status == EvidenceStatus.NOT_INTRODUCED]

        if available:
            selected_evidence = st.selectbox(
                "Select Evidence to Mark",
                options=available,
                format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}..."
            )
            content = f"I would like to mark {selected_evidence.exhibit_number} for identification."
            st.session_state.selected_evidence_id = selected_evidence.evidence_id if selected_evidence else None
        else:
            st.info("No evidence available to mark. All evidence has been introduced.")
            content = ""
        objection_type = None

    elif selected_action == ActionType.MOVE_TO_ADMIT:
        # Show player's marked evidence ready for admission
        game_ref: CourtroomGame = st.session_state.game
        player_evidence = game_ref.get_player_evidence()
        ready = [e for e in player_evidence if e.status in [EvidenceStatus.NOT_INTRODUCED, EvidenceStatus.MARKED_FOR_ID]]

        if ready:
            selected_evidence = st.selectbox(
                "Select Evidence to Admit",
                options=ready,
                format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}... ({x.status.value})"
            )
            content = st.text_area(
                "Foundation/Argument for admission:",
                height=100,
                placeholder="Explain why this evidence should be admitted..."
            )
            st.session_state.selected_evidence_id = selected_evidence.evidence_id if selected_evidence else None
        else:
            st.info("No evidence ready for admission.")
            content = ""
        objection_type = None

    elif selected_action == ActionType.CHALLENGE_AUTHENTICITY:
        # Show opponent's admitted evidence that can be challenged
        game_ref: CourtroomGame = st.session_state.game
        opponent_evidence = game_ref.get_opponent_evidence()
        challengeable = [e for e in opponent_evidence if e.status == EvidenceStatus.ADMITTED and not e.authenticity_challenged]

        if challengeable:
            selected_evidence = st.selectbox(
                "Select Evidence to Challenge",
                options=challengeable,
                format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}..."
            )
            content = st.text_area(
                "Grounds for challenging authenticity:",
                height=100,
                placeholder="Explain why you believe this evidence is not authentic..."
            )
            st.session_state.selected_evidence_id = selected_evidence.evidence_id if selected_evidence else None
        else:
            st.info("No opponent evidence available to challenge.")
            content = ""
        objection_type = None

    else:
        content = st.text_area(
            "Your statement/question:",
            height=150,
            placeholder="Type your argument, question, or statement here..."
        )
        objection_type = None

    # Timer and confidence inline display
    timer_col, conf_col = st.columns(2)
    with timer_col:
        render_timer_inline()
    with conf_col:
        render_confidence_inline()

    # Submit action
    col1, col2 = st.columns([3, 1])

    with col1:
        if st.button("📤 Submit Action", use_container_width=True, type="primary"):
            if selected_action not in [ActionType.NO_QUESTIONS, ActionType.REST_CASE] and not content.strip():
                st.error("Please enter your statement/question")
            else:
                # Build GameAction with appropriate fields based on action type
                evidence_id = None
                evidence_objection_type = None

                # Get evidence_id for evidence-related actions
                if selected_action in [ActionType.PRESENT_EVIDENCE, ActionType.MARK_FOR_IDENTIFICATION,
                                       ActionType.MOVE_TO_ADMIT, ActionType.OBJECT_TO_EVIDENCE,
                                       ActionType.CHALLENGE_AUTHENTICITY]:
                    evidence_id = st.session_state.get('selected_evidence_id')

                # Get evidence objection type for OBJECT_TO_EVIDENCE
                if selected_action == ActionType.OBJECT_TO_EVIDENCE:
                    evidence_objection_type = st.session_state.get('evidence_objection_type')

                action = GameAction(
                    action_type=selected_action,
                    content=content,
                    objection_type=objection_type if selected_action == ActionType.RAISE_OBJECTION else None,
                    evidence_id=evidence_id,
                    evidence_objection_type=evidence_objection_type
                )

                with st.spinner("Court proceedings in progress..."):
                    result = game.process_player_action(action)

                # Add messages to log
                safe_extend_messages(result.get("messages", []))

                # Show etiquette feedback if violations occurred
                if result.get("etiquette_violations"):
                    violations = result["etiquette_violations"]
                    severity_icons = {"minor": "📝", "moderate": "⚠️", "serious": "🚨"}
                    for v in violations:
                        icon = severity_icons.get(v["severity"], "📝")
                        st.toast(f"{icon} Etiquette: {v['description']}", icon="⚖️")

                    # Store feedback for display
                    if result.get("etiquette_feedback"):
                        st.session_state.last_etiquette_feedback = result["etiquette_feedback"]

                # Show timing feedback
                timing_stats = result.get("timing_stats") or {}
                if timing_stats.get("time_expired"):
                    st.toast("⏰ Time expired! Your response may be less effective.", icon="⚠️")
                elif timing_stats.get("was_rushed"):
                    st.toast("⚡ Quick response! Judge may question your certainty.", icon="💨")
                elif timing_stats.get("judge_prompted"):
                    st.toast("⏱️ Judge had to prompt you - try to respond faster.", icon="⏰")

                # Show confidence updates
                confidence_update = result.get("confidence_update") or {}
                if confidence_update.get("updated"):
                    total_change = confidence_update.get("total_change", 0)
                    if total_change >= 5:
                        st.toast(f"📈 Confidence +{total_change:.0f}%", icon="💪")
                    elif total_change <= -5:
                        st.toast(f"📉 Confidence {total_change:.0f}%", icon="😰")

                # Show judge confidence remark if any
                if result.get("judge_confidence_remark"):
                    st.toast(f"👨‍⚖️ {result['judge_confidence_remark']}", icon="⚖️")

                # Show Judge warning notification if any
                if result.get("judge_warning"):
                    st.toast(f"⚠️ Judge issued a warning: {result['judge_warning']}", icon="👨‍⚖️")

                # Show phase change notification
                if result.get("judge_advanced_phase"):
                    st.toast(f"📋 Judge advanced to: {result.get('new_phase', 'Next Phase')}", icon="⚖️")

                # Handle events
                if result["events"]:
                    st.session_state.pending_event = result["events"][0]

                # Check for legal mistakes and trigger learning moments
                if game.state.education_enabled and content.strip():
                    mistake_check = game.check_action_for_mistakes(
                        content,
                        selected_action.value
                    )
                    if mistake_check.get("learning_moment_triggered"):
                        st.session_state.pending_learning_moment = True

                st.rerun()

    with col2:
        if st.button("🔄 Reset", use_container_width=True):
            st.session_state.game_started = False
            st.session_state.game = None
            st.session_state.game_messages = []
            st.session_state.game_step = 'upload'
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
                    safe_extend_messages(result.get("messages", []))

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

    # Witness examination stats
    st.divider()
    st.write("**Witness Exam:**")
    st.write(f"• Contradictions: {game.state.total_contradictions_caught}")
    st.write(f"• Hostile witnesses: {game.state.witnesses_turned_hostile}")
    st.write(f"• Breakdowns: {game.state.witness_breakdowns}")


def render_judge_personality_panel():
    """Render the judge personality panel showing judge info and mood."""
    game: CourtroomGame = st.session_state.game

    judge_info = game.get_judge_display_info()

    if judge_info.get("error"):
        return

    with st.expander("👨‍⚖️ The Judge", expanded=True):
        # Judge name and type
        st.subheader(f"{judge_info['mood_emoji']} {judge_info['name']}")
        st.caption(f"{judge_info['title']} | {judge_info['personality_type'].replace('_', ' ').title()}")

        # Current mood indicator
        mood = judge_info['current_mood']
        mood_colors = {
            "neutral": "gray",
            "pleased": "green",
            "impatient": "orange",
            "annoyed": "red",
            "interested": "blue",
            "skeptical": "purple"
        }
        mood_color = mood_colors.get(mood, "gray")

        st.markdown(f"**Mood:** :{mood_color}[{mood.title()}]")

        # Patience meter
        patience = judge_info['patience_level']
        if patience > 70:
            st.progress(patience / 100, text=f"Patience: {patience:.0f}%")
        elif patience > 40:
            st.progress(patience / 100, text=f"⚠️ Patience: {patience:.0f}%")
        else:
            st.progress(patience / 100, text=f"🚨 Patience: {patience:.0f}%")

        st.divider()

        # Judge characteristics
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Traits:**")
            if judge_info.get('prefers_brevity'):
                st.write("• Prefers brevity")
            else:
                st.write("• Allows detail")

            if judge_info.get('values_precedent'):
                st.write("• Values citations")
            else:
                st.write("• Less focused on precedent")

        with col2:
            st.write("**Focus:**")
            tech_focus = judge_info.get('technical_focus', 50)
            if tech_focus > 70:
                st.write("• Highly technical")
            elif tech_focus > 40:
                st.write("• Moderate technical")
            else:
                st.write("• Practical/factual")

        # Stats
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Questions", judge_info['questions_asked'])
        with col2:
            st.metric("Interruptions", judge_info['interruptions'])
        with col3:
            st.metric("Warnings", judge_info['warnings_given'])

        # Strengths and weaknesses
        with st.expander("📋 Judge Profile", expanded=False):
            st.write(f"*{judge_info['description']}*")

            st.write("**✅ Appreciates:**")
            for s in judge_info.get('strengths', []):
                st.write(f"  • {s}")

            st.write("**⚠️ Dislikes:**")
            for w in judge_info.get('weaknesses', []):
                st.write(f"  • {w}")

        # Strategic tips
        st.divider()
        st.write("**💡 Strategy Tips:**")
        tips = game.get_judge_tips()
        for tip in tips[:4]:  # Show max 4 tips
            st.write(f"  {tip}")


def render_quick_reference():
    """Render quick reference panel."""
    game: CourtroomGame = st.session_state.game
    case = game.case

    # Judge Personality Panel
    render_judge_personality_panel()

    # Real-Time Pressure Panel (Timer & Confidence)
    render_pressure_panel()

    # Court Etiquette Tips Panel
    with st.expander("⚖️ Court Etiquette", expanded=True):
        # Etiquette status
        decorum_score = game.state.score.courtroom_decorum
        streak = game.state.proper_decorum_streak
        warnings = game.state.etiquette_warnings

        # Status indicator
        if warnings == 0 and streak >= 3:
            st.success(f"✅ Excellent decorum! Streak: {streak}")
        elif warnings == 0:
            st.info(f"📋 Good standing | Streak: {streak}")
        elif warnings == 1:
            st.warning(f"⚠️ 1 warning received")
        else:
            st.error(f"🚨 {warnings} warnings - Be careful!")

        st.divider()

        # Tips for current phase
        st.write("**📝 Protocol Tips:**")
        tips = game.get_etiquette_tips()
        for tip in tips:
            st.write(f"• {tip}")

    with st.expander("📚 Quick Reference", expanded=False):
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

    # Witness Credibility Panel
    render_witness_credibility_panel()

    # Evidence Locker Panel
    render_evidence_locker_panel()

    # Legal Research Panel
    render_legal_research_panel()

    # Sidebar Conference Panel
    render_sidebar_conference_panel()

    # Education Panel
    render_education_panel()

    # Legal Principles Reference
    render_legal_principles_reference()


def render_witness_credibility_panel():
    """Render the witness credibility panel showing current witness stats."""
    game: CourtroomGame = st.session_state.game

    # Check if we're in an examination phase
    is_examination_phase = game.state.phase in [
        GamePhase.PETITIONER_WITNESS_EXAM,
        GamePhase.RESPONDENT_WITNESS_EXAM,
        GamePhase.CROSS_EXAMINATION
    ]

    with st.expander("🧑 Witness Analysis", expanded=is_examination_phase):
        # Current witness stats
        if game.state.current_witness:
            witness = game.state.current_witness
            witness_id = f"{witness.witness_type.value}_{witness.witness_number}"

            st.subheader(f"📋 {witness.name}")
            st.caption(f"{witness.witness_number} | {'Your witness' if _is_player_witness(game) else 'Opposing witness'}")

            # Get credibility display info
            cred_display = game.get_witness_credibility_display(witness_id)

            if cred_display.get("error"):
                st.info("Witness stats not available")
            else:
                # Current reaction
                reaction = cred_display.get("current_reaction", "cooperative")
                reaction_emoji = {
                    "cooperative": "😊",
                    "defensive": "😐",
                    "hostile": "😠",
                    "nervous": "😰",
                    "confused": "😕",
                    "evasive": "🤐",
                    "confident": "😎",
                    "breakdown": "😢"
                }.get(reaction, "😐")

                st.write(f"**Current State:** {reaction_emoji} {reaction.title()}")

                st.divider()

                # Stats display (based on reveal percentage)
                reveal_pct = cred_display.get("reveal_percentage", 0.3)

                # Show credibility meter
                st.write("**Witness Assessment:**")

                # Use columns for stat display
                col1, col2 = st.columns(2)

                with col1:
                    if "credibility" in cred_display:
                        # Full stats revealed
                        st.metric("Credibility", f"{cred_display['credibility']}%")
                    elif "credibility_hint" in cred_display:
                        st.write(f"Credibility: {cred_display['credibility_hint']}")

                    if "nervousness" in cred_display:
                        st.metric("Nervousness", f"{cred_display['nervousness']}%")
                    elif "nervousness_hint" in cred_display:
                        st.write(f"Nervousness: {cred_display['nervousness_hint']}")

                with col2:
                    if "hostility" in cred_display:
                        st.metric("Hostility", f"{cred_display['hostility']}%")
                    elif "hostility_hint" in cred_display:
                        st.write(f"Hostility: {cred_display['hostility_hint']}")

                    if "memory_accuracy" in cred_display:
                        st.metric("Memory", f"{cred_display['memory_accuracy']}%")
                    elif "memory_hint" in cred_display:
                        st.write(f"Memory: {cred_display['memory_hint']}")

                # Progress bar for reveal
                st.caption(f"Analysis: {int(reveal_pct * 100)}% complete")
                st.progress(reveal_pct)

                # Special indicators
                if cred_display.get("is_hostile"):
                    st.error("⚠️ HOSTILE WITNESS - Leading questions allowed")
                if cred_display.get("has_broken_down"):
                    st.warning("😢 Witness has had emotional breakdown")
                if cred_display.get("rapport_built"):
                    st.success("🤝 Good rapport established")

                # Contradictions caught
                contradictions = cred_display.get("contradictions_caught", 0)
                if contradictions > 0:
                    st.info(f"📊 Contradictions caught: {contradictions}")

                st.divider()

                # Strategic tips
                st.write("**💡 Strategy Tips:**")
                tips = game.get_witness_tips()
                for tip in tips:
                    st.write(f"  {tip}")

                # Questions asked
                st.caption(f"Questions asked: {cred_display.get('questions_asked', 0)}")

        else:
            st.info("No witness currently being examined.")

            # Show summary of all witnesses
            st.write("**📊 Witness Summary:**")

            witness_states = game.get_all_witness_states()
            if witness_states:
                for wid, ws in witness_states.items():
                    status_icon = "⚪"
                    if ws.stats.is_hostile:
                        status_icon = "😠"
                    elif ws.stats.has_broken_down:
                        status_icon = "😢"
                    elif ws.questions_asked > 0:
                        status_icon = "✅"

                    st.write(f"  {status_icon} {ws.witness_name} ({ws.witness_type})")
                    if ws.stats.contradictions_caught > 0:
                        st.caption(f"    └─ {ws.stats.contradictions_caught} contradiction(s)")
            else:
                st.caption("Witness data will load when examination begins.")

        # Global witness stats
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Hostile", game.state.witnesses_turned_hostile)
        with col2:
            st.metric("Contradictions", game.state.total_contradictions_caught)
        with col3:
            st.metric("Breakdowns", game.state.witness_breakdowns)


def _is_player_witness(game: CourtroomGame) -> bool:
    """Check if current witness belongs to player's side."""
    if not game.state.current_witness:
        return False
    witness = game.state.current_witness
    player_side = game.state.player_side
    if player_side == PlayerSide.PETITIONER:
        return witness.witness_type.value == "PW"
    else:
        return witness.witness_type.value == "RW"


def render_evidence_locker_panel():
    """Render the evidence locker panel showing all evidence and their status."""
    game: CourtroomGame = st.session_state.game
    locker = game.get_evidence_locker()

    with st.expander("📁 Evidence Locker", expanded=True):
        # Summary stats
        total_evidence = len(locker.get_all_evidence())
        admitted = len(locker.admitted_evidence)
        excluded = len(locker.excluded_evidence)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total", total_evidence)
        with col2:
            st.metric("Admitted", admitted, delta=None)
        with col3:
            st.metric("Excluded", excluded, delta=None)

        st.divider()

        # Tab for different views
        tab1, tab2, tab3 = st.tabs(["📄 Your Evidence", "📄 Opponent's", "✅ Admitted"])

        with tab1:
            player_evidence = game.get_player_evidence()
            if player_evidence:
                for item in player_evidence:
                    status_icons = {
                        EvidenceStatus.NOT_INTRODUCED: "⚪",
                        EvidenceStatus.MARKED_FOR_ID: "🔵",
                        EvidenceStatus.OFFERED: "🟡",
                        EvidenceStatus.OBJECTED: "🟠",
                        EvidenceStatus.ADMITTED: "🟢",
                        EvidenceStatus.EXCLUDED: "🔴",
                        EvidenceStatus.WITHDRAWN: "⚫"
                    }
                    icon = status_icons.get(item.status, "⚪")

                    with st.container():
                        st.markdown(f"""
                        **{icon} {item.exhibit_number}** - {item.title[:40]}
                        - Category: {item.category.value}
                        - Status: {item.status.value}
                        """)

                        # Action buttons based on status
                        if item.status == EvidenceStatus.NOT_INTRODUCED:
                            col1, col2 = st.columns(2)
                            with col1:
                                if st.button(f"📋 Mark for ID", key=f"mark_{item.evidence_id}", use_container_width=True):
                                    result = game.mark_evidence_for_identification(item.evidence_id)
                                    if result["success"]:
                                        safe_extend_messages(result.get("messages", []))
                                        st.rerun()
                            with col2:
                                if st.button(f"📤 Admit", key=f"admit_{item.evidence_id}", use_container_width=True):
                                    result = game.move_to_admit_evidence(item.evidence_id)
                                    if result["success"]:
                                        safe_extend_messages(result.get("messages", []))
                                        if result.get("admitted"):
                                            st.toast(f"✅ {item.exhibit_number} admitted!", icon="📄")
                                        else:
                                            st.toast(f"❌ {item.exhibit_number} excluded", icon="🚫")
                                        st.rerun()

                        elif item.status == EvidenceStatus.MARKED_FOR_ID:
                            if st.button(f"📤 Move to Admit", key=f"admit2_{item.evidence_id}", use_container_width=True):
                                result = game.move_to_admit_evidence(item.evidence_id)
                                if result["success"]:
                                    safe_extend_messages(result.get("messages", []))
                                    st.rerun()

                        st.divider()
            else:
                st.info("No evidence available")

        with tab2:
            opponent_evidence = game.get_opponent_evidence()
            if opponent_evidence:
                for item in opponent_evidence:
                    status_icons = {
                        EvidenceStatus.NOT_INTRODUCED: "⚪",
                        EvidenceStatus.MARKED_FOR_ID: "🔵",
                        EvidenceStatus.OFFERED: "🟡",
                        EvidenceStatus.OBJECTED: "🟠",
                        EvidenceStatus.ADMITTED: "🟢",
                        EvidenceStatus.EXCLUDED: "🔴",
                    }
                    icon = status_icons.get(item.status, "⚪")

                    st.markdown(f"""
                    **{icon} {item.exhibit_number}** - {item.title[:40]}
                    - Category: {item.category.value}
                    - Status: {item.status.value}
                    """)

                    # Allow challenging admitted evidence
                    if item.status == EvidenceStatus.ADMITTED and not item.authenticity_challenged:
                        if st.button(f"⚠️ Challenge Authenticity", key=f"challenge_{item.evidence_id}"):
                            st.session_state.challenging_evidence = item.evidence_id

                    st.divider()
            else:
                st.info("No opponent evidence yet")

        with tab3:
            admitted_items = locker.get_admitted_items()
            if admitted_items:
                for item in admitted_items:
                    owner = "👤 Yours" if game._is_player_evidence(item) else "🤖 Opponent"
                    st.markdown(f"""
                    **✅ {item.exhibit_number}** - {item.title[:40]}
                    - {owner} | {item.category.value}
                    {"- ⚠️ Authenticity Challenged" if item.authenticity_challenged else ""}
                    """)
                    st.divider()
            else:
                st.info("No evidence admitted yet")

        # Evidence legend
        with st.expander("📖 Status Legend", expanded=False):
            st.markdown("""
            - ⚪ **Not Introduced** - In your locker, not yet shown
            - 🔵 **Marked for ID** - Marked as exhibit for identification
            - 🟡 **Offered** - Moved to admit, awaiting ruling
            - 🟠 **Objected** - Opponent objected, awaiting ruling
            - 🟢 **Admitted** - Judge admitted into evidence
            - 🔴 **Excluded** - Judge excluded/rejected
            """)


def render_pressure_panel():
    """Render the real-time pressure panel with timer and confidence meter."""
    game: CourtroomGame = st.session_state.game

    if not game.state.pressure_enabled:
        return

    # Get display info
    pressure_info = game.get_pressure_display()
    confidence_info = game.get_confidence_display()

    with st.expander("⏱️ Pressure & Confidence", expanded=True):
        # Timer section
        st.subheader("⏱️ Response Timer")

        if pressure_info.get("timer_active"):
            time_remaining = pressure_info.get("time_remaining", 0)
            time_limit = pressure_info.get("time_limit", 60)
            time_pct = pressure_info.get("time_percentage", 1.0)
            pressure_level = pressure_info.get("pressure_level", "calm")
            pressure_emoji = pressure_info.get("pressure_emoji", "🟢")

            # Time display with color based on pressure
            if pressure_level == "critical":
                st.error(f"{pressure_emoji} **{time_remaining:.0f}s** remaining!")
            elif pressure_level == "high":
                st.warning(f"{pressure_emoji} **{time_remaining:.0f}s** remaining")
            elif pressure_level == "moderate":
                st.info(f"{pressure_emoji} **{time_remaining:.0f}s** remaining")
            else:
                st.success(f"{pressure_emoji} **{time_remaining:.0f}s** remaining")

            # Progress bar
            st.progress(time_pct, text=f"Time: {time_remaining:.0f}/{time_limit}s")

            # Extension button if available
            if pressure_info.get("extensions_remaining", 0) > 0:
                if st.button(f"🕐 Request Extension ({pressure_info['extensions_remaining']} left)",
                           use_container_width=True, key="request_extension"):
                    result = game.request_time_extension()
                    if result.get("granted"):
                        st.toast(f"✅ {result['message']}", icon="⏰")
                    else:
                        st.toast(f"❌ {result['message']}", icon="⚠️")
                    st.rerun()
        else:
            st.info("Timer starts when it's your turn to respond.")

        st.divider()

        # Confidence meter section
        st.subheader("📊 Confidence Meter")

        if confidence_info.get("active"):
            confidence_score = confidence_info.get("confidence_score", 50)
            confidence_state = confidence_info.get("confidence_state", "steady")
            state_emoji = confidence_info.get("state_emoji", "😐")
            trend = confidence_info.get("trend", "stable")

            # Trend arrows
            trend_icons = {
                "rising": "📈",
                "falling": "📉",
                "stable": "➡️"
            }
            trend_icon = trend_icons.get(trend, "➡️")

            # Confidence display
            st.metric(
                label=f"{state_emoji} {confidence_state.title()}",
                value=f"{confidence_score:.0f}%",
                delta=f"{trend_icon} {trend.title()}"
            )

            # Confidence progress bar with color
            if confidence_score >= 70:
                st.progress(confidence_score / 100, text="Confidence Level")
            elif confidence_score >= 45:
                st.progress(confidence_score / 100, text="⚠️ Confidence Level")
            else:
                st.progress(confidence_score / 100, text="🚨 Low Confidence!")

            # Sub-metrics
            col1, col2 = st.columns(2)
            with col1:
                st.caption(f"Judge Approval: {confidence_info.get('judge_approval', 50):.0f}%")
                st.caption(f"Argument Flow: {confidence_info.get('argument_coherence', 50):.0f}%")
            with col2:
                st.caption(f"Witness Control: {confidence_info.get('witness_control', 50):.0f}%")
                st.caption(f"Evidence: {confidence_info.get('evidence_handling', 50):.0f}%")

            # Streaks
            confident_streak = confidence_info.get("confident_streak", 0)
            if confident_streak >= 3:
                st.success(f"🔥 Confidence streak: {confident_streak}")

            # Warnings
            hesitations = confidence_info.get("hesitation_count", 0)
            if hesitations > 2:
                st.warning(f"⏰ Hesitations: {hesitations} - respond more promptly!")

        st.divider()

        # Stats summary
        st.caption("**Session Stats:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.caption(f"Actions: {pressure_info.get('total_actions', 0)}")
        with col2:
            st.caption(f"Rushed: {pressure_info.get('rushed_actions', 0)}")
        with col3:
            avg_time = pressure_info.get('average_response_time', 0)
            st.caption(f"Avg: {avg_time:.1f}s")

        # Tips
        tips = game.get_pressure_tips()
        if tips:
            st.divider()
            st.caption("**💡 Tips:**")
            for tip in tips[:2]:
                st.caption(tip)


def render_timer_inline():
    """Render an inline timer display for the action input area."""
    game: CourtroomGame = st.session_state.game

    if not game.state.pressure_enabled:
        return

    pressure_info = game.get_pressure_display()

    if pressure_info.get("timer_active"):
        time_remaining = pressure_info.get("time_remaining", 0)
        pressure_level = pressure_info.get("pressure_level", "calm")
        pressure_emoji = pressure_info.get("pressure_emoji", "🟢")

        # Compact timer display
        if pressure_level == "critical":
            st.error(f"{pressure_emoji} **{time_remaining:.0f}s** - Respond now!")
        elif pressure_level == "high":
            st.warning(f"{pressure_emoji} **{time_remaining:.0f}s** - Time running low!")
        else:
            st.info(f"{pressure_emoji} **{time_remaining:.0f}s** remaining")


def render_confidence_inline():
    """Render an inline confidence display."""
    game: CourtroomGame = st.session_state.game

    if not game.state.pressure_enabled:
        return

    confidence_info = game.get_confidence_display()

    if confidence_info.get("active"):
        confidence_score = confidence_info.get("confidence_score", 50)
        state_emoji = confidence_info.get("state_emoji", "😐")
        confidence_state = confidence_info.get("confidence_state", "steady")

        # Color-coded confidence badge
        if confidence_score >= 70:
            st.success(f"{state_emoji} **{confidence_state.title()}** ({confidence_score:.0f}%)")
        elif confidence_score >= 45:
            st.warning(f"{state_emoji} **{confidence_state.title()}** ({confidence_score:.0f}%)")
        else:
            st.error(f"{state_emoji} **{confidence_state.title()}** ({confidence_score:.0f}%)")


def render_legal_research_panel():
    """Render the legal research panel for mid-trial case law research."""
    game: CourtroomGame = st.session_state.game

    if not game.state.research_enabled:
        return

    research_info = game.get_research_display()

    with st.expander("📚 Legal Research", expanded=False):
        st.subheader("📖 Mid-Trial Research")
        st.caption("Search for case laws to strengthen your arguments (costs a turn)")

        # Research status
        can_research = game.can_do_research()
        remaining = can_research.get("remaining", 0)

        col1, col2 = st.columns(2)
        with col1:
            if can_research.get("can_research"):
                st.success(f"✅ {remaining} research action(s) available")
            else:
                st.warning(f"❌ {can_research.get('reason', 'Cannot research')}")
        with col2:
            st.metric("Discovered", research_info.get("discovered_count", 0))

        # Warning if judge is impatient
        if can_research.get("warning"):
            st.warning(can_research["warning"])

        st.divider()

        # Search interface
        if can_research.get("can_research"):
            st.write("**🔍 Search Case Laws:**")

            # Search input
            search_query = st.text_input(
                "Enter search terms:",
                placeholder="e.g., evidence, compensation, negligence, contract breach...",
                key="research_query"
            )

            # Quick search buttons
            st.caption("Quick search:")
            quick_cols = st.columns(4)
            quick_searches = ["evidence", "compensation", "procedure", "constitutional"]
            for i, term in enumerate(quick_searches):
                with quick_cols[i]:
                    if st.button(f"📖 {term.title()}", key=f"quick_{term}", use_container_width=True):
                        search_query = term

            if st.button("🔍 Search", use_container_width=True, type="primary", disabled=not search_query):
                if search_query:
                    with st.spinner("Researching case laws..."):
                        result = game.search_case_law(search_query)

                    if result.get("success"):
                        found = result.get("results", [])
                        if found:
                            st.success(f"✅ Found {len(found)} relevant case(s)!")
                            for case in found:
                                st.toast(f"📋 Found: {case.citation}", icon="📚")
                        else:
                            st.info("No new cases found for this query. Try different terms.")

                        # Show judge reaction
                        if result.get("judge_reaction"):
                            st.warning(f"👨‍⚖️ {result['judge_reaction']}")
                    else:
                        st.error(result.get("error", "Search failed"))

                    st.rerun()

        st.divider()

        # Discovered cases section
        discovered = game.get_discovered_cases()
        uncited = game.get_uncited_cases()

        if discovered:
            st.write(f"**📋 Discovered Cases ({len(discovered)}):**")

            # Tabs for uncited vs cited
            tab1, tab2 = st.tabs([f"📝 Uncited ({len(uncited)})", f"✅ Cited ({len(discovered) - len(uncited)})"])

            with tab1:
                if uncited:
                    for case in uncited:
                        with st.container():
                            # Relevance indicator
                            relevance_icons = {
                                ResearchRelevance.HIGHLY_RELEVANT: "🟢",
                                ResearchRelevance.RELEVANT: "🔵",
                                ResearchRelevance.SOMEWHAT_RELEVANT: "🟡",
                                ResearchRelevance.TANGENTIAL: "⚪"
                            }
                            rel_icon = relevance_icons.get(case.relevance, "⚪")

                            st.markdown(f"**{rel_icon} {case.citation}**")
                            st.caption(f"*{case.case_name}* ({case.court}, {case.year})")

                            with st.expander("View Details", expanded=False):
                                st.write(f"**Key Principle:** {case.key_principle}")
                                st.write(f"**Application:** {case.applicable_facts}")
                                st.write(f"**Strength:** {case.strength_score:.0f}%")

                            # Cite button
                            col1, col2 = st.columns([3, 1])
                            with col1:
                                cite_arg = st.text_input(
                                    "Argument (optional):",
                                    placeholder="How does this apply to your case?",
                                    key=f"cite_arg_{case.citation}",
                                    label_visibility="collapsed"
                                )
                            with col2:
                                if st.button("📢 Cite", key=f"cite_{case.citation}", use_container_width=True):
                                    result = game.cite_case_law(case.citation, cite_arg)
                                    if result.get("success"):
                                        st.toast(f"✅ Cited {case.citation}! +{result.get('score_bonus', 0):.0f} pts", icon="📚")
                                        safe_extend_messages(result.get("messages", []))
                                    else:
                                        st.error(result.get("error", "Failed to cite"))
                                    st.rerun()

                            st.divider()
                else:
                    st.info("No uncited cases. Research more or all cases have been cited.")

            with tab2:
                cited_cases = [c for c in discovered if c.has_been_cited]
                if cited_cases:
                    for case in cited_cases:
                        st.markdown(f"✅ **{case.citation}** - {case.case_name[:40]}...")
                else:
                    st.info("No cases cited yet.")

        else:
            st.info("No cases discovered yet. Use the search above to find relevant case laws.")

        st.divider()

        # Research tips
        tips = game.get_research_tips()
        if tips:
            st.caption("**💡 Tips:**")
            for tip in tips[:3]:
                st.caption(tip)

        # Stats
        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Research", research_info.get("total_research", 0))
        with col2:
            st.metric("Cases Cited", research_info.get("cited_count", 0))
        with col3:
            if research_info.get("judge_impressed"):
                st.metric("Judge", "✅ Impressed")
            elif research_info.get("judge_warnings", 0) > 0:
                st.metric("Judge", f"⚠️ {research_info['judge_warnings']} warning(s)")
            else:
                st.metric("Judge", "😐 Neutral")


def render_sidebar_conference_panel():
    """Render the sidebar/chamber conference panel."""
    game: CourtroomGame = st.session_state.game

    if not game.state.sidebar_enabled:
        return

    sidebar_info = game.get_sidebar_display()

    with st.expander("⚖️ Sidebar Conference", expanded=False):
        st.subheader("🔒 Private Conference")
        st.caption("Request a private discussion with the judge")

        # Check if currently in sidebar
        if sidebar_info.get("in_conference"):
            st.warning("🔒 **Currently in sidebar conference**")

            # Show end sidebar button
            if st.button("✅ End Sidebar Conference", use_container_width=True, type="primary"):
                result = game.end_sidebar_conference()
                if result.get("success"):
                    safe_extend_messages(result.get("messages", []))
                    st.toast("📋 Sidebar concluded - returning to proceedings", icon="⚖️")
                st.rerun()

            st.divider()

            # Settlement offer section (only during sidebar)
            st.write("**🤝 Settlement Discussion:**")
            settlement_terms = st.text_area(
                "Settlement terms:",
                placeholder="Propose settlement terms...",
                key="settlement_terms"
            )
            settlement_amount = st.number_input(
                "Settlement amount (if applicable):",
                min_value=0,
                value=0,
                key="settlement_amount"
            )

            if st.button("📝 Make Settlement Offer", use_container_width=True):
                if settlement_terms:
                    result = game.make_settlement_offer(
                        terms=settlement_terms,
                        amount=settlement_amount if settlement_amount > 0 else None
                    )
                    if result.get("success"):
                        safe_extend_messages(result.get("messages", []))
                        if result.get("accepted"):
                            st.toast("✅ Settlement ACCEPTED!", icon="🎉")
                        elif result.get("countered"):
                            st.toast(f"🔄 Counter-offer: {result.get('counter_terms')}", icon="🤝")
                        elif result.get("rejected"):
                            st.toast("❌ Settlement rejected", icon="😞")
                    st.rerun()
                else:
                    st.error("Please enter settlement terms")

        else:
            # Sidebar request interface
            can_sidebar = game.can_request_sidebar()
            remaining = can_sidebar.get("remaining", 0)

            # Status display
            col1, col2 = st.columns(2)
            with col1:
                if can_sidebar.get("can_request"):
                    st.success(f"✅ {remaining} sidebar(s) available")
                else:
                    st.warning(f"❌ {can_sidebar.get('reason', 'Cannot request')}")
            with col2:
                patience = sidebar_info.get("judge_patience", 100)
                if patience > 70:
                    st.metric("Judge Patience", f"{patience:.0f}%")
                elif patience > 40:
                    st.metric("Judge Patience", f"⚠️ {patience:.0f}%")
                else:
                    st.metric("Judge Patience", f"🚨 {patience:.0f}%")

            if can_sidebar.get("warning"):
                st.warning(can_sidebar["warning"])

            st.divider()

            if can_sidebar.get("can_request"):
                st.write("**📋 Request Type:**")

                # Request type selection
                request_options = []
                for req_type, info in SIDEBAR_REQUEST_OPTIONS.items():
                    request_options.append((req_type, f"{info['icon']} {info['title']}"))

                selected_type = st.selectbox(
                    "Select request type:",
                    options=[opt[0] for opt in request_options],
                    format_func=lambda x: next(opt[1] for opt in request_options if opt[0] == x),
                    key="sidebar_request_type"
                )

                # Show description
                if selected_type:
                    info = SIDEBAR_REQUEST_OPTIONS.get(selected_type, {})
                    st.caption(f"*{info.get('description', '')}*")
                    st.caption(f"Turn cost: {info.get('turn_cost', 1)}")

                st.divider()

                # Reason input
                reason = st.text_input(
                    "Reason for request:",
                    placeholder="State your reason for requesting this sidebar...",
                    key="sidebar_reason"
                )

                # Additional fields based on request type
                evidence_id = None
                witness_id = None
                adjournment_reason = None
                adjournment_duration = None
                supporting_argument = ""

                if selected_type == SidebarRequestType.EXCLUDE_EVIDENCE:
                    # Show evidence to exclude
                    opponent_evidence = game.get_opponent_evidence()
                    admitted = [e for e in opponent_evidence if e.status == EvidenceStatus.ADMITTED]
                    if admitted:
                        selected_evidence = st.selectbox(
                            "Evidence to exclude:",
                            options=admitted,
                            format_func=lambda x: f"{x.exhibit_number}: {x.title[:40]}...",
                            key="exclude_evidence"
                        )
                        if selected_evidence:
                            evidence_id = selected_evidence.evidence_id
                    else:
                        st.info("No admitted opponent evidence to exclude")

                elif selected_type == SidebarRequestType.REQUEST_ADJOURNMENT:
                    # Adjournment options
                    adj_reason = st.selectbox(
                        "Reason for adjournment:",
                        options=list(AdjournmentReason),
                        format_func=lambda x: x.value.replace("_", " ").title(),
                        key="adj_reason"
                    )
                    adjournment_reason = adj_reason

                    adj_duration = st.selectbox(
                        "Duration requested:",
                        options=list(ADJOURNMENT_DURATIONS.keys()),
                        format_func=lambda x: ADJOURNMENT_DURATIONS[x][0],
                        key="adj_duration"
                    )
                    adjournment_duration = adj_duration

                elif selected_type == SidebarRequestType.WITNESS_AVAILABILITY:
                    # Witness selection
                    if game.state.current_witness:
                        st.info(f"Current witness: {game.state.current_witness.name}")

                # Supporting argument
                supporting_argument = st.text_area(
                    "Supporting argument (optional):",
                    placeholder="Provide additional arguments to support your request...",
                    height=80,
                    key="sidebar_argument"
                )

                # Submit button
                if st.button("⚖️ Request Sidebar", use_container_width=True, type="primary"):
                    if not reason:
                        st.error("Please provide a reason for your request")
                    else:
                        result = game.request_sidebar(
                            request_type=selected_type,
                            reason=reason,
                            argument=supporting_argument,
                            evidence_id=evidence_id,
                            witness_id=witness_id,
                            adjournment_reason=adjournment_reason,
                            adjournment_duration=adjournment_duration
                        )

                        if result.get("success"):
                            safe_extend_messages(result.get("messages", []))

                            outcome = result.get("outcome", "")
                            if result.get("granted"):
                                st.toast(f"✅ Sidebar GRANTED: {result.get('judge_remarks', '')[:50]}...", icon="⚖️")
                            else:
                                st.toast(f"❌ Sidebar DENIED: {result.get('judge_remarks', '')[:50]}...", icon="⚠️")

                            # Show specific outcomes
                            if result.get("evidence_excluded"):
                                st.toast("🚫 Evidence has been excluded!", icon="📋")
                            if result.get("adjournment_granted"):
                                st.toast(f"⏸️ Adjournment granted: {result.get('adjournment_duration')}", icon="⏰")
                            if result.get("settlement_discussion"):
                                st.toast("🤝 Settlement discussion opened", icon="💼")
                        else:
                            st.error(result.get("error", "Request failed"))

                        st.rerun()

        st.divider()

        # History and stats
        st.write("**📊 Sidebar History:**")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total", sidebar_info.get("total_sidebars", 0))
        with col2:
            st.metric("Adjournments", sidebar_info.get("adjournments_granted", 0))
        with col3:
            st.metric("Exclusions", sidebar_info.get("evidence_exclusions", 0))

        # Settlement status
        if sidebar_info.get("settlement_reached"):
            st.success("🎉 Settlement reached!")
        elif sidebar_info.get("settlement_offers", 0) > 0:
            st.info(f"🤝 {sidebar_info['settlement_offers']} settlement offer(s) made")

        # Tips
        tips = game.get_sidebar_tips()
        if tips:
            st.divider()
            st.caption("**💡 Tips:**")
            for tip in tips[:3]:
                st.caption(tip)


def render_learning_moment_popup():
    """Render a learning moment flashcard popup when a mistake is detected."""
    game: CourtroomGame = st.session_state.game

    if not game.state.education_enabled:
        return

    # Check if there's a pending learning moment
    learning_moment_display = game.get_learning_moment_display()
    if not learning_moment_display:
        return

    # Create a modal-like experience with a prominent container
    st.markdown("""
    <style>
    .learning-moment-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border: 2px solid #e94560;
        border-radius: 15px;
        padding: 1.5rem;
        margin: 1rem 0;
        box-shadow: 0 8px 32px rgba(233, 69, 96, 0.3);
    }
    .learning-moment-header {
        color: #e94560;
        font-size: 1.3rem;
        font-weight: bold;
        margin-bottom: 0.5rem;
    }
    .wrong-example {
        background: rgba(255, 0, 0, 0.1);
        border-left: 4px solid #ff4444;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .correct-example {
        background: rgba(0, 255, 0, 0.1);
        border-left: 4px solid #44ff44;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .legal-section-badge {
        background: #0f3460;
        color: #fff;
        padding: 0.25rem 0.75rem;
        border-radius: 15px;
        font-size: 0.85rem;
        display: inline-block;
        margin: 0.5rem 0;
    }
    .tip-box {
        background: rgba(255, 193, 7, 0.1);
        border-left: 4px solid #ffc107;
        padding: 0.5rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown("---")
        st.markdown("### 📚 Learning Moment")

        # Color-coded severity indicator
        severity_color = learning_moment_display.get("severity_color", "orange")
        category = learning_moment_display.get("category", "Legal Principle")
        level_badge = learning_moment_display.get("level_badge", "")

        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            st.markdown(f"**{learning_moment_display.get('title', 'Learning Moment')}**")
        with col2:
            st.markdown(f"<span class='legal-section-badge'>{level_badge}</span>",
                       unsafe_allow_html=True)
        with col3:
            st.markdown(f"📑 *{learning_moment_display.get('legal_section', '')}*")

        # What you said
        if learning_moment_display.get("player_action"):
            st.markdown(f"**Your action:** *\"{learning_moment_display['player_action'][:100]}...\"*"
                       if len(learning_moment_display['player_action']) > 100
                       else f"**Your action:** *\"{learning_moment_display['player_action']}\"*")

        st.markdown(f"**Context:** {learning_moment_display.get('context', 'General')}")

        # Explanation
        st.markdown("---")
        st.markdown("#### 📖 Legal Principle")
        st.write(learning_moment_display.get("explanation", ""))

        # Short rule in a highlighted box
        st.info(f"**Rule:** {learning_moment_display.get('short_rule', '')}")

        # Examples section
        col_wrong, col_correct = st.columns(2)

        with col_wrong:
            st.markdown("#### ❌ Incorrect Example")
            st.markdown(f"""
            <div class="wrong-example">
            {learning_moment_display.get('example_wrong', '')}
            </div>
            """, unsafe_allow_html=True)

        with col_correct:
            st.markdown("#### ✅ Correct Example")
            st.markdown(f"""
            <div class="correct-example">
            {learning_moment_display.get('example_correct', '')}
            </div>
            """, unsafe_allow_html=True)

        # Tip
        st.markdown(f"""
        <div class="tip-box">
        💡 <strong>Tip:</strong> {learning_moment_display.get('tip', '')}
        </div>
        """, unsafe_allow_html=True)

        # Related principles (if any)
        related = learning_moment_display.get("related_principles", [])
        if related:
            st.caption(f"**Related concepts:** {', '.join(related)}")

        st.markdown("---")

        # Acknowledge button
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            if st.button("✅ I Understand - Continue", use_container_width=True, type="primary"):
                game.acknowledge_learning_moment()
                st.toast("Keep practicing! You'll master these principles.", icon="📚")
                st.rerun()


def render_education_panel():
    """Render the education progress panel in the sidebar or quick reference."""
    game: CourtroomGame = st.session_state.game

    if not game.state.education_enabled:
        return

    edu_display = game.get_education_display()
    if not edu_display.get("active"):
        return

    with st.expander("📚 Learning Progress", expanded=False):
        st.subheader("📊 Your Progress")

        progress = edu_display.get("progress", {})

        # Progress bars
        learning_pct = progress.get("learning_percentage", 0)
        mastery_pct = progress.get("mastery_percentage", 0)

        st.write("**Principles Learned:**")
        st.progress(learning_pct / 100)
        st.caption(f"{progress.get('principles_learned', 0)} / {progress.get('total_principles', 0)} "
                  f"({learning_pct:.0f}%)")

        st.write("**Principles Mastered:**")
        st.progress(mastery_pct / 100)
        st.caption(f"{progress.get('principles_mastered', 0)} / {progress.get('total_principles', 0)} "
                  f"({mastery_pct:.0f}%)")

        st.divider()

        # Stats
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Flashcards Viewed", progress.get("flashcards_viewed", 0))
            st.metric("Learning Streak", f"{progress.get('learning_streak', 0)} 🔥")
        with col2:
            st.metric("Correct After Learning", progress.get("correct_after_learning", 0))
            remaining = edu_display.get("flashcards_remaining", 0)
            st.metric("Flashcards Remaining", f"{remaining} / {edu_display.get('flashcards_limit', 10)}")

        # Top mistakes
        top_mistakes = edu_display.get("top_mistakes", [])
        if top_mistakes:
            st.divider()
            st.write("**🎯 Areas to Improve:**")
            for mistake, count in top_mistakes:
                category_name = mistake.replace("_", " ").title()
                st.caption(f"• {category_name}: {count} occurrence(s)")

        # Toggle flashcards
        st.divider()
        flashcards_on = edu_display.get("show_flashcards", True)
        new_setting = st.checkbox(
            "Show learning moments when mistakes are detected",
            value=flashcards_on,
            key="edu_flashcard_toggle"
        )
        if new_setting != flashcards_on:
            game.toggle_education_flashcards(new_setting)
            st.rerun()

        # Tips
        tips = game.get_education_tips()
        if tips:
            st.divider()
            st.caption("**💡 Tips:**")
            for tip in tips[:3]:
                st.caption(tip)


def render_legal_principles_reference():
    """Render a reference panel for all legal principles."""
    game: CourtroomGame = st.session_state.game

    with st.expander("📖 Legal Principles Reference", expanded=False):
        st.subheader("Legal Principles Library")
        st.caption("Reference guide for court procedure and evidence rules")

        # Get all principles organized by category
        categorized = game.get_all_principles_by_category()

        # Create tabs for categories
        if categorized:
            category_names = list(categorized.keys())
            tabs = st.tabs([cat.replace("_", " ").title() for cat in category_names])

            for tab, category in zip(tabs, category_names):
                with tab:
                    principles = categorized[category]
                    for p in principles:
                        level_emoji = {
                            "basic": "🟢",
                            "intermediate": "🟡",
                            "advanced": "🔴"
                        }.get(p["level"], "⚪")

                        with st.container():
                            st.markdown(f"**{level_emoji} {p['title']}**")
                            st.caption(f"*{p['short_rule']}*")

                            # Show full details on click
                            if st.button(f"📖 Details", key=f"principle_{p['principle_id']}"):
                                info = game.get_principle_info(p["principle_id"])
                                if info:
                                    st.info(f"**{info['title']}**\n\n"
                                           f"📑 {info['legal_section']}\n\n"
                                           f"{info['explanation']}\n\n"
                                           f"❌ Wrong: *{info['example_wrong']}*\n\n"
                                           f"✅ Correct: *{info['example_correct']}*\n\n"
                                           f"💡 Tip: {info['tip']}")

                        st.markdown("---")


def render_game_over():
    """Render game over screen with comprehensive post-game analysis."""
    game: CourtroomGame = st.session_state.game
    summary = game.get_game_summary()

    # Custom CSS for analysis report
    st.markdown("""
    <style>
    .analysis-card {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        border-radius: 15px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        border: 1px solid #0f3460;
    }
    .strength-item {
        background: rgba(76, 175, 80, 0.1);
        border-left: 4px solid #4CAF50;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .weakness-item {
        background: rgba(244, 67, 54, 0.1);
        border-left: 4px solid #f44336;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .turning-point-positive {
        background: rgba(33, 150, 243, 0.1);
        border-left: 4px solid #2196F3;
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
        border-radius: 0 8px 8px 0;
    }
    .turning-point-negative {
        background: rgba(255, 152, 0, 0.1);
        border-left: 4px solid #FF9800;
        padding: 0.5rem 1rem;
        margin: 0.25rem 0;
        border-radius: 0 8px 8px 0;
    }
    .recommendation-card {
        background: rgba(156, 39, 176, 0.1);
        border-left: 4px solid #9C27B0;
        padding: 0.75rem 1rem;
        margin: 0.5rem 0;
        border-radius: 0 8px 8px 0;
    }
    .grade-display {
        font-size: 4rem;
        font-weight: bold;
        text-align: center;
        padding: 1rem;
    }
    .grade-A { color: #4CAF50; }
    .grade-B { color: #8BC34A; }
    .grade-C { color: #FFC107; }
    .grade-D { color: #FF9800; }
    .grade-F { color: #f44336; }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div class="phase-banner" style="background: linear-gradient(90deg, #4CAF50 0%, #2E7D32 100%);">
        🏆 JUDGMENT DELIVERED - GAME COMPLETE
    </div>
    """, unsafe_allow_html=True)

    # Get analysis data
    analysis_display = game.get_analysis_display()

    # Create tabs for different sections
    tab_score, tab_analysis, tab_turning, tab_improve = st.tabs([
        "📊 Score Summary",
        "📋 Case Analysis",
        "⚡ Key Moments",
        "🎯 Improvement"
    ])

    with tab_score:
        # Overall grade display
        if analysis_display.get("available"):
            grade = analysis_display["overall_grade"]
            grade_class = f"grade-{grade}"

            col_grade, col_summary = st.columns([1, 3])

            with col_grade:
                st.markdown(f"""
                <div class="grade-display {grade_class}">
                    {grade}
                </div>
                """, unsafe_allow_html=True)
                st.caption("Overall Grade")

            with col_summary:
                st.markdown(f"**{analysis_display['overall_summary']}**")

                # Score comparison
                stats = analysis_display.get("statistics", {})
                if stats.get("optimal_score"):
                    score_pct = stats.get("score_percentage", 0)
                    st.progress(min(1.0, score_pct / 100))
                    st.caption(f"Score: {stats['actual_score']} / {stats['optimal_score']} estimated optimal ({score_pct:.0f}%)")

        st.divider()

        # Standard score display
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

        # Category scores from analysis
        if analysis_display.get("available") and analysis_display.get("category_scores"):
            st.divider()
            st.subheader("📊 Detailed Category Analysis")

            category_scores = analysis_display["category_scores"]
            for category, score in sorted(category_scores.items(), key=lambda x: x[1], reverse=True):
                cat_name = category.replace("_", " ").title()
                col_name, col_bar = st.columns([1, 3])
                with col_name:
                    st.write(f"**{cat_name}**")
                with col_bar:
                    # Color based on score
                    if score >= 70:
                        color = "green"
                    elif score >= 50:
                        color = "orange"
                    else:
                        color = "red"
                    st.progress(score / 100)
                    st.caption(f"{score}/100")

    with tab_analysis:
        if not analysis_display.get("available"):
            st.info("Analysis data not available for this game session.")
        else:
            # Strengths section
            st.subheader("✅ Strengths")
            strengths = analysis_display.get("strengths", [])
            if strengths:
                for strength in strengths:
                    st.markdown(f"""
                    <div class="strength-item">
                        <strong>✓ {strength['title']}</strong><br>
                        {strength['description']}
                    </div>
                    """, unsafe_allow_html=True)
                    if strength.get("examples"):
                        with st.expander("View examples"):
                            for ex in strength["examples"]:
                                st.write(f"• {ex}")
            else:
                st.info("No significant strengths identified. Keep practicing!")

            st.divider()

            # Weaknesses section
            st.subheader("❌ Areas to Improve")
            weaknesses = analysis_display.get("weaknesses", [])
            if weaknesses:
                for weakness in weaknesses:
                    st.markdown(f"""
                    <div class="weakness-item">
                        <strong>✗ {weakness['title']}</strong><br>
                        {weakness['description']}
                    </div>
                    """, unsafe_allow_html=True)
                    if weakness.get("tip"):
                        st.caption(f"💡 **Tip:** {weakness['tip']}")
                    if weakness.get("examples"):
                        with st.expander("View examples"):
                            for ex in weakness["examples"]:
                                st.write(f"• {ex}")
            else:
                st.success("No significant weaknesses found. Great job!")

    with tab_turning:
        if not analysis_display.get("available"):
            st.info("Turning point data not available.")
        else:
            st.subheader("⚡ Key Turning Points")
            st.caption("Moments that significantly impacted your case")

            turning_points = analysis_display.get("turning_points", [])

            if turning_points:
                # Sort by turn number
                sorted_tps = sorted(turning_points, key=lambda x: x["turn"])

                for tp in sorted_tps:
                    css_class = "turning-point-positive" if tp["is_positive"] else "turning-point-negative"
                    icon = "📈" if tp["is_positive"] else "📉"
                    impact_icon = "+" if tp["impact_score"] > 0 else ""

                    st.markdown(f"""
                    <div class="{css_class}">
                        <strong>{icon} Turn {tp['turn']}: {tp['description']}</strong><br>
                        <em>Impact: {tp['impact']}</em><br>
                        <small>Score effect: {impact_icon}{tp['impact_score']}</small>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No major turning points recorded in this trial.")

            # Missed opportunities
            st.divider()
            st.subheader("💭 Missed Opportunities")

            missed = analysis_display.get("missed_opportunities", [])
            if missed:
                for mo in missed:
                    with st.expander(f"Turn {mo['turn']}: {mo['description'][:50]}..."):
                        st.write(f"**What happened:** {mo['description']}")
                        st.write(f"**What you could have done:** {mo['suggestion']}")
                        st.write(f"**Potential impact:** {mo['impact']}")
            else:
                st.success("No significant missed opportunities identified!")

    with tab_improve:
        if not analysis_display.get("available"):
            st.info("Recommendations not available.")
        else:
            st.subheader("🎯 AI Recommendations for Improvement")

            recommendations = analysis_display.get("recommendations", [])

            if recommendations:
                for i, rec in enumerate(recommendations, 1):
                    priority_stars = "⭐" * min(5, 6 - rec["priority"])

                    st.markdown(f"""
                    <div class="recommendation-card">
                        <strong>{priority_stars} {rec['title']}</strong><br>
                        <em>{rec['recommendation']}</em><br>
                        <small>Rationale: {rec['rationale']}</small>
                    </div>
                    """, unsafe_allow_html=True)

                    cat_name = rec["category"].replace("_", " ").title()
                    st.caption(f"Category: {cat_name}")
            else:
                st.success("No specific recommendations - you performed well!")

            # Summary statistics
            st.divider()
            st.subheader("📊 Action Effectiveness")

            stats = analysis_display.get("statistics", {})
            if stats:
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Effective Actions", stats.get("effective_actions", 0), delta=None)
                with col2:
                    st.metric("Neutral Actions", stats.get("neutral_actions", 0), delta=None)
                with col3:
                    st.metric("Ineffective Actions", stats.get("ineffective_actions", 0), delta=None)

                # Effectiveness ratio
                total_actions = (stats.get("effective_actions", 0) +
                                stats.get("neutral_actions", 0) +
                                stats.get("ineffective_actions", 0))
                if total_actions > 0:
                    effectiveness_ratio = stats.get("effective_actions", 0) / total_actions
                    st.progress(effectiveness_ratio)
                    st.caption(f"Action effectiveness: {effectiveness_ratio * 100:.0f}%")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🔄 Play Again", use_container_width=True, type="primary"):
            st.session_state.game_started = False
            st.session_state.game = None
            st.session_state.game_messages = []
            st.session_state.pending_learning_moment = False
            st.rerun()
    with col2:
        if st.button("📥 Download Report", use_container_width=True):
            # Create downloadable report
            report_text = generate_analysis_report(game, summary, analysis_display)
            st.download_button(
                label="📄 Download Full Report",
                data=report_text,
                file_name="courtroom_analysis_report.txt",
                mime="text/plain",
                use_container_width=True
            )


def generate_analysis_report(game, summary, analysis_display) -> str:
    """Generate a text report of the game analysis."""
    lines = []
    lines.append("=" * 60)
    lines.append("COURTROOM ADVOCATE - POST-GAME ANALYSIS REPORT")
    lines.append("=" * 60)
    lines.append("")

    # Case info
    lines.append(f"Case: {summary.get('case_title', 'Unknown')}")
    lines.append(f"Player Side: {summary.get('player_side', 'Unknown')}")
    lines.append(f"Total Turns: {summary.get('total_turns', 0)}")
    lines.append("")

    # Grade
    if analysis_display.get("available"):
        lines.append(f"OVERALL GRADE: {analysis_display['overall_grade']}")
        lines.append(f"Summary: {analysis_display['overall_summary']}")
        lines.append("")

    # Score
    lines.append("-" * 40)
    lines.append("FINAL SCORE")
    lines.append("-" * 40)
    score = summary.get("score", {})
    lines.append(f"Total Points: {score.get('total_points', 0)}")
    lines.append(f"Judge's Favor: {score.get('judge_favor', 0):.0f}%")
    lines.append(f"Overall Performance: {score.get('weighted_score', 0):.1f}%")
    lines.append("")

    # Strengths
    if analysis_display.get("strengths"):
        lines.append("-" * 40)
        lines.append("STRENGTHS")
        lines.append("-" * 40)
        for s in analysis_display["strengths"]:
            lines.append(f"✓ {s['title']}")
            lines.append(f"  {s['description']}")
        lines.append("")

    # Weaknesses
    if analysis_display.get("weaknesses"):
        lines.append("-" * 40)
        lines.append("AREAS TO IMPROVE")
        lines.append("-" * 40)
        for w in analysis_display["weaknesses"]:
            lines.append(f"✗ {w['title']}")
            lines.append(f"  {w['description']}")
            if w.get("tip"):
                lines.append(f"  Tip: {w['tip']}")
        lines.append("")

    # Turning Points
    if analysis_display.get("turning_points"):
        lines.append("-" * 40)
        lines.append("KEY TURNING POINTS")
        lines.append("-" * 40)
        for tp in analysis_display["turning_points"]:
            symbol = "+" if tp["is_positive"] else "-"
            lines.append(f"Turn {tp['turn']}: {tp['description']}")
            lines.append(f"  Impact: {tp['impact']} ({symbol}{abs(tp['impact_score'])})")
        lines.append("")

    # Recommendations
    if analysis_display.get("recommendations"):
        lines.append("-" * 40)
        lines.append("RECOMMENDATIONS")
        lines.append("-" * 40)
        for r in analysis_display["recommendations"]:
            lines.append(f"{r['priority']}. {r['title']}")
            lines.append(f"   {r['recommendation']}")
        lines.append("")

    lines.append("=" * 60)
    lines.append("Report generated by Courtroom Advocate")
    lines.append("=" * 60)

    return "\n".join(lines)


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


def render_step_indicator():
    """Render the current step indicator."""
    step = st.session_state.game_step
    steps = [
        ("1️⃣", "Upload", step == 'upload'),
        ("2️⃣", "Side", step == 'select_side'),
        ("3️⃣", "Prepare", step == 'preparation'),
        ("4️⃣", "Play", step == 'playing')
    ]

    cols = st.columns(4)
    for i, (icon, label, active) in enumerate(steps):
        with cols[i]:
            if active:
                st.markdown(f"""
                <div style="text-align: center; padding: 0.5rem;
                            background: linear-gradient(135deg, #e94560, #0f3460);
                            border-radius: 10px; color: white;">
                    <strong>{icon} {label}</strong>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="text-align: center; padding: 0.5rem;
                            background: #333; border-radius: 10px; color: #888;">
                    {icon} {label}
                </div>
                """, unsafe_allow_html=True)


def render_upload_step(config):
    """Step 1: Upload PDF and auto-extract text."""
    st.markdown("""
    <div class="phase-banner">
        📄 STEP 1: Upload Your Court Case
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    col1, col2 = st.columns([2, 1])

    with col1:
        uploaded_file = st.file_uploader(
            "Upload Court Case PDF",
            type="pdf",
            help="Upload any court case judgment - MACT, Civil, Criminal, Appeals, etc."
        )

        if uploaded_file:
            # Auto-extract text when file is uploaded
            if st.session_state.uploaded_file_name != uploaded_file.name:
                with st.spinner("📖 Reading document..."):
                    uploaded_file.seek(0)
                    text = extract_pdf_text(uploaded_file)
                    st.session_state.extracted_text = text
                    st.session_state.uploaded_file_name = uploaded_file.name
                st.success(f"✅ Loaded: **{uploaded_file.name}**")
            else:
                st.success(f"✅ Loaded: **{uploaded_file.name}**")

            # Show preview
            with st.expander("📜 Preview Document", expanded=False):
                st.text_area("", st.session_state.extracted_text[:2000] + "...", height=200, disabled=True)

            st.write("")
            if st.button("▶️ Continue to Side Selection", use_container_width=True, type="primary"):
                st.session_state.game_step = 'select_side'
                st.rerun()

    with col2:
        st.info("""
        **Supported Cases:**
        - Motor Accident Claims (MACT)
        - Civil Suits
        - Criminal Cases
        - Writ Petitions
        - Appeals
        - Any court judgment PDF
        """)

        st.divider()

        st.write("**No PDF? Try a sample:**")
        if st.button("📥 Load Sample Case", use_container_width=True):
            st.session_state.case_data = create_sample_case()
            st.session_state.extracted_text = "Sample case loaded"
            st.session_state.uploaded_file_name = "sample_case.pdf"
            st.session_state.game_step = 'select_side'
            st.rerun()


def render_side_selection_step(config):
    """Step 2: Select which side to represent and start game."""
    st.markdown("""
    <div class="phase-banner">
        ⚖️ STEP 2: Choose Your Side
    </div>
    """, unsafe_allow_html=True)

    st.write("")

    # Show case info if we have extracted data
    if st.session_state.case_data:
        case = st.session_state.case_data
        st.subheader(f"📋 {case.case_metadata.case_title}")
        st.write(f"**Case Type:** {case.case_metadata.case_type.value}")
    else:
        st.info("📄 Case data will be extracted when you start the game.")

    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #4CAF50 0%, #2E7D32 100%);
                    padding: 1.5rem; border-radius: 15px; color: white; min-height: 200px;">
            <h3>👨‍💼 Appellant / Petitioner</h3>
            <p><strong>You are fighting FOR the claim</strong></p>
            <ul>
                <li>Prove your case with evidence</li>
                <li>Examine your witnesses</li>
                <li>Cross-examine opponent's witnesses</li>
                <li>Argue for maximum relief</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("⚔️ Play as Appellant/Petitioner", use_container_width=True, type="primary"):
            start_preparation_phase(PlayerSide.PETITIONER, config)

    with col2:
        st.markdown("""
        <div style="background: linear-gradient(135deg, #f44336 0%, #c62828 100%);
                    padding: 1.5rem; border-radius: 15px; color: white; min-height: 200px;">
            <h3>👩‍💼 Respondent</h3>
            <p><strong>You are DEFENDING against the claim</strong></p>
            <ul>
                <li>Challenge opponent's evidence</li>
                <li>Present counter-arguments</li>
                <li>Cross-examine their witnesses</li>
                <li>Minimize liability/damages</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        st.write("")
        if st.button("🛡️ Play as Respondent", use_container_width=True, type="primary"):
            start_preparation_phase(PlayerSide.RESPONDENT, config)

    st.divider()

    # Back button
    if st.button("⬅️ Back to Upload", use_container_width=False):
        st.session_state.game_step = 'upload'
        st.rerun()


def start_preparation_phase(side: PlayerSide, config):
    """Initialize preparation phase before starting the game."""
    # Extract case data if not already done
    if not st.session_state.case_data:
        with st.spinner("🤖 AI is analyzing the case..."):
            try:
                extractor = CourtCaseExtractor(
                    provider=config["provider"],
                    model_name=config["model"]
                )
                case = extractor.extract_full_case(st.session_state.extracted_text)
                st.session_state.case_data = case
            except Exception as e:
                st.error(f"Error extracting case data: {str(e)}")
                st.info("Loading sample case instead...")
                st.session_state.case_data = create_sample_case()

    # Initialize the game object (but don't start the trial yet)
    case = st.session_state.case_data
    game = CourtroomGame(
        case=case,
        llm_provider=config["provider"],
        model_name=config["model"],
        difficulty=config["difficulty"]
    )

    # Initialize preparation phase
    game.initialize_preparation(side)

    st.session_state.game = game
    st.session_state.player_side = side
    st.session_state.preparation_initialized = True
    st.session_state.game_step = 'preparation'
    st.rerun()


def render_preparation_step(config):
    """Step 3: Pre-trial preparation phase."""
    st.markdown("""
    <div class="phase-banner">
        📋 STEP 3: Case Preparation
    </div>
    """, unsafe_allow_html=True)

    game: CourtroomGame = st.session_state.game
    prep_state = game.get_preparation_state()

    if not prep_state:
        st.error("Preparation not initialized")
        return

    st.write("")

    # Header with time remaining
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.subheader("⚖️ Prepare Your Case")
        st.caption("Better preparation leads to higher starting scores!")
    with col2:
        st.metric("⏱️ Time Left", f"{prep_state.remaining_points} pts")
    with col3:
        grade_colors = {"A": "🟢", "B": "🔵", "C": "🟡", "D": "🟠", "F": "🔴"}
        grade_icon = grade_colors.get(prep_state.preparation_grade, "⚪")
        st.metric("📊 Grade", f"{grade_icon} {prep_state.preparation_grade}")

    st.divider()

    # Main content area
    col_tasks, col_info = st.columns([2, 1])

    with col_tasks:
        st.subheader("📝 Preparation Tasks")

        # Get tasks by category
        tasks_by_cat = game.get_prep_tasks_by_category()
        available_tasks = game.get_available_prep_tasks()
        available_ids = [t.task_id for t in available_tasks]

        for category in PreparationCategory:
            if category not in tasks_by_cat:
                continue

            tasks = tasks_by_cat[category]
            completed_count = sum(1 for t in tasks if t.is_completed)

            # Category header
            cat_icons = {
                PreparationCategory.CASE_REVIEW: "📄",
                PreparationCategory.WITNESS_PREP: "🧑",
                PreparationCategory.LEGAL_RESEARCH: "📚",
                PreparationCategory.EVIDENCE_ANALYSIS: "🔍",
                PreparationCategory.STRATEGY: "🎯",
                PreparationCategory.OPENING_STATEMENT: "📢"
            }
            cat_icon = cat_icons.get(category, "📋")
            cat_name = category.value.replace("_", " ").title()

            with st.expander(f"{cat_icon} {cat_name} ({completed_count}/{len(tasks)})", expanded=completed_count < len(tasks)):
                for task in tasks:
                    if task.is_completed:
                        st.markdown(f"✅ ~~{task.title}~~ (+{task.score_bonus:.0f} pts)")
                    elif task.task_id in available_ids:
                        col_t, col_b = st.columns([3, 1])
                        with col_t:
                            st.markdown(f"**{task.title}** ({task.time_cost} pts)")
                            st.caption(task.description)
                        with col_b:
                            if st.button("Do Task", key=f"prep_{task.task_id}", use_container_width=True):
                                result = game.complete_prep_task(task.task_id)
                                if result["success"]:
                                    st.toast(f"✅ {task.title} completed! +{result['bonus_gained']:.0f} pts", icon="📋")
                                    if result.get("insight"):
                                        st.toast(f"💡 {result['insight']}", icon="🔍")
                                    st.rerun()
                                else:
                                    st.error(result.get("error", "Could not complete task"))
                    else:
                        # Locked task
                        st.markdown(f"🔒 {task.title}")
                        if task.requires_task:
                            req_task = next((t for t in prep_state.tasks if t.task_id == task.requires_task), None)
                            if req_task:
                                st.caption(f"Requires: {req_task.title}")

    with col_info:
        # Preparation summary
        st.subheader("📊 Summary")

        # Progress
        total_tasks = len(prep_state.tasks)
        completed_tasks = len(prep_state.completed_tasks)
        progress = completed_tasks / total_tasks if total_tasks > 0 else 0
        st.progress(progress, text=f"{completed_tasks}/{total_tasks} tasks")

        # Bonuses earned
        st.write("**Bonuses Earned:**")
        st.write(f"• Total: +{prep_state.total_score_bonus:.0f} pts")
        for skill, bonus in prep_state.skill_bonuses.items():
            skill_name = skill.replace("_", " ").title()
            st.write(f"• {skill_name}: +{bonus:.0f}")

        st.divider()

        # Insights gained
        if prep_state.case_insights:
            st.write("**💡 Insights:**")
            for insight in prep_state.case_insights[-3:]:  # Show last 3
                st.caption(f"• {insight}")

        st.divider()

        # Tips
        st.write("**💡 Tips:**")
        tips = game.get_preparation_tips()
        for tip in tips[:3]:
            st.write(f"• {tip}")

    st.divider()

    # Action buttons
    col1, col2, col3 = st.columns([1, 1, 1])

    with col1:
        if st.button("⬅️ Back", use_container_width=True):
            st.session_state.game_step = 'select_side'
            st.session_state.game = None
            st.session_state.preparation_initialized = False
            st.rerun()

    with col2:
        if st.button("⏭️ Skip Preparation", use_container_width=True):
            game.skip_preparation()
            start_game_after_prep(config)

    with col3:
        if st.button("▶️ Start Trial", use_container_width=True, type="primary"):
            result = game.finish_preparation()
            st.toast(f"📋 Preparation Grade: {result['grade']} | +{result['total_bonus']:.0f} pts bonus!", icon="⚖️")
            start_game_after_prep(config)


def start_game_after_prep(config):
    """Start the actual game after preparation is complete."""
    game: CourtroomGame = st.session_state.game
    side = st.session_state.player_side

    # Apply pressure system setting
    pressure_enabled = config.get("pressure_enabled", True)
    game.state.pressure_enabled = pressure_enabled

    # Initialize education system
    game.initialize_education_system()

    # Initialize analysis system for post-game report
    game.initialize_analysis_system()

    # Start the game (this will apply preparation bonuses)
    initial_messages = game.start_game(side)

    # Start the timer for first action if pressure is enabled
    if pressure_enabled:
        game.start_action_timer()

    st.session_state.game_messages = initial_messages
    st.session_state.game_started = True
    st.session_state.game_step = 'playing'
    st.rerun()


def start_streamlined_game(side: PlayerSide, config):
    """Extract case data (if needed) and start the game."""
    # Extract case data if not already done
    if not st.session_state.case_data:
        with st.spinner("🤖 AI is analyzing the case... This may take a moment."):
            try:
                extractor = CourtCaseExtractor(
                    provider=config["provider"],
                    model_name=config["model"]
                )
                case = extractor.extract_full_case(st.session_state.extracted_text)
                st.session_state.case_data = case
            except Exception as e:
                st.error(f"Error extracting case data: {str(e)}")
                st.info("Loading sample case instead...")
                st.session_state.case_data = create_sample_case()

    case = st.session_state.case_data

    # Initialize the game
    game = CourtroomGame(
        case=case,
        llm_provider=config["provider"],
        model_name=config["model"],
        difficulty=config["difficulty"]
    )

    # Initialize education system
    game.initialize_education_system()

    # Initialize analysis system for post-game report
    game.initialize_analysis_system()

    # Start the game with selected side
    initial_messages = game.start_game(side)

    st.session_state.game = game
    st.session_state.game_messages = initial_messages
    st.session_state.game_started = True
    st.session_state.player_side = side
    st.session_state.game_step = 'playing'
    st.rerun()


def main():
    """Main application entry point."""
    init_session_state()
    render_header()
    config = render_sidebar()

    # Step indicator
    render_step_indicator()
    st.write("")

    # Route based on current step
    if st.session_state.game_step == 'upload':
        render_upload_step(config)

    elif st.session_state.game_step == 'select_side':
        render_side_selection_step(config)

    elif st.session_state.game_step == 'preparation':
        render_preparation_step(config)

    elif st.session_state.game_step == 'playing':
        render_game_play(config)

        # Reset button in sidebar
        with st.sidebar:
            st.divider()
            if st.button("🔄 Start New Game", use_container_width=True):
                # Reset game state
                st.session_state.game = None
                st.session_state.game_started = False
                st.session_state.game_messages = []
                st.session_state.case_data = None
                st.session_state.extracted_text = None
                st.session_state.uploaded_file_name = None
                st.session_state.game_step = 'upload'
                st.rerun()


if __name__ == "__main__":
    main()
