"""
光州事件 — 單頁 PPT 生成器
使用 python-pptx，16:9 (33.87 × 19.05 cm)
"""
from pptx import Presentation
from pptx.util import Cm, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Inches
import copy
from lxml import etree
import math

# ── Colours ──────────────────────────────────────────────────────────
BLACK   = RGBColor(0x11, 0x11, 0x11)
DARKRED = RGBColor(0x7A, 0x1F, 0x1F)
CREAM   = RGBColor(0xF5, 0xF1, 0xE8)
GREY    = RGBColor(0x5B, 0x67, 0x70)
DIM     = RGBColor(0x2A, 0x20, 0x18)       # dim warm brown for image bg
DIMCITY = RGBColor(0x0e, 0x0b, 0x08)       # silhouette colour

# ── Slide dimensions (16:9) ───────────────────────────────────────────
W = Cm(33.867)   # 1920 pt equivalent
H = Cm(19.05)    # 1080 pt equivalent

prs = Presentation()
prs.slide_width  = W
prs.slide_height = H

blank_layout = prs.slide_layouts[6]   # completely blank
slide = prs.slides.add_slide(blank_layout)
shapes = slide.shapes

# ─────────────────────────────────────────────────────────────────────
# Helper: add solid-filled rectangle
# ─────────────────────────────────────────────────────────────────────
def add_rect(slide, x, y, w, h, fill_rgb, alpha=None):
    shape = slide.shapes.add_shape(1, x, y, w, h)   # MSO_SHAPE_TYPE.RECTANGLE = 1
    shape.line.fill.background()
    shape.line.width = 0
    fill = shape.fill
    fill.solid()
    fill.fore_color.rgb = fill_rgb
    if alpha is not None:
        # set lumMod/lumOff via XML for transparency workaround
        # python-pptx uses alpha on fore_color via _xFill
        sp = shape._element
        spPr = sp.find(qn('p:spPr'))
        solidFill = spPr.find('.//' + qn('a:solidFill'))
        srgbClr   = solidFill.find(qn('a:srgbClr'))
        if srgbClr is not None:
            alpha_elem = etree.SubElement(srgbClr, qn('a:alpha'))
            alpha_elem.set('val', str(int(alpha * 100000)))
    return shape

# ─────────────────────────────────────────────────────────────────────
# Helper: add text box
# ─────────────────────────────────────────────────────────────────────
def add_text(slide, text, x, y, w, h,
             size_pt, bold=False, color=CREAM,
             align=PP_ALIGN.LEFT, spacing_pt=None,
             font_name='Noto Sans TC'):
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = False
    p  = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size  = Pt(size_pt)
    run.font.bold  = bold
    run.font.color.rgb = color
    run.font.name  = font_name
    if spacing_pt:
        pPr = p._pPr
        if pPr is None:
            pPr = p._p.get_or_add_pPr()
        pPr.set('spc', str(int(spacing_pt * 100)))
    return tb

# ─────────────────────────────────────────────────────────────────────
# Helper: add line (via connector)
# ─────────────────────────────────────────────────────────────────────
def add_line(slide, x1, y1, x2, y2, color_rgb, width_pt=0.75):
    from pptx.util import Pt as PtU
    from pptx.enum.shapes import MSO_CONNECTOR
    conn = slide.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, x1, y1, x2, y2)
    conn.line.color.rgb = color_rgb
    conn.line.width = Pt(width_pt)
    return conn

# ═════════════════════════════════════════════════════════════════════
# 1. BACKGROUND
# ═════════════════════════════════════════════════════════════════════
add_rect(slide, 0, 0, W, H, BLACK)

# Subtle warm-tinted overlay to break pure black
add_rect(slide, 0, 0, W, H, RGBColor(0x18, 0x12, 0x0e), alpha=0.25)

# ═════════════════════════════════════════════════════════════════════
# 2. LEFT ACCENT BAR
# ═════════════════════════════════════════════════════════════════════
add_rect(slide, 0, 0, Cm(0.22), H, DARKRED)

# ═════════════════════════════════════════════════════════════════════
# 3. HEADER  (top ~19% ≈ 3.6 cm)
# ═════════════════════════════════════════════════════════════════════
HEADER_H = Cm(3.7)

# Faint header background
add_rect(slide, 0, 0, W, HEADER_H, RGBColor(0x16, 0x10, 0x0e), alpha=0.4)

