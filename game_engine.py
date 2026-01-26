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


class ObjectionType(str, Enum):
    LEADING = "Leading question"
    HEARSAY = "Hearsay"
    RELEVANCE = "Irrelevant"
    SPECULATION = "Calls for speculation"
    ARGUMENTATIVE = "Argumentative"
    COMPOUND = "Compound question"
    BADGERING = "Badgering the witness"
    ASSUMES_FACTS = "Assumes facts not in evidence"


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


@dataclass
class GameAction:
    """Represents a player action in the game."""
    action_type: ActionType
    content: str
    target: Optional[str] = None  # e.g., witness name for questions
    evidence_id: Optional[str] = None
    objection_type: Optional[ObjectionType] = None


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
class GameState:
    """Current state of the game."""
    phase: GamePhase = GamePhase.SETUP
    turn_number: int = 0
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
    score: GameScore = field(default_factory=GameScore)
    game_log: List[Dict[str, Any]] = field(default_factory=list)


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

        # Collect all opening messages
        opening_messages = []

        # 1. Clerk announces the case
        clerk_msg = self._clerk_announce_case()
        opening_messages.append(clerk_msg)
        self.state.messages.append(clerk_msg)

        # 2. Judge opens proceedings
        judge: JudgeAgent = self.agents['judge']
        judge_opening = judge.respond(
            "The court is now in session. This court will hear the matter. "
            "Counsel for both parties may note their appearances. "
            "Counsel for the petitioner may proceed with the opening statement.",
            CourtPhase.OPENING
        )
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

    def _clerk_announce_case(self) -> AgentMessage:
        """Have the clerk announce the case."""
        clerk: CourtClerkAgent = self.agents['clerk']
        return clerk.announce_case(self.case)

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
            GamePhase.OPENING_STATEMENT: [ActionType.MAKE_ARGUMENT],
            GamePhase.PETITIONER_WITNESS_EXAM: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS
            ],
            GamePhase.CROSS_EXAMINATION: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS
            ],
            GamePhase.RESPONDENT_WITNESS_EXAM: [
                ActionType.ASK_QUESTION,
                ActionType.PRESENT_EVIDENCE,
                ActionType.RAISE_OBJECTION,
                ActionType.NO_QUESTIONS
            ],
            GamePhase.FINAL_ARGUMENTS: [
                ActionType.MAKE_ARGUMENT,
                ActionType.CITE_CASE_LAW
            ],
            GamePhase.REBUTTAL: [ActionType.MAKE_ARGUMENT]
        }
        return phase_actions.get(self.state.phase, [])

    def process_player_action(self, action: GameAction) -> Dict[str, Any]:
        """Process a player's action and return results."""
        self.state.turn_number += 1
        results = {
            "messages": [],
            "events": [],
            "score_change": {},
            "phase_changed": False,
            "game_over": False
        }

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

        # Check for dynamic events
        event = self.event_generator.maybe_trigger_event(self.state.phase, self.state)
        if event:
            results["events"].append(event)
            self.state.events_occurred.append(event)
            self._emit("event_triggered", event)

        # Check for phase transition
        if self._should_advance_phase():
            self._advance_phase()
            results["phase_changed"] = True
            results["new_phase"] = self.state.phase
            results["instructions"] = self._get_phase_instructions()

        # Update score
        self._update_score(action, results)
        results["score"] = self.state.score

        # AI opponent's turn
        if not self.state.is_player_turn and self.state.phase != GamePhase.GAME_OVER:
            opponent_response = self._get_opponent_response()
            results["messages"].append(opponent_response)
            self.state.is_player_turn = True

        # Log the turn
        self.state.game_log.append({
            "turn": self.state.turn_number,
            "phase": self.state.phase.value,
            "action": action.action_type.value,
            "content": action.content
        })

        return results

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
                witness_response = witness.respond(action.content, CourtPhase.EXAMINATION)
                messages.append(witness_response)
                self.state.messages.append(witness_response)

                # Possible opponent objection
                if random.random() < 0.2:  # 20% chance of objection
                    opponent: LawyerAgent = self.agents['opponent']
                    objection = opponent.raise_objection("The question is leading/improper")
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

    def proceed_to_next_phase(self) -> Dict[str, Any]:
        """
        Advance to the next phase and run any necessary AI actions.
        Returns the messages and new state.
        """
        self._advance_phase()

        result = {
            "messages": [],
            "phase": self.state.phase,
            "is_player_turn": self.state.is_player_turn,
            "instructions": self._get_phase_instructions()
        }

        # Determine who goes first in the new phase
        judge: JudgeAgent = self.agents['judge']

        if self.state.phase == GamePhase.PETITIONER_WITNESS_EXAM:
            # Announce phase
            announce = judge.respond(
                "The court will now proceed with the examination of petitioner's witnesses. "
                "Counsel for petitioner, please call your first witness.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(announce)
            self.state.messages.append(announce)

            if self.state.player_side == PlayerSide.RESPONDENT:
                # AI petitioner examines first, then player cross-examines
                result["messages"].extend(self.run_ai_turn())
                self.state.phase = GamePhase.CROSS_EXAMINATION
                result["phase"] = self.state.phase

        elif self.state.phase == GamePhase.RESPONDENT_WITNESS_EXAM:
            announce = judge.respond(
                "The court will now proceed with the examination of respondent's witnesses. "
                "Counsel for respondent, please call your witness.",
                CourtPhase.EXAMINATION
            )
            result["messages"].append(announce)
            self.state.messages.append(announce)

            if self.state.player_side == PlayerSide.PETITIONER:
                # AI respondent examines first, then player cross-examines
                result["messages"].extend(self.run_ai_turn())
                self.state.phase = GamePhase.CROSS_EXAMINATION
                result["phase"] = self.state.phase

        elif self.state.phase == GamePhase.FINAL_ARGUMENTS:
            announce = judge.respond(
                "Evidence is closed. The court will now hear final arguments. "
                "Counsel for petitioner may proceed.",
                CourtPhase.FINAL_ARGUMENTS
            )
            result["messages"].append(announce)
            self.state.messages.append(announce)

            if self.state.player_side == PlayerSide.RESPONDENT:
                # AI petitioner argues first
                result["messages"].extend(self.run_ai_turn())

        elif self.state.phase == GamePhase.JUDGMENT:
            judgment = self._deliver_judgment()
            result["messages"].append(judgment)
            result["phase"] = GamePhase.GAME_OVER

        result["is_player_turn"] = self.state.is_player_turn
        result["instructions"] = self._get_phase_instructions()

        return result

    def _should_advance_phase(self) -> bool:
        """Check if should move to next phase - now controlled by player."""
        # Let player control phase advancement via proceed_to_next_phase()
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
