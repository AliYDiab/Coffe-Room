from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, JpegImagePlugin  # noqa: F401

try:
    from bidi.algorithm import get_display
except ImportError:
    get_display = None


BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "static" / "loyalty_cards"
ICON_PATH = BASE_DIR / "CoffeRoom.ico"

# Standard business-card size at 300 DPI.
CARD_W, CARD_H = 1050, 600
RADIUS = 46

CREAM = "#fff8e8"
WARM = "#f3ead7"
GOLD = "#f5c400"
GOLD_DARK = "#c99700"
INK = "#15100a"
COFFEE = "#3b2e1c"
LINE = "#d3bf83"
MUTED = "#725a34"
WHITE = "#ffffff"
SOFT_WHITE = "#fffdf6"
SHADOW = "#eadcbf"


ARABIC_FORMS = {
    "ء": ("ﺀ", "ﺀ", "ﺀ", "ﺀ"),
    "آ": ("ﺁ", "ﺂ", "ﺁ", "ﺂ"),
    "أ": ("ﺃ", "ﺄ", "ﺃ", "ﺄ"),
    "ؤ": ("ﺅ", "ﺆ", "ﺅ", "ﺆ"),
    "إ": ("ﺇ", "ﺈ", "ﺇ", "ﺈ"),
    "ئ": ("ﺉ", "ﺊ", "ﺋ", "ﺌ"),
    "ا": ("ﺍ", "ﺎ", "ﺍ", "ﺎ"),
    "ب": ("ﺏ", "ﺐ", "ﺑ", "ﺒ"),
    "ة": ("ﺓ", "ﺔ", "ﺓ", "ﺔ"),
    "ت": ("ﺕ", "ﺖ", "ﺗ", "ﺘ"),
    "ث": ("ﺙ", "ﺚ", "ﺛ", "ﺜ"),
    "ج": ("ﺝ", "ﺞ", "ﺟ", "ﺠ"),
    "ح": ("ﺡ", "ﺢ", "ﺣ", "ﺤ"),
    "خ": ("ﺥ", "ﺦ", "ﺧ", "ﺨ"),
    "د": ("ﺩ", "ﺪ", "ﺩ", "ﺪ"),
    "ذ": ("ﺫ", "ﺬ", "ﺫ", "ﺬ"),
    "ر": ("ﺭ", "ﺮ", "ﺭ", "ﺮ"),
    "ز": ("ﺯ", "ﺰ", "ﺯ", "ﺰ"),
    "س": ("ﺱ", "ﺲ", "ﺳ", "ﺴ"),
    "ش": ("ﺵ", "ﺶ", "ﺷ", "ﺸ"),
    "ص": ("ﺹ", "ﺺ", "ﺻ", "ﺼ"),
    "ض": ("ﺽ", "ﺾ", "ﺿ", "ﻀ"),
    "ط": ("ﻁ", "ﻂ", "ﻃ", "ﻄ"),
    "ظ": ("ﻅ", "ﻆ", "ﻇ", "ﻈ"),
    "ع": ("ﻉ", "ﻊ", "ﻋ", "ﻌ"),
    "غ": ("ﻍ", "ﻎ", "ﻏ", "ﻐ"),
    "ف": ("ﻑ", "ﻒ", "ﻓ", "ﻔ"),
    "ق": ("ﻕ", "ﻖ", "ﻗ", "ﻘ"),
    "ك": ("ﻙ", "ﻚ", "ﻛ", "ﻜ"),
    "ل": ("ﻝ", "ﻞ", "ﻟ", "ﻠ"),
    "م": ("ﻡ", "ﻢ", "ﻣ", "ﻤ"),
    "ن": ("ﻥ", "ﻦ", "ﻧ", "ﻨ"),
    "ه": ("ﻩ", "ﻪ", "ﻫ", "ﻬ"),
    "و": ("ﻭ", "ﻮ", "ﻭ", "ﻮ"),
    "ى": ("ﻯ", "ﻰ", "ﻯ", "ﻰ"),
    "ي": ("ﻱ", "ﻲ", "ﻳ", "ﻴ"),
}

RIGHT_JOINING = set("آأؤإادذرزوىةء")
DUAL_JOINING = set(ARABIC_FORMS) - RIGHT_JOINING


