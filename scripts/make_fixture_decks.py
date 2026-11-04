"""Generate the shareable sample decks in tests/fixtures/decks/ (committed).

    .venv/bin/python scripts/make_fixture_decks.py
"""

from __future__ import annotations

import io
from pathlib import Path

import pymupdf as fitz
from pptx import Presentation
from pptx.util import Inches, Pt

OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "decks"

REGRESSION = [
    ("Linear Regression", ["Lecture 4 · Introduction to Machine Learning"]),
    ("Outline", ["Supervised learning recap", "Linear models", "Least squares", "Gradient descent", "Regularisation", "Evaluation"]),
    ("Supervised learning", ["Given pairs (x, y), learn a function f so that f(x) ≈ y", "Regression: y is a real number", "Classification: y is a label"]),
    ("Training data", ["Dataset D = {(x_i, y_i)} for i = 1..n", "Features x_i ∈ R^d", "Targets y_i ∈ R"]),
    ("The linear model", ["Prediction ŷ = wᵀx + b", "w: weights, b: bias (intercept)", "Linear in the parameters, not necessarily in x"]),
    ("Feature maps", ["Replace x with φ(x) to fit curves", "Polynomial features: φ(x) = (1, x, x², x³)", "Still a linear model in w"]),
    ("Loss functions", ["Measure how wrong predictions are", "Squared error: (y − ŷ)²", "Absolute error: |y − ŷ|"]),
    ("Least squares objective", ["Minimise J(w) = Σ (y_i − wᵀx_i)²", "Convex in w → single global minimum", "Matrix form: J(w) = ||y − Xw||²"]),
    ("Normal equations", ["Set gradient to zero: Xᵀ(Xw − y) = 0", "Solution: w* = (XᵀX)⁻¹ Xᵀy", "Requires XᵀX to be invertible"]),
    ("Geometry of least squares", ["Xw* is the projection of y onto the column space of X", "Residual y − Xw* is orthogonal to the columns of X"]),
    ("Cost of the closed form", ["Inverting XᵀX costs O(d³)", "Slow when d is large", "Motivates iterative methods"]),
    ("Gradient descent", ["Start from w₀", "Repeat: w ← w − η ∇J(w)", "η is the learning rate"]),
    ("Choosing the learning rate", ["Too small: slow convergence", "Too large: divergence or oscillation", "Use a schedule or line search"]),
    ("Stochastic gradient descent", ["Use one example (or a mini-batch) per step", "Noisy but cheap updates", "Scales to very large datasets"]),
    ("Feature scaling", ["Standardise each feature to mean 0, variance 1", "Makes gradient descent converge faster"]),
    ("Overfitting", ["Model fits noise in the training data", "Low training error, high test error", "More likely with many features"]),
    ("Ridge regression", ["Add L2 penalty λ||w||²", "Closed form: w* = (XᵀX + λI)⁻¹ Xᵀy", "Shrinks weights towards zero"]),
    ("Lasso regression", ["Add L1 penalty λ||w||₁", "Produces sparse weights", "No closed form; use coordinate descent"]),
    ("Choosing λ", ["Hold out a validation set", "k-fold cross-validation", "Pick λ with the lowest validation error"]),
    ("Bias–variance trade-off", ["Bias: error from wrong assumptions", "Variance: error from sensitivity to data", "Regularisation trades variance for bias"]),
    ("Evaluation metrics", ["Mean squared error (MSE)", "Root mean squared error (RMSE)", "Coefficient of determination R²"]),
    ("Interpreting R²", ["R² = 1 − SS_res / SS_tot", "1 means perfect fit, 0 means no better than the mean"]),
    ("", []),  # figure-only slide (image, almost no text)
    ("Summary", ["Linear models predict with wᵀx + b", "Least squares has a closed form", "Gradient descent scales better", "Regularise to avoid overfitting"]),
    ("Questions?", []),
]


