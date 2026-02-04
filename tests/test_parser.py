"""Tests for beamer2animate.parser."""

from beamer2animate.parser import (
    extract_preamble,
    extract_frames,
    split_align_lines,
    split_itemize_items,
    split_text_into_paragraphs,
    parse_frame_content,
    parse_beamer,
    BlockType,
)


class TestExtractPreamble:
    def test_basic(self):
        tex = r"""\documentclass{beamer}
\usepackage{amsmath}
\begin{document}
hello
\end{document}"""
        preamble = extract_preamble(tex)
        assert r"\documentclass{beamer}" in preamble
        assert r"\usepackage{amsmath}" in preamble
        assert r"\begin{document}" not in preamble

    def test_no_document(self):
        assert extract_preamble("just text") == ""


class TestExtractFrames:
    def test_single_frame(self):
        tex = r"""
\begin{document}
\begin{frame}{My Title}
content here
\end{frame}
\end{document}"""
        frames = extract_frames(tex)
        assert len(frames) == 1
        assert frames[0][1] == "My Title"
        assert "content here" in frames[0][2]

    def test_frame_with_options(self):
        tex = r"""
\begin{frame}[fragile]{Code Slide}
some code
\end{frame}"""
        frames = extract_frames(tex)
        assert len(frames) == 1
        assert frames[0][0] == "fragile"
        assert frames[0][1] == "Code Slide"

    def test_frame_no_title(self):
        tex = r"""
\begin{frame}
untitled content
\end{frame}"""
        frames = extract_frames(tex)
        assert len(frames) == 1
        assert frames[0][1] == ""

    def test_multiple_frames(self):
        tex = r"""
\begin{frame}{A}
alpha
\end{frame}
\begin{frame}{B}
beta
\end{frame}
\begin{frame}{C}
gamma
\end{frame}"""
        frames = extract_frames(tex)
        assert len(frames) == 3
        assert [f[1] for f in frames] == ["A", "B", "C"]


class TestSplitAlignLines:
    def test_basic(self):
        content = r"x &= 1 \\ y &= 2 \\ z &= 3"
        lines = split_align_lines(content)
        assert len(lines) == 3
        assert lines[0] == "x &= 1"
        assert lines[1] == "y &= 2"
        assert lines[2] == "z &= 3"

    def test_with_optional_spacing(self):
        content = r"a &= 1 \\[5pt] b &= 2"
        lines = split_align_lines(content)
        assert len(lines) == 2

    def test_single_line(self):
        lines = split_align_lines("x = 1")
        assert len(lines) == 1
        assert lines[0] == "x = 1"


class TestSplitItemizeItems:
    def test_basic(self):
        content = r"\item First \item Second \item Third"
        items = split_itemize_items(content)
        assert len(items) == 3
        assert items[0] == "First"
        assert items[1] == "Second"
        assert items[2] == "Third"

    def test_multiline_items(self):
        content = r"""
\item First item
with more text
\item Second item
"""
        items = split_itemize_items(content)
        assert len(items) == 2
        assert "First item" in items[0]
        assert "Second item" in items[1]


class TestSplitTextIntoParagraphs:
    def test_double_newline(self):
        text = "First paragraph.\n\nSecond paragraph."
        paras = split_text_into_paragraphs(text)
        assert len(paras) == 2
        assert paras[0] == "First paragraph."
        assert paras[1] == "Second paragraph."

    def test_textbf_split(self):
        text = r"""\textbf{Heading 1}
Some detail.
\textbf{Heading 2}
More detail."""
        paras = split_text_into_paragraphs(text)
        assert len(paras) == 2
        assert r"\textbf{Heading 1}" in paras[0]
        assert r"\textbf{Heading 2}" in paras[1]

    def test_vspace_becomes_break(self):
        text = r"Before\vspace{1em}After"
        paras = split_text_into_paragraphs(text)
        assert len(paras) == 2

    def test_single_paragraph(self):
        paras = split_text_into_paragraphs("Just one paragraph.")
        assert len(paras) == 1

    def test_empty(self):
        assert split_text_into_paragraphs("") == []
        assert split_text_into_paragraphs("   ") == []


class TestParseFrameContent:
    def test_itemize(self):
        content = r"""
\begin{itemize}
\item A
\item B
\end{itemize}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.ITEMIZE
        assert len(blocks[0].items) == 2

    def test_enumerate(self):
        content = r"""
\begin{enumerate}
\item First
\item Second
\end{enumerate}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.ENUMERATE
        assert len(blocks[0].items) == 2

    def test_align(self):
        content = r"""
\begin{align*}
x &= 1 \\
y &= 2
\end{align*}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.MATH_ALIGN
        assert len(blocks[0].items) == 2

    def test_equation(self):
        content = r"""
\begin{equation*}
E = mc^2
\end{equation*}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.DISPLAY_MATH

    def test_lstlisting(self):
        content = r"""
\begin{lstlisting}
print("hello")
\end{lstlisting}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 1
        assert blocks[0].block_type == BlockType.CODE

    def test_text_before_env(self):
        content = r"""Some intro text.

\begin{itemize}
\item A
\end{itemize}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 2
        assert blocks[0].block_type == BlockType.TEXT
        assert blocks[1].block_type == BlockType.ITEMIZE

    def test_text_after_env(self):
        content = r"""
\begin{itemize}
\item A
\end{itemize}
Some trailing text."""
        blocks = parse_frame_content(content)
        assert len(blocks) == 2
        assert blocks[0].block_type == BlockType.ITEMIZE
        assert blocks[1].block_type == BlockType.TEXT

    def test_mixed_blocks(self):
        content = r"""Intro text.

\begin{align*}
x &= 1
\end{align*}

\begin{itemize}
\item A
\item B
\end{itemize}"""
        blocks = parse_frame_content(content)
        assert len(blocks) == 3
        assert blocks[0].block_type == BlockType.TEXT
        assert blocks[1].block_type == BlockType.MATH_ALIGN
        assert blocks[2].block_type == BlockType.ITEMIZE

    def test_empty_content(self):
        blocks = parse_frame_content("")
        assert len(blocks) == 0


class TestParseBeamer:
    def test_full_document(self, sample_document):
        doc = parse_beamer(sample_document)
        assert doc.title == "Test Presentation"
        assert doc.author == "Test Author"
        assert len(doc.frames) == 3

    def test_frame_titles(self, sample_document):
        doc = parse_beamer(sample_document)
        assert doc.frames[0].title == "First Slide"
        assert doc.frames[1].title == "Math Slide"
        assert doc.frames[2].title == "Text Slide"

    def test_frame_block_types(self, sample_document):
        doc = parse_beamer(sample_document)
        assert doc.frames[0].blocks[0].block_type == BlockType.ITEMIZE
        assert doc.frames[1].blocks[0].block_type == BlockType.MATH_ALIGN
        assert doc.frames[2].blocks[0].block_type == BlockType.TEXT

    def test_has_code_flag(self):
        tex = r"""
\documentclass{beamer}
\begin{document}
\begin{frame}[fragile]{Code}
\begin{lstlisting}
x = 1
\end{lstlisting}
\end{frame}
\begin{frame}{Normal}
hello
\end{frame}
\end{document}"""
        doc = parse_beamer(tex)
        assert doc.frames[0].has_code is True
        assert doc.frames[1].has_code is False

    def test_preamble_extraction(self, sample_document):
        doc = parse_beamer(sample_document)
        assert r"\usetheme{Madrid}" in doc.preamble
        assert r"\usepackage{amsmath}" in doc.preamble
