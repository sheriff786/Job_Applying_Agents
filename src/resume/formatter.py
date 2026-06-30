"""Resume DOCX formatter - Handles reading/writing Word documents with precise formatting."""

import copy
from pathlib import Path

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.style import WD_STYLE_TYPE

from src.resume.tailoring_agent import TailoringResult, TailoredSection


class ResumeFormatter:
    """Handles reading resume template and writing tailored versions with perfect formatting.

    Design principles:
    - Single template DOCX with defined sections
    - Preserves original formatting, fonts, spacing
    - Only modifies content text, not structure
    - Ensures ATS-friendly output (no tables, text boxes, or images in critical areas)
    - Clean alignment and consistent spacing
    """

    # Standard resume section identifiers
    SECTION_HEADERS = [
        "summary", "profile", "objective",
        "experience", "work experience", "professional experience",
        "skills", "technical skills", "core competencies",
        "projects", "key projects",
        "education",
        "certifications", "certificates",
        "achievements", "awards",
    ]

    def __init__(self, template_path: str):
        self.template_path = Path(template_path)
        if not self.template_path.exists():
            raise FileNotFoundError(f"Resume template not found: {template_path}")
        self.template_doc = Document(str(self.template_path))

    def read_sections(self) -> dict[str, str]:
        """Read the template and extract sections as text."""
        sections: dict[str, str] = {}
        current_section = "header"
        current_content: list[str] = []

        for para in self.template_doc.paragraphs:
            text = para.text.strip()
            if not text:
                current_content.append("")
                continue

            # Check if this is a section header
            if self._is_section_header(para):
                # Save previous section
                if current_content:
                    sections[current_section] = "\n".join(current_content).strip()
                current_section = text.lower()
                current_content = []
            else:
                current_content.append(text)

        # Save last section
        if current_content:
            sections[current_section] = "\n".join(current_content).strip()

        return sections

    def write_tailored_resume(self, tailoring_result: TailoringResult) -> str:
        """Write a new DOCX with tailored content, preserving formatting."""
        # Deep copy the template document
        doc = copy.deepcopy(self.template_doc)

        # Map tailored sections by name
        tailored_map: dict[str, TailoredSection] = {
            section.section_name.lower(): section
            for section in tailoring_result.sections_modified
        }

        # Walk through document and replace section content
        current_section = "header"
        section_start_idx = -1

        paragraphs = doc.paragraphs
        i = 0
        while i < len(paragraphs):
            para = paragraphs[i]
            text = para.text.strip()

            if self._is_section_header(para):
                # If we have a tailored version of the previous section, apply it
                if current_section in tailored_map:
                    self._replace_section_content(
                        doc, section_start_idx + 1, i, tailored_map[current_section]
                    )
                    # Recalculate after modification
                    paragraphs = doc.paragraphs
                    i = self._find_next_section_header(paragraphs, section_start_idx + 1)
                    if i == -1:
                        break

                current_section = text.lower()
                section_start_idx = i

            i += 1

        # Handle last section
        if current_section in tailored_map:
            self._replace_section_content(
                doc, section_start_idx + 1, len(doc.paragraphs), tailored_map[current_section]
            )

        # Apply final formatting pass
        self._apply_formatting_pass(doc)

        # Save
        output_path = tailoring_result.output_path
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)

        return output_path

    def _is_section_header(self, paragraph) -> bool:
        """Determine if a paragraph is a section header."""
        text = paragraph.text.strip().lower()

        # Check by content
        for header in self.SECTION_HEADERS:
            if text == header or text.startswith(header):
                return True

        # Check by formatting (bold, larger font, or heading style)
        if paragraph.style and "heading" in paragraph.style.name.lower():
            return True

        # Check if all runs are bold
        if paragraph.runs and all(run.bold for run in paragraph.runs if run.text.strip()):
            if len(text) < 40:  # Headers are usually short
                return True

        return False

    def _replace_section_content(
        self, doc: Document, start_idx: int, end_idx: int, tailored: TailoredSection
    ):
        """Replace content between section headers with tailored content."""
        # Get the new content lines
        new_lines = [line for line in tailored.tailored_content.split("\n") if line.strip()]

        # Get paragraphs to replace (excluding headers)
        body = doc.element.body
        paragraphs = doc.paragraphs

        # Count content paragraphs in range
        content_paras = []
        for idx in range(start_idx, min(end_idx, len(paragraphs))):
            if not self._is_section_header(paragraphs[idx]):
                content_paras.append(idx)

        # Replace content in existing paragraphs where possible
        for i, line_idx in enumerate(content_paras):
            if i < len(new_lines):
                para = paragraphs[line_idx]
                self._set_paragraph_text(para, new_lines[i])
            else:
                # Remove extra paragraphs (set to empty, will be cleaned)
                paragraphs[line_idx].text = ""

        # If we need more paragraphs than exist, add them
        if len(new_lines) > len(content_paras) and content_paras:
            last_para = paragraphs[content_paras[-1]]
            for i in range(len(content_paras), len(new_lines)):
                new_para = copy.deepcopy(last_para._element)
                # Clear and set text
                for child in list(new_para):
                    new_para.remove(child)
                last_para._element.addnext(new_para)
                # Set text on the new paragraph
                from docx.oxml.ns import qn
                from docx.oxml import OxmlElement

                run = OxmlElement("w:r")
                text_el = OxmlElement("w:t")
                text_el.text = new_lines[i]
                run.append(text_el)
                new_para.append(run)

    def _set_paragraph_text(self, paragraph, new_text: str):
        """Set paragraph text while preserving formatting of first run."""
        if paragraph.runs:
            # Preserve formatting from first run
            first_run = paragraph.runs[0]
            # Clear all runs
            for run in paragraph.runs:
                run.text = ""
            # Set text in first run
            first_run.text = new_text
        else:
            paragraph.text = new_text

    def _find_next_section_header(self, paragraphs, start_idx: int) -> int:
        """Find the next section header after start_idx."""
        for i in range(start_idx, len(paragraphs)):
            if self._is_section_header(paragraphs[i]):
                return i
        return -1

    def _apply_formatting_pass(self, doc: Document):
        """Final formatting pass to ensure consistency."""
        for para in doc.paragraphs:
            # Ensure consistent bullet point formatting
            text = para.text.strip()
            if text.startswith("•") or text.startswith("-") or text.startswith("▪"):
                # Ensure bullet points have consistent left indent
                if para.paragraph_format.left_indent is None:
                    para.paragraph_format.left_indent = Cm(0.5)
                # Ensure consistent spacing after bullets
                para.paragraph_format.space_after = Pt(2)

            # Remove empty paragraphs (cleanup)
            if not text and para.paragraph_format.space_before is None:
                para.paragraph_format.space_before = Pt(0)
                para.paragraph_format.space_after = Pt(0)

    def create_default_template(self, output_path: str, user_data: dict):
        """Create a professionally formatted resume template from user data."""
        doc = Document()

        # Set default font
        style = doc.styles["Normal"]
        font = style.font
        font.name = "Calibri"
        font.size = Pt(10.5)
        font.color.rgb = RGBColor(0x33, 0x33, 0x33)

        # Set margins
        sections = doc.sections
        for section in sections:
            section.top_margin = Cm(1.5)
            section.bottom_margin = Cm(1.5)
            section.left_margin = Cm(2.0)
            section.right_margin = Cm(2.0)

        # Name
        name_para = doc.add_paragraph()
        name_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_run = name_para.add_run(user_data.get("name", "Your Name"))
        name_run.bold = True
        name_run.font.size = Pt(18)
        name_run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)

        # Contact info
        contact_para = doc.add_paragraph()
        contact_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_parts = []
        if user_data.get("email"):
            contact_parts.append(user_data["email"])
        if user_data.get("phone"):
            contact_parts.append(user_data["phone"])
        if user_data.get("linkedin"):
            contact_parts.append(user_data["linkedin"])
        if user_data.get("github"):
            contact_parts.append(user_data["github"])
        if user_data.get("location"):
            contact_parts.append(user_data["location"])

        contact_run = contact_para.add_run(" | ".join(contact_parts))
        contact_run.font.size = Pt(9)
        contact_run.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

        # Professional Summary
        self._add_section_header(doc, "PROFESSIONAL SUMMARY")
        summary_para = doc.add_paragraph()
        summary_para.add_run(
            user_data.get("summary", "Experienced software engineer with expertise in...")
        )
        summary_para.paragraph_format.space_after = Pt(6)

        # Technical Skills
        self._add_section_header(doc, "TECHNICAL SKILLS")
        skills = user_data.get("skills", {})
        for category, skill_list in skills.items():
            skill_para = doc.add_paragraph()
            cat_run = skill_para.add_run(f"{category}: ")
            cat_run.bold = True
            skill_para.add_run(", ".join(skill_list))
            skill_para.paragraph_format.space_after = Pt(2)

        # Experience
        self._add_section_header(doc, "PROFESSIONAL EXPERIENCE")
        for exp in user_data.get("experience", []):
            # Company and title line
            exp_para = doc.add_paragraph()
            title_run = exp_para.add_run(f"{exp.get('title', '')} | ")
            title_run.bold = True
            exp_para.add_run(exp.get("company", ""))
            # Add location/date on same line with tab
            exp_para.add_run(f"\t{exp.get('location', '')} | {exp.get('dates', '')}")
            exp_para.paragraph_format.space_after = Pt(2)

            # Bullet points
            for bullet in exp.get("bullets", []):
                bullet_para = doc.add_paragraph()
                bullet_para.add_run(f"• {bullet}")
                bullet_para.paragraph_format.left_indent = Cm(0.5)
                bullet_para.paragraph_format.space_after = Pt(1)

        # Projects
        if user_data.get("projects"):
            self._add_section_header(doc, "KEY PROJECTS")
            for project in user_data["projects"]:
                proj_para = doc.add_paragraph()
                proj_run = proj_para.add_run(f"{project.get('name', '')} ")
                proj_run.bold = True
                if project.get("tech"):
                    proj_para.add_run(f"| {project['tech']}")
                proj_para.paragraph_format.space_after = Pt(2)

                for bullet in project.get("bullets", []):
                    bullet_para = doc.add_paragraph()
                    bullet_para.add_run(f"• {bullet}")
                    bullet_para.paragraph_format.left_indent = Cm(0.5)
                    bullet_para.paragraph_format.space_after = Pt(1)

        # Education
        self._add_section_header(doc, "EDUCATION")
        for edu in user_data.get("education", []):
            edu_para = doc.add_paragraph()
            degree_run = edu_para.add_run(f"{edu.get('degree', '')} ")
            degree_run.bold = True
            edu_para.add_run(f"| {edu.get('institution', '')} | {edu.get('year', '')}")
            edu_para.paragraph_format.space_after = Pt(2)

        # Certifications
        if user_data.get("certifications"):
            self._add_section_header(doc, "CERTIFICATIONS")
            for cert in user_data["certifications"]:
                cert_para = doc.add_paragraph()
                cert_para.add_run(f"• {cert}")
                cert_para.paragraph_format.left_indent = Cm(0.5)
                cert_para.paragraph_format.space_after = Pt(1)

        # Save template
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        doc.save(output_path)
        return output_path

    def _add_section_header(self, doc: Document, title: str):
        """Add a consistently formatted section header."""
        # Add separator line
        sep_para = doc.add_paragraph()
        sep_para.paragraph_format.space_before = Pt(8)
        sep_para.paragraph_format.space_after = Pt(0)

        # Add header
        header_para = doc.add_paragraph()
        header_run = header_para.add_run(title)
        header_run.bold = True
        header_run.font.size = Pt(11)
        header_run.font.color.rgb = RGBColor(0x1A, 0x1A, 0x2E)
        header_para.paragraph_format.space_after = Pt(4)
        header_para.paragraph_format.space_before = Pt(2)

        # Bottom border for section header
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement

        pPr = header_para._element.get_or_add_pPr()
        pBdr = OxmlElement("w:pBdr")
        bottom = OxmlElement("w:bottom")
        bottom.set(qn("w:val"), "single")
        bottom.set(qn("w:sz"), "4")
        bottom.set(qn("w:space"), "1")
        bottom.set(qn("w:color"), "1A1A2E")
        pBdr.append(bottom)
        pPr.append(pBdr)
