"""Render LaTeX content to images."""

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple
import fitz  # PyMuPDF


# Default styling to match Beamer look
DEFAULT_STYLE = {
    'font_size': '11pt',
    'text_width': '12cm',  # Consistent width for all content
    'title_color': '0.2,0.2,0.6',  # Dark blue
    'text_color': '0,0,0',
    'math_color': '0,0,0',
}


def remove_nested_braces(content: str, command: str) -> str:
    """Remove a command with nested braces like \\fbox{...nested...}."""
    result = []
    i = 0
    cmd = '\\' + command

    while i < len(content):
        if content[i:].startswith(cmd):
            j = i + len(cmd)
            while j < len(content) and content[j] in ' \t\n':
                j += 1

            if j < len(content) and content[j] == '{':
                brace_count = 1
                k = j + 1
                while k < len(content) and brace_count > 0:
                    if content[k] == '{':
                        brace_count += 1
                    elif content[k] == '}':
                        brace_count -= 1
                    k += 1
                i = k
                continue

        result.append(content[i])
        i += 1

    return ''.join(result)


def extract_beamer_theme(preamble: str) -> dict:
    """Extract theme colors and settings from Beamer preamble."""
    style = DEFAULT_STYLE.copy()

    # Look for usetheme
    theme_match = re.search(r'\\usetheme\{([^}]+)\}', preamble)
    if theme_match:
        theme = theme_match.group(1).lower()
        # Madrid theme has dark blue titles
        if theme == 'madrid':
            style['title_color'] = '0.0,0.27,0.53'  # Madrid blue

    # Look for usecolortheme
    color_match = re.search(r'\\usecolortheme\{([^}]+)\}', preamble)
    if color_match:
        color_theme = color_match.group(1).lower()
        # Could add more color themes here

    return style


def sanitize_beamer_content(content: str) -> str:
    """Remove or convert Beamer-specific commands for standalone rendering."""
    # Remove columns environment
    content = re.sub(r'\\begin\{columns\}.*?\\end\{columns\}', '', content, flags=re.DOTALL)
    content = re.sub(r'\\column\{[^}]*\}', '', content)

    # Remove fbox and parbox
    content = remove_nested_braces(content, 'fbox')
    content = remove_nested_braces(content, 'parbox')

    # Clean center environments
    def clean_center(match):
        inner = match.group(1)
        if '\\parbox' in inner or '\\fbox' in inner:
            return ''
        return f'\\begin{{center}}{inner}\\end{{center}}'

    content = re.sub(r'\\begin\{center\}(.*?)\\end\{center\}', clean_center, content, flags=re.DOTALL)

    # Remove Beamer commands
    beamer_commands = [
        r'\\pause', r'\\onslide<[^>]*>', r'\\only<[^>]*>',
        r'\\visible<[^>]*>', r'\\invisible<[^>]*>', r'\\uncover<[^>]*>',
        r'\\alert<[^>]*>\{[^}]*\}', r'\\alert\{',
        r'\\structure\{[^}]*\}', r'\\titlepage', r'\\maketitle',
    ]
    for cmd in beamer_commands:
        content = re.sub(cmd, '', content)

    # Remove spacing commands
    content = re.sub(r'\\vfill', '', content)
    content = re.sub(r'\\vspace\{[^}]*\}', '\n', content)
    content = re.sub(r'\\hspace\{[^}]*\}', ' ', content)

    # Clean whitespace
    content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
    content = content.strip()

    return content if content and not content.isspace() else ''


