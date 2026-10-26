from paddlepdf.pdftools.contract import ToolSpec
from paddlepdf.pdftools.forms.create import pdf_create_form_field
from paddlepdf.pdftools.forms.fill import pdf_fill_form
from paddlepdf.pdftools.forms.read import pdf_read_form

TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="pdf_read_form",
        description=(
            "Extract AcroForm fields from a PDF: each field's name, type "
            "(text/checkbox/radio/pushbutton/choice/signature), current value, "
            "choice options, and 1-based page number."
        ),
        handler=pdf_read_form,
    ),
    ToolSpec(
        name="pdf_fill_form",
        description=(
            "Fill AcroForm fields in a PDF from a field_name -> value mapping "
            "(bool for checkbox/radio, string for text/choice) and regenerate "
            "their appearance streams, writing a new PDF."
        ),
        handler=pdf_fill_form,
    ),
    ToolSpec(
        name="pdf_create_form_field",
        description=(
            "Add a new text or checkbox AcroForm widget to a PDF page at a given "
            "rect (left, bottom, right, top in PDF points), writing a new PDF."
        ),
        handler=pdf_create_form_field,
    ),
)
