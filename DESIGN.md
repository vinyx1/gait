---
name: TripLens
description: City decisions told at the kitchen table, one colour field per scene.
colors:
  harvest-gold: "#e8b03a"
  avocado: "#5f6d22"
  burnt-orange: "#d0662a"
  walnut: "#4e3220"
  snow: "#f1f3f2"
  pyrex-turquoise: "#3c9c95"
  coffee-ink: "#24140a"
  teal-ink: "#0c2220"
  cream: "#fbf1d8"
  stoneware: "#f3e3bf"
typography:
  display:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "clamp(46px, 5vw, 80px)"
    fontWeight: 400
    lineHeight: 1.04
    letterSpacing: "-0.015em"
  headline:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "clamp(38px, 4vw, 62px)"
    fontWeight: 400
    lineHeight: 1.04
    letterSpacing: "-0.015em"
  figure:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "clamp(56px, 5.6vw, 92px)"
    fontWeight: 400
    lineHeight: 1
    fontFeature: "lnum, tnum"
  quote:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "clamp(24px, 2vw, 32px)"
    fontWeight: 400
    lineHeight: 1.3
  body:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "clamp(20px, 1.4vw, 22px)"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "Atkinson Hyperlegible, system-ui, sans-serif"
    fontSize: "clamp(20px, 1.5vw, 23px)"
    fontWeight: 700
    lineHeight: 1.2
rounded:
  drawing: "7px"
  focus: "12px"
  pill: "999px"
spacing:
  gutter: "clamp(18px, 4.5vw, 72px)"
  column-gap: "24px"
  control-gap: "10px"
  action-gap: "26px"
  paragraph: "26px"
  block: "38px"
components:
  button-primary:
    backgroundColor: "{colors.coffee-ink}"
    textColor: "{colors.harvest-gold}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 32px"
    height: "64px"
  button-primary-nav:
    backgroundColor: "{colors.coffee-ink}"
    textColor: "{colors.harvest-gold}"
    rounded: "{rounded.pill}"
    padding: "0 24px"
    height: "52px"
  chip-rider:
    backgroundColor: "transparent"
    textColor: "{colors.coffee-ink}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 22px"
    height: "56px"
  chip-rider-pressed:
    backgroundColor: "{colors.coffee-ink}"
    textColor: "{colors.burnt-orange}"
    rounded: "{rounded.pill}"
  scale-track:
    rounded: "{rounded.pill}"
    height: "22px"
    width: "560px"
  footer:
    backgroundColor: "{colors.walnut}"
    textColor: "{colors.cream}"
    padding: "72px {spacing.gutter} 48px"
---

# Design System: TripLens

## Overview

**Creative North Star: "The Harvest Kitchen"**

TripLens tells City decisions the way they would be read aloud at a 1970s Toronto kitchen table. Each scene owns the whole screen in one flat colour from the kitchen (harvest gold, avocado, burnt orange, snow white, Pyrex turquoise; walnut for the footer), and the ink flips between dark coffee brown and cream so the words always sit on the field at body-text contrast. Nothing floats on a card; the page is a stack of full-width colour courses, and the background colour itself changes as the reader scrolls (0.9s cross-fade), so the scene change is the section break.

The world's one picture is a small earth with the neighbourhood standing on its rim: a teal ocean with faint stitched wave rings, and land sewn as a patchwork quilt of farm-field patches (avocado, olive, gold, burnt orange, some with furrows) joined by cream dashed stitches, an avocado glaze edge, a dotted stoneware band, a turquoise dashed bus route, and Toronto building types standing on its rim (bay-and-gable houses, main-street shops with striped awnings, mid-rise apartments with regular window rows) set in a repeating rhythm, round trees, stops and a cream bus, with a soft ink skyline and the CN Tower behind at 16% opacity. In the winter scene white snow caps appear on every roof. It turns like a lazy Susan, one scene per scroll. Drawings are fabric appliqué: one SVG filter (#fabric) gives every shape a woven warp-and-weft grain and softly displaced cut-cloth edges, each building is sewn on with a dashed stitch line just inside its walls, and the page fields carry a faint linen weave (body::before, multiply, 22%). Never gradients, never photographs.

Density is low and type is large: the body never drops below 20px, the display face is a warm, soft-shouldered serif, and every control is a chunky pill at 56px or taller. The register is warm and plain, never alarming.

**Key Characteristics:**
- One colour field per scene; the field is the background of the whole viewport, nav included.
- Ink is either coffee brown or cream (teal ink on turquoise), chosen per field for contrast.
- Pills that invert: the primary action is always ink-on-field reversed (field-coloured text on an ink pill).
- Flat stoneware drawing language; the platter is the only illustration.
- Large, legible type: Young Serif display, Atkinson Hyperlegible body at 20px and up.
- Figures are read on one measured scale against the rider's limit.

