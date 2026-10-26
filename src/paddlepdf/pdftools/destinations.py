"""Resolve outline and link destinations (explicit, named, or GoTo actions) to pages.

LaTeX/hyperref PDFs use named destinations stored in the /Names /Dests tree, so an
outline item often carries ``/A << /S /GoTo /D (section.1) >>`` instead of a page.
"""

from collections.abc import Mapping

import pikepdf

type PageNumbers = Mapping[tuple[int, int], int]


def page_numbers(pdf: pikepdf.Pdf) -> dict[tuple[int, int], int]:
    return {page.obj.objgen: number for number, page in enumerate(pdf.pages, start=1)}


def outline_page(
    pdf: pikepdf.Pdf, item: pikepdf.OutlineItem, numbers: PageNumbers
) -> int | None:
    target: object = item.destination
    if target is None and item.action is not None:
        target = item.action.get("/D")
    return destination_page(pdf, target, numbers)


def destination_page(
    pdf: pikepdf.Pdf, target: object, numbers: PageNumbers
) -> int | None:
    if isinstance(target, pikepdf.String | pikepdf.Name):
        target = _named_destination(pdf, target)
    if isinstance(target, pikepdf.Dictionary):
        target = target.get("/D")
    if not isinstance(target, pikepdf.Array) or len(target) == 0:
        return None
    page = target[0]
    if isinstance(page, pikepdf.Dictionary):
        return numbers.get(page.objgen)
    return None


def _named_destination(pdf: pikepdf.Pdf, name: pikepdf.String | pikepdf.Name) -> object:
    key = str(name).removeprefix("/") if isinstance(name, pikepdf.Name) else str(name)
    names = pdf.Root.get("/Names")
    if isinstance(names, pikepdf.Dictionary) and "/Dests" in names:
        tree = pikepdf.NameTree(names.Dests)
        if key in tree:
            return tree[key]
    legacy = pdf.Root.get("/Dests")
    if isinstance(legacy, pikepdf.Dictionary):
        return legacy.get(f"/{key}")
    return None
