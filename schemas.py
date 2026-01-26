"""
Pydantic Schema for Court Case & Judgement Extraction
Covers all 15 layers of court case metadata
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date
from enum import Enum


# ============================================================
# ENUMS
# ============================================================

class CaseType(str, Enum):
    MACT = "MACT"
    CIVIL = "Civil"
    CRIMINAL = "Criminal"
    WRIT = "Writ"
    APPEAL = "Appeal"
    OTHER = "Other"


class PartyRole(str, Enum):
    DRIVER = "Driver"
    OWNER = "Owner"
    INSURER = "Insurer"
    OTHER = "Other"


class LegalStatus(str, Enum):
    INJURED = "Injured"
    DECEASED = "Deceased"
    CLAIMANT = "Claimant"
    LEGAL_REPRESENTATIVE = "Legal Representative"


class IssueFinding(str, Enum):
    PROVED = "Proved"
    NOT_PROVED = "Not Proved"
    PARTLY_PROVED = "Partly Proved"


class WitnessType(str, Enum):
    PW = "PW"  # Petitioner Witness
    RW = "RW"  # Respondent Witness
    CW = "CW"  # Court Witness


class DisabilityType(str, Enum):
    PERMANENT = "Permanent"
    TEMPORARY = "Temporary"


class JudgmentTone(str, Enum):
    CLAIMANT_FRIENDLY = "Claimant Friendly"
    RESPONDENT_FRIENDLY = "Respondent Friendly"
    NEUTRAL = "Neutral"


class NegligenceType(str, Enum):
    RASH_DRIVING = "Rash Driving"
    WRONG_SIDE = "Wrong Side"
    OVER_SPEEDING = "Over Speeding"
    DRUNK_DRIVING = "Drunk Driving"
    SIGNAL_VIOLATION = "Signal Violation"
    OTHER = "Other"


# ============================================================
# 1. CASE METADATA (Court Identity Layer)
# ============================================================

class CaseDates(BaseModel):
    """Important dates in the case lifecycle"""
    institution: Optional[date] = Field(None, description="Date case was filed")
    arguments: Optional[date] = Field(None, description="Date of final arguments")
    judgment: Optional[date] = Field(None, description="Date of judgment/award")


class CaseMetadata(BaseModel):
    """Section 1: Case Metadata - Court Identity Layer"""
    case_title: str = Field(..., description="Petitioner vs Respondents")
    main_case_number: Optional[str] = Field(None, description="Main case no. (e.g., MACP No.)")
    fir_number: Optional[str] = Field(None, description="FIR Number")
    cnr_uid_number: Optional[str] = Field(None, description="CNR / UID Number")
    case_type: CaseType = Field(..., description="Type of case")
    relevant_acts_sections: List[str] = Field(default_factory=list, description="e.g., MV Act §166, IPC §279")
    court_name: str = Field(..., description="Name of the court")
    judge_name: Optional[str] = Field(None, description="Judge name")
    judge_designation: Optional[str] = Field(None, description="Judge designation")
    court_location: Optional[str] = Field(None, description="Court location/city")
    case_dates: CaseDates = Field(default_factory=CaseDates)
    source_reference: Optional[str] = Field(None, description="Indian Kanoon / Court copy reference")


# ============================================================
# 2. PARTY DETAILS (Role Assignment Layer)
# ============================================================

class Petitioner(BaseModel):
    """Petitioner/Claimant details"""
    full_name: str = Field(..., description="Full name of petitioner")
    parentage: Optional[str] = Field(None, description="Father's/Guardian's name")
    address: Optional[str] = Field(None, description="Address")
    legal_status: LegalStatus = Field(..., description="Legal status")
    occupation: Optional[str] = Field(None, description="Occupation")
    income_claimed: Optional[float] = Field(None, description="Income claimed")
    income_proved: Optional[float] = Field(None, description="Income proved in court")
    age: Optional[int] = Field(None, description="Age at time of incident")


class InsuranceDetails(BaseModel):
    """Insurance policy details"""
    company_name: Optional[str] = Field(None, description="Insurance company name")
    policy_number: Optional[str] = Field(None, description="Policy number")
    policy_status: Optional[str] = Field(None, description="Policy status (valid/expired/fake)")
    coverage_amount: Optional[float] = Field(None, description="Coverage amount")


class Respondent(BaseModel):
    """Respondent details"""
    name: str = Field(..., description="Name of respondent")
    role: PartyRole = Field(..., description="Role (driver/owner/insurer)")
    is_alive: bool = Field(True, description="Whether alive or deceased")
    legal_representatives: Optional[List[str]] = Field(None, description="LRs if deceased")
    address: Optional[str] = Field(None, description="Address")
    representation: Optional[str] = Field(None, description="Advocate name or ex-parte")
    is_ex_parte: bool = Field(False, description="Whether proceeding ex-parte")
    insurance_details: Optional[InsuranceDetails] = None


class PartyDetails(BaseModel):
    """Section 2: Party Details - Role Assignment Layer"""
    petitioners: List[Petitioner] = Field(default_factory=list)
    respondents: List[Respondent] = Field(default_factory=list)


# ============================================================
# 3. LEGAL REPRESENTATION (Advocacy Layer)
# ============================================================

class LegalRepresentation(BaseModel):
    """Section 3: Legal Representation - Advocacy Layer"""
    counsel_for_petitioner: List[str] = Field(default_factory=list)
    counsel_for_respondents: List[str] = Field(default_factory=list)
    parties_appearing: List[str] = Field(default_factory=list)
    parties_not_appearing: List[str] = Field(default_factory=list)
    written_statement_filed: bool = Field(False, description="Whether WS/reply was filed")


# ============================================================
# 4. FACTUAL MATRIX (Accident / Cause of Action Layer)
# ============================================================

class VehicleInvolved(BaseModel):
    """Details of vehicle involved in accident"""
    registration_number: str = Field(..., description="Vehicle registration number")
    vehicle_type: Optional[str] = Field(None, description="Type of vehicle")
    direction_of_movement: Optional[str] = Field(None, description="Direction vehicle was moving")
    owner: Optional[str] = Field(None, description="Owner of vehicle")
    driver: Optional[str] = Field(None, description="Driver at time of accident")


class FIRDetails(BaseModel):
    """FIR registration details"""
    fir_date: Optional[date] = Field(None, description="Date of FIR")
    delay_in_days: Optional[int] = Field(None, description="Delay in FIR registration")
    delay_explanation: Optional[str] = Field(None, description="Explanation for delay")
    police_station: Optional[str] = Field(None, description="Police station name")
    gd_entry: Optional[str] = Field(None, description="GD entry number")


class FactualMatrix(BaseModel):
    """Section 4: Factual Matrix - Accident/Cause of Action Layer"""
    incident_date: Optional[date] = Field(None, description="Date of incident")
    incident_time: Optional[str] = Field(None, description="Time of incident")
    place_of_occurrence: Optional[str] = Field(None, description="Exact location")
    vehicles_involved: List[VehicleInvolved] = Field(default_factory=list)
    alleged_manner_of_accident: Optional[str] = Field(None, description="How accident occurred")
    nature_of_negligence: List[NegligenceType] = Field(default_factory=list)
    immediate_medical_response: Optional[str] = Field(None, description="First aid/hospital taken to")
    fir_details: FIRDetails = Field(default_factory=FIRDetails)


# ============================================================
# 5. PROCEDURAL HISTORY (Timeline Engine)
# ============================================================

class ProceduralEvent(BaseModel):
    """A procedural event in the case timeline"""
    event_date: Optional[date] = Field(None)
    event_description: str = Field(...)
    event_type: Optional[str] = Field(None)


class ProceduralHistory(BaseModel):
    """Section 5: Procedural History - Timeline Engine"""
    dar_chargesheet_date: Optional[date] = Field(None, description="Filing of DAR/chargesheet")
    dar_treated_as_claim: bool = Field(False, description="DAR treated as claim petition")
    issues_framed_date: Optional[date] = Field(None, description="Date issues were framed")
    pe_closed_date: Optional[date] = Field(None, description="Petitioner evidence closed")
    re_closed_date: Optional[date] = Field(None, description="Respondent evidence closed")
    interim_offers: List[str] = Field(default_factory=list)
    legal_offers: List[str] = Field(default_factory=list)
    defaults_by_parties: List[str] = Field(default_factory=list)
    timeline_events: List[ProceduralEvent] = Field(default_factory=list)


# ============================================================
# 6. ISSUES FRAMED (Decision Tree Core)
# ============================================================

class IssueFramed(BaseModel):
    """An issue framed by the court"""
    issue_number: int = Field(..., description="Issue number")
    issue_text: str = Field(..., description="Exact wording of the issue")
    onus_of_proof: str = Field(..., description="OPP/OPR - who bears burden")
    finding: IssueFinding = Field(..., description="Court's finding")
    reasoning: Optional[str] = Field(None, description="Brief reasoning for finding")


class IssuesFramed(BaseModel):
    """Section 6: Issues Framed - Decision Tree Core"""
    issues: List[IssueFramed] = Field(default_factory=list)


# ============================================================
# 7. EVIDENCE DETAILS (Proof Evaluation Layer)
# ============================================================

class OralWitness(BaseModel):
    """Oral testimony details"""
    witness_number: str = Field(..., description="PW1, RW2, etc.")
    witness_type: WitnessType = Field(...)
    name: str = Field(...)
    affidavit_reference: Optional[str] = Field(None)
    examination_in_chief_summary: Optional[str] = Field(None)
    cross_examination_highlights: Optional[str] = Field(None)
    admissions: List[str] = Field(default_factory=list)
    contradictions: List[str] = Field(default_factory=list)


class DocumentaryExhibit(BaseModel):
    """Documentary evidence"""
    exhibit_number: str = Field(..., description="Ex. PW1/A, etc.")
    description: str = Field(...)
    party_relying: str = Field(...)
    court_view: str = Field(..., description="Accepted/Disputed/Rejected")
    relevance: Optional[str] = Field(None)


class EvidenceDetails(BaseModel):
    """Section 7: Evidence Details - Proof Evaluation Layer"""
    oral_witnesses: List[OralWitness] = Field(default_factory=list)
    documentary_exhibits: List[DocumentaryExhibit] = Field(default_factory=list)


# ============================================================
# 8. MEDICAL & DISABILITY EVIDENCE (Injury Engine)
# ============================================================

class MedicalTreatment(BaseModel):
    """Medical treatment details"""
    hospital_name: str = Field(...)
    admission_date: Optional[date] = Field(None)
    discharge_date: Optional[date] = Field(None)
    nature_of_injuries: List[str] = Field(default_factory=list)
    surgical_procedures: List[str] = Field(default_factory=list)


class DisabilityCertificate(BaseModel):
    """Disability assessment details"""
    percentage: float = Field(..., description="Disability percentage")
    limb_affected: Optional[str] = Field(None)
    disability_type: DisabilityType = Field(...)
    functional_disability: Optional[float] = Field(None, description="Functional disability %")
    issuing_authority: Optional[str] = Field(None)


class MedicalEvidence(BaseModel):
    """Section 8: Medical & Disability Evidence - Injury Engine"""
    treatments: List[MedicalTreatment] = Field(default_factory=list)
    disability_certificates: List[DisabilityCertificate] = Field(default_factory=list)
    total_disability_percentage: Optional[float] = Field(None)


# ============================================================
# 9. INCOME & EMPLOYMENT PROOF (Economic Loss Layer)
# ============================================================

class IncomeProof(BaseModel):
    """Section 9: Income & Employment Proof - Economic Loss Layer"""
    employer_name: Optional[str] = Field(None)
    job_title: Optional[str] = Field(None)
    salary_slips_available: bool = Field(False)
    income_claimed: Optional[float] = Field(None)
    income_accepted_by_court: Optional[float] = Field(None)
    loss_of_income_claimed: Optional[float] = Field(None)
    loss_of_income_proved: Optional[float] = Field(None)
    loss_of_income_rejected: Optional[float] = Field(None)
    rejection_reasons: Optional[str] = Field(None)
    retirement_age_assumed: Optional[int] = Field(None)
    remaining_working_years: Optional[int] = Field(None)


# ============================================================
# 10. COMPENSATION HEADS (Award Computation Core)
# ============================================================

class CompensationHead(BaseModel):
    """Individual compensation head"""
    head_name: str = Field(..., description="Name of compensation head")
    amount_claimed: Optional[float] = Field(None)
    amount_awarded: Optional[float] = Field(None)
    amount_disallowed: Optional[float] = Field(None)
    disallowance_reason: Optional[str] = Field(None)


class CompensationComputation(BaseModel):
    """Section 10: Compensation Heads - Award Computation Core"""
    heads: List[CompensationHead] = Field(default_factory=list)
    formula_used: Optional[str] = Field(None, description="Computation formula")
    multiplier: Optional[float] = Field(None, description="Multiplier used")
    percentage_applied: Optional[float] = Field(None)
    rounding_off_logic: Optional[str] = Field(None)
    total_claimed: Optional[float] = Field(None)
    total_awarded: Optional[float] = Field(None)


# ============================================================
# 11. CASE LAW & PRECEDENTS (Legal Reasoning Layer)
# ============================================================

class CaseLaw(BaseModel):
    """Cited case law"""
    case_name: str = Field(..., description="Case citation name")
    court: Optional[str] = Field(None, description="Court that decided")
    year: Optional[int] = Field(None)
    legal_principle: str = Field(..., description="Principle relied upon")
    purpose_of_citation: Optional[str] = Field(None, description="Why cited - delay, compensation, etc.")
    citation_reference: Optional[str] = Field(None, description="Full citation")


class CaseLawCitations(BaseModel):
    """Section 11: Case Law & Precedents - Legal Reasoning Layer"""
    citations: List[CaseLaw] = Field(default_factory=list)


# ============================================================
# 12. FINDINGS & RATIO (Judicial Reasoning Core)
# ============================================================

class JudicialFindings(BaseModel):
    """Section 12: Findings & Ratio - Judicial Reasoning Core"""
    negligence_finding: Optional[str] = Field(None, description="Finding on negligence")
    liability_finding: Optional[str] = Field(None, description="Finding on liability")
    contributory_negligence_percentage: Optional[float] = Field(None)
    standard_of_proof_applied: Optional[str] = Field(None)
    reasoning_summary: Optional[str] = Field(None, description="Court's reasoning style")
    adverse_inference_drawn: Optional[str] = Field(None)
    key_observations: List[str] = Field(default_factory=list)


# ============================================================
# 13. FINAL ORDER / RELIEF (Outcome Layer)
# ============================================================

class FinalOrder(BaseModel):
    """Section 13: Final Order/Relief - Outcome Layer"""
    total_compensation_awarded: float = Field(..., description="Total amount awarded")
    interest_rate: Optional[float] = Field(None, description="Interest rate %")
    interest_start_date: Optional[date] = Field(None)
    liable_party: List[str] = Field(default_factory=list, description="Who is liable to pay")
    compliance_time_days: Optional[int] = Field(None, description="Time granted for compliance")
    penalty_for_delay: Optional[str] = Field(None)
    mode_of_disbursement: Optional[str] = Field(None)
    apportionment_instructions: Optional[str] = Field(None)


# ============================================================
# 14. COMPLIANCE & POST-JUDGMENT DIRECTIONS
# ============================================================

class PostJudgmentDirections(BaseModel):
    """Section 14: Compliance & Post-Judgment Directions"""
    bank_instructions: Optional[str] = Field(None)
    forms_annexed: List[str] = Field(default_factory=list, description="MCTAP Forms")
    directions_to_insurer: List[str] = Field(default_factory=list)
    directions_to_claimant: List[str] = Field(default_factory=list)
    copies_to_authorities: List[str] = Field(default_factory=list, description="CJM, DLSA, etc.")


# ============================================================
# 15. MACHINE-READABLE METADATA (For Agents / RAG)
# ============================================================

class MachineMetadata(BaseModel):
    """Section 15: Machine-Readable Metadata - For Agents/RAG"""
    case_category_tags: List[str] = Field(default_factory=list, description="MACT, injury, etc.")
    negligence_types: List[NegligenceType] = Field(default_factory=list)
    dispute_complexity_level: Optional[str] = Field(None, description="Low/Medium/High")
    claim_success_probability: Optional[float] = Field(None, description="0-100%")
    judgment_tone: Optional[JudgmentTone] = Field(None)
    keywords: List[str] = Field(default_factory=list)
    summary: Optional[str] = Field(None, description="Brief case summary")


# ============================================================
# MASTER SCHEMA - Complete Court Case
# ============================================================

class CourtCase(BaseModel):
    """
    Complete Court Case Schema
    Combines all 15 layers for comprehensive case representation
    """
    # Layer 1: Case Identity
    case_metadata: CaseMetadata

    # Layer 2: Parties
    party_details: PartyDetails = Field(default_factory=PartyDetails)

    # Layer 3: Legal Representation
    legal_representation: LegalRepresentation = Field(default_factory=LegalRepresentation)

    # Layer 4: Facts
    factual_matrix: FactualMatrix = Field(default_factory=FactualMatrix)

    # Layer 5: Procedure
    procedural_history: ProceduralHistory = Field(default_factory=ProceduralHistory)

    # Layer 6: Issues
    issues_framed: IssuesFramed = Field(default_factory=IssuesFramed)

    # Layer 7: Evidence
    evidence_details: EvidenceDetails = Field(default_factory=EvidenceDetails)

    # Layer 8: Medical
    medical_evidence: MedicalEvidence = Field(default_factory=MedicalEvidence)

    # Layer 9: Income
    income_proof: IncomeProof = Field(default_factory=IncomeProof)

    # Layer 10: Compensation
    compensation: CompensationComputation = Field(default_factory=CompensationComputation)

    # Layer 11: Case Law
    case_law: CaseLawCitations = Field(default_factory=CaseLawCitations)

    # Layer 12: Findings
    judicial_findings: JudicialFindings = Field(default_factory=JudicialFindings)

    # Layer 13: Final Order
    final_order: Optional[FinalOrder] = None

    # Layer 14: Post-Judgment
    post_judgment: PostJudgmentDirections = Field(default_factory=PostJudgmentDirections)

    # Layer 15: Machine Metadata
    machine_metadata: MachineMetadata = Field(default_factory=MachineMetadata)

    class Config:
        json_schema_extra = {
            "title": "Court Case Schema",
            "description": "Comprehensive schema for Indian court case judgments"
        }
