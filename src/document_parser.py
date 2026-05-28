from __future__ import annotations

from io import BytesIO
from pathlib import Path


class DocumentParseError(ValueError):
    pass


def parse_uploaded_document(uploaded_file) -> str:
    if uploaded_file is None:
        return ""

    suffix = Path(uploaded_file.name).suffix.lower()
    data = uploaded_file.getvalue()
    if not data:
        raise DocumentParseError("上传文件为空，请重新选择文件。")

    if suffix in {".txt", ".md", ".markdown", ".csv"}:
        return _decode_text(data)
    if suffix == ".docx":
        return _read_docx(data)
    if suffix == ".pdf":
        return _read_pdf(data)

    raise DocumentParseError("仅支持 .txt、.md、.markdown、.csv、.docx、.pdf 文件。")


def parse_local_document(file_path: str) -> str:
    path = Path(file_path.strip().strip('"'))
    if not path.exists():
        raise DocumentParseError(f"本地文件不存在：{path}")
    if not path.is_file():
        raise DocumentParseError(f"路径不是文件：{path}")

    suffix = path.suffix.lower()
    data = path.read_bytes()
    if not data:
        raise DocumentParseError("本地文件为空，请选择其他文件。")

    if suffix in {".txt", ".md", ".markdown", ".csv"}:
        return _decode_text(data)
    if suffix == ".docx":
        return _read_docx(data)
    if suffix == ".pdf":
        return _read_pdf(data)
    raise DocumentParseError("仅支持 .txt、.md、.markdown、.csv、.docx、.pdf 文件。")


def choose_prd_text(uploaded_file, pasted_text: str, local_file_path: str = "") -> tuple[str, str]:
    if uploaded_file is not None:
        text = parse_uploaded_document(uploaded_file)
        if not text.strip():
            raise DocumentParseError("文件已上传，但没有解析出有效文本。请确认文件内容不是空白、扫描图片或受保护文档。")
        return text.strip(), f"上传材料：{uploaded_file.name}"
    if local_file_path and local_file_path.strip():
        text = parse_local_document(local_file_path)
        if not text.strip():
            raise DocumentParseError("本地文件没有解析出有效文本。请确认文件内容不是空白、扫描图片或受保护文档。")
        local_name = Path(local_file_path.strip().strip('"')).name
        return text.strip(), f"本地文件：{local_name}"
    if pasted_text and pasted_text.strip():
        return pasted_text.strip(), "粘贴的产品想法"
    return "", ""


def _decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _read_docx(data: bytes) -> str:
    try:
        from docx import Document
    except ImportError as exc:
        raise DocumentParseError("缺少 python-docx 依赖，无法读取 docx。") from exc

    doc = Document(BytesIO(data))
    paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def _read_pdf(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentParseError("缺少 pypdf 依赖，无法读取 pdf。") from exc

    reader = PdfReader(BytesIO(data))
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n".join(pages).strip()
