"""테트로 클라임에 쓰이는 모든 그림(PNG)을 코드로 그린다.

엔트리 무대는 480x270 이지만, 전체화면에서도 선명하도록 모든 그림을 2배(OUT=2)로 만들고
오브젝트 크기를 50% 로 둔다. 그릴 때는 다시 SS 배로 크게 그린 뒤 줄여서 계단 현상을 없앤다.
"""

import math
import os
import random

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

OUT = 2  # 무대 1px = 그림 2px
SS = 3  # 안티앨리어싱용 슈퍼샘플링
CELL = 18  # 무대 기준 한 칸 크기(px)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")


def font(name, size_stage):
    files = {
        "logo": "RussoOne-Regular.ttf",
        "title": "BlackHanSans-Regular.ttf",
        "body": "DoHyeon-Regular.ttf",
        "symbol": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    }
    path = files[name]
    if not os.path.isabs(path):
        path = os.path.join(FONT_DIR, path)
    return ImageFont.truetype(path, int(size_stage * OUT * SS))


# ------------------------------------------------------------------ 색 도우미
def mix(c1, c2, t):
    return tuple(int(round(a + (b - a) * t)) for a, b in zip(c1, c2))


def shade(c, t):
    """t>0 이면 밝게, t<0 이면 어둡게."""
    if t >= 0:
        return mix(c, (255, 255, 255), t)
    return mix(c, (0, 0, 0), -t)


