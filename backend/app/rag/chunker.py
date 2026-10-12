import uuid
from typing import List, Optional
from pydantic import BaseModel, Field

from app.rag.parser import ParsedDocument, DocumentSection


# Default gold chunking parameters for ERP documents & gemini-embedding-2
DEFAULT_CHUNK_SIZE = 1800       # ~450 - 550 tokens
DEFAULT_CHUNK_OVERLAP = 200     # ~50 - 60 tokens
SEPARATORS = ["\n\n", "\n", ". ", "; ", ", ", " "]


class ChunkPayload(BaseModel):
    """Normalized payload ready to be embedded and stored in ai.document_chunks."""
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section_type: str = "text"
    metadata: dict = Field(default_factory=dict)


def _split_text_recursive(
    text: str,
    max_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
    separators: Optional[List[str]] = None,
) -> List[str]:
    """
    Recursively splits text into chunks under max_size using hierarchical separators.
    Preserves whole words and sentences with overlap.
    """
    separators = separators or SEPARATORS
    text = text.strip()
    if not text:
        return []

    if len(text) <= max_size:
        return [text]

    # Find the first separator present in text
    chosen_sep = None
    for sep in separators:
        if sep in text:
            chosen_sep = sep
            break

    if not chosen_sep:
        # Fallback: slice by words or hard boundary
        parts = text.split(" ")
        chosen_sep = " "

    # Split using the chosen separator
    raw_splits = text.split(chosen_sep)
    chunks: List[str] = []
    current_piece = ""

    for split in raw_splits:
        split_with_sep = split if not current_piece else chosen_sep + split
        if len(current_piece) + len(split_with_sep) <= max_size:
            current_piece += split_with_sep
        else:
            if current_piece:
                chunks.append(current_piece.strip())
                # Create overlap buffer from end of current_piece
                if overlap > 0 and len(current_piece) > overlap:
                    overlap_seed = current_piece[-overlap:]
                    # Try not to cut in middle of a word
                    space_idx = overlap_seed.find(" ")
                    if space_idx != -1:
                        overlap_seed = overlap_seed[space_idx + 1:]
                    current_piece = overlap_seed + chosen_sep + split
                else:
                    current_piece = split
            else:
                # A single split exceeds max_size -> recursively split with finer separators
                next_seps = separators[separators.index(chosen_sep) + 1:] if chosen_sep in separators else []
                if next_seps:
                    sub_chunks = _split_text_recursive(split, max_size, overlap, next_seps)
                    chunks.extend(sub_chunks)
                else:
                    # Hard split
                    for i in range(0, len(split), max_size - overlap):
                        chunks.append(split[i : i + max_size].strip())
                current_piece = ""

    if current_piece.strip():
        chunks.append(current_piece.strip())

    return [c for c in chunks if c.strip()]


def _split_markdown_table(table_text: str, max_size: int = DEFAULT_CHUNK_SIZE) -> List[str]:
    """
    Splits a Markdown table while preserving the table header on every chunk.
    Never splits single table rows in half.
    """
    lines = [line.strip() for line in table_text.strip().split("\n") if line.strip()]
    if len(lines) <= 2 or len(table_text) <= max_size:
        return [table_text.strip()]

    header_lines = lines[:2]  # [Header row, |---|---| separator]
    header_block = "\n".join(header_lines)
    data_rows = lines[2:]

    chunks: List[str] = []
    current_rows: List[str] = []
    current_len = len(header_block)

    for row in data_rows:
        row_len = len(row) + 1  # newline
        if current_len + row_len <= max_size:
            current_rows.append(row)
            current_len += row_len
        else:
            if current_rows:
                chunk = header_block + "\n" + "\n".join(current_rows)
                chunks.append(chunk)
            current_rows = [row]
            current_len = len(header_block) + row_len

    if current_rows:
        chunk = header_block + "\n" + "\n".join(current_rows)
        chunks.append(chunk)

    return chunks


def chunk_document(
    parsed_doc: ParsedDocument,
    document_id: Optional[uuid.UUID] = None,
    access_scope: str = "internal",
    checksum: Optional[str] = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[ChunkPayload]:
    """
    Structure-Aware Recursive Chunking pipeline.
    Splits ParsedDocument sections, preserving tables and tagging ACL & page metadata.
    """
    chunks: List[ChunkPayload] = []
    current_index = 0

    for section in parsed_doc.sections:
        section_text = section.text.strip()
        if not section_text:
            continue

        # Strategy 1: Table Preservation
        if section.section_type == "table":
            table_chunks = _split_markdown_table(section_text, max_size=chunk_size)
            for t_chunk in table_chunks:
                payload = ChunkPayload(
                    chunk_index=current_index,
                    content=t_chunk,
                    page_number=section.page_number,
                    section_type="table",
                    metadata={
                        "document_id": str(document_id) if document_id else None,
                        "filename": parsed_doc.filename,
                        "page_number": section.page_number,
                        "section_type": "table",
                        "access_scope": access_scope,
                        "checksum": checksum,
                        "char_count": len(t_chunk),
                        "token_count_approx": max(1, len(t_chunk) // 4),
                    },
                )
                chunks.append(payload)
                current_index += 1

        # Strategy 2: Text / Headings Recursive Split
        else:
            text_chunks = _split_text_recursive(
                section_text,
                max_size=chunk_size,
                overlap=chunk_overlap,
            )
            for t_chunk in text_chunks:
                payload = ChunkPayload(
                    chunk_index=current_index,
                    content=t_chunk,
                    page_number=section.page_number,
                    section_type=section.section_type,
                    metadata={
                        "document_id": str(document_id) if document_id else None,
                        "filename": parsed_doc.filename,
                        "page_number": section.page_number,
                        "section_type": section.section_type,
                        "access_scope": access_scope,
                        "checksum": checksum,
                        "char_count": len(t_chunk),
                        "token_count_approx": max(1, len(t_chunk) // 4),
                    },
                )
                chunks.append(payload)
                current_index += 1

    return chunks
