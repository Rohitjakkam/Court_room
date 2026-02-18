from schemas import (
    TrialStage, RoleType, WitnessExamPhase, Dialogue,
    GameState, STAGE_ORDER, STAGE_DISPLAY, EvidenceStatus,
)
from case_data import get_case_info, get_pw_witnesses, get_dw_witnesses, get_evidence_list, get_characters
from agents import AgentManager


class TrialEngine:
    def __init__(self, player_role: RoleType):
        self.state = GameState(player_role=player_role)
        self.case_info = get_case_info()
        self.pw_witnesses = get_pw_witnesses()
        self.dw_witnesses = get_dw_witnesses()
        self.state.evidence_list = get_evidence_list()
        self.characters = get_characters()
        self.agents = AgentManager(player_role)

    def add_dialogue(self, speaker: str, role: RoleType, text: str, is_player: bool = False):
        d = Dialogue(
            speaker=speaker,
            role=role,
            text=text,
            stage=self.state.current_stage,
            is_player=is_player,
        )
        self.state.dialogues.append(d)
        return d

    def get_character_by_role(self, role: RoleType):
        for c in self.characters:
            if c.role == role:
                return c
        return None

    def is_player(self, role: RoleType) -> bool:
        return role == self.state.player_role

    def advance_stage(self):
        idx = STAGE_ORDER.index(self.state.current_stage)
        if idx < len(STAGE_ORDER) - 1:
            self.state.current_stage = STAGE_ORDER[idx + 1]
            self.state.stage_initialized = False
            self.state.waiting_for_player = False
            self.state.sub_step = 0

    def get_stage_label(self) -> str:
        return STAGE_DISPLAY.get(self.state.current_stage, "Unknown Stage")

    def get_recent_context(self, n: int = 10) -> str:
        recent = self.state.dialogues[-n:]
        lines = []
        for d in recent:
            lines.append(f"{d.speaker} ({d.role.value}): {d.text}")
        return "\n".join(lines)

    # ─── STAGE PROCESSORS ───────────────────────────────────────

    def run_pre_trial(self) -> bool:
        """Stage 1: Pre-Trial — Clerk announces case, FIR summary shown."""
        if self.state.stage_initialized:
            return True  # done

        clerk = self.get_character_by_role(RoleType.CLERK)
        self.add_dialogue(
            clerk.name, RoleType.CLERK,
            f"May it please the Court. {self.case_info.case_number}. "
            f"{self.case_info.title} is called for hearing."
        )

        judge = self.get_character_by_role(RoleType.JUDGE)
        self.add_dialogue(judge.name, RoleType.JUDGE, "Appearances?")

        pp = self.get_character_by_role(RoleType.PROSECUTOR)
        self.add_dialogue(pp.name, RoleType.PROSECUTOR, "Learned Public Prosecutor for the State, My Lord.")

        defence = self.get_character_by_role(RoleType.DEFENCE)
        self.add_dialogue(defence.name, RoleType.DEFENCE, "Counsel for the accused, My Lord.")

        self.state.stage_initialized = True
        return True  # auto-advance

    def run_cognizance(self) -> bool:
        """Stage 2: Cognizance & Supply of Documents."""
        if self.state.stage_initialized:
            return True

        judge = self.get_character_by_role(RoleType.JUDGE)
        pp = self.get_character_by_role(RoleType.PROSECUTOR)
        defence = self.get_character_by_role(RoleType.DEFENCE)

        self.add_dialogue(
            judge.name, RoleType.JUDGE,
            "Have copies under Section 207 CrPC been supplied to the accused?"
        )

        if self.is_player(RoleType.PROSECUTOR):
            self.state.waiting_for_player = True
            self.state.stage_initialized = True
            return False

        self.add_dialogue(pp.name, RoleType.PROSECUTOR, "Yes, My Lord. All documents have been supplied.")

        if self.is_player(RoleType.DEFENCE):
            self.state.waiting_for_player = True
            self.state.stage_initialized = True
            return False

        self.add_dialogue(defence.name, RoleType.DEFENCE, "Received, My Lord.")
        self.state.stage_initialized = True
        return True

    def handle_cognizance_input(self, player_input: str):
        """Handle player input during cognizance stage."""
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

        if self.state.player_role == RoleType.PROSECUTOR:
            defence = self.get_character_by_role(RoleType.DEFENCE)
            if self.is_player(RoleType.DEFENCE):
                self.state.sub_step = 1
            else:
                self.add_dialogue(defence.name, RoleType.DEFENCE, "Received, My Lord.")
                self.state.waiting_for_player = False
        else:
            self.state.waiting_for_player = False

    def run_charge_stage(self) -> bool:
        """Stage 3: Charge — PP argues, Defence argues for discharge, Judge frames charge."""
        # sub_step 30 means charge stage fully complete
        if self.state.sub_step >= 30:
            return True

        if self.state.stage_initialized:
            return False  # waiting for player interaction

        judge = self.get_character_by_role(RoleType.JUDGE)
        self.add_dialogue(judge.name, RoleType.JUDGE, "Arguments on charge.")

        # Prosecution argues for charge
        if self.is_player(RoleType.PROSECUTOR):
            self.state.waiting_for_player = True
            self.state.stage_initialized = True
            self.state.sub_step = 0
            return False

        context = f"Stage: Charge hearing. Judge has asked for arguments on charge. Sections: {', '.join(self.case_info.sections)}."
        pp_response = self.agents.get_response("prosecutor", context)
        pp = self.get_character_by_role(RoleType.PROSECUTOR)
        self.add_dialogue(pp.name, RoleType.PROSECUTOR, pp_response)

        # Defence argues for discharge
        if self.is_player(RoleType.DEFENCE):
            self.state.waiting_for_player = True
            self.state.stage_initialized = True
            self.state.sub_step = 1
            return False

        context = f"Stage: Charge hearing. Prosecution has argued. Now defence argues for discharge.\n{self.get_recent_context(5)}"
        def_response = self.agents.get_response("defence", context)
        defence = self.get_character_by_role(RoleType.DEFENCE)
        self.add_dialogue(defence.name, RoleType.DEFENCE, def_response)

        # Judge frames charge
        self._judge_frames_charge()
        self.state.stage_initialized = True
        return self.state.sub_step >= 30

    def _judge_frames_charge(self):
        judge = self.get_character_by_role(RoleType.JUDGE)
        accused = self.get_character_by_role(RoleType.ACCUSED)

        if self.is_player(RoleType.JUDGE):
            self.state.waiting_for_player = True
            self.state.sub_step = 10
            return

        context = (
            f"Both sides have argued on charge. Frame charges under {', '.join(self.case_info.sections)} "
            f"and ask the accused to plead.\n{self.get_recent_context(6)}"
        )
        judge_response = self.agents.get_response("judge", context)
        self.add_dialogue(judge.name, RoleType.JUDGE, judge_response)

        # Accused pleads
        if self.is_player(RoleType.ACCUSED):
            self.state.waiting_for_player = True
            self.state.sub_step = 20
            return

        self.add_dialogue(accused.name, RoleType.ACCUSED, "I plead not guilty and claim trial, My Lord.")
        # Mark charge stage as complete
        self.state.sub_step = 30
        self.state.waiting_for_player = False

    def handle_charge_input(self, player_input: str):
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

        if self.state.sub_step == 0:
            # Player was prosecutor, now defence argues (AI)
            context = f"Charge hearing. Defence turn to argue for discharge.\n{self.get_recent_context(5)}"
            def_response = self.agents.get_response("defence", context)
            defence = self.get_character_by_role(RoleType.DEFENCE)
            self.add_dialogue(defence.name, RoleType.DEFENCE, def_response)
            self._judge_frames_charge()

        elif self.state.sub_step == 1:
            # Player was defence, now judge frames charge + accused pleads (all AI)
            self._judge_frames_charge()

        elif self.state.sub_step == 10:
            # Player was judge framing charges, now accused pleads
            accused = self.get_character_by_role(RoleType.ACCUSED)
            if self.is_player(RoleType.ACCUSED):
                self.state.sub_step = 20
                self.state.waiting_for_player = True
                return
            self.add_dialogue(accused.name, RoleType.ACCUSED, "I plead not guilty and claim trial, My Lord.")
            self.state.sub_step = 30
            self.state.waiting_for_player = False

        elif self.state.sub_step == 20:
            # Accused has pleaded
            self.state.sub_step = 30
            self.state.waiting_for_player = False

    def run_prosecution_opening(self) -> bool:
        """Stage 4: Prosecution opens its case."""
        if self.state.stage_initialized:
            return True

        if self.is_player(RoleType.PROSECUTOR):
            self.state.waiting_for_player = True
            self.state.stage_initialized = True
            return False

        context = (
            f"Stage 4: You open the prosecution's case. Explain the prosecution story and list the witnesses "
            f"you will examine. Witnesses: {', '.join(w.designation for w in self.pw_witnesses)}."
        )
        pp_response = self.agents.get_response("prosecutor", context)
        pp = self.get_character_by_role(RoleType.PROSECUTOR)
        self.add_dialogue(pp.name, RoleType.PROSECUTOR, pp_response)
        self.state.stage_initialized = True
        return True

    def handle_prosecution_opening_input(self, player_input: str):
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)
        self.state.waiting_for_player = False

    def run_witness_examination(self) -> bool:
        """Stage 5: Witness Examination — handles all PW witnesses with Chief/Cross/Re-exam."""
        wi = self.state.current_witness_index
        if wi >= len(self.pw_witnesses):
            # All witnesses examined — close prosecution evidence
            pp = self.get_character_by_role(RoleType.PROSECUTOR)
            if not self.state.stage_initialized:
                self.add_dialogue(pp.name, RoleType.PROSECUTOR, "My Lord, prosecution evidence is closed.")
                self.state.stage_initialized = True
            return True

        witness = self.pw_witnesses[wi]
        phase = self.state.current_exam_phase

        if not self.state.stage_initialized:
            # Call the witness
            clerk = self.get_character_by_role(RoleType.CLERK)
            self.add_dialogue(
                clerk.name, RoleType.CLERK,
                f"{witness.designation} — {witness.name} is called to the witness stand."
            )
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, f"{witness.name}, please tell the truth. You may begin.")
            self.state.stage_initialized = True
            self.state.current_exam_phase = WitnessExamPhase.CHIEF

        self.state.waiting_for_player = True
        return False

    def handle_witness_exam_input(self, player_input: str):
        """Handle player input during witness examination."""
        wi = self.state.current_witness_index
        witness = self.pw_witnesses[wi]
        phase = self.state.current_exam_phase
        player_char = self.get_character_by_role(self.state.player_role)
        witness_key = f"pw_{wi}"

        # Determine who is asking/answering
        if phase == WitnessExamPhase.CHIEF:
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"
        elif phase == WitnessExamPhase.CROSS:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"
        else:  # RE_EXAMINATION
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"

        # If player is the examiner — they ask a question, witness AI answers
        if self.is_player(examiner_role):
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)
            context = (
                f"Stage 5: Witness Examination. Phase: {phase.value}. "
                f"You are {witness.name} ({witness.designation}). "
                f"The {'prosecutor' if examiner_role == RoleType.PROSECUTOR else 'defence counsel'} asked: \"{player_input}\"\n"
                f"Answer the question based on what you know."
            )
            witness_response = self.agents.get_response(witness_key, context, player_input)
            self.add_dialogue(witness.name, RoleType.WITNESS_PW, witness_response)

        # If player is the witness — examiner AI asks, player answers
        elif self.is_player(RoleType.WITNESS_PW):
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

        # If player is judge or accused — AI handles both examiner and witness
        elif self.is_player(RoleType.JUDGE):
            # Player as judge can interject
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)
            # AI continues examination
            examiner_char = self.get_character_by_role(examiner_role)
            context = (
                f"Stage 5: Witness Examination. Phase: {phase.value}. Examining {witness.name}. "
                f"The Judge said: \"{player_input}\". Continue your examination.\n{self.get_recent_context(5)}"
            )
            q = self.agents.get_response(examiner_key, context)
            self.add_dialogue(examiner_char.name, examiner_role, q)

            w_context = f"Phase: {phase.value}. Question: \"{q}\". Answer based on your knowledge."
            a = self.agents.get_response(witness_key, w_context, q)
            self.add_dialogue(witness.name, RoleType.WITNESS_PW, a)
        else:
            # Player is accused or other — just observe, AI handles
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

    def auto_witness_exchange(self):
        """Generate one AI examiner question + AI witness answer (for non-examiner players)."""
        wi = self.state.current_witness_index
        witness = self.pw_witnesses[wi]
        phase = self.state.current_exam_phase
        witness_key = f"pw_{wi}"

        if phase == WitnessExamPhase.CHIEF:
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"
        elif phase == WitnessExamPhase.CROSS:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"
        else:
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"

        if self.is_player(examiner_role):
            return  # player asks

        examiner_char = self.get_character_by_role(examiner_role)
        context = (
            f"Stage 5: Witness Examination. Phase: {phase.value}. "
            f"You are examining {witness.name} ({witness.designation}). "
            f"Ask your next question.\n{self.get_recent_context(5)}"
        )
        question = self.agents.get_response(examiner_key, context)
        self.add_dialogue(examiner_char.name, examiner_role, question)

        if not self.is_player(RoleType.WITNESS_PW):
            w_context = f"Phase: {phase.value}. Question: \"{question}\". Answer based on your knowledge."
            answer = self.agents.get_response(witness_key, w_context, question)
            self.add_dialogue(witness.name, RoleType.WITNESS_PW, answer)

    def advance_exam_phase(self):
        """Move to next exam phase or next witness."""
        phase = self.state.current_exam_phase
        if phase == WitnessExamPhase.CHIEF:
            self.state.current_exam_phase = WitnessExamPhase.CROSS
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Defence, you may cross-examine the witness.")
        elif phase == WitnessExamPhase.CROSS:
            self.state.current_exam_phase = WitnessExamPhase.RE_EXAMINATION
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Prosecution, any re-examination?")
        else:
            # Done with this witness, move to next
            self.state.current_witness_index += 1
            self.state.current_exam_phase = WitnessExamPhase.CHIEF
            self.state.stage_initialized = False

    def run_accused_statement(self) -> bool:
        """Stage 6: Statement of Accused — Judge asks, accused answers. No cross-exam."""
        if self.state.stage_initialized and not self.state.waiting_for_player:
            return True

        if not self.state.stage_initialized:
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(
                judge.name, RoleType.JUDGE,
                "Under Section 313 CrPC, I shall now examine the accused. "
                "The accused is reminded that this is not on oath and there is no cross-examination."
            )
            self.state.stage_initialized = True
            self.state.sub_step = 0

        # Judge asks question
        if self.state.sub_step < 3:
            if self.is_player(RoleType.JUDGE):
                self.state.waiting_for_player = True
                return False

            context = (
                f"Stage 6: Accused Statement. You are the Judge examining the accused. "
                f"Ask question {self.state.sub_step + 1} of 3 based on prosecution evidence. "
                f"Previous exchanges:\n{self.get_recent_context(6)}"
            )
            judge = self.get_character_by_role(RoleType.JUDGE)
            question = self.agents.get_response("judge", context)
            self.add_dialogue(judge.name, RoleType.JUDGE, question)

            # Accused answers
            if self.is_player(RoleType.ACCUSED):
                self.state.waiting_for_player = True
                return False

            a_context = f"The Judge asked you: \"{question}\". Answer based on your version of events."
            accused = self.get_character_by_role(RoleType.ACCUSED)
            answer = self.agents.get_response("accused", a_context, question)
            self.add_dialogue(accused.name, RoleType.ACCUSED, answer)
            self.state.sub_step += 1
            return False
        else:
            return True

    def handle_accused_statement_input(self, player_input: str):
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

        if self.is_player(RoleType.JUDGE):
            # Player judge asked, accused AI answers
            accused = self.get_character_by_role(RoleType.ACCUSED)
            if self.is_player(RoleType.ACCUSED):
                return
            a_context = f"The Judge asked: \"{player_input}\". Answer."
            answer = self.agents.get_response("accused", a_context, player_input)
            self.add_dialogue(accused.name, RoleType.ACCUSED, answer)
            self.state.sub_step += 1
            if self.state.sub_step >= 3:
                self.state.waiting_for_player = False

        elif self.is_player(RoleType.ACCUSED):
            # Player answered, continue
            self.state.sub_step += 1
            if self.state.sub_step >= 3:
                self.state.waiting_for_player = False

    def run_defence_evidence(self) -> bool:
        """Stage 7: Defence Evidence (Optional)."""
        if not self.dw_witnesses:
            if not self.state.stage_initialized:
                defence = self.get_character_by_role(RoleType.DEFENCE)
                self.add_dialogue(defence.name, RoleType.DEFENCE, "The defence does not wish to lead any evidence, My Lord.")
                self.state.stage_initialized = True
            return True

        dwi = self.state.dw_index
        if dwi >= len(self.dw_witnesses):
            if not self.state.is_defence_evidence_phase:
                defence = self.get_character_by_role(RoleType.DEFENCE)
                self.add_dialogue(defence.name, RoleType.DEFENCE, "Defence evidence is closed, My Lord.")
                self.state.is_defence_evidence_phase = True
            return True

        dw = self.dw_witnesses[dwi]
        if not self.state.stage_initialized:
            defence = self.get_character_by_role(RoleType.DEFENCE)
            self.add_dialogue(defence.name, RoleType.DEFENCE, f"The defence wishes to examine {dw.designation} — {dw.name}.")
            clerk = self.get_character_by_role(RoleType.CLERK)
            self.add_dialogue(clerk.name, RoleType.CLERK, f"{dw.designation} — {dw.name} is called to the witness stand.")
            self.state.stage_initialized = True
            self.state.dw_exam_phase = WitnessExamPhase.CHIEF

        self.state.waiting_for_player = True
        return False

    def handle_dw_exam_input(self, player_input: str):
        dwi = self.state.dw_index
        dw = self.dw_witnesses[dwi]
        phase = self.state.dw_exam_phase
        player_char = self.get_character_by_role(self.state.player_role)
        dw_key = f"dw_{dwi}"

        if phase == WitnessExamPhase.CHIEF:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"
        elif phase == WitnessExamPhase.CROSS:
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"
        else:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"

        if self.is_player(examiner_role):
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)
            context = f"Phase: {phase.value}. Question: \"{player_input}\". Answer."
            response = self.agents.get_response(dw_key, context, player_input)
            self.add_dialogue(dw.name, RoleType.WITNESS_DW, response)
        else:
            self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

    def auto_dw_exchange(self):
        dwi = self.state.dw_index
        dw = self.dw_witnesses[dwi]
        phase = self.state.dw_exam_phase
        dw_key = f"dw_{dwi}"

        if phase == WitnessExamPhase.CHIEF:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"
        elif phase == WitnessExamPhase.CROSS:
            examiner_role = RoleType.PROSECUTOR
            examiner_key = "prosecutor"
        else:
            examiner_role = RoleType.DEFENCE
            examiner_key = "defence"

        if self.is_player(examiner_role):
            return

        examiner_char = self.get_character_by_role(examiner_role)
        context = f"Stage 7: Defence Evidence. Phase: {phase.value}. Examining {dw.name}. Ask next question.\n{self.get_recent_context(5)}"
        question = self.agents.get_response(examiner_key, context)
        self.add_dialogue(examiner_char.name, examiner_role, question)

        if not self.is_player(RoleType.WITNESS_DW):
            w_context = f"Phase: {phase.value}. Question: \"{question}\". Answer."
            answer = self.agents.get_response(dw_key, w_context, question)
            self.add_dialogue(dw.name, RoleType.WITNESS_DW, answer)

    def advance_dw_exam_phase(self):
        phase = self.state.dw_exam_phase
        if phase == WitnessExamPhase.CHIEF:
            self.state.dw_exam_phase = WitnessExamPhase.CROSS
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Prosecution, you may cross-examine.")
        elif phase == WitnessExamPhase.CROSS:
            self.state.dw_exam_phase = WitnessExamPhase.RE_EXAMINATION
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Defence, any re-examination?")
        else:
            self.state.dw_index += 1
            self.state.dw_exam_phase = WitnessExamPhase.CHIEF
            self.state.stage_initialized = False

    def run_final_arguments(self) -> bool:
        """Stage 8: Final Arguments — Prosecution first, then Defence."""
        if not self.state.stage_initialized:
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "The Court will now hear final arguments. Prosecution may begin.")
            self.state.stage_initialized = True
            self.state.final_arg_turn = "prosecution"

        if self.state.final_arg_turn == "prosecution":
            if self.is_player(RoleType.PROSECUTOR):
                self.state.waiting_for_player = True
                return False

            context = (
                f"Stage 8: Final Arguments. You are the Public Prosecutor. Deliver your closing argument. "
                f"Summarize the prosecution evidence, witness testimony, and argue guilt beyond reasonable doubt.\n"
                f"Case summary:\n{self.get_recent_context(15)}"
            )
            pp = self.get_character_by_role(RoleType.PROSECUTOR)
            response = self.agents.get_response("prosecutor", context)
            self.add_dialogue(pp.name, RoleType.PROSECUTOR, response)
            self.state.final_arg_turn = "defence"

            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Defence, your final arguments.")

        if self.state.final_arg_turn == "defence":
            if self.is_player(RoleType.DEFENCE):
                self.state.waiting_for_player = True
                return False

            context = (
                f"Stage 8: Final Arguments. You are Defence Counsel. Deliver your closing argument. "
                f"Highlight contradictions, delay in FIR, interested witnesses, and argue for acquittal.\n"
                f"Case summary:\n{self.get_recent_context(20)}"
            )
            defence = self.get_character_by_role(RoleType.DEFENCE)
            response = self.agents.get_response("defence", context)
            self.add_dialogue(defence.name, RoleType.DEFENCE, response)
            self.state.final_arg_turn = "done"
            return True

        if self.state.final_arg_turn == "done":
            return True

        return False

    def handle_final_args_input(self, player_input: str):
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)

        if self.state.final_arg_turn == "prosecution":
            self.state.final_arg_turn = "defence"
            judge = self.get_character_by_role(RoleType.JUDGE)
            self.add_dialogue(judge.name, RoleType.JUDGE, "Defence, your final arguments.")
            self.state.waiting_for_player = False

        elif self.state.final_arg_turn == "defence":
            self.state.final_arg_turn = "done"
            self.state.waiting_for_player = False

    def run_judgment(self) -> bool:
        """Stage 9: Judgment."""
        if self.state.verdict:
            return True

        if self.is_player(RoleType.JUDGE):
            self.state.waiting_for_player = True
            return False

        judge = self.get_character_by_role(RoleType.JUDGE)
        context = (
            f"Stage 9: Judgment. You are the Sessions Judge. After hearing both sides and examining all evidence, "
            f"deliver your judgment. Consider:\n"
            f"- Prosecution witnesses and their credibility\n"
            f"- Defence arguments about delay, contradictions, self-defence\n"
            f"- Medical and forensic evidence\n"
            f"- The accused's statement\n"
            f"Pronounce either ACQUITTAL or CONVICTION with detailed reasoning (5-8 sentences).\n\n"
            f"Full trial record:\n{self.get_recent_context(30)}"
        )
        verdict = self.agents.get_response("judge", context)
        self.add_dialogue(judge.name, RoleType.JUDGE, verdict)
        self.state.verdict = verdict
        return True

    def handle_judgment_input(self, player_input: str):
        player_char = self.get_character_by_role(self.state.player_role)
        self.add_dialogue(player_char.name, self.state.player_role, player_input, is_player=True)
        self.state.verdict = player_input
        self.state.waiting_for_player = False