def hexc(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


# ------------------------------------------------------------------ 캔버스
class Canvas:
    """무대 좌표(1x) 크기로 만들고, 내부는 OUT*SS 배로 그린다."""

    def __init__(self, w, h, bg=(0, 0, 0, 0)):
        self.w, self.h = w, h
        self.k = OUT * SS
        self.img = Image.new("RGBA", (int(round(w * self.k)), int(round(h * self.k))), bg)

    def p(self, v):
        return v * self.k

    def box(self, x0, y0, x1, y1):
        return [x0 * self.k, y0 * self.k, x1 * self.k - 1, y1 * self.k - 1]

    def layer(self):
        return Image.new("RGBA", self.img.size, (0, 0, 0, 0))

    def paste(self, layer):
        self.img = Image.alpha_composite(self.img, layer)

    def final(self):
        size = (int(round(self.w * OUT)), int(round(self.h * OUT)))
        return self.img.resize(size, Image.LANCZOS)


def vgradient(size, top, bottom):
    w, h = size
    grad = Image.new("RGBA", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        grad.putpixel((0, y), tuple(int(round(a + (b - a) * t)) for a, b in zip(top, bottom)))
    return grad.resize((w, h))


def hgradient(size, left, right):
    w, h = size
    grad = Image.new("RGBA", (w, 1))
    for x in range(w):
        t = x / max(1, w - 1)
        grad.putpixel((x, 0), tuple(int(round(a + (b - a) * t)) for a, b in zip(left, right)))
    return grad.resize((w, h))


def rrect_mask(size, box, radius):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle(box, radius, fill=255)
    return m


def glow(layer, radius, strength=1.0):
    blurred = layer.filter(ImageFilter.GaussianBlur(radius))
    if strength != 1.0:
        a = blurred.getchannel("A").point(lambda v: min(255, int(v * strength)))
        blurred.putalpha(a)
    return blurred


def text_layer(cv, text, fnt, cx, cy, fill, anchor="mm", stroke=0, stroke_fill=None):
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    d.text(
        (cv.p(cx), cv.p(cy)),
        text,
        font=fnt,
        fill=fill,
        anchor=anchor,
        stroke_width=int(stroke * cv.k),
        stroke_fill=stroke_fill,
    )
    return lay


def gradient_text(cv, text, fnt, cx, cy, top, bottom, anchor="mm", stroke=0, stroke_fill=None):
    """위->아래 그라데이션 글자."""
    mask_layer = text_layer(cv, text, fnt, cx, cy, (255, 255, 255, 255), anchor)
    bbox = mask_layer.getbbox()
    lay = cv.layer()
    if stroke:
        lay = text_layer(cv, text, fnt, cx, cy, stroke_fill, anchor, stroke, stroke_fill)
    if bbox:
        g = vgradient((bbox[2] - bbox[0], bbox[3] - bbox[1]), top, bottom)
        full = Image.new("RGBA", cv.img.size, (0, 0, 0, 0))
        full.paste(g, (bbox[0], bbox[1]))
        full.putalpha(mask_layer.getchannel("A"))
        lay = Image.alpha_composite(lay, full)
    return lay


# ------------------------------------------------------------------ 테트로미노
BASE_SHAPES = {
    "I": [(0, 0), (1, 0), (2, 0), (3, 0)],
    "O": [(0, 0), (1, 0), (0, 1), (1, 1)],
    "T": [(0, 1), (1, 1), (2, 1), (1, 0)],
    "S": [(0, 0), (1, 0), (1, 1), (2, 1)],
    "Z": [(0, 1), (1, 1), (1, 0), (2, 0)],
    "J": [(0, 1), (0, 0), (1, 0), (2, 0)],
    "L": [(2, 1), (0, 0), (1, 0), (2, 0)],
}
PIECE_COLORS = {
    "I": hexc("#4fe8f2"),  # 하늘
    "O": hexc("#ffd84a"),  # 노랑
    "T": hexc("#b46bff"),  # 보라
    "S": hexc("#5fe38a"),  # 초록
    "Z": hexc("#ff5fb4"),  # 분홍
    "J": hexc("#5b86ff"),  # 파랑
    "L": hexc("#ff9d45"),  # 주황
}
PIECE_NAMES = {"I": "I", "O": "O", "T": "T", "S": "S", "Z": "Z", "J": "J", "L": "L"}


def _normalize(cells):
    mx = min(x for x, _ in cells)
    my = min(y for _, y in cells)
    return tuple(sorted((x - mx, y - my) for x, y in cells))


def piece_states():
    """(종류, 회전번호, 칸 목록, 폭, 높이) 19가지."""
    states = []
    for kind, cells in BASE_SHAPES.items():
        seen = []
        cur = _normalize(cells)
        for _ in range(4):
            if cur not in seen:
                seen.append(cur)
            cur = _normalize([(y, -x) for x, y in cur])
        for r, st in enumerate(seen):
            w = max(x for x, _ in st) + 1
            h = max(y for _, y in st) + 1
            states.append((kind, r, list(st), w, h))
    return states


def draw_cell(cv, lay, x, y, color, alpha=255, size=CELL):
    """(x, y) = 칸의 왼쪽 위 (무대 px). 반짝이는 사탕 느낌의 입체 블록."""
    d = ImageDraw.Draw(lay)
    k = cv.k
    inset = 0.6
    x0, y0, x1, y1 = x + inset, y + inset, x + size - inset, y + size - inset
    r = 3.2 * k
    lip = shade(color, -0.42) + (alpha,)
    face = color + (alpha,)
    d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], r, fill=lip)
    # 윗면(밝은 면)
    face_box = [x0 * k, y0 * k, x1 * k, (y1 - 2.2) * k]
    fw = int(face_box[2] - face_box[0])
    fh = int(face_box[3] - face_box[1])
    g = vgradient((max(1, fw), max(1, fh)), shade(color, 0.28) + (alpha,), shade(color, -0.06) + (alpha,))
    m = rrect_mask((max(1, fw), max(1, fh)), [0, 0, fw - 1, fh - 1], r)
    lay.paste(g, (int(face_box[0]), int(face_box[1])), m)
    # 안쪽 사각형(살짝 들어간 느낌)
    ib = [(x0 + 3.2) * k, (y0 + 3.0) * k, (x1 - 3.2) * k, (y1 - 5.0) * k]
    iw, ih = int(ib[2] - ib[0]), int(ib[3] - ib[1])
    g2 = vgradient((iw, ih), shade(color, 0.12) + (alpha,), shade(color, 0.02) + (alpha,))
    m2 = rrect_mask((iw, ih), [0, 0, iw - 1, ih - 1], 2.0 * k)
    lay.paste(g2, (int(ib[0]), int(ib[1])), m2)
    # 하이라이트
    hl = [(x0 + 2.0) * k, (y0 + 1.4) * k, (x0 + 7.5) * k, (y0 + 2.8) * k]
    d.rounded_rectangle(hl, 0.7 * k, fill=(255, 255, 255, int(150 * alpha / 255)))


