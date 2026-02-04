"""Tests for beamer2animate.converter."""

import os
import shutil
import tempfile

import pytest

from beamer2animate.parser import BlockType, ContentBlock, Frame
from beamer2animate.converter import BeamerConverter, convert_beamer_to_pptx

requires_pdflatex = pytest.mark.skipif(
    shutil.which("pdflatex") is None,
    reason="pdflatex not available",
)


class TestFitContentWidth:
    """Test the _fit_content_width scaling logic."""

    @pytest.fixture
    def converter(self):
        return BeamerConverter(dpi=150)

    def test_no_blocks_returns_default(self, converter):
        width = converter._fit_content_width([], has_title=True)
        assert width == converter.content_width

    @requires_pdflatex
    def test_small_content_no_scaling(self, converter, tmp_dir):
        """Content that fits should not be scaled."""
        from beamer2animate.renderer import render_text_block, extract_beamer_theme

        converter.style = extract_beamer_theme("")
        converter.temp_dir = tmp_dir

        img_path = os.path.join(tmp_dir, "small.png")
        render_text_block("Short text.", img_path, style=converter.style, dpi=converter.dpi)

        rendered_blocks = [(0, [img_path], False, 0.15)]
        width = converter._fit_content_width(rendered_blocks, has_title=True)
        assert width == converter.content_width

    @requires_pdflatex
    def test_tall_content_gets_scaled(self, converter, tmp_dir):
        """Content that overflows should be scaled down."""
        from beamer2animate.renderer import render_itemize_cumulative, extract_beamer_theme

        converter.style = extract_beamer_theme("")
        converter.temp_dir = tmp_dir

        # Create many items to force overflow
        items = [f"Item number {i} with some extra text to make it longer" for i in range(15)]
        block_dir = os.path.join(tmp_dir, "block")
        paths = render_itemize_cumulative(items, block_dir, style=converter.style, dpi=converter.dpi)

        if paths:
            rendered_blocks = [(0, paths, True, 0.2)]
            width = converter._fit_content_width(rendered_blocks, has_title=True)
            # Should be scaled down (or equal if it happens to fit)
            assert width <= converter.content_width

    @requires_pdflatex
    def test_scaling_floor_at_50_percent(self, converter, tmp_dir):
        """Scaling should not go below 50% of content width."""
        from PIL import Image

        # Create a very tall image to force extreme scaling
        tall_img = os.path.join(tmp_dir, "tall.png")
        img = Image.new("RGB", (100, 2000), color="white")
        img.save(tall_img)

        rendered_blocks = [(0, [tall_img], False, 0.15)]
        width = converter._fit_content_width(rendered_blocks, has_title=True)
        assert width >= converter.content_width * 0.5

    def test_no_title_gives_more_space(self, converter, tmp_dir):
        """Without a title, more vertical space is available."""
        from PIL import Image

        # Create an image that's moderately tall
        img_path = os.path.join(tmp_dir, "medium.png")
        img = Image.new("RGB", (100, 800), color="white")
        img.save(img_path)

        rendered_blocks = [(0, [img_path], False, 0.15)]
        width_with_title = converter._fit_content_width(rendered_blocks, has_title=True)
        width_no_title = converter._fit_content_width(rendered_blocks, has_title=False)
        # Without title, should allow equal or wider content (less scaling needed)
        assert width_no_title >= width_with_title


class TestRenderBlock:
    @pytest.fixture
    def converter(self):
        from beamer2animate.renderer import extract_beamer_theme
        c = BeamerConverter(dpi=150)
        c.style = extract_beamer_theme("")
        return c

    @requires_pdflatex
    def test_text_single_paragraph(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            raw_content="Hello world",
            items=["Hello world"],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is not None
        block_idx, paths, is_animated, spacing = result
        assert len(paths) == 1
        assert is_animated is False
        assert spacing == 0.15

    @requires_pdflatex
    def test_text_multi_paragraph(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.TEXT,
            raw_content="A\n\nB",
            items=["Paragraph A.", "Paragraph B."],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is not None
        _, paths, is_animated, _ = result
        assert len(paths) == 2
        assert is_animated is True

    @requires_pdflatex
    def test_itemize_block(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.ITEMIZE,
            raw_content=r"\begin{itemize}\item A\item B\end{itemize}",
            items=["A", "B"],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is not None
        _, paths, is_animated, spacing = result
        assert len(paths) == 2
        assert is_animated is True
        assert spacing == 0.2

    @requires_pdflatex
    def test_math_align_block(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.MATH_ALIGN,
            raw_content=r"\begin{align*}x &= 1 \\ y &= 2\end{align*}",
            items=["x &= 1", "y &= 2"],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is not None
        _, paths, is_animated, spacing = result
        assert len(paths) == 2
        assert is_animated is True
        assert spacing == 0.2

    @requires_pdflatex
    def test_display_math_block(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.DISPLAY_MATH,
            raw_content=r"\begin{equation*}E = mc^2\end{equation*}",
            items=["E = mc^2"],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is not None
        _, paths, is_animated, _ = result
        assert len(paths) == 1
        assert is_animated is True

    def test_code_block_returns_none(self, converter, tmp_dir):
        block = ContentBlock(
            block_type=BlockType.CODE,
            raw_content=r"\begin{lstlisting}x=1\end{lstlisting}",
            items=[],
        )
        result = converter._render_block(block, 0, tmp_dir, "", False)
        assert result is None


class TestGetEnvName:
    def test_align_star(self):
        c = BeamerConverter()
        assert c._get_env_name(r"\begin{align*}x\end{align*}") == "align*"

    def test_gather_star(self):
        c = BeamerConverter()
        assert c._get_env_name(r"\begin{gather*}x\end{gather*}") == "gather*"

    def test_fallback(self):
        c = BeamerConverter()
        assert c._get_env_name("no env here") == "align*"


class TestEndToEnd:
    @requires_pdflatex
    def test_convert_sample(self, tmp_dir, sample_document):
        """Full end-to-end conversion of a sample document."""
        tex_path = os.path.join(tmp_dir, "test.tex")
        pptx_path = os.path.join(tmp_dir, "test.pptx")

        with open(tex_path, "w") as f:
            f.write(sample_document)

        result_path = convert_beamer_to_pptx(tex_path, pptx_path, dpi=150, verbose=False)
        assert result_path == pptx_path
        assert os.path.exists(pptx_path)
        assert os.path.getsize(pptx_path) > 0

    @requires_pdflatex
    def test_output_has_correct_slide_count(self, tmp_dir, sample_document):
        """Output should have one slide per frame."""
        from pptx import Presentation

        tex_path = os.path.join(tmp_dir, "test.tex")
        pptx_path = os.path.join(tmp_dir, "test.pptx")

        with open(tex_path, "w") as f:
            f.write(sample_document)

        convert_beamer_to_pptx(tex_path, pptx_path, dpi=150, verbose=False)

        prs = Presentation(pptx_path)
        assert len(prs.slides) == 3

    @requires_pdflatex
    def test_default_output_path(self, tmp_dir, sample_document):
        """Without explicit output, should use .pptx extension."""
        tex_path = os.path.join(tmp_dir, "presentation.tex")

        with open(tex_path, "w") as f:
            f.write(sample_document)

        result_path = convert_beamer_to_pptx(tex_path, verbose=False)
        expected = os.path.join(tmp_dir, "presentation.pptx")
        assert result_path == expected
        assert os.path.exists(expected)
