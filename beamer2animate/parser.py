"""Parse Beamer .tex files and extract frames with animation points."""

import re
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum


class BlockType(Enum):
    TEXT = "text"
    MATH_ALIGN = "math_align"
    ITEMIZE = "itemize"
    ENUMERATE = "enumerate"
    CODE = "code"  # lstlisting environments
    DISPLAY_MATH = "display_math"  # \[ \] or equation without lines


@dataclass
class ContentBlock:
    """A block of content within a frame."""
    block_type: BlockType
    raw_content: str
    # For animatable blocks, these are the individual items/lines
    items: List[str] = field(default_factory=list)
    # Preamble content (e.g., text before an align environment)
    preamble: str = ""


@dataclass
class Frame:
    """A single Beamer frame."""
    title: str
    raw_content: str
    blocks: List[ContentBlock] = field(default_factory=list)
    frame_options: str = ""  # e.g., [fragile]
    has_code: bool = False  # True if frame contains lstlisting


@dataclass
class BeamerDocument:
    """Parsed Beamer document."""
    preamble: str
    frames: List[Frame] = field(default_factory=list)
    title: str = ""
    author: str = ""


def extract_preamble(tex_content: str) -> str:
    """Extract the document preamble (everything before \\begin{document})."""
    match = re.search(r'^(.*?)\\begin\{document\}', tex_content, re.DOTALL)
    if match:
        return match.group(1)
    return ""


def extract_frames(tex_content: str) -> List[tuple]:
    """Extract all frames from the document."""
    frame_pattern = r'\\begin\{frame\}(?:\[([^\]]*)\])?(?:\{([^}]*)\})?\s*(.*?)\\end\{frame\}'
    matches = re.findall(frame_pattern, tex_content, re.DOTALL)

    frames = []
    for options, title, content in matches:
        frames.append((options or "", title or "", content.strip()))

    return frames


def split_align_lines(align_content: str) -> List[str]:
    """Split an align environment into individual lines."""
    content = align_content.strip()
    lines = re.split(r'\\\\(?:\s*\[[^\]]*\])?\s*', content)
    return [line.strip() for line in lines if line.strip()]


def split_itemize_items(itemize_content: str) -> List[str]:
    """Split an itemize/enumerate environment into individual items."""
    parts = re.split(r'\\item\s*', itemize_content)
    return [part.strip() for part in parts if part.strip()]


def split_text_into_paragraphs(text: str) -> List[str]:
    """Split text content into animatable paragraphs/lines.

    Each of these becomes a separate animation step:
    - Lines starting with \textbf{...}
    - Lines with inline math like $...$
    - Regular paragraphs separated by blank lines or \vspace
    """
    # First, split on vspace commands
    text = re.sub(r'\\vspace\{[^}]*\}', '\n\n', text)

    # Split on double newlines (paragraph breaks)
    paragraphs = re.split(r'\n\s*\n', text)

    result = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Check if this paragraph has multiple \textbf lines that should be separate
        # Pattern: starts with \textbf and contains content
        lines = para.split('\n')
        current_chunk = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # If line starts with \textbf, it's a new animation point
            if line.startswith('\\textbf{') and current_chunk:
                result.append('\n'.join(current_chunk))
                current_chunk = [line]
            else:
                current_chunk.append(line)

        if current_chunk:
            result.append('\n'.join(current_chunk))

    return result


def parse_frame_content(content: str) -> List[ContentBlock]:
    """Parse frame content into blocks, identifying animation points."""
    blocks = []

    # Check for lstlisting (code) - these should be handled specially
    has_code = '\\begin{lstlisting}' in content

    # Pattern for all special environments
    # Order matters: check lstlisting first, then math, then lists
    env_pattern = r'\\begin\{(lstlisting|align\*?|gather\*?|equation\*?|itemize|enumerate)\}(.*?)\\end\{\1\}'

    last_end = 0
    for match in re.finditer(env_pattern, content, re.DOTALL):
        # Add any text before this environment
        text_before = content[last_end:match.start()].strip()
        if text_before:
            # Split text into paragraphs for animation
            paragraphs = split_text_into_paragraphs(text_before)
            if len(paragraphs) > 1:
                # Multiple paragraphs - animate each separately
                blocks.append(ContentBlock(
                    block_type=BlockType.TEXT,
                    raw_content=text_before,
                    items=paragraphs
                ))
            elif paragraphs:
                # Single paragraph - still make it a block
                blocks.append(ContentBlock(
                    block_type=BlockType.TEXT,
                    raw_content=text_before,
                    items=paragraphs
                ))

        env_name = match.group(1)
        env_content = match.group(2).strip()
        full_env = match.group(0)

        if env_name == 'lstlisting':
            # Code block - don't try to animate, just mark it
            blocks.append(ContentBlock(
                block_type=BlockType.CODE,
                raw_content=full_env,
                items=[]  # No animation for code
            ))
        elif env_name in ('align', 'align*', 'gather', 'gather*'):
            lines = split_align_lines(env_content)
            blocks.append(ContentBlock(
                block_type=BlockType.MATH_ALIGN,
                raw_content=full_env,
                items=lines
            ))
        elif env_name in ('equation', 'equation*'):
            # Single equation - one animation step
            blocks.append(ContentBlock(
                block_type=BlockType.DISPLAY_MATH,
                raw_content=full_env,
                items=[env_content]
            ))
        elif env_name == 'itemize':
            items = split_itemize_items(env_content)
            blocks.append(ContentBlock(
                block_type=BlockType.ITEMIZE,
                raw_content=full_env,
                items=items
            ))
        elif env_name == 'enumerate':
            items = split_itemize_items(env_content)
            blocks.append(ContentBlock(
                block_type=BlockType.ENUMERATE,
                raw_content=full_env,
                items=items
            ))

        last_end = match.end()

    # Add any remaining text
    text_after = content[last_end:].strip()
    if text_after:
        paragraphs = split_text_into_paragraphs(text_after)
        if paragraphs:
            blocks.append(ContentBlock(
                block_type=BlockType.TEXT,
                raw_content=text_after,
                items=paragraphs
            ))

    return blocks


def parse_beamer(tex_content: str) -> BeamerDocument:
    """Parse a complete Beamer document."""
    preamble = extract_preamble(tex_content)

    title_match = re.search(r'\\title\{([^}]*)\}', preamble)
    author_match = re.search(r'\\author\{([^}]*)\}', preamble)

    doc = BeamerDocument(
        preamble=preamble,
        title=title_match.group(1) if title_match else "",
        author=author_match.group(1) if author_match else ""
    )

    raw_frames = extract_frames(tex_content)

    for options, title, content in raw_frames:
        has_code = '\\begin{lstlisting}' in content
        frame = Frame(
            title=title,
            raw_content=content,
            frame_options=options,
            blocks=parse_frame_content(content),
            has_code=has_code
        )
        doc.frames.append(frame)

    return doc