def piece_image(cells, w, h, color, trail=False):
    """trail=True 면 위로 잔상이 남는 '떨어지는 중' 모양.
    잔상 때문에 그림이 위로 길어지지만, 아래에도 같은 높이의 빈 공간을 둬서
    그림의 중심이 항상 블록 묶음의 중심과 같게 한다."""
    T = 3.2 * CELL if trail else 0
    cv = Canvas(w * CELL, h * CELL + 2 * T)
    lay = cv.layer()
    if trail:
        tops = {}
        for x, y in cells:
            tops[x] = max(tops.get(x, -1), y)
        ghosts = [(0.30, 0.34), (0.60, 0.25), (0.92, 0.17), (1.26, 0.10), (1.62, 0.05)]
        k = cv.k
        for x, top in tops.items():
            for off, a in ghosts:
                gl = cv.layer()
                gy = T + (h - 1 - top) * CELL - off * CELL
                ImageDraw.Draw(gl).rounded_rectangle(
                    [(x * CELL + 1.2) * k, (gy + 1.2) * k, (x * CELL + CELL - 1.2) * k, (gy + CELL - 1.2) * k],
                    3.0 * k,
                    fill=shade(color, -0.10) + (int(255 * a),),
                )
                lay = Image.alpha_composite(lay, gl)
    body = cv.layer()
    for x, y in cells:
        draw_cell(cv, body, x * CELL, T + (h - 1 - y) * CELL, color)
    halo = glow(body, 2.2 * cv.k, 0.55)
    lay = Image.alpha_composite(lay, halo)
    lay = Image.alpha_composite(lay, body)
    cv.paste(lay)
    return cv.final()


def floor_image():
    cv = Canvas(10 * CELL, CELL)
    lay = cv.layer()
    for c in range(10):
        draw_cell(cv, lay, c * CELL, 0, hexc("#555a68"))
    cv.paste(lay)
    return cv.final()


# ------------------------------------------------------------------ 플레이어
PLAYER = hexc("#ff4d3d")


def player_image(facing=1, jumping=False, dead=False):
    size = 16
    cv = Canvas(size, size)
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    k = cv.k
    body = PLAYER if not dead else hexc("#9aa0a8")
    d.rounded_rectangle([0.6 * k, 0.6 * k, 15.4 * k, 15.4 * k], 4.2 * k, fill=shade(body, -0.45) + (255,))
    fb = [0.6 * k, 0.6 * k, 15.4 * k, 13.6 * k]
    fw, fh = int(fb[2] - fb[0]), int(fb[3] - fb[1])
    g = vgradient((fw, fh), shade(body, 0.22) + (255,), shade(body, -0.05) + (255,))
    lay.paste(g, (int(fb[0]), int(fb[1])), rrect_mask((fw, fh), [0, 0, fw - 1, fh - 1], 4.2 * k))
    d.rounded_rectangle([2.4 * k, 1.5 * k, 7.0 * k, 2.8 * k], 0.6 * k, fill=(255, 255, 255, 120))
    ey = 5.0 if not jumping else 3.6
    if dead:
        for ex in (4.6, 10.2):
            d.line([(ex - 1.6) * k, (ey) * k, (ex + 1.6) * k, (ey + 3.4) * k], fill=(40, 40, 50, 255), width=int(1.3 * k))
            d.line([(ex + 1.6) * k, (ey) * k, (ex - 1.6) * k, (ey + 3.4) * k], fill=(40, 40, 50, 255), width=int(1.3 * k))
    else:
        shift = 1.6 * facing
        for ex in (5.2 + shift, 10.8 + shift):
            d.rounded_rectangle([(ex - 1.2) * k, ey * k, (ex + 1.2) * k, (ey + 3.8) * k], 0.9 * k, fill=(255, 255, 255, 255))
    cv.paste(lay)
    return cv.final()


# ------------------------------------------------------------------ 독극물
POISON_W, POISON_H = 180, 300
POISON_SURFACE = 16  # 그림 맨 위에서 수면(물결 중심)까지 (무대 px)


