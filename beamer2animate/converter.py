"""Main converter: Beamer to animated PowerPoint."""

import os
import tempfile
from pathlib import Path
from typing import Optional

from .parser import parse_beamer, Frame, ContentBlock, BlockType
from .renderer import (
    render_align_cumulative,
    render_itemize_cumulative,
    render_text_cumulative,
    render_text_block,
    render_latex_to_image,
    compile_beamer_to_pdf,
    extract_frame_from_pdf,
    extract_beamer_theme
)
from .pptx_builder import (
    create_presentation,
    add_slide,
    add_title_to_slide,
    add_image_to_slide,
    add_content_background,
    add_appear_animation,
    add_disappear_animation,
    save_presentation
)


class BeamerConverter:
    """Convert Beamer presentations to animated PowerPoint."""

    def __init__(self, dpi: int = 400):
        """Initialize the converter.

        Args:
            dpi: Resolution for rendered LaTeX images (higher = crisper)
        """
        self.dpi = dpi
        self.temp_dir = None
        self.beamer_pdf_path = None
        self.content_width = 10.0  # inches in PowerPoint

    def convert(self, tex_path: str, output_path: str, verbose: bool = True) -> bool:
        """Convert a Beamer .tex file to an animated PowerPoint.

        Args:
            tex_path: Path to the input .tex file
            output_path: Path for the output .pptx file
            verbose: Print progress messages

        Returns:
            True if successful
        """
        with open(tex_path, 'r', encoding='utf-8') as f:
            tex_content = f.read()

        if verbose:
            print("Parsing Beamer document...")
        doc = parse_beamer(tex_content)

        if verbose:
            print(f"Found {len(doc.frames)} frames")

        # Extract theme styling
        self.style = extract_beamer_theme(doc.preamble)

        # Create temp directory
        self.temp_dir = tempfile.mkdtemp(prefix="beamer2animate_")

        # Always compile the Beamer PDF for slide backgrounds (theme chrome)
        if verbose:
            print("Compiling Beamer document...")
        pdf_dir = os.path.join(self.temp_dir, "beamer_pdf")
        self.beamer_pdf_path = compile_beamer_to_pdf(tex_path, pdf_dir)
        if self.beamer_pdf_path and verbose:
            print("  Beamer PDF compiled successfully")
        elif verbose:
            print("  Warning: Could not compile Beamer PDF, slides will lack theme styling")

        # Create presentation
        prs = create_presentation()

        # Process each frame
        for frame_idx, frame in enumerate(doc.frames):
            if verbose:
                title_preview = frame.title[:40] + "..." if len(frame.title) > 40 else frame.title
                print(f"Processing frame {frame_idx + 1}: {title_preview or '(no title)'}")

            self._process_frame(prs, frame, frame_idx, doc.preamble, verbose)

        if verbose:
            print(f"Saving to {output_path}...")
        save_presentation(prs, output_path)

        if verbose:
            print("Done!")

        return True

    def _is_static_frame(self, frame: Frame) -> bool:
        """Check if this frame should be rendered as a static Beamer PDF page."""
        if frame.has_code:
            return True
        if '\\titlepage' in frame.raw_content or '\\maketitle' in frame.raw_content:
            return True
        return False

    def _process_frame(self, prs, frame: Frame, frame_idx: int, preamble: str, verbose: bool):
        """Process a single frame and add it to the presentation."""
        slide = add_slide(prs)

        # Add Beamer PDF page as background for theme styling (blue banners, etc.)
        has_bg = False
        if self.beamer_pdf_path:
            bg_path = os.path.join(self.temp_dir, f"bg_{frame_idx:03d}.png")
            if extract_frame_from_pdf(self.beamer_pdf_path, frame_idx + 1, bg_path, self.dpi):
                add_image_to_slide(slide, bg_path, left=0, top=0, width=13.333)
                has_bg = True

        # Static frames (title page, code): just the Beamer PDF background
        if self._is_static_frame(frame):
            if not has_bg and frame.title:
                add_title_to_slide(slide, frame.title)
            return

        # For animated frames: cover the content area with white so animated
        # content can appear on top, while the theme chrome stays visible
        if has_bg:
            add_content_background(slide)
        elif frame.title:
            add_title_to_slide(slide, frame.title)

        frame_dir = os.path.join(self.temp_dir, f"frame_{frame_idx:03d}")
        os.makedirs(frame_dir, exist_ok=True)

        # Pass 1: Render all blocks to images
        rendered_blocks = []
        for block_idx, block in enumerate(frame.blocks):
            block_dir = os.path.join(frame_dir, f"block_{block_idx:03d}")
            os.makedirs(block_dir, exist_ok=True)
            rendered = self._render_block(block, block_idx, block_dir, preamble, verbose)
            if rendered:
                rendered_blocks.append(rendered)

        # Pass 2: Compute content width, scaling down if content overflows
        content_width = self._fit_content_width(rendered_blocks, has_bg)

        # Pass 3: Place images on slide
        if has_bg:
            current_top = 0.88
            left_margin = 0.8
        else:
            current_top = 1.2 if frame.title else 0.5
            left_margin = 1.0
        shapes_by_block = []

        for block_idx, image_paths, is_animated, spacing in rendered_blocks:
            shapes = []
            for img_path in image_paths:
                shape = add_image_to_slide(
                    slide, img_path,
                    left=left_margin, top=current_top,
                    width=content_width
                )
                shapes.append(shape)
            if shapes:
                current_top += shapes[-1].height.inches + spacing
            shapes_by_block.append((block_idx, shapes, is_animated))

        # Add animations - each shape after the first in a block appears on click
        self._add_animations(slide, shapes_by_block)

    def _render_block(self, block, block_idx, block_dir, preamble, verbose):
        """Render a content block to images.

        Returns:
            Tuple of (block_idx, image_paths, is_animated, spacing) or None
        """
        if block.block_type == BlockType.TEXT:
            if len(block.items) > 1:
                image_paths = render_text_cumulative(
                    block.items, block_dir, preamble, self.style, self.dpi
                )
                if image_paths:
                    return (block_idx, image_paths, True, 0.15)
            elif block.items:
                img_path = os.path.join(block_dir, "text.png")
                if render_text_block(block.items[0], img_path, preamble, self.style, self.dpi):
                    return (block_idx, [img_path], False, 0.15)

        elif block.block_type == BlockType.MATH_ALIGN:
            env_name = self._get_env_name(block.raw_content)
            image_paths = render_align_cumulative(
                block.items, block_dir, preamble, env_name, self.style, self.dpi
            )
            if image_paths:
                return (block_idx, image_paths, True, 0.2)

        elif block.block_type == BlockType.DISPLAY_MATH:
            img_path = os.path.join(block_dir, "equation.png")
            if render_latex_to_image(block.raw_content, img_path, preamble, "math", self.style, self.dpi):
                return (block_idx, [img_path], True, 0.2)

        elif block.block_type in (BlockType.ITEMIZE, BlockType.ENUMERATE):
            env_name = 'enumerate' if block.block_type == BlockType.ENUMERATE else 'itemize'
            image_paths = render_itemize_cumulative(
                block.items, block_dir, preamble, env_name, self.style, self.dpi
            )
            if image_paths:
                return (block_idx, image_paths, True, 0.2)

        elif block.block_type == BlockType.CODE:
            if verbose:
                print(f"  Skipping code block (handled via Beamer PDF)")

        return None

    def _fit_content_width(self, rendered_blocks, has_beamer_bg):
        """Compute content width, scaling down if content would overflow the slide."""
        if not rendered_blocks:
            return self.content_width

        from PIL import Image

        slide_height = 7.5
        if has_beamer_bg:
            top_start = 0.88
            bottom_margin = 0.6
        else:
            top_start = 1.2
            bottom_margin = 0.3
        available_height = slide_height - top_start - bottom_margin

        total_image_height = 0.0
        total_spacing = 0.0

        for i, (block_idx, image_paths, is_animated, spacing) in enumerate(rendered_blocks):
            if not image_paths:
                continue
            # The last image in each block is the tallest (cumulative rendering)
            last_img = image_paths[-1]
            with Image.open(last_img) as img:
                pixel_w, pixel_h = img.size
            if pixel_w > 0:
                total_image_height += (pixel_h / pixel_w) * self.content_width
            if i < len(rendered_blocks) - 1:
                total_spacing += spacing

        total_height = total_image_height + total_spacing

        if total_height > available_height and total_image_height > 0:
            target_image_height = available_height - total_spacing
            if target_image_height > 0:
                scale = target_image_height / total_image_height
                scale = max(scale, 0.5)  # Don't shrink below 50%
                return self.content_width * scale

        return self.content_width

    def _add_animations(self, slide, shapes_by_block):
        """Add appear/disappear animations to shapes.

        ALL content requires a click to appear - nothing is visible initially.
        """
        click_index = 0

        for block_idx, shapes, is_animated in shapes_by_block:
            if not shapes:
                continue

            # Make the first shape appear on click (not visible initially)
            add_appear_animation(slide, shapes[0], click_index)
            click_index += 1

            # For subsequent shapes: appear on click and hide previous
            for shape_idx in range(1, len(shapes)):
                add_appear_animation(slide, shapes[shape_idx], click_index)
                add_disappear_animation(slide, shapes[shape_idx - 1], click_index)
                click_index += 1

    def _get_env_name(self, raw_content: str) -> str:
        """Extract environment name from raw content."""
        import re
        match = re.search(r'\\begin\{([^}]+)\}', raw_content)
        if match:
            return match.group(1)
        return 'align*'


def convert_beamer_to_pptx(
    input_path: str,
    output_path: Optional[str] = None,
    dpi: int = 400,
    verbose: bool = True
) -> str:
    """Convenience function to convert a Beamer file to PowerPoint.

    Args:
        input_path: Path to input .tex file
        output_path: Path for output .pptx (default: same name with .pptx extension)
        dpi: Resolution for rendered images (400 recommended for crisp output)
        verbose: Print progress

    Returns:
        Path to the output file
    """
    if output_path is None:
        output_path = str(Path(input_path).with_suffix('.pptx'))

    converter = BeamerConverter(dpi=dpi)
    converter.convert(input_path, output_path, verbose)

    return output_path
