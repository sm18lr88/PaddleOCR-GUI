# PaddleOCR-GUI design system

## 1. Direction

Native Windows desktop utility with a Linear-inspired dark surface: near-black canvas, cool-gray panels, small precise controls, and one restrained indigo accent for the primary action and progress state.

## 2. Color tokens

- `bg.canvas`: `#08090a`
- `bg.panel`: `#0f1011`
- `bg.surface`: `#15171a`
- `bg.surface-hover`: `#1d2025`
- `text.primary`: `#f7f8f8`
- `text.secondary`: `#d0d6e0`
- `text.muted`: `#8a8f98`
- `text.disabled`: `#62666d`
- `border.subtle`: `rgba(255, 255, 255, 0.06)`
- `border.standard`: `rgba(255, 255, 255, 0.10)`
- `accent.primary`: `#5e6ad2`
- `accent.hover`: `#7170ff`
- `accent.pressed`: `#4d58b8`

## 3. Typography

- Primary font: Windows system UI stack, 10 pt base.
- Window title: 20 pt, 590 weight, tight tracking where supported.
- Section labels: 10 pt, 590 weight, secondary text.
- Body and controls: 10 pt, 400-510 weight.
- Logs and paths: monospace system font where Qt chooses one for plain text.

## 4. Spacing and shape

- Base spacing: 8 px.
- Root margin: 18 px.
- Panel padding: 16 px.
- Control radius: 6 px.
- Panel radius: 10 px.
- Inputs and buttons use 28-32 px height; no oversized colorful controls.

## 5. Components

- `Header`: title plus muted subtitle, no decorative imagery.
- `Panel`: subtle translucent surface with thin white border.
- `Input`: dark recessed field, subtle border, indigo focus ring.
- `Primary button`: solid indigo, compact, used only for conversion.
- `Secondary button`: dark transparent surface with subtle border.
- `Progress bar`: low-height track with indigo chunk.
- `Log`: dark recessed monospace output with muted text.

## 6. Interaction states

- Hover increases surface luminance by one step.
- Pressed state darkens or lowers luminance.
- Focus uses an indigo border and subtle glow, never a bright default outline.
- Disabled state lowers contrast and preserves layout.

## 7. Accessibility

- All interactive controls retain visible focus.
- Accent is not the only indicator for progress; text status remains visible.
- RTL layout remains controlled by the existing language switch.