def font(size, bold=False):
    names = (
        ["C:/Windows/Fonts/tahomabd.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/tahoma.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


def latin_font(size, bold=False):
    names = (
        ["C:/Windows/Fonts/segoeuib.ttf", "C:/Windows/Fonts/arialbd.ttf"]
        if bold
        else ["C:/Windows/Fonts/segoeui.ttf", "C:/Windows/Fonts/arial.ttf"]
    )
    for name in names:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    return ImageFont.load_default()


FONTS = {
    "brand": font(60, True),
    "brand_en": latin_font(56, True),
    "title": font(44, True),
    "subtitle": font(25, True),
    "body": font(22),
    "small": font(19),
    "tiny": font(16),
    "box": font(20, True),
}


def is_arabic_char(ch):
    return ch in ARABIC_FORMS


def can_join_left(ch):
    return ch in DUAL_JOINING


def can_join_right(ch):
    return ch in DUAL_JOINING or ch in RIGHT_JOINING


def shape_arabic(text):
    chars = list(text)
    shaped = []
    for i, ch in enumerate(chars):
        if not is_arabic_char(ch):
            shaped.append(ch)
            continue

        prev_ch = chars[i - 1] if i > 0 else ""
        next_ch = chars[i + 1] if i + 1 < len(chars) else ""
        connect_prev = is_arabic_char(prev_ch) and can_join_left(prev_ch) and can_join_right(ch)
        connect_next = is_arabic_char(next_ch) and can_join_left(ch) and can_join_right(next_ch)

        isolated, final, initial, medial = ARABIC_FORMS[ch]
        if connect_prev and connect_next:
            shaped.append(medial)
        elif connect_prev:
            shaped.append(final)
        elif connect_next:
            shaped.append(initial)
        else:
            shaped.append(isolated)
    display_text = "".join(shaped)
    return get_display(display_text) if get_display else display_text[::-1]


def ar(text):
    return shape_arabic(text)


def rounded_card():
    img = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, CARD_W - 1, CARD_H - 1), RADIUS, fill=CREAM)
    return img


def draw_text_center(draw, box, text, fill, text_font):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=text_font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - 2), text, fill=fill, font=text_font)


def draw_text_right(draw, right_x, y, text, fill, text_font):
    shaped = ar(text)
    bbox = draw.textbbox((0, 0), shaped, font=text_font)
    draw.text((right_x - (bbox[2] - bbox[0]), y), shaped, fill=fill, font=text_font)


def draw_text_center_ar(draw, box, text, fill, text_font):
    draw_text_center(draw, box, ar(text), fill, text_font)


def logo_image(size):
    icon = Image.open(ICON_PATH)
    try:
        frame = icon.ico.getimage(max(icon.ico.sizes(), key=lambda s: s[0] * s[1]))
    except Exception:
        frame = icon
    frame = frame.convert("RGBA")
    frame.thumbnail((size, size), Image.Resampling.LANCZOS)
    return frame


def add_logo(draw_img, x, y, size):
    logo = logo_image(size)
    draw_img.alpha_composite(logo, (x, y))


def draw_cut_guides(draw):
    margin = 18
    draw.rounded_rectangle(
        (margin, margin, CARD_W - margin, CARD_H - margin),
        RADIUS - 12,
        outline=LINE,
        width=3,
    )


def make_front():
    img = rounded_card()
    draw = ImageDraw.Draw(img)
    draw_cut_guides(draw)

    draw.rounded_rectangle((36, 36, CARD_W - 36, 158), 26, fill=SOFT_WHITE, outline=LINE, width=2)
    add_logo(img, 864, 52, 82)
    draw.text((492, 62), "Coffe Room", fill=INK, font=FONTS["brand_en"])
    draw.rounded_rectangle((382, 116, 474, 126), 5, fill=GOLD)
    draw_text_right(draw, 838, 124, "اشتر ٨ أكواب واحصل على قهوة مجانية", MUTED, FONTS["body"])

    draw_text_right(draw, 962, 196, "بطاقة الولاء", COFFEE, FONTS["title"])
    draw_text_right(draw, 962, 252, "ضع علامة عند كل عملية شراء", MUTED, FONTS["body"])

    draw.rounded_rectangle((62, 306, 646, 532), 28, fill=WHITE, outline=SHADOW, width=2)
    start_x, start_y = 96, 330
    box, gap_x, gap_y = 84, 62, 34
    arabic_numbers = ["١", "٢", "٣", "٤", "٥", "٦", "٧", "٨"]
    for i in range(8):
        row = i // 4
        col = i % 4
        x = start_x + col * (box + gap_x)
        y = start_y + row * (box + gap_y)
        draw.rounded_rectangle((x + 4, y + 6, x + box + 4, y + box + 6), 18, fill=SHADOW)
        draw.rounded_rectangle((x, y, x + box, y + box), 18, fill=SOFT_WHITE, outline=INK, width=5)
        draw.rounded_rectangle((x + 10, y + 10, x + box - 10, y + box - 10), 12, outline=LINE, width=2)
        draw.ellipse((x + 12, y + 12, x + 40, y + 40), fill=GOLD)
        draw_text_center(draw, (x + 12, y + 10, x + 40, y + 39), arabic_numbers[i], INK, FONTS["tiny"])

    free_x, free_y = 716, 316
    draw.rounded_rectangle((free_x + 6, free_y + 8, 982 + 6, 512 + 8), 30, fill=SHADOW)
    draw.rounded_rectangle((free_x, free_y, 982, 512), 30, fill=INK)
    draw.rounded_rectangle((free_x + 15, free_y + 15, 982 - 15, 512 - 15), 20, outline=GOLD, width=4)
    draw_text_center_ar(draw, (free_x + 18, free_y + 28, 982 - 18, free_y + 94), "قهوة", GOLD, FONTS["title"])
    draw_text_center_ar(draw, (free_x + 18, free_y + 90, 982 - 18, free_y + 152), "مجانية", WHITE, FONTS["title"])
    draw_text_center_ar(draw, (free_x + 24, free_y + 145, 982 - 24, free_y + 186), "بعد ٨ علامات", WARM, FONTS["body"])

    draw_text_right(draw, 380, 548, "اسم العميل:", MUTED, FONTS["small"])
    draw.line((64, 574, 250, 574), fill=MUTED, width=2)
    draw_text_right(draw, 966, 548, "صالحة داخل المتجر فقط", MUTED, FONTS["small"])
    return img