def poison_image(phase):
    cv = Canvas(POISON_W, POISON_H)
    k = cv.k
    W, H = cv.img.size
    wave_len = 60.0
    amp = 2.4
    rnd = random.Random(7)

    def surf(xs):
        return POISON_SURFACE + amp * math.sin((xs / wave_len + phase / 4.0) * 2 * math.pi) + 0.9 * math.sin(
            (xs / 23.0 - phase / 4.0) * 2 * math.pi
        )

    # 수면 위로 번지는 초록 빛
    haze = cv.layer()
    hd = ImageDraw.Draw(haze)
    for i in range(14):
        a = int(70 * (1 - i / 14) ** 2)
        pts = [(0, H)]
        for xi in range(0, POISON_W + 1, 2):
            pts.append((xi * k, (surf(xi) - i * 1.0) * k))
        pts.append((POISON_W * k, H))
        hd.polygon(pts, fill=(120, 255, 90, a))
    haze = haze.filter(ImageFilter.GaussianBlur(3 * k))
    cv.paste(haze)

    # 몸통
    body_mask = Image.new("L", (W, H), 0)
    md = ImageDraw.Draw(body_mask)
    pts = [(0, H)]
    for xi in range(0, POISON_W + 1, 1):
        pts.append((xi * k, surf(xi) * k))
    pts.append((POISON_W * k, H))
    md.polygon(pts, fill=255)
    top = int((POISON_SURFACE - amp - 1) * k)
    grad = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    g1 = vgradient((W, int(40 * k)), (132, 250, 70, 238), (38, 150, 40, 246))
    g2 = vgradient((W, H - top - int(40 * k)), (38, 150, 40, 246), (10, 52, 14, 252))
    grad.paste(g1, (0, top))
    grad.paste(g2, (0, top + int(40 * k)))
    body = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    body.paste(grad, (0, 0), body_mask)
    cv.paste(body)

    # 소용돌이 무늬(어두운 줄)
    streak = cv.layer()
    sd = ImageDraw.Draw(streak)
    for i in range(9):
        yy = POISON_SURFACE + 18 + i * 26 + (phase * 2.5) % 26
        xs = [(x * k, (yy + 3 * math.sin(x / 17.0 + i)) * k) for x in range(0, POISON_W + 1, 3)]
        sd.line(xs, fill=(8, 60, 12, 55), width=int(2.2 * k))
    streak = streak.filter(ImageFilter.GaussianBlur(1.2 * k))
    cv.paste(streak)

    # 거품
    bub = cv.layer()
    bd = ImageDraw.Draw(bub)
    for i in range(16):
        bx = rnd.uniform(8, POISON_W - 8)
        base_y = rnd.uniform(POISON_SURFACE + 14, POISON_SURFACE + 150)
        speed = rnd.uniform(1.5, 3.2)
        by = base_y - (phase * speed) % 40
        if by < POISON_SURFACE + 6:
            continue
        r = rnd.uniform(1.0, 3.2)
        a = int(170 * min(1.0, (by - POISON_SURFACE) / 40.0) * (1 - (by - POISON_SURFACE) / 200.0))
        a = max(40, min(200, a))
        bd.ellipse([(bx - r) * k, (by - r) * k, (bx + r) * k, (by + r) * k], outline=(200, 255, 150, a), width=int(0.7 * k))
        bd.ellipse([(bx - r * 0.45) * k, (by - r * 0.6) * k, (bx - r * 0.05) * k, (by - r * 0.2) * k], fill=(230, 255, 200, a))
    cv.paste(bub)

    # 수면 반짝이 선
    foam = cv.layer()
    fd = ImageDraw.Draw(foam)
    line = [(x * k, surf(x) * k) for x in range(0, POISON_W + 1)]
    fd.line(line, fill=(214, 255, 120, 255), width=int(1.6 * k))
    cv.paste(glow(foam, 1.6 * k, 1.2))
    cv.paste(foam)
    return cv.final()


# ------------------------------------------------------------------ 배경
STAGE_W, STAGE_H = 480, 270


def sx(x):
    return x + STAGE_W / 2


def sy(y):
    return STAGE_H / 2 - y


def keycap(cv, lay, cx, cy, w, label, fnt):
    d = ImageDraw.Draw(lay)
    k = cv.k
    h = 15
    d.rounded_rectangle([(cx - w / 2) * k, (cy - h / 2) * k, (cx + w / 2) * k, (cy + h / 2) * k], 3 * k, fill=(34, 40, 58, 255))
    d.rounded_rectangle(
        [(cx - w / 2) * k, (cy - h / 2) * k, (cx + w / 2) * k, (cy + h / 2 - 2) * k], 3 * k, fill=(62, 72, 100, 255)
    )
    d.text((cx * k, (cy - 1) * k), label, font=fnt, fill=(235, 240, 255, 255), anchor="mm")


