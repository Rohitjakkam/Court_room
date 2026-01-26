"""
AI Agent Roles for Courtroom Simulation
Judge, Lawyer, and Witness agents with distinct personalities and behaviors
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
from enum import Enum
from dataclasses import dataclass, field
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic

from schemas import CourtCase, OralWitness, IssueFramed


class AgentRole(str, Enum):
    JUDGE = "Judge"
    PETITIONER_COUNSEL = "Petitioner Counsel"
    RESPONDENT_COUNSEL = "Respondent Counsel"
    WITNESS = "Witness"
    COURT_CLERK = "Court Clerk"


class CourtPhase(str, Enum):
    OPENING = "Opening"
    PETITIONER_ARGUMENTS = "Petitioner Arguments"
    RESPONDENT_ARGUMENTS = "Respondent Arguments"
    EXAMINATION = "Examination in Chief"
    CROSS_EXAMINATION = "Cross Examination"
    RE_EXAMINATION = "Re-Examination"
    FINAL_ARGUMENTS = "Final Arguments"
    JUDGMENT = "Judgment"


@dataclass
class AgentMessage:
    """A message from an agent in the courtroom."""
    role: AgentRole
    agent_name: str
    content: str
    phase: CourtPhase
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseCourtAgent(ABC):
    """Base class for all courtroom agents."""

    def __init__(
        self,
        name: str,
        role: AgentRole,
        llm_provider: str = "openai",
        model_name: Optional[str] = None,
        temperature: float = 0.7
    ):
        self.name = name
        self.role = role
        self.temperature = temperature

        if llm_provider == "openai":
            self.llm = ChatOpenAI(
                model=model_name or "gpt-4o",
                temperature=temperature
            )
        elif llm_provider == "anthropic":
            self.llm = ChatAnthropic(
                model=model_name or "claude-3-5-sonnet-20241022",
                temperature=temperature
            )

        self.conversation_history: List[AgentMessage] = []
        self.case_context: Optional[CourtCase] = None

    def set_case_context(self, case: CourtCase):
        """Set the case context for the agent."""
        self.case_context = case

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this agent."""
        pass

    @abstractmethod
    def respond(self, message: str, phase: CourtPhase) -> AgentMessage:
        """Generate a response to a message."""
        pass

    def _format_case_summary(self) -> str:
        """Format key case details for agent context."""
        if not self.case_context:
            return "No case context available."

        case = self.case_context
        summary = f"""
CASE: {case.case_metadata.case_title}
COURT: {case.case_metadata.court_name}
JUDGE: {case.case_metadata.judge_name or 'Unknown'}
TYPE: {case.case_metadata.case_type.value}

PETITIONERS: {', '.join([p.full_name for p in case.party_details.petitioners])}
RESPONDENTS: {', '.join([r.name for r in case.party_details.respondents])}

KEY ISSUES:
{chr(10).join([f"  {i.issue_number}. {i.issue_text}" for i in case.issues_framed.issues])}

COMPENSATION CLAIMED: {case.compensation.total_claimed or 'Not specified'}
"""
        return summary


class JudgeAgent(BaseCourtAgent):
    """
    Judge AI Agent
    - Maintains courtroom decorum
    - Asks clarifying questions
    - Makes rulings on objections
    - Delivers judgment
    """

    def __init__(
        self,
        name: str = "Hon'ble Judge",
        designation: str = "Presiding Officer, Motor Accident Claims Tribunal",
        **kwargs
    ):
        super().__init__(name=name, role=AgentRole.JUDGE, **kwargs)
        self.designation = designation
        self.rulings: List[Dict[str, Any]] = []

    def get_system_prompt(self) -> str:
        return f"""You are {self.name}, {self.designation} presiding over this court case.

PERSONALITY & BEHAVIOR:
- Maintain strict courtroom decorum and formality
- Be impartial and fair to all parties
- Ask probing questions to clarify facts
- Cite relevant legal principles when appropriate
- Use formal judicial language ("This Court observes...", "Let the record reflect...")
- Show patience but be firm when necessary
- Reference Indian legal precedents when relevant

RESPONSIBILITIES:
1. Control courtroom proceedings
2. Rule on objections (sustained/overruled)
3. Ask clarifying questions to witnesses and counsel
4. Ensure proper legal procedure is followed
5. Deliver well-reasoned judgment based on evidence

CASE CONTEXT:
{self._format_case_summary()}

Always respond in character as a distinguished Indian tribunal judge."""

    def respond(self, message: str, phase: CourtPhase) -> AgentMessage:
        """Generate judge's response."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"[{phase.value}]\n\n{message}\n\nProvide your judicial response:")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=phase
        )

    def rule_on_objection(self, objection: str, context: str) -> AgentMessage:
        """Rule on an objection raised in court."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"""An objection has been raised:

