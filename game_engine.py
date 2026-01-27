"""
Courtroom Simulation Game Engine
Interactive legal game where player acts as an advocate
"""

import random
from enum import Enum
from typing import Optional, List, Dict, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from schemas import CourtCase, OralWitness, WitnessType, IssueFramed
from agents import (
    JudgeAgent, LawyerAgent, WitnessAgent, CourtClerkAgent,
    AgentMessage, AgentRole, CourtPhase, create_agents_from_case
)


class PlayerSide(str, Enum):
    PETITIONER = "petitioner"
    RESPONDENT = "respondent"


class GamePhase(str, Enum):
    SETUP = "Setup"
    OPENING_STATEMENT = "Opening Statement"
    PETITIONER_EVIDENCE = "Petitioner Evidence"
    PETITIONER_WITNESS_EXAM = "Petitioner Witness Examination"
    CROSS_EXAMINATION = "Cross Examination"
    RESPONDENT_EVIDENCE = "Respondent Evidence"
    RESPONDENT_WITNESS_EXAM = "Respondent Witness Examination"
    REBUTTAL = "Rebuttal"
    FINAL_ARGUMENTS = "Final Arguments"
    JUDGMENT = "Judgment"
    GAME_OVER = "Game Over"


class ActionType(str, Enum):
    ASK_QUESTION = "ask_question"
    MAKE_ARGUMENT = "make_argument"
    RAISE_OBJECTION = "raise_objection"
    PRESENT_EVIDENCE = "present_evidence"
    REQUEST_ADJOURNMENT = "request_adjournment"
    CITE_CASE_LAW = "cite_case_law"
    CROSS_EXAMINE = "cross_examine"
    NO_QUESTIONS = "no_questions"
    REST_CASE = "rest_case"  # Conclude submissions for current phase
    # Evidence handling actions
    MARK_FOR_IDENTIFICATION = "mark_for_identification"
    MOVE_TO_ADMIT = "move_to_admit"
    OBJECT_TO_EVIDENCE = "object_to_evidence"
    CHALLENGE_AUTHENTICITY = "challenge_authenticity"


class ObjectionType(str, Enum):
    LEADING = "Leading question"
    HEARSAY = "Hearsay"
    RELEVANCE = "Irrelevant"
    SPECULATION = "Calls for speculation"
    ARGUMENTATIVE = "Argumentative"
    COMPOUND = "Compound question"
    BADGERING = "Badgering the witness"
    ASSUMES_FACTS = "Assumes facts not in evidence"


# ============================================================================
# EVIDENCE MANAGEMENT SYSTEM
# ============================================================================

class EvidenceCategory(str, Enum):
    """Categories of evidence in court."""
    DOCUMENTARY = "Documentary Evidence"
    MEDICAL_RECORDS = "Medical Records"
    PHOTOGRAPHS = "Photographs/Videos"
    EXPERT_REPORTS = "Expert Reports"
    WITNESS_STATEMENTS = "Witness Statements"
    PHYSICAL = "Physical Evidence"
    ELECTRONIC = "Electronic Evidence"
    OFFICIAL_RECORDS = "Official Records"


class EvidenceStatus(str, Enum):
    """Status of evidence in the trial."""
    NOT_INTRODUCED = "Not Introduced"  # In locker, not yet shown
    MARKED_FOR_ID = "Marked for Identification"  # Marked as exhibit for ID
    OFFERED = "Offered for Admission"  # Moved to admit
    OBJECTED = "Objection Pending"  # Opponent objected, awaiting ruling
    ADMITTED = "Admitted"  # Judge admitted into evidence
    EXCLUDED = "Excluded"  # Judge excluded/rejected
    WITHDRAWN = "Withdrawn"  # Party withdrew the evidence


class EvidenceObjectionType(str, Enum):
    """Types of objections to evidence admission."""
    HEARSAY = "Hearsay"
    IRRELEVANT = "Irrelevant"
    UNFAIR_PREJUDICE = "Unfair Prejudice"
    LACK_OF_FOUNDATION = "Lack of Foundation"
    BEST_EVIDENCE_RULE = "Best Evidence Rule Violation"
    AUTHENTICATION = "Not Properly Authenticated"
    CHAIN_OF_CUSTODY = "Chain of Custody Issues"
    PRIVILEGE = "Privileged Communication"
    IMPROPER_CHARACTER = "Improper Character Evidence"
    SPECULATION = "Speculative"


@dataclass
class EvidenceItem:
    """Represents a piece of evidence in the case."""
    evidence_id: str
    exhibit_number: str  # e.g., "Exhibit P-1", "Exhibit D-3"
    title: str
    description: str
    category: EvidenceCategory
    status: EvidenceStatus = EvidenceStatus.NOT_INTRODUCED
    owner_side: str = "petitioner"  # "petitioner" or "respondent"
    introduced_by: Optional[str] = None  # Who introduced it
    introduced_turn: Optional[int] = None
    witness_who_identified: Optional[str] = None
    objections: List[Dict[str, Any]] = field(default_factory=list)
    judge_ruling: Optional[str] = None
    relevance_score: float = 0.0  # How relevant to the case (0-100)
    authenticity_challenged: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class EvidenceLocker:
    """
    Manages all evidence in the case.
    Simulates realistic evidence handling in court.
    """
    petitioner_evidence: List[EvidenceItem] = field(default_factory=list)
    respondent_evidence: List[EvidenceItem] = field(default_factory=list)
    admitted_evidence: List[str] = field(default_factory=list)  # IDs of admitted evidence
    excluded_evidence: List[str] = field(default_factory=list)  # IDs of excluded evidence
    current_exhibit_number: int = 1

    def get_all_evidence(self) -> List[EvidenceItem]:
        """Get all evidence items."""
        return self.petitioner_evidence + self.respondent_evidence

    def get_evidence_by_id(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Find evidence by ID."""
        for item in self.get_all_evidence():
            if item.evidence_id == evidence_id:
                return item
        return None

    def get_evidence_by_status(self, status: EvidenceStatus) -> List[EvidenceItem]:
        """Get all evidence with a specific status."""
        return [e for e in self.get_all_evidence() if e.status == status]

    def get_evidence_by_category(self, category: EvidenceCategory) -> List[EvidenceItem]:
        """Get all evidence in a category."""
        return [e for e in self.get_all_evidence() if e.category == category]

    def get_party_evidence(self, side: str) -> List[EvidenceItem]:
        """Get evidence belonging to a party."""
        if side == "petitioner":
            return self.petitioner_evidence
        return self.respondent_evidence

    def get_available_to_present(self, side: str) -> List[EvidenceItem]:
        """Get evidence that can still be presented by a party."""
        evidence = self.get_party_evidence(side)
        return [e for e in evidence if e.status in [
            EvidenceStatus.NOT_INTRODUCED,
            EvidenceStatus.MARKED_FOR_ID
        ]]

    def get_admitted_items(self) -> List[EvidenceItem]:
        """Get all admitted evidence."""
        return [e for e in self.get_all_evidence() if e.status == EvidenceStatus.ADMITTED]


class DynamicEventType(str, Enum):
    NEW_WITNESS = "New witness emerges"
    NEW_EVIDENCE = "New evidence discovered"
    WITNESS_HOSTILE = "Witness turns hostile"
    WITNESS_RECANTS = "Witness recants statement"
    NEW_FACT = "New fact revealed"
    OPPOSING_OBJECTION = "Opposing counsel objects"
    JUDGE_WARNING = "Judge issues warning"
    ADJOURNMENT = "Court adjourns"
    MEDIA_ATTENTION = "Media attention"
    CLIENT_PRESSURE = "Client pressure"


# ============================================================================
# JUDGE PERSONALITY SYSTEM
# ============================================================================

class JudgePersonalityType(str, Enum):
    """Types of judge personalities."""
    STRICT = "strict"  # Low tolerance, strict on procedures
    PATIENT = "patient"  # Allows detailed arguments, lenient
    TECHNICAL = "technical"  # Wants citations, focuses on legal points
    PRAGMATIC = "pragmatic"  # Focuses on facts, practical outcomes
    FORMAL = "formal"  # High emphasis on court decorum
    INQUISITIVE = "inquisitive"  # Asks many questions, probes deeply


class JudgeMood(str, Enum):
    """Current mood of the judge during proceedings."""
    NEUTRAL = "neutral"
    PLEASED = "pleased"
    IMPATIENT = "impatient"
    ANNOYED = "annoyed"
    INTERESTED = "interested"
    SKEPTICAL = "skeptical"


@dataclass
class JudgePersonality:
    """
    Defines a judge's personality traits that affect their behavior.
    All traits are on a scale of 0-100.
    """
    # Basic info
    name: str
    title: str  # e.g., "Hon'ble Justice"
    personality_type: JudgePersonalityType

    # Core traits (0-100)
    patience: float = 50.0  # How patient with long arguments/delays
    formality: float = 50.0  # How strict about court decorum
    technical_focus: float = 50.0  # How much they want legal citations
    emotional_tolerance: float = 50.0  # Tolerance for emotional appeals
    interruption_tendency: float = 30.0  # How often they interrupt
    question_frequency: float = 40.0  # How often they ask clarifying questions

    # Behavioral preferences
    prefers_brevity: bool = False  # Prefers concise arguments
    values_precedent: bool = True  # Values case law citations
    sympathetic_to_victims: bool = False  # Leans toward claimants
    strict_on_evidence: bool = False  # Strict evidence admission
    tolerates_repetition: bool = True  # Allows repeated points

    # Thresholds
    patience_warning_threshold: float = 60.0  # When patience drops below, gives warning
    annoyance_threshold: float = 30.0  # When patience drops below, becomes annoyed

    # Bonus/penalty multipliers for scoring
    citation_bonus: float = 1.0  # Multiplier for good citations
    decorum_penalty: float = 1.0  # Multiplier for decorum violations
    brevity_bonus: float = 1.0  # Multiplier for concise arguments

    # Description for UI
    description: str = ""
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)


@dataclass
class JudgeState:
    """
    Tracks the current state of the judge during the trial.
    """
    personality: JudgePersonality
    current_mood: JudgeMood = JudgeMood.NEUTRAL
    current_patience: float = 100.0  # Starts full, decreases over time
    satisfaction_score: float = 50.0  # How satisfied with the proceedings
    questions_asked: int = 0
    warnings_given: int = 0
    interruptions_made: int = 0

    # Tracking player performance in judge's eyes
    player_credibility: float = 50.0  # How much judge trusts player
    player_preparation_score: float = 50.0  # How prepared player seems
    citations_appreciated: int = 0
    emotional_appeals_made: int = 0
    repetitions_noted: int = 0

    # Recent actions tracking
    recent_actions: List[str] = field(default_factory=list)  # Last 5 action types

    def update_mood(self):
        """Update judge's mood based on current state."""
        if self.current_patience < self.personality.annoyance_threshold:
            self.current_mood = JudgeMood.ANNOYED
        elif self.current_patience < self.personality.patience_warning_threshold:
            self.current_mood = JudgeMood.IMPATIENT
        elif self.satisfaction_score > 70:
            self.current_mood = JudgeMood.PLEASED
        elif self.satisfaction_score < 30:
            self.current_mood = JudgeMood.SKEPTICAL
        else:
            self.current_mood = JudgeMood.NEUTRAL


# Predefined Judge Personalities
JUDGE_PERSONALITIES = {
    "strict_kumar": JudgePersonality(
        name="Justice Strict Kumar",
        title="Hon'ble Mr. Justice",
        personality_type=JudgePersonalityType.STRICT,
        patience=30.0,
        formality=85.0,
        technical_focus=60.0,
        emotional_tolerance=25.0,
        interruption_tendency=60.0,
        question_frequency=30.0,
        prefers_brevity=True,
        values_precedent=True,
        sympathetic_to_victims=False,
        strict_on_evidence=True,
        tolerates_repetition=False,
        patience_warning_threshold=70.0,
        annoyance_threshold=40.0,
        citation_bonus=1.2,
        decorum_penalty=1.5,
        brevity_bonus=1.3,
        description="A no-nonsense judge with low tolerance for delays and strict adherence to procedure.",
        strengths=["Appreciates concise arguments", "Values proper citations", "Respects procedural compliance"],
        weaknesses=["Impatient with long explanations", "Intolerant of informality", "Dislikes emotional appeals"]
    ),
    "patient_sharma": JudgePersonality(
        name="Justice Patient Sharma",
        title="Hon'ble Mrs. Justice",
        personality_type=JudgePersonalityType.PATIENT,
        patience=85.0,
        formality=50.0,
        technical_focus=40.0,
        emotional_tolerance=75.0,
        interruption_tendency=15.0,
        question_frequency=60.0,
        prefers_brevity=False,
        values_precedent=True,
        sympathetic_to_victims=True,
        strict_on_evidence=False,
        tolerates_repetition=True,
        patience_warning_threshold=40.0,
        annoyance_threshold=20.0,
        citation_bonus=1.0,
        decorum_penalty=0.8,
        brevity_bonus=0.9,
        description="A compassionate judge who allows detailed arguments and is lenient on first-time mistakes.",
        strengths=["Allows thorough explanations", "Asks helpful questions", "Lenient on minor errors"],
        weaknesses=["May seem indecisive", "Proceedings can run long", "May favor emotional arguments"]
    ),
    "technical_rao": JudgePersonality(
        name="Justice Technical Rao",
        title="Hon'ble Mr. Justice",
        personality_type=JudgePersonalityType.TECHNICAL,
        patience=55.0,
        formality=70.0,
        technical_focus=95.0,
        emotional_tolerance=20.0,
        interruption_tendency=45.0,
        question_frequency=70.0,
        prefers_brevity=False,
        values_precedent=True,
        sympathetic_to_victims=False,
        strict_on_evidence=True,
        tolerates_repetition=False,
        patience_warning_threshold=55.0,
        annoyance_threshold=30.0,
        citation_bonus=1.5,
        decorum_penalty=1.2,
        brevity_bonus=1.0,
        description="A scholarly judge who demands case law citations and focuses on legal technicalities.",
        strengths=["Highly values legal citations", "Appreciates technical arguments", "Thorough legal analysis"],
        weaknesses=["Dismissive of emotional appeals", "Expects deep legal knowledge", "Can be pedantic"]
    ),
    "pragmatic_verma": JudgePersonality(
        name="Justice Pragmatic Verma",
        title="Hon'ble Mr. Justice",
        personality_type=JudgePersonalityType.PRAGMATIC,
        patience=60.0,
        formality=45.0,
        technical_focus=50.0,
        emotional_tolerance=55.0,
        interruption_tendency=35.0,
        question_frequency=50.0,
        prefers_brevity=True,
        values_precedent=False,
        sympathetic_to_victims=False,
        strict_on_evidence=True,
        tolerates_repetition=False,
        patience_warning_threshold=50.0,
        annoyance_threshold=25.0,
        citation_bonus=0.9,
        decorum_penalty=1.0,
        brevity_bonus=1.2,
        description="A practical judge focused on facts and outcomes rather than legal formalities.",
        strengths=["Focuses on core issues", "Values factual evidence", "Efficient proceedings"],
        weaknesses=["Less impressed by case law", "May cut short legal arguments", "Results-oriented"]
    ),
    "inquisitive_gupta": JudgePersonality(
        name="Justice Inquisitive Gupta",
        title="Hon'ble Mrs. Justice",
        personality_type=JudgePersonalityType.INQUISITIVE,
        patience=70.0,
        formality=55.0,
        technical_focus=65.0,
        emotional_tolerance=50.0,
        interruption_tendency=70.0,
        question_frequency=90.0,
        prefers_brevity=False,
        values_precedent=True,
        sympathetic_to_victims=False,
        strict_on_evidence=False,
        tolerates_repetition=True,
        patience_warning_threshold=45.0,
        annoyance_threshold=25.0,
        citation_bonus=1.1,
        decorum_penalty=1.0,
        brevity_bonus=0.8,
        description="An intellectually curious judge who probes deeply and asks many clarifying questions.",
        strengths=["Thorough understanding", "Fair opportunity to explain", "Engaged in proceedings"],
        weaknesses=["Frequent interruptions", "May derail arguments", "Lengthy questioning"]
    )
}


def get_random_judge() -> JudgePersonality:
    """Get a random judge personality."""
    import random
    return random.choice(list(JUDGE_PERSONALITIES.values()))


def get_judge_by_type(personality_type: JudgePersonalityType) -> JudgePersonality:
    """Get a judge matching the specified personality type."""
    for judge in JUDGE_PERSONALITIES.values():
        if judge.personality_type == personality_type:
            return judge
    return get_random_judge()


# ============================================================================
# PRE-TRIAL PREPARATION SYSTEM
# ============================================================================

class PreparationCategory(str, Enum):
    """Categories of preparation tasks."""
    CASE_REVIEW = "case_review"
    WITNESS_PREP = "witness_prep"
    LEGAL_RESEARCH = "legal_research"
    EVIDENCE_ANALYSIS = "evidence_analysis"
    STRATEGY = "strategy"
    OPENING_STATEMENT = "opening_statement"


class PreparationDifficulty(str, Enum):
    """Difficulty level of preparation tasks."""
    BASIC = "basic"  # Quick, easy tasks
    INTERMEDIATE = "intermediate"  # Moderate effort
    ADVANCED = "advanced"  # Requires careful thought


@dataclass
class PreparationTask:
    """A single preparation task the player can complete."""
    task_id: str
    title: str
    description: str
    category: PreparationCategory
    difficulty: PreparationDifficulty
    time_cost: int = 1  # How many prep points it costs
    score_bonus: float = 5.0  # Bonus to starting score
    skill_bonuses: Dict[str, float] = field(default_factory=dict)  # Specific skill bonuses
    is_completed: bool = False
    is_available: bool = True
    requires_task: Optional[str] = None  # Task ID that must be completed first
    reveal_info: Optional[str] = None  # Information revealed when completed
    choices: List[str] = field(default_factory=list)  # For tasks with choices
    chosen_option: Optional[int] = None


@dataclass
class PreparationState:
    """
    Tracks the player's pre-trial preparation progress.
    """
    total_prep_points: int = 10  # Total preparation time/points available
    used_prep_points: int = 0
    tasks: List[PreparationTask] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)

    # Bonuses accumulated from preparation
    total_score_bonus: float = 0.0
    skill_bonuses: Dict[str, float] = field(default_factory=dict)

    # Key insights discovered
    case_insights: List[str] = field(default_factory=list)
    witness_insights: Dict[str, str] = field(default_factory=dict)
    opponent_weaknesses: List[str] = field(default_factory=list)
    key_evidence_identified: List[str] = field(default_factory=list)

    # Preparation quality rating
    preparation_grade: str = "D"  # A, B, C, D, F

    @property
    def remaining_points(self) -> int:
        return self.total_prep_points - self.used_prep_points

    def calculate_grade(self) -> str:
        """Calculate preparation grade based on completed tasks."""
        if not self.tasks:
            return "F"

        completion_rate = len(self.completed_tasks) / len(self.tasks)
        total_possible_bonus = sum(t.score_bonus for t in self.tasks)
        bonus_rate = self.total_score_bonus / total_possible_bonus if total_possible_bonus > 0 else 0

        combined_score = (completion_rate * 0.4 + bonus_rate * 0.6) * 100

        if combined_score >= 90:
            return "A"
        elif combined_score >= 75:
            return "B"
        elif combined_score >= 60:
            return "C"
        elif combined_score >= 40:
            return "D"
        else:
            return "F"


def generate_preparation_tasks(case: 'CourtCase', player_side: 'PlayerSide') -> List[PreparationTask]:
    """Generate preparation tasks based on the case and player's side."""
    tasks = []

    # ========================================
    # CASE REVIEW TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="review_case_file",
        title="Review Case File",
        description="Thoroughly review the case documents to understand the facts and allegations.",
        category=PreparationCategory.CASE_REVIEW,
        difficulty=PreparationDifficulty.BASIC,
        time_cost=1,
        score_bonus=5.0,
        skill_bonuses={"legal_accuracy": 5.0},
        reveal_info="You have a clear understanding of the case timeline and key facts."
    ))

    tasks.append(PreparationTask(
        task_id="analyze_issues",
        title="Analyze Legal Issues",
        description="Identify and analyze the key legal issues that need to be addressed.",
        category=PreparationCategory.CASE_REVIEW,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=8.0,
        skill_bonuses={"legal_accuracy": 8.0, "persuasiveness": 3.0},
        requires_task="review_case_file",
        reveal_info="You've identified the critical legal issues and burden of proof."
    ))

    # ========================================
    # WITNESS PREPARATION TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="identify_witnesses",
        title="Identify Key Witnesses",
        description="Review the witness list and identify which witnesses are most important.",
        category=PreparationCategory.WITNESS_PREP,
        difficulty=PreparationDifficulty.BASIC,
        time_cost=1,
        score_bonus=5.0,
        skill_bonuses={"witness_examination": 5.0},
        reveal_info="You know which witnesses hold the key to your case."
    ))

    tasks.append(PreparationTask(
        task_id="prepare_questions",
        title="Prepare Question List",
        description="Draft key questions for examination and cross-examination of witnesses.",
        category=PreparationCategory.WITNESS_PREP,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=10.0,
        skill_bonuses={"witness_examination": 10.0},
        requires_task="identify_witnesses",
        reveal_info="You have a strategic question list ready."
    ))

    tasks.append(PreparationTask(
        task_id="anticipate_testimony",
        title="Anticipate Witness Testimony",
        description="Predict what each witness is likely to say based on their statements.",
        category=PreparationCategory.WITNESS_PREP,
        difficulty=PreparationDifficulty.ADVANCED,
        time_cost=2,
        score_bonus=12.0,
        skill_bonuses={"witness_examination": 8.0, "persuasiveness": 5.0},
        requires_task="identify_witnesses",
        reveal_info="You can anticipate witness responses and prepare follow-ups."
    ))

    # ========================================
    # LEGAL RESEARCH TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="research_case_law",
        title="Research Case Law",
        description="Find relevant precedents and case law to support your arguments.",
        category=PreparationCategory.LEGAL_RESEARCH,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=10.0,
        skill_bonuses={"legal_accuracy": 10.0, "persuasiveness": 5.0},
        reveal_info="You've found strong precedents to cite during arguments."
    ))

    tasks.append(PreparationTask(
        task_id="study_statutes",
        title="Study Relevant Statutes",
        description="Review the statutory provisions and sections applicable to this case.",
        category=PreparationCategory.LEGAL_RESEARCH,
        difficulty=PreparationDifficulty.BASIC,
        time_cost=1,
        score_bonus=6.0,
        skill_bonuses={"legal_accuracy": 8.0},
        reveal_info="You understand the legal framework governing this case."
    ))

    # ========================================
    # EVIDENCE ANALYSIS TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="review_evidence",
        title="Review Documentary Evidence",
        description="Examine all documentary evidence and identify key documents.",
        category=PreparationCategory.EVIDENCE_ANALYSIS,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=8.0,
        skill_bonuses={"evidence_handling": 10.0},
        reveal_info="You've identified the strongest evidence for your case."
    ))

    tasks.append(PreparationTask(
        task_id="find_weaknesses_evidence",
        title="Find Evidence Weaknesses",
        description="Identify potential weaknesses or gaps in the opponent's evidence.",
        category=PreparationCategory.EVIDENCE_ANALYSIS,
        difficulty=PreparationDifficulty.ADVANCED,
        time_cost=2,
        score_bonus=12.0,
        skill_bonuses={"evidence_handling": 8.0, "objection_success": 10.0},
        requires_task="review_evidence",
        reveal_info="You've spotted vulnerabilities in the opponent's evidence."
    ))

    # ========================================
    # STRATEGY TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="analyze_opponent",
        title="Analyze Opponent's Case",
        description="Study the opponent's likely strategy and identify weaknesses.",
        category=PreparationCategory.STRATEGY,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=10.0,
        skill_bonuses={"persuasiveness": 8.0, "objection_success": 5.0},
        reveal_info="You understand your opponent's likely approach."
    ))

    tasks.append(PreparationTask(
        task_id="develop_theory",
        title="Develop Case Theory",
        description="Formulate a compelling narrative theory for your case.",
        category=PreparationCategory.STRATEGY,
        difficulty=PreparationDifficulty.ADVANCED,
        time_cost=2,
        score_bonus=15.0,
        skill_bonuses={"persuasiveness": 12.0, "legal_accuracy": 5.0},
        requires_task="analyze_issues",
        reveal_info="You have a clear, persuasive theory of the case."
    ))

    # ========================================
    # OPENING STATEMENT TASKS
    # ========================================

    tasks.append(PreparationTask(
        task_id="draft_opening",
        title="Draft Opening Statement",
        description="Prepare your opening statement outlining your case theory.",
        category=PreparationCategory.OPENING_STATEMENT,
        difficulty=PreparationDifficulty.INTERMEDIATE,
        time_cost=2,
        score_bonus=10.0,
        skill_bonuses={"persuasiveness": 10.0, "courtroom_decorum": 5.0},
        reveal_info="Your opening statement is ready and compelling."
    ))

    tasks.append(PreparationTask(
        task_id="practice_delivery",
        title="Practice Delivery",
        description="Practice your opening statement for confident delivery.",
        category=PreparationCategory.OPENING_STATEMENT,
        difficulty=PreparationDifficulty.BASIC,
        time_cost=1,
        score_bonus=5.0,
        skill_bonuses={"courtroom_decorum": 8.0, "persuasiveness": 3.0},
        requires_task="draft_opening",
        reveal_info="You feel confident about your courtroom presence."
    ))

    # Set difficulty-based time costs based on game difficulty
    # (This could be adjusted based on the game's difficulty setting)

    return tasks


# ============================================================================
# WITNESS CREDIBILITY SYSTEM
# ============================================================================

class QuestioningStyle(str, Enum):
    """Style of questioning that affects witness behavior."""
    AGGRESSIVE = "aggressive"  # Confrontational, rapid-fire, accusatory
    GENTLE = "gentle"  # Soft, empathetic, building rapport
    NEUTRAL = "neutral"  # Professional, straightforward
    LEADING = "leading"  # Suggestive, guiding answers
    CONFUSING = "confusing"  # Complex, convoluted questions
    RAPID_FIRE = "rapid_fire"  # Quick succession of questions


class WitnessReaction(str, Enum):
    """How a witness reacts to questioning."""
    COOPERATIVE = "cooperative"
    DEFENSIVE = "defensive"
    HOSTILE = "hostile"
    NERVOUS = "nervous"
    CONFUSED = "confused"
    EVASIVE = "evasive"
    CONFIDENT = "confident"
    BREAKDOWN = "breakdown"  # Emotional breakdown


@dataclass
class WitnessStats:
    """
    Hidden statistics for each witness that affect their testimony.
    These stats change dynamically based on questioning.
    """
    # Core stats (0-100)
    credibility: float = 75.0  # How believable the witness appears
    nervousness: float = 30.0  # Current anxiety level
    hostility: float = 10.0  # How hostile toward the examiner
    memory_accuracy: float = 80.0  # How accurate their recall is

    # Derived stats
    cooperation: float = 70.0  # Willingness to answer fully
    composure: float = 70.0  # Ability to stay calm under pressure
    consistency: float = 85.0  # How consistent their answers are

    # Hidden traits (set at initialization, don't change)
    base_credibility: float = 75.0
    base_nervousness: float = 30.0
    base_hostility: float = 10.0
    base_memory: float = 80.0

    # Thresholds for special behaviors
    hostility_threshold: float = 70.0  # Above this, witness may turn hostile
    breakdown_threshold: float = 85.0  # Nervousness above this may cause breakdown

    # Tracking
    contradictions_caught: int = 0
    times_challenged: int = 0
    rapport_built: bool = False
    has_broken_down: bool = False
    is_hostile: bool = False

    def clamp_stats(self):
        """Ensure all stats stay within 0-100 range."""
        self.credibility = max(0, min(100, self.credibility))
        self.nervousness = max(0, min(100, self.nervousness))
        self.hostility = max(0, min(100, self.hostility))
        self.memory_accuracy = max(0, min(100, self.memory_accuracy))
        self.cooperation = max(0, min(100, self.cooperation))
        self.composure = max(0, min(100, self.composure))
        self.consistency = max(0, min(100, self.consistency))


@dataclass
class WitnessState:
    """
    Tracks the current state of a witness during examination.
    """
    witness_id: str
    witness_name: str
    witness_type: str  # "PW" or "RW"
    stats: WitnessStats
    current_reaction: WitnessReaction = WitnessReaction.COOPERATIVE
    questions_asked: int = 0
    examination_phase: str = "chief"  # "chief" or "cross"
    key_admissions: List[str] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    favorable_statements: List[str] = field(default_factory=list)
    unfavorable_statements: List[str] = field(default_factory=list)

    # For tracking question patterns
    recent_styles: List[QuestioningStyle] = field(default_factory=list)
    aggressive_streak: int = 0
    gentle_streak: int = 0


@dataclass
class GameAction:
    """Represents a player action in the game."""
    action_type: ActionType
    content: str
    target: Optional[str] = None  # e.g., witness name for questions
    evidence_id: Optional[str] = None
    objection_type: Optional[ObjectionType] = None
    evidence_objection_type: Optional[EvidenceObjectionType] = None  # For evidence objections


@dataclass
class DynamicEvent:
    """A dynamic event that can occur during the game."""
    event_type: DynamicEventType
    description: str
    impact: str
    requires_response: bool = False
    response_options: List[str] = field(default_factory=list)
    difficulty_modifier: float = 0.0


@dataclass
class GameScore:
    """Player's game score and performance metrics."""
    legal_accuracy: float = 0.0  # How legally sound arguments are
    persuasiveness: float = 0.0  # How convincing to the judge
    evidence_handling: float = 0.0  # How well evidence is presented
    witness_examination: float = 0.0  # Quality of witness questioning
    objection_success: float = 0.0  # Success rate of objections
    courtroom_decorum: float = 0.0  # Following court protocols
    case_theory: float = 0.0  # Coherence of overall case theory
    total_points: int = 0
    judge_favor: float = 50.0  # 0-100, starts neutral

    def calculate_total(self) -> float:
        weights = {
            'legal_accuracy': 0.2,
            'persuasiveness': 0.2,
            'evidence_handling': 0.15,
            'witness_examination': 0.15,
            'objection_success': 0.1,
            'courtroom_decorum': 0.1,
            'case_theory': 0.1
        }
        return sum(getattr(self, k) * v for k, v in weights.items())


@dataclass
class PhaseTimeLimit:
    """Time/turn limits for each phase - Judge controls this."""
    max_turns: int  # Maximum turns allowed in this phase
    warning_at: int  # Turn number when Judge gives "wrap up" warning
    can_extend: bool = True  # Whether Judge may grant extension


# Phase limits - simulating a Judge with limited court time
PHASE_LIMITS = {
    GamePhase.OPENING_STATEMENT: PhaseTimeLimit(max_turns=3, warning_at=2, can_extend=False),
    GamePhase.PETITIONER_WITNESS_EXAM: PhaseTimeLimit(max_turns=6, warning_at=4, can_extend=True),
    GamePhase.CROSS_EXAMINATION: PhaseTimeLimit(max_turns=5, warning_at=3, can_extend=True),
    GamePhase.RESPONDENT_WITNESS_EXAM: PhaseTimeLimit(max_turns=6, warning_at=4, can_extend=True),
    GamePhase.FINAL_ARGUMENTS: PhaseTimeLimit(max_turns=4, warning_at=3, can_extend=False),
}


# ============================================================================
# COURT ETIQUETTE & PROTOCOL SYSTEM
# ============================================================================

class EtiquetteViolationType(str, Enum):
    """Types of court etiquette violations."""
    IMPROPER_ADDRESS = "improper_address"  # Not addressing judge properly
    NO_PERMISSION = "no_permission"  # Acting without court's permission
    MISSING_COURTESY = "missing_courtesy"  # Missing "May it please the court"
    INTERRUPTING = "interrupting"  # Interrupting proceedings
    INFORMAL_LANGUAGE = "informal_language"  # Too casual/informal
    DISRESPECTFUL = "disrespectful"  # Disrespectful to court/parties
    IMPROPER_REFERENCE = "improper_reference"  # Improper reference to parties


@dataclass
class EtiquetteViolation:
    """Represents a court etiquette violation."""
    violation_type: EtiquetteViolationType
    description: str
    severity: str  # "minor", "moderate", "serious"
    suggestion: str  # How to correct it


class CourtEtiquetteChecker:
    """
    Checks player submissions for proper court etiquette and protocol.
    Teaches real courtroom decorum through feedback.
    """

    # Proper ways to address the Judge (Indian courts)
    JUDGE_ADDRESSES = [
        "my lord", "your lordship", "your honour", "your honor",
        "hon'ble court", "honourable court", "honorable court",
        "this court", "learned court", "my lady"
    ]

    # Courtesy phrases expected at start of arguments
    COURTESY_STARTERS = [
        "may it please", "with your lordship's permission",
        "with the court's permission", "if it please the court",
        "with due respect", "respectfully", "i humbly submit",
        "it is submitted", "my submission is", "i submit"
    ]

    # Phrases for seeking permission
    PERMISSION_PHRASES = [
        "may i", "with your permission", "if i may",
        "with the court's leave", "seeking permission",
        "permission to", "i seek leave"
    ]

    # Informal/casual words to avoid
    INFORMAL_WORDS = [
        "yeah", "yep", "nope", "gonna", "wanna", "gotta",
        "ok so", "like ", "you know", "basically", "actually",
        "hey", "hi judge", "hello"
    ]

    # Disrespectful patterns
    DISRESPECTFUL_PATTERNS = [
        "you're wrong", "that's ridiculous", "nonsense",
        "that's stupid", "clearly you don't understand",
        "waste of time", "this is unfair"
    ]

    def __init__(self, phase: GamePhase, action_type: ActionType, is_first_in_phase: bool = False):
        self.phase = phase
        self.action_type = action_type
        self.is_first_in_phase = is_first_in_phase

    def check_etiquette(self, content: str) -> List[EtiquetteViolation]:
        """
        Check the player's submission for etiquette violations.
        Returns list of violations found.
        """
        violations = []
        content_lower = content.lower()

        # Check 1: Proper address to Judge
        if self._should_check_judge_address():
            if not self._has_proper_judge_address(content_lower):
                violations.append(EtiquetteViolation(
                    violation_type=EtiquetteViolationType.IMPROPER_ADDRESS,
                    description="Statement does not properly address the Court",
                    severity="minor",
                    suggestion="Address the Court as 'My Lord', 'Your Lordship', or 'Your Honour'"
                ))

        # Check 2: Courtesy phrases for arguments
        if self._should_check_courtesy():
            if not self._has_courtesy_phrase(content_lower):
                violations.append(EtiquetteViolation(
                    violation_type=EtiquetteViolationType.MISSING_COURTESY,
                    description="Opening submission without proper courtesy",
                    severity="minor",
                    suggestion="Begin with 'May it please the Court' or 'It is respectfully submitted'"
                ))

        # Check 3: Permission for witness approach
        if self._should_check_permission():
            if not self._has_permission_phrase(content_lower):
                violations.append(EtiquetteViolation(
                    violation_type=EtiquetteViolationType.NO_PERMISSION,
                    description="Proceeding without seeking Court's permission",
                    severity="minor",
                    suggestion="Seek permission: 'With Your Lordship's permission, I would like to...'"
                ))

        # Check 4: Informal language
        informal_found = self._check_informal_language(content_lower)
        if informal_found:
            violations.append(EtiquetteViolation(
                violation_type=EtiquetteViolationType.INFORMAL_LANGUAGE,
                description=f"Informal language detected: '{informal_found}'",
                severity="moderate",
                suggestion="Use formal legal language appropriate for court proceedings"
            ))

        # Check 5: Disrespectful language
        disrespect_found = self._check_disrespectful_language(content_lower)
        if disrespect_found:
            violations.append(EtiquetteViolation(
                violation_type=EtiquetteViolationType.DISRESPECTFUL,
                description=f"Potentially disrespectful language: '{disrespect_found}'",
                severity="serious",
                suggestion="Maintain respect for the Court and all parties at all times"
            ))

        return violations

    def _should_check_judge_address(self) -> bool:
        """Check if we should verify Judge address."""
        # Check for arguments and important submissions
        return self.action_type in [
            ActionType.MAKE_ARGUMENT,
            ActionType.RAISE_OBJECTION,
            ActionType.CITE_CASE_LAW,
            ActionType.REST_CASE
        ]

    def _should_check_courtesy(self) -> bool:
        """Check if courtesy phrase is expected."""
        # First argument in opening or final arguments should have courtesy
        return self.is_first_in_phase and self.phase in [
            GamePhase.OPENING_STATEMENT,
            GamePhase.FINAL_ARGUMENTS
        ]

    def _should_check_permission(self) -> bool:
        """Check if permission phrase is expected."""
        # When presenting evidence or approaching witness
        return self.action_type in [
            ActionType.PRESENT_EVIDENCE,
        ]

    def _has_proper_judge_address(self, content: str) -> bool:
        """Check if content properly addresses the Judge."""
        return any(addr in content for addr in self.JUDGE_ADDRESSES)

    def _has_courtesy_phrase(self, content: str) -> bool:
        """Check if content has proper courtesy phrase."""
        return any(phrase in content for phrase in self.COURTESY_STARTERS)

    def _has_permission_phrase(self, content: str) -> bool:
        """Check if content seeks permission."""
        return any(phrase in content for phrase in self.PERMISSION_PHRASES)

    def _check_informal_language(self, content: str) -> Optional[str]:
        """Check for informal language, return the offending word/phrase."""
        for word in self.INFORMAL_WORDS:
            if word in content:
                return word.strip()
        return None

    def _check_disrespectful_language(self, content: str) -> Optional[str]:
        """Check for disrespectful language."""
        for pattern in self.DISRESPECTFUL_PATTERNS:
            if pattern in content:
                return pattern
        return None

    @staticmethod
    def get_etiquette_tips(phase: GamePhase) -> List[str]:
        """Get etiquette tips for the current phase."""
        tips = {
            GamePhase.OPENING_STATEMENT: [
                "Begin with 'May it please the Court' or 'My Lord'",
                "Introduce yourself: 'I appear for the Petitioner/Respondent'",
                "Be concise and outline your case theory",
                "End with 'I humbly submit' or similar courtesy"
            ],
            GamePhase.PETITIONER_WITNESS_EXAM: [
                "Address the Court before examining: 'My Lord, I call PW-1'",
                "Ask the witness to state their name for the record",
                "Use open-ended questions, not leading questions",
                "Say 'No further questions, My Lord' when done"
            ],
            GamePhase.CROSS_EXAMINATION: [
                "Seek permission: 'With Your Lordship's permission, I proceed to cross-examine'",
                "You may ask leading questions in cross-examination",
                "Be firm but respectful to the witness",
                "Do not badger or harass the witness"
            ],
            GamePhase.RESPONDENT_WITNESS_EXAM: [
                "Address the Court before examining: 'My Lord, I call DW-1'",
                "Establish witness credentials if expert",
                "Build your case through witness testimony",
                "Say 'No further questions, My Lord' when done"
            ],
            GamePhase.FINAL_ARGUMENTS: [
                "Begin with 'May it please Your Lordship'",
                "Summarize key evidence and legal points",
                "Cite relevant case law with proper citations",
                "End with 'I rest my case' or 'I humbly submit'"
            ]
        }
        return tips.get(phase, ["Maintain proper court decorum at all times"])


