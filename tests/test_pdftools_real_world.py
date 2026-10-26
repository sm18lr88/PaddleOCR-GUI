from collections.abc import Callable
from pathlib import Path

import pikepdf
from pydantic import BaseModel, TypeAdapter

from paddlepdf.pdftools.forms import TOOLS as FORM_TOOLS
from paddlepdf.pdftools.marking import TOOLS as MARKING_TOOLS
from paddlepdf.pdftools.pages_basic import TOOLS as BASIC_TOOLS
from paddlepdf.pdftools.pages_geometry import TOOLS as GEOMETRY_TOOLS
from paddlepdf.pdftools.pdfium import page_texts
from paddlepdf.pdftools.runner import run_tool
from paddlepdf.pdftools.structure_meta import TOOLS as META_TOOLS
from paddlepdf.pdftools.structure_ops import TOOLS as OPS_TOOLS

type MakePdf = Callable[..., Path]


class ListedMark(BaseModel):
    page: int | None


SPECS = {
    spec.name: spec
    for spec in (
        *BASIC_TOOLS,
        *FORM_TOOLS,
        *MARKING_TOOLS,
        *GEOMETRY_TOOLS,
        *META_TOOLS,
        *OPS_TOOLS,
    )
}


def _hyperref_style_outline(source: Path, target: Path) -> None:
    with pikepdf.open(source) as pdf:
        dests = pikepdf.Array()
        outline_items: list[pikepdf.Dictionary] = []
        for name, page_index in (("section.1", 0), ("section.2", 2), ("section.3", 4)):
            dests.extend(
                [
                    pikepdf.String(name),
                    pikepdf.Array([pdf.pages[page_index].obj, pikepdf.Name.Fit]),
                ]
            )
            outline_items.append(
                pdf.make_indirect(
                    pikepdf.Dictionary(
                        Title=pikepdf.String(f"Chapter {name[-1]}"),
                        A=pikepdf.Dictionary(
                            S=pikepdf.Name.GoTo, D=pikepdf.String(name)
                        ),
                    )
                )
            )
        pdf.Root.Names = pikepdf.Dictionary(
            Dests=pdf.make_indirect(pikepdf.Dictionary(Names=dests))
        )
        outlines = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Outlines))
        for index, item in enumerate(outline_items):
            item.Parent = outlines
            if index:
                item.Prev = outline_items[index - 1]
            if index < len(outline_items) - 1:
                item.Next = outline_items[index + 1]
        outlines.First, outlines.Last, outlines.Count = (
            outline_items[0],
            outline_items[-1],
            3,
        )
        pdf.Root.Outlines = outlines
        pdf.save(target)


def test_outline_with_named_destinations_splits_and_lists(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    source = tmp_path / "hyperref.pdf"
    _hyperref_style_outline(make_pdf(pages=6), source)

    split = run_tool(
        SPECS["pdf_split_by_outline"],
        {"input_file": str(source), "output_dir": str(tmp_path / "ch")},
    )
    listed = run_tool(SPECS["pdf_bookmarks"], {"input_file": str(source)})

    assert split.status == "success", split.errors
    assert split.data == [
        {"title": "Chapter 1", "start_page": 1, "end_page": 2},
        {"title": "Chapter 2", "start_page": 3, "end_page": 4},
        {"title": "Chapter 3", "start_page": 5, "end_page": 6},
    ]
    marks = TypeAdapter(dict[str, list[ListedMark]]).validate_python(listed.data)
    assert [mark.page for mark in marks["bookmarks"]] == [1, 3, 5]


def test_auto_rotate_undoes_a_quarter_turn_to_upright(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    turned, upright = tmp_path / "turned.pdf", tmp_path / "upright.pdf"
    run_tool(
        SPECS["pdf_rotate"],
        {
            "input_file": str(make_pdf()),
            "angle": 90,
            "pages": "2",
            "output_file": str(turned),
        },
    )

    result = run_tool(
        SPECS["pdf_auto_rotate"],
        {"input_file": str(turned), "output_file": str(upright)},
    )

    assert result.status == "success"
    with pikepdf.open(upright) as pdf:
        assert [int(page.obj.get("/Rotate", 0)) for page in pdf.pages] == [0, 0, 0]


def test_created_fields_fill_and_flatten_into_page_text(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    form1, form2, filled, flat = (
        tmp_path / n for n in ("f1.pdf", "f2.pdf", "filled.pdf", "flat.pdf")
    )
    run_tool(
        SPECS["pdf_create_form_field"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(form1),
            "field_name": "reviewer",
            "field_type": "text",
            "page": 1,
            "rect": [72, 60, 300, 84],
        },
    )
    run_tool(
        SPECS["pdf_create_form_field"],
        {
            "input_file": str(form1),
            "output_file": str(form2),
            "field_name": "ok",
            "field_type": "checkbox",
            "page": 1,
            "rect": [320, 60, 340, 80],
        },
    )
    run_tool(
        SPECS["pdf_fill_form"],
        {
            "input_file": str(form2),
            "output_file": str(filled),
            "values": {"reviewer": "Dr. QA", "ok": True},
        },
    )

    result = run_tool(
        SPECS["pdf_flatten"], {"input_file": str(filled), "output_file": str(flat)}
    )

    assert result.status == "success"
    assert result.warnings == ()
    assert "Dr. QA" in page_texts(flat)[0]
    with pikepdf.open(flat) as pdf:
        assert "/AcroForm" not in pdf.Root
        assert "/Annots" not in pdf.pages[0] or len(pdf.pages[0].Annots) == 0


def test_annotations_carry_appearances_and_flatten_away(
    make_pdf: MakePdf, tmp_path: Path
) -> None:
    annotated, flat = tmp_path / "annot.pdf", tmp_path / "flat.pdf"
    run_tool(
        SPECS["pdf_annotate"],
        {
            "input_file": str(make_pdf()),
            "output_file": str(annotated),
            "annotations": [
                {
                    "type": kind,
                    "page": 1,
                    "x": 72,
                    "y": 500 - 40 * index,
                    "content": "n",
                }
                for index, kind in enumerate(
                    ("highlight", "underline", "strikethrough", "note", "pen")
                )
            ],
        },
    )
    with pikepdf.open(annotated) as pdf:
        assert all("/AP" in annot for annot in pdf.pages[0].Annots)

    result = run_tool(
        SPECS["pdf_flatten"], {"input_file": str(annotated), "output_file": str(flat)}
    )

    assert result.warnings == ()
    with pikepdf.open(flat) as pdf:
        assert "/Annots" not in pdf.pages[0] or len(pdf.pages[0].Annots) == 0