OBJECTION: {objection}
CONTEXT: {context}

As the presiding judge, rule on this objection. State whether it is SUSTAINED or OVERRULED, with brief reasoning.""")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        ruling = AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=CourtPhase.EXAMINATION,
            metadata={"type": "objection_ruling"}
        )

        self.rulings.append({
            "objection": objection,
            "ruling": response.content
        })

        return ruling

    def deliver_judgment(self) -> AgentMessage:
        """Deliver final judgment based on case evidence."""
        if not self.case_context:
            raise ValueError("Case context not set")

        findings_summary = ""
        if self.case_context.judicial_findings:
            findings_summary = f"""
NEGLIGENCE: {self.case_context.judicial_findings.negligence_finding or 'To be determined'}
LIABILITY: {self.case_context.judicial_findings.liability_finding or 'To be determined'}
"""

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"""Based on the evidence and arguments presented, deliver your judgment.

{findings_summary}

COMPENSATION HEADS TO CONSIDER:
{chr(10).join([f"- {h.head_name}: Claimed Rs. {h.amount_claimed}" for h in self.case_context.compensation.heads])}

CITED PRECEDENTS:
{chr(10).join([f"- {c.case_name} ({c.year}): {c.legal_principle}" for c in self.case_context.case_law.citations])}

Deliver a comprehensive judgment addressing each issue framed, findings, and the final award.""")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=CourtPhase.JUDGMENT,
            metadata={"type": "final_judgment"}
        )


class LawyerAgent(BaseCourtAgent):
    """
    Lawyer AI Agent
    - Represents either petitioner or respondent
    - Makes arguments and objections
    - Examines and cross-examines witnesses
    - Cites relevant case law
    """

    def __init__(
        self,
        name: str,
        representing: str,  # "petitioner" or "respondent"
        **kwargs
    ):
        role = AgentRole.PETITIONER_COUNSEL if representing == "petitioner" else AgentRole.RESPONDENT_COUNSEL
        super().__init__(name=name, role=role, **kwargs)
        self.representing = representing
        self.arguments_made: List[str] = []
        self.objections_raised: List[str] = []

    def get_system_prompt(self) -> str:
        party = "Petitioner/Claimant" if self.representing == "petitioner" else "Respondent"
        strategy = self._get_strategy()

        return f"""You are Advocate {self.name}, representing the {party} in this case.

PERSONALITY & BEHAVIOR:
- Be eloquent, persuasive, and professional
- Cite relevant case law and statutory provisions
- Use formal legal language ("My Lord", "With respect", "It is submitted that...")
- Be strategic in questioning witnesses
- Raise timely objections when opposing counsel oversteps
- Maintain composure under pressure

YOUR STRATEGY:
{strategy}

CASE CONTEXT:
{self._format_case_summary()}

Always respond in character as an experienced Indian lawyer."""

    def _get_strategy(self) -> str:
        """Get litigation strategy based on representing party."""
        if self.representing == "petitioner":
            return """
- Establish negligence of the respondent driver
- Prove the injuries and suffering of your client
- Maximize the compensation claim with supporting evidence
- Highlight any admissions by respondents
- Emphasize medical evidence and disability
- Argue for higher multiplier based on age and income
"""
        else:
            return """