def qr_from_data(qr_data):
    if not qr_data:
        return None
    try:
        import qrcode
    except ImportError:
        return None

    qr = qrcode.QRCode(version=2, box_size=10, border=2)
    qr.add_data(qr_data)
    qr.make(fit=True)
    return qr.make_image(fill_color=INK, back_color=WHITE).convert("RGBA")


def make_back(qr_data=None, qr_image_path=None):
    img = rounded_card()
    draw = ImageDraw.Draw(img)
    draw_cut_guides(draw)

    draw.rounded_rectangle((36, 36, CARD_W - 36, 148), 26, fill=INK)
    add_logo(img, 866, 50, 78)
    draw.text((468, 52), "Coffe Room", fill=WHITE, font=FONTS["brand_en"])
    draw_text_right(draw, 838, 114, "امسح البطاقة عند الدفع", GOLD, FONTS["body"])

    qr_box = (350, 184, 700, 534)
    draw.rounded_rectangle((qr_box[0] - 18, qr_box[1] - 18, qr_box[2] + 18, qr_box[3] + 18), 34, fill=WHITE, outline=LINE, width=3)

    qr_img = None
    if qr_image_path:
        qr_img = Image.open(qr_image_path).convert("RGBA")
    if qr_img is None:
        qr_img = qr_from_data(qr_data)

    if qr_img is not None:
        qr_img.thumbnail((qr_box[2] - qr_box[0], qr_box[3] - qr_box[1]), Image.Resampling.LANCZOS)
        x = qr_box[0] + ((qr_box[2] - qr_box[0]) - qr_img.width) // 2
        y = qr_box[1] + ((qr_box[3] - qr_box[1]) - qr_img.height) // 2
        img.alpha_composite(qr_img, (x, y))
    else:
        draw.rounded_rectangle(qr_box, 18, fill="#fbfbfb", outline=INK, width=5)
        step = 34
        for x in range(qr_box[0] + step, qr_box[2], step):
            draw.line((x, qr_box[1] + 18, x, qr_box[3] - 18), fill="#e7e0d2", width=2)
        for y in range(qr_box[1] + step, qr_box[3], step):
            draw.line((qr_box[0] + 18, y, qr_box[2] - 18, y), fill="#e7e0d2", width=2)
        draw_text_center_ar(draw, (qr_box[0] + 18, qr_box[1] + 106, qr_box[2] - 18, qr_box[1] + 166), "مكان الرمز", INK, FONTS["title"])
        draw_text_center(draw, (qr_box[0] + 18, qr_box[1] + 168, qr_box[2] - 18, qr_box[1] + 214), "QR", MUTED, FONTS["subtitle"])

    draw_text_right(draw, 286, 216, "طريقة الاستخدام", COFFEE, FONTS["subtitle"])
    steps = ["١. اشتر قهوة", "٢. احصل على علامة", "٣. أكمل ٨ علامات", "٤. استمتع بقهوة مجانية"]
    for idx, step_text in enumerate(steps):
        draw_text_right(draw, 286, 258 + idx * 38, step_text, MUTED, FONTS["small"])

    draw_text_right(draw, 968, 220, "رقم البطاقة", COFFEE, FONTS["subtitle"])
    draw.rounded_rectangle((744, 266, 968, 318), 12, fill=WHITE, outline=LINE, width=2)
    draw_text_center(draw, (744, 266, 968, 318), "CR-0000", MUTED, FONTS["small"])
    draw_text_right(draw, 968, 374, "مكان مخصص للـ QR", MUTED, FONTS["tiny"])
    draw_text_right(draw, 968, 402, "استبدله لاحقا من بايثون", MUTED, FONTS["tiny"])
    draw_text_right(draw, 968, 486, "@ كوفي روم", INK, FONTS["subtitle"])
    return img


def export_cards(qr_data=None, qr_image_path=None):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    front = make_front()
    back = make_back(qr_data=qr_data, qr_image_path=qr_image_path)

    front_path = OUTPUT_DIR / "coffee_room_loyalty_front.png"
    back_path = OUTPUT_DIR / "coffee_room_loyalty_back.png"
    pdf_path = OUTPUT_DIR / "coffee_room_loyalty_card.pdf"

    front.convert("RGB").save(front_path, quality=95)
    back.convert("RGB").save(back_path, quality=95)
    front.convert("RGB").save(pdf_path, save_all=True, append_images=[back.convert("RGB")], resolution=300)
    return front_path, back_path, pdf_path


if __name__ == "__main__":
    paths = export_cards()
    for path in paths:
        print(path)