def background_image():
    cv = Canvas(STAGE_W, STAGE_H, (6, 7, 12, 255))
    k = cv.k
    W, H = cv.img.size

    # 옆 패널의 은은한 무늬
    deco = cv.layer()
    dd = ImageDraw.Draw(deco)
    rnd = random.Random(3)
    for _ in range(26):
        side = rnd.choice([-1, 1])
        x = sx(side * rnd.uniform(100, 232))
        y = rnd.uniform(0, STAGE_H)
        s = rnd.choice([5, 6, 7])
        c = rnd.choice(list(PIECE_COLORS.values()))
        dd.rounded_rectangle([x * k, y * k, (x + s) * k, (y + s) * k], 1.4 * k, fill=c + (26,))
    cv.paste(deco)

    # 가운데 경기장
    field = cv.layer()
    fx0, fx1 = sx(-90), sx(90)
    g = vgradient((int((fx1 - fx0) * k), H), (16, 20, 34, 255), (9, 11, 19, 255))
    field.paste(g, (int(fx0 * k), 0))
    fd = ImageDraw.Draw(field)
    for c in range(1, 10):
        x = fx0 + c * CELL
        fd.line([(x * k, 0), (x * k, H)], fill=(255, 255, 255, 9), width=max(1, int(0.5 * k)))
    cv.paste(field)

    # 경기장 테두리 빛
    edge = cv.layer()
    ed = ImageDraw.Draw(edge)
    for x, col in ((fx0, (80, 220, 255, 255)), (fx1, (255, 95, 180, 255))):
        ed.line([(x * k, 0), (x * k, H)], fill=col, width=int(1.2 * k))
    cv.paste(glow(edge, 3 * k, 1.3))
    cv.paste(edge)

    # 패널 카드
    cards = cv.layer()
    cd = ImageDraw.Draw(cards)

    def card(x0, y0, x1, y1, outline=(40, 48, 72, 255)):
        cd.rounded_rectangle([sx(x0) * k, sy(y0) * k, sx(x1) * k, sy(y1) * k], 7 * k, fill=(13, 16, 27, 235), outline=outline, width=int(0.8 * k))

    card(-230, 64, -100, -46)  # 점수 카드
    card(-230, -54, -100, -128)  # 조작법 카드
    card(100, 128, 230, 76)  # 독극물 거리 카드
    card(100, 68, 230, -128)  # 높이 게이지 카드
    cv.paste(cards)

    # 로고
    cv.paste(glow(gradient_text(cv, "TETRO", font("logo", 25), sx(-165), sy(113), (110, 240, 255, 255), (70, 150, 255, 255)), 2.5 * k, 0.9))
    cv.paste(gradient_text(cv, "TETRO", font("logo", 25), sx(-165), sy(113), (130, 245, 255, 255), (70, 160, 255, 255)))
    cv.paste(glow(gradient_text(cv, "CLIMB", font("logo", 25), sx(-165), sy(88), (255, 140, 205, 255), (255, 90, 120, 255)), 2.5 * k, 0.9))
    cv.paste(gradient_text(cv, "CLIMB", font("logo", 25), sx(-165), sy(88), (255, 150, 210, 255), (255, 95, 125, 255)))
    cv.paste(text_layer(cv, "테트로 클라임", font("title", 9.5), sx(-165), sy(72), (190, 198, 225, 255)))

    # 점수 카드 글자
    cv.paste(text_layer(cv, "HEIGHT", font("logo", 8.5), sx(-165), sy(52), (125, 138, 175, 255)))
    lay = cv.layer()
    ImageDraw.Draw(lay).line([(sx(-218) * k, sy(4) * k), (sx(-112) * k, sy(4) * k)], fill=(45, 54, 80, 255), width=int(0.6 * k))
    cv.paste(lay)
    cv.paste(text_layer(cv, "BEST", font("logo", 8.5), sx(-165), sy(-7), (255, 216, 74, 255)))

    # 조작법
    kl = cv.layer()
    small = font("logo", 7.5)
    keycap(cv, kl, sx(-205), sy(-72), 17, "<", small)
    keycap(cv, kl, sx(-185), sy(-72), 17, ">", small)
    keycap(cv, kl, sx(-192), sy(-94), 32, "SPACE", font("logo", 6))
    keycap(cv, kl, sx(-205), sy(-114), 17, "^", small)
    cv.paste(kl)
    body = font("body", 10)
    cv.paste(text_layer(cv, "좌우 이동", body, sx(-168), sy(-72), (205, 212, 235, 255), anchor="lm"))
    cv.paste(text_layer(cv, "점프", body, sx(-168), sy(-94), (205, 212, 235, 255), anchor="lm"))
    cv.paste(text_layer(cv, "점프(위쪽키)", body, sx(-190), sy(-114), (150, 158, 185, 255), anchor="lm"))

    # 독극물 카드
    cv.paste(text_layer(cv, "독극물까지", font("body", 10), sx(165), sy(118), (120, 240, 110, 255)))

    # 높이 게이지
    cv.paste(text_layer(cv, "HEIGHT MAP", font("logo", 7.5), sx(165), sy(59), (125, 138, 175, 255)))
    track = cv.layer()
    td = ImageDraw.Draw(track)
    tx = sx(GAUGE_X)
    td.rounded_rectangle(
        [(tx - 3) * k, sy(GAUGE_TOP + 3) * k, (tx + 3) * k, sy(GAUGE_BOTTOM - 3) * k], 3 * k, fill=(24, 29, 44, 255)
    )
    for i in range(11):
        yy = GAUGE_BOTTOM + (GAUGE_TOP - GAUGE_BOTTOM) * i / 10
        w = 5 if i % 5 == 0 else 3
        td.line([((tx - 3 - w) * k, sy(yy) * k), ((tx - 4) * k, sy(yy) * k)], fill=(60, 70, 100, 255), width=int(0.6 * k))
    cv.paste(track)
    cv.paste(text_layer(cv, "0", font("logo", 6), sx(GAUGE_X - 16), sy(GAUGE_BOTTOM), (90, 100, 130, 255)))
    return cv.final()