# ============================================================================
# REAL-TIME PRESSURE SYSTEM
# ============================================================================

class PressureLevel(str, Enum):
    """Pressure levels affecting the player."""
    CALM = "calm"
    MILD = "mild"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ConfidenceState(str, Enum):
    """Player's apparent confidence state."""
    COMMANDING = "commanding"
    CONFIDENT = "confident"
    STEADY = "steady"
    UNCERTAIN = "uncertain"
    NERVOUS = "nervous"
    FLUSTERED = "flustered"


@dataclass
class TimePressureConfig:
    """Configuration for time pressure based on difficulty."""
    base_time_seconds: int = 60  # Base time per action
    warning_threshold: float = 0.3  # When to show warning (30% time left)
    critical_threshold: float = 0.1  # When to show critical (10% time left)
    judge_prompt_delay: int = 45  # Seconds before judge prompts
    rush_penalty_threshold: float = 0.2  # If answered in <20% of time, may have errors
    extension_available: bool = True  # Can request extension
    max_extensions: int = 2  # Max extensions per trial


@dataclass
class ResponseTimingStats:
    """Statistics about player's response timing."""
    response_time_seconds: float = 0.0
    was_rushed: bool = False
    was_slow: bool = False
    judge_prompted: bool = False
    time_expired: bool = False
    extension_used: bool = False


@dataclass
class ConfidenceMeter:
    """
    Tracks player's apparent confidence level.
    Visible to the judge and affects their perception.
    """
    confidence_score: float = 70.0  # 0-100 scale
    min_confidence: float = 0.0
    max_confidence: float = 100.0

    # Factors affecting confidence
    hesitation_count: int = 0  # Times player took too long
    contradiction_count: int = 0  # Self-contradictions
    objection_success_rate: float = 0.5  # Successful objections ratio
    argument_coherence: float = 70.0  # How well arguments flow
    evidence_handling: float = 70.0  # How well evidence is presented
    witness_control: float = 70.0  # Control over witness examination
    judge_approval: float = 50.0  # Judge's perception

    # Streak tracking
    confident_actions_streak: int = 0
    uncertain_actions_streak: int = 0

    # Historical tracking
    confidence_history: List[float] = field(default_factory=list)
    peak_confidence: float = 70.0
    lowest_confidence: float = 70.0

    @property
    def confidence_state(self) -> ConfidenceState:
        """Get the current confidence state category."""
        if self.confidence_score >= 90:
            return ConfidenceState.COMMANDING
        elif self.confidence_score >= 75:
            return ConfidenceState.CONFIDENT
        elif self.confidence_score >= 60:
            return ConfidenceState.STEADY
        elif self.confidence_score >= 45:
            return ConfidenceState.UNCERTAIN
        elif self.confidence_score >= 30:
            return ConfidenceState.NERVOUS
        else:
            return ConfidenceState.FLUSTERED

    def adjust_confidence(self, delta: float, reason: str = "") -> Dict[str, Any]:
        """Adjust confidence score and track the change."""
        old_score = self.confidence_score
        self.confidence_score = max(self.min_confidence,
                                     min(self.max_confidence, self.confidence_score + delta))

        # Update history
        self.confidence_history.append(self.confidence_score)
        if len(self.confidence_history) > 50:  # Keep last 50 entries
            self.confidence_history = self.confidence_history[-50:]

        # Update peaks
        if self.confidence_score > self.peak_confidence:
            self.peak_confidence = self.confidence_score
        if self.confidence_score < self.lowest_confidence:
            self.lowest_confidence = self.confidence_score

        # Update streaks
        if delta > 0:
            self.confident_actions_streak += 1
            self.uncertain_actions_streak = 0
        elif delta < 0:
            self.uncertain_actions_streak += 1
            self.confident_actions_streak = 0

        return {
            "old_score": old_score,
            "new_score": self.confidence_score,
            "delta": delta,
            "reason": reason,
            "state": self.confidence_state.value
        }


@dataclass
class TimePressureState:
    """
    Tracks the time pressure system state.
    """
    config: TimePressureConfig = field(default_factory=TimePressureConfig)

    # Current action timing
    action_start_time: Optional[datetime] = None
    current_time_limit: int = 60  # Seconds for current action
    time_remaining: float = 60.0

    # Session statistics
    total_actions: int = 0
    rushed_actions: int = 0
    slow_actions: int = 0
    timed_out_actions: int = 0
    judge_prompts_received: int = 0
    extensions_used: int = 0
    extensions_remaining: int = 2

    # Current state
    is_timer_active: bool = False
    current_pressure_level: PressureLevel = PressureLevel.CALM
    judge_has_prompted: bool = False

    # Response time tracking
    response_times: List[float] = field(default_factory=list)
    average_response_time: float = 0.0

    @property
    def time_percentage(self) -> float:
        """Get percentage of time remaining."""
        if self.current_time_limit == 0:
            return 0.0
        return self.time_remaining / self.current_time_limit

    def start_timer(self, time_limit: Optional[int] = None) -> None:
        """Start the timer for a new action."""
        self.action_start_time = datetime.now()
        self.current_time_limit = time_limit or self.config.base_time_seconds
        self.time_remaining = float(self.current_time_limit)
        self.is_timer_active = True
        self.judge_has_prompted = False
        self.current_pressure_level = PressureLevel.CALM

    def update_time(self) -> Dict[str, Any]:
        """Update time remaining and pressure level."""
        if not self.is_timer_active or not self.action_start_time:
            return {"active": False}

        elapsed = (datetime.now() - self.action_start_time).total_seconds()
        self.time_remaining = max(0, self.current_time_limit - elapsed)

        # Update pressure level
        time_pct = self.time_percentage
        if time_pct <= 0:
            self.current_pressure_level = PressureLevel.CRITICAL
        elif time_pct <= self.config.critical_threshold:
            self.current_pressure_level = PressureLevel.CRITICAL
        elif time_pct <= self.config.warning_threshold:
            self.current_pressure_level = PressureLevel.HIGH
        elif time_pct <= 0.5:
            self.current_pressure_level = PressureLevel.MODERATE
        elif time_pct <= 0.7:
            self.current_pressure_level = PressureLevel.MILD
        else:
            self.current_pressure_level = PressureLevel.CALM

        # Check if judge should prompt
        should_judge_prompt = (elapsed >= self.config.judge_prompt_delay and
                              not self.judge_has_prompted)

        return {
            "active": True,
            "time_remaining": self.time_remaining,
            "time_percentage": time_pct,
            "pressure_level": self.current_pressure_level.value,
            "should_judge_prompt": should_judge_prompt,
            "is_expired": self.time_remaining <= 0
        }

    def stop_timer(self) -> ResponseTimingStats:
        """Stop the timer and calculate response stats."""
        if not self.action_start_time:
            return ResponseTimingStats()

        elapsed = (datetime.now() - self.action_start_time).total_seconds()
        self.is_timer_active = False

        # Calculate stats
        stats = ResponseTimingStats()
        stats.response_time_seconds = elapsed
        stats.time_expired = self.time_remaining <= 0
        stats.judge_prompted = self.judge_has_prompted

        # Check if rushed (answered very quickly - may indicate hasty response)
        if elapsed < self.current_time_limit * self.config.rush_penalty_threshold:
            stats.was_rushed = True
            self.rushed_actions += 1

        # Check if slow (took more than 80% of time)
        if elapsed > self.current_time_limit * 0.8:
            stats.was_slow = True
            self.slow_actions += 1

        if stats.time_expired:
            self.timed_out_actions += 1

        if stats.judge_prompted:
            self.judge_prompts_received += 1

        # Update tracking
        self.total_actions += 1
        self.response_times.append(elapsed)
        if len(self.response_times) > 0:
            self.average_response_time = sum(self.response_times) / len(self.response_times)

        return stats

    def use_extension(self, extra_seconds: int = 30) -> bool:
        """Use a time extension if available."""
        if self.extensions_remaining <= 0:
            return False

        self.extensions_remaining -= 1
        self.extensions_used += 1
        self.time_remaining += extra_seconds
        self.current_time_limit += extra_seconds
        return True

    def mark_judge_prompted(self) -> None:
        """Mark that the judge has prompted the player."""
        self.judge_has_prompted = True


# Difficulty-based time pressure configurations
TIME_PRESSURE_CONFIGS = {
    "easy": TimePressureConfig(
        base_time_seconds=90,
        warning_threshold=0.25,
        critical_threshold=0.1,
        judge_prompt_delay=70,
        rush_penalty_threshold=0.15,
        extension_available=True,
        max_extensions=3
    ),
    "medium": TimePressureConfig(
        base_time_seconds=60,
        warning_threshold=0.3,
        critical_threshold=0.1,
        judge_prompt_delay=45,
        rush_penalty_threshold=0.2,
        extension_available=True,
        max_extensions=2
    ),
    "hard": TimePressureConfig(
        base_time_seconds=45,
        warning_threshold=0.35,
        critical_threshold=0.15,
        judge_prompt_delay=30,
        rush_penalty_threshold=0.25,
        extension_available=True,
        max_extensions=1
    ),
    "expert": TimePressureConfig(
        base_time_seconds=30,
        warning_threshold=0.4,
        critical_threshold=0.2,
        judge_prompt_delay=20,
        rush_penalty_threshold=0.3,
        extension_available=False,
        max_extensions=0
    )
}


# Judge prompts when player takes too long
JUDGE_TIME_PROMPTS = [
    "Counsel, the court is waiting for your response.",
    "Mr./Ms. Advocate, please proceed with your submission.",
    "The court does not have unlimited time, Counsel.",
    "I trust you are ready to continue, Advocate?",
    "Counsel, do you need a moment, or shall we proceed?",
    "The court notes the delay. Please continue.",
    "Mr./Ms. Advocate, your response?",
    "Counsel, we must maintain the pace of proceedings.",
]

# Judge remarks about rushed responses
JUDGE_RUSH_REMARKS = [
    "The court notes counsel's... enthusiasm to respond.",
    "A hasty answer, Counsel. Are you certain?",
    "The court appreciates brevity, but clarity is paramount.",
    "Counsel seems eager. Let's hope that eagerness is matched with accuracy.",
]

# Judge remarks about confident advocacy
JUDGE_CONFIDENCE_REMARKS = {
    ConfidenceState.COMMANDING: [
        "The court appreciates counsel's command of the facts.",
        "A well-prepared advocate, I see.",
    ],
    ConfidenceState.CONFIDENT: [
        "Counsel appears well-versed in the matter.",
        "The court notes counsel's preparation.",
    ],
    ConfidenceState.UNCERTAIN: [
        "Counsel seems uncertain. Do you wish to reconsider?",
        "The court senses some hesitation, Advocate.",
    ],
    ConfidenceState.NERVOUS: [
        "Take a breath, Counsel. Collect your thoughts.",
        "The court notices counsel's... discomfort.",
    ],
    ConfidenceState.FLUSTERED: [
        "Counsel, perhaps you need a moment?",
        "The court is concerned about counsel's state.",
    ],
}


# ============================================================================
# LEGAL RESEARCH MID-TRIAL SYSTEM
# ============================================================================

class LegalResearchCategory(str, Enum):
    """Categories of legal research."""
    CASE_LAW = "case_law"
    STATUTE = "statute"
    PRECEDENT = "precedent"
    PROCEDURE = "procedure"
    QUANTUM = "quantum"  # For damages/compensation cases
    EVIDENCE_LAW = "evidence_law"


class ResearchRelevance(str, Enum):
    """How relevant the research result is."""
    HIGHLY_RELEVANT = "highly_relevant"
    RELEVANT = "relevant"
    SOMEWHAT_RELEVANT = "somewhat_relevant"
    TANGENTIAL = "tangential"


@dataclass
class CaseLawResult:
    """A case law search result."""
    citation: str  # e.g., "AIR 1985 SC 234"
    case_name: str  # e.g., "State of Punjab v. Mohinder Singh"
    court: str  # e.g., "Supreme Court", "High Court"
    year: int
    category: LegalResearchCategory
    relevance: ResearchRelevance
    key_principle: str  # The legal principle from this case
    applicable_facts: str  # How it applies to current case
    strength_score: float = 70.0  # How strong this citation is (0-100)
    has_been_cited: bool = False  # Whether player has cited this
    discovered_turn: int = 0  # When it was discovered


@dataclass
class ResearchSession:
    """A single research session."""
    search_query: str
    turn_number: int
    results_found: List[CaseLawResult] = field(default_factory=list)
    time_spent: int = 1  # Turns spent on this research
    was_successful: bool = True


@dataclass
class LegalResearchState:
    """
    Tracks the player's legal research during the trial.
    """
    # Research limits
    max_research_per_phase: int = 3  # Max research actions per phase
    research_this_phase: int = 0
    total_research_actions: int = 0

    # Discovered case laws
    discovered_cases: List[CaseLawResult] = field(default_factory=list)
    cited_cases: List[str] = field(default_factory=list)  # Citations that have been used

    # Research history
    research_sessions: List[ResearchSession] = field(default_factory=list)

    # Judge patience tracking
    judge_patience_warnings: int = 0  # Warnings about too much research
    judge_impressed_by_research: bool = False  # If a citation really helped

    # Bonuses/penalties
    research_quality_score: float = 50.0  # Overall quality of research (0-100)
    citation_accuracy_score: float = 50.0  # How well citations were applied

    @property
    def can_research(self) -> bool:
        """Check if player can still do research this phase."""
        return self.research_this_phase < self.max_research_per_phase

    @property
    def research_remaining(self) -> int:
        """Get number of research actions remaining this phase."""
        return max(0, self.max_research_per_phase - self.research_this_phase)


# Pre-defined case law database for different legal topics
# These are sample Indian legal citations for the simulation
CASE_LAW_DATABASE = {
    # Contract Law
    "contract": [
        CaseLawResult(
            citation="AIR 1954 SC 44",
            case_name="Satyabrata Ghose v. Mugneeram Bangur & Co.",
            court="Supreme Court",
            year=1954,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Doctrine of frustration - when performance becomes impossible",
            applicable_facts="Contract obligations when circumstances fundamentally change",
            strength_score=85.0
        ),
        CaseLawResult(
            citation="(2003) 5 SCC 705",
            case_name="Central Inland Water Transport Corp. v. Brojo Nath Ganguly",
            court="Supreme Court",
            year=2003,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Unfair contract terms in employment can be struck down",
            applicable_facts="Courts can intervene in unconscionable contracts",
            strength_score=80.0
        ),
    ],
    # Property Law
    "property": [
        CaseLawResult(
            citation="AIR 1965 SC 1017",
            case_name="Mulla v. Mulla",
            court="Supreme Court",
            year=1965,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Adverse possession requires continuous, open, hostile possession",
            applicable_facts="Requirements for claiming property through adverse possession",
            strength_score=88.0
        ),
        CaseLawResult(
            citation="(2011) 4 SCC 266",
            case_name="Hemaji Waghaji Jat v. Bhikhabhai Khengarbhai Harijan",
            court="Supreme Court",
            year=2011,
            category=LegalResearchCategory.PRECEDENT,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="12 years continuous possession required for adverse possession",
            applicable_facts="Time period and nature of possession in property disputes",
            strength_score=82.0
        ),
    ],
    # Criminal Law
    "criminal": [
        CaseLawResult(
            citation="AIR 1973 SC 947",
            case_name="Bachan Singh v. State of Punjab",
            court="Supreme Court",
            year=1973,
            category=LegalResearchCategory.PRECEDENT,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Death penalty only in 'rarest of rare' cases",
            applicable_facts="Sentencing guidelines for capital punishment",
            strength_score=95.0
        ),
        CaseLawResult(
            citation="(2017) 2 SCC 574",
            case_name="Shayara Bano v. Union of India",
            court="Supreme Court",
            year=2017,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Triple talaq declared unconstitutional",
            applicable_facts="Personal law subject to constitutional scrutiny",
            strength_score=90.0
        ),
    ],
    # Evidence Law
    "evidence": [
        CaseLawResult(
            citation="AIR 1974 SC 348",
            case_name="State of HP v. Jai Lal",
            court="Supreme Court",
            year=1974,
            category=LegalResearchCategory.EVIDENCE_LAW,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Dying declaration can be sole basis of conviction if reliable",
            applicable_facts="Weight to be given to dying declarations",
            strength_score=87.0
        ),
        CaseLawResult(
            citation="(2005) 11 SCC 600",
            case_name="State of NCT Delhi v. Navjot Sandhu",
            court="Supreme Court",
            year=2005,
            category=LegalResearchCategory.EVIDENCE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Circumstantial evidence must form complete chain",
            applicable_facts="Standard for conviction on circumstantial evidence",
            strength_score=85.0
        ),
    ],
    # Compensation/Damages
    "compensation": [
        CaseLawResult(
            citation="(2009) 6 SCC 121",
            case_name="Sarla Verma v. Delhi Transport Corp.",
            court="Supreme Court",
            year=2009,
            category=LegalResearchCategory.QUANTUM,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Multiplier method for calculating compensation in motor accident cases",
            applicable_facts="Formula for computing compensation based on age and income",
            strength_score=92.0
        ),
        CaseLawResult(
            citation="(2017) 16 SCC 680",
            case_name="National Insurance Co. Ltd. v. Pranay Sethi",
            court="Supreme Court",
            year=2017,
            category=LegalResearchCategory.QUANTUM,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Conventional heads for compensation: loss of estate, consortium, funeral",
            applicable_facts="Standard amounts for non-pecuniary damages",
            strength_score=90.0
        ),
    ],
    # Procedure
    "procedure": [
        CaseLawResult(
            citation="AIR 1987 SC 1086",
            case_name="Baldev Singh v. State of Punjab",
            court="Supreme Court",
            year=1987,
            category=LegalResearchCategory.PROCEDURE,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Fair trial is a fundamental right",
            applicable_facts="Procedural safeguards in criminal trials",
            strength_score=88.0
        ),
        CaseLawResult(
            citation="(2014) 9 SCC 737",
            case_name="Arnab Goswami v. Union of India",
            court="Supreme Court",
            year=2014,
            category=LegalResearchCategory.PROCEDURE,
            relevance=ResearchRelevance.SOMEWHAT_RELEVANT,
            key_principle="Courts must protect against harassment through multiple FIRs",
            applicable_facts="Protection against abuse of legal process",
            strength_score=75.0
        ),
    ],
    # Constitutional Law
    "constitutional": [
        CaseLawResult(
            citation="AIR 1973 SC 1461",
            case_name="Kesavananda Bharati v. State of Kerala",
            court="Supreme Court",
            year=1973,
            category=LegalResearchCategory.PRECEDENT,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Basic structure of Constitution cannot be amended",
            applicable_facts="Limits on Parliament's amending power",
            strength_score=98.0
        ),
        CaseLawResult(
            citation="(1978) 1 SCC 248",
            case_name="Maneka Gandhi v. Union of India",
            court="Supreme Court",
            year=1978,
            category=LegalResearchCategory.PRECEDENT,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Right to life includes right to live with dignity",
            applicable_facts="Expanded interpretation of Article 21",
            strength_score=95.0
        ),
    ],
    # Family Law
    "family": [
        CaseLawResult(
            citation="(2017) 9 SCC 766",
            case_name="Shayara Bano v. Union of India",
            court="Supreme Court",
            year=2017,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Instant triple talaq is unconstitutional",
            applicable_facts="Gender equality in personal laws",
            strength_score=90.0
        ),
        CaseLawResult(
            citation="(2014) 1 SCC 188",
            case_name="Rajnesh v. Neha",
            court="Supreme Court",
            year=2014,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Guidelines for maintenance and alimony",
            applicable_facts="Factors for determining maintenance amount",
            strength_score=85.0
        ),
    ],
    # Tort/Negligence
    "negligence": [
        CaseLawResult(
            citation="AIR 1987 SC 1086",
            case_name="M.C. Mehta v. Union of India",
            court="Supreme Court",
            year=1987,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Absolute liability for hazardous industries",
            applicable_facts="No defense available for ultra-hazardous activities",
            strength_score=92.0
        ),
        CaseLawResult(
            citation="(1996) 4 SCC 37",
            case_name="Indian Council for Enviro-Legal Action v. Union of India",
            court="Supreme Court",
            year=1996,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Polluter pays principle",
            applicable_facts="Liability for environmental damage",
            strength_score=88.0
        ),
    ],
    # Service/Employment
    "employment": [
        CaseLawResult(
            citation="(2006) 4 SCC 1",
            case_name="Secretary, State of Karnataka v. Umadevi",
            court="Supreme Court",
            year=2006,
            category=LegalResearchCategory.PRECEDENT,
            relevance=ResearchRelevance.HIGHLY_RELEVANT,
            key_principle="Regularization of temporary employees guidelines",
            applicable_facts="When temporary employees can claim regularization",
            strength_score=90.0
        ),
        CaseLawResult(
            citation="(2015) 4 SCC 136",
            case_name="State of Punjab v. Rafiq Masih",
            court="Supreme Court",
            year=2015,
            category=LegalResearchCategory.CASE_LAW,
            relevance=ResearchRelevance.RELEVANT,
            key_principle="Recovery of excess payment from employees",
            applicable_facts="When employer can recover overpayments",
            strength_score=78.0
        ),
    ],
}

# Search keywords mapping to categories
RESEARCH_KEYWORDS = {
    "contract": ["contract", "agreement", "breach", "performance", "frustration", "consideration"],
    "property": ["property", "land", "possession", "title", "adverse", "easement", "partition"],
    "criminal": ["criminal", "murder", "theft", "assault", "bail", "sentence", "conviction"],
    "evidence": ["evidence", "witness", "testimony", "hearsay", "confession", "dying declaration"],
    "compensation": ["compensation", "damages", "quantum", "loss", "injury", "accident", "death"],
    "procedure": ["procedure", "limitation", "appeal", "revision", "jurisdiction", "forum"],
    "constitutional": ["constitution", "fundamental", "rights", "article", "writ", "PIL"],
    "family": ["divorce", "maintenance", "custody", "marriage", "alimony", "succession"],
    "negligence": ["negligence", "tort", "duty of care", "defamation", "nuisance", "strict liability"],
    "employment": ["employment", "service", "termination", "regularization", "pension", "gratuity"],
}

# Judge remarks about research
JUDGE_RESEARCH_REMARKS = {
    "impatient": [
        "Counsel, are we conducting a trial or a library session?",
        "The court's time is valuable. Do you have your case prepared?",
        "Perhaps counsel should have done this research before coming to court.",
        "I trust this will be your last research break, Advocate.",
    ],
    "warning": [
        "Counsel, the court notes excessive reliance on mid-trial research.",
        "This is highly irregular. Please conclude your research.",
        "The court expects advocates to come prepared.",
    ],
    "appreciative": [
        "A well-researched citation, Counsel.",
        "The court notes the relevant precedent cited.",
        "That is indeed an apt citation.",
    ],
    "neutral": [
        "The court will take note of the cited authority.",
        "Proceed, Counsel.",
    ],
}


# ============================================================================
# SIDEBAR/CHAMBER CONFERENCE SYSTEM
# ============================================================================

class SidebarRequestType(str, Enum):
    """Types of sidebar conference requests."""
    EXCLUDE_EVIDENCE = "exclude_evidence"
    WITNESS_AVAILABILITY = "witness_availability"
    REQUEST_ADJOURNMENT = "request_adjournment"
    SETTLEMENT_DISCUSSION = "settlement_discussion"
    PROCEDURAL_CLARIFICATION = "procedural_clarification"
    JURY_INSTRUCTION = "jury_instruction"  # For jury trials
    WITNESS_PROTECTION = "witness_protection"
    MISTRIAL_MOTION = "mistrial_motion"


class SidebarOutcome(str, Enum):
    """Possible outcomes of a sidebar conference."""
    GRANTED = "granted"
    DENIED = "denied"
    PARTIALLY_GRANTED = "partially_granted"
    DEFERRED = "deferred"
    TAKEN_UNDER_ADVISEMENT = "taken_under_advisement"


class AdjournmentReason(str, Enum):
    """Reasons for requesting adjournment."""
    WITNESS_UNAVAILABLE = "witness_unavailable"
    NEED_MORE_TIME = "need_more_time"
    NEW_EVIDENCE_DISCOVERED = "new_evidence_discovered"
    HEALTH_REASONS = "health_reasons"
    SETTLEMENT_NEGOTIATIONS = "settlement_negotiations"
    CONSULT_CLIENT = "consult_client"


@dataclass
class SidebarRequest:
    """A sidebar conference request."""
    request_id: str
    request_type: SidebarRequestType
    turn_number: int
    reason: str
    supporting_argument: str = ""
    evidence_id: Optional[str] = None  # For evidence exclusion requests
    witness_id: Optional[str] = None  # For witness-related requests
    adjournment_reason: Optional[AdjournmentReason] = None
    adjournment_duration: Optional[str] = None  # e.g., "30 minutes", "next day"


@dataclass
class SidebarConference:
    """Record of a sidebar conference."""
    conference_id: str
    request: SidebarRequest
    outcome: SidebarOutcome
    judge_remarks: str
    conditions: List[str] = field(default_factory=list)  # Any conditions attached
    score_impact: float = 0.0
    confidence_impact: float = 0.0
    opponent_reaction: Optional[str] = None
    turn_cost: int = 1


@dataclass
class SettlementOffer:
    """A settlement offer made during sidebar."""
    offer_id: str
    offering_side: PlayerSide
    turn_number: int
    terms: str
    amount: Optional[float] = None  # For monetary settlements
    conditions: List[str] = field(default_factory=list)
    is_accepted: bool = False
    is_rejected: bool = False
    is_countered: bool = False
    counter_terms: Optional[str] = None


@dataclass
class SidebarState:
    """
    Tracks sidebar/chamber conference state throughout the trial.
    """
    # Conference limits
    max_sidebars_per_phase: int = 2
    sidebars_this_phase: int = 0
    total_sidebars: int = 0

    # Conference history
    conferences: List[SidebarConference] = field(default_factory=list)
    pending_request: Optional[SidebarRequest] = None

    # Settlement tracking
    settlement_offers: List[SettlementOffer] = field(default_factory=list)
    settlement_reached: bool = False
    settlement_terms: Optional[str] = None

    # Adjournment tracking
    adjournments_requested: int = 0
    adjournments_granted: int = 0
    current_adjournment: bool = False

    # Evidence exclusion tracking
    evidence_exclusion_requests: int = 0
    evidence_exclusions_granted: int = 0

    # Judge patience with sidebars
    judge_sidebar_patience: float = 100.0  # Decreases with each sidebar

    @property
    def can_request_sidebar(self) -> bool:
        """Check if player can request another sidebar this phase."""
        return self.sidebars_this_phase < self.max_sidebars_per_phase

    @property
    def sidebars_remaining(self) -> int:
        """Get number of sidebar requests remaining this phase."""
        return max(0, self.max_sidebars_per_phase - self.sidebars_this_phase)


# Sidebar request descriptions for UI
SIDEBAR_REQUEST_OPTIONS = {
    SidebarRequestType.EXCLUDE_EVIDENCE: {
        "title": "Request Evidence Exclusion",
        "description": "Ask the judge to exclude prejudicial or inadmissible evidence",
        "icon": "🚫",
        "turn_cost": 1,
        "requires_evidence": True
    },
    SidebarRequestType.WITNESS_AVAILABILITY: {
        "title": "Discuss Witness Issues",
        "description": "Address witness availability, protection, or scheduling concerns",
        "icon": "👤",
        "turn_cost": 1,
        "requires_witness": False
    },
    SidebarRequestType.REQUEST_ADJOURNMENT: {
        "title": "Request Adjournment",
        "description": "Ask for a recess or postponement of proceedings",
        "icon": "⏸️",
        "turn_cost": 1,
        "requires_reason": True
    },
    SidebarRequestType.SETTLEMENT_DISCUSSION: {
        "title": "Settlement Discussion",
        "description": "Initiate or discuss settlement terms privately",
        "icon": "🤝",
        "turn_cost": 2,
        "strategic": True
    },
    SidebarRequestType.PROCEDURAL_CLARIFICATION: {
        "title": "Procedural Clarification",
        "description": "Seek clarification on court procedures or rulings",
        "icon": "❓",
        "turn_cost": 1,
        "always_available": True
    },
    SidebarRequestType.MISTRIAL_MOTION: {
        "title": "Motion for Mistrial",
        "description": "Request mistrial due to prejudicial error or misconduct",
        "icon": "⚠️",
        "turn_cost": 2,
        "serious": True
    }
}

# Judge responses to sidebar requests
SIDEBAR_JUDGE_RESPONSES = {
    "grant": [
        "The court grants counsel's request. Let us proceed off the record.",
        "Very well, Counsel. The court will hear you at sidebar.",
        "Approach the bench. The court notes counsel's request.",
        "The request is granted. Both counsel, please approach.",
    ],
    "deny": [
        "The court denies the request. Please continue with proceedings.",
        "Counsel, this matter does not warrant a sidebar. Proceed.",
        "The request is denied. The court sees no merit in this application.",
        "I'm not inclined to grant this request. Let us continue.",
    ],
    "partial": [
        "The court will partially accommodate counsel's request.",
        "I will grant a limited sidebar to address the specific issue.",
        "Very well, but let us be brief. The court has limited patience.",
    ],
    "impatient": [
        "Counsel, this is your second sidebar request. The court's patience wears thin.",
        "Another sidebar? The court expects advocates to handle matters in open court.",
        "I trust this will be counsel's final request for private conference today.",
    ],
    "settlement": [
        "The court encourages parties to explore settlement. Please discuss.",
        "A settlement would serve the interests of justice. Proceed with discussions.",
        "The court will grant time for settlement talks. Use it wisely.",
    ],
    "adjournment_grant": [
        "The court grants a brief adjournment. We shall reconvene shortly.",
        "Very well, the court is adjourned for the requested period.",
        "Granted. The court expects counsel to be ready when we resume.",
    ],
    "adjournment_deny": [
        "The request for adjournment is denied. We must proceed.",
        "The court cannot grant further delay. Continue with your case.",
        "Time is of the essence. The request is denied.",
    ],
    "evidence_exclusion_grant": [
        "The court will exclude the contested evidence. So ordered.",
        "Upon consideration, the evidence shall be excluded from the record.",
        "The objection is sustained. The evidence is excluded.",
    ],
    "evidence_exclusion_deny": [
        "The evidence is admissible. The request is denied.",
        "The court finds no grounds for exclusion. The evidence stands.",
        "Denied. The evidence meets the threshold for admissibility.",
    ],
}

# Adjournment durations
ADJOURNMENT_DURATIONS = {
    "brief": ("15 minutes", 0.5),  # (display text, turn cost multiplier)
    "short": ("30 minutes", 1.0),
    "lunch": ("1 hour", 1.5),
    "extended": ("2 hours", 2.0),
    "next_day": ("Next day", 3.0),
}


# ============================================================================
# EDUCATIONAL FEATURES - LEGAL PRINCIPLE FLASHCARDS
# ============================================================================

class MistakeCategory(str, Enum):
    """Categories of common legal mistakes."""
    LEADING_QUESTION = "leading_question"
    HEARSAY = "hearsay"
    RELEVANCE = "relevance"
    SPECULATION = "speculation"
    ARGUMENTATIVE = "argumentative"
    COMPOUND_QUESTION = "compound_question"
    BADGERING = "badgering"
    ASSUMES_FACTS = "assumes_facts"
    IMPROPER_FOUNDATION = "improper_foundation"
    BEST_EVIDENCE = "best_evidence"
    CHARACTER_EVIDENCE = "character_evidence"
    PRIVILEGED_INFO = "privileged_info"
    IMPROPER_IMPEACHMENT = "improper_impeachment"
    PROCEDURE_ERROR = "procedure_error"
    ETIQUETTE_VIOLATION = "etiquette_violation"
    EVIDENCE_HANDLING = "evidence_handling"


class LegalPrincipleLevel(str, Enum):
    """Difficulty/complexity level of legal principle."""
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


@dataclass
class LegalPrinciple:
    """A legal principle that can be taught through flashcards."""
    principle_id: str
    title: str
    category: MistakeCategory
    level: LegalPrincipleLevel
    legal_section: str  # e.g., "Section 142, Evidence Act"
    explanation: str  # Full explanation of the principle
    short_rule: str  # One-line rule summary
    example_wrong: str  # Example of wrong usage
    example_correct: str  # Example of correct usage
    tip: str  # Practical tip for the player
    related_principles: List[str] = field(default_factory=list)  # IDs of related principles


@dataclass
class LearningMoment:
    """A learning moment triggered by a player mistake."""
    moment_id: str
    turn_number: int
    mistake_category: MistakeCategory
    principle: LegalPrinciple
    player_action: str  # What the player did wrong
    context: str  # Context of the mistake
    was_reviewed: bool = False
    was_helpful: bool = False  # Player feedback


@dataclass
class EducationProgress:
    """Tracks player's learning progress."""
    principles_learned: List[str] = field(default_factory=list)  # Principle IDs player has seen
    principles_mastered: List[str] = field(default_factory=list)  # Correct 3+ times after learning
    mistakes_made: Dict[str, int] = field(default_factory=dict)  # Category -> count
    learning_moments: List[LearningMoment] = field(default_factory=list)
    flashcards_viewed: int = 0
    correct_after_learning: int = 0  # Correct applications after seeing flashcard
    learning_streak: int = 0  # Consecutive correct applications
    total_mistakes: int = 0
    quiz_score: float = 0.0  # Optional end-of-game quiz


