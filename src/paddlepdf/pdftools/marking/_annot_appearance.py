"""Appearance streams for created annotations so viewers, print, and flatten agree."""

import pikepdf

type Rect = tuple[float, float, float, float]
type Rgb = tuple[float, float, float]


def appearance(
    pdf: pikepdf.Pdf,
    kind: str,
    rect: Rect,
    color: Rgb,
    stroke: list[tuple[float, float]] | None = None,
) -> pikepdf.Dictionary:
    left, bottom, right, top = rect
    r, g, b = color
    resources = pikepdf.Dictionary()
    match kind:
        case "highlight":
            resources.ExtGState = pikepdf.Dictionary(
                GS0=pikepdf.Dictionary(
                    Type=pikepdf.Name.ExtGState, BM=pikepdf.Name.Multiply
                )
            )
            width, height = right - left, top - bottom
            body = f"/GS0 gs {r} {g} {b} rg {left} {bottom} {width} {height} re f"
        case "underline":
            body = (
                f"{r} {g} {b} RG 1.5 w {left} {bottom + 1} m {right} {bottom + 1} l S"
            )
        case "strikethrough":
            middle = (bottom + top) / 2
            body = f"{r} {g} {b} RG 1.5 w {left} {middle} m {right} {middle} l S"
        case "note":
            body = (
                f"{r} {g} {b} rg 0 G 1 w {left + 1} {bottom + 1} "
                f"{right - left - 2} {top - bottom - 2} re B"
            )
        case _:
            points = stroke or [(left, bottom), (right, top)]
            path = " ".join(
                f"{x} {y} {'m' if index == 0 else 'l'}"
                for index, (x, y) in enumerate(points)
            )
            body = f"{r} {g} {b} RG 2 w 1 J 1 j {path} S"
    stream = pikepdf.Stream(
        pdf,
        f"q {body} Q".encode(),
        Type=pikepdf.Name.XObject,
        Subtype=pikepdf.Name.Form,
        BBox=[left, bottom, right, top],
        Resources=resources,
    )
    return pikepdf.Dictionary(N=stream)