GAUGE_X = 165
GAUGE_TOP = 44
GAUGE_BOTTOM = -118


def marker_player():
    cv = Canvas(28, 14)
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    k = cv.k
    d.polygon([(10 * k, 7 * k), (15 * k, 3.5 * k), (15 * k, 10.5 * k)], fill=(255, 255, 255, 255))
    d.rounded_rectangle([15.5 * k, 1 * k, 27.5 * k, 13 * k], 3 * k, fill=shade(PLAYER, -0.4) + (255,))
    d.rounded_rectangle([15.5 * k, 1 * k, 27.5 * k, 11.8 * k], 3 * k, fill=PLAYER + (255,))
    for ex in (19.6, 23.6):
        d.rounded_rectangle([(ex - 0.9) * k, 4.2 * k, (ex + 0.9) * k, 7.6 * k], 0.6 * k, fill=(255, 255, 255, 255))
    cv.paste(lay)
    return cv.final()


def marker_best():
    cv = Canvas(52, 12)
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    k = cv.k
    d.rounded_rectangle([25 * k, 5 * k, 51 * k, 7 * k], 1 * k, fill=(255, 216, 74, 255))
    cv.paste(glow(lay, 1.2 * k, 1.0))
    cv.paste(lay)
    cv.paste(text_layer(cv, "BEST", font("logo", 6.5), 12, 6, (255, 216, 74, 255)))
    return cv.final()


def marker_poison():
    cv = Canvas(52, 12)
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    k = cv.k
    d.rounded_rectangle([25 * k, 5 * k, 51 * k, 7 * k], 1 * k, fill=(120, 250, 90, 255))
    cv.paste(glow(lay, 1.2 * k, 1.0))
    cv.paste(lay)
    cv.paste(text_layer(cv, "독", font("title", 8), 17, 6.2, (120, 250, 90, 255)))
    return cv.final()


# ------------------------------------------------------------------ 안내 화면
def panel(cv, x0, y0, x1, y1, border_top, border_bottom, fill=(10, 12, 22, 232)):
    k = cv.k
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], 10 * k, fill=fill)
    cv.paste(lay)
    # 테두리 그라데이션
    ring = Image.new("L", cv.img.size, 0)
    rd = ImageDraw.Draw(ring)
    rd.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], 10 * k, outline=255, width=int(1.1 * k))
    g = vgradient(cv.img.size, border_top, border_bottom)
    g.putalpha(ring)
    cv.paste(glow(g, 2.5 * k, 0.8))
    cv.paste(g)