## Colors

A 1970s kitchen palette of five saturated, slightly earthy fields and two inks, with no white and no grey anywhere.

### Primary
- **Harvest Gold** (`harvest-gold`): the opening and closing field (scenes 0 and 5) and the default field. The colour of the brand's first impression.

### Secondary
- **Avocado** (`avocado`): the "before" scene field (her short walk); also the platter's glaze edge and tree canopies in the drawing.
- **Burnt Orange** (`burnt-orange`): the "change" scene field (the stop removed, the scale bar); also roofs, the bus stripe and the removed stop's sign in the drawing.

### Tertiary
- **Walnut** (`walnut`): the footer ground.
- **Snow** (`snow`): the winter scene field, with coffee ink; snowflakes are #9fb3bd so they read on white.
- **Pyrex Turquoise** (`pyrex-turquoise`): the sources scene field; in the drawing, the bus route, bus windows, active stop signs and the walker's frame.

### Neutral
- **Coffee Ink** (`coffee-ink`): text, rules, pills and the scale fill on gold and orange fields.
- **Teal Ink** (`teal-ink`): text on the turquoise field only.
- **Cream** (`cream`): text on avocado and walnut fields and the footer; snow, windows, the bus body and the stoneware band in the drawing.
- **Stoneware** (`stoneware`): the platter rim and the second City Hall tower in the drawing. Not used for page text or fields.

Field and ink pairs as shipped: gold with coffee ink (9.1:1), avocado with cream (5.1:1), burnt orange with coffee ink (4.8:1), snow with coffee ink (about 16:1), turquoise with teal ink (5.0:1).

### Named Rules
**The One Field Rule.** A scene owns the whole screen in one field colour. Never place two fields side by side on one screen, and never set a field colour as a small accent on another field.

**The Ink Flip Rule.** Every field has exactly one ink, and everything on it (text, rules, pills, scale bar, focus ring, selection) uses that ink or that field. Ink is chosen for at least 4.5:1 at body size; secondary text uses full ink, not a faded one, on avocado, orange and turquoise.

