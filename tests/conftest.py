"""Shared fixtures for beamer2animate tests."""

import os
import shutil
import tempfile

import pytest


@pytest.fixture
def tmp_dir():
    """Create a temporary directory for test outputs."""
    d = tempfile.mkdtemp(prefix="b2a_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def sample_preamble():
    """A minimal Beamer preamble."""
    return r"""\documentclass{beamer}
\usetheme{Madrid}
\usepackage{amsmath}
\title{Test Presentation}
\author{Test Author}
"""


@pytest.fixture
def sample_document(sample_preamble):
    """A complete minimal Beamer document."""
    return sample_preamble + r"""
\begin{document}

\begin{frame}{First Slide}
\begin{itemize}
\item Alpha
\item Beta
\item Gamma
\end{itemize}
\end{frame}

\begin{frame}{Math Slide}
\begin{align*}
x &= 1 \\
y &= 2
\end{align*}
\end{frame}

\begin{frame}{Text Slide}
First paragraph about something.

Second paragraph about something else.
\end{frame}

\end{document}
"""
