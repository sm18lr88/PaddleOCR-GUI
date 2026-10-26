"""Default appearance data so qpdf can render, fill, and flatten widgets we create."""

import pikepdf

TEXT_DEFAULT_APPEARANCE = "/Helv 10 Tf 0 g"
CHECKBOX_ON_STATE = "Yes"


def ensure_helvetica_resource(pdf: pikepdf.Pdf) -> None:
    acroform = pdf.Root.AcroForm
    if "/DR" not in acroform:
        acroform.DR = pikepdf.Dictionary()
    if "/Font" not in acroform.DR:
        acroform.DR.Font = pikepdf.Dictionary()
    if "/Helv" not in acroform.DR.Font:
        acroform.DR.Font.Helv = pdf.make_indirect(
            pikepdf.Dictionary(
                Type=pikepdf.Name.Font,
                Subtype=pikepdf.Name.Type1,
                BaseFont=pikepdf.Name.Helvetica,
                Encoding=pikepdf.Name.WinAnsiEncoding,
            )
        )
    if "/DA" not in acroform:
        acroform.DA = pikepdf.String(TEXT_DEFAULT_APPEARANCE)


def checkbox_appearances(
    pdf: pikepdf.Pdf, width: float, height: float
) -> pikepdf.Dictionary:
    tick = (
        f"q 0 g 1.5 w {width * 0.2:.2f} {height * 0.5:.2f} m "
        f"{width * 0.42:.2f} {height * 0.22:.2f} l "
        f"{width * 0.82:.2f} {height * 0.82:.2f} l S Q"
    )
    return pikepdf.Dictionary(
        N=pikepdf.Dictionary(
            {
                f"/{CHECKBOX_ON_STATE}": _form(pdf, tick.encode(), width, height),
                "/Off": _form(pdf, b"", width, height),
            }
        )
    )


def _form(
    pdf: pikepdf.Pdf, content: bytes, width: float, height: float
) -> pikepdf.Stream:
    return pikepdf.Stream(
        pdf,
        content,
        Type=pikepdf.Name.XObject,
        Subtype=pikepdf.Name.Form,
        BBox=[0, 0, width, height],
    )
