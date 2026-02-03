#!/usr/bin/env python3
"""CLI for beamer2animate: Convert Beamer presentations to animated PowerPoint."""

import argparse
import sys
from pathlib import Path

from beamer2animate.converter import convert_beamer_to_pptx


def main():
    parser = argparse.ArgumentParser(
        description="Convert Beamer LaTeX presentations to animated PowerPoint",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    %(prog)s presentation.tex
    %(prog)s presentation.tex -o output.pptx
    %(prog)s presentation.tex --dpi 300
        """
    )

    parser.add_argument(
        "input",
        help="Input Beamer .tex file"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output .pptx file (default: same name as input with .pptx extension)"
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=400,
        help="DPI for rendered LaTeX images (default: 400 for crisp output)"
    )
    parser.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Suppress progress output"
    )

    args = parser.parse_args()

    # Validate input file
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    if not input_path.suffix == '.tex':
        print(f"Warning: Input file does not have .tex extension", file=sys.stderr)

    # Determine output path
    output_path = args.output
    if output_path is None:
        output_path = str(input_path.with_suffix('.pptx'))

    # Convert
    try:
        result = convert_beamer_to_pptx(
            str(input_path),
            output_path,
            dpi=args.dpi,
            verbose=not args.quiet
        )
        if not args.quiet:
            print(f"\nCreated: {result}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
