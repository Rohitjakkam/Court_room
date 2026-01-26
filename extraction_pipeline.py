"""
LangChain Extraction Pipeline for Court Case Documents
Extracts structured data from PDF text using LLM
"""

import os
from typing import Optional
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_text_splitters import RecursiveCharacterTextSplitter

from schemas import (
    CourtCase, CaseMetadata, PartyDetails, LegalRepresentation,
    FactualMatrix, ProceduralHistory, IssuesFramed, EvidenceDetails,
    MedicalEvidence, IncomeProof, CompensationComputation,
    CaseLawCitations, JudicialFindings, FinalOrder,
    PostJudgmentDirections, MachineMetadata, CaseType
)


class CourtCaseExtractor:
    """
    LangChain-based extraction pipeline for court case documents.
    Supports multiple LLM providers (OpenAI, Anthropic).
    """

    def __init__(
        self,
        provider: str = "openai",
        model_name: Optional[str] = None,
        temperature: float = 0.0
    ):
        """
        Initialize the extractor with specified LLM provider.

        Args:
            provider: "openai" or "anthropic"
            model_name: Specific model to use (defaults based on provider)
            temperature: LLM temperature (0.0 for deterministic extraction)
        """
        self.provider = provider
        self.temperature = temperature

        if provider == "openai":
            self.model_name = model_name or "gpt-4o"
            self.llm = ChatOpenAI(
                model=self.model_name,
                temperature=temperature
            )
        elif provider == "anthropic":
            self.model_name = model_name or "claude-3-5-sonnet-20241022"
            self.llm = ChatAnthropic(
                model=self.model_name,
                temperature=temperature
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=8000,
            chunk_overlap=500,
            separators=["\n\n", "\n", ". ", " ", ""]
        )

    def _create_extraction_chain(self, section_name: str, schema_class, document_text: str):
        """Create extraction chain for a specific section."""
        parser = PydanticOutputParser(pydantic_object=schema_class)
        format_instructions = parser.get_format_instructions()

        system_content = f"""You are an expert legal document analyst specializing in Indian court judgments.
Your task is to extract the {section_name} information from the provided court document text.

IMPORTANT INSTRUCTIONS:
1. Extract ONLY information that is explicitly stated in the document
2. Use null/None for fields where information is not available
3. Be precise with dates, names, and numbers
4. For legal citations, include the full citation if available
5. Maintain the exact terminology used in the document

{format_instructions}
"""

        human_content = f"""Extract the {section_name} from the following court document text:

---DOCUMENT TEXT---
{document_text}
---END DOCUMENT---

Provide the extracted information in the required JSON format."""

        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=human_content)
        ]

        return messages, parser

    def _extract_section(self, section_name: str, schema_class, text: str):
        """Generic extraction method for any section."""
        messages, parser = self._create_extraction_chain(section_name, schema_class, text)
        response = self.llm.invoke(messages)
        return parser.parse(response.content)

    def extract_case_metadata(self, text: str) -> CaseMetadata:
        """Extract case metadata (Section 1)."""
        return self._extract_section("Case Metadata", CaseMetadata, text)

    def extract_party_details(self, text: str) -> PartyDetails:
        """Extract party details (Section 2)."""
        return self._extract_section("Party Details", PartyDetails, text)

    def extract_legal_representation(self, text: str) -> LegalRepresentation:
        """Extract legal representation (Section 3)."""
        return self._extract_section("Legal Representation", LegalRepresentation, text)

    def extract_factual_matrix(self, text: str) -> FactualMatrix:
        """Extract factual matrix (Section 4)."""
        return self._extract_section("Factual Matrix", FactualMatrix, text)

    def extract_procedural_history(self, text: str) -> ProceduralHistory:
        """Extract procedural history (Section 5)."""
        return self._extract_section("Procedural History", ProceduralHistory, text)

    def extract_issues_framed(self, text: str) -> IssuesFramed:
        """Extract issues framed (Section 6)."""
        return self._extract_section("Issues Framed", IssuesFramed, text)

    def extract_evidence_details(self, text: str) -> EvidenceDetails:
        """Extract evidence details (Section 7)."""
        return self._extract_section("Evidence Details", EvidenceDetails, text)

    def extract_medical_evidence(self, text: str) -> MedicalEvidence:
        """Extract medical evidence (Section 8)."""
        return self._extract_section("Medical Evidence", MedicalEvidence, text)

    def extract_income_proof(self, text: str) -> IncomeProof:
        """Extract income proof (Section 9)."""
        return self._extract_section("Income Proof", IncomeProof, text)

    def extract_compensation(self, text: str) -> CompensationComputation:
        """Extract compensation computation (Section 10)."""
        return self._extract_section("Compensation Computation", CompensationComputation, text)

    def extract_case_law(self, text: str) -> CaseLawCitations:
        """Extract case law citations (Section 11)."""
        return self._extract_section("Case Law Citations", CaseLawCitations, text)

    def extract_judicial_findings(self, text: str) -> JudicialFindings:
        """Extract judicial findings (Section 12)."""
        return self._extract_section("Judicial Findings", JudicialFindings, text)

    def extract_final_order(self, text: str) -> Optional[FinalOrder]:
        """Extract final order (Section 13)."""
        try:
            return self._extract_section("Final Order", FinalOrder, text)
        except Exception:
            return None

    def extract_post_judgment(self, text: str) -> PostJudgmentDirections:
        """Extract post-judgment directions (Section 14)."""
        return self._extract_section("Post-Judgment Directions", PostJudgmentDirections, text)

    def extract_machine_metadata(self, text: str) -> MachineMetadata:
        """Extract machine metadata (Section 15)."""
        return self._extract_section("Machine Metadata", MachineMetadata, text)

    def extract_full_case(self, text: str, progress_callback=None) -> CourtCase:
        """
        Extract complete court case from document text.

        Args:
            text: Full document text
            progress_callback: Optional callback function(section_name, progress_pct)

        Returns:
            CourtCase: Complete extracted case data
        """
        sections = [
            ("Case Metadata", self.extract_case_metadata),
            ("Party Details", self.extract_party_details),
            ("Legal Representation", self.extract_legal_representation),
            ("Factual Matrix", self.extract_factual_matrix),
            ("Procedural History", self.extract_procedural_history),
            ("Issues Framed", self.extract_issues_framed),
            ("Evidence Details", self.extract_evidence_details),
            ("Medical Evidence", self.extract_medical_evidence),
            ("Income Proof", self.extract_income_proof),
            ("Compensation", self.extract_compensation),
            ("Case Law", self.extract_case_law),
            ("Judicial Findings", self.extract_judicial_findings),
            ("Final Order", self.extract_final_order),
            ("Post-Judgment Directions", self.extract_post_judgment),
            ("Machine Metadata", self.extract_machine_metadata),
        ]

        results = {}
        for idx, (section_name, extractor_fn) in enumerate(sections):
            if progress_callback:
                progress_callback(section_name, (idx / len(sections)) * 100)

            try:
                results[section_name] = extractor_fn(text)
            except Exception as e:
                print(f"Warning: Failed to extract {section_name}: {e}")
                results[section_name] = None

        if progress_callback:
            progress_callback("Complete", 100)

        # Construct the full CourtCase object
        return CourtCase(
            case_metadata=results.get("Case Metadata") or CaseMetadata(
                case_title="Unknown",
                case_type=CaseType.OTHER,
                court_name="Unknown"
            ),
            party_details=results.get("Party Details") or PartyDetails(),
            legal_representation=results.get("Legal Representation") or LegalRepresentation(),
            factual_matrix=results.get("Factual Matrix") or FactualMatrix(),
            procedural_history=results.get("Procedural History") or ProceduralHistory(),
            issues_framed=results.get("Issues Framed") or IssuesFramed(),
            evidence_details=results.get("Evidence Details") or EvidenceDetails(),
            medical_evidence=results.get("Medical Evidence") or MedicalEvidence(),
            income_proof=results.get("Income Proof") or IncomeProof(),
            compensation=results.get("Compensation") or CompensationComputation(),
            case_law=results.get("Case Law") or CaseLawCitations(),
            judicial_findings=results.get("Judicial Findings") or JudicialFindings(),
            final_order=results.get("Final Order"),
            post_judgment=results.get("Post-Judgment Directions") or PostJudgmentDirections(),
            machine_metadata=results.get("Machine Metadata") or MachineMetadata(),
        )


class BatchExtractor:
    """Batch extraction for multiple documents."""

    def __init__(self, extractor: CourtCaseExtractor):
        self.extractor = extractor

    def extract_batch(self, documents: list[tuple[str, str]]) -> list[CourtCase]:
        """
        Extract from multiple documents.

        Args:
            documents: List of (document_id, text) tuples

        Returns:
            List of CourtCase objects
        """
        results = []
        for doc_id, text in documents:
            try:
                case = self.extractor.extract_full_case(text)
                results.append(case)
            except Exception as e:
                print(f"Failed to extract {doc_id}: {e}")
                results.append(None)
        return results


# Utility functions for PDF processing
def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file."""
    import PyPDF2

    with open(pdf_path, 'rb') as file:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
    return text


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """Extract text from PDF bytes."""
    import PyPDF2
    from io import BytesIO

    reader = PyPDF2.PdfReader(BytesIO(pdf_bytes))
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text