# Main title
add_text(slide, '光州事件',
         x=Cm(1.5), y=Cm(0.55), w=Cm(18), h=Cm(1.9),
         size_pt=44, bold=True, color=CREAM)

# Dark-red rule under title
add_rect(slide, Cm(1.5), Cm(2.55), Cm(3.8), Cm(0.08), DARKRED)

# Subtitle
add_text(slide, '1980  韓國民主化運動時間軸',
         x=Cm(1.5), y=Cm(2.75), w=Cm(22), h=Cm(0.75),
         size_pt=12, bold=False, color=GREY)

# Header bottom border line
add_line(slide, 0, HEADER_H, W, HEADER_H,
         color_rgb=RGBColor(0x7A, 0x1F, 0x1F), width_pt=0.6)

# Year watermark (faint, top-right)
add_text(slide, '1980',
         x=Cm(26), y=Cm(0.2), w=Cm(7), h=Cm(3.5),
         size_pt=72, bold=True,
         color=RGBColor(0x2a, 0x09, 0x09))

# ═════════════════════════════════════════════════════════════════════
# 4. TIMELINE  (left 55%)
# ═════════════════════════════════════════════════════════════════════
TL_X     = Cm(1.5)          # panel left edge
SPINE_X  = Cm(5.0)          # centre of vertical spine
TL_TOP   = HEADER_H + Cm(0.65)
TL_BOT   = H - Cm(1.1)
TL_WIDTH = W * 0.55          # 55% of slide width

# Vertical spine
add_line(slide, SPINE_X, TL_TOP, SPINE_X, TL_BOT,
         color_rgb=RGBColor(0x44, 0x3e, 0x38), width_pt=0.75)

events = [
    ("1979.10.26", "二六事件（朴正熙遇刺）", False),
    ("1979.12.12", "雙十二政變",              False),
    ("1980.05.14–16", "漢城之春大遊行",        False),
    ("1980.05.17",  "五一七擴大戒嚴",           False),
    ("1980.05.18",  "光州民主化運動爆發",       True),
    ("1980.05.21",  "全羅南道廳前開槍",        True),
    ("1980.05.22–26", "光州短暫自治",           False),
    ("1980.05.27",  "尚武忠正作戰",             True),
]

n = len(events)
usable_h = TL_BOT - TL_TOP
step = usable_h / (n - 1)

for i, (date, event_name, is_key) in enumerate(events):
    cy = TL_TOP + i * step   # vertical centre for this event

    # Dot on spine
    dot_r = Cm(0.18) if is_key else Cm(0.14)
    dot_color = DARKRED if is_key else RGBColor(0x5B, 0x67, 0x70)
    add_rect(slide,
             SPINE_X - dot_r, cy - dot_r,
             dot_r * 2, dot_r * 2,
             dot_color)

    # Horizontal tick to text
    TICK_END = SPINE_X + Cm(0.55)
    add_line(slide, SPINE_X, cy, TICK_END, cy,
             color_rgb=RGBColor(0x3a, 0x34, 0x2e), width_pt=0.5)

    # Date label
    date_color = CREAM if is_key else RGBColor(0x7a, 0x8a, 0x94)
    date_size  = 10.5 if is_key else 9.5
    add_text(slide, date,
             x=TICK_END + Cm(0.15),
             y=cy - Cm(0.4),
             w=Cm(4.5), h=Cm(0.5),
             size_pt=date_size, bold=is_key, color=date_color)

    # Event name
    event_color = CREAM if is_key else RGBColor(0xa8, 0xa0, 0x94)
    event_size  = 10 if is_key else 9
    add_text(slide, event_name,
             x=TICK_END + Cm(0.15),
             y=cy + Cm(0.06),
             w=Cm(10), h=Cm(0.5),
             size_pt=event_size, bold=False, color=event_color)

# ═════════════════════════════════════════════════════════════════════
# 5. PANEL DIVIDER (vertical line between timeline and image)
# ═════════════════════════════════════════════════════════════════════
DIV_X = W * 0.55
add_line(slide, DIV_X, HEADER_H + Cm(0.3), DIV_X, H - Cm(1.1),
         color_rgb=RGBColor(0x55, 0x18, 0x18), width_pt=0.6)

# ═════════════════════════════════════════════════════════════════════
# 6. IMAGE PANEL — cinematic background + scene
# ═════════════════════════════════════════════════════════════════════
IMG_X = DIV_X + Cm(0.05)
IMG_W = W - IMG_X
IMG_Y = HEADER_H
IMG_H = H - HEADER_H - Cm(1.05)