# Comprehensive Legal Principles Database
LEGAL_PRINCIPLES_DATABASE = {
    # Leading Questions
    "leading_examination": LegalPrinciple(
        principle_id="leading_examination",
        title="Leading Questions in Examination-in-Chief",
        category=MistakeCategory.LEADING_QUESTION,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Section 142, Indian Evidence Act",
        explanation=(
            "A leading question is one that suggests the answer within the question itself. "
            "In examination-in-chief (questioning your own witness), leading questions are "
            "generally not allowed because the witness might simply agree with whatever you suggest. "
            "The purpose is to get the witness's own recollection, not counsel's version of events."
        ),
        short_rule="Don't suggest answers when questioning your own witness.",
        example_wrong="Isn't it true that the defendant was driving at 80 km/h?",
        example_correct="What speed was the vehicle traveling?",
        tip="Use open-ended questions starting with What, When, Where, How, or Who.",
        related_principles=["leading_cross", "hostile_witness"]
    ),

    "leading_cross": LegalPrinciple(
        principle_id="leading_cross",
        title="Leading Questions in Cross-Examination",
        category=MistakeCategory.LEADING_QUESTION,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Section 143, Indian Evidence Act",
        explanation=(
            "Unlike examination-in-chief, leading questions ARE permitted in cross-examination. "
            "This is because the witness is adverse to your client's interests, and you need to "
            "control the narrative and test the witness's credibility. You can suggest facts and "
            "challenge the witness's version of events."
        ),
        short_rule="Leading questions are ALLOWED in cross-examination.",
        example_wrong="What did you see that day?",
        example_correct="You didn't actually see the accident happen, did you?",
        tip="In cross-examination, control the witness with yes/no questions.",
        related_principles=["leading_examination", "impeachment"]
    ),

    # Hearsay
    "hearsay_basic": LegalPrinciple(
        principle_id="hearsay_basic",
        title="Hearsay Evidence",
        category=MistakeCategory.HEARSAY,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="Section 60, Indian Evidence Act",
        explanation=(
            "Hearsay is an out-of-court statement offered to prove the truth of the matter asserted. "
            "If a witness says 'Ram told me that he saw the accident,' this is hearsay because the "
            "witness has no direct knowledge - they're repeating what someone else said. The problem "
            "is that Ram cannot be cross-examined about his statement."
        ),
        short_rule="A witness can only testify to facts they personally perceived.",
        example_wrong="What did your neighbor tell you about the incident?",
        example_correct="What did you personally see or hear that day?",
        tip="Ask: Is the witness testifying about their own perception or someone else's statement?",
        related_principles=["hearsay_exceptions", "res_gestae"]
    ),

    "hearsay_exceptions": LegalPrinciple(
        principle_id="hearsay_exceptions",
        title="Exceptions to Hearsay Rule",
        category=MistakeCategory.HEARSAY,
        level=LegalPrincipleLevel.ADVANCED,
        legal_section="Sections 32-39, Indian Evidence Act",
        explanation=(
            "Certain hearsay statements are admissible as exceptions: (1) Dying declarations - "
            "statements made by a person about to die regarding the cause of their death; "
            "(2) Statements against interest; (3) Statements in the course of business; "
            "(4) Statements about family relationships; (5) Res gestae - spontaneous statements "
            "made during or immediately after an event."
        ),
        short_rule="Some hearsay is admissible under recognized exceptions.",
        example_wrong="Objecting to all out-of-court statements without considering exceptions",
        example_correct="This statement qualifies as res gestae, made immediately after the event.",
        tip="Learn the hearsay exceptions - they can be powerful tools in your case.",
        related_principles=["hearsay_basic", "dying_declaration"]
    ),

    # Relevance
    "relevance_basic": LegalPrinciple(
        principle_id="relevance_basic",
        title="Relevance of Evidence",
        category=MistakeCategory.RELEVANCE,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Section 5, Indian Evidence Act",
        explanation=(
            "Evidence must be relevant to be admissible. Relevant facts are those connected to "
            "the facts in issue - they make a fact more or less probable. Evidence about unrelated "
            "matters wastes court time and may prejudice the tribunal. Always establish how the "
            "evidence connects to an issue the court must decide."
        ),
        short_rule="Only relevant facts are admissible as evidence.",
        example_wrong="What is the defendant's opinion about climate change?",
        example_correct="Were you present at the scene of the accident?",
        tip="Before asking, consider: Does this help prove or disprove a fact in issue?",
        related_principles=["character_evidence", "similar_fact"]
    ),

    # Speculation
    "speculation_witness": LegalPrinciple(
        principle_id="speculation_witness",
        title="Witness Speculation",
        category=MistakeCategory.SPECULATION,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Section 60, Indian Evidence Act",
        explanation=(
            "Witnesses can only testify to facts they know - not guesses, theories, or speculation. "
            "If a witness didn't see something happen, they cannot speculate about what might have "
            "happened. Only expert witnesses can give opinion testimony, and only within their "
            "area of expertise."
        ),
        short_rule="Witnesses testify to facts, not speculation or guesses.",
        example_wrong="What do you think the driver was trying to do?",
        example_correct="What did you observe the driver do?",
        tip="If a witness says 'I think' or 'maybe,' that's speculation. Stick to observations.",
        related_principles=["expert_opinion", "lay_opinion"]
    ),

    # Argumentative
    "argumentative_question": LegalPrinciple(
        principle_id="argumentative_question",
        title="Argumentative Questions",
        category=MistakeCategory.ARGUMENTATIVE,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="General Procedural Law",
        explanation=(
            "An argumentative question is one that argues counsel's case rather than seeking facts. "
            "It's essentially making a closing argument disguised as a question. Questions should "
            "elicit facts from the witness, not make arguments to the judge. Save your arguments "
            "for closing submissions."
        ),
        short_rule="Questions should seek facts, not argue your case.",
        example_wrong="Don't you think a reasonable person would have stopped?",
        example_correct="Did the driver apply the brakes before the collision?",
        tip="If your question sounds like a statement from your closing argument, rephrase it.",
        related_principles=["compound_question", "badgering"]
    ),

    # Compound Questions
    "compound_question": LegalPrinciple(
        principle_id="compound_question",
        title="Compound Questions",
        category=MistakeCategory.COMPOUND_QUESTION,
        level=LegalPrincipleLevel.BASIC,
        legal_section="General Procedural Law",
        explanation=(
            "A compound question combines multiple questions into one, making it unclear which "
            "part the witness is answering. This creates confusion in the record and is unfair "
            "to the witness. Each question should address one fact at a time."
        ),
        short_rule="Ask one question at a time.",
        example_wrong="Did you see the car and was it speeding and did you call the police?",
        example_correct="Did you see the car? [wait] Was it speeding? [wait] Did you call police?",
        tip="If your question has 'and' connecting different topics, split it into separate questions.",
        related_principles=["argumentative_question"]
    ),

    # Badgering
    "badgering_witness": LegalPrinciple(
        principle_id="badgering_witness",
        title="Badgering the Witness",
        category=MistakeCategory.BADGERING,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="Section 151, Indian Evidence Act",
        explanation=(
            "Badgering means harassing or intimidating a witness through repetitive, aggressive, "
            "or hostile questioning. While firm cross-examination is allowed, counsel must not "
            "bully witnesses. Repeatedly asking the same question after receiving an answer, "
            "or being unnecessarily rude, constitutes badgering."
        ),
        short_rule="Vigorous cross-examination is allowed; harassment is not.",
        example_wrong="I'll ask you again - didn't you lie? Didn't you? Answer me!",
        example_correct="Your earlier statement was different. Can you explain the discrepancy?",
        tip="If the witness has answered, move on. Repetition looks desperate.",
        related_principles=["hostile_witness", "impeachment"]
    ),

    # Assumes Facts Not in Evidence
    "assumes_facts": LegalPrinciple(
        principle_id="assumes_facts",
        title="Assuming Facts Not in Evidence",
        category=MistakeCategory.ASSUMES_FACTS,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="General Procedural Law",
        explanation=(
            "A question assumes facts not in evidence when it presupposes something that hasn't "
            "been proven or testified to. The classic example is 'When did you stop beating your wife?' "
            "which assumes the person was beating their wife. Such questions are unfair because "
            "any answer seems to confirm the assumed fact."
        ),
        short_rule="Don't assume facts that haven't been established.",
        example_wrong="When you fled the scene, where did you go? (assuming they fled)",
        example_correct="Did you leave the scene? [if yes] Where did you go?",
        tip="Establish the foundational facts before building on them.",
        related_principles=["improper_foundation", "leading_examination"]
    ),

    # Improper Foundation
    "improper_foundation": LegalPrinciple(
        principle_id="improper_foundation",
        title="Lack of Proper Foundation",
        category=MistakeCategory.IMPROPER_FOUNDATION,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="Section 60-65, Indian Evidence Act",
        explanation=(
            "Before certain evidence can be admitted, you must establish a proper foundation - "
            "basic facts showing the evidence is what you claim it is. For documents, you must "
            "show authenticity. For physical evidence, you must establish chain of custody. "
            "For expert opinion, you must qualify the expert."
        ),
        short_rule="Establish authenticity and relevance before admitting evidence.",
        example_wrong="I'd like to show the witness this document. [without authentication]",
        example_correct="Do you recognize this document? Is that your signature? Can you identify it?",
        tip="Always authenticate documents through a witness who can identify them.",
        related_principles=["best_evidence", "chain_custody"]
    ),

    # Best Evidence Rule
    "best_evidence": LegalPrinciple(
        principle_id="best_evidence",
        title="Best Evidence Rule",
        category=MistakeCategory.BEST_EVIDENCE,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="Section 64-65, Indian Evidence Act",
        explanation=(
            "When the contents of a document are in issue, the original document must be produced "
            "(the 'best evidence'). Secondary evidence (copies, oral accounts of contents) is only "
            "admissible if the original is lost, destroyed, or otherwise unavailable, and this "
            "must be established first."
        ),
        short_rule="Produce original documents; copies require justification.",
        example_wrong="Let me tell you what the contract says...",
        example_correct="I present the original contract, marked as Exhibit P-1.",
        tip="Always try to get original documents. If unavailable, explain why to the court.",
        related_principles=["improper_foundation", "secondary_evidence"]
    ),

    # Character Evidence
    "character_evidence": LegalPrinciple(
        principle_id="character_evidence",
        title="Character Evidence",
        category=MistakeCategory.CHARACTER_EVIDENCE,
        level=LegalPrincipleLevel.ADVANCED,
        legal_section="Sections 52-55, Indian Evidence Act",
        explanation=(
            "Generally, evidence of a person's character is not admissible to prove they acted "
            "in conformity with that character on a particular occasion. However, character "
            "evidence may be relevant for damages, in defamation cases, or when character "
            "itself is in issue. In criminal cases, the accused may present good character."
        ),
        short_rule="Character evidence is generally inadmissible to prove conduct.",
        example_wrong="The defendant has a history of reckless behavior, so he was reckless here.",
        example_correct="On this specific occasion, what actions did you observe the defendant take?",
        tip="Focus on what happened in this case, not the person's general reputation.",
        related_principles=["relevance_basic", "similar_fact"]
    ),

    # Privileged Information
    "privileged_info": LegalPrinciple(
        principle_id="privileged_info",
        title="Privileged Communications",
        category=MistakeCategory.PRIVILEGED_INFO,
        level=LegalPrincipleLevel.ADVANCED,
        legal_section="Sections 126-129, Indian Evidence Act",
        explanation=(
            "Certain communications are privileged and cannot be disclosed without consent: "
            "(1) Attorney-client communications; (2) Spousal communications during marriage; "
            "(3) Official communications; (4) Communications during mediation. Attempting to "
            "elicit privileged information is improper."
        ),
        short_rule="Some communications are protected from disclosure.",
        example_wrong="What did your lawyer advise you to say?",
        example_correct="What is your understanding of the agreement, in your own words?",
        tip="Respect privileges. Ask about facts, not legal advice received.",
        related_principles=["attorney_client", "spousal_privilege"]
    ),

    # Impeachment
    "impeachment": LegalPrinciple(
        principle_id="impeachment",
        title="Proper Impeachment of Witness",
        category=MistakeCategory.IMPROPER_IMPEACHMENT,
        level=LegalPrincipleLevel.INTERMEDIATE,
        legal_section="Section 145, Indian Evidence Act",
        explanation=(
            "To impeach (discredit) a witness using their prior inconsistent statement, you must "
            "first draw the witness's attention to the relevant parts of the statement. You cannot "
            "simply produce a prior statement without giving the witness a chance to explain the "
            "inconsistency. This is called 'laying the foundation' for impeachment."
        ),
        short_rule="Confront the witness with prior statement before using it.",
        example_wrong="Your Honor, I have a prior statement that contradicts the witness.",
        example_correct="Witness, I direct your attention to your police statement dated... Did you say...?",
        tip="Read the exact prior statement to the witness and ask them to explain the difference.",
        related_principles=["prior_statement", "credibility"]
    ),

    # Procedure - Addressing the Court
    "addressing_court": LegalPrinciple(
        principle_id="addressing_court",
        title="Properly Addressing the Court",
        category=MistakeCategory.ETIQUETTE_VIOLATION,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Court Procedure & Etiquette",
        explanation=(
            "In Indian courts, the judge is addressed as 'My Lord' (High Court/Supreme Court) or "
            "'Your Honour' (District Courts). Always stand when addressing the court. Begin "
            "submissions with 'May it please the court' and end with 'I humbly submit.' "
            "Never interrupt the judge or opposing counsel."
        ),
        short_rule="Address the court with proper respect and formality.",
        example_wrong="Hey Judge, I think...",
        example_correct="My Lord, may it please the court, I humbly submit that...",
        tip="When in doubt, more formality is better. Respect earns the court's attention.",
        related_principles=["court_decorum", "proper_attire"]
    ),

    # Evidence Handling
    "evidence_marking": LegalPrinciple(
        principle_id="evidence_marking",
        title="Marking and Admitting Evidence",
        category=MistakeCategory.EVIDENCE_HANDLING,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Civil/Criminal Procedure",
        explanation=(
            "Documents must be marked for identification before they can be admitted into evidence. "
            "First, have the document marked (e.g., 'Exhibit P-1 for identification'). Then, "
            "establish foundation through a witness who can authenticate it. Finally, move to "
            "admit the document into evidence. The judge rules on admissibility."
        ),
        short_rule="Mark → Authenticate → Move to Admit → Get Ruling",
        example_wrong="I want to show this document to the court.",
        example_correct="I request this document be marked as Exhibit P-1. May I show it to the witness?",
        tip="Follow the formal procedure: mark, authenticate, then move for admission.",
        related_principles=["improper_foundation", "best_evidence"]
    ),

    # Examination Order
    "examination_order": LegalPrinciple(
        principle_id="examination_order",
        title="Order of Witness Examination",
        category=MistakeCategory.PROCEDURE_ERROR,
        level=LegalPrincipleLevel.BASIC,
        legal_section="Section 137-138, Indian Evidence Act",
        explanation=(
            "Witness examination follows a specific order: (1) Examination-in-chief by the party "
            "calling the witness; (2) Cross-examination by the opposing party; (3) Re-examination "
            "by the calling party (limited to matters raised in cross). Re-examination cannot "
            "introduce new matters without court permission."
        ),
        short_rule="Chief → Cross → Re-examination (limited to cross topics)",
        example_wrong="In re-examination, let me ask about something completely new.",
        example_correct="In re-examination: You were asked about X in cross. Can you clarify?",
        tip="Re-examination is only to clarify issues raised in cross-examination.",
        related_principles=["leading_examination", "leading_cross"]
    ),

    # Res Gestae
    "res_gestae": LegalPrinciple(
        principle_id="res_gestae",
        title="Res Gestae - Spontaneous Statements",
        category=MistakeCategory.HEARSAY,
        level=LegalPrincipleLevel.ADVANCED,
        legal_section="Section 6, Indian Evidence Act",
        explanation=(
            "Res gestae (things done) refers to statements made so closely connected to an event "
            "that they form part of the transaction itself. These spontaneous utterances are "
            "admissible because there's no time for fabrication. The statement must be "
            "contemporaneous with the act and explain or characterize it."
        ),
        short_rule="Spontaneous statements during an event are admissible.",
        example_wrong="What did she say three days after the accident?",
        example_correct="What did she exclaim immediately upon seeing the collision?",
        tip="Res gestae requires the statement to be part of the event, not a later narrative.",
        related_principles=["hearsay_basic", "hearsay_exceptions"]
    ),

    # Dying Declaration
    "dying_declaration": LegalPrinciple(
        principle_id="dying_declaration",
        title="Dying Declaration",
        category=MistakeCategory.HEARSAY,
        level=LegalPrincipleLevel.ADVANCED,
        legal_section="Section 32(1), Indian Evidence Act",
        explanation=(
            "A dying declaration is a statement made by a person about the cause of their death "
            "or the circumstances of the transaction resulting in their death, when they believe "
            "death is imminent. Such statements are admissible because a dying person is "
            "presumed to speak the truth. The declarant must be in a fit mental state."
        ),
        short_rule="Statements about cause of death by a dying person are admissible.",
        example_wrong="The dying declaration is hearsay and inadmissible.",
        example_correct="This dying declaration is admissible under Section 32(1) of the Evidence Act.",
        tip="Establish that the person had apprehension of death when making the statement.",
        related_principles=["hearsay_exceptions", "res_gestae"]
    ),
}

# Mistake detection patterns (simplified regex-like patterns for demonstration)
MISTAKE_PATTERNS = {
    MistakeCategory.LEADING_QUESTION: [
        r"isn't it true",
        r"wouldn't you agree",
        r"don't you think",
        r"isn't that correct",
        r"you did .* didn't you",
        r"it's true that",
        r"you saw .* right",
        r"correct\?$",
    ],
    MistakeCategory.HEARSAY: [
        r"what did .* tell you",
        r"what did .* say",
        r"someone told",
        r"i heard that",
        r"they said",
        r"according to",
    ],
    MistakeCategory.SPECULATION: [
        r"what do you think",
        r"in your opinion",
        r"would you guess",
        r"what might have",
        r"probably",
        r"maybe .* happened",
    ],
    MistakeCategory.COMPOUND_QUESTION: [
        r".* and .* and .*\?",
        r"did you .* and did you",
    ],
    MistakeCategory.ARGUMENTATIVE: [
        r"don't you think .* should",
        r"any reasonable person would",
        r"obviously",
        r"clearly you",
    ],
    MistakeCategory.ASSUMES_FACTS: [
        r"when you .* why did you",
        r"after you .* what happened",
        r"since you .*",
    ],
}


@dataclass
class EducationState:
    """
    Tracks educational features state.
    """
    progress: EducationProgress = field(default_factory=EducationProgress)
    education_enabled: bool = True
    show_flashcards: bool = True
    pending_flashcard: Optional[LearningMoment] = None
    flashcards_shown_this_session: int = 0
    max_flashcards_per_session: int = 10  # Don't overwhelm the player


# ========================================
# POST-GAME ANALYSIS SYSTEM
# ========================================

class TurningPointType(str, Enum):
    """Types of turning points in a trial."""
    WITNESS_CONTRADICTION = "witness_contradiction"
    EVIDENCE_ADMITTED = "evidence_admitted"
    EVIDENCE_EXCLUDED = "evidence_excluded"
    OBJECTION_SUSTAINED = "objection_sustained"
    OBJECTION_OVERRULED = "objection_overruled"
    WITNESS_BREAKDOWN = "witness_breakdown"
    WITNESS_HOSTILE = "witness_hostile"
    JUDGE_WARNING = "judge_warning"
    JUDGE_PRAISE = "judge_praise"
    SUCCESSFUL_IMPEACHMENT = "successful_impeachment"
    FAILED_IMPEACHMENT = "failed_impeachment"
    KEY_ADMISSION = "key_admission"
    SETTLEMENT_OFFERED = "settlement_offered"
    RESEARCH_CITED = "research_cited"
    CONFIDENCE_PEAK = "confidence_peak"
    CONFIDENCE_LOW = "confidence_low"
    ETIQUETTE_VIOLATION = "etiquette_violation"
    STRATEGIC_MOVE = "strategic_move"


class AnalysisCategory(str, Enum):
    """Categories for analysis."""
    OPENING_STATEMENT = "opening_statement"
    WITNESS_EXAMINATION = "witness_examination"
    CROSS_EXAMINATION = "cross_examination"
    EVIDENCE_HANDLING = "evidence_handling"
    OBJECTIONS = "objections"
    LEGAL_ARGUMENTS = "legal_arguments"
    COURT_ETIQUETTE = "court_etiquette"
    TIME_MANAGEMENT = "time_management"
    JUDGE_RELATIONS = "judge_relations"
    CLOSING_ARGUMENT = "closing_argument"


@dataclass
class TurningPoint:
    """A key moment that impacted the case outcome."""
    turn_number: int
    point_type: TurningPointType
    description: str
    impact: str  # How it affected the case
    impact_score: int  # -10 to +10, how much it helped/hurt
    phase: str
    involved_witness: Optional[str] = None
    involved_evidence: Optional[str] = None
    player_action: Optional[str] = None


@dataclass
class StrengthWeakness:
    """A strength or weakness identified in player's performance."""
    category: AnalysisCategory
    is_strength: bool
    title: str
    description: str
    examples: List[str] = field(default_factory=list)  # Specific examples from the game
    improvement_tip: Optional[str] = None  # For weaknesses
    score_impact: int = 0  # How much it affected final score


@dataclass
class MissedOpportunity:
    """An opportunity the player missed during the trial."""
    turn_number: int
    phase: str
    description: str
    what_could_have_been_done: str
    potential_impact: str
    category: AnalysisCategory


@dataclass
class AIRecommendation:
    """AI-generated recommendation for improvement."""
    category: AnalysisCategory
    priority: int  # 1 = highest priority
    title: str
    recommendation: str
    rationale: str
    related_principles: List[str] = field(default_factory=list)


@dataclass
class GameAnalysis:
    """Complete post-game analysis."""
    # Overall assessment
    overall_grade: str  # A, B, C, D, F
    overall_summary: str
    verdict_prediction_accuracy: float  # How well player performed vs expected outcome

    # Strengths and weaknesses
    strengths: List[StrengthWeakness] = field(default_factory=list)
    weaknesses: List[StrengthWeakness] = field(default_factory=list)

    # Key moments
    turning_points: List[TurningPoint] = field(default_factory=list)
    missed_opportunities: List[MissedOpportunity] = field(default_factory=list)

    # Recommendations
    recommendations: List[AIRecommendation] = field(default_factory=list)

    # Category scores
    category_scores: Dict[str, int] = field(default_factory=dict)

    # Statistics
    total_turns: int = 0
    effective_actions: int = 0
    ineffective_actions: int = 0
    neutral_actions: int = 0

    # Comparison to "ideal" play
    optimal_score_estimate: int = 0
    actual_score: int = 0
    score_percentage: float = 0.0


@dataclass
class GameEventLog:
    """Tracks important events during gameplay for later analysis."""
    turn_number: int
    phase: str
    event_type: str
    description: str
    outcome: str
    score_change: int = 0
    player_action: Optional[str] = None
    ai_response: Optional[str] = None
    witness_involved: Optional[str] = None
    evidence_involved: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AnalysisState:
    """Tracks data needed for post-game analysis."""
    event_log: List[GameEventLog] = field(default_factory=list)
    turning_points: List[TurningPoint] = field(default_factory=list)

    # Category tracking
    opening_statement_delivered: bool = False
    opening_statement_quality: int = 50  # 0-100
    closing_argument_delivered: bool = False
    closing_argument_quality: int = 50

    # Witness examination tracking
    witnesses_examined: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cross_examinations: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # Evidence tracking
    evidence_presented_successfully: List[str] = field(default_factory=list)
    evidence_excluded: List[str] = field(default_factory=list)
    evidence_challenged: List[str] = field(default_factory=list)

    # Objection tracking
    objection_history: List[Dict[str, Any]] = field(default_factory=list)

    # Judge interaction tracking
    judge_praise_count: int = 0
    judge_criticism_count: int = 0
    judge_patience_history: List[int] = field(default_factory=list)

    # Timing tracking
    rushed_responses: int = 0
    slow_responses: int = 0
    timed_out_responses: int = 0

    # Confidence tracking
    confidence_peaks: List[Dict[str, Any]] = field(default_factory=list)
    confidence_lows: List[Dict[str, Any]] = field(default_factory=list)

    # Missed opportunities (detected during play)
    potential_missed_opportunities: List[Dict[str, Any]] = field(default_factory=list)

    # Research and citations
    cases_cited: List[str] = field(default_factory=list)
    research_effectiveness: Dict[str, bool] = field(default_factory=dict)


@dataclass
class GameState:
    """Current state of the game."""
    phase: GamePhase = GamePhase.SETUP
    turn_number: int = 0
    phase_turn_number: int = 0  # Turns within current phase
    current_witness: Optional[OralWitness] = None
    current_witness_index: int = 0
    current_issue_index: int = 0
    player_side: Optional[PlayerSide] = None
    is_player_turn: bool = True
    messages: List[AgentMessage] = field(default_factory=list)
    events_occurred: List[DynamicEvent] = field(default_factory=list)
    evidence_presented: List[str] = field(default_factory=list)
    objections_made: int = 0
    objections_sustained: int = 0
    warnings_received: int = 0
    judge_warnings_in_phase: int = 0  # Warnings given by judge in current phase
    extension_granted: bool = False  # Whether judge granted time extension
    score: GameScore = field(default_factory=GameScore)
    game_log: List[Dict[str, Any]] = field(default_factory=list)

    # Court Etiquette Tracking
    etiquette_violations: List[Dict[str, Any]] = field(default_factory=list)
    etiquette_warnings: int = 0  # Number of etiquette warnings from Judge
    is_first_action_in_phase: bool = True  # Track if this is first action in phase
    proper_decorum_streak: int = 0  # Consecutive actions with good etiquette

    # Evidence Management
    evidence_locker: EvidenceLocker = field(default_factory=EvidenceLocker)
    pending_evidence_ruling: Optional[str] = None  # Evidence ID awaiting Judge ruling
    evidence_objections_made: int = 0
    evidence_objections_sustained: int = 0

    # Witness Credibility System
    witness_states: Dict[str, WitnessState] = field(default_factory=dict)  # witness_id -> WitnessState
    current_witness_state: Optional[WitnessState] = None
    witness_credibility_revealed: Dict[str, float] = field(default_factory=dict)  # How much player knows about each witness
    total_contradictions_caught: int = 0
    witnesses_turned_hostile: int = 0
    witness_breakdowns: int = 0

    # Judge Personality System
    judge_state: Optional[JudgeState] = None
    judge_interruptions: int = 0
    judge_questions_to_player: int = 0
    player_adaptation_score: float = 50.0  # How well player adapts to judge's style

    # Pre-Trial Preparation System
    preparation_state: Optional[PreparationState] = None
    preparation_completed: bool = False
    preparation_bonuses_applied: bool = False

    # Real-Time Pressure System
    time_pressure_state: Optional[TimePressureState] = None
    confidence_meter: Optional[ConfidenceMeter] = None
    pressure_enabled: bool = True  # Can be disabled for accessibility
    last_response_stats: Optional[ResponseTimingStats] = None
    judge_time_prompts_given: int = 0
    rushed_answer_penalties: int = 0
    confidence_bonuses_earned: int = 0

    # Legal Research Mid-Trial System
    legal_research_state: Optional[LegalResearchState] = None
    research_enabled: bool = True
    last_research_result: Optional[ResearchSession] = None
    pending_citation: Optional[CaseLawResult] = None  # Case selected but not yet cited

    # Sidebar/Chamber Conference System
    sidebar_state: Optional[SidebarState] = None
    sidebar_enabled: bool = True
    in_sidebar_conference: bool = False
    last_sidebar_result: Optional[SidebarConference] = None

    # Educational Features System
    education_state: Optional[EducationState] = None
    education_enabled: bool = True
    pending_learning_moment: Optional[LearningMoment] = None
    learning_moments_shown: List[LearningMoment] = field(default_factory=list)

    # Post-Game Analysis System
    analysis_state: Optional[AnalysisState] = None
    analysis_enabled: bool = True
    game_analysis: Optional[GameAnalysis] = None  # Generated after game ends


class DynamicEventGenerator:
    """Generates dynamic events during gameplay."""

    def __init__(self, case: CourtCase, difficulty: str = "medium"):
        self.case = case
        self.difficulty = difficulty
        self.event_probability = {
            "easy": 0.1,
            "medium": 0.2,
            "hard": 0.35
        }.get(difficulty, 0.2)

    def maybe_trigger_event(self, phase: GamePhase, state: GameState) -> Optional[DynamicEvent]:
        """Possibly trigger a dynamic event based on game state."""
        if random.random() > self.event_probability:
            return None

        # Select appropriate events for current phase
        possible_events = self._get_phase_events(phase, state)
        if not possible_events:
            return None

        return random.choice(possible_events)

    def _get_phase_events(self, phase: GamePhase, state: GameState) -> List[DynamicEvent]:
        """Get possible events for current phase."""
        events = []

        if phase in [GamePhase.PETITIONER_WITNESS_EXAM, GamePhase.RESPONDENT_WITNESS_EXAM]:
            events.extend([
                DynamicEvent(
                    event_type=DynamicEventType.WITNESS_HOSTILE,
                    description="The witness becomes uncooperative and hostile!",
                    impact="Witness is now giving evasive answers",
                    requires_response=True,
                    response_options=[
                        "Request the court to declare witness hostile",
                        "Change questioning strategy",
                        "Request a brief recess"
                    ],
                    difficulty_modifier=0.2
                ),
                DynamicEvent(
                    event_type=DynamicEventType.NEW_FACT,
                    description="The witness reveals an unexpected fact during testimony!",
                    impact="A new angle has emerged in the case",
                    requires_response=True,
                    response_options=[
                        "Pursue this new line of questioning",
                        "Object and move to strike",
                        "Reserve for re-examination"
                    ]
                ),
                DynamicEvent(
                    event_type=DynamicEventType.WITNESS_RECANTS,
                    description="The witness contradicts their earlier affidavit!",
                    impact="Witness credibility is now in question",
                    requires_response=True,
                    response_options=[
                        "Highlight the contradiction immediately",
                        "Mark for final arguments",
                        "Request to confront with prior statement"
                    ]
                )
            ])

        if phase == GamePhase.CROSS_EXAMINATION:
            events.extend([
                DynamicEvent(
                    event_type=DynamicEventType.OPPOSING_OBJECTION,
                    description="Opposing counsel raises an objection!",
                    impact="Your question has been challenged",
                    requires_response=True,
                    response_options=[
                        "Rephrase the question",
                        "Argue against the objection",
                        "Withdraw the question"
                    ]
                ),
                DynamicEvent(
                    event_type=DynamicEventType.JUDGE_WARNING,
                    description="The judge warns you about your line of questioning!",
                    impact="Courtroom decorum affected",
                    requires_response=False,
                    difficulty_modifier=0.15
                )
            ])

        if phase in [GamePhase.PETITIONER_EVIDENCE, GamePhase.RESPONDENT_EVIDENCE]:
            events.extend([
                DynamicEvent(
                    event_type=DynamicEventType.NEW_EVIDENCE,
                    description="New documentary evidence has surfaced!",
                    impact="Additional evidence can be presented",
                    requires_response=True,
                    response_options=[
                        "Move to admit the new evidence",
                        "Object to late submission",
                        "Request time to examine"
                    ]
                ),
                DynamicEvent(
                    event_type=DynamicEventType.NEW_WITNESS,
                    description="A new witness has come forward with relevant testimony!",
                    impact="Potential new testimony available",
                    requires_response=True,
                    response_options=[
                        "Request to call the new witness",
                        "Object to surprise witness",
                        "Reserve right to recall later"
                    ]
                )
            ])

        # General events that can happen anytime
        if state.turn_number > 5 and random.random() < 0.1:
            events.append(DynamicEvent(
                event_type=DynamicEventType.CLIENT_PRESSURE,
                description="Your client is getting anxious about the proceedings!",
                impact="You need to reassure your client",
                requires_response=False
            ))

        return events


