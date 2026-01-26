"""
Courtroom Replay Engine
Orchestrates the courtroom simulation from JSON case data
"""

import json
from typing import Optional, List, Dict, Any, Generator, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from schemas import CourtCase
from agents import (
    BaseCourtAgent, JudgeAgent, LawyerAgent, WitnessAgent, CourtClerkAgent,
    AgentMessage, AgentRole, CourtPhase, create_agents_from_case
)


class SimulationMode(str, Enum):
    FULL_REPLAY = "full_replay"  # Complete simulation
    STEP_BY_STEP = "step_by_step"  # Interactive step through
    EXAMINATION_ONLY = "examination_only"  # Only witness examinations
    ARGUMENTS_ONLY = "arguments_only"  # Only legal arguments
    JUDGMENT_ONLY = "judgment_only"  # Skip to judgment


@dataclass
class SimulationConfig:
    """Configuration for courtroom simulation."""
    mode: SimulationMode = SimulationMode.FULL_REPLAY
    llm_provider: str = "openai"
    model_name: Optional[str] = None
    include_objections: bool = True
    include_clerk_announcements: bool = True
    max_questions_per_witness: int = 5
    enable_cross_examination: bool = True
    verbose: bool = True


@dataclass
class SimulationState:
    """Current state of the simulation."""
    current_phase: CourtPhase = CourtPhase.OPENING
    current_witness_index: int = 0
    current_issue_index: int = 0
    messages: List[AgentMessage] = field(default_factory=list)
    is_complete: bool = False
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class CourtroomReplayEngine:
    """
    Main engine for replaying court proceedings from case data.
    Orchestrates all agents and manages the simulation flow.
    """

    def __init__(self, config: Optional[SimulationConfig] = None):
        """Initialize the replay engine."""
        self.config = config or SimulationConfig()
        self.case: Optional[CourtCase] = None
        self.agents: Dict[str, Any] = {}
        self.state = SimulationState()
        self.event_handlers: Dict[str, List[Callable]] = {
            "message": [],
            "phase_change": [],
            "simulation_complete": [],
            "error": []
        }

    def load_case_from_json(self, json_path: str) -> CourtCase:
        """Load case data from JSON file."""
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        self.case = CourtCase(**data)
        self._initialize_agents()
        return self.case

    def load_case_from_dict(self, data: Dict[str, Any]) -> CourtCase:
        """Load case data from dictionary."""
        self.case = CourtCase(**data)
        self._initialize_agents()
        return self.case

    def load_case(self, case: CourtCase) -> None:
        """Load an existing CourtCase object."""
        self.case = case
        self._initialize_agents()

    def _initialize_agents(self) -> None:
        """Initialize all agents from case data."""
        if not self.case:
            raise ValueError("No case loaded")

        self.agents = create_agents_from_case(
            self.case,
            llm_provider=self.config.llm_provider,
            model_name=self.config.model_name
        )

    def on(self, event: str, handler: Callable) -> None:
        """Register an event handler."""
        if event in self.event_handlers:
            self.event_handlers[event].append(handler)

    def _emit(self, event: str, data: Any) -> None:
        """Emit an event to all handlers."""
        for handler in self.event_handlers.get(event, []):
            handler(data)

    def _log_message(self, message: AgentMessage) -> None:
        """Log a message and emit event."""
        self.state.messages.append(message)
        self._emit("message", message)

        if self.config.verbose:
            print(f"\n[{message.phase.value}] {message.agent_name}:")
            print(message.content)
            print("-" * 50)

    def _change_phase(self, new_phase: CourtPhase) -> None:
        """Change simulation phase."""
        old_phase = self.state.current_phase
        self.state.current_phase = new_phase
        self._emit("phase_change", {"old": old_phase, "new": new_phase})

        if self.config.verbose:
            print(f"\n{'='*60}")
            print(f"PHASE: {new_phase.value}")
            print(f"{'='*60}\n")

    def run_full_simulation(self) -> Generator[AgentMessage, None, None]:
        """
        Run the complete courtroom simulation.
        Yields messages as they are generated.
        """
        if not self.case:
            raise ValueError("No case loaded")

        self.state = SimulationState(start_time=datetime.now())

        # Phase 1: Opening
        yield from self._run_opening_phase()

        # Phase 2: Petitioner Arguments
        yield from self._run_arguments_phase(is_petitioner=True)

        # Phase 3: Evidence/Examination
        yield from self._run_examination_phase()

        # Phase 4: Respondent Arguments
        yield from self._run_arguments_phase(is_petitioner=False)

        # Phase 5: Final Arguments
        yield from self._run_final_arguments()

        # Phase 6: Judgment
        yield from self._run_judgment_phase()

        self.state.is_complete = True
        self.state.end_time = datetime.now()
        self._emit("simulation_complete", self.state)

    def _run_opening_phase(self) -> Generator[AgentMessage, None, None]:
        """Run the opening phase."""
        self._change_phase(CourtPhase.OPENING)

        # Clerk announces case
        if self.config.include_clerk_announcements:
            clerk: CourtClerkAgent = self.agents['clerk']
            announcement = clerk.announce_case(self.case)
            self._log_message(announcement)
            yield announcement

        # Judge opens proceedings
        judge: JudgeAgent = self.agents['judge']
        opening = judge.respond(
            "The court is assembled. Let the proceedings begin. "
            "Counsel for petitioner, please make your opening statement.",
            CourtPhase.OPENING
        )
        self._log_message(opening)
        yield opening

        # Petitioner counsel opening
        pet_counsel: LawyerAgent = self.agents['petitioner_counsel']
        pet_opening = pet_counsel.make_opening_statement()
        self._log_message(pet_opening)
        yield pet_opening

        # Respondent counsel opening
        resp_counsel: LawyerAgent = self.agents['respondent_counsel']
        resp_opening = resp_counsel.make_opening_statement()
        self._log_message(resp_opening)
        yield resp_opening

    def _run_arguments_phase(self, is_petitioner: bool) -> Generator[AgentMessage, None, None]:
        """Run arguments phase for a party."""
        phase = CourtPhase.PETITIONER_ARGUMENTS if is_petitioner else CourtPhase.RESPONDENT_ARGUMENTS
        self._change_phase(phase)

        counsel_key = 'petitioner_counsel' if is_petitioner else 'respondent_counsel'
        counsel: LawyerAgent = self.agents[counsel_key]
        judge: JudgeAgent = self.agents['judge']

        # Counsel presents arguments
        party = "petitioner" if is_petitioner else "respondent"
        argument_prompt = f"Present your main arguments on behalf of the {party}, addressing the issues framed."

        argument = counsel.respond(argument_prompt, phase)
        self._log_message(argument)
        yield argument

        # Judge may ask questions
        judge_question = judge.respond(
            f"Having heard the arguments of {counsel.name}, the Court has some queries.",
            phase
        )
        self._log_message(judge_question)
        yield judge_question

        # Counsel responds to judge's queries
        response = counsel.respond(judge_question.content, phase)
        self._log_message(response)
        yield response

    def _run_examination_phase(self) -> Generator[AgentMessage, None, None]:
        """Run witness examination phase."""
        self._change_phase(CourtPhase.EXAMINATION)

        witnesses: List[WitnessAgent] = self.agents['witnesses']
        pet_counsel: LawyerAgent = self.agents['petitioner_counsel']
        resp_counsel: LawyerAgent = self.agents['respondent_counsel']
        clerk: CourtClerkAgent = self.agents['clerk']
        judge: JudgeAgent = self.agents['judge']

        for idx, witness in enumerate(witnesses):
            self.state.current_witness_index = idx

            # Clerk calls witness
            if self.config.include_clerk_announcements:
                call = clerk.call_witness(witness.witness_data)
                self._log_message(call)
                yield call

            # Determine examining counsel based on witness type
            if witness.witness_data.witness_type.value == "PW":
                examining_counsel = pet_counsel
                cross_counsel = resp_counsel
            else:
                examining_counsel = resp_counsel
                cross_counsel = pet_counsel

            # Examination in Chief
            self._change_phase(CourtPhase.EXAMINATION)
            questions = examining_counsel.examine_witness(witness.witness_data, is_cross=False)

            for q_idx, question in enumerate(questions[:self.config.max_questions_per_witness]):
                # Counsel asks question
                q_message = AgentMessage(
                    role=examining_counsel.role,
                    agent_name=examining_counsel.name,
                    content=question,
                    phase=CourtPhase.EXAMINATION
                )
                self._log_message(q_message)
                yield q_message

                # Witness answers
                answer = witness.respond(question, CourtPhase.EXAMINATION)
                self._log_message(answer)
                yield answer

            # Cross Examination
            if self.config.enable_cross_examination:
                self._change_phase(CourtPhase.CROSS_EXAMINATION)
                cross_questions = cross_counsel.examine_witness(witness.witness_data, is_cross=True)

                for q_idx, question in enumerate(cross_questions[:self.config.max_questions_per_witness]):
                    # Cross-examining counsel asks question
                    q_message = AgentMessage(
                        role=cross_counsel.role,
                        agent_name=cross_counsel.name,
                        content=question,
                        phase=CourtPhase.CROSS_EXAMINATION
                    )
                    self._log_message(q_message)
                    yield q_message

                    # Witness answers
                    answer = witness.respond(question, CourtPhase.CROSS_EXAMINATION)
                    self._log_message(answer)
                    yield answer

                    # Possible objection
                    if self.config.include_objections and q_idx == 2:
                        objection = examining_counsel.raise_objection(
                            "Leading question / argumentative"
                        )
                        self._log_message(objection)
                        yield objection

                        ruling = judge.rule_on_objection(
                            objection.content,
                            f"During cross-examination of {witness.name}"
                        )
                        self._log_message(ruling)
                        yield ruling

    def _run_final_arguments(self) -> Generator[AgentMessage, None, None]:
        """Run final arguments phase."""
        self._change_phase(CourtPhase.FINAL_ARGUMENTS)

        pet_counsel: LawyerAgent = self.agents['petitioner_counsel']
        resp_counsel: LawyerAgent = self.agents['respondent_counsel']
        judge: JudgeAgent = self.agents['judge']

        # Judge invites final arguments
        invitation = judge.respond(
            "Evidence has been closed. The Court now invites final arguments. "
            "Counsel for petitioner may proceed.",
            CourtPhase.FINAL_ARGUMENTS
        )
        self._log_message(invitation)
        yield invitation

        # Petitioner final argument
        pet_final = pet_counsel.make_final_argument()
        self._log_message(pet_final)
        yield pet_final

        # Respondent final argument
        resp_final = resp_counsel.make_final_argument()
        self._log_message(resp_final)
        yield resp_final

        # Judge reserves judgment
        reserve = judge.respond(
            "The Court has heard the final arguments of both sides. "
            "Judgment is reserved.",
            CourtPhase.FINAL_ARGUMENTS
        )
        self._log_message(reserve)
        yield reserve

    def _run_judgment_phase(self) -> Generator[AgentMessage, None, None]:
        """Run judgment phase."""
        self._change_phase(CourtPhase.JUDGMENT)

        judge: JudgeAgent = self.agents['judge']
        clerk: CourtClerkAgent = self.agents['clerk']

        # Clerk announces judgment day
        if self.config.include_clerk_announcements:
            announcement = AgentMessage(
                role=clerk.role,
                agent_name=clerk.name,
                content="The judgment in the matter is being pronounced. All parties to remain standing.",
                phase=CourtPhase.JUDGMENT
            )
            self._log_message(announcement)
            yield announcement

        # Judge delivers judgment
        judgment = judge.deliver_judgment()
        self._log_message(judgment)
        yield judgment

    def get_transcript(self) -> str:
        """Get the full transcript of the simulation."""
        transcript = []
        current_phase = None

        for msg in self.state.messages:
            if msg.phase != current_phase:
                current_phase = msg.phase
                transcript.append(f"\n{'='*60}")
                transcript.append(f"PHASE: {current_phase.value}")
                transcript.append(f"{'='*60}\n")

            transcript.append(f"[{msg.agent_name}]")
            transcript.append(msg.content)
            transcript.append("-" * 40)

        return "\n".join(transcript)

    def export_to_json(self, filepath: str) -> None:
        """Export simulation results to JSON."""
        data = {
            "case_title": self.case.case_metadata.case_title if self.case else "Unknown",
            "simulation_config": {
                "mode": self.config.mode.value,
                "llm_provider": self.config.llm_provider
            },
            "state": {
                "is_complete": self.state.is_complete,
                "start_time": self.state.start_time.isoformat() if self.state.start_time else None,
                "end_time": self.state.end_time.isoformat() if self.state.end_time else None
            },
            "messages": [
                {
                    "role": msg.role.value,
                    "agent_name": msg.agent_name,
                    "content": msg.content,
                    "phase": msg.phase.value,
                    "metadata": msg.metadata
                }
                for msg in self.state.messages
            ]
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)