def create_styled_document(content: str, preamble: str = "",
                           style: dict = None, content_type: str = "text") -> str:
    """Create a LaTeX document with consistent Beamer-like styling.

    Args:
        content: The LaTeX content
        preamble: Original Beamer preamble
        style: Style dictionary
        content_type: "text", "math", or "itemize"
    """
    if style is None:
        style = extract_beamer_theme(preamble)

    # Sanitize non-math content
    if content_type == "text":
        content = sanitize_beamer_content(content)
        if not content:
            return ""

    # Build document with consistent styling
    doc = f"""\\documentclass[{style['font_size']}]{{article}}
\\usepackage[paperwidth={style['text_width']},paperheight=20cm,margin=0.3cm]{{geometry}}
\\usepackage{{amsmath,amssymb,amsfonts}}
\\usepackage{{xcolor}}
\\usepackage{{helvet}}
\\usepackage{{enumitem}}
\\renewcommand{{\\familydefault}}{{\\sfdefault}}

% Match Beamer styling
\\definecolor{{beamerblue}}{{rgb}}{{{style['title_color']}}}
\\setlength{{\\parindent}}{{0pt}}
\\setlength{{\\parskip}}{{0.5em}}

% Beamer-like itemize
\\setlist[itemize]{{leftmargin=1.5em,itemsep=0.3em,parsep=0pt}}
\\setlist[enumerate]{{leftmargin=1.5em,itemsep=0.3em,parsep=0pt}}

% Custom bullet
\\renewcommand{{\\labelitemi}}{{\\textcolor{{beamerblue}}{{$\\blacktriangleright$}}}}
\\renewcommand{{\\labelenumi}}{{\\textcolor{{beamerblue}}{{\\arabic{{enumi}}.}}}}

"""

    # Add packages from original preamble
    if preamble:
        for line in preamble.split('\n'):
            if r'\usepackage' in line and 'beamer' not in line.lower():
                if 'geometry' not in line:  # Don't override our geometry
                    doc += line + '\n'

    doc += """
\\begin{document}
\\pagestyle{empty}
"""
    doc += content
    doc += """
\\end{document}
"""
    return doc


def render_latex_to_image(
    content: str,
    output_path: str,
    preamble: str = "",
    content_type: str = "text",
    style: dict = None,
    dpi: int = 400
) -> bool:
    """Render LaTeX content to a PNG image.

    Args:
        content: LaTeX content
        output_path: Path to save PNG
        preamble: Original document preamble
        content_type: "text", "math", or "itemize"
        style: Style dictionary
        dpi: Resolution (default 400 for crisp output)

    Returns:
        True if successful
    """
    doc = create_styled_document(content, preamble, style, content_type)
    if not doc:
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        tex_path = Path(tmpdir) / "content.tex"
        pdf_path = Path(tmpdir) / "content.pdf"

        tex_path.write_text(doc)

        try:
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", tmpdir, str(tex_path)],
                capture_output=True,
                text=True,
                timeout=30
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

        if not pdf_path.exists():
            return False

        try:
            pdf_doc = fitz.open(str(pdf_path))
            page = pdf_doc[0]

            zoom = dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            # Crop vertically only to remove excess height
            # Keep full width for consistent sizing when scaled
            content_rect = page.rect

            blocks = page.get_text("blocks")
            if blocks:
                min_y = min(b[1] for b in blocks)
                max_y = max(b[3] for b in blocks)

                # Add vertical margin
                margin = 8
                content_rect = fitz.Rect(
                    0,  # Keep full width from left
                    max(0, min_y - margin),
                    page.rect.width,  # Keep full width to right
                    min(page.rect.height, max_y + margin)
                )

            pix = page.get_pixmap(matrix=mat, clip=content_rect, alpha=False)
            pix.save(output_path)
            pdf_doc.close()
            return True
        except Exception:
            return False


def render_align_cumulative(
    lines: List[str],
    output_dir: str,
    preamble: str = "",
    env_name: str = "align*",
    style: dict = None,
    dpi: int = 400
) -> List[str]:
    """Render cumulative versions of an align environment."""
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    if style is None:
        style = extract_beamer_theme(preamble)

    for i in range(1, len(lines) + 1):
        cumulative_lines = lines[:i]
        content = f"\\begin{{{env_name}}}\n"
        content += " \\\\\n".join(cumulative_lines)
        content += f"\n\\end{{{env_name}}}"

        output_path = os.path.join(output_dir, f"step_{i:03d}.png")

        if render_latex_to_image(content, output_path, preamble, "math", style, dpi):
            image_paths.append(output_path)

    return image_paths


