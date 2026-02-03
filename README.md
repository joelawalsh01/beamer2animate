# beamer2animate

Convert LaTeX Beamer presentations to animated PowerPoint (PPTX) with line-by-line animations.

## Features

- **Line-by-line animations**: Each bullet point, math line, and paragraph appears on click
- **Math support**: `align*`, `gather*`, `equation*` environments animate line by line
- **Bullet animations**: `itemize` and `enumerate` items appear one at a time
- **Code slides**: Frames with `lstlisting` are captured as screenshots from the compiled Beamer PDF
- **Theme preservation**: Extracts colors from Beamer themes (e.g., Madrid blue)
- **High quality**: Renders at 400 DPI for crisp output

## Requirements

- Python 3.10+
- LaTeX distribution with `pdflatex` (e.g., TeX Live, MacTeX, MiKTeX)
- [uv](https://github.com/astral-sh/uv) package manager (recommended) or pip

## Installation

### Using uv (recommended)

```bash
# Clone the repository
git clone https://github.com/yourusername/beamer2animate.git
cd beamer2animate

# Install dependencies
uv sync
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/yourusername/beamer2animate.git
cd beamer2animate

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install python-pptx pylatexenc pillow pymupdf pdf2image
```

## Usage

### Command Line

```bash
# Basic usage
uv run python main.py presentation.tex

# Specify output file
uv run python main.py presentation.tex -o output.pptx

# Adjust DPI (default: 400)
uv run python main.py presentation.tex --dpi 300

# Quiet mode
uv run python main.py presentation.tex -q
```

### Python API

```python
from beamer2animate import convert_beamer_to_pptx

# Convert a Beamer file
convert_beamer_to_pptx("presentation.tex", "output.pptx", dpi=400)
```

## How It Works

1. **Parsing**: The Beamer `.tex` file is parsed to identify frames, math environments, itemize/enumerate blocks, and code listings.

2. **Rendering**: Each content block is rendered to PNG images using LaTeX:
   - For animated content (math, bullets), cumulative images are created (step 1, steps 1-2, steps 1-2-3, etc.)
   - Code slides are extracted directly from the compiled Beamer PDF

3. **PowerPoint Generation**: Images are placed on slides with "appear on click" animations using OOXML manipulation.

## Supported Beamer Elements

| Element | Animation |
|---------|-----------|
| `itemize` | Each `\item` appears on click |
| `enumerate` | Each `\item` appears on click |
| `align*`, `gather*` | Each line (separated by `\\`) appears on click |
| `equation*` | Appears on click |
| Text with `\textbf{}` | Each bold section starts a new animation step |
| `lstlisting` | Full frame screenshot from Beamer PDF (no animation) |

## Example

Input (`presentation.tex`):
```latex
\begin{frame}{Example}
\textbf{Introduction:}
This is the first point.

\begin{itemize}
    \item First bullet
    \item Second bullet
    \item Third bullet
\end{itemize}

\begin{align*}
f(x) &= x^2 + 2x + 1 \\
     &= (x + 1)^2
\end{align*}
\end{frame}
```

Output: A PowerPoint slide where:
1. Click → "Introduction: This is the first point." appears
2. Click → First bullet appears
3. Click → Second bullet appears (first stays visible)
4. Click → Third bullet appears (all three visible)
5. Click → First math line appears
6. Click → Second math line appears (both visible)

## Limitations

- Complex Beamer layouts (columns, overlays with `\only`, `\visible`) may not render correctly
- Custom Beamer themes are approximated, not perfectly replicated
- TikZ graphics are not supported
- Beamer animations (`\pause`, `\onslide`) are stripped; all content is re-animated

## License

MIT License