class InteractiveCourtroom:
    """
    Interactive mode for courtroom simulation.
    Allows user to step through proceedings or intervene.
    """

    def __init__(self, engine: CourtroomReplayEngine):
        self.engine = engine
        self.generator: Optional[Generator] = None

    def start(self) -> AgentMessage:
        """Start the interactive simulation."""
        self.generator = self.engine.run_full_simulation()
        return next(self.generator)

    def next_step(self) -> Optional[AgentMessage]:
        """Get the next step in the simulation."""
        if not self.generator:
            raise ValueError("Simulation not started")

        try:
            return next(self.generator)
        except StopIteration:
            return None

    def inject_message(self, role: AgentRole, content: str) -> AgentMessage:
        """Inject a custom message into the simulation."""
        message = AgentMessage(
            role=role,
            agent_name="User",
            content=content,
            phase=self.engine.state.current_phase
        )
        self.engine._log_message(message)
        return message

    def ask_judge(self, question: str) -> AgentMessage:
        """Ask the judge a question."""
        judge: JudgeAgent = self.engine.agents['judge']
        response = judge.respond(question, self.engine.state.current_phase)
        self.engine._log_message(response)
        return response

    def get_current_phase(self) -> CourtPhase:
        """Get current simulation phase."""
        return self.engine.state.current_phase


# Convenience function for quick simulation
def simulate_case(
    case_data: Dict[str, Any],
    config: Optional[SimulationConfig] = None
) -> List[AgentMessage]:
    """
    Quick function to simulate a court case from JSON data.

    Args:
        case_data: Dictionary containing case data
        config: Optional simulation configuration

    Returns:
        List of all messages from the simulation
    """
    engine = CourtroomReplayEngine(config=config)
    engine.load_case_from_dict(case_data)

    messages = list(engine.run_full_simulation())
    return messages
