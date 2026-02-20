from schemas import CaseInfo, Character, RoleType, Evidence, EvidenceStatus


def get_case_info() -> CaseInfo:
    return CaseInfo(
        title="State of Maharashtra vs. Rajesh Kumar Sharma",
        case_number="Sessions Case No. 142 of 2025",
        court="Court of the Learned Sessions Judge, Mumbai",
        sections=["Section 304 (Culpable Homicide not amounting to Murder)", "Section 323 (Voluntarily causing hurt)"],
        fir_number="FIR No. 287/2025",
        fir_date="15th March, 2025",
        fir_summary=(
            "FIR lodged by Amit Verma (brother of deceased Sunil Verma) at Andheri Police Station. "
            "Complainant states that on 14th March 2025, at approximately 9:30 PM, near Lokhandwala Circle, "
            "a road rage incident occurred between the accused Rajesh Kumar Sharma and the deceased Sunil Verma. "
            "The accused struck the deceased on the head with an iron rod causing fatal injuries. "
            "The deceased was rushed to Cooper Hospital where he was declared dead on arrival."
        ),
        incident_date="14th March, 2025",
        incident_summary=(
            "On the evening of 14th March 2025, near Lokhandwala Circle, Andheri West, Mumbai, "
            "the accused Rajesh Kumar Sharma's car brushed against the motorcycle of deceased Sunil Verma. "
            "A heated argument ensued. The accused retrieved an iron rod from his car and struck the deceased "
            "on the head multiple times. Bystanders intervened but the deceased had already sustained severe "
            "head injuries. He was rushed to Cooper Hospital but was declared dead on arrival. "
            "The accused fled the scene but was apprehended by police the next morning at his residence."
        ),
        prosecution_story=(
            "The prosecution alleges that the accused Rajesh Kumar Sharma, in a fit of rage during a road "
            "altercation, deliberately retrieved an iron rod from his car boot and struck the deceased Sunil "
            "Verma on the head with full force, causing fatal cranial injuries. The act was intentional and "
            "the accused knew that such a blow to the head was likely to cause death. The prosecution relies "
            "on the testimony of the complainant (PW-1, brother of deceased), an independent eyewitness "
            "(PW-2), the Investigating Officer (PW-3), medical evidence (post-mortem report), CCTV footage "
            "from a nearby shop, and the recovery of the weapon (iron rod) from the scene."
        ),
        defence_story=(
            "The defence contends that the deceased Sunil Verma was the initial aggressor. After the minor "
            "collision, the deceased and two of his companions attacked the accused with fists and kicks. "
            "The accused, fearing for his life, picked up an iron rod lying on the road (not from his car) "
            "and swung it in self-defence. The blow was not intended to kill. The accused has no prior "
            "criminal record. The FIR was lodged with a delay of over 6 hours. PW-1 is an interested "
            "witness being the brother of the deceased. The CCTV footage is of poor quality and does not "
            "clearly show who struck first."
        ),
    )