**The Drawing Palette Rule.** The platter drawing uses the same hues, lifted slightly brighter so it reads against its own field (gold #f0c04a, orange #e07a3a, avocado #8a9b3a, turquoise #4fb0a8, walnut #5a3a22, wood #6b4428 / #7a5032, leaf shade #6f7f2c). These are drawing-only; never use them for text or page fields.

## Typography

**Display Font:** Young Serif (with Georgia, serif)
**Body Font:** Atkinson Hyperlegible (with system-ui, sans-serif)

**Character:** Young Serif is a soft, chunky, slightly bookish serif that reads like a cookbook title; Atkinson Hyperlegible is built for low-vision readers and keeps every number and letter unambiguous. Both are self-hosted woff2 files (Young Serif 400; Atkinson 400 and 700).

### Hierarchy
- **Display** (400, clamp(46px, 5vw, 80px), 1.04, -0.015em, balanced wrap): the single page headline, two lines.
- **Headline** (400, clamp(38px, 4vw, 62px), 1.04): each scene's title, written as a short plain sentence.
- **Figure** (Young Serif 400, clamp(56px, 5.6vw, 92px), 1, lining tabular numerals): the one big number in a scene; its unit follows in Atkinson 700 at clamp(22px, 2vw, 30px).
- **Quote** (Young Serif 400, clamp(24px, 2vw, 32px), 1.3, max 28ch): verbatim source quotations.
- **Body** (Atkinson 400, clamp(20px, 1.4vw, 22px), 1.6, max 34ch in scenes): all running text; the opening sentence is 22px.
- **Label** (Atkinson 700, clamp(20px, 1.5vw, 23px)): button and pill labels, inline emphasis, the text-link action.

### Named Rules
**The Twenty Pixel Floor Rule.** Running text, notes, sources and labels are 20px or larger. Smaller sizes appear only on aria-hidden decoration (scale tick numbers, 16px).

**The Sentence Headline Rule.** Headlines are full plain sentences with a full stop, in sentence case. No small labels or eyebrows above them.

## Layout

A 12-column grid (column gap 24px) inside a fluid side gutter of clamp(18px, 4.5vw, 72px). Each scene is at least one viewport tall (100svh), with its text block in columns 1 to 5 (1 to 7 for the opening) and top padding of clamp(120px, 17svh, 170px) to clear the fixed nav. The platter is a fixed full-viewport SVG behind the text: on desktop its centre sits on the bottom edge at 80% across, lower half off screen; the text stays left, the drawing stays right.

At 860px and below the grid collapses to one column, the text block takes the field as its own background (so text never overlaps the drawing), scenes drop their minimum height and leave about 58svh beneath the text for the platter, which centres and widens to nearly the full screen width. The nav button hides its label and keeps its arrow.

Vertical rhythm inside a scene: 26px between headline and paragraphs, 30px before a figure or quote, 38px before the action row; actions sit 26px apart; pills sit 10px apart.

The footer is a walnut course on the same 12-column grid: link list in columns 1 to 5, small print in columns 7 to 12.

## Elevation & Depth

Flat. There are no drop shadows, gradients or blurs on page elements. Depth comes from the fixed platter sitting behind the scrolling text layer and from the field colour changing underneath everything. The only shadow-like device is a 3px solid ink ring around the scale bar's "was" marker, which acts as an outline, not an elevation.

### Named Rules
**The Sewn Cloth Rule.** Surfaces are flat colour with a woven grain, never glossy or shaded. Lift is expressed by motion (a pill rises 3px on hover), never by a shadow.

## Shapes

Everything is rounded and soft. Controls are full pills (999px). The focus ring is a 4px ink outline offset 4px with 12px corners. In the drawing, buildings use 7px corner radii, windows and doors are rounded slots, roofs are single quadratic domes or rounded slabs, trees are circles on rounded trunks. Dashed and dotted lines carry meaning: the turquoise dashed ring is the bus route, dotted arcs are walks (cream for before, coffee brown for after), and the scale bar's limit is a 4px dashed ink line.

## Components

### Buttons
Big, warm and unmistakable; the one action on every screen.
- **Shape:** full pill (999px), 64px tall, 32px side padding, an inline arrow icon (26px, 2.6 stroke, round caps) after the label.
- **Primary:** ink background, field-coloured label, so the pill always inverts its scene and changes colour with it.
- **Hover / Focus:** rises 3px and the arrow slides 4px right (0.2s, the house ease); presses down 1px on active; 4px ink focus ring.
- **Nav variant:** same pill at 52px tall, 24px padding, 18px label; on phones the label hides and the arrow remains.
- **Text action:** a second, quieter action beside the pill is a bold underlined link (2px underline, 5px offset), never a second pill.

### Chips (rider choice)
- **Style:** 56px pill, 3px ink border, transparent fill, ink label in Atkinson 700 at 19px.
- **State:** pressed fills with ink and turns the label field-coloured, so the state never depends on colour alone (aria-pressed). Hover rises 2px.

### Navigation
A fixed bar across the top in the current field colour (it cross-fades with the scene), with the wordmark left (Young Serif 30px beside a 34px platter mark) and the primary pill right.

### Scale bar (signature)
Every distance is read on one measured bar against the rider's limit. A 22px pill track in ink at 18% over the field, an ink fill for the walk now, a 6px field-coloured "was" marker ringed in ink for the walk before, and a 4px dashed ink line for the limit labelled "limit N m" above it in bold. Tick numbers 0 to 600 m sit underneath. Marker and fill move with a 0.6s ease when the rider changes. A plain-sentence verdict (with the metres in bold) follows below and is the accessible equivalent; the bar itself is aria-hidden.

### The platter (signature)
The single illustration: a fixed SVG platter that rotates to a new angle and zooms per scene, with a cream bus driving round the rim. Scene state is carried by the drawing too (the removed stop's sign shrinks away, a ring and cross mark its spot, before and after walks appear). It carries a text description (role="img" with aria-label). With reduced motion, rotation snaps and the bus and snow stop.

### Footer
A walnut course with cream ink: navigation links set in Young Serif at clamp(28px, 2.4vw, 38px), and the honest small print (prototype status, data sources, limits) in body text.

## Do's and Don'ts

### Do:
- **Do** give each scene one full-screen field from the palette and flip the ink to the shipped pair for that field.
- **Do** make the primary action a 64px ink pill with field-coloured text and an arrow, one per screen.
- **Do** keep running text at 20px or larger in Atkinson Hyperlegible, and headlines as plain sentences in Young Serif.
- **Do** show any distance against the rider's limit on the scale bar, with a plain-sentence verdict beside it.
- **Do** draw in flat, rounded stoneware shapes using the drawing palette, with a text description.
- **Do** honour reduced motion: colour changes and the platter snap rather than ease.

### Don't:
- **Don't** use white, grey, or a white civic page with a headline, button and three feature cards.
- **Don't** add drop shadows, gradients, glass or blur to page elements.
- **Don't** put small labels or eyebrows above headlines.
- **Don't** use faded or translucent ink for text on avocado, orange or turquoise fields.
- **Don't** bring outline-style icon sets or glyph icons into this world; the platter drawing and the inline SVG arrow are the vocabulary.
