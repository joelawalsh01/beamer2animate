"""Tests for beamer2animate.renderer."""

import os
import shutil
import subprocess

import pytest

from beamer2animate.renderer import (
    extract_beamer_theme,
    sanitize_beamer_content,
    create_styled_document,
    render_latex_to_image,
    render_align_cumulative,
    render_itemize_cumulative,
    render_text_cumulative,
    render_text_block,
    remove_nested_braces,
)

requires_pdflatex = pytest.mark.skipif(
    shutil.which("pdflatex") is None,
    reason="pdflatex not available",
)


class TestExtractBeamerTheme:
    def test_default_style(self):
        style = extract_beamer_theme("")
        assert style["font_size"] == "11pt"
        assert style["text_width"] == "12cm"
        assert style["title_color"] == "0.2,0.2,0.6"

    def test_madrid_theme(self):
        preamble = r"\usetheme{Madrid}"
        style = extract_beamer_theme(preamble)
        assert style["title_color"] == "0.0,0.27,0.53"

    def test_unknown_theme(self):
        style = extract_beamer_theme(r"\usetheme{SomeOther}")
        # Falls back to default
        assert style["title_color"] == "0.2,0.2,0.6"


class TestRemoveNestedBraces:
    def test_fbox(self):
        result = remove_nested_braces(r"before \fbox{content} after", "fbox")
        assert result == "before  after"

    def test_nested(self):
        result = remove_nested_braces(r"\fbox{outer {inner} end}", "fbox")
        assert result == ""

    def test_no_match(self):
        result = remove_nested_braces("no commands here", "fbox")
        assert result == "no commands here"


class TestSanitizeBeamerContent:
    def test_removes_pause(self):
        result = sanitize_beamer_content(r"before \pause after")
        assert r"\pause" not in result
        assert "before" in result
        assert "after" in result

    def test_removes_columns(self):
        content = r"""
\begin{columns}
\column{0.5\textwidth}
stuff
\end{columns}"""
        result = sanitize_beamer_content(content)
        assert r"\begin{columns}" not in result

    def test_removes_vfill(self):
        result = sanitize_beamer_content(r"before \vfill after")
        assert r"\vfill" not in result

    def test_removes_vspace(self):
        result = sanitize_beamer_content(r"before \vspace{1em} after")
        assert r"\vspace" not in result

    def test_removes_onslide(self):
        result = sanitize_beamer_content(r"text \onslide<2> more")
        assert r"\onslide" not in result

    def test_removes_titlepage(self):
        result = sanitize_beamer_content(r"\titlepage")
        assert result == ""

    def test_empty_returns_empty(self):
        assert sanitize_beamer_content("") == ""
        assert sanitize_beamer_content("   ") == ""


class TestCreateStyledDocument:
    def test_basic_text(self):
        doc = create_styled_document("Hello world", content_type="text")
        assert r"\documentclass" in doc
        assert r"\begin{document}" in doc
        assert "Hello world" in doc
        assert r"\end{document}" in doc

    def test_geometry_settings(self):
        doc = create_styled_document("test", content_type="text")
        assert "paperwidth=12cm" in doc
        assert "paperheight=20cm" in doc
        assert "margin=0.3cm" in doc

    def test_math_content_not_sanitized(self):
        content = r"\begin{align*} x &= 1 \end{align*}"
        doc = create_styled_document(content, content_type="math")
        assert r"\begin{align*}" in doc

    def test_text_content_sanitized(self):
        doc = create_styled_document(r"text \pause more", content_type="text")
        assert r"\pause" not in doc

    def test_empty_text_after_sanitize(self):
        doc = create_styled_document(r"\titlepage", content_type="text")
        assert doc == ""

    def test_includes_preamble_packages(self):
        preamble = r"\usepackage{tikz}"
        doc = create_styled_document("test", preamble=preamble, content_type="text")
        assert r"\usepackage{tikz}" in doc

    def test_excludes_geometry_from_preamble(self):
        preamble = r"\usepackage[margin=1in]{geometry}"
        doc = create_styled_document("test", preamble=preamble, content_type="text")
        # Should not have duplicate geometry
        assert doc.count("geometry") == 1


class TestRenderLatexToImage:
    @requires_pdflatex
    def test_basic_render(self, tmp_dir):
        out = os.path.join(tmp_dir, "test.png")
        result = render_latex_to_image("Hello world", out, content_type="text")
        assert result is True
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    @requires_pdflatex
    def test_math_render(self, tmp_dir):
        out = os.path.join(tmp_dir, "math.png")
        content = r"\begin{align*} x &= 1 \end{align*}"
        result = render_latex_to_image(content, out, content_type="math")
        assert result is True
        assert os.path.exists(out)

    @requires_pdflatex
    def test_empty_content_returns_false(self, tmp_dir):
        out = os.path.join(tmp_dir, "empty.png")
        result = render_latex_to_image(r"\titlepage", out, content_type="text")
        assert result is False

    @requires_pdflatex
    def test_dpi_affects_size(self, tmp_dir):
        from PIL import Image

        out_lo = os.path.join(tmp_dir, "lo.png")
        out_hi = os.path.join(tmp_dir, "hi.png")
        render_latex_to_image("Test text", out_lo, content_type="text", dpi=150)
        render_latex_to_image("Test text", out_hi, content_type="text", dpi=400)

        with Image.open(out_lo) as lo, Image.open(out_hi) as hi:
            assert hi.width > lo.width
            assert hi.height > lo.height


class TestRenderCumulative:
    @requires_pdflatex
    def test_align_cumulative(self, tmp_dir):
        lines = ["x &= 1", "y &= 2", "z &= 3"]
        paths = render_align_cumulative(lines, tmp_dir)
        assert len(paths) == 3
        for p in paths:
            assert os.path.exists(p)

    @requires_pdflatex
    def test_align_cumulative_images_grow(self, tmp_dir):
        from PIL import Image

        lines = ["x &= 1", "y &= 2", "z &= 3"]
        paths = render_align_cumulative(lines, tmp_dir)
        heights = []
        for p in paths:
            with Image.open(p) as img:
                heights.append(img.height)
        # Each cumulative image should be at least as tall as the previous
        assert heights[0] <= heights[1] <= heights[2]

    @requires_pdflatex
    def test_itemize_cumulative(self, tmp_dir):
        items = ["First", "Second", "Third"]
        paths = render_itemize_cumulative(items, tmp_dir)
        assert len(paths) == 3
        for p in paths:
            assert os.path.exists(p)

    @requires_pdflatex
    def test_text_cumulative(self, tmp_dir):
        paragraphs = ["First paragraph.", "Second paragraph."]
        paths = render_text_cumulative(paragraphs, tmp_dir)
        assert len(paths) == 2
        for p in paths:
            assert os.path.exists(p)

    @requires_pdflatex
    def test_text_block(self, tmp_dir):
        out = os.path.join(tmp_dir, "block.png")
        result = render_text_block("A single block of text.", out)
        assert result is True
        assert os.path.exists(out)
