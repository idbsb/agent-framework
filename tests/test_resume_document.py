import io
import unittest

from docx import Document

from src.core.resume_document import MAX_FILE_BYTES, ResumeDocumentError, extract_resume_document


class ResumeDocumentTest(unittest.TestCase):
    def test_txt_extracts_draft_fields(self):
        text = "教育背景\n硕士 人工智能\n工作经历\n3年开发经验，负责Python平台\n项目经历\n使用RAG和Docker\n专业技能\nPython、RAG、Docker"
        result = extract_resume_document("简历.txt", text.encode())
        self.assertEqual(result.file_type, "txt")
        self.assertIn("硕士", result.education)
        self.assertIn("3年", result.experience)
        self.assertIn("RAG", result.projects)
        self.assertIn("Docker", result.skills_raw)

    def test_docx_extracts_paragraphs_and_tables(self):
        document = Document(); document.add_paragraph("专业技能"); document.add_paragraph("Python、LangGraph")
        table = document.add_table(rows=1, cols=2); table.cell(0, 0).text = "项目经历"; table.cell(0, 1).text = "RAG知识库"
        stream = io.BytesIO(); document.save(stream)
        result = extract_resume_document("resume.docx", stream.getvalue())
        self.assertIn("Python", result.raw_text); self.assertIn("RAG知识库", result.raw_text)

    def test_rejects_old_doc_spoofed_pdf_binary_and_oversize(self):
        cases = [("resume.doc", b"legacy"), ("resume.pdf", b"not-pdf"),
                 ("resume.txt", b"a" * (MAX_FILE_BYTES + 1))]
        for name, data in cases:
            with self.subTest(name=name), self.assertRaises(ResumeDocumentError):
                extract_resume_document(name, data)

    def test_filename_is_reduced_to_basename(self):
        self.assertEqual(extract_resume_document("../../private/resume.txt", b"Python").file_name, "resume.txt")


if __name__ == "__main__":
    unittest.main()
