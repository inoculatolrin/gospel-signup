"""
Generate 光州事件 (Gwangju Incident) single-page PPT
Style: historical documentary, heavy realism
"""

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import io
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
import random

# ── Palette ──────────────────────────────────────────────────────────────────
BLACK   = RGBColor(0x11, 0x11, 0x11)
DARKRED = RGBColor(0x7A, 0x1F, 0x1F)
CREAM   = RGBColor(0xF5, 0xF1, 0xE8)
GREYBLUE= RGBColor(0x5B, 0x67, 0x70)
WHITE   = RGBColor(0xFF, 0xFF, 0xFF)
DIM_RED = RGBColor(0x9B, 0x2C, 0x2C)
GOLD    = RGBColor(0xC8, 0xA9, 0x2E)
LINE_CLR= RGBColor(0xCC, 0xCC, 0xCC)

# ── Slide dimensions (16:9 widescreen) ───────────────────────────────────────
W = Inches(13.33)
H = Inches(7.5)

# ── Timeline events ───────────────────────────────────────────────────────────
EVENTS = [
    ("1979.10.26", "朴正熙遇刺（10.26事件）"),
    ("1979.12.12", "雙十二政變"),
    ("1980.05.14–16", "漢城之春大遊行"),
    ("1980.05.17", "五一七擴大戒嚴"),
    ("1980.05.18", "光州民主化運動爆發"),
    ("1980.05.21", "全羅南道廳前開槍鎮壓"),
    ("1980.05.22–26", "光州短暫自治"),
    ("1980.05.27", "尚武忠正作戰"),
]

# ─────────────────────────────────────────────────────────────────────────────
# Helper: create grainy newspaper-texture background image
# ─────────────────────────────────────────────────────────────────────────────

def make_background(px_w=1920, px_h=1080):
    rng = random.Random(42)
    img = Image.new("RGB", (px_w, px_h), (17, 17, 17))
    px = img.load()

    # subtle grain
    for y in range(px_h):
        for x in range(px_w):
            n = rng.randint(-12, 12)
            r, g, b = px[x, y]
            px[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )

    # subtle vignette
    draw = ImageDraw.Draw(img)
    for i in range(60):
        alpha = int(80 * (1 - i / 60))
        col = (0, 0, 0, alpha)
        draw = ImageDraw.Draw(img.convert("RGBA"))
    img = img.filter(ImageFilter.GaussianBlur(radius=0.4))
    return img


def pil_to_stream(img: Image.Image, fmt="PNG") -> io.BytesIO:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    buf.seek(0)
    return buf


# ─────────────────────────────────────────────────────────────────────────────
# Helper: movie-poster placeholder image (dark green taxi)
# ─────────────────────────────────────────────────────────────────────────────

def make_movie_placeholder(pw=600, ph=780):
    img = Image.new("RGB", (pw, ph), (20, 35, 20))
    draw = ImageDraw.Draw(img)

    # gradient-ish dark overlay bands
    for y in range(ph):
        t = y / ph
        r = int(15 + 10 * t)
        g = int(30 + 15 * t)
        b = int(15 + 10 * t)
        draw.line([(0, y), (pw, y)], fill=(r, g, b))

    # taxi silhouette (simple rectangle shapes)
    # body
    draw.rectangle([60, 340, 540, 480], fill=(30, 80, 30))
    # roof
    draw.rectangle([140, 270, 460, 345], fill=(25, 65, 25))
    # windows
    draw.rectangle([155, 285, 270, 340], fill=(60, 90, 60))
    draw.rectangle([330, 285, 445, 340], fill=(60, 90, 60))
    # wheels
    draw.ellipse([80, 460, 180, 510],  fill=(15, 15, 15))
    draw.ellipse([420, 460, 520, 510], fill=(15, 15, 15))
    # dark overlay (40%)
    overlay = Image.new("RGBA", (pw, ph), (0, 0, 0, 100))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay).convert("RGB")

    # grain
    rng = random.Random(7)
    pix = img.load()
    for y in range(ph):
        for x in range(pw):
            n = rng.randint(-8, 8)
            r, g, b = pix[x, y]
            pix[x, y] = (
                max(0, min(255, r + n)),
                max(0, min(255, g + n)),
                max(0, min(255, b + n)),
            )

    return img


