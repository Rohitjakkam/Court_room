from enum import Enum
from typing import Optional
from pydantic import BaseModel


class RoleType(str, Enum):
    JUDGE = "Judge"
    PROSECUTOR = "Public Prosecutor"
    DEFENCE = "Defence Counsel"
    ACCUSED = "Accused"
    WITNESS_PW = "Prosecution Witness"
    WITNESS_DW = "Defence Witness"
    CLERK = "Court Clerk"


class TrialStage(str, Enum):
    PRE_TRIAL = "PRE_TRIAL"
    COGNIZANCE = "COGNIZANCE"
    CHARGE = "CHARGE"
    PROSECUTION_OPENING = "PROSECUTION_OPENING"
    WITNESS_EXAMINATION = "WITNESS_EXAMINATION"
    ACCUSED_STATEMENT = "ACCUSED_STATEMENT"
    DEFENCE_EVIDENCE = "DEFENCE_EVIDENCE"
    FINAL_ARGUMENTS = "FINAL_ARGUMENTS"
    JUDGMENT = "JUDGMENT"


STAGE_DISPLAY = {
    TrialStage.PRE_TRIAL: "Stage 1: Case Comes to Court (Pre-Trial)",
    TrialStage.COGNIZANCE: "Stage 2: Taking Cognizance & Supply of Documents",
    TrialStage.CHARGE: "Stage 3: Charge Stage",
    TrialStage.PROSECUTION_OPENING: "Stage 4: Prosecution Evidence",
    TrialStage.WITNESS_EXAMINATION: "Stage 5: Examination of Prosecution Witnesses",
    TrialStage.ACCUSED_STATEMENT: "Stage 6: Statement of Accused",
    TrialStage.DEFENCE_EVIDENCE: "Stage 7: Defence Evidence",
    TrialStage.FINAL_ARGUMENTS: "Stage 8: Final Arguments",
    TrialStage.JUDGMENT: "Stage 9: Judgment",
}

STAGE_ORDER = list(TrialStage)


class WitnessExamPhase(str, Enum):
    CHIEF = "Examination-in-Chief"
    CROSS = "Cross-Examination"
    RE_EXAMINATION = "Re-Examination"


class EvidenceStatus(str, Enum):
    NOT_PRESENTED = "Not Presented"
    PRESENTED = "Presented"
    EXHIBITED = "Exhibited"
    OBJECTED = "Objected"


class Evidence(BaseModel):
    id: str
    name: str
    description: str
    evidence_type: str  # documentary, oral, physical
    presented_by: str  # prosecution or defence
    status: EvidenceStatus = EvidenceStatus.NOT_PRESENTED


class Character(BaseModel):
    name: str
    role: RoleType
    designation: str  # e.g. "PW-1", "DW-1", "Sessions Judge"
    description: str
    personality: str
    facts_known: str  # what this character knows about the case
    chief_exam_topics: list[str] = []  # topics prosecutor should cover
    cross_exam_points: list[str] = []  # weak points defence should target


class CaseInfo(BaseModel):
    title: str
    case_number: str
    court: str
    sections: list[str]
    fir_number: str
    fir_date: str
    fir_summary: str
    incident_date: str
    incident_summary: str
    prosecution_story: str
    defence_story: str


class Dialogue(BaseModel):
    speaker: str
    role: RoleType
    text: str
    stage: TrialStage
    is_player: bool = False


class GameState(BaseModel):
    current_stage: TrialStage = TrialStage.PRE_TRIAL
    player_role: Optional[RoleType] = None
    dialogues: list[Dialogue] = []
    current_witness_index: int = 0
    current_exam_phase: WitnessExamPhase = WitnessExamPhase.CHIEF
    evidence_list: list[Evidence] = []
    is_defence_evidence_phase: bool = False
    dw_index: int = 0
    dw_exam_phase: WitnessExamPhase = WitnessExamPhase.CHIEF
    verdict: Optional[str] = None
    stage_initialized: bool = False
    waiting_for_player: bool = False
    sub_step: int = 0
    final_arg_turn: str = "prosecution"  # prosecution or defence
    # Track exam question count per witness to follow structured topics
    witness_question_count: int = 0
    # Store chief-exam transcript per witness index for cross-exam reference
    chief_exam_transcripts: dict[int, list[str]] = {}
    dw_chief_exam_transcripts: dict[int, list[str]] = {}