def get_characters() -> list[Character]:
    return [
        Character(
            name="Hon'ble Justice Meera Deshmukh",
            role=RoleType.JUDGE,
            designation="Sessions Judge",
            description="Experienced Sessions Judge with 18 years on the bench. Known for being thorough and fair.",
            personality="Formal, patient but firm, insists on proper procedure, asks pointed questions.",
            facts_known="Has read the charge-sheet, FIR, and all statements. Knows the case facts from the record.",
        ),
        Character(
            name="Adv. Vikram Patil",
            role=RoleType.PROSECUTOR,
            designation="Public Prosecutor",
            description="Senior Public Prosecutor with 15 years of experience in criminal trials.",
            personality="Methodical, assertive, builds case brick by brick. Professional but aggressive in cross-examination.",
            facts_known=(
                "Knows the full prosecution story. The accused hit the deceased with an iron rod from his car "
                "during a road rage incident. Has FIR, post-mortem report, CCTV footage, eyewitness accounts. "
                "Witnesses: PW-1 Amit Verma (complainant, brother), PW-2 Ramesh Gupta (eyewitness, shopkeeper), "
                "PW-3 Inspector Suresh Jadhav (IO)."
            ),
        ),
        Character(
            name="Adv. Priya Malhotra",
            role=RoleType.DEFENCE,
            designation="Defence Counsel",
            description="Sharp criminal defence lawyer known for finding contradictions and raising reasonable doubt.",
            personality="Strategic, calm, finds weaknesses in prosecution's case. Uses delay in FIR, interested witnesses, and self-defence arguments.",
            facts_known=(
                "The accused claims self-defence. The deceased and his companions attacked first. "
                "The iron rod was lying on the road, not from the accused's car. FIR was delayed by 6 hours. "
                "PW-1 is an interested witness. CCTV is unclear. Accused has no prior criminal record. "
                "DW-1 is Kiran Sharma (wife of accused) who spoke to him on phone during the incident."
            ),
        ),
        Character(
            name="Rajesh Kumar Sharma",
            role=RoleType.ACCUSED,
            designation="Accused",
            description="35-year-old businessman with no prior criminal record. Married with two children.",
            personality="Nervous but maintains innocence. Respectful to the court. Claims he acted in self-defence.",
            facts_known=(
                "Was driving home after work. A motorcycle brushed his car. The rider (deceased) and two "
                "companions started beating him. He picked up an iron rod from the roadside to defend himself. "
                "He did not intend to kill anyone. He panicked and drove away. He was arrested next morning. "
                "He called his wife during the incident. He has never been in trouble with the law before."
            ),
        ),
        Character(
            name="Amit Verma",
            role=RoleType.WITNESS_PW,
            designation="PW-1 (Complainant / Brother of Deceased)",
            description="28-year-old, brother of the deceased Sunil Verma. Lodged the FIR.",
            personality="Emotional, cooperative with prosecution, gets defensive during cross-examination.",
            facts_known=(
                "Was riding pillion on his brother Sunil's motorcycle. The accused's car brushed their bike. "
                "When they stopped, the accused came out aggressively, opened his car boot, took out an iron rod "
                "and struck Sunil on the head. Sunil fell down bleeding. Amit called the ambulance and rushed "
                "Sunil to hospital. Sunil was declared dead. Amit went to the police station and filed FIR "
                "at around 3:30 AM (about 6 hours after the incident). He was at the hospital attending to "
                "his brother which caused the delay."
            ),
            chief_exam_topics=[
                "Ask witness to state his relationship with the deceased",
                "Ask what happened on the evening of 14th March 2025",
                "Ask how the collision occurred between the car and motorcycle",
                "Ask what the accused did after the collision — did he go to his car boot?",
                "Ask witness to describe the assault — how many blows, where on the body",
                "Ask witness to identify the accused in court",
                "Ask what happened after the assault — hospital, death",
                "Ask when and why FIR was filed — explain the 6-hour delay",
                "Present FIR (E1) and ask witness to identify it",
            ],
            cross_exam_points=[
                "You are the brother of the deceased — you are an interested witness, correct?",
                "You filed the FIR 6 hours after the incident. Why the delay?",
                "In your FIR you did not mention that the accused opened the car boot. Is that correct?",
                "Is it true that your brother Sunil and his companions attacked the accused first?",
                "Did you see any injuries on the accused at the scene?",
                "How far were you standing when the blow was struck?",
                "Is it not true that there was prior enmity between your family and the accused?",
                "You were emotional and traumatised — can you be sure of the exact sequence of events?",
            ],
        ),
        Character(
            name="Ramesh Gupta",
            role=RoleType.WITNESS_PW,
            designation="PW-2 (Independent Eyewitness / Shopkeeper)",
            description="45-year-old shopkeeper whose shop is near Lokhandwala Circle. Witnessed the incident.",
            personality="Nervous, tries to be truthful, sometimes uncertain about details. Independent witness.",
            facts_known=(
                "Was closing his shop around 9:30 PM when he heard loud arguments. Saw two men arguing near "
                "a car and motorcycle. Saw one man (the accused) go to his car and come back with something "
                "in his hand — looked like a rod. He struck the other man (deceased) on the head. The deceased "
                "fell. People gathered. He went inside his shop and called police. He has CCTV in his shop "
                "which captured part of the incident. He does not know either party personally."
            ),
            chief_exam_topics=[
                "Ask witness where his shop is located relative to Lokhandwala Circle",
                "Ask what he was doing at approximately 9:30 PM on 14th March 2025",
                "Ask what first drew his attention — what did he hear/see",
                "Ask witness to describe what he saw — the argument, the assault",
                "Ask whether he saw where the rod came from — car boot or elsewhere",
                "Ask what happened after the blow was struck",
                "Ask whether his shop has CCTV and whether it captured the incident",
                "Present CCTV footage (E4) and ask witness to confirm it is from his shop",
                "Ask whether he knows either party personally",
            ],
            cross_exam_points=[
                "How far was your shop from the spot where the incident occurred?",
                "It was 9:30 PM — was it dark? What was the lighting like?",
                "You said you saw him go to his car — but could you clearly see the car boot from your position?",
                "Did you see who started the physical altercation?",
                "The CCTV footage is grainy — do you agree it does not clearly show faces?",
                "Is it possible that there were other persons involved who attacked the accused?",
                "When did you call the police? Why did you not intervene?",
                "You are nervous — are you sure about the sequence of events?",
            ],
        ),
        Character(
            name="Inspector Suresh Jadhav",
            role=RoleType.WITNESS_PW,
            designation="PW-3 (Investigating Officer)",
            description="Senior Inspector at Andheri Police Station. Investigated this case.",
            personality="Professional, factual, sticks to the investigation record. Confident under cross-examination.",
            facts_known=(
                "Received the FIR at 3:30 AM on 15th March. Visited the scene. Recovered the iron rod (blood-stained) "
                "from the spot. Seized CCTV footage from PW-2's shop. Recorded statements of PW-1 and PW-2. "
                "Arrested the accused at his residence on 15th March at 8:00 AM. The accused was cooperative. "
                "Sent the iron rod for forensic analysis — blood matched deceased. Post-mortem confirmed cause "
                "of death as severe cranial trauma. Filed charge-sheet under Section 304 and 323 IPC."
            ),
            chief_exam_topics=[
                "Ask when the FIR was received and what action was taken",
                "Ask about visiting the scene — what was found there",
                "Ask about recovery of the iron rod (E3) — where exactly, condition",
                "Ask about seizure of CCTV footage from PW-2's shop",
                "Ask about arrest of the accused — when, where, his condition",
                "Present post-mortem report (E2) and ask about cause of death",
                "Present forensic report (E5) and ask about blood match on the rod",
                "Ask about filing of charge-sheet",
            ],
            cross_exam_points=[
                "The FIR was received at 3:30 AM — nearly 6 hours after the incident. Did you investigate this delay?",
                "Did you find any injuries on the accused when he was arrested?",
                "Did the accused tell you that he acted in self-defence?",
                "Were there other persons at the scene apart from PW-1 and the deceased?",
                "The CCTV footage does not clearly show who struck first — do you agree?",
                "Did you investigate whether the deceased had companions who may have attacked the accused?",
                "The iron rod — did you consider it could have been lying on the road rather than from the car?",
                "Did you collect the medical report of the accused showing his injuries?",
            ],
        ),
        Character(
            name="Kiran Sharma",
            role=RoleType.WITNESS_DW,
            designation="DW-1 (Wife of Accused)",
            description="32-year-old homemaker, wife of the accused Rajesh Kumar Sharma.",
            personality="Supportive of husband, emotional, tries to help the defence case.",
            facts_known=(
                "Her husband called her at approximately 9:35 PM on the night of the incident sounding panicked. "
                "He said some men were beating him on the road and he had to defend himself. She heard shouting "
                "in the background. He said he was coming home. When he arrived home around 10:15 PM, he had "
                "bruises on his face and arms, and his shirt was torn. He told her what happened. She wanted "
                "to go to the police but he was too shaken. He was arrested the next morning."
            ),
        ),
        Character(
            name="Court Clerk",
            role=RoleType.CLERK,
            designation="Court Clerk",
            description="Court administrative officer responsible for calling cases and recording proceedings.",
            personality="Procedural, formal, announces cases and stages clearly.",
            facts_known="Knows the case number, parties, and procedural requirements.",
        ),
    ]