def render_itemize_cumulative(
    items: List[str],
    output_dir: str,
    preamble: str = "",
    env_name: str = "itemize",
    style: dict = None,
    dpi: int = 400
) -> List[str]:
    """Render cumulative versions of an itemize/enumerate environment."""
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    if style is None:
        style = extract_beamer_theme(preamble)

    for i in range(1, len(items) + 1):
        cumulative_items = items[:i]
        content = f"\\begin{{{env_name}}}\n"
        for item in cumulative_items:
            content += f"\\item {item}\n"
        content += f"\\end{{{env_name}}}"

        output_path = os.path.join(output_dir, f"step_{i:03d}.png")

        if render_latex_to_image(content, output_path, preamble, "itemize", style, dpi):
            image_paths.append(output_path)

    return image_paths


def render_text_block(
    content: str,
    output_path: str,
    preamble: str = "",
    style: dict = None,
    dpi: int = 400
) -> bool:
    """Render a text block to an image."""
    if style is None:
        style = extract_beamer_theme(preamble)

    return render_latex_to_image(content, output_path, preamble, "text", style, dpi)


def render_text_cumulative(
    paragraphs: List[str],
    output_dir: str,
    preamble: str = "",
    style: dict = None,
    dpi: int = 400
) -> List[str]:
    """Render cumulative versions of text paragraphs.

    Each step shows one more paragraph than the previous.
    """
    os.makedirs(output_dir, exist_ok=True)
    image_paths = []

    if style is None:
        style = extract_beamer_theme(preamble)

    for i in range(1, len(paragraphs) + 1):
        cumulative = paragraphs[:i]
        content = '\n\n'.join(cumulative)

        output_path = os.path.join(output_dir, f"step_{i:03d}.png")

        if render_latex_to_image(content, output_path, preamble, "text", style, dpi):
            image_paths.append(output_path)

    return image_paths


def compile_beamer_to_pdf(tex_path: str, output_dir: str) -> Optional[str]:
    """Compile a Beamer document to PDF.

    Args:
        tex_path: Path to the .tex file
        output_dir: Directory to store output

    Returns:
        Path to the generated PDF, or None if failed
    """
    import shutil

    tex_path = Path(tex_path)
    os.makedirs(output_dir, exist_ok=True)

    # Copy tex file to output dir
    work_tex = Path(output_dir) / tex_path.name
    shutil.copy(tex_path, work_tex)

    try:
        # Run pdflatex twice for proper references
        for _ in range(2):
            result = subprocess.run(
                ["pdflatex", "-interaction=nonstopmode", "-output-directory", output_dir, str(work_tex)],
                capture_output=True,
                text=True,
                timeout=120
            )

        pdf_path = work_tex.with_suffix('.pdf')
        if pdf_path.exists():
            return str(pdf_path)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def extract_frame_from_pdf(
    pdf_path: str,
    frame_number: int,
    output_path: str,
    dpi: int = 400
) -> bool:
    """Extract a specific frame from a Beamer PDF as an image.

    Args:
        pdf_path: Path to the Beamer PDF
        frame_number: 1-indexed frame number
        output_path: Where to save the PNG
        dpi: Resolution

    Returns:
        True if successful
    """
    try:
        pdf_doc = fitz.open(pdf_path)
        if frame_number < 1 or frame_number > len(pdf_doc):
            pdf_doc.close()
            return False

        page = pdf_doc[frame_number - 1]

        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)

        pix.save(output_path)
        pdf_doc.close()
        return True
    except Exception:
        return False
