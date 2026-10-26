# PaddleOCR-GUI design system

## 1. Direction

Cross-platform desktop utility with a compact, OpenAI_TTS_GUI-inspired control layout: slate canvas, flat ordered rows, no stacked cards, and one restrained steel-blue accent for the primary action and progress state.

## 2. Color tokens

- `bg.canvas`: `#202327`
- `bg.field`: `#282d33`
- `bg.button`: `#30363e`
- `bg.button-hover`: `#39404a`
- `text.primary`: `#eceff3`
- `text.secondary`: `#b3bac5`
- `text.disabled`: `#7d8794`
- `border.panel`: `#353c45`
- `border.control`: `#444c57`
- `accent.primary`: `#7890ae`
- `accent.hover`: `#8ba1bc`
- `accent.pressed`: `#5f7899`

## 3. Typography

- Primary font: system UI stack with Segoe UI Variable Text first on Windows, 10 pt base.
- Window title: 17 pt, 700 weight.
- Section labels: 9 pt, 700 weight, secondary text.
- Body and controls: 10 pt, 400-510 weight.
- Logs and paths: monospace system font where Qt chooses one for plain text.

## 4. Spacing and shape

- Base spacing: 8 px.
- Root margin: 12-14 px.
- Row spacing: 6-8 px.
- Control radius: 6 px.
- Inputs and buttons use 26-30 px height; no oversized colorful controls.
- Dividers may separate workflow areas; avoid card boxes unless a real modal/popup needs containment.

## 5. Components

- `Header`: title plus inline language switch, no subtitle or marketing copy.
- `Document queue`: compact list with add/select button in the same row as the label.
- `Output row`: label, path field, and browse button in one line.
- `Settings grid`: output format, profile, device, and OCR checkboxes in dense ordered rows.
- `Input`: slate recessed field, subtle border, steel-blue focus ring.
- `Primary button`: solid steel-blue, compact, used only for conversion.
- `Secondary button`: slate surface with subtle border.
- `Progress bar`: low-height track with steel-blue chunk.
- `Log`: dark recessed monospace output with muted text.

## 6. Interaction states

- Hover increases surface luminance by one step.
- Pressed state darkens or lowers luminance.
- Focus uses a steel-blue border and subtle glow, never a bright default outline.
- Disabled state lowers contrast and preserves layout.

## 7. Accessibility

- All interactive controls retain visible focus.
- Accent is not the only indicator for progress; text status remains visible.
- RTL layout remains controlled by the existing language switch.
