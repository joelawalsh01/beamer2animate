"""Beamer to PowerPoint converter with line-by-line animations."""

from .parser import parse_beamer, BlockType
from .renderer import (
    render_latex_to_image,
    render_align_cumulative,
    render_itemize_cumulative,
    render_text_cumulative,
    render_text_block,
    compile_beamer_to_pdf,
    extract_frame_from_pdf,
    extract_beamer_theme
)
from .pptx_builder import create_pptx
from .converter import convert_beamer_to_pptx

__all__ = [
    "parse_beamer",
    "BlockType",
    "render_latex_to_image",
    "render_align_cumulative",
    "render_itemize_cumulative",
    "render_text_cumulative",
    "render_text_block",
    "compile_beamer_to_pdf",
    "extract_frame_from_pdf",
    "extract_beamer_theme",
    "create_pptx",
    "convert_beamer_to_pptx"
]