def _png(w: int, h: int) -> bytes:
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, w, h), 0)
    pix.set_rect(pix.irect, (210, 220, 240))
    for x in range(20, w - 20):
        y = int(h - 20 - (x - 20) * (h - 40) / (w - 40))
        for dy in range(-2, 3):
            if 0 <= y + dy < h:
                pix.set_pixel(x, y + dy, (47, 79, 201))
    return pix.tobytes("png")


_FONT = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")


def _text(page: "fitz.Page", pos: tuple[int, int], text: str, size: int) -> None:
    if _FONT.exists():
        page.insert_text(pos, text, fontsize=size, fontname="dejavu", fontfile=str(_FONT))
    else:
        page.insert_text(pos, text, fontsize=size)


def make_pdf() -> None:
    doc = fitz.open()
    img = _png(320, 200)
    for title, bullets in REGRESSION:
        page = doc.new_page(width=960, height=540)
        if title:
            _text(page, (60, 90), title, 34)
        y = 160
        for b in bullets:
            _text(page, (80, y), "• " + b, 20)
            y += 44
        if not title and not bullets:
            page.insert_image(fitz.Rect(240, 100, 720, 440), stream=img)
            _text(page, (400, 480), "Fig. 3", 14)
    doc.subset_fonts()
    doc.save(OUT / "linear_regression.pdf", garbage=4, deflate=True)


SORTING = [
    ("Sorting Algorithms", ["Data Structures · Week 6"]),
    ("Why sorting matters", ["Searching is faster on sorted data", "Many algorithms assume sorted input"]),
    ("Bubble sort", ["Repeatedly swap adjacent out-of-order elements", "O(n²) comparisons in the worst case"]),
    ("Insertion sort", ["Build the sorted prefix one element at a time", "O(n) on nearly sorted input"]),
    ("Merge sort", ["Divide the array in half, sort each half, merge", "O(n log n) always", "Needs O(n) extra memory"]),
    ("Quicksort", ["Pick a pivot, partition, recurse", "O(n log n) on average, O(n²) worst case", "In-place"]),
    ("TABLE", []),
    ("Stability", ["A stable sort keeps equal keys in their original order", "Merge sort is stable; quicksort is not"]),
    ("IMAGE", []),
    ("Summary", ["Use insertion sort for tiny arrays", "Merge sort when stability matters", "Quicksort is fast in practice"]),
]


def make_pptx() -> None:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    img = io.BytesIO(_png(320, 200))
    for title, bullets in SORTING:
        if title == "TABLE":
            s = prs.slides.add_slide(prs.slide_layouts[5])
            s.shapes.title.text = "Comparison"
            tbl = s.shapes.add_table(4, 3, Inches(1), Inches(2), Inches(10), Inches(3)).table
            rows = [("Algorithm", "Average", "Worst"), ("Bubble", "O(n²)", "O(n²)"),
                    ("Merge", "O(n log n)", "O(n log n)"), ("Quick", "O(n log n)", "O(n²)")]
            for r, row in enumerate(rows):
                for c, val in enumerate(row):
                    tbl.cell(r, c).text = val
            continue
        if title == "IMAGE":
            s = prs.slides.add_slide(prs.slide_layouts[6])
            img.seek(0)
            s.shapes.add_picture(img, Inches(3), Inches(1.5), width=Inches(7))
            continue
        layout = prs.slide_layouts[0] if not bullets or len(bullets) == 1 else prs.slide_layouts[1]
        s = prs.slides.add_slide(layout)
        s.shapes.title.text = title
        body = s.placeholders[1].text_frame
        body.text = bullets[0] if bullets else ""
        for b in bullets[1:]:
            p = body.add_paragraph()
            p.text = b
            p.font.size = Pt(24)
    prs.save(OUT / "sorting.pptx")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    make_pdf()
    make_pptx()
    print("wrote", sorted(p.name for p in OUT.iterdir()))
