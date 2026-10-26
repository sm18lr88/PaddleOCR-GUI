"""Shared helpers that place source pages as form XObjects and edit page resources."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import cast

import pikepdf

_QUARTER_TURN = 90


@dataclass(frozen=True, slots=True)
class PageForm:
    """A source page imported as a form XObject, with its visible box in sheet units."""

    form: pikepdf.Object
    width: float
    height: float
    origin_x: float
    origin_y: float


@dataclass(frozen=True, slots=True)
class Placement:
    form: PageForm
    scale: float
    x: float
    y: float


def _number(value: object) -> float:
    return float(cast("float", value))


def _numbers(values: object) -> list[float]:
    return [_number(value) for value in cast("pikepdf.Array", values)]


def _copy(dictionary: pikepdf.Object) -> pikepdf.Dictionary:
    return pikepdf.Dictionary(dict(dictionary.items()))


def import_page(dst: pikepdf.Pdf, page: pikepdf.Page) -> PageForm:
    """Copy ``page`` into ``dst`` as a form; rotation is folded into the form matrix."""
    form = dst.copy_foreign(page.as_form_xobject())
    left, bottom, right, top = _numbers(form["/BBox"])
    matrix = _numbers(form["/Matrix"]) if "/Matrix" in form else [1, 0, 0, 1, 0, 0]
    a, b, c, d, e, f = matrix
    corners = [(left, bottom), (right, bottom), (left, top), (right, top)]
    xs = [a * x + c * y + e for x, y in corners]
    ys = [b * x + d * y + f for x, y in corners]
    return PageForm(form, max(xs) - min(xs), max(ys) - min(ys), min(xs), min(ys))


def page_size(page: pikepdf.Page) -> tuple[float, float]:
    """Visible width and height of a page, honouring its crop box and rotation."""
    left, bottom, right, top = _numbers(page.trimbox)
    width, height = right - left, top - bottom
    rotation = int(cast("int", page.obj.get("/Rotate", 0))) % 180
    return (height, width) if rotation == _QUARTER_TURN else (width, height)


def place_ops(name: str, placement: Placement) -> bytes:
    form, scale = placement.form, placement.scale
    tx = placement.x - scale * form.origin_x
    ty = placement.y - scale * form.origin_y
    return f"q {scale:.6f} 0 0 {scale:.6f} {tx:.4f} {ty:.4f} cm /{name} Do Q\n".encode()


def add_sheet(
    dst: pikepdf.Pdf,
    width: float,
    height: float,
    placements: Sequence[Placement],
    extra: bytes = b"",
) -> None:
    xobjects = pikepdf.Dictionary()
    operations: list[bytes] = []
    for index, placement in enumerate(placements):
        name = f"Fm{index}"
        xobjects[f"/{name}"] = placement.form.form
        operations.append(place_ops(name, placement))
    sheet = pikepdf.Dictionary(
        Type=pikepdf.Name.Page,
        MediaBox=[0, 0, width, height],
        Resources=pikepdf.Dictionary(XObject=xobjects),
        Contents=dst.make_stream(b"".join(operations) + extra),
    )
    dst.pages.append(pikepdf.Page(sheet))


def add_resource(page: pikepdf.Page, category: str, name: str, value: object) -> None:
    """Register ``value`` under ``/category /name`` on a private copy of the resources.

    Writer-made PDFs often share one resource dictionary between all pages; copying it
    keeps a change to one page from leaking into the others.
    """
    fresh = _copy(page.resources)
    group = _copy(fresh[category]) if category in fresh else pikepdf.Dictionary()
    group[name] = value
    fresh[category] = group
    page.obj["/Resources"] = fresh


def paint_under(pdf: pikepdf.Pdf, page: pikepdf.Page, operations: bytes) -> None:
    page.contents_add(pdf.make_stream(b"q\n" + operations + b"Q\n"), prepend=True)


def paint_over(pdf: pikepdf.Pdf, page: pikepdf.Page, operations: bytes) -> None:
    """Append ``operations`` above the page content, isolated from its state."""
    page.contents_add(pdf.make_stream(b"q\n"), prepend=True)
    page.contents_add(pdf.make_stream(b"Q\nq\n" + operations + b"Q\n"))
