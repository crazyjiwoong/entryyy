"""테트로 클라임에 쓰이는 그림(PNG)을 코드로 그린다.

엔트리 그림판에서 네모 도구로 그린 것처럼 단색 + 검은 테두리로만 그린다.
그림 1px = 무대 1px (오브젝트 크기 100%).
"""

from PIL import Image, ImageDraw

CELL = 18  # 무대 기준 한 칸 크기(px)
LINE = (40, 40, 40, 255)  # 테두리 색

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
    "I": (0, 200, 255),
    "O": (255, 220, 0),
    "T": (170, 80, 255),
    "S": (60, 200, 60),
    "Z": (255, 60, 60),
    "J": (40, 90, 255),
    "L": (255, 140, 0),
}


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


def piece_image(cells, w, h, color):
    img = Image.new("RGBA", (w * CELL, h * CELL), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y in cells:
        x0 = x * CELL
        y0 = (h - 1 - y) * CELL
        d.rectangle([x0, y0, x0 + CELL - 1, y0 + CELL - 1], fill=color + (255,), outline=LINE, width=2)
    return img


def floor_image():
    img = Image.new("RGBA", (10 * CELL, CELL), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle([0, 0, 10 * CELL - 1, CELL - 1], fill=(150, 100, 50, 255), outline=LINE, width=2)
    return img


# ------------------------------------------------------------------ 플레이어
def player_image():
    img = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 15, 15], fill=(255, 50, 50, 255), outline=LINE, width=1)
    d.rectangle([4, 4, 5, 7], fill=LINE)
    d.rectangle([10, 4, 11, 7], fill=LINE)
    return img


# ------------------------------------------------------------------ 독극물
POISON_W, POISON_H = 180, 300
POISON_SURFACE = 6  # 그림 맨 위에서 수면까지 (무대 px)


def poison_image():
    img = Image.new("RGBA", (POISON_W, POISON_H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    green = (70, 220, 70, 255)
    d.rectangle([0, POISON_SURFACE, POISON_W - 1, POISON_H - 1], fill=green)
    for x in range(0, POISON_W + 1, 20):
        d.ellipse([x - 6, 0, x + 6, POISON_SURFACE * 2], fill=green)
    return img


# ------------------------------------------------------------------ 배경
STAGE_W, STAGE_H = 480, 270


def background_image():
    img = Image.new("RGBA", (STAGE_W, STAGE_H), (225, 225, 225, 255))
    d = ImageDraw.Draw(img)
    d.rectangle([150, 0, 329, STAGE_H - 1], fill=(190, 230, 255, 255))
    d.rectangle([147, 0, 149, STAGE_H - 1], fill=LINE)
    d.rectangle([330, 0, 332, STAGE_H - 1], fill=LINE)
    return img


def blank():
    """게임 관리자 오브젝트용 그림 (무대에서는 숨겨 둔다)."""
    return Image.new("RGBA", (8, 8), (128, 128, 128, 255))


def thumbnail(img, size=96):
    t = img.copy()
    t.thumbnail((size, size), Image.NEAREST)
    return t