# Warm dark background
add_rect(slide, IMG_X, IMG_Y, IMG_W, IMG_H, RGBColor(0x14, 0x10, 0x0c))

# Subtle radial warm glow at centre (simulated with a smaller lighter rect)
add_rect(slide,
         IMG_X + IMG_W * 0.2, IMG_Y + IMG_H * 0.1,
         IMG_W * 0.6, IMG_H * 0.6,
         RGBColor(0x2a, 0x20, 0x16), alpha=0.45)

# Dark overlay (40%)
add_rect(slide, IMG_X, IMG_Y, IMG_W, IMG_H,
         RGBColor(0x00, 0x00, 0x00), alpha=0.40)

# City skyline — a row of rectangles at the bottom of the image area
GROUND_Y = IMG_Y + IMG_H - Cm(1.6)
CITY_COLOR = RGBColor(0x0b, 0x09, 0x07)

buildings = [
    # (rel_x %, width_cm, height_cm)
    (0.02, 0.9, 2.8),
    (0.08, 1.2, 3.8),
    (0.16, 0.8, 2.5),
    (0.21, 1.4, 4.4),
    (0.30, 0.9, 3.0),
    (0.37, 1.1, 3.6),
    (0.45, 0.8, 2.4),
    (0.51, 1.3, 4.0),
    (0.59, 1.0, 3.2),
    (0.66, 1.5, 4.8),
    (0.75, 0.9, 2.9),
    (0.81, 1.2, 3.5),
    (0.88, 1.0, 2.7),
    (0.93, 1.1, 3.3),
]
for rx, bw, bh in buildings:
    bx = IMG_X + IMG_W * rx
    by = GROUND_Y - Cm(bh)
    add_rect(slide, bx, by, Cm(bw), Cm(bh), CITY_COLOR)

# Ground strip
add_rect(slide, IMG_X, GROUND_Y, IMG_W, Cm(0.35), RGBColor(0x09, 0x07, 0x05))

# Crowd silhouettes — small rectangles as figure bodies
CROWD_Y = GROUND_Y - Cm(0.35)
for k in range(18):
    fx = IMG_X + IMG_W * 0.05 + k * (IMG_W * 0.055)
    # head
    add_rect(slide, fx,           CROWD_Y - Cm(0.55), Cm(0.22), Cm(0.22), CITY_COLOR)
    # body
    add_rect(slide, fx - Cm(0.06), CROWD_Y - Cm(0.33), Cm(0.3),  Cm(0.33), CITY_COLOR)

# Bottom gradient fill (vignette)
add_rect(slide, IMG_X, IMG_Y + IMG_H - Cm(2.5), IMG_W, Cm(2.5),
         RGBColor(0x00, 0x00, 0x00), alpha=0.55)

# Caption box
CAP_Y = IMG_Y + IMG_H - Cm(1.8)
add_text(slide, '《我只是個計程車司機》',
         x=IMG_X, y=CAP_Y,
         w=IMG_W, h=Cm(0.75),
         size_pt=14, bold=True, color=CREAM,
         align=PP_ALIGN.CENTER)

add_text(slide, 'A Taxi Driver  ｜  韓國電影（2017）',
         x=IMG_X, y=CAP_Y + Cm(0.72),
         w=IMG_W, h=Cm(0.55),
         size_pt=10, bold=False, color=GREY,
         align=PP_ALIGN.CENTER)

# ═════════════════════════════════════════════════════════════════════
# 7. FOOTER
# ═════════════════════════════════════════════════════════════════════
FOOTER_Y = H - Cm(1.05)

# Footer top border
add_line(slide, 0, FOOTER_Y, W, FOOTER_Y,
         color_rgb=RGBColor(0x55, 0x18, 0x18), width_pt=0.6)

# Quote
add_text(slide,
         '「民主並非憑空而來，而是有人曾為它流血。」',
         x=0, y=FOOTER_Y + Cm(0.15),
         w=W, h=Cm(0.75),
         size_pt=11, bold=False,
         color=RGBColor(0x88, 0x78, 0x68),
         align=PP_ALIGN.CENTER)

# ═════════════════════════════════════════════════════════════════════
# SAVE
# ═════════════════════════════════════════════════════════════════════
out = '/home/user/gospel-signup/gwangju-incident.pptx'
prs.save(out)
print(f'Saved → {out}')