class CourtroomGame:
    """
    Main game class for the courtroom simulation.
    Handles player interactions, AI responses, and game flow.
    """

    def __init__(
        self,
        case: CourtCase,
        llm_provider: str = "openai",
        model_name: Optional[str] = None,
        difficulty: str = "medium"
    ):
        self.case = case
        self.llm_provider = llm_provider
        self.model_name = model_name
        self.difficulty = difficulty

        self.state = GameState()
        self.agents: Dict[str, Any] = {}
        self.event_generator = DynamicEventGenerator(case, difficulty)

        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],
            "phase_change": [],
            "event_triggered": [],
            "score_update": [],
            "game_over": []
        }

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler."""
        if event in self.event_handlers:
            self.event_handlers[event].append(handler)

    def _emit(self, event: str, data: Any) -> None:
        """Emit an event."""
        for handler in self.event_handlers.get(event, []):
            handler(data)

    def start_game(self, player_side: PlayerSide) -> Dict[str, Any]:
        """Initialize and start the game."""
        self.state.player_side = player_side
        self.state.phase = GamePhase.SETUP

        # Initialize AI agents
        self._initialize_agents()

        # Initialize evidence locker from case data
        self._initialize_evidence_locker()

        # Initialize witness credibility states
        self._initialize_witness_states()

        # Initialize judge personality
        self._initialize_judge_personality()

        # Initialize pressure system (time pressure and confidence meter)
        self.initialize_pressure_system()

        # Initialize legal research system
        self.initialize_legal_research()

        # Initialize sidebar/chamber conference system
        self.initialize_sidebar_system()

        # Apply preparation bonuses if preparation was completed
        if self.state.preparation_completed and not self.state.preparation_bonuses_applied:
            self.apply_preparation_bonuses()

        # Collect all opening messages
        opening_messages = []

        # 1. Clerk announces the case
        clerk_msg = self._clerk_announce_case()
        opening_messages.append(clerk_msg)
        self.state.messages.append(clerk_msg)

        # 2. Judge opens proceedings (with personality-influenced style)
        judge: JudgeAgent = self.agents['judge']
        judge_opening_text = self._get_judge_opening_statement()
        judge_opening = judge.respond(judge_opening_text, CourtPhase.OPENING)
        opening_messages.append(judge_opening)
        self.state.messages.append(judge_opening)

        self.state.phase = GamePhase.OPENING_STATEMENT

        # 3. If player is respondent, AI petitioner goes first
        if player_side == PlayerSide.RESPONDENT:
            # AI Petitioner makes opening statement
            opponent: LawyerAgent = self.agents['opponent']
            opponent_opening = opponent.make_opening_statement()
            opening_messages.append(opponent_opening)
            self.state.messages.append(opponent_opening)

            # Judge acknowledges and invites respondent
            judge_invite = judge.respond(
                "The court has heard the opening statement of the petitioner's counsel. "
                "Counsel for the respondent may now present their opening statement.",
                CourtPhase.OPENING
            )
            opening_messages.append(judge_invite)
            self.state.messages.append(judge_invite)

            self.state.is_player_turn = True
        else:
            # Player is petitioner, they go first
            self.state.is_player_turn = True

        return {
            "messages": opening_messages,
            "phase": self.state.phase,
            "is_player_turn": self.state.is_player_turn,
            "instructions": self._get_phase_instructions()
        }

    def _initialize_agents(self) -> None:
        """Initialize AI agents based on player's side."""
        base_agents = create_agents_from_case(
            self.case,
            llm_provider=self.llm_provider,
            model_name=self.model_name
        )

        self.agents['judge'] = base_agents['judge']
        self.agents['clerk'] = base_agents['clerk']
        self.agents['witnesses'] = base_agents['witnesses']

        # Store both counsel for proper courtroom flow
        self.agents['petitioner_counsel'] = base_agents['petitioner_counsel']
        self.agents['respondent_counsel'] = base_agents['respondent_counsel']

        # Set opponent counsel based on player's side
        if self.state.player_side == PlayerSide.PETITIONER:
            self.agents['opponent'] = base_agents['respondent_counsel']
            self.agents['opponent'].name = "Respondent's Counsel (AI)"
            self.agents['petitioner_counsel'].name = "You (Petitioner's Counsel)"
        else:
            self.agents['opponent'] = base_agents['petitioner_counsel']
            self.agents['opponent'].name = "Petitioner's Counsel (AI)"
            self.agents['respondent_counsel'].name = "You (Respondent's Counsel)"

        # Separate witnesses by type
        self.agents['petitioner_witnesses'] = [
            w for w in base_agents['witnesses']
            if w.witness_data.witness_type == WitnessType.PW
        ]
        self.agents['respondent_witnesses'] = [
            w for w in base_agents['witnesses']
            if w.witness_data.witness_type == WitnessType.RW
        ]

    def _initialize_evidence_locker(self) -> None:
        """Initialize evidence locker from case data."""
        locker = self.state.evidence_locker
        exhibit_num = 1

        # Extract documentary evidence from case
        if hasattr(self.case, 'evidence_details') and self.case.evidence_details:
            evidence_details = self.case.evidence_details

            # Documentary exhibits
            for doc in evidence_details.documentary_exhibits:
                # Determine category
                category = EvidenceCategory.DOCUMENTARY
                desc_lower = doc.description.lower() if doc.description else ""

                if any(w in desc_lower for w in ['medical', 'hospital', 'doctor', 'treatment']):
                    category = EvidenceCategory.MEDICAL_RECORDS
                elif any(w in desc_lower for w in ['photo', 'picture', 'video', 'cctv']):
                    category = EvidenceCategory.PHOTOGRAPHS
                elif any(w in desc_lower for w in ['fir', 'police', 'official', 'government']):
                    category = EvidenceCategory.OFFICIAL_RECORDS
                elif any(w in desc_lower for w in ['expert', 'valuation', 'assessment']):
                    category = EvidenceCategory.EXPERT_REPORTS

                # Determine owner side based on exhibit number
                owner = "petitioner" if doc.exhibit_number.upper().startswith(('P', 'EX-P')) else "respondent"

                item = EvidenceItem(
                    evidence_id=f"DOC_{exhibit_num}",
                    exhibit_number=doc.exhibit_number or f"Exhibit-{exhibit_num}",
                    title=doc.description[:50] if doc.description else f"Document {exhibit_num}",
                    description=doc.description or "Documentary evidence",
                    category=category,
                    owner_side=owner,
                    relevance_score=70.0  # Default relevance
                )

                if owner == "petitioner":
                    locker.petitioner_evidence.append(item)
                else:
                    locker.respondent_evidence.append(item)

                exhibit_num += 1

        # Add medical evidence if available
        if hasattr(self.case, 'medical_evidence') and self.case.medical_evidence:
            med = self.case.medical_evidence

            # Add treatment records from the treatments list
            if hasattr(med, 'treatments') and med.treatments:
                for i, treatment in enumerate(med.treatments):
                    hospital_name = getattr(treatment, 'hospital_name', None) or \
                                   getattr(treatment, 'facility_name', None) or \
                                   "Medical Facility"
                    item = EvidenceItem(
                        evidence_id=f"MED_{exhibit_num}",
                        exhibit_number=f"Exhibit P-{exhibit_num}",
                        title=f"Medical Treatment Record {i+1}",
                        description=f"Treatment records from {hospital_name}",
                        category=EvidenceCategory.MEDICAL_RECORDS,
                        owner_side="petitioner",
                        relevance_score=85.0
                    )
                    locker.petitioner_evidence.append(item)
                    exhibit_num += 1

            # Add disability certificates if available
            if hasattr(med, 'disability_certificates') and med.disability_certificates:
                for i, cert in enumerate(med.disability_certificates):
                    item = EvidenceItem(
                        evidence_id=f"DIS_{exhibit_num}",
                        exhibit_number=f"Exhibit P-{exhibit_num}",
                        title=f"Disability Certificate {i+1}",
                        description=f"Disability: {getattr(cert, 'disability_percentage', 'N/A')}%",
                        category=EvidenceCategory.MEDICAL_RECORDS,
                        owner_side="petitioner",
                        relevance_score=90.0
                    )
                    locker.petitioner_evidence.append(item)
                    exhibit_num += 1

        locker.current_exhibit_number = exhibit_num

    # ========================================
    # WITNESS CREDIBILITY SYSTEM
    # ========================================

    def _initialize_witness_states(self) -> None:
        """Initialize credibility stats for all witnesses in the case."""
        if not hasattr(self.case, 'evidence_details') or not self.case.evidence_details:
            return

        for witness in self.case.evidence_details.oral_witnesses:
            # Generate unique witness ID
            witness_id = f"{witness.witness_type.value}_{witness.witness_number}"

            # Base stats vary by witness type and characteristics
            base_credibility = self._calculate_base_credibility(witness)
            base_nervousness = self._calculate_base_nervousness(witness)
            base_hostility = self._calculate_base_hostility(witness)
            base_memory = self._calculate_base_memory(witness)

            stats = WitnessStats(
                credibility=base_credibility,
                nervousness=base_nervousness,
                hostility=base_hostility,
                memory_accuracy=base_memory,
                base_credibility=base_credibility,
                base_nervousness=base_nervousness,
                base_hostility=base_hostility,
                base_memory=base_memory,
                cooperation=70 + random.randint(-15, 15),
                composure=70 + random.randint(-20, 20),
                consistency=80 + random.randint(-10, 10)
            )
            stats.clamp_stats()

            witness_state = WitnessState(
                witness_id=witness_id,
                witness_name=witness.name,
                witness_type=witness.witness_type.value,
                stats=stats
            )

            self.state.witness_states[witness_id] = witness_state
            # Initially reveal only 20-40% of witness info
            self.state.witness_credibility_revealed[witness_id] = random.uniform(0.2, 0.4)

    def _calculate_base_credibility(self, witness: OralWitness) -> float:
        """Calculate base credibility based on witness characteristics."""
        credibility = 75.0  # Default

        # Check if witness might be an expert based on their role/name
        witness_name_lower = witness.name.lower() if witness.name else ""
        is_expert = any(term in witness_name_lower for term in
                       ['doctor', 'dr.', 'engineer', 'expert', 'specialist',
                        'professor', 'analyst', 'inspector', 'officer'])

        # Expert witnesses have higher base credibility
        if is_expert:
            credibility += 15

        # Court witnesses (CW) typically have moderate-high credibility
        elif witness.witness_type == WitnessType.CW:
            credibility += 10

        # If witness has contradictions noted in case, lower credibility
        if hasattr(witness, 'contradictions') and witness.contradictions:
            credibility -= len(witness.contradictions) * 10

        # If witness made admissions, adjust
        if hasattr(witness, 'admissions') and witness.admissions:
            credibility += 5  # Honest witnesses who admit things

        # Add some randomness
        credibility += random.randint(-10, 10)

        return max(30, min(95, credibility))

    def _calculate_base_nervousness(self, witness: OralWitness) -> float:
        """Calculate base nervousness based on witness type."""
        nervousness = 30.0  # Default

        # Check if witness might be an expert based on their role/name
        witness_name_lower = witness.name.lower() if witness.name else ""
        is_expert = any(term in witness_name_lower for term in
                       ['doctor', 'dr.', 'engineer', 'expert', 'specialist',
                        'professor', 'analyst', 'inspector', 'officer'])

        # Experts are usually less nervous
        if is_expert:
            nervousness -= 15

        # Court witnesses (CW) are typically composed
        elif witness.witness_type == WitnessType.CW:
            nervousness -= 10

        # Difficulty affects nervousness
        difficulty_mod = {"easy": -10, "medium": 0, "hard": 10}.get(self.difficulty, 0)
        nervousness += difficulty_mod

        # Add randomness
        nervousness += random.randint(-10, 20)

        return max(5, min(70, nervousness))

    def _calculate_base_hostility(self, witness: OralWitness) -> float:
        """Calculate base hostility level."""
        hostility = 10.0  # Default is low

        # Witnesses from opposing side might be slightly hostile
        player_side = self.state.player_side
        witness_is_opponent = (
            (player_side == PlayerSide.PETITIONER and witness.witness_type == WitnessType.RW) or
            (player_side == PlayerSide.RESPONDENT and witness.witness_type == WitnessType.PW)
        )

        if witness_is_opponent:
            hostility += 15

        # Add randomness
        hostility += random.randint(-5, 15)

        return max(0, min(40, hostility))

    def _calculate_base_memory(self, witness: OralWitness) -> float:
        """Calculate base memory accuracy."""
        memory = 80.0  # Default

        # Check if witness might be an expert based on their role/name
        witness_name_lower = witness.name.lower() if witness.name else ""
        is_expert = any(term in witness_name_lower for term in
                       ['doctor', 'dr.', 'engineer', 'expert', 'specialist',
                        'professor', 'analyst', 'inspector', 'officer'])

        # Expert witnesses have better recall of their opinions
        if is_expert:
            memory += 10

        # Court witnesses typically have reliable memory
        elif witness.witness_type == WitnessType.CW:
            memory += 5

        # Randomness
        memory += random.randint(-15, 10)

        return max(50, min(95, memory))

    def get_current_witness_state(self) -> Optional[WitnessState]:
        """Get the current witness's state."""
        return self.state.current_witness_state

    def get_witness_state(self, witness_id: str) -> Optional[WitnessState]:
        """Get a specific witness's state."""
        return self.state.witness_states.get(witness_id)

    def get_all_witness_states(self) -> Dict[str, WitnessState]:
        """Get all witness states."""
        return self.state.witness_states

    def _set_current_witness_state(self) -> None:
        """Set the current witness state based on current_witness."""
        if not self.state.current_witness:
            self.state.current_witness_state = None
            return

        witness = self.state.current_witness
        witness_id = f"{witness.witness_type.value}_{witness.witness_number}"

        if witness_id in self.state.witness_states:
            self.state.current_witness_state = self.state.witness_states[witness_id]
            # Determine if this is cross-examination
            is_cross = self._is_cross_examination()
            self.state.current_witness_state.examination_phase = "cross" if is_cross else "chief"

    def _is_cross_examination(self) -> bool:
        """Check if current examination is cross-examination."""
        if not self.state.current_witness:
            return False

        witness = self.state.current_witness
        player_side = self.state.player_side

        # Cross-examination when examining opposing side's witness
        if player_side == PlayerSide.PETITIONER:
            return witness.witness_type == WitnessType.RW
        else:
            return witness.witness_type == WitnessType.PW

    def analyze_questioning_style(self, question: str) -> QuestioningStyle:
        """Analyze the style of a question based on content and language."""
        question_lower = question.lower()

        # Check for aggressive indicators
        aggressive_words = [
            'isn\'t it true', 'admit', 'confess', 'lie', 'liar', 'contradict',
            'didn\'t you', 'weren\'t you', 'false', 'wrong', 'deceive',
            'how dare', 'explain yourself', 'isn\'t that a lie'
        ]
        if any(word in question_lower for word in aggressive_words):
            return QuestioningStyle.AGGRESSIVE

        # Check for gentle indicators
        gentle_words = [
            'please', 'could you', 'would you mind', 'help us understand',
            'in your own words', 'take your time', 'if you can recall',
            'i understand', 'thank you for', 'appreciate'
        ]
        if any(word in question_lower for word in gentle_words):
            return QuestioningStyle.GENTLE

        # Check for leading question indicators
        leading_words = [
            'isn\'t it', 'wasn\'t it', 'don\'t you agree', 'you saw',
            'you did', 'you were', 'it\'s true that', 'correct that',
            'right?', 'correct?', 'yes?'
        ]
        if any(word in question_lower for word in leading_words):
            return QuestioningStyle.LEADING

        # Check for confusing/complex questions
        if len(question.split()) > 40 or question.count(',') > 3:
            return QuestioningStyle.CONFUSING

        # Check for rapid-fire (very short, direct)
        if len(question.split()) < 8 and question.endswith('?'):
            return QuestioningStyle.RAPID_FIRE

        return QuestioningStyle.NEUTRAL

    def update_witness_stats(self, style: QuestioningStyle, caught_contradiction: bool = False) -> Dict[str, Any]:
        """
        Update witness stats based on questioning style and outcomes.
        Returns information about the effect.
        """
        if not self.state.current_witness_state:
            return {"effect": "none", "message": ""}

        ws = self.state.current_witness_state
        stats = ws.stats
        effect_info = {"effect": "neutral", "stat_changes": {}, "events": []}

        # Track questioning style
        ws.recent_styles.append(style)
        if len(ws.recent_styles) > 5:
            ws.recent_styles.pop(0)

        # Update streaks
        if style == QuestioningStyle.AGGRESSIVE:
            ws.aggressive_streak += 1
            ws.gentle_streak = 0
        elif style == QuestioningStyle.GENTLE:
            ws.gentle_streak += 1
            ws.aggressive_streak = 0
        else:
            ws.aggressive_streak = max(0, ws.aggressive_streak - 1)
            ws.gentle_streak = max(0, ws.gentle_streak - 1)

        ws.questions_asked += 1

        # Apply effects based on style
        old_stats = {
            "credibility": stats.credibility,
            "nervousness": stats.nervousness,
            "hostility": stats.hostility,
            "cooperation": stats.cooperation
        }

        if style == QuestioningStyle.AGGRESSIVE:
            self._apply_aggressive_effects(stats, ws, effect_info)
        elif style == QuestioningStyle.GENTLE:
            self._apply_gentle_effects(stats, ws, effect_info)
        elif style == QuestioningStyle.LEADING:
            self._apply_leading_effects(stats, ws, effect_info)
        elif style == QuestioningStyle.CONFUSING:
            self._apply_confusing_effects(stats, ws, effect_info)
        elif style == QuestioningStyle.RAPID_FIRE:
            self._apply_rapid_fire_effects(stats, ws, effect_info)

        # Handle caught contradiction
        if caught_contradiction:
            self._apply_contradiction_effects(stats, ws, effect_info)

        # Check for threshold events
        self._check_witness_thresholds(stats, ws, effect_info)

        # Clamp all stats
        stats.clamp_stats()

        # Record stat changes
        effect_info["stat_changes"] = {
            "credibility": stats.credibility - old_stats["credibility"],
            "nervousness": stats.nervousness - old_stats["nervousness"],
            "hostility": stats.hostility - old_stats["hostility"],
            "cooperation": stats.cooperation - old_stats["cooperation"]
        }

        # Reveal more about witness based on questioning
        witness_id = ws.witness_id
        current_reveal = self.state.witness_credibility_revealed.get(witness_id, 0.3)
        self.state.witness_credibility_revealed[witness_id] = min(1.0, current_reveal + 0.05)

        return effect_info

    def _apply_aggressive_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects of aggressive questioning."""
        # Increases nervousness and hostility
        stats.nervousness += random.uniform(5, 12)
        stats.hostility += random.uniform(3, 8)
        stats.cooperation -= random.uniform(2, 6)

        # Sustained aggression has compounding effects
        if ws.aggressive_streak >= 3:
            stats.hostility += 10
            stats.cooperation -= 10
            effect_info["events"].append("Witness becoming defensive")

        # Cross-examination allows more aggressive questioning
        if ws.examination_phase == "cross":
            stats.hostility -= 3  # Less penalty during cross

        effect_info["effect"] = "aggressive_pressure"

    def _apply_gentle_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects of gentle questioning."""
        # Decreases nervousness, may build rapport
        stats.nervousness -= random.uniform(3, 8)
        stats.cooperation += random.uniform(2, 5)
        stats.hostility -= random.uniform(1, 4)

        # Sustained gentleness builds rapport
        if ws.gentle_streak >= 3 and not ws.stats.rapport_built:
            ws.stats.rapport_built = True
            stats.cooperation += 15
            stats.nervousness -= 10
            effect_info["events"].append("Rapport established with witness")

        effect_info["effect"] = "rapport_building"

    def _apply_leading_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects of leading questions."""
        # May get objections, affects credibility of testimony
        if ws.examination_phase == "chief":
            # Leading during direct is improper
            stats.consistency -= random.uniform(2, 5)
            effect_info["events"].append("Leading question during direct examination")
        else:
            # Leading is allowed in cross
            stats.nervousness += random.uniform(2, 5)

        effect_info["effect"] = "leading_question"

    def _apply_confusing_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects of confusing questions."""
        # Increases witness confusion, may affect memory accuracy
        stats.nervousness += random.uniform(3, 7)
        stats.memory_accuracy -= random.uniform(2, 6)
        stats.consistency -= random.uniform(1, 4)

        # But may also cause hostile reaction
        if random.random() < 0.3:
            stats.hostility += random.uniform(3, 8)
            effect_info["events"].append("Witness frustrated by confusing question")

        effect_info["effect"] = "confusion"

    def _apply_rapid_fire_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects of rapid-fire questioning."""
        # Increases pressure, may cause mistakes
        stats.nervousness += random.uniform(4, 10)
        stats.composure -= random.uniform(3, 7)

        # More likely to get inconsistent answers
        if stats.composure < 50:
            stats.consistency -= random.uniform(5, 10)
            effect_info["events"].append("Witness struggling to keep up")

        effect_info["effect"] = "rapid_pressure"

    def _apply_contradiction_effects(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Apply effects when a contradiction is caught."""
        stats.credibility -= random.uniform(10, 20)
        stats.nervousness += random.uniform(8, 15)
        stats.consistency -= random.uniform(5, 12)
        stats.composure -= random.uniform(5, 10)

        ws.stats.contradictions_caught += 1
        self.state.total_contradictions_caught += 1

        effect_info["events"].append(f"Contradiction caught! Credibility damaged.")
        effect_info["effect"] = "contradiction_caught"

    def _check_witness_thresholds(self, stats: WitnessStats, ws: WitnessState, effect_info: Dict):
        """Check if witness has crossed any behavioral thresholds."""
        # Check for hostile witness
        if stats.hostility >= stats.hostility_threshold and not ws.stats.is_hostile:
            ws.stats.is_hostile = True
            ws.current_reaction = WitnessReaction.HOSTILE
            self.state.witnesses_turned_hostile += 1
            effect_info["events"].append("⚠️ WITNESS HAS TURNED HOSTILE!")
            effect_info["hostile"] = True

        # Check for breakdown
        if stats.nervousness >= stats.breakdown_threshold and not ws.stats.has_broken_down:
            ws.stats.has_broken_down = True
            ws.current_reaction = WitnessReaction.BREAKDOWN
            self.state.witness_breakdowns += 1
            effect_info["events"].append("⚠️ WITNESS EMOTIONAL BREAKDOWN!")
            effect_info["breakdown"] = True

        # Update current reaction based on stats
        if not ws.stats.is_hostile and not ws.stats.has_broken_down:
            ws.current_reaction = self._determine_witness_reaction(stats)

    def _determine_witness_reaction(self, stats: WitnessStats) -> WitnessReaction:
        """Determine current witness reaction based on stats."""
        if stats.nervousness > 70:
            return WitnessReaction.NERVOUS
        elif stats.hostility > 50:
            return WitnessReaction.DEFENSIVE
        elif stats.cooperation < 40:
            return WitnessReaction.EVASIVE
        elif stats.composure > 70 and stats.credibility > 70:
            return WitnessReaction.CONFIDENT
        elif stats.cooperation > 70:
            return WitnessReaction.COOPERATIVE
        else:
            return WitnessReaction.COOPERATIVE

    def get_witness_response_modifier(self) -> Dict[str, Any]:
        """
        Get modifiers for witness response generation based on current state.
        This affects how the AI generates witness responses.
        """
        if not self.state.current_witness_state:
            return {"modifier": "normal", "instructions": ""}

        ws = self.state.current_witness_state
        stats = ws.stats

        modifier = {
            "reaction": ws.current_reaction.value,
            "credibility": stats.credibility,
            "nervousness": stats.nervousness,
            "memory_accuracy": stats.memory_accuracy,
            "cooperation": stats.cooperation,
            "instructions": ""
        }

        # Build instructions based on witness state
        instructions = []

        if ws.current_reaction == WitnessReaction.HOSTILE:
            instructions.append("The witness is hostile. Give reluctant, brief, or argumentative answers.")
        elif ws.current_reaction == WitnessReaction.NERVOUS:
            instructions.append("The witness is very nervous. Show hesitation, ask for clarification, speak uncertainly.")
        elif ws.current_reaction == WitnessReaction.DEFENSIVE:
            instructions.append("The witness is defensive. Qualify answers, be guarded, avoid volunteering information.")
        elif ws.current_reaction == WitnessReaction.EVASIVE:
            instructions.append("The witness is evasive. Give vague answers, try to redirect, avoid direct responses.")
        elif ws.current_reaction == WitnessReaction.BREAKDOWN:
            instructions.append("The witness is having an emotional breakdown. Show distress, difficulty speaking, may need a break.")
        elif ws.current_reaction == WitnessReaction.CONFUSED:
            instructions.append("The witness is confused. Ask for the question to be repeated, give uncertain answers.")

        if stats.memory_accuracy < 60:
            instructions.append("Memory is poor. Say 'I don't recall' or 'I'm not certain' frequently.")

        if ws.stats.rapport_built:
            instructions.append("The witness has rapport with the examiner. Be more forthcoming and helpful.")

        if stats.consistency < 60:
            instructions.append("Give slightly inconsistent details compared to earlier testimony.")

        modifier["instructions"] = " ".join(instructions)
        return modifier

    def detect_contradiction(self, response: str) -> bool:
        """
        Check if a witness response contains a potential contradiction.
        This is a simplified check - could be enhanced with AI analysis.
        """
        if not self.state.current_witness_state:
            return False

        ws = self.state.current_witness_state

        # Low consistency means higher chance of contradiction
        if ws.stats.consistency < 50:
            return random.random() < 0.4
        elif ws.stats.consistency < 70:
            return random.random() < 0.2

        return random.random() < 0.05

    def get_witness_credibility_display(self, witness_id: str) -> Dict[str, Any]:
        """
        Get witness credibility info for UI display.
        Amount shown depends on how much has been revealed through questioning.
        """
        ws = self.state.witness_states.get(witness_id)
        if not ws:
            return {"error": "Witness not found"}

        reveal_pct = self.state.witness_credibility_revealed.get(witness_id, 0.3)
        stats = ws.stats

        display = {
            "witness_name": ws.witness_name,
            "witness_id": witness_id,
            "reaction": ws.current_reaction.value,
            "questions_asked": ws.questions_asked,
            "reveal_percentage": reveal_pct
        }

        # Always show reaction
        display["current_reaction"] = ws.current_reaction.value

        # Show stats based on reveal percentage
        if reveal_pct >= 0.3:
            display["credibility_hint"] = self._get_stat_hint(stats.credibility)
        if reveal_pct >= 0.4:
            display["nervousness_hint"] = self._get_stat_hint(stats.nervousness, inverted=True)
        if reveal_pct >= 0.5:
            display["hostility_hint"] = self._get_stat_hint(stats.hostility, inverted=True)
        if reveal_pct >= 0.6:
            display["memory_hint"] = self._get_stat_hint(stats.memory_accuracy)

        # At high reveal, show actual numbers
        if reveal_pct >= 0.8:
            display["credibility"] = round(stats.credibility)
            display["nervousness"] = round(stats.nervousness)
            display["hostility"] = round(stats.hostility)
            display["memory_accuracy"] = round(stats.memory_accuracy)

        # Special states
        if ws.stats.is_hostile:
            display["is_hostile"] = True
        if ws.stats.has_broken_down:
            display["has_broken_down"] = True
        if ws.stats.rapport_built:
            display["rapport_built"] = True

        display["contradictions_caught"] = ws.stats.contradictions_caught

        return display

    def _get_stat_hint(self, value: float, inverted: bool = False) -> str:
        """Convert stat value to a descriptive hint."""
        if inverted:
            # For stats where lower is better (nervousness, hostility)
            if value >= 70:
                return "Very High ⚠️"
            elif value >= 50:
                return "High"
            elif value >= 30:
                return "Moderate"
            else:
                return "Low ✓"
        else:
            # For stats where higher is better (credibility, memory)
            if value >= 80:
                return "Excellent ✓"
            elif value >= 60:
                return "Good"
            elif value >= 40:
                return "Fair"
            else:
                return "Poor ⚠️"

    def get_witness_tips(self) -> List[str]:
        """Get strategic tips for handling the current witness."""
        tips = []

        if not self.state.current_witness_state:
            return ["No witness currently being examined."]

        ws = self.state.current_witness_state
        stats = ws.stats

        # Tips based on witness state
        if stats.nervousness > 60:
            tips.append("💡 Witness is nervous - gentle approach may get better answers")
        if stats.hostility > 40:
            tips.append("⚠️ Witness showing hostility - avoid aggressive questioning")
        if stats.credibility > 80:
            tips.append("📊 High credibility witness - focus on specific contradictions")
        if stats.memory_accuracy < 60:
            tips.append("💭 Witness has poor recall - ask about specific details")
        if ws.stats.rapport_built:
            tips.append("🤝 Good rapport established - witness more cooperative")
        if ws.aggressive_streak >= 2:
            tips.append("⚡ You've been aggressive - consider softening approach")
        if ws.examination_phase == "cross":
            tips.append("⚔️ Cross-examination - leading questions allowed")
        else:
            tips.append("📋 Direct examination - avoid leading questions")

        if not tips:
            tips.append("📋 Witness is in a neutral state")

        return tips

    # ========================================
    # JUDGE PERSONALITY SYSTEM
    # ========================================

    def _initialize_judge_personality(self) -> None:
        """Initialize the judge's personality for this case."""
        # Select a random judge or based on difficulty
        if self.difficulty == "easy":
            # Easy mode gets patient judge
            personality = JUDGE_PERSONALITIES["patient_sharma"]
        elif self.difficulty == "hard":
            # Hard mode gets strict or technical judge
            personality = random.choice([
                JUDGE_PERSONALITIES["strict_kumar"],
                JUDGE_PERSONALITIES["technical_rao"]
            ])
        else:
            # Medium mode gets random judge
            personality = get_random_judge()

        self.state.judge_state = JudgeState(
            personality=personality,
            current_patience=personality.patience,  # Start with base patience
            satisfaction_score=50.0
        )

    def get_judge_state(self) -> Optional[JudgeState]:
        """Get the current judge state."""
        return self.state.judge_state

    def get_judge_personality(self) -> Optional[JudgePersonality]:
        """Get the judge's personality."""
        if self.state.judge_state:
            return self.state.judge_state.personality
        return None

    def _get_judge_opening_statement(self) -> str:
        """Generate judge's opening statement based on personality."""
        if not self.state.judge_state:
            return (
                "The court is now in session. This court will hear the matter. "
                "Counsel for both parties may note their appearances. "
                "Counsel for the petitioner may proceed with the opening statement."
            )

        personality = self.state.judge_state.personality
        ptype = personality.personality_type

        base_opening = "The court is now in session. This court will hear the matter. "

        if ptype == JudgePersonalityType.STRICT:
            return (
                f"{base_opening}"
                "Counsel are reminded that the Court has limited time. "
                "Arguments shall be concise and to the point. "
                "The Court will not tolerate delays or repetition. "
                "Counsel for the petitioner may proceed with the opening statement."
            )
        elif ptype == JudgePersonalityType.PATIENT:
            return (
                f"{base_opening}"
                "The Court will hear both parties in full. "
                "Counsel may take their time to present their case thoroughly. "
                "If any clarification is needed, please do not hesitate to ask. "
                "Counsel for the petitioner may proceed with the opening statement."
            )
        elif ptype == JudgePersonalityType.TECHNICAL:
            return (
                f"{base_opening}"
                "The Court expects counsel to support arguments with relevant case law. "
                "Legal submissions should cite applicable precedents. "
                "The Court values technical accuracy in legal arguments. "
                "Counsel for the petitioner may proceed with the opening statement."
            )
        elif ptype == JudgePersonalityType.PRAGMATIC:
            return (
                f"{base_opening}"
                "The Court is interested in the facts of the matter. "
                "Counsel should focus on the core issues and relevant evidence. "
                "Let us proceed efficiently. "
                "Counsel for the petitioner may begin."
            )
        elif ptype == JudgePersonalityType.INQUISITIVE:
            return (
                f"{base_opening}"
                "The Court may ask questions during submissions for clarification. "
                "Counsel should be prepared to address the Court's queries. "
                "A thorough understanding of the facts is expected. "
                "Counsel for the petitioner may proceed with the opening statement."
            )
        else:
            return (
                f"{base_opening}"
                "Counsel for both parties may note their appearances. "
                "Counsel for the petitioner may proceed with the opening statement."
            )

    def update_judge_state(self, action_type: str, action_quality: float = 0.5) -> Dict[str, Any]:
        """
        Update judge's state based on player's action.
        Returns feedback about how the judge reacted.
        """
        if not self.state.judge_state:
            return {"feedback": None, "mood_changed": False}

        js = self.state.judge_state
        personality = js.personality
        result = {"feedback": None, "mood_changed": False, "events": []}

        old_mood = js.current_mood

        # Track recent actions
        js.recent_actions.append(action_type)
        if len(js.recent_actions) > 5:
            js.recent_actions.pop(0)

        # Check for repetition
        if js.recent_actions.count(action_type) >= 3 and not personality.tolerates_repetition:
            js.current_patience -= 10
            js.repetitions_noted += 1
            result["events"].append("Judge notes repetitive approach")

        # Apply personality-specific effects
        if action_type == "citation":
            if personality.values_precedent:
                js.satisfaction_score += 5 * personality.citation_bonus
                js.player_credibility += 3
                js.citations_appreciated += 1
                result["feedback"] = "Judge appreciates the citation"
            else:
                js.satisfaction_score += 1
                result["feedback"] = "Judge acknowledges the citation"

        elif action_type == "emotional_appeal":
            if personality.emotional_tolerance > 50:
                js.satisfaction_score += 3
                js.emotional_appeals_made += 1
            else:
                js.current_patience -= 5
                js.emotional_appeals_made += 1
                result["feedback"] = "Judge seems unimpressed by emotional appeal"

        elif action_type == "long_argument":
            if personality.prefers_brevity:
                js.current_patience -= 8
                result["events"].append("Judge appears impatient with lengthy argument")
            else:
                js.satisfaction_score += 2

        elif action_type == "concise_argument":
            if personality.prefers_brevity:
                js.satisfaction_score += 5 * personality.brevity_bonus
                result["feedback"] = "Judge appreciates the brevity"

        elif action_type == "decorum_violation":
            js.current_patience -= 10 * personality.decorum_penalty
            js.satisfaction_score -= 5 * personality.decorum_penalty
            result["events"].append("Judge displeased with breach of decorum")

        elif action_type == "good_decorum":
            if personality.formality > 60:
                js.satisfaction_score += 3
                js.player_credibility += 2

        elif action_type == "technical_argument":
            if personality.technical_focus > 60:
                js.satisfaction_score += 4
                js.player_credibility += 3
                result["feedback"] = "Judge engaged by technical argument"

        elif action_type == "factual_presentation":
            js.satisfaction_score += 3
            js.player_preparation_score += 2

        # General patience decay over time
        js.current_patience -= 1

        # Clamp values
        js.current_patience = max(0, min(100, js.current_patience))
        js.satisfaction_score = max(0, min(100, js.satisfaction_score))
        js.player_credibility = max(0, min(100, js.player_credibility))

        # Update mood
        js.update_mood()

        if js.current_mood != old_mood:
            result["mood_changed"] = True
            result["new_mood"] = js.current_mood.value

        return result

    def get_judge_interruption_chance(self) -> float:
        """Get the chance that the judge will interrupt based on personality and state."""
        if not self.state.judge_state:
            return 0.1

        js = self.state.judge_state
        personality = js.personality

        base_chance = personality.interruption_tendency / 100

        # Modify based on mood
        if js.current_mood == JudgeMood.IMPATIENT:
            base_chance *= 1.5
        elif js.current_mood == JudgeMood.ANNOYED:
            base_chance *= 2.0
        elif js.current_mood == JudgeMood.INTERESTED:
            base_chance *= 1.3  # Interested judges ask more questions

        return min(0.8, base_chance)

    def get_judge_question_chance(self) -> float:
        """Get the chance that the judge will ask a clarifying question."""
        if not self.state.judge_state:
            return 0.2

        js = self.state.judge_state
        personality = js.personality

        base_chance = personality.question_frequency / 100

        # Modify based on mood and state
        if js.current_mood == JudgeMood.INTERESTED:
            base_chance *= 1.5
        elif js.current_mood == JudgeMood.SKEPTICAL:
            base_chance *= 1.3

        return min(0.7, base_chance)

    def should_judge_intervene(self) -> Dict[str, Any]:
        """
        Check if judge should intervene based on personality and current state.
        Returns intervention type and content.
        """
        if not self.state.judge_state:
            return {"intervene": False}

        js = self.state.judge_state
        personality = js.personality

        # Check for interruption
        if random.random() < self.get_judge_interruption_chance():
            intervention_type = "interruption"

            if js.current_mood == JudgeMood.IMPATIENT:
                content = self._get_impatient_interruption(personality)
            elif js.current_mood == JudgeMood.ANNOYED:
                content = self._get_annoyed_interruption(personality)
            else:
                content = self._get_neutral_interruption(personality)

            js.interruptions_made += 1
            self.state.judge_interruptions += 1

            return {
                "intervene": True,
                "type": intervention_type,
                "content": content
            }

        # Check for clarifying question
        if random.random() < self.get_judge_question_chance():
            question = self._get_judge_question(personality)
            js.questions_asked += 1
            self.state.judge_questions_to_player += 1

            return {
                "intervene": True,
                "type": "question",
                "content": question
            }

        return {"intervene": False}

    def _get_impatient_interruption(self, personality: JudgePersonality) -> str:
        """Get an impatient interruption based on personality."""
        interruptions = {
            JudgePersonalityType.STRICT: [
                "Counsel, please come to the point.",
                "The Court has understood. Please move on.",
                "This is taking too long. What is your submission?"
            ],
            JudgePersonalityType.TECHNICAL: [
                "Counsel, what is the legal basis for this argument?",
                "Do you have any case law to support this?",
                "Please cite the relevant provision."
            ],
            JudgePersonalityType.PRAGMATIC: [
                "What is the factual basis for this?",
                "Let's focus on the evidence.",
                "How does this help your case?"
            ]
        }
        options = interruptions.get(personality.personality_type, [
            "Counsel, please proceed expeditiously.",
            "The Court is waiting for your submission."
        ])
        return random.choice(options)

    def _get_annoyed_interruption(self, personality: JudgePersonality) -> str:
        """Get an annoyed interruption based on personality."""
        interruptions = {
            JudgePersonalityType.STRICT: [
                "Counsel! The Court's patience is being tested.",
                "This is highly improper. Proceed properly.",
                "The Court will not tolerate further delays."
            ],
            JudgePersonalityType.TECHNICAL: [
                "Counsel, you are wasting the Court's time without legal substance.",
                "Where is the legal authority for these submissions?",
                "The Court expected better preparation."
            ],
            JudgePersonalityType.FORMAL: [
                "Counsel, maintain proper decorum.",
                "The Court finds this conduct unacceptable.",
                "You are testing the Court's patience."
            ]
        }
        options = interruptions.get(personality.personality_type, [
            "Counsel, the Court is not pleased with these proceedings.",
            "Please conclude your submissions."
        ])
        return random.choice(options)

    def _get_neutral_interruption(self, personality: JudgePersonality) -> str:
        """Get a neutral interruption/comment based on personality."""
        interruptions = {
            JudgePersonalityType.INQUISITIVE: [
                "One moment, counsel. The Court has a question.",
                "Before you proceed, could you clarify something?",
                "The Court would like to understand this point better."
            ],
            JudgePersonalityType.PATIENT: [
                "Please continue, counsel. The Court is following.",
                "Take your time, but please stay on point.",
                "The Court notes your submission."
            ]
        }
        options = interruptions.get(personality.personality_type, [
            "The Court has noted your submission.",
            "Please proceed, counsel."
        ])
        return random.choice(options)

    def _get_judge_question(self, personality: JudgePersonality) -> str:
        """Generate a clarifying question based on judge personality."""
        questions = {
            JudgePersonalityType.TECHNICAL: [
                "What is the ratio decidendi of the case you cited?",
                "How does this precedent apply to the present facts?",
                "What is the statutory provision governing this issue?",
                "Can you distinguish the facts from the cited case?"
            ],
            JudgePersonalityType.INQUISITIVE: [
                "Could you elaborate on that point?",
                "What evidence supports this assertion?",
                "How do you reconcile this with the opposing party's version?",
                "What is the witness's basis of knowledge for this?"
            ],
            JudgePersonalityType.PRAGMATIC: [
                "What is the practical impact of your argument?",
                "How does this affect the outcome of the case?",
                "What relief are you specifically seeking?",
                "Can you summarize your core submission?"
            ],
            JudgePersonalityType.STRICT: [
                "What is your submission?",
                "Is this relevant to the issues framed?",
                "What is the purpose of this line of questioning?"
            ]
        }
        options = questions.get(personality.personality_type, [
            "Could you clarify your submission?",
            "What is the basis for this argument?",
            "How does this help your case?"
        ])
        return random.choice(options)

    def get_judge_ruling_modifier(self) -> Dict[str, float]:
        """
        Get modifiers for judge's rulings based on personality and state.
        Returns multipliers for different aspects.
        """
        if not self.state.judge_state:
            return {"sustain_bias": 0.5, "leniency": 0.5}

        js = self.state.judge_state
        personality = js.personality

        # Base values
        sustain_bias = 0.5  # 50% base chance to sustain valid objections
        leniency = 0.5  # 50% base leniency

        # Modify based on personality
        if personality.personality_type == JudgePersonalityType.STRICT:
            sustain_bias += 0.1  # More likely to sustain objections
            leniency -= 0.2  # Less lenient
        elif personality.personality_type == JudgePersonalityType.PATIENT:
            leniency += 0.2  # More lenient
        elif personality.personality_type == JudgePersonalityType.TECHNICAL:
            sustain_bias += 0.05
            # Technical judges rule based on law, not mood

        # Modify based on current mood
        if js.current_mood == JudgeMood.ANNOYED:
            leniency -= 0.15
        elif js.current_mood == JudgeMood.PLEASED:
            leniency += 0.1

        # Modify based on player credibility
        leniency += (js.player_credibility - 50) / 200

        return {
            "sustain_bias": max(0.2, min(0.8, sustain_bias)),
            "leniency": max(0.2, min(0.8, leniency))
        }

    def get_judge_display_info(self) -> Dict[str, Any]:
        """Get judge information for UI display."""
        if not self.state.judge_state:
            return {"error": "Judge state not initialized"}

        js = self.state.judge_state
        personality = js.personality

        mood_emoji = {
            JudgeMood.NEUTRAL: "😐",
            JudgeMood.PLEASED: "😊",
            JudgeMood.IMPATIENT: "😤",
            JudgeMood.ANNOYED: "😠",
            JudgeMood.INTERESTED: "🤔",
            JudgeMood.SKEPTICAL: "🤨"
        }.get(js.current_mood, "😐")

        return {
            "name": personality.name,
            "title": personality.title,
            "personality_type": personality.personality_type.value,
            "description": personality.description,
            "strengths": personality.strengths,
            "weaknesses": personality.weaknesses,
            "current_mood": js.current_mood.value,
            "mood_emoji": mood_emoji,
            "patience_level": js.current_patience,
            "satisfaction": js.satisfaction_score,
            "player_credibility": js.player_credibility,
            "interruptions": js.interruptions_made,
            "questions_asked": js.questions_asked,
            "warnings_given": js.warnings_given,
            "prefers_brevity": personality.prefers_brevity,
            "values_precedent": personality.values_precedent,
            "technical_focus": personality.technical_focus
        }

    def get_judge_tips(self) -> List[str]:
        """Get strategic tips for dealing with the current judge."""
        if not self.state.judge_state:
            return ["No judge information available"]

        js = self.state.judge_state
        personality = js.personality
        tips = []

        # Personality-based tips
        if personality.personality_type == JudgePersonalityType.STRICT:
            tips.append("⏱️ Keep arguments brief and to the point")
            tips.append("📋 Follow strict procedural formalities")
            if js.current_patience < 50:
                tips.append("⚠️ Judge's patience is low - be concise!")
        elif personality.personality_type == JudgePersonalityType.PATIENT:
            tips.append("📝 You can elaborate on complex points")
            tips.append("💬 Judge is open to detailed explanations")
        elif personality.personality_type == JudgePersonalityType.TECHNICAL:
            tips.append("📚 Cite relevant case law and statutes")
            tips.append("⚖️ Focus on legal technicalities")
            tips.append("🔍 Judge expects thorough legal research")
        elif personality.personality_type == JudgePersonalityType.PRAGMATIC:
            tips.append("📊 Focus on facts and evidence")
            tips.append("🎯 Get to the practical point quickly")
        elif personality.personality_type == JudgePersonalityType.INQUISITIVE:
            tips.append("❓ Expect frequent questions from the bench")
            tips.append("🗣️ Be prepared to clarify your arguments")

        # Mood-based tips
        if js.current_mood == JudgeMood.IMPATIENT:
            tips.append("⚡ Judge is impatient - wrap up quickly")
        elif js.current_mood == JudgeMood.ANNOYED:
            tips.append("🚨 Judge is annoyed - tread carefully!")
        elif js.current_mood == JudgeMood.PLEASED:
            tips.append("✅ Judge is pleased - maintain this approach")
        elif js.current_mood == JudgeMood.INTERESTED:
            tips.append("🎯 Judge is engaged - good opportunity to make key points")

        # Preference-based tips
        if not personality.tolerates_repetition and js.repetitions_noted > 0:
            tips.append("🔄 Avoid repeating arguments")
        if personality.values_precedent and js.citations_appreciated < 2:
            tips.append("📖 Cite more case law to impress this judge")

        return tips

    # ========================================
    # PRE-TRIAL PREPARATION METHODS
    # ========================================

    def initialize_preparation(self, player_side: PlayerSide) -> PreparationState:
        """Initialize the preparation phase for the player."""
        # Generate tasks based on case and difficulty
        tasks = generate_preparation_tasks(self.case, player_side)

        # Adjust prep points based on difficulty
        prep_points = {
            "easy": 15,
            "medium": 10,
            "hard": 7
        }.get(self.difficulty, 10)

        prep_state = PreparationState(
            total_prep_points=prep_points,
            tasks=tasks
        )

        self.state.preparation_state = prep_state
        self.state.player_side = player_side
        return prep_state

    def get_preparation_state(self) -> Optional[PreparationState]:
        """Get the current preparation state."""
        return self.state.preparation_state

    def get_available_prep_tasks(self) -> List[PreparationTask]:
        """Get tasks that are available to be completed."""
        if not self.state.preparation_state:
            return []

        prep = self.state.preparation_state
        available = []

        for task in prep.tasks:
            if task.is_completed:
                continue
            if not task.is_available:
                continue
            if task.time_cost > prep.remaining_points:
                continue
            # Check prerequisite
            if task.requires_task and task.requires_task not in prep.completed_tasks:
                continue
            available.append(task)

        return available

    def get_prep_tasks_by_category(self) -> Dict[PreparationCategory, List[PreparationTask]]:
        """Get preparation tasks organized by category."""
        if not self.state.preparation_state:
            return {}

        by_category = {}
        for task in self.state.preparation_state.tasks:
            if task.category not in by_category:
                by_category[task.category] = []
            by_category[task.category].append(task)

        return by_category

    def complete_prep_task(self, task_id: str) -> Dict[str, Any]:
        """Complete a preparation task."""
        if not self.state.preparation_state:
            return {"success": False, "error": "Preparation not initialized"}

        prep = self.state.preparation_state
        result = {
            "success": False,
            "task": None,
            "bonus_gained": 0,
            "insight": None,
            "unlocked_tasks": []
        }

        # Find the task
        task = None
        for t in prep.tasks:
            if t.task_id == task_id:
                task = t
                break

        if not task:
            result["error"] = "Task not found"
            return result

        if task.is_completed:
            result["error"] = "Task already completed"
            return result

        if task.time_cost > prep.remaining_points:
            result["error"] = "Not enough preparation time"
            return result

        # Check prerequisite
        if task.requires_task and task.requires_task not in prep.completed_tasks:
            result["error"] = f"Must complete prerequisite task first"
            return result

        # Complete the task
        task.is_completed = True
        prep.used_prep_points += task.time_cost
        prep.completed_tasks.append(task_id)
        prep.total_score_bonus += task.score_bonus

        # Apply skill bonuses
        for skill, bonus in task.skill_bonuses.items():
            if skill not in prep.skill_bonuses:
                prep.skill_bonuses[skill] = 0
            prep.skill_bonuses[skill] += bonus

        # Store any revealed insights
        if task.reveal_info:
            prep.case_insights.append(task.reveal_info)

        # Check for unlocked tasks
        for t in prep.tasks:
            if t.requires_task == task_id and not t.is_completed:
                result["unlocked_tasks"].append(t.title)

        # Update preparation grade
        prep.preparation_grade = prep.calculate_grade()

        result["success"] = True
        result["task"] = task
        result["bonus_gained"] = task.score_bonus
        result["insight"] = task.reveal_info
        result["remaining_points"] = prep.remaining_points
        result["grade"] = prep.preparation_grade

        return result

    def skip_preparation(self) -> Dict[str, Any]:
        """Skip the preparation phase entirely."""
        if self.state.preparation_state:
            self.state.preparation_state.preparation_grade = "F"
        self.state.preparation_completed = True
        return {"skipped": True, "grade": "F"}

    def finish_preparation(self) -> Dict[str, Any]:
        """Finish the preparation phase and apply bonuses."""
        if not self.state.preparation_state:
            return {"success": False, "error": "No preparation state"}

        prep = self.state.preparation_state
        prep.preparation_grade = prep.calculate_grade()

        self.state.preparation_completed = True

        return {
            "success": True,
            "grade": prep.preparation_grade,
            "total_bonus": prep.total_score_bonus,
            "skill_bonuses": prep.skill_bonuses,
            "insights_gained": len(prep.case_insights),
            "tasks_completed": len(prep.completed_tasks),
            "total_tasks": len(prep.tasks)
        }

    def apply_preparation_bonuses(self) -> None:
        """Apply preparation bonuses to the game score."""
        if not self.state.preparation_state or self.state.preparation_bonuses_applied:
            return

        prep = self.state.preparation_state

        # Apply skill bonuses to game score
        for skill, bonus in prep.skill_bonuses.items():
            if hasattr(self.state.score, skill):
                current = getattr(self.state.score, skill)
                setattr(self.state.score, skill, current + bonus)

        # Grade bonus to judge favor
        grade_bonus = {
            "A": 15,
            "B": 10,
            "C": 5,
            "D": 0,
            "F": -5
        }.get(prep.preparation_grade, 0)

        self.state.score.judge_favor = min(100, self.state.score.judge_favor + grade_bonus)

        # Bonus to total points
        self.state.score.total_points += int(prep.total_score_bonus)

        self.state.preparation_bonuses_applied = True

    def get_preparation_summary(self) -> Dict[str, Any]:
        """Get a summary of the preparation phase for display."""
        if not self.state.preparation_state:
            return {"error": "No preparation data"}

        prep = self.state.preparation_state

        # Count by category
        category_stats = {}
        for cat in PreparationCategory:
            tasks_in_cat = [t for t in prep.tasks if t.category == cat]
            completed_in_cat = [t for t in tasks_in_cat if t.is_completed]
            category_stats[cat.value] = {
                "total": len(tasks_in_cat),
                "completed": len(completed_in_cat)
            }

        return {
            "grade": prep.preparation_grade,
            "total_bonus": prep.total_score_bonus,
            "tasks_completed": len(prep.completed_tasks),
            "total_tasks": len(prep.tasks),
            "time_used": prep.used_prep_points,
            "time_total": prep.total_prep_points,
            "skill_bonuses": prep.skill_bonuses,
            "insights": prep.case_insights,
            "category_stats": category_stats
        }

    def get_preparation_tips(self) -> List[str]:
        """Get tips for the preparation phase."""
        tips = []

        if not self.state.preparation_state:
            return ["Start preparation to gain advantages in court."]

        prep = self.state.preparation_state
        available = self.get_available_prep_tasks()

        # General tips
        if prep.remaining_points > 0:
            tips.append(f"⏱️ {prep.remaining_points} prep points remaining")

        if len(prep.completed_tasks) == 0:
            tips.append("📋 Start with 'Review Case File' for a solid foundation")

        # Category-specific tips
        witness_tasks = [t for t in available if t.category == PreparationCategory.WITNESS_PREP]
        if witness_tasks:
            tips.append("🧑 Witness preparation improves examination skills")

        legal_tasks = [t for t in available if t.category == PreparationCategory.LEGAL_RESEARCH]
        if legal_tasks:
            tips.append("📚 Legal research helps with citations and legal accuracy")

        # Grade tip
        if prep.preparation_grade in ["D", "F"]:
            tips.append("⚠️ Complete more tasks to improve your preparation grade")
        elif prep.preparation_grade == "A":
            tips.append("✅ Excellent preparation! You're ready for court")

        # Time warning
        if prep.remaining_points <= 2 and len(available) > 0:
            tips.append("⏰ Limited time - prioritize key tasks")

        return tips

    # ========================================
    # REAL-TIME PRESSURE SYSTEM METHODS
    # ========================================

    def initialize_pressure_system(self) -> None:
        """Initialize the time pressure and confidence system."""
        # Get config based on difficulty
        config = TIME_PRESSURE_CONFIGS.get(self.difficulty, TIME_PRESSURE_CONFIGS["medium"])

        self.state.time_pressure_state = TimePressureState(config=config)
        self.state.time_pressure_state.extensions_remaining = config.max_extensions

        self.state.confidence_meter = ConfidenceMeter()

        # Apply preparation bonuses to confidence if applicable
        if self.state.preparation_state and self.state.preparation_completed:
            prep = self.state.preparation_state
            if prep.preparation_grade == "A":
                self.state.confidence_meter.confidence_score = 85.0
            elif prep.preparation_grade == "B":
                self.state.confidence_meter.confidence_score = 75.0
            elif prep.preparation_grade == "C":
                self.state.confidence_meter.confidence_score = 65.0
            elif prep.preparation_grade == "D":
                self.state.confidence_meter.confidence_score = 55.0
            else:  # F
                self.state.confidence_meter.confidence_score = 45.0

    def start_action_timer(self, action_type: Optional[ActionType] = None) -> Dict[str, Any]:
        """Start the timer for a new player action."""
        if not self.state.pressure_enabled or not self.state.time_pressure_state:
            return {"active": False}

        tps = self.state.time_pressure_state

        # Adjust time based on action type
        base_time = tps.config.base_time_seconds
        if action_type:
            # Some actions get more/less time
            time_adjustments = {
                ActionType.MAKE_ARGUMENT: 1.5,  # Arguments get more time
                ActionType.CITE_CASE_LAW: 1.3,  # Citations get more time
                ActionType.RAISE_OBJECTION: 0.5,  # Objections need quick response
                ActionType.ASK_QUESTION: 0.8,  # Questions should be ready
                ActionType.CROSS_EXAMINE: 1.0,
                ActionType.NO_QUESTIONS: 0.3,  # Quick decision
                ActionType.REST_CASE: 0.5,
            }
            multiplier = time_adjustments.get(action_type, 1.0)
            base_time = int(base_time * multiplier)

        tps.start_timer(base_time)

        return {
            "active": True,
            "time_limit": base_time,
            "time_remaining": float(base_time),
            "pressure_level": PressureLevel.CALM.value
        }

    def get_timer_status(self) -> Dict[str, Any]:
        """Get current timer status for UI display."""
        if not self.state.pressure_enabled or not self.state.time_pressure_state:
            return {"active": False, "enabled": False}

        tps = self.state.time_pressure_state
        status = tps.update_time()

        # Check if we should generate a judge prompt
        if status.get("should_judge_prompt") and not tps.judge_has_prompted:
            tps.mark_judge_prompted()
            self.state.judge_time_prompts_given += 1
            status["judge_prompt"] = random.choice(JUDGE_TIME_PROMPTS)

        return status

    def stop_action_timer(self) -> Dict[str, Any]:
        """Stop the timer and process response timing."""
        if not self.state.pressure_enabled or not self.state.time_pressure_state:
            return {"processed": False}

        tps = self.state.time_pressure_state
        stats = tps.stop_timer()
        self.state.last_response_stats = stats

        result = {
            "processed": True,
            "response_time": stats.response_time_seconds,
            "was_rushed": stats.was_rushed,
            "was_slow": stats.was_slow,
            "time_expired": stats.time_expired,
            "judge_prompted": stats.judge_prompted,
            "confidence_impact": 0.0,
            "judge_remark": None
        }

        # Apply confidence impacts based on timing
        if self.state.confidence_meter:
            cm = self.state.confidence_meter

            if stats.time_expired:
                # Time expired - significant confidence hit
                impact = cm.adjust_confidence(-15, "Time expired")
                result["confidence_impact"] = -15
                cm.hesitation_count += 1

            elif stats.judge_prompted:
                # Judge had to prompt - moderate confidence hit
                impact = cm.adjust_confidence(-8, "Judge prompted due to delay")
                result["confidence_impact"] = -8
                cm.hesitation_count += 1

            elif stats.was_slow:
                # Slow response - small confidence hit
                impact = cm.adjust_confidence(-3, "Slow response")
                result["confidence_impact"] = -3

            elif stats.was_rushed:
                # Rushed response - depends on outcome (handled in process_player_action)
                result["potentially_rushed"] = True
                self.state.rushed_answer_penalties += 1
                # Add judge remark about rushed answer
                result["judge_remark"] = random.choice(JUDGE_RUSH_REMARKS)

            else:
                # Good timing - small confidence boost
                impact = cm.adjust_confidence(2, "Good response timing")
                result["confidence_impact"] = 2

        return result

    def request_time_extension(self) -> Dict[str, Any]:
        """Request a time extension from the judge."""
        result = {"success": False, "granted": False, "message": ""}

        if not self.state.time_pressure_state:
            result["message"] = "Time pressure system not active"
            return result

        tps = self.state.time_pressure_state

        if not tps.config.extension_available:
            result["message"] = "Extensions not available at this difficulty"
            return result

        if tps.extensions_remaining <= 0:
            result["message"] = "No extensions remaining"
            return result

        # Judge decides based on personality and situation
        grant_probability = 0.7  # Base probability

        if self.state.judge_state:
            js = self.state.judge_state
            # Patient judges more likely to grant
            if js.personality.patience > 60:
                grant_probability += 0.15
            elif js.personality.patience < 40:
                grant_probability -= 0.2

            # Mood affects decision
            if js.current_mood == JudgeMood.IMPATIENT:
                grant_probability -= 0.3
            elif js.current_mood == JudgeMood.PLEASED:
                grant_probability += 0.1

        # Previous extensions reduce chance
        grant_probability -= tps.extensions_used * 0.15

        granted = random.random() < grant_probability

        if granted:
            extra_time = 30  # 30 seconds extension
            tps.use_extension(extra_time)
            result["success"] = True
            result["granted"] = True
            result["extra_time"] = extra_time
            result["message"] = "The court grants counsel a brief extension."
            result["extensions_remaining"] = tps.extensions_remaining
        else:
            result["success"] = True
            result["granted"] = False
            result["message"] = "The court expects counsel to proceed promptly."

            # Confidence hit for denied extension
            if self.state.confidence_meter:
                self.state.confidence_meter.adjust_confidence(-5, "Extension denied")

        return result

    def update_confidence_from_action(self, action_result: Dict[str, Any]) -> Dict[str, Any]:
        """Update confidence based on action outcome."""
        if not self.state.confidence_meter:
            return {"updated": False}

        cm = self.state.confidence_meter
        changes = []

        # Objection outcomes
        if action_result.get("objection_result"):
            if action_result["objection_result"] == "sustained":
                changes.append(cm.adjust_confidence(8, "Objection sustained"))
                cm.objection_success_rate = (cm.objection_success_rate + 1) / 2
            elif action_result["objection_result"] == "overruled":
                changes.append(cm.adjust_confidence(-5, "Objection overruled"))
                cm.objection_success_rate = cm.objection_success_rate / 2

        # Evidence handling
        if action_result.get("evidence_admitted"):
            changes.append(cm.adjust_confidence(6, "Evidence admitted"))
            cm.evidence_handling = min(100, cm.evidence_handling + 5)
        elif action_result.get("evidence_excluded"):
            changes.append(cm.adjust_confidence(-4, "Evidence excluded"))
            cm.evidence_handling = max(0, cm.evidence_handling - 5)

        # Witness control
        if action_result.get("witness_cooperative"):
            changes.append(cm.adjust_confidence(3, "Good witness control"))
            cm.witness_control = min(100, cm.witness_control + 3)
        elif action_result.get("witness_hostile"):
            changes.append(cm.adjust_confidence(-4, "Lost witness control"))
            cm.witness_control = max(0, cm.witness_control - 5)

        # Contradiction caught
        if action_result.get("contradiction_caught"):
            changes.append(cm.adjust_confidence(10, "Caught contradiction"))

        # Judge approval/disapproval
        if action_result.get("judge_approved"):
            changes.append(cm.adjust_confidence(5, "Judge approval"))
            cm.judge_approval = min(100, cm.judge_approval + 5)
        elif action_result.get("judge_disapproved"):
            changes.append(cm.adjust_confidence(-6, "Judge disapproval"))
            cm.judge_approval = max(0, cm.judge_approval - 8)

        # Etiquette
        if action_result.get("etiquette_violation"):
            changes.append(cm.adjust_confidence(-4, "Etiquette violation"))
        elif action_result.get("proper_etiquette"):
            changes.append(cm.adjust_confidence(2, "Proper etiquette"))

        # Self-contradiction (player contradicted themselves)
        if action_result.get("self_contradiction"):
            changes.append(cm.adjust_confidence(-12, "Self-contradiction"))
            cm.contradiction_count += 1
            cm.argument_coherence = max(0, cm.argument_coherence - 10)

        # Streak bonuses
        if cm.confident_actions_streak >= 3:
            changes.append(cm.adjust_confidence(3, f"Confidence streak ({cm.confident_actions_streak})"))
            self.state.confidence_bonuses_earned += 1

        total_change = sum(c.get("delta", 0) for c in changes)

        return {
            "updated": True,
            "changes": changes,
            "total_change": total_change,
            "current_confidence": cm.confidence_score,
            "confidence_state": cm.confidence_state.value
        }

    def get_confidence_display(self) -> Dict[str, Any]:
        """Get confidence meter info for UI display."""
        if not self.state.confidence_meter:
            return {"active": False}

        cm = self.state.confidence_meter

        # Get state emoji
        state_emojis = {
            ConfidenceState.COMMANDING: "💪",
            ConfidenceState.CONFIDENT: "😊",
            ConfidenceState.STEADY: "😐",
            ConfidenceState.UNCERTAIN: "😟",
            ConfidenceState.NERVOUS: "😰",
            ConfidenceState.FLUSTERED: "😵"
        }

        # Calculate trend
        if len(cm.confidence_history) >= 3:
            recent = cm.confidence_history[-3:]
            if all(recent[i] <= recent[i+1] for i in range(len(recent)-1)):
                trend = "rising"
            elif all(recent[i] >= recent[i+1] for i in range(len(recent)-1)):
                trend = "falling"
            else:
                trend = "stable"
        else:
            trend = "stable"

        return {
            "active": True,
            "confidence_score": cm.confidence_score,
            "confidence_state": cm.confidence_state.value,
            "state_emoji": state_emojis.get(cm.confidence_state, "😐"),
            "trend": trend,
            "peak_confidence": cm.peak_confidence,
            "lowest_confidence": cm.lowest_confidence,
            "hesitation_count": cm.hesitation_count,
            "contradiction_count": cm.contradiction_count,
            "confident_streak": cm.confident_actions_streak,
            "uncertain_streak": cm.uncertain_actions_streak,
            "judge_approval": cm.judge_approval,
            "argument_coherence": cm.argument_coherence,
            "witness_control": cm.witness_control,
            "evidence_handling": cm.evidence_handling
        }

    def get_pressure_display(self) -> Dict[str, Any]:
        """Get time pressure info for UI display."""
        if not self.state.time_pressure_state:
            return {"active": False}

        tps = self.state.time_pressure_state

        # Get pressure level colors
        pressure_colors = {
            PressureLevel.CALM: "green",
            PressureLevel.MILD: "blue",
            PressureLevel.MODERATE: "yellow",
            PressureLevel.HIGH: "orange",
            PressureLevel.CRITICAL: "red"
        }

        pressure_emojis = {
            PressureLevel.CALM: "🟢",
            PressureLevel.MILD: "🔵",
            PressureLevel.MODERATE: "🟡",
            PressureLevel.HIGH: "🟠",
            PressureLevel.CRITICAL: "🔴"
        }

        return {
            "active": True,
            "timer_active": tps.is_timer_active,
            "time_remaining": tps.time_remaining,
            "time_limit": tps.current_time_limit,
            "time_percentage": tps.time_percentage,
            "pressure_level": tps.current_pressure_level.value,
            "pressure_color": pressure_colors.get(tps.current_pressure_level, "gray"),
            "pressure_emoji": pressure_emojis.get(tps.current_pressure_level, "⚪"),
            "extensions_remaining": tps.extensions_remaining,
            "extensions_used": tps.extensions_used,
            "total_actions": tps.total_actions,
            "rushed_actions": tps.rushed_actions,
            "slow_actions": tps.slow_actions,
            "timed_out_actions": tps.timed_out_actions,
            "average_response_time": tps.average_response_time,
            "judge_prompts_received": tps.judge_prompts_received
        }

    def get_judge_confidence_remark(self) -> Optional[str]:
        """Get a judge remark based on current confidence level."""
        if not self.state.confidence_meter:
            return None

        cm = self.state.confidence_meter
        state = cm.confidence_state

        # Only remark occasionally (20% chance) or at extreme states
        if state in [ConfidenceState.COMMANDING, ConfidenceState.FLUSTERED]:
            if random.random() < 0.4:  # 40% at extremes
                remarks = JUDGE_CONFIDENCE_REMARKS.get(state, [])
                if remarks:
                    return random.choice(remarks)
        elif state in [ConfidenceState.NERVOUS, ConfidenceState.UNCERTAIN]:
            if random.random() < 0.2:  # 20% for uncertain states
                remarks = JUDGE_CONFIDENCE_REMARKS.get(state, [])
                if remarks:
                    return random.choice(remarks)

        return None

    def toggle_pressure_system(self, enabled: bool) -> None:
        """Enable or disable the pressure system (accessibility option)."""
        self.state.pressure_enabled = enabled
        if enabled and not self.state.time_pressure_state:
            self.initialize_pressure_system()

    def get_pressure_tips(self) -> List[str]:
        """Get tips based on current pressure/confidence state."""
        tips = []

        if not self.state.time_pressure_state or not self.state.confidence_meter:
            return tips

        tps = self.state.time_pressure_state
        cm = self.state.confidence_meter

        # Time pressure tips
        if tps.is_timer_active:
            if tps.current_pressure_level == PressureLevel.CRITICAL:
                tips.append("⚠️ Time is almost up! Submit your response or request extension.")
            elif tps.current_pressure_level == PressureLevel.HIGH:
                tips.append("⏰ Time is running low. Consider wrapping up.")

        if tps.rushed_actions > 2:
            tips.append("💡 Slow down - rushed answers may contain errors.")

        if tps.extensions_remaining > 0 and tps.is_timer_active:
            tips.append(f"📋 {tps.extensions_remaining} time extension(s) available if needed.")

        # Confidence tips
        if cm.confidence_state == ConfidenceState.NERVOUS:
            tips.append("😰 Stay calm. Take a breath and organize your thoughts.")
        elif cm.confidence_state == ConfidenceState.FLUSTERED:
            tips.append("🆘 Consider requesting a brief adjournment to collect yourself.")

        if cm.confident_actions_streak >= 2:
            tips.append("🔥 You're on a roll! Maintain your composure.")

        if cm.hesitation_count > 3:
            tips.append("⏱️ Respond more promptly to maintain confidence.")

        if cm.judge_approval < 40:
            tips.append("👨‍⚖️ The judge seems unimpressed. Focus on substance.")

        return tips

    # ========================================
    # LEGAL RESEARCH MID-TRIAL METHODS
    # ========================================

    def initialize_legal_research(self) -> None:
        """Initialize the legal research system."""
        # Set research limits based on difficulty
        limits = {
            "easy": 5,
            "medium": 3,
            "hard": 2
        }
        max_research = limits.get(self.difficulty, 3)

        self.state.legal_research_state = LegalResearchState(
            max_research_per_phase=max_research
        )

    def can_do_research(self) -> Dict[str, Any]:
        """Check if player can currently do legal research."""
        result = {
            "can_research": False,
            "reason": "",
            "remaining": 0,
            "warning": None
        }

        if not self.state.research_enabled:
            result["reason"] = "Legal research is disabled"
            return result

        if not self.state.legal_research_state:
            self.initialize_legal_research()

        lrs = self.state.legal_research_state

        # Check if research allowed in current phase
        allowed_phases = [
            GamePhase.OPENING_STATEMENT,
            GamePhase.PETITIONER_EVIDENCE,
            GamePhase.PETITIONER_WITNESS_EXAM,
            GamePhase.CROSS_EXAMINATION,
            GamePhase.RESPONDENT_EVIDENCE,
            GamePhase.RESPONDENT_WITNESS_EXAM,
            GamePhase.FINAL_ARGUMENTS
        ]

        if self.state.phase not in allowed_phases:
            result["reason"] = "Research not allowed in this phase"
            return result

        if not lrs.can_research:
            result["reason"] = f"Research limit reached for this phase ({lrs.max_research_per_phase} max)"
            return result

        result["can_research"] = True
        result["remaining"] = lrs.research_remaining

        # Add warning if judge is getting impatient
        if lrs.research_this_phase >= 2:
            result["warning"] = "⚠️ Judge may get impatient with more research"

        return result

    def search_case_law(self, query: str) -> Dict[str, Any]:
        """
        Search for relevant case laws based on query.
        This costs a turn and may irritate the judge if overused.
        """
        result = {
            "success": False,
            "results": [],
            "messages": [],
            "judge_reaction": None,
            "turn_cost": 1
        }

        # Check if can research
        can_research = self.can_do_research()
        if not can_research["can_research"]:
            result["error"] = can_research["reason"]
            return result

        if not self.state.legal_research_state:
            self.initialize_legal_research()

        lrs = self.state.legal_research_state

        # Process search query
        query_lower = query.lower()
        found_cases = []

        # Find matching categories based on keywords
        matching_categories = []
        for category, keywords in RESEARCH_KEYWORDS.items():
            for keyword in keywords:
                if keyword in query_lower:
                    matching_categories.append(category)
                    break

        # If no direct match, try to find any related cases
        if not matching_categories:
            # Default to some general categories based on case type
            matching_categories = ["evidence", "procedure"]

        # Gather results from matching categories
        for category in matching_categories:
            if category in CASE_LAW_DATABASE:
                for case_law in CASE_LAW_DATABASE[category]:
                    # Check if already discovered
                    already_found = any(
                        c.citation == case_law.citation
                        for c in lrs.discovered_cases
                    )
                    if not already_found:
                        # Create a copy with discovery info
                        new_case = CaseLawResult(
                            citation=case_law.citation,
                            case_name=case_law.case_name,
                            court=case_law.court,
                            year=case_law.year,
                            category=case_law.category,
                            relevance=case_law.relevance,
                            key_principle=case_law.key_principle,
                            applicable_facts=case_law.applicable_facts,
                            strength_score=case_law.strength_score,
                            discovered_turn=self.state.turn_number
                        )
                        found_cases.append(new_case)

        # Limit results
        found_cases = found_cases[:4]  # Max 4 results per search

        # Update research state
        lrs.research_this_phase += 1
        lrs.total_research_actions += 1

        # Create research session
        session = ResearchSession(
            search_query=query,
            turn_number=self.state.turn_number,
            results_found=found_cases,
            was_successful=len(found_cases) > 0
        )
        lrs.research_sessions.append(session)
        self.state.last_research_result = session

        # Add discovered cases to state
        lrs.discovered_cases.extend(found_cases)

        # Judge reaction based on research frequency
        judge_msg = self._get_judge_research_reaction(lrs)
        if judge_msg:
            result["messages"].append(judge_msg)
            self.state.messages.append(judge_msg)
            result["judge_reaction"] = judge_msg.content

        # Update confidence (research shows uncertainty)
        if self.state.confidence_meter:
            if lrs.research_this_phase >= 3:
                self.state.confidence_meter.adjust_confidence(-5, "Excessive research")
            elif lrs.research_this_phase == 1:
                # First research is fine
                pass
            else:
                self.state.confidence_meter.adjust_confidence(-2, "Mid-trial research")

        result["success"] = True
        result["results"] = found_cases
        result["research_remaining"] = lrs.research_remaining

        return result

    def _get_judge_research_reaction(self, lrs: LegalResearchState) -> Optional[AgentMessage]:
        """Get judge's reaction to research based on personality and frequency."""
        judge: JudgeAgent = self.agents['judge']

        # Determine reaction type
        reaction_type = "neutral"

        if lrs.research_this_phase >= 3:
            reaction_type = "warning"
            lrs.judge_patience_warnings += 1
        elif lrs.research_this_phase >= 2:
            reaction_type = "impatient"

        # Adjust based on judge personality
        if self.state.judge_state:
            js = self.state.judge_state
            if js.personality.patience < 40:
                # Strict judge gets impatient faster
                if lrs.research_this_phase >= 2:
                    reaction_type = "warning"
                elif lrs.research_this_phase >= 1:
                    reaction_type = "impatient"
            elif js.personality.patience > 70:
                # Patient judge is more tolerant
                if reaction_type == "impatient":
                    reaction_type = "neutral"

        # Get appropriate remark
        if reaction_type in JUDGE_RESEARCH_REMARKS:
            remarks = JUDGE_RESEARCH_REMARKS[reaction_type]
            remark = random.choice(remarks)
            return judge.respond(remark, CourtPhase.EXAMINATION)

        return None

    def cite_case_law(self, citation: str, argument: str = "") -> Dict[str, Any]:
        """
        Cite a discovered case law in your argument.
        """
        result = {
            "success": False,
            "messages": [],
            "score_bonus": 0,
            "judge_reaction": None
        }

        if not self.state.legal_research_state:
            result["error"] = "No research state available"
            return result

        lrs = self.state.legal_research_state

        # Find the case in discovered cases
        case_to_cite = None
        for case in lrs.discovered_cases:
            if case.citation == citation:
                case_to_cite = case
                break

        if not case_to_cite:
            result["error"] = f"Case {citation} not found in your research"
            return result

        if case_to_cite.has_been_cited:
            result["error"] = f"Case {citation} has already been cited"
            return result

        # Mark as cited
        case_to_cite.has_been_cited = True
        lrs.cited_cases.append(citation)

        # Calculate score bonus based on relevance
        relevance_bonuses = {
            ResearchRelevance.HIGHLY_RELEVANT: 15,
            ResearchRelevance.RELEVANT: 10,
            ResearchRelevance.SOMEWHAT_RELEVANT: 5,
            ResearchRelevance.TANGENTIAL: 2
        }
        base_bonus = relevance_bonuses.get(case_to_cite.relevance, 5)

        # Adjust based on argument quality (if provided)
        if argument and len(argument) > 50:
            base_bonus += 3  # Bonus for explaining the citation

        # Adjust based on judge personality
        if self.state.judge_state:
            js = self.state.judge_state
            if js.personality.values_precedent:
                base_bonus *= 1.3  # Judge values citations
            if js.personality.technical_focus > 70:
                base_bonus *= 1.2  # Technical judge appreciates citations

        result["score_bonus"] = base_bonus

        # Update scores
        self.state.score.legal_accuracy += base_bonus * 0.5
        self.state.score.total_points += base_bonus
        lrs.citation_accuracy_score = min(100, lrs.citation_accuracy_score + 5)

        # Update confidence
        if self.state.confidence_meter:
            self.state.confidence_meter.adjust_confidence(5, "Successful citation")

        # Create citation message
        player_side_name = "Petitioner" if self.state.player_side == PlayerSide.PETITIONER else "Respondent"
        citation_statement = (
            f"My Lord, I rely upon the judgment in {case_to_cite.case_name} ({case_to_cite.citation}), "
            f"wherein the Hon'ble {case_to_cite.court} held that {case_to_cite.key_principle}. "
        )
        if argument:
            citation_statement += f"{argument}"

        # Add to messages
        player_msg = AgentMessage(
            role=AgentRole.PETITIONER_LAWYER if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_LAWYER,
            agent_name=f"Adv. ({player_side_name})",
            content=citation_statement,
            phase=CourtPhase.ARGUMENTS
        )
        result["messages"].append(player_msg)
        self.state.messages.append(player_msg)

        # Judge acknowledges (sometimes appreciatively)
        judge: JudgeAgent = self.agents['judge']
        if case_to_cite.relevance == ResearchRelevance.HIGHLY_RELEVANT:
            reaction = random.choice(JUDGE_RESEARCH_REMARKS["appreciative"])
            lrs.judge_impressed_by_research = True
        else:
            reaction = random.choice(JUDGE_RESEARCH_REMARKS["neutral"])

        judge_msg = judge.respond(reaction, CourtPhase.ARGUMENTS)
        result["messages"].append(judge_msg)
        self.state.messages.append(judge_msg)
        result["judge_reaction"] = reaction

        result["success"] = True
        result["cited_case"] = case_to_cite

        return result

    def get_discovered_cases(self) -> List[CaseLawResult]:
        """Get all discovered case laws."""
        if not self.state.legal_research_state:
            return []
        return self.state.legal_research_state.discovered_cases

    def get_uncited_cases(self) -> List[CaseLawResult]:
        """Get discovered cases that haven't been cited yet."""
        if not self.state.legal_research_state:
            return []
        return [c for c in self.state.legal_research_state.discovered_cases
                if not c.has_been_cited]

    def get_research_display(self) -> Dict[str, Any]:
        """Get research state info for UI display."""
        if not self.state.legal_research_state:
            return {"active": False}

        lrs = self.state.legal_research_state

        return {
            "active": True,
            "can_research": lrs.can_research,
            "research_remaining": lrs.research_remaining,
            "research_this_phase": lrs.research_this_phase,
            "total_research": lrs.total_research_actions,
            "discovered_count": len(lrs.discovered_cases),
            "cited_count": len(lrs.cited_cases),
            "judge_warnings": lrs.judge_patience_warnings,
            "quality_score": lrs.research_quality_score,
            "citation_accuracy": lrs.citation_accuracy_score,
            "judge_impressed": lrs.judge_impressed_by_research
        }

    def get_research_tips(self) -> List[str]:
        """Get tips for the research system."""
        tips = []

        if not self.state.legal_research_state:
            return ["📚 Use legal research to find supporting case laws"]

        lrs = self.state.legal_research_state

        if lrs.research_remaining > 0:
            tips.append(f"📖 {lrs.research_remaining} research action(s) remaining this phase")
        else:
            tips.append("📕 Research limit reached for this phase")

        uncited = self.get_uncited_cases()
        if uncited:
            tips.append(f"📋 {len(uncited)} discovered case(s) available to cite")

        if lrs.judge_patience_warnings > 0:
            tips.append("⚠️ Judge is getting impatient with research breaks")

        if lrs.judge_impressed_by_research:
            tips.append("✅ Judge was impressed by your citation!")

        # Suggest when to cite
        if uncited and self.state.phase == GamePhase.FINAL_ARGUMENTS:
            tips.append("💡 Final arguments - cite your key precedents now!")

        return tips

    def reset_phase_research(self) -> None:
        """Reset research count for new phase."""
        if self.state.legal_research_state:
            self.state.legal_research_state.research_this_phase = 0

    # ========================================
    # SIDEBAR/CHAMBER CONFERENCE METHODS
    # ========================================

    def initialize_sidebar_system(self) -> None:
        """Initialize the sidebar conference system."""
        limits = {
            "easy": 3,
            "medium": 2,
            "hard": 1
        }
        max_sidebars = limits.get(self.difficulty, 2)

        self.state.sidebar_state = SidebarState(
            max_sidebars_per_phase=max_sidebars
        )

    def can_request_sidebar(self) -> Dict[str, Any]:
        """Check if player can request a sidebar conference."""
        result = {
            "can_request": False,
            "reason": "",
            "remaining": 0,
            "warning": None
        }

        if not self.state.sidebar_enabled:
            result["reason"] = "Sidebar conferences are disabled"
            return result

        if not self.state.sidebar_state:
            self.initialize_sidebar_system()

        sbs = self.state.sidebar_state

        # Check if already in a sidebar
        if self.state.in_sidebar_conference:
            result["reason"] = "Already in a sidebar conference"
            return result

        # Check phase limits
        if not sbs.can_request_sidebar:
            result["reason"] = f"Sidebar limit reached for this phase ({sbs.max_sidebars_per_phase} max)"
            return result

        # Check judge patience
        if sbs.judge_sidebar_patience < 30:
            result["warning"] = "⚠️ Judge's patience is very low - sidebar may be denied"

        result["can_request"] = True
        result["remaining"] = sbs.sidebars_remaining

        return result

    def request_sidebar(self, request_type: SidebarRequestType, reason: str,
                       argument: str = "", evidence_id: Optional[str] = None,
                       witness_id: Optional[str] = None,
                       adjournment_reason: Optional[AdjournmentReason] = None,
                       adjournment_duration: Optional[str] = None) -> Dict[str, Any]:
        """
        Request a sidebar conference with the judge.
        """
        result = {
            "success": False,
            "granted": False,
            "messages": [],
            "outcome": None,
            "judge_remarks": "",
            "conditions": [],
            "turn_cost": 1
        }

        # Check if can request
        can_request = self.can_request_sidebar()
        if not can_request["can_request"]:
            result["error"] = can_request["reason"]
            return result

        if not self.state.sidebar_state:
            self.initialize_sidebar_system()

        sbs = self.state.sidebar_state

        # Create the request
        request_id = f"sidebar_{self.state.turn_number}_{request_type.value}"
        request = SidebarRequest(
            request_id=request_id,
            request_type=request_type,
            turn_number=self.state.turn_number,
            reason=reason,
            supporting_argument=argument,
            evidence_id=evidence_id,
            witness_id=witness_id,
            adjournment_reason=adjournment_reason,
            adjournment_duration=adjournment_duration
        )

        # Determine turn cost
        turn_cost = SIDEBAR_REQUEST_OPTIONS.get(request_type, {}).get("turn_cost", 1)
        result["turn_cost"] = turn_cost

        # Judge evaluates the request
        outcome, judge_remarks, conditions = self._evaluate_sidebar_request(request)

        # Create conference record
        conference = SidebarConference(
            conference_id=f"conf_{request_id}",
            request=request,
            outcome=outcome,
            judge_remarks=judge_remarks,
            conditions=conditions,
            turn_cost=turn_cost
        )

        # Update state
        sbs.sidebars_this_phase += 1
        sbs.total_sidebars += 1
        sbs.conferences.append(conference)
        self.state.last_sidebar_result = conference

        # Reduce judge patience
        patience_reduction = 15 if outcome == SidebarOutcome.DENIED else 10
        sbs.judge_sidebar_patience = max(0, sbs.judge_sidebar_patience - patience_reduction)

        # Generate messages
        # Player approaches bench
        player_side_name = "Petitioner" if self.state.player_side == PlayerSide.PETITIONER else "Respondent"
        approach_msg = AgentMessage(
            role=AgentRole.PETITIONER_LAWYER if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_LAWYER,
            agent_name=f"Adv. ({player_side_name})",
            content=f"My Lord, may I approach the bench? {reason}",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(approach_msg)
        self.state.messages.append(approach_msg)

        # Judge response
        judge: JudgeAgent = self.agents['judge']
        judge_msg = judge.respond(judge_remarks, CourtPhase.EXAMINATION)
        result["messages"].append(judge_msg)
        self.state.messages.append(judge_msg)

        # Handle specific outcomes
        if outcome in [SidebarOutcome.GRANTED, SidebarOutcome.PARTIALLY_GRANTED]:
            result["granted"] = True
            self.state.in_sidebar_conference = True

            # Process based on request type
            self._process_sidebar_outcome(request, outcome, conference, result)

        # Update scores and confidence
        self._apply_sidebar_impacts(conference, result)

        result["success"] = True
        result["outcome"] = outcome.value
        result["judge_remarks"] = judge_remarks
        result["conditions"] = conditions

        return result

    def _evaluate_sidebar_request(self, request: SidebarRequest) -> tuple:
        """Evaluate a sidebar request and determine outcome."""
        sbs = self.state.sidebar_state

        # Base probability of granting
        grant_probability = 0.6

        # Adjust based on request type
        type_adjustments = {
            SidebarRequestType.PROCEDURAL_CLARIFICATION: 0.3,  # Almost always granted
            SidebarRequestType.WITNESS_AVAILABILITY: 0.1,
            SidebarRequestType.REQUEST_ADJOURNMENT: -0.1,
            SidebarRequestType.SETTLEMENT_DISCUSSION: 0.2,
            SidebarRequestType.EXCLUDE_EVIDENCE: -0.1,
            SidebarRequestType.MISTRIAL_MOTION: -0.3,
        }
        grant_probability += type_adjustments.get(request.request_type, 0)

        # Adjust based on judge personality
        if self.state.judge_state:
            js = self.state.judge_state
            if js.personality.patience > 60:
                grant_probability += 0.15
            elif js.personality.patience < 40:
                grant_probability -= 0.2

            # Formal judges may grant more procedural requests
            if js.personality.formality > 60 and request.request_type == SidebarRequestType.PROCEDURAL_CLARIFICATION:
                grant_probability += 0.2

        # Adjust based on sidebar history
        if sbs.sidebars_this_phase >= 1:
            grant_probability -= 0.15 * sbs.sidebars_this_phase

        # Adjust based on judge patience
        grant_probability *= (sbs.judge_sidebar_patience / 100)

        # Argument quality bonus
        if request.supporting_argument and len(request.supporting_argument) > 50:
            grant_probability += 0.1

        # Determine outcome
        roll = random.random()
        conditions = []

        if roll < grant_probability:
            outcome = SidebarOutcome.GRANTED
            remarks_key = "grant"
        elif roll < grant_probability + 0.15:
            outcome = SidebarOutcome.PARTIALLY_GRANTED
            remarks_key = "partial"
            conditions.append("Limited time allowed for discussion")
        else:
            outcome = SidebarOutcome.DENIED
            remarks_key = "deny"

        # Get judge remarks
        if sbs.sidebars_this_phase >= 2:
            remarks_key = "impatient"

        # Special handling for specific request types
        if request.request_type == SidebarRequestType.SETTLEMENT_DISCUSSION and outcome == SidebarOutcome.GRANTED:
            remarks_key = "settlement"
        elif request.request_type == SidebarRequestType.REQUEST_ADJOURNMENT:
            if outcome == SidebarOutcome.GRANTED:
                remarks_key = "adjournment_grant"
            else:
                remarks_key = "adjournment_deny"
        elif request.request_type == SidebarRequestType.EXCLUDE_EVIDENCE:
            if outcome == SidebarOutcome.GRANTED:
                remarks_key = "evidence_exclusion_grant"
            else:
                remarks_key = "evidence_exclusion_deny"

        remarks = random.choice(SIDEBAR_JUDGE_RESPONSES.get(remarks_key, SIDEBAR_JUDGE_RESPONSES["grant"]))

        return outcome, remarks, conditions

    def _process_sidebar_outcome(self, request: SidebarRequest, outcome: SidebarOutcome,
                                conference: SidebarConference, result: Dict[str, Any]) -> None:
        """Process the specific outcome of a sidebar request."""
        sbs = self.state.sidebar_state

        if request.request_type == SidebarRequestType.EXCLUDE_EVIDENCE:
            if outcome == SidebarOutcome.GRANTED and request.evidence_id:
                # Mark evidence as excluded
                item = self.state.evidence_locker.get_evidence_by_id(request.evidence_id)
                if item:
                    item.status = EvidenceStatus.EXCLUDED
                    sbs.evidence_exclusions_granted += 1
                    result["evidence_excluded"] = True
                    result["excluded_evidence_id"] = request.evidence_id
            sbs.evidence_exclusion_requests += 1

        elif request.request_type == SidebarRequestType.REQUEST_ADJOURNMENT:
            if outcome == SidebarOutcome.GRANTED:
                sbs.adjournments_granted += 1
                sbs.current_adjournment = True
                result["adjournment_granted"] = True
                result["adjournment_duration"] = request.adjournment_duration or "brief"

                # Adjournment can restore some confidence
                if self.state.confidence_meter:
                    self.state.confidence_meter.adjust_confidence(10, "Adjournment to collect thoughts")
            sbs.adjournments_requested += 1

        elif request.request_type == SidebarRequestType.SETTLEMENT_DISCUSSION:
            if outcome == SidebarOutcome.GRANTED:
                result["settlement_discussion"] = True
                # Create a settlement opportunity
                result["can_make_offer"] = True

    def _apply_sidebar_impacts(self, conference: SidebarConference, result: Dict[str, Any]) -> None:
        """Apply score and confidence impacts from sidebar."""
        outcome = conference.outcome

        # Score impacts
        if outcome == SidebarOutcome.GRANTED:
            conference.score_impact = 5
            self.state.score.total_points += 5
        elif outcome == SidebarOutcome.DENIED:
            conference.score_impact = -3
            self.state.score.total_points -= 3
        elif outcome == SidebarOutcome.PARTIALLY_GRANTED:
            conference.score_impact = 2
            self.state.score.total_points += 2

        # Confidence impacts
        if self.state.confidence_meter:
            if outcome == SidebarOutcome.GRANTED:
                self.state.confidence_meter.adjust_confidence(5, "Sidebar granted")
                conference.confidence_impact = 5
            elif outcome == SidebarOutcome.DENIED:
                self.state.confidence_meter.adjust_confidence(-8, "Sidebar denied")
                conference.confidence_impact = -8

        result["score_impact"] = conference.score_impact
        result["confidence_impact"] = conference.confidence_impact

    def end_sidebar_conference(self) -> Dict[str, Any]:
        """End the current sidebar conference."""
        result = {"success": False, "messages": []}

        if not self.state.in_sidebar_conference:
            result["error"] = "Not currently in a sidebar conference"
            return result

        self.state.in_sidebar_conference = False

        # Judge announces return to proceedings
        judge: JudgeAgent = self.agents['judge']
        resume_remarks = [
            "Let us return to open proceedings.",
            "The sidebar is concluded. We are back on the record.",
            "Very well. Let us continue with the matter at hand.",
            "The conference is concluded. Proceed, Counsel."
        ]
        resume_msg = judge.respond(random.choice(resume_remarks), CourtPhase.EXAMINATION)
        result["messages"].append(resume_msg)
        self.state.messages.append(resume_msg)

        result["success"] = True
        return result

    def make_settlement_offer(self, terms: str, amount: Optional[float] = None,
                             conditions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Make a settlement offer during sidebar."""
        result = {"success": False, "messages": [], "offer": None}

        if not self.state.in_sidebar_conference:
            result["error"] = "Can only make settlement offers during sidebar"
            return result

        if not self.state.sidebar_state:
            result["error"] = "Sidebar system not initialized"
            return result

        sbs = self.state.sidebar_state

        # Create the offer
        offer = SettlementOffer(
            offer_id=f"offer_{self.state.turn_number}",
            offering_side=self.state.player_side,
            turn_number=self.state.turn_number,
            terms=terms,
            amount=amount,
            conditions=conditions or []
        )

        sbs.settlement_offers.append(offer)

        # Opponent AI considers the offer
        acceptance_probability = self._evaluate_settlement_offer(offer)
        roll = random.random()

        if roll < acceptance_probability:
            offer.is_accepted = True
            sbs.settlement_reached = True
            sbs.settlement_terms = terms
            result["accepted"] = True
            result["messages"].append(self._create_settlement_acceptance_message(offer))
        elif roll < acceptance_probability + 0.3:
            # Counter offer
            offer.is_countered = True
            counter_terms = self._generate_counter_offer(offer)
            offer.counter_terms = counter_terms
            result["countered"] = True
            result["counter_terms"] = counter_terms
            result["messages"].append(self._create_counter_offer_message(counter_terms))
        else:
            offer.is_rejected = True
            result["rejected"] = True
            result["messages"].append(self._create_settlement_rejection_message())

        result["success"] = True
        result["offer"] = offer

        return result

    def _evaluate_settlement_offer(self, offer: SettlementOffer) -> float:
        """Evaluate how likely opponent is to accept settlement."""
        # Base probability depends on game state
        base_probability = 0.3

        # Better scores mean less likely to settle
        player_score = self.state.score.total_points
        if player_score > 100:
            base_probability -= 0.1
        elif player_score < 50:
            base_probability += 0.15

        # Late game more likely to settle
        if self.state.phase in [GamePhase.FINAL_ARGUMENTS, GamePhase.RESPONDENT_WITNESS_EXAM]:
            base_probability += 0.1

        # Good terms increase probability
        if offer.amount and offer.amount > 0:
            base_probability += 0.1

        return min(0.6, max(0.1, base_probability))

    def _generate_counter_offer(self, original: SettlementOffer) -> str:
        """Generate a counter offer from opponent."""
        counters = [
            "We would consider settlement if the amount is increased by 25%.",
            "The respondent may accept with additional terms regarding costs.",
            "A settlement may be possible if the petitioner agrees to mutual release.",
            "We counter-propose that each party bear their own costs.",
        ]
        return random.choice(counters)

    def _create_settlement_acceptance_message(self, offer: SettlementOffer) -> AgentMessage:
        """Create message for settlement acceptance."""
        opponent: LawyerAgent = self.agents['opponent']
        return opponent.respond(
            f"My Lord, the respondent accepts the settlement terms proposed. "
            f"We agree to: {offer.terms}",
            CourtPhase.SETTLEMENT
        )

    def _create_counter_offer_message(self, counter_terms: str) -> AgentMessage:
        """Create message for counter offer."""
        opponent: LawyerAgent = self.agents['opponent']
        return opponent.respond(
            f"My Lord, while we appreciate the offer, {counter_terms}",
            CourtPhase.SETTLEMENT
        )

    def _create_settlement_rejection_message(self) -> AgentMessage:
        """Create message for settlement rejection."""
        opponent: LawyerAgent = self.agents['opponent']
        rejections = [
            "My Lord, the respondent cannot accept these terms and wishes to proceed with trial.",
            "We respectfully decline the offer and will present our case fully.",
            "The offer is rejected. We believe the court should decide this matter.",
        ]
        return opponent.respond(random.choice(rejections), CourtPhase.SETTLEMENT)

    def get_sidebar_display(self) -> Dict[str, Any]:
        """Get sidebar state info for UI display."""
        if not self.state.sidebar_state:
            return {"active": False}

        sbs = self.state.sidebar_state

        return {
            "active": True,
            "can_request": sbs.can_request_sidebar,
            "sidebars_remaining": sbs.sidebars_remaining,
            "sidebars_this_phase": sbs.sidebars_this_phase,
            "total_sidebars": sbs.total_sidebars,
            "in_conference": self.state.in_sidebar_conference,
            "judge_patience": sbs.judge_sidebar_patience,
            "settlement_reached": sbs.settlement_reached,
            "adjournments_granted": sbs.adjournments_granted,
            "evidence_exclusions": sbs.evidence_exclusions_granted,
            "settlement_offers": len(sbs.settlement_offers)
        }

    def get_sidebar_tips(self) -> List[str]:
        """Get tips for the sidebar system."""
        tips = []

        if not self.state.sidebar_state:
            return ["⚖️ Request a sidebar for private conferences with the judge"]

        sbs = self.state.sidebar_state

        if sbs.sidebars_remaining > 0:
            tips.append(f"📋 {sbs.sidebars_remaining} sidebar request(s) remaining this phase")
        else:
            tips.append("📕 Sidebar limit reached for this phase")

        if sbs.judge_sidebar_patience < 50:
            tips.append("⚠️ Judge's patience with sidebars is low")

        if self.state.in_sidebar_conference:
            tips.append("🔒 Currently in sidebar - end conference to continue trial")

        # Strategic tips
        if self.state.phase == GamePhase.FINAL_ARGUMENTS and not sbs.settlement_reached:
            tips.append("💡 Consider settlement discussion before final judgment")

        if len(sbs.settlement_offers) > 0 and not sbs.settlement_reached:
            tips.append("🤝 Previous settlement offer was not accepted")

        return tips

    def reset_phase_sidebars(self) -> None:
        """Reset sidebar count for new phase."""
        if self.state.sidebar_state:
            self.state.sidebar_state.sidebars_this_phase = 0
            # Restore some judge patience
            self.state.sidebar_state.judge_sidebar_patience = min(
                100,
                self.state.sidebar_state.judge_sidebar_patience + 20
            )

    # ========================================
    # EDUCATIONAL FEATURES SYSTEM
    # ========================================

    def initialize_education_system(self) -> None:
        """Initialize the educational features system."""
        if not self.state.education_enabled:
            return

        # Use default constructor - all fields have default values
        self.state.education_state = EducationState()

    def detect_mistake(self, player_input: str, context: str = "examination") -> Optional[LearningMoment]:
        """
        Detect if the player made a legal mistake in their input.
        Returns a LearningMoment if a mistake is detected.
        """
        if not self.state.education_enabled or not self.state.education_state:
            return None

        if not self.state.education_state.show_flashcards:
            return None

        # Check if we've shown too many flashcards this session
        if self.state.education_state.flashcards_shown_this_session >= \
           self.state.education_state.max_flashcards_per_session:
            return None

        input_lower = player_input.lower()
        detected_category = None
        matched_pattern = None

        # Check against mistake patterns
        import re
        for category, patterns in MISTAKE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, input_lower):
                    # Determine if this is actually a mistake based on context
                    if self._is_mistake_in_context(category, context):
                        detected_category = category
                        matched_pattern = pattern
                        break
            if detected_category:
                break

        if not detected_category:
            return None

        # Find the appropriate legal principle to teach
        principle = self._get_principle_for_mistake(detected_category)
        if not principle:
            return None

        # Create learning moment
        learning_moment = LearningMoment(
            trigger=player_input[:100],  # Truncate long inputs
            mistake_category=detected_category,
            principle=principle,
            context=context,
            player_action=player_input[:200],
            correct_alternative=principle.example_correct,
            explanation=self._generate_contextual_explanation(principle, player_input)
        )

        # Track the mistake
        if detected_category.value not in self.state.education_state.progress.mistakes_made:
            self.state.education_state.progress.mistakes_made[detected_category.value] = 0
        self.state.education_state.progress.mistakes_made[detected_category.value] += 1

        # Reset learning streak on mistake
        self.state.education_state.progress.learning_streak = 0

        return learning_moment

    def _is_mistake_in_context(self, category: MistakeCategory, context: str) -> bool:
        """Determine if the detected pattern is actually a mistake in the given context."""
        # Leading questions are allowed in cross-examination
        if category == MistakeCategory.LEADING_QUESTION:
            if context in ["cross_examination", "hostile_witness"]:
                return False  # Leading questions are allowed here
            return True  # Mistake in examination-in-chief

        # Most other mistakes are context-independent
        return True

    def _get_principle_for_mistake(self, category: MistakeCategory) -> Optional[LegalPrinciple]:
        """Get the most appropriate legal principle to teach for a given mistake category."""
        # Map categories to primary principles
        category_to_principle = {
            MistakeCategory.LEADING_QUESTION: "leading_examination",
            MistakeCategory.HEARSAY: "hearsay_basic",
            MistakeCategory.RELEVANCE: "relevance_basic",
            MistakeCategory.SPECULATION: "speculation",
            MistakeCategory.COMPOUND_QUESTION: "compound_question",
            MistakeCategory.ARGUMENTATIVE: "argumentative_question",
            MistakeCategory.IMPROPER_FOUNDATION: "improper_foundation",
            MistakeCategory.BEST_EVIDENCE: "best_evidence",
            MistakeCategory.PRIVILEGE: "privilege_basic",
            MistakeCategory.CHARACTER_EVIDENCE: "character_evidence",
            MistakeCategory.IMPROPER_IMPEACHMENT: "impeachment",
            MistakeCategory.PROCEDURE_ERROR: "examination_order",
            MistakeCategory.ETIQUETTE_VIOLATION: "addressing_court",
            MistakeCategory.EVIDENCE_HANDLING: "evidence_marking",
            MistakeCategory.ASSUMES_FACTS: "assumes_facts",
        }

        principle_id = category_to_principle.get(category)
        if principle_id and principle_id in LEGAL_PRINCIPLES_DATABASE:
            return LEGAL_PRINCIPLES_DATABASE[principle_id]

        # Fallback: search for any principle with this category
        for principle in LEGAL_PRINCIPLES_DATABASE.values():
            if principle.category == category:
                return principle

        return None

    def _generate_contextual_explanation(self, principle: LegalPrinciple, player_input: str) -> str:
        """Generate a contextual explanation based on the principle and what the player said."""
        base_explanation = principle.explanation

        # Add context based on the specific input
        if len(player_input) > 20:
            input_preview = player_input[:50] + "..." if len(player_input) > 50 else player_input
            contextual = f"\n\nIn your statement \"{input_preview}\", {principle.short_rule.lower()}"
            return base_explanation + contextual

        return base_explanation

    def trigger_learning_moment(self, learning_moment: LearningMoment) -> Dict[str, Any]:
        """
        Trigger a learning moment to show to the player.
        """
        if not self.state.education_state:
            return {"triggered": False, "reason": "Education system not initialized"}

        self.state.pending_learning_moment = learning_moment
        self.state.education_state.pending_flashcard = learning_moment
        self.state.education_state.flashcards_shown_this_session += 1
        self.state.education_state.progress.flashcards_viewed += 1

        # Track that player has seen this principle
        principle_id = learning_moment.principle.principle_id
        if principle_id not in self.state.education_state.progress.principles_learned:
            self.state.education_state.progress.principles_learned.append(principle_id)

        return {
            "triggered": True,
            "learning_moment": learning_moment,
            "principle": learning_moment.principle,
            "flashcards_remaining": (
                self.state.education_state.max_flashcards_per_session -
                self.state.education_state.flashcards_shown_this_session
            )
        }

    def acknowledge_learning_moment(self) -> Dict[str, Any]:
        """
        Called when player acknowledges (dismisses) a learning moment.
        """
        if not self.state.education_state or not self.state.pending_learning_moment:
            return {"acknowledged": False}

        learning_moment = self.state.pending_learning_moment
        self.state.learning_moments_shown.append(learning_moment)

        # Clear pending
        self.state.pending_learning_moment = None
        self.state.education_state.pending_flashcard = None

        return {
            "acknowledged": True,
            "principle_id": learning_moment.principle.principle_id,
            "category": learning_moment.mistake_category.value,
            "total_flashcards_viewed": self.state.education_state.progress.flashcards_viewed
        }

    def mark_correct_after_learning(self, principle_id: str) -> Dict[str, Any]:
        """
        Called when the player demonstrates correct understanding after learning a principle.
        This helps track learning progress.
        """
        if not self.state.education_state:
            return {"recorded": False}

        progress = self.state.education_state.progress
        progress.correct_after_learning += 1
        progress.learning_streak += 1

        # Check if player has mastered this principle (correct 3 times after learning)
        # Track mastery per principle
        if not hasattr(progress, '_mastery_count'):
            progress._mastery_count = {}

        if principle_id not in progress._mastery_count:
            progress._mastery_count[principle_id] = 0

        progress._mastery_count[principle_id] += 1

        mastered = False
        if progress._mastery_count[principle_id] >= 3:
            if principle_id not in progress.principles_mastered:
                progress.principles_mastered.append(principle_id)
                mastered = True

        return {
            "recorded": True,
            "principle_id": principle_id,
            "correct_count": progress._mastery_count.get(principle_id, 0),
            "mastered": mastered,
            "learning_streak": progress.learning_streak
        }

    def get_education_display(self) -> Dict[str, Any]:
        """Get education state info for UI display."""
        if not self.state.education_state:
            return {"active": False}

        es = self.state.education_state
        progress = es.progress

        # Calculate mastery percentage
        total_principles = len(LEGAL_PRINCIPLES_DATABASE)
        learned_count = len(progress.principles_learned)
        mastered_count = len(progress.principles_mastered)

        # Get most common mistake categories
        mistake_summary = sorted(
            progress.mistakes_made.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        return {
            "active": True,
            "education_enabled": es.education_enabled,
            "show_flashcards": es.show_flashcards,
            "has_pending_flashcard": es.pending_flashcard is not None,
            "pending_flashcard": es.pending_flashcard,
            "flashcards_shown": es.flashcards_shown_this_session,
            "flashcards_limit": es.max_flashcards_per_session,
            "flashcards_remaining": es.max_flashcards_per_session - es.flashcards_shown_this_session,
            "progress": {
                "total_principles": total_principles,
                "principles_learned": learned_count,
                "principles_mastered": mastered_count,
                "learning_percentage": (learned_count / total_principles * 100) if total_principles > 0 else 0,
                "mastery_percentage": (mastered_count / total_principles * 100) if total_principles > 0 else 0,
                "flashcards_viewed": progress.flashcards_viewed,
                "correct_after_learning": progress.correct_after_learning,
                "learning_streak": progress.learning_streak
            },
            "top_mistakes": mistake_summary,
            "total_mistakes": sum(progress.mistakes_made.values())
        }

    def get_learning_moment_display(self) -> Optional[Dict[str, Any]]:
        """Get the current pending learning moment for UI display."""
        if not self.state.pending_learning_moment:
            return None

        lm = self.state.pending_learning_moment
        principle = lm.principle

        # Determine severity based on category
        severity_colors = {
            MistakeCategory.LEADING_QUESTION: "orange",
            MistakeCategory.HEARSAY: "red",
            MistakeCategory.RELEVANCE: "yellow",
            MistakeCategory.SPECULATION: "orange",
            MistakeCategory.COMPOUND_QUESTION: "yellow",
            MistakeCategory.ARGUMENTATIVE: "orange",
            MistakeCategory.IMPROPER_FOUNDATION: "red",
            MistakeCategory.BEST_EVIDENCE: "red",
            MistakeCategory.PRIVILEGE: "red",
            MistakeCategory.CHARACTER_EVIDENCE: "orange",
            MistakeCategory.IMPROPER_IMPEACHMENT: "orange",
            MistakeCategory.PROCEDURE_ERROR: "yellow",
            MistakeCategory.ETIQUETTE_VIOLATION: "blue",
            MistakeCategory.EVIDENCE_HANDLING: "orange",
            MistakeCategory.ASSUMES_FACTS: "orange",
            MistakeCategory.BEYOND_SCOPE: "yellow",
        }

        # Get level badge
        level_badges = {
            LegalPrincipleLevel.BASIC: "Fundamental",
            LegalPrincipleLevel.INTERMEDIATE: "Intermediate",
            LegalPrincipleLevel.ADVANCED: "Advanced"
        }

        return {
            "title": f"Learning Moment: {principle.title}",
            "category": lm.mistake_category.value.replace("_", " ").title(),
            "category_raw": lm.mistake_category.value,
            "severity_color": severity_colors.get(lm.mistake_category, "gray"),
            "level": principle.level.value,
            "level_badge": level_badges.get(principle.level, ""),
            "legal_section": principle.legal_section,
            "explanation": lm.explanation,
            "short_rule": principle.short_rule,
            "example_wrong": principle.example_wrong,
            "example_correct": principle.example_correct,
            "tip": principle.tip,
            "related_principles": principle.related_principles,
            "player_action": lm.player_action,
            "context": lm.context.replace("_", " ").title()
        }

    def get_principle_info(self, principle_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific legal principle."""
        if principle_id not in LEGAL_PRINCIPLES_DATABASE:
            return None

        p = LEGAL_PRINCIPLES_DATABASE[principle_id]

        return {
            "principle_id": p.principle_id,
            "title": p.title,
            "category": p.category.value,
            "level": p.level.value,
            "legal_section": p.legal_section,
            "explanation": p.explanation,
            "short_rule": p.short_rule,
            "example_wrong": p.example_wrong,
            "example_correct": p.example_correct,
            "tip": p.tip,
            "related_principles": p.related_principles
        }

    def get_all_principles_by_category(self) -> Dict[str, List[Dict[str, Any]]]:
        """Get all legal principles organized by category for reference."""
        categorized = {}

        for principle in LEGAL_PRINCIPLES_DATABASE.values():
            category = principle.category.value
            if category not in categorized:
                categorized[category] = []

            categorized[category].append({
                "principle_id": principle.principle_id,
                "title": principle.title,
                "level": principle.level.value,
                "short_rule": principle.short_rule
            })

        return categorized

    def toggle_education_flashcards(self, enabled: bool) -> Dict[str, Any]:
        """Toggle whether flashcards are shown."""
        if not self.state.education_state:
            return {"toggled": False, "reason": "Education system not initialized"}

        self.state.education_state.show_flashcards = enabled

        return {
            "toggled": True,
            "flashcards_enabled": enabled
        }

    def get_education_tips(self) -> List[str]:
        """Get tips related to the education system."""
        tips = []

        if not self.state.education_state:
            return ["Enable educational features to learn legal principles while playing!"]

        es = self.state.education_state
        progress = es.progress

        # General tips
        if progress.flashcards_viewed == 0:
            tips.append("Learning moments will appear when you make common legal mistakes")

        if progress.learning_streak >= 3:
            tips.append(f"Learning streak: {progress.learning_streak} correct actions!")

        if len(progress.principles_mastered) > 0:
            tips.append(f"You've mastered {len(progress.principles_mastered)} legal principle(s)")

        # Mistake-specific tips
        if progress.mistakes_made:
            top_mistake = max(progress.mistakes_made.items(), key=lambda x: x[1])
            category_name = top_mistake[0].replace("_", " ")
            tips.append(f"Focus area: {category_name} ({top_mistake[1]} occurrences)")

        # Flashcard availability
        remaining = es.max_flashcards_per_session - es.flashcards_shown_this_session
        if remaining <= 3 and remaining > 0:
            tips.append(f"Only {remaining} learning moment(s) remaining this session")
        elif remaining == 0:
            tips.append("Flashcard limit reached - keep practicing what you've learned!")

        return tips

    def check_action_for_mistakes(self, action_text: str, action_type: str) -> Dict[str, Any]:
        """
        Check a player action for potential legal mistakes and trigger learning moments.
        This is the main entry point to call when processing player actions.
        """
        result = {
            "mistake_detected": False,
            "learning_moment_triggered": False,
            "learning_moment": None
        }

        if not self.state.education_enabled:
            return result

        # Determine context from action type
        context_map = {
            "examine_witness": "examination_in_chief",
            "cross_examine": "cross_examination",
            "question": "examination",
            "present_evidence": "evidence_handling",
            "make_argument": "argument",
            "object": "objection",
            "opening_statement": "opening",
            "closing_argument": "closing"
        }
        context = context_map.get(action_type, "general")

        # Detect mistake
        learning_moment = self.detect_mistake(action_text, context)

        if learning_moment:
            result["mistake_detected"] = True
            result["mistake_category"] = learning_moment.mistake_category.value

            # Trigger the learning moment
            trigger_result = self.trigger_learning_moment(learning_moment)

            if trigger_result["triggered"]:
                result["learning_moment_triggered"] = True
                result["learning_moment"] = learning_moment

        return result

    # ========================================
    # POST-GAME ANALYSIS SYSTEM
    # ========================================

    def initialize_analysis_system(self) -> None:
        """Initialize the post-game analysis tracking system."""
        if not self.state.analysis_enabled:
            return

        self.state.analysis_state = AnalysisState(
            event_log=[],
            turning_points=[],
            witnesses_examined={},
            cross_examinations={},
            evidence_presented_successfully=[],
            evidence_excluded=[],
            evidence_challenged=[],
            objection_history=[],
            judge_patience_history=[],
            confidence_peaks=[],
            confidence_lows=[],
            potential_missed_opportunities=[],
            cases_cited=[],
            research_effectiveness={}
        )

    def log_game_event(
        self,
        event_type: str,
        description: str,
        outcome: str,
        score_change: int = 0,
        player_action: Optional[str] = None,
        ai_response: Optional[str] = None,
        witness_involved: Optional[str] = None,
        evidence_involved: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Log a game event for later analysis."""
        if not self.state.analysis_state:
            return

        event = GameEventLog(
            turn_number=self.state.turn_number,
            phase=self.state.phase.value,
            event_type=event_type,
            description=description,
            outcome=outcome,
            score_change=score_change,
            player_action=player_action,
            ai_response=ai_response,
            witness_involved=witness_involved,
            evidence_involved=evidence_involved,
            metadata=metadata or {}
        )
        self.state.analysis_state.event_log.append(event)

    def record_turning_point(
        self,
        point_type: TurningPointType,
        description: str,
        impact: str,
        impact_score: int,
        witness: Optional[str] = None,
        evidence: Optional[str] = None,
        player_action: Optional[str] = None
    ) -> None:
        """Record a key turning point in the trial."""
        if not self.state.analysis_state:
            return

        turning_point = TurningPoint(
            turn_number=self.state.turn_number,
            point_type=point_type,
            description=description,
            impact=impact,
            impact_score=impact_score,
            phase=self.state.phase.value,
            involved_witness=witness,
            involved_evidence=evidence,
            player_action=player_action
        )
        self.state.analysis_state.turning_points.append(turning_point)

    def record_missed_opportunity(
        self,
        description: str,
        what_could_have_been_done: str,
        potential_impact: str,
        category: AnalysisCategory
    ) -> None:
        """Record a missed opportunity for the analysis."""
        if not self.state.analysis_state:
            return

        self.state.analysis_state.potential_missed_opportunities.append({
            "turn_number": self.state.turn_number,
            "phase": self.state.phase.value,
            "description": description,
            "what_could_have_been_done": what_could_have_been_done,
            "potential_impact": potential_impact,
            "category": category.value
        })

    def track_objection(self, objection_type: str, sustained: bool, context: str) -> None:
        """Track objection for analysis."""
        if not self.state.analysis_state:
            return

        self.state.analysis_state.objection_history.append({
            "turn": self.state.turn_number,
            "type": objection_type,
            "sustained": sustained,
            "context": context,
            "phase": self.state.phase.value
        })

        # Check if this is a turning point
        if sustained:
            self.record_turning_point(
                TurningPointType.OBJECTION_SUSTAINED,
                f"Objection ({objection_type}) sustained",
                "Successfully blocked opposing counsel's improper question/evidence",
                impact_score=3,
                player_action=f"Objected: {objection_type}"
            )
        else:
            # Failed objection might be a negative turning point
            if len([o for o in self.state.analysis_state.objection_history
                   if not o["sustained"]]) >= 2:
                self.record_turning_point(
                    TurningPointType.OBJECTION_OVERRULED,
                    f"Objection ({objection_type}) overruled",
                    "Multiple failed objections may affect credibility",
                    impact_score=-2,
                    player_action=f"Objected: {objection_type}"
                )

    def track_witness_examination(
        self,
        witness_id: str,
        witness_name: str,
        is_cross: bool,
        effectiveness: int
    ) -> None:
        """Track witness examination quality."""
        if not self.state.analysis_state:
            return

        tracking_dict = (self.state.analysis_state.cross_examinations
                        if is_cross else self.state.analysis_state.witnesses_examined)

        if witness_id not in tracking_dict:
            tracking_dict[witness_id] = {
                "name": witness_name,
                "questions_asked": 0,
                "effective_questions": 0,
                "contradictions_found": 0,
                "admissions_obtained": 0,
                "overall_effectiveness": 50
            }

        tracking_dict[witness_id]["questions_asked"] += 1
        if effectiveness > 60:
            tracking_dict[witness_id]["effective_questions"] += 1

        # Update running average
        current = tracking_dict[witness_id]["overall_effectiveness"]
        tracking_dict[witness_id]["overall_effectiveness"] = int(
            (current + effectiveness) / 2
        )

    def track_evidence_action(
        self,
        evidence_id: str,
        action: str,
        success: bool
    ) -> None:
        """Track evidence handling for analysis."""
        if not self.state.analysis_state:
            return

        if action == "presented" and success:
            self.state.analysis_state.evidence_presented_successfully.append(evidence_id)
            self.record_turning_point(
                TurningPointType.EVIDENCE_ADMITTED,
                f"Evidence {evidence_id} successfully admitted",
                "Strengthened case with documentary support",
                impact_score=4,
                evidence=evidence_id
            )
        elif action == "excluded":
            self.state.analysis_state.evidence_excluded.append(evidence_id)
            self.record_turning_point(
                TurningPointType.EVIDENCE_EXCLUDED,
                f"Evidence {evidence_id} excluded",
                "Successfully challenged opponent's evidence",
                impact_score=5,
                evidence=evidence_id
            )
        elif action == "challenged":
            self.state.analysis_state.evidence_challenged.append(evidence_id)

    def track_judge_interaction(self, interaction_type: str, positive: bool) -> None:
        """Track judge interactions for analysis."""
        if not self.state.analysis_state:
            return

        if positive:
            self.state.analysis_state.judge_praise_count += 1
            if self.state.analysis_state.judge_praise_count == 3:
                self.record_turning_point(
                    TurningPointType.JUDGE_PRAISE,
                    "Earned judge's repeated approval",
                    "Established credibility and favorable disposition",
                    impact_score=4
                )
        else:
            self.state.analysis_state.judge_criticism_count += 1
            if self.state.analysis_state.judge_criticism_count == 3:
                self.record_turning_point(
                    TurningPointType.JUDGE_WARNING,
                    "Received multiple judge warnings",
                    "Credibility and judicial patience diminished",
                    impact_score=-5
                )

        # Track judge patience
        if self.state.judge_state:
            self.state.analysis_state.judge_patience_history.append(
                self.state.judge_state.patience_remaining
            )

    def track_confidence_change(self, new_score: int, reason: str) -> None:
        """Track confidence meter changes for analysis."""
        if not self.state.analysis_state:
            return

        if new_score >= 85:
            self.state.analysis_state.confidence_peaks.append({
                "turn": self.state.turn_number,
                "score": new_score,
                "reason": reason
            })
            if len(self.state.analysis_state.confidence_peaks) == 1:
                self.record_turning_point(
                    TurningPointType.CONFIDENCE_PEAK,
                    "Reached peak confidence",
                    "Commanding courtroom presence established",
                    impact_score=3
                )
        elif new_score <= 30:
            self.state.analysis_state.confidence_lows.append({
                "turn": self.state.turn_number,
                "score": new_score,
                "reason": reason
            })
            if len(self.state.analysis_state.confidence_lows) == 1:
                self.record_turning_point(
                    TurningPointType.CONFIDENCE_LOW,
                    "Confidence dropped critically",
                    "Court may perceive weakness in arguments",
                    impact_score=-4
                )

    def generate_post_game_analysis(self) -> GameAnalysis:
        """Generate comprehensive post-game analysis."""
        if not self.state.analysis_state:
            # Create minimal analysis
            return GameAnalysis(
                overall_grade="C",
                overall_summary="Analysis data not available.",
                verdict_prediction_accuracy=0.5,
                total_turns=self.state.turn_number,
                actual_score=self.state.score.total_points
            )

        analysis_state = self.state.analysis_state
        score = self.state.score

        # Calculate category scores
        category_scores = self._calculate_category_scores(analysis_state)

        # Identify strengths
        strengths = self._identify_strengths(analysis_state, category_scores)

        # Identify weaknesses
        weaknesses = self._identify_weaknesses(analysis_state, category_scores)

        # Convert missed opportunities
        missed_opportunities = [
            MissedOpportunity(
                turn_number=mo["turn_number"],
                phase=mo["phase"],
                description=mo["description"],
                what_could_have_been_done=mo["what_could_have_been_done"],
                potential_impact=mo["potential_impact"],
                category=AnalysisCategory(mo["category"])
            )
            for mo in analysis_state.potential_missed_opportunities
        ]

        # Generate AI recommendations
        recommendations = self._generate_recommendations(
            analysis_state, weaknesses, missed_opportunities
        )

        # Calculate overall grade
        total_score = score.calculate_total()
        overall_grade = self._calculate_grade(total_score)

        # Generate summary
        overall_summary = self._generate_summary(
            overall_grade, strengths, weaknesses, analysis_state.turning_points
        )

        # Calculate effectiveness stats
        effective, ineffective, neutral = self._calculate_action_effectiveness(analysis_state)

        # Estimate optimal score
        optimal_score = self._estimate_optimal_score()

        analysis = GameAnalysis(
            overall_grade=overall_grade,
            overall_summary=overall_summary,
            verdict_prediction_accuracy=min(1.0, total_score / 100),
            strengths=strengths,
            weaknesses=weaknesses,
            turning_points=analysis_state.turning_points,
            missed_opportunities=missed_opportunities,
            recommendations=recommendations,
            category_scores=category_scores,
            total_turns=self.state.turn_number,
            effective_actions=effective,
            ineffective_actions=ineffective,
            neutral_actions=neutral,
            optimal_score_estimate=optimal_score,
            actual_score=score.total_points,
            score_percentage=(score.total_points / optimal_score * 100) if optimal_score > 0 else 0
        )

        self.state.game_analysis = analysis
        return analysis

    def _calculate_category_scores(self, analysis_state: AnalysisState) -> Dict[str, int]:
        """Calculate scores for each analysis category."""
        scores = {}
        score = self.state.score

        # Opening Statement
        scores[AnalysisCategory.OPENING_STATEMENT.value] = analysis_state.opening_statement_quality

        # Witness Examination
        if analysis_state.witnesses_examined:
            avg_effectiveness = sum(
                w["overall_effectiveness"] for w in analysis_state.witnesses_examined.values()
            ) / len(analysis_state.witnesses_examined)
            scores[AnalysisCategory.WITNESS_EXAMINATION.value] = int(avg_effectiveness)
        else:
            scores[AnalysisCategory.WITNESS_EXAMINATION.value] = 50

        # Cross Examination
        if analysis_state.cross_examinations:
            avg_effectiveness = sum(
                w["overall_effectiveness"] for w in analysis_state.cross_examinations.values()
            ) / len(analysis_state.cross_examinations)
            scores[AnalysisCategory.CROSS_EXAMINATION.value] = int(avg_effectiveness)
        else:
            scores[AnalysisCategory.CROSS_EXAMINATION.value] = 50

        # Evidence Handling
        evidence_score = min(100, score.evidence_handling + len(
            analysis_state.evidence_presented_successfully
        ) * 5)
        scores[AnalysisCategory.EVIDENCE_HANDLING.value] = evidence_score

        # Objections
        if analysis_state.objection_history:
            sustained = len([o for o in analysis_state.objection_history if o["sustained"]])
            total = len(analysis_state.objection_history)
            scores[AnalysisCategory.OBJECTIONS.value] = int((sustained / total) * 100) if total > 0 else 50
        else:
            scores[AnalysisCategory.OBJECTIONS.value] = 50

        # Legal Arguments
        scores[AnalysisCategory.LEGAL_ARGUMENTS.value] = score.legal_accuracy

        # Court Etiquette
        scores[AnalysisCategory.COURT_ETIQUETTE.value] = score.courtroom_decorum

        # Time Management
        if analysis_state.rushed_responses + analysis_state.slow_responses > 0:
            total_timed = (analysis_state.rushed_responses + analysis_state.slow_responses +
                         analysis_state.timed_out_responses)
            good_timing = max(0, self.state.turn_number - total_timed)
            scores[AnalysisCategory.TIME_MANAGEMENT.value] = int(
                (good_timing / self.state.turn_number) * 100
            ) if self.state.turn_number > 0 else 50
        else:
            scores[AnalysisCategory.TIME_MANAGEMENT.value] = 70

        # Judge Relations
        praise = analysis_state.judge_praise_count
        criticism = analysis_state.judge_criticism_count
        if praise + criticism > 0:
            scores[AnalysisCategory.JUDGE_RELATIONS.value] = int(
                (praise / (praise + criticism)) * 100
            )
        else:
            scores[AnalysisCategory.JUDGE_RELATIONS.value] = 50

        # Closing Argument
        scores[AnalysisCategory.CLOSING_ARGUMENT.value] = analysis_state.closing_argument_quality

        return scores

    def _identify_strengths(
        self,
        analysis_state: AnalysisState,
        category_scores: Dict[str, int]
    ) -> List[StrengthWeakness]:
        """Identify player's strengths from the game."""
        strengths = []

        # Check each category for strengths (score >= 70)
        strength_thresholds = {
            AnalysisCategory.OPENING_STATEMENT: (70, "Strong Opening Statement",
                "Delivered a compelling opening that set the stage for your case"),
            AnalysisCategory.WITNESS_EXAMINATION: (70, "Effective Witness Examination",
                "Successfully guided witnesses to provide helpful testimony"),
            AnalysisCategory.CROSS_EXAMINATION: (75, "Skillful Cross-Examination",
                "Effectively challenged opposing witnesses and exposed weaknesses"),
            AnalysisCategory.EVIDENCE_HANDLING: (70, "Competent Evidence Management",
                "Successfully introduced and leveraged documentary evidence"),
            AnalysisCategory.OBJECTIONS: (70, "Strategic Objections",
                "Made timely and appropriate objections to protect your case"),
            AnalysisCategory.LEGAL_ARGUMENTS: (75, "Sound Legal Reasoning",
                "Demonstrated strong understanding of applicable legal principles"),
            AnalysisCategory.COURT_ETIQUETTE: (80, "Excellent Court Decorum",
                "Maintained professional demeanor and proper courtroom etiquette"),
            AnalysisCategory.TIME_MANAGEMENT: (75, "Good Time Management",
                "Responded promptly and managed court time effectively"),
            AnalysisCategory.JUDGE_RELATIONS: (70, "Positive Judge Relations",
                "Built rapport and maintained favorable standing with the court"),
            AnalysisCategory.CLOSING_ARGUMENT: (70, "Persuasive Closing",
                "Delivered a strong closing that summarized your case effectively"),
        }

        for category, (threshold, title, description) in strength_thresholds.items():
            score = category_scores.get(category.value, 0)
            if score >= threshold:
                examples = self._get_examples_for_category(analysis_state, category, positive=True)
                strengths.append(StrengthWeakness(
                    category=category,
                    is_strength=True,
                    title=title,
                    description=description,
                    examples=examples[:3],  # Top 3 examples
                    score_impact=score - 50
                ))

        # Add turning point based strengths
        positive_turning_points = [tp for tp in analysis_state.turning_points if tp.impact_score > 0]
        if len(positive_turning_points) >= 3:
            strengths.append(StrengthWeakness(
                category=AnalysisCategory.LEGAL_ARGUMENTS,
                is_strength=True,
                title="Created Multiple Positive Turning Points",
                description="Successfully capitalized on key moments in the trial",
                examples=[tp.description for tp in positive_turning_points[:3]],
                score_impact=sum(tp.impact_score for tp in positive_turning_points)
            ))

        # Sort by impact
        strengths.sort(key=lambda x: x.score_impact, reverse=True)
        return strengths[:5]  # Top 5 strengths

    def _identify_weaknesses(
        self,
        analysis_state: AnalysisState,
        category_scores: Dict[str, int]
    ) -> List[StrengthWeakness]:
        """Identify player's weaknesses from the game."""
        weaknesses = []

        weakness_thresholds = {
            AnalysisCategory.OPENING_STATEMENT: (50, "Weak Opening Statement",
                "Opening statement could have been more compelling",
                "Practice structuring your opening with a clear theme and preview of evidence"),
            AnalysisCategory.WITNESS_EXAMINATION: (50, "Ineffective Witness Examination",
                "Struggled to elicit helpful testimony from witnesses",
                "Use open-ended questions and follow up on key points"),
            AnalysisCategory.CROSS_EXAMINATION: (50, "Weak Cross-Examination",
                "Failed to effectively challenge opposing witnesses",
                "Focus on impeachment with prior statements and logical inconsistencies"),
            AnalysisCategory.EVIDENCE_HANDLING: (50, "Poor Evidence Management",
                "Did not effectively utilize available documentary evidence",
                "Remember to mark, authenticate, and move to admit evidence properly"),
            AnalysisCategory.OBJECTIONS: (40, "Ineffective Objections",
                "Many objections were overruled or opportunities missed",
                "Study common objection grounds and when to use them"),
            AnalysisCategory.LEGAL_ARGUMENTS: (50, "Weak Legal Arguments",
                "Legal reasoning could be stronger and more persuasive",
                "Cite relevant sections and precedents to support arguments"),
            AnalysisCategory.COURT_ETIQUETTE: (60, "Etiquette Issues",
                "Received warnings for courtroom protocol violations",
                "Always address the court properly and maintain decorum"),
            AnalysisCategory.TIME_MANAGEMENT: (50, "Time Management Issues",
                "Frequently rushed or took too long to respond",
                "Practice balancing thoroughness with promptness"),
            AnalysisCategory.JUDGE_RELATIONS: (40, "Strained Judge Relations",
                "Judge showed signs of impatience or displeasure",
                "Adapt to the judge's style and respect court time"),
            AnalysisCategory.CLOSING_ARGUMENT: (50, "Weak Closing Argument",
                "Closing could have been more persuasive",
                "Tie together evidence and testimony to support your theory of the case"),
        }

        for category, (threshold, title, description, tip) in weakness_thresholds.items():
            score = category_scores.get(category.value, 50)
            if score < threshold:
                examples = self._get_examples_for_category(analysis_state, category, positive=False)
                weaknesses.append(StrengthWeakness(
                    category=category,
                    is_strength=False,
                    title=title,
                    description=description,
                    examples=examples[:3],
                    improvement_tip=tip,
                    score_impact=score - 50  # Negative impact
                ))

        # Add turning point based weaknesses
        negative_turning_points = [tp for tp in analysis_state.turning_points if tp.impact_score < -2]
        if len(negative_turning_points) >= 2:
            weaknesses.append(StrengthWeakness(
                category=AnalysisCategory.LEGAL_ARGUMENTS,
                is_strength=False,
                title="Multiple Negative Turning Points",
                description="Several moments hurt your case significantly",
                examples=[tp.description for tp in negative_turning_points[:3]],
                improvement_tip="Review these moments to understand what went wrong",
                score_impact=sum(tp.impact_score for tp in negative_turning_points)
            ))

        # Sort by impact (most negative first)
        weaknesses.sort(key=lambda x: x.score_impact)
        return weaknesses[:5]

    def _get_examples_for_category(
        self,
        analysis_state: AnalysisState,
        category: AnalysisCategory,
        positive: bool
    ) -> List[str]:
        """Get specific examples for a category."""
        examples = []

        if category == AnalysisCategory.OBJECTIONS:
            relevant = [o for o in analysis_state.objection_history if o["sustained"] == positive]
            for obj in relevant[:3]:
                result = "sustained" if obj["sustained"] else "overruled"
                examples.append(f"Turn {obj['turn']}: {obj['type']} objection ({result})")

        elif category == AnalysisCategory.WITNESS_EXAMINATION:
            for witness_id, data in analysis_state.witnesses_examined.items():
                if positive and data["overall_effectiveness"] >= 70:
                    examples.append(f"Effective examination of {data['name']}")
                elif not positive and data["overall_effectiveness"] < 50:
                    examples.append(f"Struggled with {data['name']}")

        elif category == AnalysisCategory.CROSS_EXAMINATION:
            for witness_id, data in analysis_state.cross_examinations.items():
                if positive and data.get("contradictions_found", 0) > 0:
                    examples.append(f"Exposed contradictions in {data['name']}'s testimony")
                elif not positive and data["overall_effectiveness"] < 50:
                    examples.append(f"Ineffective cross of {data['name']}")

        elif category == AnalysisCategory.EVIDENCE_HANDLING:
            if positive:
                for eid in analysis_state.evidence_presented_successfully[:3]:
                    examples.append(f"Successfully admitted {eid}")
            else:
                for eid in analysis_state.evidence_excluded[:3]:
                    examples.append(f"Evidence {eid} was excluded")

        # Get from turning points
        relevant_tps = [
            tp for tp in analysis_state.turning_points
            if (tp.impact_score > 0) == positive
        ]
        for tp in relevant_tps[:2]:
            if tp.description not in examples:
                examples.append(tp.description)

        return examples

    def _generate_recommendations(
        self,
        analysis_state: AnalysisState,
        weaknesses: List[StrengthWeakness],
        missed_opportunities: List[MissedOpportunity]
    ) -> List[AIRecommendation]:
        """Generate AI recommendations based on analysis."""
        recommendations = []
        priority = 1

        # Create recommendations from weaknesses
        for weakness in weaknesses[:3]:  # Top 3 weaknesses
            related_principles = []
            if weakness.category == AnalysisCategory.OBJECTIONS:
                related_principles = ["hearsay_basic", "leading_examination", "relevance_basic"]
            elif weakness.category == AnalysisCategory.WITNESS_EXAMINATION:
                related_principles = ["leading_examination", "examination_order"]
            elif weakness.category == AnalysisCategory.EVIDENCE_HANDLING:
                related_principles = ["evidence_marking", "best_evidence", "improper_foundation"]
            elif weakness.category == AnalysisCategory.COURT_ETIQUETTE:
                related_principles = ["addressing_court"]

            recommendations.append(AIRecommendation(
                category=weakness.category,
                priority=priority,
                title=f"Improve {weakness.category.value.replace('_', ' ').title()}",
                recommendation=weakness.improvement_tip or f"Focus on improving {weakness.title.lower()}",
                rationale=weakness.description,
                related_principles=related_principles
            ))
            priority += 1

        # Add recommendations from missed opportunities
        for mo in missed_opportunities[:2]:
            recommendations.append(AIRecommendation(
                category=mo.category,
                priority=priority,
                title="Missed Opportunity",
                recommendation=mo.what_could_have_been_done,
                rationale=f"At turn {mo.turn_number}: {mo.description}",
                related_principles=[]
            ))
            priority += 1

        # Add general strategic recommendations
        if self.state.total_contradictions_caught == 0:
            recommendations.append(AIRecommendation(
                category=AnalysisCategory.CROSS_EXAMINATION,
                priority=priority,
                title="Look for Contradictions",
                recommendation="Focus on finding inconsistencies between witness testimony and prior statements or other evidence",
                rationale="No contradictions were exposed during the trial",
                related_principles=["impeachment", "prior_statement"]
            ))

        if len(analysis_state.cases_cited) == 0:
            recommendations.append(AIRecommendation(
                category=AnalysisCategory.LEGAL_ARGUMENTS,
                priority=priority + 1,
                title="Cite Legal Precedents",
                recommendation="Use the legal research feature to find and cite relevant case law during arguments",
                rationale="No case precedents were cited during the trial",
                related_principles=[]
            ))

        return recommendations[:5]

    def _calculate_grade(self, total_score: float) -> str:
        """Calculate overall grade from total score."""
        if total_score >= 90:
            return "A"
        elif total_score >= 80:
            return "B"
        elif total_score >= 70:
            return "C"
        elif total_score >= 60:
            return "D"
        else:
            return "F"

    def _generate_summary(
        self,
        grade: str,
        strengths: List[StrengthWeakness],
        weaknesses: List[StrengthWeakness],
        turning_points: List[TurningPoint]
    ) -> str:
        """Generate overall summary text."""
        grade_descriptions = {
            "A": "Outstanding performance! You demonstrated excellent courtroom skills and legal acumen.",
            "B": "Good performance. You showed competent advocacy with some room for improvement.",
            "C": "Adequate performance. While you managed the basics, there are areas to develop.",
            "D": "Below average performance. Consider reviewing fundamental advocacy techniques.",
            "F": "Poor performance. Significant improvement needed in basic courtroom skills."
        }

        summary = grade_descriptions.get(grade, "Performance evaluation complete.")

        if strengths:
            top_strength = strengths[0].title
            summary += f" Your strongest area was {top_strength.lower()}."

        if weaknesses:
            top_weakness = weaknesses[0].title
            summary += f" Focus on improving {top_weakness.lower()}."

        positive_tps = len([tp for tp in turning_points if tp.impact_score > 0])
        negative_tps = len([tp for tp in turning_points if tp.impact_score < 0])

        if positive_tps > negative_tps:
            summary += " You created more positive than negative turning points, which helped your case."
        elif negative_tps > positive_tps:
            summary += " Several negative turning points hurt your case - review them for improvement."

        return summary

    def _calculate_action_effectiveness(
        self,
        analysis_state: AnalysisState
    ) -> tuple:
        """Calculate how many actions were effective, ineffective, or neutral."""
        effective = 0
        ineffective = 0
        neutral = 0

        for event in analysis_state.event_log:
            if event.score_change > 5:
                effective += 1
            elif event.score_change < -3:
                ineffective += 1
            else:
                neutral += 1

        # Add from turning points
        for tp in analysis_state.turning_points:
            if tp.impact_score > 3:
                effective += 1
            elif tp.impact_score < -3:
                ineffective += 1

        return effective, ineffective, neutral

    def _estimate_optimal_score(self) -> int:
        """Estimate the optimal possible score for this case."""
        # Base optimal score
        base_score = 500

        # Add potential from evidence (with safety checks)
        try:
            if self.state.evidence_locker:
                all_evidence = self.state.evidence_locker.petitioner_evidence + \
                              self.state.evidence_locker.respondent_evidence
                evidence_count = len(all_evidence)
            else:
                evidence_count = 0
        except (AttributeError, TypeError):
            evidence_count = 0
        base_score += evidence_count * 10

        # Add potential from witnesses (with safety checks)
        try:
            if self.case and self.case.evidence_details and self.case.evidence_details.oral_witnesses:
                witness_count = len(self.case.evidence_details.oral_witnesses)
            else:
                witness_count = 0
        except (AttributeError, TypeError):
            witness_count = 0
        base_score += witness_count * 20

        # Difficulty adjustment
        difficulty_multipliers = {
            "easy": 0.8,
            "medium": 1.0,
            "hard": 1.2
        }
        multiplier = difficulty_multipliers.get(self.difficulty, 1.0)

        return int(base_score * multiplier)

    def get_analysis_display(self) -> Dict[str, Any]:
        """Get analysis data for UI display."""
        if not self.state.game_analysis:
            # Generate if not already done
            self.generate_post_game_analysis()

        analysis = self.state.game_analysis
        if not analysis:
            return {"available": False}

        return {
            "available": True,
            "overall_grade": analysis.overall_grade,
            "overall_summary": analysis.overall_summary,
            "strengths": [
                {
                    "title": s.title,
                    "description": s.description,
                    "examples": s.examples,
                    "category": s.category.value
                }
                for s in analysis.strengths
            ],
            "weaknesses": [
                {
                    "title": w.title,
                    "description": w.description,
                    "examples": w.examples,
                    "tip": w.improvement_tip,
                    "category": w.category.value
                }
                for w in analysis.weaknesses
            ],
            "turning_points": [
                {
                    "turn": tp.turn_number,
                    "type": tp.point_type.value,
                    "description": tp.description,
                    "impact": tp.impact,
                    "impact_score": tp.impact_score,
                    "is_positive": tp.impact_score > 0
                }
                for tp in analysis.turning_points
            ],
            "missed_opportunities": [
                {
                    "turn": mo.turn_number,
                    "description": mo.description,
                    "suggestion": mo.what_could_have_been_done,
                    "impact": mo.potential_impact
                }
                for mo in analysis.missed_opportunities
            ],
            "recommendations": [
                {
                    "priority": r.priority,
                    "title": r.title,
                    "recommendation": r.recommendation,
                    "rationale": r.rationale,
                    "category": r.category.value
                }
                for r in analysis.recommendations
            ],
            "category_scores": analysis.category_scores,
            "statistics": {
                "total_turns": analysis.total_turns,
                "effective_actions": analysis.effective_actions,
                "ineffective_actions": analysis.ineffective_actions,
                "neutral_actions": analysis.neutral_actions,
                "optimal_score": analysis.optimal_score_estimate,
                "actual_score": analysis.actual_score,
                "score_percentage": analysis.score_percentage
            }
        }

    # ========================================
    # EVIDENCE MANAGEMENT METHODS
    # ========================================

    def get_evidence_locker(self) -> EvidenceLocker:
        """Get the evidence locker."""
        return self.state.evidence_locker

    def get_player_evidence(self) -> List[EvidenceItem]:
        """Get evidence available to the player."""
        side = "petitioner" if self.state.player_side == PlayerSide.PETITIONER else "respondent"
        return self.state.evidence_locker.get_party_evidence(side)

    def get_opponent_evidence(self) -> List[EvidenceItem]:
        """Get opponent's evidence."""
        side = "respondent" if self.state.player_side == PlayerSide.PETITIONER else "petitioner"
        return self.state.evidence_locker.get_party_evidence(side)

    def mark_evidence_for_identification(self, evidence_id: str) -> Dict[str, Any]:
        """
        Mark a document for identification (first step in evidence admission).
        """
        result = {"success": False, "messages": [], "evidence": None}

        item = self.state.evidence_locker.get_evidence_by_id(evidence_id)
        if not item:
            result["error"] = "Evidence not found"
            return result

        if item.status != EvidenceStatus.NOT_INTRODUCED:
            result["error"] = f"Evidence already {item.status.value}"
            return result

        # Mark for identification
        item.status = EvidenceStatus.MARKED_FOR_ID
        item.introduced_turn = self.state.turn_number
        item.introduced_by = "player" if self._is_player_evidence(item) else "opponent"

        # Clerk announces
        clerk: CourtClerkAgent = self.agents['clerk']
        clerk_msg = AgentMessage(
            role=AgentRole.COURT_CLERK,
            agent_name=clerk.name,
            content=f"Let the record show that {item.exhibit_number} - '{item.title}' "
                    f"has been marked for identification.",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(clerk_msg)
        self.state.messages.append(clerk_msg)

        result["success"] = True
        result["evidence"] = item
        return result

    def move_to_admit_evidence(self, evidence_id: str, foundation: str = "") -> Dict[str, Any]:
        """
        Move to admit evidence (formal request to Judge).
        Opponent may object.
        """
        result = {"success": False, "messages": [], "admitted": False, "objection": None}

        item = self.state.evidence_locker.get_evidence_by_id(evidence_id)
        if not item:
            result["error"] = "Evidence not found"
            return result

        if item.status not in [EvidenceStatus.NOT_INTRODUCED, EvidenceStatus.MARKED_FOR_ID]:
            result["error"] = f"Evidence cannot be admitted - status: {item.status.value}"
            return result

        item.status = EvidenceStatus.OFFERED

        # Player's motion
        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL
        motion_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=f"My Lord, I move to admit {item.exhibit_number} - '{item.title}' into evidence. "
                    f"{foundation if foundation else 'The document is relevant to establish the facts of the case.'}",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(motion_msg)
        self.state.messages.append(motion_msg)

        # Check if opponent objects (based on relevance and randomness)
        opponent_objects = self._check_opponent_evidence_objection(item)

        if opponent_objects:
            objection_result = self._process_opponent_evidence_objection(item)
            result["messages"].extend(objection_result["messages"])
            result["objection"] = objection_result["objection_type"]

            # Judge rules on objection
            ruling_result = self._judge_rule_on_evidence_objection(item, objection_result["objection_type"])
            result["messages"].extend(ruling_result["messages"])
            result["admitted"] = ruling_result["admitted"]
        else:
            # No objection - Judge admits
            result["admitted"] = True
            judge: JudgeAgent = self.agents['judge']
            admission_msg = judge.respond(
                f"The document {item.exhibit_number} is admitted into evidence. "
                f"Let it be marked as Exhibit.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(admission_msg)
            self.state.messages.append(admission_msg)

        # Update evidence status
        if result["admitted"]:
            item.status = EvidenceStatus.ADMITTED
            self.state.evidence_locker.admitted_evidence.append(item.evidence_id)
            self.state.score.evidence_handling = min(100, self.state.score.evidence_handling + 10)
        else:
            item.status = EvidenceStatus.EXCLUDED
            self.state.evidence_locker.excluded_evidence.append(item.evidence_id)

        result["success"] = True
        result["evidence"] = item
        return result

    def object_to_evidence(self, evidence_id: str, objection_type: EvidenceObjectionType, grounds: str = "") -> Dict[str, Any]:
        """
        Object to opponent's evidence.
        """
        result = {"success": False, "messages": [], "sustained": False}

        item = self.state.evidence_locker.get_evidence_by_id(evidence_id)
        if not item:
            result["error"] = "Evidence not found"
            return result

        if item.status != EvidenceStatus.OFFERED:
            result["error"] = "Evidence is not currently being offered for admission"
            return result

        self.state.evidence_objections_made += 1

        # Player's objection
        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL
        objection_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=f"Objection, My Lord! I object to the admission of {item.exhibit_number} "
                    f"on the grounds of {objection_type.value}. {grounds}",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(objection_msg)
        self.state.messages.append(objection_msg)

        # Record objection
        item.objections.append({
            "type": objection_type.value,
            "by": "player",
            "grounds": grounds,
            "turn": self.state.turn_number
        })
        item.status = EvidenceStatus.OBJECTED

        # Judge rules
        ruling_result = self._judge_rule_on_evidence_objection(item, objection_type, player_objected=True)
        result["messages"].extend(ruling_result["messages"])
        result["sustained"] = ruling_result["sustained"]

        if result["sustained"]:
            item.status = EvidenceStatus.EXCLUDED
            self.state.evidence_locker.excluded_evidence.append(item.evidence_id)
            self.state.evidence_objections_sustained += 1
            self.state.score.evidence_handling = min(100, self.state.score.evidence_handling + 15)
        else:
            item.status = EvidenceStatus.ADMITTED
            self.state.evidence_locker.admitted_evidence.append(item.evidence_id)

        result["success"] = True
        return result

    def challenge_evidence_authenticity(self, evidence_id: str, challenge_basis: str) -> Dict[str, Any]:
        """
        Challenge the authenticity of opponent's evidence.
        """
        result = {"success": False, "messages": []}

        item = self.state.evidence_locker.get_evidence_by_id(evidence_id)
        if not item:
            result["error"] = "Evidence not found"
            return result

        item.authenticity_challenged = True
        item.notes.append(f"Authenticity challenged: {challenge_basis}")

        # Player's challenge
        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL
        challenge_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=f"My Lord, I challenge the authenticity of {item.exhibit_number}. {challenge_basis}",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(challenge_msg)
        self.state.messages.append(challenge_msg)

        # Judge responds
        judge: JudgeAgent = self.agents['judge']
        judge_response = judge.respond(
            f"The Court notes the challenge to the authenticity of {item.exhibit_number}. "
            f"The opposing party may address this challenge. "
            f"The weight to be given to this evidence will be determined accordingly.",
            CourtPhase.EXAMINATION
        )
        result["messages"].append(judge_response)
        self.state.messages.append(judge_response)

        # Opponent responds to challenge
        opponent: LawyerAgent = self.agents['opponent']
        opponent_response = opponent.respond(
            f"Respond to the authenticity challenge of {item.exhibit_number}. "
            f"The challenge basis is: {challenge_basis}",
            CourtPhase.EXAMINATION
        )
        result["messages"].append(opponent_response)
        self.state.messages.append(opponent_response)

        result["success"] = True
        return result

    def _is_player_evidence(self, item: EvidenceItem) -> bool:
        """Check if evidence belongs to player."""
        player_side = "petitioner" if self.state.player_side == PlayerSide.PETITIONER else "respondent"
        return item.owner_side == player_side

    def _check_opponent_evidence_objection(self, item: EvidenceItem) -> bool:
        """Determine if AI opponent will object to evidence."""
        # Higher chance to object if:
        # - Evidence is highly relevant (threatens their case)
        # - Difficulty is higher
        # - Evidence category is prone to objections

        base_objection_chance = {
            "easy": 0.15,
            "medium": 0.30,
            "hard": 0.50
        }.get(self.difficulty, 0.30)

        # Increase chance for highly relevant evidence
        if item.relevance_score > 80:
            base_objection_chance += 0.15

        # Increase chance for certain categories
        if item.category in [EvidenceCategory.PHOTOGRAPHS, EvidenceCategory.ELECTRONIC]:
            base_objection_chance += 0.10

        return random.random() < base_objection_chance

    def _process_opponent_evidence_objection(self, item: EvidenceItem) -> Dict[str, Any]:
        """Process AI opponent's objection to evidence."""
        result = {"messages": [], "objection_type": None}

        # Select appropriate objection type based on evidence category
        category_objections = {
            EvidenceCategory.DOCUMENTARY: [EvidenceObjectionType.HEARSAY, EvidenceObjectionType.AUTHENTICATION],
            EvidenceCategory.MEDICAL_RECORDS: [EvidenceObjectionType.LACK_OF_FOUNDATION, EvidenceObjectionType.HEARSAY],
            EvidenceCategory.PHOTOGRAPHS: [EvidenceObjectionType.AUTHENTICATION, EvidenceObjectionType.UNFAIR_PREJUDICE],
            EvidenceCategory.EXPERT_REPORTS: [EvidenceObjectionType.LACK_OF_FOUNDATION, EvidenceObjectionType.SPECULATION],
            EvidenceCategory.WITNESS_STATEMENTS: [EvidenceObjectionType.HEARSAY, EvidenceObjectionType.IMPROPER_CHARACTER],
            EvidenceCategory.ELECTRONIC: [EvidenceObjectionType.AUTHENTICATION, EvidenceObjectionType.BEST_EVIDENCE_RULE],
        }

        possible_objections = category_objections.get(item.category, [EvidenceObjectionType.IRRELEVANT])
        objection_type = random.choice(possible_objections)

        opponent: LawyerAgent = self.agents['opponent']
        objection_msg = AgentMessage(
            role=opponent.role,
            agent_name=opponent.name,
            content=f"Objection, My Lord! I object to the admission of {item.exhibit_number} "
                    f"on the grounds of {objection_type.value}.",
            phase=CourtPhase.EXAMINATION
        )
        result["messages"].append(objection_msg)
        self.state.messages.append(objection_msg)

        result["objection_type"] = objection_type
        item.objections.append({
            "type": objection_type.value,
            "by": "opponent",
            "turn": self.state.turn_number
        })

        return result

    def _judge_rule_on_evidence_objection(
        self,
        item: EvidenceItem,
        objection_type: EvidenceObjectionType,
        player_objected: bool = False
    ) -> Dict[str, Any]:
        """Judge rules on an evidence objection."""
        result = {"messages": [], "sustained": False, "admitted": False}

        judge: JudgeAgent = self.agents['judge']

        # Determine ruling based on objection type and evidence
        # Some objections are more likely to be sustained
        sustain_probability = {
            EvidenceObjectionType.HEARSAY: 0.40,
            EvidenceObjectionType.IRRELEVANT: 0.30,
            EvidenceObjectionType.LACK_OF_FOUNDATION: 0.35,
            EvidenceObjectionType.AUTHENTICATION: 0.25,
            EvidenceObjectionType.BEST_EVIDENCE_RULE: 0.30,
            EvidenceObjectionType.UNFAIR_PREJUDICE: 0.20,
            EvidenceObjectionType.CHAIN_OF_CUSTODY: 0.35,
            EvidenceObjectionType.PRIVILEGE: 0.50,
            EvidenceObjectionType.IMPROPER_CHARACTER: 0.40,
            EvidenceObjectionType.SPECULATION: 0.35
        }

        base_sustain = sustain_probability.get(objection_type, 0.30)

        # Adjust based on evidence relevance
        if item.relevance_score > 85:
            base_sustain -= 0.15  # Highly relevant evidence harder to exclude

        sustained = random.random() < base_sustain

        if sustained:
            result["sustained"] = True
            result["admitted"] = False
            ruling_msg = judge.respond(
                f"Objection sustained. The document {item.exhibit_number} is excluded from evidence. "
                f"The grounds of {objection_type.value} are valid in this instance.",
                CourtPhase.EXAMINATION
            )
        else:
            result["sustained"] = False
            result["admitted"] = True
            ruling_msg = judge.respond(
                f"Objection overruled. The document {item.exhibit_number} is admitted into evidence. "
                f"The Court finds the objection on grounds of {objection_type.value} not tenable.",
                CourtPhase.EXAMINATION
            )

        result["messages"].append(ruling_msg)
        self.state.messages.append(ruling_msg)
        item.judge_ruling = "Sustained" if sustained else "Overruled"

        return result

    def _clerk_announce_case(self) -> AgentMessage:
        """Have the clerk announce the case."""
        clerk: CourtClerkAgent = self.agents['clerk']
        return clerk.announce_case(self.case)

    def _check_court_etiquette(self, action: GameAction) -> Dict[str, Any]:
        """
        Check player's action for court etiquette violations.
        Returns violations, feedback, and optional Judge response.
        """
        result = {
            "violations": [],
            "feedback": None,
            "judge_response": None,
            "score_penalty": 0
        }

        # Create etiquette checker for current context
        checker = CourtEtiquetteChecker(
            phase=self.state.phase,
            action_type=action.action_type,
            is_first_in_phase=self.state.is_first_action_in_phase
        )

        # Check for violations
        violations = checker.check_etiquette(action.content)

        if not violations:
            # Good etiquette! Increment streak
            self.state.proper_decorum_streak += 1

            # Bonus for maintaining good decorum
            if self.state.proper_decorum_streak >= 5:
                self.state.score.courtroom_decorum = min(100, self.state.score.courtroom_decorum + 2)

            return result

        # Reset streak on violation
        self.state.proper_decorum_streak = 0

        # Record violations
        for v in violations:
            violation_record = {
                "type": v.violation_type.value,
                "description": v.description,
                "severity": v.severity,
                "suggestion": v.suggestion,
                "turn": self.state.turn_number
            }
            self.state.etiquette_violations.append(violation_record)
            result["violations"].append(violation_record)

        # Calculate severity and penalty
        serious_count = sum(1 for v in violations if v.severity == "serious")
        moderate_count = sum(1 for v in violations if v.severity == "moderate")
        minor_count = sum(1 for v in violations if v.severity == "minor")

        score_penalty = (serious_count * 10) + (moderate_count * 5) + (minor_count * 2)
        result["score_penalty"] = score_penalty

        # Apply score penalty
        self.state.score.courtroom_decorum = max(0, self.state.score.courtroom_decorum - score_penalty)

        # Generate feedback for player
        feedback_parts = []
        for v in violations:
            feedback_parts.append(f"• {v.description}\n  💡 {v.suggestion}")
        result["feedback"] = "\n".join(feedback_parts)

        # Determine if Judge should respond
        total_etiquette_warnings = self.state.etiquette_warnings
        should_judge_respond = False
        judge_severity = "gentle"

        if serious_count > 0:
            should_judge_respond = True
            judge_severity = "stern"
            self.state.etiquette_warnings += 1
        elif moderate_count > 0 and total_etiquette_warnings < 2:
            should_judge_respond = True
            judge_severity = "mild"
            self.state.etiquette_warnings += 1
        elif minor_count >= 2:
            should_judge_respond = True
            judge_severity = "gentle"
            self.state.etiquette_warnings += 1
        elif total_etiquette_warnings == 0 and (moderate_count > 0 or minor_count > 0):
            # First violation - Judge gives guidance
            should_judge_respond = True
            judge_severity = "educational"

        if should_judge_respond:
            judge: JudgeAgent = self.agents['judge']
            result["judge_response"] = self._generate_etiquette_response(
                judge, violations, judge_severity
            )

        return result

    def _generate_etiquette_response(
        self,
        judge: JudgeAgent,
        violations: List[EtiquetteViolation],
        severity: str
    ) -> AgentMessage:
        """Generate Judge's response to etiquette violations."""

        # Build context for judge response
        violation_types = [v.violation_type for v in violations]

        if severity == "stern":
            prompt = (
                "The counsel has committed a serious breach of court etiquette. "
                "Issue a stern warning about proper court conduct. "
                "Remind them that repeated violations may result in contempt proceedings. "
                f"Violations: {', '.join(v.description for v in violations)}"
            )
        elif severity == "mild":
            prompt = (
                "The counsel has shown a lapse in proper court protocol. "
                "Gently but firmly remind them of proper courtroom etiquette. "
                f"Issue: {violations[0].description}"
            )
        elif severity == "educational":
            prompt = (
                "This appears to be counsel's first etiquette lapse. "
                "Provide gentle guidance on proper court protocol in a helpful manner. "
                f"They should: {violations[0].suggestion}"
            )
        else:  # gentle
            prompt = (
                "The counsel has minor protocol issues. "
                "Provide a brief, polite reminder about court etiquette. "
                f"Suggestion: {violations[0].suggestion}"
            )

        return judge.respond(prompt, CourtPhase.EXAMINATION)

    def get_etiquette_tips(self) -> List[str]:
        """Get etiquette tips for current phase."""
        return CourtEtiquetteChecker.get_etiquette_tips(self.state.phase)

    def _get_phase_instructions(self) -> str:
        """Get instructions for current phase."""
        player_is_petitioner = self.state.player_side == PlayerSide.PETITIONER

        instructions = {
            GamePhase.OPENING_STATEMENT: f"""
📋 **OPENING STATEMENT PHASE**

{'You are the Petitioner counsel. You present your opening statement FIRST.' if player_is_petitioner else 'You are the Respondent counsel. The Petitioner has made their opening statement. Now it is YOUR turn to respond.'}

**What to include:**
- Introduce your client and their case
- Outline the key facts you will prove
- Preview the evidence and witnesses
- State the relief you seek (petitioner) or your defense (respondent)

**Tips:**
- Be clear and organized
- Create a compelling narrative
- Set the stage for your evidence
""",
            GamePhase.PETITIONER_WITNESS_EXAM: f"""
📋 **PETITIONER'S WITNESS EXAMINATION**

{'You are examining YOUR OWN witnesses. Ask open-ended questions to bring out favorable testimony.' if player_is_petitioner else 'The opposing counsel is examining their witnesses. After they finish, you will CROSS-EXAMINE.'}

{'**Your Role:** Examine your witnesses in chief' if player_is_petitioner else '**Your Role:** Wait for examination, then cross-examine'}

**Tips for Examination-in-Chief:**
- Ask open-ended questions (Who, What, When, Where, Why, How)
- Let the witness tell their story
- Don't lead the witness

**Tips for Cross-Examination:**
- Use leading questions (questions that suggest the answer)
- Challenge inconsistencies
- Be brief and pointed
""",
            GamePhase.CROSS_EXAMINATION: f"""
📋 **CROSS-EXAMINATION PHASE**

You are cross-examining the opposing party's witness.

**Objectives:**
- Challenge the witness's credibility
- Highlight contradictions with their affidavit
- Extract admissions helpful to your case
- Limit damage from their testimony

**Tips:**
- Use leading questions ("Isn't it true that...?")
- Keep questions short and pointed
- Don't ask questions you don't know the answer to
- Control the witness - don't let them explain
- End on a strong point
""",
            GamePhase.RESPONDENT_WITNESS_EXAM: f"""
📋 **RESPONDENT'S WITNESS EXAMINATION**

{'The opposing counsel is examining their witnesses. After they finish, you will CROSS-EXAMINE.' if player_is_petitioner else 'You are examining YOUR OWN witnesses. Ask open-ended questions to bring out favorable testimony.'}

{'**Your Role:** Wait for examination, then cross-examine' if player_is_petitioner else '**Your Role:** Examine your witnesses in chief'}

**Key Witnesses to Focus On:**
- Insurance investigator
- Expert witnesses
- Eye witnesses (if any)
""",
            GamePhase.FINAL_ARGUMENTS: f"""
📋 **FINAL ARGUMENTS PHASE**

{'The opposing counsel has presented their final arguments. Now it is YOUR turn.' if not player_is_petitioner else 'Present your closing arguments to the court.'}

**Structure your argument:**
1. Summarize the key evidence
2. Address each issue framed by the court
3. Cite relevant case law (Sarla Verma, Pranay Sethi, etc.)
4. {'Prove negligence and argue for maximum compensation' if player_is_petitioner else 'Challenge negligence findings and minimize compensation'}
5. Make your final plea

**Remember:**
- Connect the evidence to the legal issues
- Address weaknesses in your case
- End with a strong conclusion
""",
            GamePhase.JUDGMENT: """
📋 **JUDGMENT PHASE**

The Hon'ble Court is delivering its judgment.
The verdict will be based on the evidence presented and arguments made.
""",
            GamePhase.GAME_OVER: """
🏆 **CASE CONCLUDED**

The judgment has been delivered. Review your performance and see how you did!
"""
        }
        return instructions.get(self.state.phase, "⏳ Awaiting court proceedings...")

    def get_available_actions(self) -> List[ActionType]:
        """Get available actions for current phase."""
        phase_actions = {
            GamePhase.OPENING_STATEMENT: [
                ActionType.MAKE_ARGUMENT,
                ActionType.REST_CASE  # Conclude opening statement
            ],
            GamePhase.PETITIONER_WITNESS_EXAM: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.MARK_FOR_IDENTIFICATION,
                ActionType.MOVE_TO_ADMIT,
                ActionType.OBJECT_TO_EVIDENCE,
                ActionType.CHALLENGE_AUTHENTICITY,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS,
                ActionType.REST_CASE  # Conclude examination
            ],
            GamePhase.CROSS_EXAMINATION: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.MARK_FOR_IDENTIFICATION,
                ActionType.MOVE_TO_ADMIT,
                ActionType.OBJECT_TO_EVIDENCE,
                ActionType.CHALLENGE_AUTHENTICITY,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS,
                ActionType.REST_CASE  # Conclude cross-examination
            ],
            GamePhase.RESPONDENT_WITNESS_EXAM: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.MARK_FOR_IDENTIFICATION,
                ActionType.MOVE_TO_ADMIT,
                ActionType.OBJECT_TO_EVIDENCE,
                ActionType.CHALLENGE_AUTHENTICITY,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS,
                ActionType.REST_CASE  # Conclude examination
            ],
            GamePhase.FINAL_ARGUMENTS: [
                ActionType.MAKE_ARGUMENT,
                ActionType.CITE_CASE_LAW,
                ActionType.REST_CASE  # Rest your case
            ],
            GamePhase.REBUTTAL: [
                ActionType.MAKE_ARGUMENT,
                ActionType.REST_CASE
            ]
        }
        return phase_actions.get(self.state.phase, [])

    def process_player_action(self, action: GameAction) -> Dict[str, Any]:
        """Process a player's action and return results."""
        self.state.turn_number += 1
        self.state.phase_turn_number += 1

        # Stop the timer and get response timing stats
        timing_result = self.stop_action_timer()

        results = {
            "messages": [],
            "events": [],
            "score_change": {},
            "phase_changed": False,
            "game_over": False,
            "judge_warning": None,
            "judge_advanced_phase": False,
            "etiquette_violations": [],
            "etiquette_feedback": None,
            "timing_stats": timing_result,
            "confidence_update": None
        }

        # If rushed, add judge remark about it
        if timing_result.get("judge_remark"):
            judge: JudgeAgent = self.agents['judge']
            rush_msg = judge.respond(timing_result["judge_remark"], CourtPhase.EXAMINATION)
            results["messages"].append(rush_msg)
            self.state.messages.append(rush_msg)

        # ========================================
        # COURT ETIQUETTE CHECK
        # ========================================
        if action.content:  # Only check if there's content to check
            etiquette_result = self._check_court_etiquette(action)
            results["etiquette_violations"] = etiquette_result.get("violations", [])
            results["etiquette_feedback"] = etiquette_result.get("feedback")

            # If violations found, add Judge's etiquette response
            if etiquette_result.get("judge_response"):
                results["messages"].append(etiquette_result["judge_response"])
                self.state.messages.append(etiquette_result["judge_response"])

        # Mark first action in phase as done
        self.state.is_first_action_in_phase = False

        # Process the action based on type
        if action.action_type == ActionType.MAKE_ARGUMENT:
            results["messages"].extend(self._process_argument(action))
        elif action.action_type == ActionType.ASK_QUESTION:
            results["messages"].extend(self._process_question(action))
        elif action.action_type == ActionType.RAISE_OBJECTION:
            results["messages"].extend(self._process_objection(action))
        elif action.action_type == ActionType.PRESENT_EVIDENCE:
            results["messages"].extend(self._process_evidence(action))
        elif action.action_type == ActionType.CITE_CASE_LAW:
            results["messages"].extend(self._process_citation(action))
        elif action.action_type == ActionType.NO_QUESTIONS:
            results["messages"].extend(self._process_no_questions())
        elif action.action_type == ActionType.REST_CASE:
            # Player indicates they have concluded their submissions
            rest_result = self._process_rest_case()
            results["messages"].extend(rest_result["messages"])
            if rest_result.get("phase_changed"):
                results["phase_changed"] = True
                results["judge_advanced_phase"] = True
                results["new_phase"] = self.state.phase
                results["instructions"] = self._get_phase_instructions()
            return results  # Early return - Judge handles the rest

        # Evidence Management Actions
        elif action.action_type == ActionType.MARK_FOR_IDENTIFICATION:
            if action.evidence_id:
                evidence_result = self.mark_evidence_for_identification(action.evidence_id)
                results["messages"].extend(evidence_result.get("messages", []))
                results["evidence_marked"] = evidence_result.get("success", False)

        elif action.action_type == ActionType.MOVE_TO_ADMIT:
            if action.evidence_id:
                evidence_result = self.move_to_admit_evidence(action.evidence_id, action.content)
                results["messages"].extend(evidence_result.get("messages", []))
                results["evidence_admitted"] = evidence_result.get("admitted", False)
                results["evidence_excluded"] = evidence_result.get("excluded", False)

        elif action.action_type == ActionType.OBJECT_TO_EVIDENCE:
            if action.evidence_id:
                # Get objection type from action or default to RELEVANCE
                objection_type = getattr(action, 'evidence_objection_type', EvidenceObjectionType.RELEVANCE)
                evidence_result = self.object_to_evidence(action.evidence_id, objection_type, action.content)
                results["messages"].extend(evidence_result.get("messages", []))
                results["objection_sustained"] = evidence_result.get("sustained", False)

        elif action.action_type == ActionType.CHALLENGE_AUTHENTICITY:
            if action.evidence_id:
                evidence_result = self.challenge_evidence_authenticity(action.evidence_id, action.content)
                results["messages"].extend(evidence_result.get("messages", []))
                results["challenge_noted"] = evidence_result.get("success", False)

        # Check for dynamic events
        event = self.event_generator.maybe_trigger_event(self.state.phase, self.state)
        if event:
            results["events"].append(event)
            self.state.events_occurred.append(event)
            self._emit("event_triggered", event)

        # JUDGE DECISION: Check if Judge wants to give warning or advance phase
        judge_decision = self._judge_evaluate_proceedings()
        if judge_decision["action"] == "warning":
            results["messages"].append(judge_decision["message"])
            self.state.messages.append(judge_decision["message"])
            results["judge_warning"] = judge_decision["warning_type"]
            self.state.judge_warnings_in_phase += 1
        elif judge_decision["action"] == "advance_phase":
            results["messages"].append(judge_decision["message"])
            self.state.messages.append(judge_decision["message"])
            self._advance_phase()
            results["phase_changed"] = True
            results["judge_advanced_phase"] = True
            results["new_phase"] = self.state.phase
            results["instructions"] = self._get_phase_instructions()

            # Judge announces new phase
            phase_announcement = self._judge_announce_new_phase()
            if phase_announcement:
                results["messages"].extend(phase_announcement)

        # Update score
        self._update_score(action, results)
        results["score"] = self.state.score

        # Update confidence meter based on action outcomes
        confidence_update = self.update_confidence_from_action(results)
        results["confidence_update"] = confidence_update

        # Check if judge wants to remark on player's confidence
        judge_confidence_remark = self.get_judge_confidence_remark()
        if judge_confidence_remark:
            judge: JudgeAgent = self.agents['judge']
            conf_msg = judge.respond(judge_confidence_remark, CourtPhase.EXAMINATION)
            results["messages"].append(conf_msg)
            self.state.messages.append(conf_msg)
            results["judge_confidence_remark"] = judge_confidence_remark

        # AI opponent's turn (if not phase change)
        if not results["phase_changed"] and not self.state.is_player_turn and self.state.phase != GamePhase.GAME_OVER:
            opponent_response = self._get_opponent_response()
            results["messages"].append(opponent_response)
            self.state.is_player_turn = True

        # Start timer for next action if player's turn
        if self.state.is_player_turn and not results["phase_changed"]:
            self.start_action_timer(action.action_type)

        # Log the turn
        self.state.game_log.append({
            "turn": self.state.turn_number,
            "phase": self.state.phase.value,
            "action": action.action_type.value,
            "content": action.content,
            "response_time": timing_result.get("response_time"),
            "confidence": self.state.confidence_meter.confidence_score if self.state.confidence_meter else None
        })

        return results

    def _judge_evaluate_proceedings(self) -> Dict[str, Any]:
        """
        Judge evaluates current proceedings and decides:
        - Give warning to wrap up
        - Advance to next phase
        - Continue normally

        This simulates a real Judge managing court time.
        """
        phase = self.state.phase
        phase_turns = self.state.phase_turn_number

        # Get phase limits
        limits = PHASE_LIMITS.get(phase)
        if not limits:
            return {"action": "continue"}

        judge: JudgeAgent = self.agents['judge']

        # Check if at warning threshold
        if phase_turns == limits.warning_at and self.state.judge_warnings_in_phase == 0:
            warning_messages = {
                GamePhase.OPENING_STATEMENT: (
                    "Counsel, the Court notes that you have made your initial submissions. "
                    "Please conclude your opening statement concisely. The Court has limited time."
                ),
                GamePhase.PETITIONER_WITNESS_EXAM: (
                    "Counsel, the Court observes that the examination has been ongoing. "
                    "Please conclude the examination of this witness expeditiously."
                ),
                GamePhase.CROSS_EXAMINATION: (
                    "Learned counsel, kindly conclude your cross-examination. "
                    "The Court cannot permit indefinite questioning."
                ),
                GamePhase.RESPONDENT_WITNESS_EXAM: (
                    "Counsel for the respondent, please wrap up the examination. "
                    "The Court must proceed with the matter."
                ),
                GamePhase.FINAL_ARGUMENTS: (
                    "Counsel, please conclude your final arguments. "
                    "The Court has heard sufficient submissions on this point."
                )
            }

            warning_text = warning_messages.get(phase, "Counsel, please conclude your submissions.")
            warning_msg = judge.respond(warning_text, CourtPhase.EXAMINATION)

            return {
                "action": "warning",
                "message": warning_msg,
                "warning_type": "time_warning"
            }

        # Check if exceeded max turns - Judge advances phase
        if phase_turns >= limits.max_turns:
            # Check if extension possible and not yet granted
            if limits.can_extend and not self.state.extension_granted and random.random() < 0.3:
                # Judge grants brief extension (30% chance)
                self.state.extension_granted = True
                extension_msg = judge.respond(
                    "The Court will grant counsel a brief indulgence to conclude. "
                    "However, this cannot continue indefinitely. Please conclude promptly.",
                    CourtPhase.EXAMINATION
                )
                return {
                    "action": "warning",
                    "message": extension_msg,
                    "warning_type": "extension_granted"
                }

            # Judge advances the phase
            advance_messages = {
                GamePhase.OPENING_STATEMENT: (
                    "The Court has heard the opening statements. "
                    "We shall now proceed with the examination of witnesses. "
                    "Counsel for the petitioner, you may call your first witness."
                ),
                GamePhase.PETITIONER_WITNESS_EXAM: (
                    "The examination of this witness stands concluded. "
                    "The Court will now permit cross-examination by the opposing counsel."
                ),
                GamePhase.CROSS_EXAMINATION: (
                    "Cross-examination is concluded. "
                    "The Court will now proceed with the respondent's evidence."
                ),
                GamePhase.RESPONDENT_WITNESS_EXAM: (
                    "The examination stands concluded. "
                    "The Court will now hear final arguments from both sides."
                ),
                GamePhase.FINAL_ARGUMENTS: (
                    "The Court has heard sufficient arguments from both sides. "
                    "The matter is now reserved for judgment."
                )
            }

            advance_text = advance_messages.get(phase, "The Court will proceed to the next stage.")
            advance_msg = judge.respond(advance_text, CourtPhase.EXAMINATION)

            return {
                "action": "advance_phase",
                "message": advance_msg
            }

        return {"action": "continue"}

    def _judge_announce_new_phase(self) -> List[AgentMessage]:
        """Judge announces the new phase and gives directions."""
        messages = []
        judge: JudgeAgent = self.agents['judge']
        phase = self.state.phase

        # Reset phase-specific state
        self.state.phase_turn_number = 0
        self.state.judge_warnings_in_phase = 0
        self.state.extension_granted = False

        # Phase-specific announcements and AI actions
        if phase == GamePhase.PETITIONER_WITNESS_EXAM:
            if self.state.player_side == PlayerSide.RESPONDENT:
                # AI petitioner examines first
                messages.extend(self.run_ai_turn())
                # Then auto-advance to cross-exam for player
                self.state.phase = GamePhase.CROSS_EXAMINATION
                cross_announce = judge.respond(
                    "The examination-in-chief is concluded. "
                    "Counsel for the respondent may now cross-examine the witness.",
                    CourtPhase.CROSS_EXAMINATION
                )
                messages.append(cross_announce)
                self.state.messages.append(cross_announce)

        elif phase == GamePhase.RESPONDENT_WITNESS_EXAM:
            if self.state.player_side == PlayerSide.PETITIONER:
                # AI respondent examines first
                messages.extend(self.run_ai_turn())
                # Then auto-advance to cross-exam for player
                self.state.phase = GamePhase.CROSS_EXAMINATION
                cross_announce = judge.respond(
                    "The examination-in-chief is concluded. "
                    "Counsel for the petitioner may now cross-examine the witness.",
                    CourtPhase.CROSS_EXAMINATION
                )
                messages.append(cross_announce)
                self.state.messages.append(cross_announce)

        elif phase == GamePhase.FINAL_ARGUMENTS:
            if self.state.player_side == PlayerSide.RESPONDENT:
                # AI petitioner argues first
                messages.extend(self.run_ai_turn())

        elif phase == GamePhase.JUDGMENT:
            judgment = self._deliver_judgment()
            messages.append(judgment)

        return messages

    def _process_argument(self, action: GameAction) -> List[AgentMessage]:
        """Process an argument from the player."""
        messages = []

        # Player's argument
        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL
        player_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=action.content,
            phase=CourtPhase.PETITIONER_ARGUMENTS if self.state.player_side == PlayerSide.PETITIONER else CourtPhase.RESPONDENT_ARGUMENTS
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)

        # Detect if this is a challenge/question to opposing counsel
        content_lower = action.content.lower()
        is_challenge_to_opponent = any(phrase in content_lower for phrase in [
            "can the petitioner", "can the respondent", "how will", "how can",
            "what evidence", "prove", "substantiate", "learned counsel",
            "opposing counsel", "my learned friend", "other side",
            "petitioner's counsel", "respondent's counsel", "?",
            "challenge", "deny", "refute", "contradict"
        ])

        if is_challenge_to_opponent:
            # Opposing counsel should respond first
            opponent: LawyerAgent = self.agents['opponent']
            opponent_response = opponent.respond(
                f"The opposing counsel has stated: '{action.content}'\n\n"
                f"Respond to this challenge or question directly, defending your client's position.",
                CourtPhase.PETITIONER_ARGUMENTS if self.state.player_side == PlayerSide.RESPONDENT else CourtPhase.RESPONDENT_ARGUMENTS
            )
            messages.append(opponent_response)
            self.state.messages.append(opponent_response)

            # Judge may interject if needed (30% chance for follow-up)
            if random.random() < 0.3:
                judge: JudgeAgent = self.agents['judge']
                judge_response = judge.respond(
                    f"Having heard both counsels on this point, the Court notes the submissions.",
                    CourtPhase.PETITIONER_ARGUMENTS
                )
                messages.append(judge_response)
                self.state.messages.append(judge_response)
        else:
            # This is a statement/argument to the court - Judge responds
            judge: JudgeAgent = self.agents['judge']
            judge_response = judge.respond(
                f"Counsel has argued: {action.content}\n\nProvide a brief acknowledgment or ask any clarifying questions.",
                CourtPhase.PETITIONER_ARGUMENTS
            )
            messages.append(judge_response)
            self.state.messages.append(judge_response)

        return messages

    def _process_question(self, action: GameAction) -> List[AgentMessage]:
        """Process a question - routes to witness during examination, to opposing counsel during arguments."""
        messages = []
        credibility_info = {}

        # Determine the appropriate phase for the message
        is_examination_phase = self.state.phase in [
            GamePhase.PETITIONER_WITNESS_EXAM,
            GamePhase.RESPONDENT_WITNESS_EXAM,
            GamePhase.CROSS_EXAMINATION
        ]

        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL

        # Player's question
        player_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=f"Question: {action.content}",
            phase=CourtPhase.EXAMINATION if is_examination_phase else CourtPhase.PETITIONER_ARGUMENTS
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)

        if is_examination_phase:
            # During examination phases - direct question to witness
            if self.state.current_witness_index < len(self.agents['witnesses']):
                witness: WitnessAgent = self.agents['witnesses'][self.state.current_witness_index]

                # ========================================
                # WITNESS CREDIBILITY SYSTEM INTEGRATION
                # ========================================

                # Set current witness state if not already set
                self._set_current_witness_state()

                # Analyze questioning style
                questioning_style = self.analyze_questioning_style(action.content)

                # Get witness response modifier based on current state
                response_modifier = self.get_witness_response_modifier()

                # Build enhanced prompt with witness state
                enhanced_prompt = action.content
                if response_modifier.get("instructions"):
                    enhanced_prompt = f"{action.content}\n\n[Witness State: {response_modifier['instructions']}]"

                # Get witness response (ideally the WitnessAgent would use the modifier)
                witness_response = witness.respond(enhanced_prompt, CourtPhase.EXAMINATION)

                # Modify response based on witness reaction
                if self.state.current_witness_state:
                    ws = self.state.current_witness_state
                    reaction = ws.current_reaction

                    # Add reaction indicator to response
                    reaction_prefix = ""
                    if reaction == WitnessReaction.NERVOUS:
                        reaction_prefix = "*shifts uncomfortably* "
                    elif reaction == WitnessReaction.HOSTILE:
                        reaction_prefix = "*glares at counsel* "
                    elif reaction == WitnessReaction.DEFENSIVE:
                        reaction_prefix = "*pauses carefully* "
                    elif reaction == WitnessReaction.EVASIVE:
                        reaction_prefix = "*looks away* "
                    elif reaction == WitnessReaction.BREAKDOWN:
                        reaction_prefix = "*voice trembling* "

                    if reaction_prefix and not witness_response.content.startswith("*"):
                        witness_response.content = reaction_prefix + witness_response.content

                messages.append(witness_response)
                self.state.messages.append(witness_response)

                # Check for contradiction in response
                caught_contradiction = self.detect_contradiction(witness_response.content)

                # Update witness stats based on questioning
                credibility_effect = self.update_witness_stats(questioning_style, caught_contradiction)
                credibility_info = credibility_effect

                # Add contradiction message if caught
                if caught_contradiction and self.state.current_witness_state:
                    contradiction_msg = AgentMessage(
                        role=AgentRole.COURT_CLERK,
                        agent_name="[System]",
                        content=f"📊 Contradiction detected! The witness's credibility has been affected.",
                        phase=CourtPhase.EXAMINATION
                    )
                    messages.append(contradiction_msg)

                # Add witness state change events
                if credibility_effect.get("events"):
                    for event in credibility_effect["events"]:
                        event_msg = AgentMessage(
                            role=AgentRole.COURT_CLERK,
                            agent_name="[Witness State]",
                            content=f"⚖️ {event}",
                            phase=CourtPhase.EXAMINATION
                        )
                        messages.append(event_msg)
                        self.state.messages.append(event_msg)

                # Handle hostile witness event
                if credibility_effect.get("hostile"):
                    judge: JudgeAgent = self.agents['judge']
                    hostile_ruling = judge.respond(
                        f"The Court observes that the witness {witness.name} is displaying hostile behavior. "
                        f"Counsel may treat this witness as a hostile witness and proceed with leading questions.",
                        CourtPhase.EXAMINATION
                    )
                    messages.append(hostile_ruling)
                    self.state.messages.append(hostile_ruling)

                # Handle breakdown event
                if credibility_effect.get("breakdown"):
                    judge: JudgeAgent = self.agents['judge']
                    breakdown_ruling = judge.respond(
                        f"The Court will take a brief recess. The witness appears to be in distress. "
                        f"Counsel, please be mindful of the witness's state when examination resumes.",
                        CourtPhase.EXAMINATION
                    )
                    messages.append(breakdown_ruling)
                    self.state.messages.append(breakdown_ruling)

                # Possible opponent objection (modified by questioning style)
                objection_chance = 0.2
                if questioning_style == QuestioningStyle.LEADING and self._is_cross_examination() is False:
                    objection_chance = 0.6  # Higher chance for leading during direct
                elif questioning_style == QuestioningStyle.AGGRESSIVE:
                    objection_chance = 0.35
                elif questioning_style == QuestioningStyle.CONFUSING:
                    objection_chance = 0.3

                if random.random() < objection_chance:
                    opponent: LawyerAgent = self.agents['opponent']

                    # Choose objection type based on questioning style
                    objection_ground = "The question is improper"
                    if questioning_style == QuestioningStyle.LEADING:
                        objection_ground = "Objection! The question is leading."
                    elif questioning_style == QuestioningStyle.AGGRESSIVE:
                        objection_ground = "Objection! Counsel is badgering the witness."
                    elif questioning_style == QuestioningStyle.CONFUSING:
                        objection_ground = "Objection! The question is compound and confusing."

                    objection = opponent.raise_objection(objection_ground)
                    messages.append(objection)
                    self.state.messages.append(objection)

                    # Judge ruling
                    judge: JudgeAgent = self.agents['judge']
                    ruling = judge.rule_on_objection(objection.content, f"During examination of {witness.name}")
                    messages.append(ruling)
                    self.state.messages.append(ruling)
        else:
            # During opening/arguments phases - direct question to opposing counsel
            opponent: LawyerAgent = self.agents['opponent']
            opponent_response = opponent.respond(
                f"The opposing counsel has asked: '{action.content}'\n\n"
                f"Answer this question directly, presenting your client's position and supporting evidence.",
                CourtPhase.PETITIONER_ARGUMENTS if self.state.player_side == PlayerSide.RESPONDENT else CourtPhase.RESPONDENT_ARGUMENTS
            )
            messages.append(opponent_response)
            self.state.messages.append(opponent_response)

            # Judge may add a comment (20% chance)
            if random.random() < 0.2:
                judge: JudgeAgent = self.agents['judge']
                judge_response = judge.respond(
                    f"The Court has noted the exchange between learned counsels.",
                    CourtPhase.PETITIONER_ARGUMENTS
                )
                messages.append(judge_response)
                self.state.messages.append(judge_response)

        return messages

    def _process_objection(self, action: GameAction) -> List[AgentMessage]:
        """Process an objection from the player."""
        messages = []
        self.state.objections_made += 1

        # Player's objection
        player_msg = AgentMessage(
            role=AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL,
            agent_name="You (Player)",
            content=f"OBJECTION! {action.objection_type.value if action.objection_type else action.content}",
            phase=CourtPhase.EXAMINATION
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)

        # Judge's ruling
        judge: JudgeAgent = self.agents['judge']
        ruling = judge.rule_on_objection(
            action.content,
            f"Player objects on grounds: {action.objection_type.value if action.objection_type else 'general'}"
        )
        messages.append(ruling)
        self.state.messages.append(ruling)

        # Check if sustained
        if "sustained" in ruling.content.lower():
            self.state.objections_sustained += 1
            self.state.score.objection_success += 5

        return messages

    def _process_evidence(self, action: GameAction) -> List[AgentMessage]:
        """Process evidence presentation."""
        messages = []

        # Player presents evidence
        player_msg = AgentMessage(
            role=AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL,
            agent_name="You (Player)",
            content=f"I present to the court: {action.content}",
            phase=CourtPhase.EXAMINATION
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)
        self.state.evidence_presented.append(action.content)

        # Judge acknowledges
        judge: JudgeAgent = self.agents['judge']
        judge_response = judge.respond(
            f"Counsel presents evidence: {action.content}",
            CourtPhase.EXAMINATION
        )
        messages.append(judge_response)
        self.state.messages.append(judge_response)

        self.state.score.evidence_handling += 3

        return messages

    def _process_citation(self, action: GameAction) -> List[AgentMessage]:
        """Process case law citation."""
        messages = []

        player_msg = AgentMessage(
            role=AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL,
            agent_name="You (Player)",
            content=f"I cite the following precedent: {action.content}",
            phase=CourtPhase.FINAL_ARGUMENTS
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)

        # Judge acknowledges citation
        judge: JudgeAgent = self.agents['judge']
        judge_response = judge.respond(
            f"Counsel cites: {action.content}. How does this apply to the present case?",
            CourtPhase.FINAL_ARGUMENTS
        )
        messages.append(judge_response)
        self.state.messages.append(judge_response)

        self.state.score.legal_accuracy += 5

        return messages

    def _process_no_questions(self) -> List[AgentMessage]:
        """Process when player has no more questions."""
        messages = []

        player_msg = AgentMessage(
            role=AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL,
            agent_name="You (Player)",
            content="No further questions, My Lord.",
            phase=CourtPhase.EXAMINATION
        )
        messages.append(player_msg)
        self.state.messages.append(player_msg)

        # Move to next witness or phase
        self.state.current_witness_index += 1

        return messages

    def _process_rest_case(self) -> Dict[str, Any]:
        """
        Process when player indicates they have concluded their submissions.
        Judge decides whether to accept and move to next phase.
        """
        result = {"messages": [], "phase_changed": False}

        judge: JudgeAgent = self.agents['judge']
        player_role = AgentRole.PETITIONER_COUNSEL if self.state.player_side == PlayerSide.PETITIONER else AgentRole.RESPONDENT_COUNSEL

        # Player's statement
        rest_statements = {
            GamePhase.OPENING_STATEMENT: "My Lord, that concludes my opening statement.",
            GamePhase.PETITIONER_WITNESS_EXAM: "My Lord, that concludes the examination of this witness.",
            GamePhase.RESPONDENT_WITNESS_EXAM: "My Lord, that concludes the examination of this witness.",
            GamePhase.CROSS_EXAMINATION: "No further questions for this witness, My Lord.",
            GamePhase.FINAL_ARGUMENTS: "My Lord, that concludes my final submissions. I rest my case."
        }

        player_msg = AgentMessage(
            role=player_role,
            agent_name="You (Player)",
            content=rest_statements.get(self.state.phase, "My Lord, I have no further submissions."),
            phase=CourtPhase.FINAL_ARGUMENTS
        )
        result["messages"].append(player_msg)
        self.state.messages.append(player_msg)

        # Judge acknowledges and decides
        phase_turns = self.state.phase_turn_number
        limits = PHASE_LIMITS.get(self.state.phase)
        min_turns = 1 if not limits else max(1, limits.warning_at - 2)

        if phase_turns < min_turns:
            # Too early - Judge asks if counsel is sure
            judge_response = judge.respond(
                f"Counsel, you have concluded rather quickly. "
                f"Are you certain you have nothing further to add? "
                f"The Court will accept your submission if you confirm.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(judge_response)
            self.state.messages.append(judge_response)

            # Automatically accept since player explicitly rested
            confirm_msg = judge.respond(
                "Very well, the Court accepts counsel's submission. We shall proceed.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(confirm_msg)
            self.state.messages.append(confirm_msg)

        else:
            # Normal acceptance
            judge_response = judge.respond(
                "The Court notes that learned counsel has concluded submissions. "
                "We shall proceed to the next stage.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(judge_response)
            self.state.messages.append(judge_response)

        # Advance phase
        self._advance_phase()
        result["phase_changed"] = True

        # Announce new phase and handle AI turns
        phase_messages = self._judge_announce_new_phase()
        result["messages"].extend(phase_messages)

        return result

    def _get_opponent_response(self) -> AgentMessage:
        """Get AI opponent's response/action."""
        opponent: LawyerAgent = self.agents['opponent']

        if self.state.phase == GamePhase.OPENING_STATEMENT:
            return opponent.make_opening_statement()
        elif self.state.phase == GamePhase.FINAL_ARGUMENTS:
            return opponent.make_final_argument()
        else:
            # Generate appropriate response based on phase
            return opponent.respond(
                f"Respond to the current proceedings in phase: {self.state.phase.value}",
                CourtPhase.EXAMINATION
            )

    def run_ai_turn(self) -> List[AgentMessage]:
        """
        Run the AI's turn - used when AI needs to act first.
        Returns list of messages generated.
        """
        messages = []
        judge: JudgeAgent = self.agents['judge']
        opponent: LawyerAgent = self.agents['opponent']

        if self.state.phase == GamePhase.OPENING_STATEMENT:
            # AI makes opening statement
            opening = opponent.make_opening_statement()
            messages.append(opening)
            self.state.messages.append(opening)

            # Judge responds
            judge_response = judge.respond(
                f"The court has heard the opening statement. "
                f"Counsel for {'respondent' if self.state.player_side == PlayerSide.RESPONDENT else 'petitioner'}, "
                f"you may now present your opening statement.",
                CourtPhase.OPENING
            )
            messages.append(judge_response)
            self.state.messages.append(judge_response)

        elif self.state.phase == GamePhase.PETITIONER_WITNESS_EXAM:
            if self.state.player_side == PlayerSide.RESPONDENT:
                # AI (petitioner) examines their witness
                messages.extend(self._ai_examine_witness(is_petitioner_witness=True))

        elif self.state.phase == GamePhase.RESPONDENT_WITNESS_EXAM:
            if self.state.player_side == PlayerSide.PETITIONER:
                # AI (respondent) examines their witness
                messages.extend(self._ai_examine_witness(is_petitioner_witness=False))

        elif self.state.phase == GamePhase.CROSS_EXAMINATION:
            # AI cross-examines
            messages.extend(self._ai_cross_examine())

        elif self.state.phase == GamePhase.FINAL_ARGUMENTS:
            # AI makes final argument
            final_arg = opponent.make_final_argument()
            messages.append(final_arg)
            self.state.messages.append(final_arg)

            judge_response = judge.respond(
                "The court has heard the arguments. Counsel for the other side may now present their final arguments.",
                CourtPhase.FINAL_ARGUMENTS
            )
            messages.append(judge_response)
            self.state.messages.append(judge_response)

        self.state.is_player_turn = True
        return messages

    def _ai_examine_witness(self, is_petitioner_witness: bool) -> List[AgentMessage]:
        """AI examines their own witness."""
        messages = []
        judge: JudgeAgent = self.agents['judge']
        clerk: CourtClerkAgent = self.agents['clerk']

        # Get appropriate witness list
        witnesses = self.agents['petitioner_witnesses'] if is_petitioner_witness else self.agents['respondent_witnesses']

        if self.state.current_witness_index < len(witnesses):
            witness: WitnessAgent = witnesses[self.state.current_witness_index]

            # Clerk calls witness
            call_msg = clerk.call_witness(witness.witness_data)
            messages.append(call_msg)
            self.state.messages.append(call_msg)

            # AI counsel examines (ask 2-3 questions)
            examining_counsel = self.agents['opponent']
            questions = examining_counsel.examine_witness(witness.witness_data, is_cross=False)

            for q in questions[:3]:  # Limit to 3 questions
                # Question
                q_msg = AgentMessage(
                    role=examining_counsel.role,
                    agent_name=examining_counsel.name,
                    content=q,
                    phase=CourtPhase.EXAMINATION
                )
                messages.append(q_msg)
                self.state.messages.append(q_msg)

                # Witness answer
                answer = witness.respond(q, CourtPhase.EXAMINATION)
                messages.append(answer)
                self.state.messages.append(answer)

            # Judge invites cross-examination
            judge_invite = judge.respond(
                f"Examination-in-chief of {witness.name} is complete. "
                f"Counsel for the {'respondent' if is_petitioner_witness else 'petitioner'}, "
                f"you may cross-examine the witness.",
                CourtPhase.EXAMINATION
            )
            messages.append(judge_invite)
            self.state.messages.append(judge_invite)

            self.state.current_witness = witness.witness_data

        return messages

    def _ai_cross_examine(self) -> List[AgentMessage]:
        """AI cross-examines a witness."""
        messages = []

        if self.state.current_witness_index < len(self.agents['witnesses']):
            witness: WitnessAgent = self.agents['witnesses'][self.state.current_witness_index]
            opponent: LawyerAgent = self.agents['opponent']

            # AI asks cross-examination questions
            questions = opponent.examine_witness(witness.witness_data, is_cross=True)

            for q in questions[:2]:  # Limit to 2 questions
                q_msg = AgentMessage(
                    role=opponent.role,
                    agent_name=opponent.name,
                    content=q,
                    phase=CourtPhase.CROSS_EXAMINATION
                )
                messages.append(q_msg)
                self.state.messages.append(q_msg)

                answer = witness.respond(q, CourtPhase.CROSS_EXAMINATION)
                messages.append(answer)
                self.state.messages.append(answer)

            # Indicate cross done
            done_msg = AgentMessage(
                role=opponent.role,
                agent_name=opponent.name,
                content="No further questions, My Lord.",
                phase=CourtPhase.CROSS_EXAMINATION
            )
            messages.append(done_msg)
            self.state.messages.append(done_msg)

        return messages

    def request_next_phase(self) -> Dict[str, Any]:
        """
        Player requests the Judge to move to the next phase.
        Judge decides whether to grant the request based on proceedings.
        """
        result = {
            "messages": [],
            "phase": self.state.phase,
            "is_player_turn": self.state.is_player_turn,
            "request_granted": False,
            "instructions": self._get_phase_instructions()
        }

        judge: JudgeAgent = self.agents['judge']
        phase_turns = self.state.phase_turn_number
        limits = PHASE_LIMITS.get(self.state.phase)

        # Determine if Judge grants the request
        # Judge is more likely to grant if:
        # - Player has made at least minimum submissions
        # - Warning has been given
        # - Close to max turns

        min_turns_required = 1 if not limits else max(1, limits.warning_at - 1)

        if phase_turns < min_turns_required:
            # Too early - Judge denies
            denial = judge.respond(
                f"Counsel, you have barely begun your submissions. "
                f"The Court expects you to make your arguments properly. Please proceed.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(denial)
            self.state.messages.append(denial)
            return result

        # Judge grants the request
        grant_msg = judge.respond(
            "Very well. If learned counsel has no further submissions, "
            "the Court will proceed to the next stage of proceedings.",
            CourtPhase.EXAMINATION
        )
        result["messages"].append(grant_msg)
        self.state.messages.append(grant_msg)

        # Advance phase
        self._advance_phase()
        result["request_granted"] = True
        result["phase"] = self.state.phase

        # Announce new phase and handle AI turns
        phase_messages = self._judge_announce_new_phase()
        result["messages"].extend(phase_messages)

        result["is_player_turn"] = self.state.is_player_turn
        result["instructions"] = self._get_phase_instructions()

        return result

    def proceed_to_next_phase(self) -> Dict[str, Any]:
        """
        Legacy method - now redirects to request_next_phase for backward compatibility.
        Judge-controlled advancement.
        """
        return self.request_next_phase()

    def _should_advance_phase(self) -> bool:
        """Check if should move to next phase - now controlled by Judge."""
        # Judge controls phase advancement through _judge_evaluate_proceedings()
        return False

    def _advance_phase(self) -> None:
        """Advance to next game phase."""
        # Define phase transitions
        phase_transitions = {
            GamePhase.SETUP: GamePhase.OPENING_STATEMENT,
            GamePhase.OPENING_STATEMENT: GamePhase.PETITIONER_WITNESS_EXAM,
            GamePhase.PETITIONER_WITNESS_EXAM: GamePhase.CROSS_EXAMINATION,
            GamePhase.CROSS_EXAMINATION: GamePhase.RESPONDENT_WITNESS_EXAM,
            GamePhase.RESPONDENT_WITNESS_EXAM: GamePhase.FINAL_ARGUMENTS,
            GamePhase.FINAL_ARGUMENTS: GamePhase.JUDGMENT,
            GamePhase.JUDGMENT: GamePhase.GAME_OVER
        }

        if self.state.phase in phase_transitions:
            self.state.phase = phase_transitions[self.state.phase]
            self._emit("phase_change", self.state.phase)

            # Reset phase-specific state
            self.state.phase_turn_number = 0
            self.state.judge_warnings_in_phase = 0
            self.state.extension_granted = False
            self.state.is_first_action_in_phase = True  # Reset for new phase

            # Reset legal research for new phase
            self.reset_phase_research()

            # Reset sidebar conference count for new phase
            self.reset_phase_sidebars()

            # Reset witness index for new examination phase
            if self.state.phase in [GamePhase.PETITIONER_WITNESS_EXAM, GamePhase.RESPONDENT_WITNESS_EXAM]:
                self.state.current_witness_index = 0

    def _deliver_judgment(self) -> AgentMessage:
        """Have the judge deliver judgment."""
        judge: JudgeAgent = self.agents['judge']
        judgment = judge.deliver_judgment()
        self.state.messages.append(judgment)
        self.state.phase = GamePhase.GAME_OVER
        self._emit("game_over", self.state.score)
        return judgment

    def _update_score(self, action: GameAction, results: Dict) -> None:
        """Update player's score based on action."""
        score = self.state.score

        # Base points for actions
        action_points = {
            ActionType.MAKE_ARGUMENT: 10,
            ActionType.ASK_QUESTION: 5,
            ActionType.RAISE_OBJECTION: 3,
            ActionType.PRESENT_EVIDENCE: 8,
            ActionType.CITE_CASE_LAW: 7,
            ActionType.CROSS_EXAMINE: 6
        }

        score.total_points += action_points.get(action.action_type, 0)

        # Adjust based on events
        for event in results.get("events", []):
            score.total_points -= int(event.difficulty_modifier * 10)

        # Update judge favor based on performance
        if score.objection_success > score.objection_success * 0.5:
            score.judge_favor = min(100, score.judge_favor + 2)

        self._emit("score_update", score)

    def handle_event_response(self, event: DynamicEvent, response_index: int) -> Dict[str, Any]:
        """Handle player's response to a dynamic event."""
        if not event.response_options or response_index >= len(event.response_options):
            return {"success": False, "message": "Invalid response"}

        chosen_response = event.response_options[response_index]

        # Process response based on event type
        messages = []

        if event.event_type == DynamicEventType.WITNESS_HOSTILE:
            judge: JudgeAgent = self.agents['judge']
            if response_index == 0:  # Request hostile declaration
                response = judge.respond(
                    "Counsel requests the court to declare the witness hostile.",
                    CourtPhase.EXAMINATION
                )
                self.state.score.legal_accuracy += 5
            else:
                response = judge.respond(
                    f"Counsel has chosen to: {chosen_response}",
                    CourtPhase.EXAMINATION
                )
            messages.append(response)

        elif event.event_type == DynamicEventType.NEW_EVIDENCE:
            judge: JudgeAgent = self.agents['judge']
            response = judge.respond(
                f"Regarding the new evidence, counsel moves to: {chosen_response}",
                CourtPhase.EXAMINATION
            )
            messages.append(response)

        return {
            "success": True,
            "messages": messages,
            "chosen_response": chosen_response
        }

    def get_game_summary(self) -> Dict[str, Any]:
        """Get complete game summary."""
        return {
            "case_title": self.case.case_metadata.case_title,
            "player_side": self.state.player_side.value if self.state.player_side else None,
            "total_turns": self.state.turn_number,
            "final_phase": self.state.phase.value,
            "score": {
                "total_points": self.state.score.total_points,
                "judge_favor": self.state.score.judge_favor,
                "weighted_score": self.state.score.calculate_total(),
                "details": {
                    "legal_accuracy": self.state.score.legal_accuracy,
                    "persuasiveness": self.state.score.persuasiveness,
                    "evidence_handling": self.state.score.evidence_handling,
                    "witness_examination": self.state.score.witness_examination,
                    "objection_success": self.state.score.objection_success,
                    "courtroom_decorum": self.state.score.courtroom_decorum
                }
            },
            "statistics": {
                "objections_made": self.state.objections_made,
                "objections_sustained": self.state.objections_sustained,
                "evidence_presented": len(self.state.evidence_presented),
                "warnings_received": self.state.warnings_received,
                "events_occurred": len(self.state.events_occurred)
            },
            "events": [
                {"type": e.event_type.value, "description": e.description}
                for e in self.state.events_occurred
            ]
        }