# ─────────────────────────────────────────────────────────────────────────────
# Add text box helper
# ─────────────────────────────────────────────────────────────────────────────

def add_text(slide, text, left, top, width, height,
             font_size=12, bold=False, color=CREAM,
             align=PP_ALIGN.LEFT, italic=False):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = "Noto Sans TC"
    return txBox


def add_multiline(slide, lines, left, top, width, height,
                  font_size=12, bold=False, color=CREAM,
                  align=PP_ALIGN.LEFT, line_spacing_pt=None):
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        if line_spacing_pt:
            from pptx.util import Pt as Pt2
            from pptx.oxml.ns import qn
            from lxml import etree
            pPr = p._pPr
            if pPr is None:
                pPr = p._p.get_or_add_pPr()
            lnSpc = etree.SubElement(pPr, qn("a:lnSpc"))
            spcPts = etree.SubElement(lnSpc, qn("a:spcPts"))
            spcPts.set("val", str(int(line_spacing_pt * 100)))
        run = p.add_run()
        run.text = line
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = "Noto Sans TC"
    return txBox


# ─────────────────────────────────────────────────────────────────────────────
# MAIN BUILD
# ─────────────────────────────────────────────────────────────────────────────

def build():
    prs = Presentation()
    prs.slide_width  = W
    prs.slide_height = H

    blank_layout = prs.slide_layouts[6]  # completely blank
    slide = prs.slides.add_slide(blank_layout)

    # ── 1. Background ──────────────────────────────────────────────────────
    bg_img = make_background(1920, 1080)
    bg_stream = pil_to_stream(bg_img)
    slide.shapes.add_picture(
        bg_stream, Inches(0), Inches(0), W, H
    )

    # ── 2. Dark-red accent bar on top ──────────────────────────────────────
    bar = slide.shapes.add_shape(
        1,  # MSO_SHAPE_TYPE.RECTANGLE
        Inches(0), Inches(0), W, Inches(0.06)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = DARKRED
    bar.line.fill.background()

    # ── 3. Thin horizontal separator under title zone ──────────────────────
    sep = slide.shapes.add_shape(
        1, Inches(0.35), Inches(1.65), Inches(7.0), Inches(0.015)
    )
    sep.fill.solid()
    sep.fill.fore_color.rgb = DARKRED
    sep.line.fill.background()

    # ── 4. Title block (top 20%) ───────────────────────────────────────────
    add_text(slide, "光州事件",
             Inches(0.4), Inches(0.12),
             Inches(8), Inches(0.9),
             font_size=42, bold=True, color=CREAM)

    add_text(slide, "1980 韓國民主化運動時間軸",
             Inches(0.4), Inches(0.95),
             Inches(8), Inches(0.5),
             font_size=16, bold=False, color=GREYBLUE)

    # ── 5. Vertical timeline (left 55%) ───────────────────────────────────
    TL_X = Inches(0.55)          # x of the timeline line
    TL_TOP = Inches(1.85)
    TL_BOT = Inches(7.1)
    TL_H = TL_BOT - TL_TOP
    N = len(EVENTS)
    step = TL_H / (N - 1)

    # draw the vertical line
    line_shape = slide.shapes.add_shape(
        1, TL_X, TL_TOP, Inches(0.015), TL_H
    )
    line_shape.fill.solid()
    line_shape.fill.fore_color.rgb = LINE_CLR
    line_shape.line.fill.background()

    for i, (date, event) in enumerate(EVENTS):
        y = TL_TOP + step * i

        # dot
        dot_r = Inches(0.1)
        dot = slide.shapes.add_shape(
            9,  # oval
            TL_X - dot_r / 2 + Inches(0.015) / 2,
            y - dot_r / 2,
            dot_r, dot_r
        )
        dot.fill.solid()
        dot.fill.fore_color.rgb = DARKRED
        dot.line.color.rgb = CREAM
        dot.line.width = Pt(0.5)

        # date label
        add_text(slide, date,
                 TL_X + Inches(0.2), y - Inches(0.22),
                 Inches(2.0), Inches(0.28),
                 font_size=11, bold=True, color=CREAM)

        # event label
        add_text(slide, event,
                 TL_X + Inches(0.2), y + Inches(0.06),
                 Inches(5.8), Inches(0.28),
                 font_size=12, bold=False, color=GREYBLUE)

    # ── 6. Vertical divider between timeline & image area ──────────────────
    div = slide.shapes.add_shape(
        1, Inches(7.15), Inches(1.72), Inches(0.015), Inches(5.5)
    )
    div.fill.solid()
    div.fill.fore_color.rgb = RGBColor(0x44, 0x44, 0x44)
    div.line.fill.background()

    # ── 7. Movie poster area (right 45%) ──────────────────────────────────
    POSTER_L = Inches(7.35)
    POSTER_T = Inches(1.72)
    POSTER_W = Inches(5.6)
    POSTER_H = Inches(4.9)

    poster = make_movie_placeholder(600, 780)
    poster_stream = pil_to_stream(poster)
    slide.shapes.add_picture(
        poster_stream, POSTER_L, POSTER_T, POSTER_W, POSTER_H
    )

    # dark overlay rectangle on poster
    ov = slide.shapes.add_shape(
        1, POSTER_L, POSTER_T, POSTER_W, POSTER_H
    )
    ov.fill.solid()
    ov.fill.fore_color.rgb = RGBColor(0x00, 0x00, 0x00)
    from pptx.util import Pt as Pt2
    ov.fill.fore_color.theme_color  # keep solid
    # set transparency via XML
    from lxml import etree
    from pptx.oxml.ns import qn
    solidFill = ov.fill._xPr.find(qn("a:solidFill"))
    if solidFill is not None:
        srgbClr = solidFill.find(qn("a:srgbClr"))
        if srgbClr is None:
            srgbClr = solidFill.find(qn("a:sysClr"))
        if srgbClr is not None:
            alpha = etree.SubElement(srgbClr, qn("a:alpha"))
            alpha.set("val", "60000")  # 60 000 / 100 000 = 60% opaque → 40% visible
    ov.line.fill.background()

    # Movie title overlay text on poster
    add_text(slide, "《我只是個計程車司機》",
             POSTER_L + Inches(0.2),
             POSTER_T + POSTER_H - Inches(1.1),
             POSTER_W - Inches(0.4), Inches(0.4),
             font_size=15, bold=True, color=CREAM)

    add_text(slide, "《A Taxi Driver》　韓國電影 2017",
             POSTER_L + Inches(0.2),
             POSTER_T + POSTER_H - Inches(0.65),
             POSTER_W - Inches(0.4), Inches(0.35),
             font_size=11, bold=False, color=GREYBLUE, italic=True)

    # ── 8. Right-side context text ─────────────────────────────────────────
    INFO_L = Inches(7.35)
    INFO_T = POSTER_T + POSTER_H + Inches(0.18)

    context_lines = [
        "此片以光州事件為背景，描述一位首爾計程車司機",
        "載運德國記者秘密進入光州，目睹鎮壓現場的故事。",
    ]
    add_multiline(slide, context_lines,
                  INFO_L, INFO_T,
                  Inches(5.6), Inches(0.7),
                  font_size=10, color=GREYBLUE)

    # ── 9. Bottom quote ────────────────────────────────────────────────────
    QUOTE_Y = Inches(7.05)
    # thin red line above quote
    qline = slide.shapes.add_shape(
        1, Inches(0.35), QUOTE_Y - Inches(0.08),
        W - Inches(0.7), Inches(0.012)
    )
    qline.fill.solid()
    qline.fill.fore_color.rgb = DARKRED
    qline.line.fill.background()

    add_text(slide,
             "「民主並非憑空而來，而是有人曾為它流血。」",
             Inches(0.35), QUOTE_Y,
             W - Inches(0.7), Inches(0.38),
             font_size=12, bold=False, color=CREAM,
             align=PP_ALIGN.CENTER, italic=True)

    # ── Save ───────────────────────────────────────────────────────────────
    out = "/home/user/gospel-signup/gwangju_incident.pptx"
    prs.save(out)
    print(f"Saved → {out}")


if __name__ == "__main__":
    build()
