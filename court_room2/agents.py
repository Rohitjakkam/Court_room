import os
from openai import OpenAI
from dotenv import load_dotenv
from schemas import RoleType, TrialStage, WitnessExamPhase, STAGE_DISPLAY
from case_data import get_case_info, get_characters, get_evidence_list, get_pw_witnesses, get_dw_witnesses
from prompts import (
    JUDGE_SYSTEM_PROMPT,
    PROSECUTOR_SYSTEM_PROMPT,
    DEFENCE_SYSTEM_PROMPT,
    ACCUSED_SYSTEM_PROMPT,
    WITNESS_PW_SYSTEM_PROMPT,
    WITNESS_DW_SYSTEM_PROMPT,
    CLERK_SYSTEM_PROMPT,
)

load_dotenv()


class CourtAgent:
    def __init__(self, character, system_prompt: str):
        api_key = os.getenv("openai") or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=api_key)
        self.character = character
        self.system_prompt = system_prompt
        self.conversation_history = []

    def generate_response(self, context: str, user_input: str = None) -> str:
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.conversation_history[-20:]:
            messages.append(msg)

        prompt = context
        if user_input:
            prompt += f"\n\nThe player said: \"{user_input}\""
        prompt += f"\n\nRespond in character as {self.character.name} ({self.character.designation})."

        messages.append({"role": "user", "content": prompt})

        try:
            response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                max_tokens=250,
                temperature=0.7,
            )
            reply = response.choices[0].message.content.strip()
            self.conversation_history.append({"role": "user", "content": prompt})
            self.conversation_history.append({"role": "assistant", "content": reply})
            return reply
        except Exception as e:
            return f"[AI Error: {str(e)}]"


class AgentManager:
    def __init__(self, player_role: RoleType):
        self.player_role = player_role
        self.case_info = get_case_info()
        self.characters = get_characters()
        self.evidence = get_evidence_list()
        self.pw_witnesses = get_pw_witnesses()
        self.dw_witnesses = get_dw_witnesses()
        self.agents: dict[str, CourtAgent] = {}
        self._create_agents()

    def _get_char(self, role: RoleType, designation: str = None):
        for c in self.characters:
            if c.role == role:
                if designation is None or c.designation == designation:
                    return c
        return None

    def _format_witness_list(self) -> str:
        lines = []
        for w in self.pw_witnesses:
            lines.append(f"- {w.designation}: {w.name} — {w.description}")
        return "\n".join(lines)

    def _format_evidence_list(self) -> str:
        lines = []
        for e in self.evidence:
            lines.append(f"- {e.id}: {e.name} — {e.description}")
        return "\n".join(lines)

    def _create_agents(self):
        case = self.case_info
        stage_str = "Trial beginning"

        # Judge
        judge_char = self._get_char(RoleType.JUDGE)
        if judge_char:
            prompt = JUDGE_SYSTEM_PROMPT.format(
                name=judge_char.name,
                designation=judge_char.designation,
                court=case.court,
                case_title=case.title,
                case_number=case.case_number,
                sections=", ".join(case.sections),
                personality=judge_char.personality,
                facts_known=judge_char.facts_known,
                stage=stage_str,
            )
            self.agents["judge"] = CourtAgent(judge_char, prompt)

        # Prosecutor
        pp_char = self._get_char(RoleType.PROSECUTOR)
        if pp_char:
            prompt = PROSECUTOR_SYSTEM_PROMPT.format(
                name=pp_char.name,
                designation=pp_char.designation,
                court=case.court,
                case_title=case.title,
                case_number=case.case_number,
                sections=", ".join(case.sections),
                personality=pp_char.personality,
                prosecution_story=case.prosecution_story,
                facts_known=pp_char.facts_known,
                witness_list=self._format_witness_list(),
                evidence_list=self._format_evidence_list(),
                stage=stage_str,
            )
            self.agents["prosecutor"] = CourtAgent(pp_char, prompt)

        # Defence
        def_char = self._get_char(RoleType.DEFENCE)
        accused_char = self._get_char(RoleType.ACCUSED)
        if def_char:
            prompt = DEFENCE_SYSTEM_PROMPT.format(
                name=def_char.name,
                designation=def_char.designation,
                court=case.court,
                case_title=case.title,
                case_number=case.case_number,
                sections=", ".join(case.sections),
                personality=def_char.personality,
                defence_story=case.defence_story,
                facts_known=def_char.facts_known,
                accused_name=accused_char.name if accused_char else "the accused",
                stage=stage_str,
            )
            self.agents["defence"] = CourtAgent(def_char, prompt)

        # Accused
        if accused_char:
            prompt = ACCUSED_SYSTEM_PROMPT.format(
                name=accused_char.name,
                case_title=case.title,
                sections=", ".join(case.sections),
                personality=accused_char.personality,
                facts_known=accused_char.facts_known,
                stage=stage_str,
            )
            self.agents["accused"] = CourtAgent(accused_char, prompt)

        # Prosecution Witnesses
        for i, pw in enumerate(self.pw_witnesses):
            prompt = WITNESS_PW_SYSTEM_PROMPT.format(
                name=pw.name,
                designation=pw.designation,
                case_title=case.title,
                personality=pw.personality,
                facts_known=pw.facts_known,
                description=pw.description,
                stage=stage_str,
                exam_phase="Not yet called",
            )
            self.agents[f"pw_{i}"] = CourtAgent(pw, prompt)

        # Defence Witnesses
        for i, dw in enumerate(self.dw_witnesses):
            prompt = WITNESS_DW_SYSTEM_PROMPT.format(
                name=dw.name,
                designation=dw.designation,
                case_title=case.title,
                personality=dw.personality,
                facts_known=dw.facts_known,
                description=dw.description,
                stage=stage_str,
                exam_phase="Not yet called",
            )
            self.agents[f"dw_{i}"] = CourtAgent(dw, prompt)

        # Clerk
        clerk_char = self._get_char(RoleType.CLERK)
        if clerk_char:
            prompt = CLERK_SYSTEM_PROMPT.format(
                court=case.court,
                case_title=case.title,
                case_number=case.case_number,
                stage=stage_str,
            )
            self.agents["clerk"] = CourtAgent(clerk_char, prompt)

    def get_response(self, agent_key: str, context: str, user_input: str = None) -> str:
        agent = self.agents.get(agent_key)
        if not agent:
            return "[Agent not found]"
        return agent.generate_response(context, user_input)

    def get_agent_key_for_role(self, role: RoleType, index: int = 0) -> str:
        mapping = {
            RoleType.JUDGE: "judge",
            RoleType.PROSECUTOR: "prosecutor",
            RoleType.DEFENCE: "defence",
            RoleType.ACCUSED: "accused",
            RoleType.CLERK: "clerk",
        }
        if role == RoleType.WITNESS_PW:
            return f"pw_{index}"
        if role == RoleType.WITNESS_DW:
            return f"dw_{index}"
        return mapping.get(role, "judge")

    def is_player_role(self, role: RoleType) -> bool:
        return role == self.player_role