def get_evidence_list() -> list[Evidence]:
    return [
        Evidence(
            id="E1",
            name="First Information Report (FIR)",
            description="FIR No. 287/2025 lodged by Amit Verma at Andheri PS at 3:30 AM on 15/03/2025",
            evidence_type="documentary",
            presented_by="prosecution",
        ),
        Evidence(
            id="E2",
            name="Post-Mortem Report",
            description="Post-mortem of deceased Sunil Verma confirming cause of death as severe cranial trauma due to blunt force injury",
            evidence_type="documentary",
            presented_by="prosecution",
        ),
        Evidence(
            id="E3",
            name="Iron Rod (Weapon)",
            description="Blood-stained iron rod (approx. 2 feet) recovered from the scene. Forensic report confirms blood matches deceased.",
            evidence_type="physical",
            presented_by="prosecution",
        ),
        Evidence(
            id="E4",
            name="CCTV Footage",
            description="CCTV footage from PW-2's shop showing the altercation. Quality is moderate, partially captures the incident.",
            evidence_type="documentary",
            presented_by="prosecution",
        ),
        Evidence(
            id="E5",
            name="Forensic Analysis Report",
            description="FSL report confirming blood on iron rod matches deceased's blood group and DNA.",
            evidence_type="documentary",
            presented_by="prosecution",
        ),
        Evidence(
            id="E6",
            name="Scene of Crime Panchnama",
            description="Panchnama of the scene near Lokhandwala Circle prepared by IO with two panch witnesses.",
            evidence_type="documentary",
            presented_by="prosecution",
        ),
        Evidence(
            id="E7",
            name="Medical Report of Accused",
            description="Medical examination of accused showing bruises on face and forearms, consistent with a physical altercation.",
            evidence_type="documentary",
            presented_by="defence",
        ),
        Evidence(
            id="E8",
            name="Phone Call Records",
            description="Call records showing accused called his wife (DW-1) at 9:35 PM on 14/03/2025, duration 2 minutes.",
            evidence_type="documentary",
            presented_by="defence",
        ),
    ]


def get_pw_witnesses() -> list[Character]:
    """Return only prosecution witnesses in order."""
    chars = get_characters()
    return [c for c in chars if c.role == RoleType.WITNESS_PW]


def get_dw_witnesses() -> list[Character]:
    """Return only defence witnesses in order."""
    chars = get_characters()
    return [c for c in chars if c.role == RoleType.WITNESS_DW]


def get_character_by_role(role: RoleType, designation: str = None) -> Character:
    """Get a specific character by role and optionally designation."""
    chars = get_characters()
    for c in chars:
        if c.role == role:
            if designation is None or c.designation == designation:
                return c
    return None
