---
name: Scholarly Precision
colors:
  surface: '#f5faf8'
  surface-dim: '#d6dbd9'
  surface-bright: '#f5faf8'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f5f2'
  surface-container: '#eaefed'
  surface-container-high: '#e4e9e7'
  surface-container-highest: '#dee4e1'
  on-surface: '#171d1c'
  on-surface-variant: '#3d4947'
  inverse-surface: '#2c3130'
  inverse-on-surface: '#edf2f0'
  outline: '#6d7a77'
  outline-variant: '#bcc9c6'
  surface-tint: '#006a61'
  primary: '#00685f'
  on-primary: '#ffffff'
  primary-container: '#008378'
  on-primary-container: '#f4fffc'
  inverse-primary: '#6bd8cb'
  secondary: '#515f74'
  on-secondary: '#ffffff'
  secondary-container: '#d5e3fd'
  on-secondary-container: '#57657b'
  tertiary: '#5b5c5c'
  on-tertiary: '#ffffff'
  tertiary-container: '#737574'
  on-tertiary-container: '#fcfcfb'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#89f5e7'
  primary-fixed-dim: '#6bd8cb'
  on-primary-fixed: '#00201d'
  on-primary-fixed-variant: '#005049'
  secondary-fixed: '#d5e3fd'
  secondary-fixed-dim: '#b9c7e0'
  on-secondary-fixed: '#0d1c2f'
  on-secondary-fixed-variant: '#3a485c'
  tertiary-fixed: '#e2e2e2'
  tertiary-fixed-dim: '#c6c7c6'
  on-tertiary-fixed: '#1a1c1c'
  on-tertiary-fixed-variant: '#454747'
  background: '#f5faf8'
  on-background: '#171d1c'
  surface-variant: '#dee4e1'
typography:
  headline-xl:
    fontFamily: IBM Plex Sans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: IBM Plex Sans
    fontSize: 20px
    fontWeight: '600'
    lineHeight: 28px
  headline-lg-mobile:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
  body-sm:
    fontFamily: Inter
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
  label-caps:
    fontFamily: JetBrains Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.05em
  cite-tag:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  baseline: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 40px
  container-max: 1440px
  sidebar-width: 280px
---

## Brand & Style

The design system is engineered for **LitFlow**, a local-first research writing copilot. The brand personality is intellectual, disciplined, and utilitarian, eschewing the "magical" or "ethereal" aesthetics typical of generative AI in favor of a tool-like precision inspired by high-performance productivity software like Linear and IBM Design Language.

The visual style is **Corporate Modern with a Minimalist lean**. It prioritizes high information density, allowing researchers to manage vast amounts of data without cognitive overload. The emotional response should be one of "calm focus"—a digital environment that recedes into the background to highlight the user's evidence and arguments. Surfaces are flat or subtly layered, using hairline strokes instead of heavy shadows to define structure.

## Colors

The palette is anchored by a warm off-white canvas (`#F9F9F8`) to reduce eye strain during long research sessions. The primary teal accent (`#0D9488`) is used sparingly for action states, focus indicators, and successful verification, ensuring it remains meaningful rather than decorative.

Typography and iconography utilize slate (`#334155`) for high legibility and professional rigor. A strictly functional semantic color system is employed for evidence status:
- **Amber:** Indicates partial evidence or claims requiring further scrutiny.
- **Green:** Indicates verified, cross-referenced evidence.
- **Red:** Indicates failures, contradictions, or missing sources.
- **Gray:** Used for secondary metadata and inactive states.

## Typography

The typography system is optimized for bilingual (English and Chinese) academic readability. **IBM Plex Sans** is used for headings to provide a structured, engineering-led feel. **Inter** is the primary body face for its exceptional clarity at small sizes and high information density.

For citations, metadata, and technical status, **JetBrains Mono** is introduced to provide a "local-first/data" aesthetic.
- **Body Text:** Use `body-md` for primary research text and `body-sm` for sidebar citations.
- **Hierarchy:** Ensure a clear distinction between user writing (Inter) and system-generated metadata (JetBrains Mono).
- **Line Height:** Tightened for labels but generous (1.5x+) for body paragraphs to facilitate deep reading.

## Layout & Spacing

The design system utilizes a **Fixed-Fluid Hybrid Grid**.
- **Desktop:** A fixed-width left navigation (280px), a fluid central "Workplace" column, and a contextual right-hand "Evidence" inspector.
- **Rhythm:** A 4px baseline grid governs all vertical spacing. Gutters are strictly maintained at 16px to ensure density without crowding.
- **Margins:** 24px internal padding for main containers to provide "breathing room" against the slate text.

Elements should be aligned to a 12-column layout within the central workplace area, ensuring that research cards and evidence snippets can scale consistently (e.g., 2-column or 3-column layouts for source grids).

## Elevation & Depth

This design system avoids traditional drop shadows to maintain its "flat-tool" aesthetic. Instead, it uses **Tonal Layering and Low-Contrast Outlines**:
- **Level 0 (Base):** The off-white canvas (`#F9F9F8`).
- **Level 1 (Cards/Sidebar):** White surfaces (`#FFFFFF`) with a 1px hairline border in `#E2E8F0`.
- **Level 2 (Popovers/Context Menus):** White surfaces with a very subtle, tight ambient shadow (4px blur, 5% opacity) to provide minimal lift.
- **Active State:** Elements in focus use a 1px Teal (`#0D9488`) border instead of a shadow.

## Shapes

The shape language is conservative and professional. A "Soft" roundedness level (4px to 6px) is applied to all interactive components.
- **Buttons & Inputs:** 4px radius to feel precise and sharp.
- **Evidence Cards:** 6px radius to slightly soften the content blocks.
- **Tags/Status Badges:** 2px or fully square, emphasizing the "database" nature of the tool.
Avoid large pill-shapes or excessive rounding, which can appear too consumer-oriented or "soft" for academic work.

## Components

- **Buttons:** Primary buttons use a solid Teal background with white text. Secondary buttons use a white background with a 1px slate border. Text is always centered and set in `body-sm`.
- **Citations/Tags:** Small, rectangular chips with a light gray background (`#F1F5F9`) and `label-caps` typography. They should look like index cards.
- **Evidence Cards:** Contain a source title, a snippet of text, and a status indicator. Use a left-border accent (Amber/Green/Red) to denote verification status at a glance.
- **Input Fields:** Minimalist design with a 1px border. On focus, the border changes to Teal. Use `Inter` for input text.
- **Status Indicators:** Small 8px solid circles or thin vertical ribbons on the edge of cards.
- **Lists:** Clean, unstyled lists with 8px vertical spacing. Use subtle dividers only when content is highly disparate.