- Challenge the negligence allegations
- Question the extent of claimed injuries
- Point out inconsistencies in petitioner's evidence
- Argue contributory negligence if applicable
- Challenge inflated income claims
- Minimize compensation where possible
- Raise insurance policy defenses if applicable
"""

    def respond(self, message: str, phase: CourtPhase) -> AgentMessage:
        """Generate lawyer's response."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"[{phase.value}]\n\n{message}\n\nProvide your response as counsel:")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=phase
        )

    def make_opening_statement(self) -> AgentMessage:
        """Make opening statement."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", "Make your opening statement to the court, outlining your client's case and what you intend to prove.")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=CourtPhase.OPENING
        )

    def examine_witness(self, witness: OralWitness, is_cross: bool = False) -> List[str]:
        """Generate questions for witness examination."""
        exam_type = "cross-examination" if is_cross else "examination-in-chief"

        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"""Prepare questions for {exam_type} of {witness.name} ({witness.witness_number}).

WITNESS DETAILS:
- Affidavit: {witness.affidavit_reference}
- Chief Summary: {witness.examination_in_chief_summary}
- Known Contradictions: {witness.contradictions}

Generate 5-7 strategic questions for {exam_type}. Format as a numbered list.""")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return response.content.split('\n')

    def raise_objection(self, grounds: str) -> AgentMessage:
        """Raise an objection."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"""Raise an objection on the following grounds:

{grounds}

Format your objection formally for the court record.""")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        objection = AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=CourtPhase.EXAMINATION,
            metadata={"type": "objection", "grounds": grounds}
        )

        self.objections_raised.append(response.content)
        return objection

    def make_final_argument(self) -> AgentMessage:
        """Make final arguments."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", """Make your final arguments summarizing:
1. Key evidence in your favor
2. Weaknesses in opposing party's case
3. Applicable legal principles and precedents
4. Relief sought (for petitioner) or defense (for respondent)""")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=CourtPhase.FINAL_ARGUMENTS
        )


class WitnessAgent(BaseCourtAgent):
    """
    Witness AI Agent
    - Responds to examination questions
    - Maintains consistency with affidavit
    - Can be evasive or forthcoming based on personality
    """

    def __init__(
        self,
        witness_data: OralWitness,
        personality: str = "cooperative",  # cooperative, nervous, hostile, evasive
        **kwargs
    ):
        super().__init__(
            name=witness_data.name,
            role=AgentRole.WITNESS,
            **kwargs
        )
        self.witness_data = witness_data
        self.personality = personality
        self.testimony_given: List[str] = []

    def get_system_prompt(self) -> str:
        personality_traits = {
            "cooperative": "Answer questions clearly and helpfully. Be forthcoming with information.",
            "nervous": "Show signs of nervousness. Sometimes hesitate or ask for questions to be repeated.",
            "hostile": "Be reluctant to answer. Give short, defensive responses. Show mild irritation.",
            "evasive": "Try to avoid direct answers. Be vague when possible. Claim poor memory for inconvenient facts."
        }

        return f"""You are {self.witness_data.name}, appearing as witness {self.witness_data.witness_number} in this case.

YOUR BACKGROUND:
- Affidavit Reference: {self.witness_data.affidavit_reference}
- Your testimony in chief: {self.witness_data.examination_in_chief_summary}
- Known admissions you've made: {self.witness_data.admissions}

PERSONALITY: {personality_traits.get(self.personality, personality_traits['cooperative'])}

IMPORTANT RULES:
1. Stay consistent with your affidavit and previous testimony
2. You can say "I don't remember" for details not in your knowledge
3. Respond naturally as a witness would in an Indian court
4. Address the judge as "My Lord" or "Your Honour"
5. If asked about contradictions: {self.witness_data.contradictions}

CASE CONTEXT:
{self._format_case_summary()}"""

    def respond(self, message: str, phase: CourtPhase) -> AgentMessage:
        """Respond to examination question."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"[{phase.value}]\n\nCounsel asks: {message}\n\nProvide your testimony:")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        testimony = AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=phase
        )

        self.testimony_given.append(response.content)
        return testimony


class CourtClerkAgent(BaseCourtAgent):
    """
    Court Clerk AI Agent
    - Announces proceedings
    - Calls witnesses
    - Records orders
    """

    def __init__(self, **kwargs):
        super().__init__(
            name="Court Clerk",
            role=AgentRole.COURT_CLERK,
            temperature=0.3,
            **kwargs
        )

    def get_system_prompt(self) -> str:
        return """You are the Court Clerk, responsible for:
1. Announcing case proceedings
2. Calling witnesses to the stand
3. Administering oaths
4. Recording court orders

Be formal and procedural. Use standard court announcements."""

    def respond(self, message: str, phase: CourtPhase) -> AgentMessage:
        """Generate clerk announcement."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.get_system_prompt()),
            ("human", f"[{phase.value}]\n\n{message}")
        ])

        chain = prompt | self.llm
        response = chain.invoke({})

        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=response.content,
            phase=phase
        )

    def announce_case(self, case: CourtCase) -> AgentMessage:
        """Announce the case."""
        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=f"""All rise! This Hon'ble Court is now in session.

Case Number: {case.case_metadata.main_case_number}
{case.case_metadata.case_title}

Presiding: {case.case_metadata.judge_name}, {case.case_metadata.court_name}

Counsel for Petitioner, please announce your appearance.
Counsel for Respondent(s), please announce your appearance.""",
            phase=CourtPhase.OPENING
        )

    def call_witness(self, witness: OralWitness) -> AgentMessage:
        """Call a witness to the stand."""
        return AgentMessage(
            role=self.role,
            agent_name=self.name,
            content=f"""The Court calls {witness.name} ({witness.witness_number}) to the witness stand.

[Witness approaches the stand]

Please state your name for the record and take the oath:
"I solemnly affirm that the evidence I shall give shall be the truth, the whole truth, and nothing but the truth."

[Witness affirms]

Counsel may proceed with the examination.""",
            phase=CourtPhase.EXAMINATION
        )


# Factory function to create agents from case data
def create_agents_from_case(
    case: CourtCase,
    llm_provider: str = "openai",
    model_name: Optional[str] = None
) -> Dict[str, BaseCourtAgent]:
    """
    Create all courtroom agents from case data.

    Returns dict with keys: judge, petitioner_counsel, respondent_counsel, witnesses, clerk
    """
    agents = {}

    # Create Judge
    judge = JudgeAgent(
        name=case.case_metadata.judge_name or "Hon'ble Judge",
        designation=case.case_metadata.judge_designation or "Presiding Officer",
        llm_provider=llm_provider,
        model_name=model_name
    )
    judge.set_case_context(case)
    agents['judge'] = judge

    # Create Petitioner Counsel
    pet_counsel_name = (
        case.legal_representation.counsel_for_petitioner[0]
        if case.legal_representation.counsel_for_petitioner
        else "Counsel for Petitioner"
    )
    pet_counsel = LawyerAgent(
        name=pet_counsel_name,
        representing="petitioner",
        llm_provider=llm_provider,
        model_name=model_name
    )
    pet_counsel.set_case_context(case)
    agents['petitioner_counsel'] = pet_counsel

    # Create Respondent Counsel
    resp_counsel_name = (
        case.legal_representation.counsel_for_respondents[0]
        if case.legal_representation.counsel_for_respondents
        else "Counsel for Respondent"
    )
    resp_counsel = LawyerAgent(
        name=resp_counsel_name,
        representing="respondent",
        llm_provider=llm_provider,
        model_name=model_name
    )
    resp_counsel.set_case_context(case)
    agents['respondent_counsel'] = resp_counsel

    # Create Witness Agents
    witnesses = []
    for witness_data in case.evidence_details.oral_witnesses:
        witness = WitnessAgent(
            witness_data=witness_data,
            llm_provider=llm_provider,
            model_name=model_name
        )
        witness.set_case_context(case)
        witnesses.append(witness)
    agents['witnesses'] = witnesses

    # Create Court Clerk
    clerk = CourtClerkAgent(llm_provider=llm_provider, model_name=model_name)
    clerk.set_case_context(case)
    agents['clerk'] = clerk

    return agents