def title_card(blink):
    cv = Canvas(300, 190)
    panel(cv, 4, 4, 296, 186, (90, 230, 255, 255), (255, 95, 180, 255))
    k = cv.k
    logo = font("logo", 36)
    cv.paste(glow(gradient_text(cv, "TETRO CLIMB", logo, 150, 38, (120, 240, 255, 255), (255, 110, 190, 255)), 3 * k, 1.0))
    cv.paste(gradient_text(cv, "TETRO CLIMB", logo, 150, 38, (140, 245, 255, 255), (255, 120, 195, 255)))
    cv.paste(text_layer(cv, "테트로 클라임", font("title", 17), 150, 70, (240, 244, 255, 255)))
    body = font("body", 11.5)
    cv.paste(text_layer(cv, "떨어지는 블록은 피하고, 쌓인 블록은 밟고 올라가요!", body, 150, 94, (200, 208, 232, 255)))
    cv.paste(text_layer(cv, "아래에서 초록 독극물이 천천히 차오릅니다", body, 150, 110, (120, 245, 100, 255)))
    kl = cv.layer()
    small = font("logo", 7.5)
    keycap(cv, kl, 70, 134, 17, "<", small)
    keycap(cv, kl, 90, 134, 17, ">", small)
    keycap(cv, kl, 172, 134, 34, "SPACE", font("logo", 6))
    cv.paste(kl)
    cv.paste(text_layer(cv, "이동", font("body", 11), 104, 134, (220, 226, 245, 255), anchor="lm"))
    cv.paste(text_layer(cv, "점프", font("body", 11), 194, 134, (220, 226, 245, 255), anchor="lm"))
    col = (255, 216, 74, 255) if not blink else (255, 216, 74, 110)
    cv.paste(text_layer(cv, "SPACE 키를 눌러 시작!", font("title", 14), 150, 165, col))
    return cv.final()


def countdown_image(label, top, bottom):
    cv = Canvas(160, 110)
    fnt = font("logo", 70 if len(label) == 1 else 54)
    k = cv.k
    shadow = text_layer(cv, label, fnt, 80, 57, (0, 0, 0, 200))
    cv.paste(shadow.filter(ImageFilter.GaussianBlur(2 * k)))
    g = gradient_text(cv, label, fnt, 80, 55, top, bottom, stroke=1.6, stroke_fill=(10, 12, 22, 255))
    cv.paste(glow(g, 4 * k, 1.0))
    cv.paste(g)
    return cv.final()


def gameover_card(reason, reason_color):
    cv = Canvas(230, 150)
    panel(cv, 4, 4, 226, 146, (255, 110, 110, 255), (255, 180, 80, 255))
    k = cv.k
    fnt = font("logo", 27)
    cv.paste(glow(gradient_text(cv, "GAME OVER", fnt, 115, 30, (255, 120, 120, 255), (255, 170, 70, 255)), 3 * k, 1.0))
    cv.paste(gradient_text(cv, "GAME OVER", fnt, 115, 30, (255, 130, 130, 255), (255, 180, 80, 255)))
    cv.paste(text_layer(cv, reason, font("title", 13), 115, 57, reason_color))
    lay = cv.layer()
    ImageDraw.Draw(lay).line([(30 * k, 70 * k), (200 * k, 70 * k)], fill=(60, 66, 92, 255), width=int(0.6 * k))
    cv.paste(lay)
    cv.paste(text_layer(cv, "SPACE 키로 다시 도전!", font("body", 12.5), 115, 128, (255, 216, 74, 255)))
    return cv.final()


def manager_icon():
    """게임 관리자 오브젝트 목록에서 보일 작은 게임패드 아이콘 (무대에서는 숨겨 둔다)."""
    cv = Canvas(24, 24)
    lay = cv.layer()
    d = ImageDraw.Draw(lay)
    k = cv.k
    d.rounded_rectangle([1 * k, 6 * k, 23 * k, 19 * k], 6 * k, fill=(60, 70, 110, 255))
    d.rounded_rectangle([1 * k, 6 * k, 23 * k, 17.5 * k], 6 * k, fill=(96, 110, 170, 255))
    d.rectangle([5.2 * k, 10.8 * k, 10.8 * k, 12.6 * k], fill=(240, 244, 255, 255))
    d.rectangle([7.1 * k, 8.9 * k, 8.9 * k, 14.5 * k], fill=(240, 244, 255, 255))
    d.ellipse([15 * k, 9.2 * k, 17.6 * k, 11.8 * k], fill=(255, 95, 180, 255))
    d.ellipse([17.8 * k, 11.8 * k, 20.4 * k, 14.4 * k], fill=(80, 230, 240, 255))
    cv.paste(lay)
    return cv.final()


def thumbnail(img, size=96):
    t = img.copy()
    t.thumbnail((size, size), Image.LANCZOS)
    return t
