#!/usr/bin/env python3
"""테트로 클라임(.ent) 생성기.

실행:  python3 tools/build_tetro_climb.py
결과:  tetro_climb.ent  (엔트리 오프라인 / playentry.org '오프라인 작품 불러오기'로 열기)

.ent 파일 구조 (엔트리 오프라인이 저장하는 형식과 같음)
    temp/project.json                 ← 작품 데이터 (script 는 JSON 문자열)
    temp/ab/cd/image/<파일명>.png      ← 모양 그림
    temp/ab/cd/thumb/<파일명>.png      ← 모양 썸네일
    temp/ab/cd/sound/<파일명>.mp3      ← 소리
를 tar + gzip 으로 묶은 것이다.
"""

import hashlib
import io
import json
import os
import sys
import tarfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import art  # noqa: E402
import sfx  # noqa: E402
from entry_dsl import (  # noqa: E402
    FUNCTIONS,
    R,
    abs_,
    add,
    add_effect,
    add_list,
    add_message,
    add_variable,
    and_,
    broadcast,
    broadcast_wait,
    call,
    chg,
    clear_effects,
    create_clone_self,
    define_function,
    delete_clone,
    div,
    eq,
    floor,
    forever,
    ge,
    gid,
    gt,
    hide,
    if_,
    if_else,
    item,
    join,
    key,
    le,
    locate_x,
    locate_xy,
    locate_y,
    lt,
    mod,
    mul,
    ne,
    next_shape,
    not_,
    or_,
    play,
    rand,
    repeat,
    repeat_while,
    round_,
    set_effect,
    set_item,
    setv,
    shape,
    shape_id,
    show,
    sub,
    thread,
    v,
    wait,
    wait_until,
    when_clone,
    when_message,
    when_run,
    write_text,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCENE_ID = "7dwq"

# ---------------------------------------------------------------- 게임 상수
CELL = art.CELL  # 한 칸 = 18px
COLS = 12  # 0, 11 번 칸은 보이지 않는 벽. 1~10 번이 경기장
RING = 96  # 격자 리스트는 96줄짜리 순환 버퍼 (엔트리 리스트 최대 5000칸 제한 때문)
X_OFF = -6 * CELL  # 월드 x -> 무대 x (0번 칸 왼쪽 = -108)
HALF_W = 7  # 플레이어 판정 반폭
PLAYER_H = 14  # 플레이어 판정 높이
GRAVITY = 0.44
JUMP_V = 6.8
MAX_FALL = 8
MOVE_V = 2.4

# 상태 값
TITLE, READY, PLAYING, OVER = 0, 1, 2, 3

KEY_LEFT, KEY_UP, KEY_RIGHT, KEY_SPACE = 37, 38, 39, 32
POISON_START = -45  # 독극물 처음 높이 (바닥 윗면 = 18)
TARGET_PERCENT = 30  # 플레이어 머리 위를 노리고 떨어지는 블록 비율(%)


# ================================================================ 에셋
class Assets:
    def __init__(self):
        self.files = {}  # tar 경로 -> bytes

    def picture(self, name, img):
        buf = io.BytesIO()
        img.save(buf, "PNG", optimize=True)
        data = buf.getvalue()
        fn = hashlib.md5(data + name.encode()).hexdigest()
        sub_dir = f"temp/{fn[0:2]}/{fn[2:4]}"
        self.files[f"{sub_dir}/image/{fn}.png"] = data
        tbuf = io.BytesIO()
        art.thumbnail(img).save(tbuf, "PNG", optimize=True)
        self.files[f"{sub_dir}/thumb/{fn}.png"] = tbuf.getvalue()
        return {
            "id": gid(),
            "name": name,
            "filename": fn,
            "fileurl": f"{sub_dir}/image/{fn}.png",
            "thumbUrl": f"{sub_dir}/thumb/{fn}.png",
            "imageType": "png",
            "dimension": {"width": img.width, "height": img.height},
        }

    def sound(self, name):
        data, duration = sfx.to_mp3(sfx.SOUNDS[name]())
        fn = hashlib.md5(data + name.encode()).hexdigest()
        path = f"temp/{fn[0:2]}/{fn[2:4]}/sound/{fn}.mp3"
        self.files[path] = data
        return {
            "id": gid(),
            "name": name,
            "filename": fn,
            "fileurl": path,
            "ext": ".mp3",
            "duration": duration,
        }


A = Assets()


def sprite_object(obj_id, name, pictures, sounds, x=0, y=0, visible=True, scale=0.5):
    first = pictures[0]
    w, h = first["dimension"]["width"], first["dimension"]["height"]
    return {
        "id": obj_id,
        "name": name,
        "script": "[]",
        "objectType": "sprite",
        "rotateMethod": "none",
        "scene": SCENE_ID,
        "sprite": {"pictures": pictures, "sounds": sounds},
        "selectedPictureId": first["id"],
        "lock": False,
        "entity": {
            "x": x,
            "y": y,
            "regX": w / 2,
            "regY": h / 2,
            "scaleX": scale,
            "scaleY": scale,
            "rotation": 0,
            "direction": 90,
            "width": w,
            "height": h,
            "font": "undefinedpx ",
            "visible": visible,
        },
    }


def text_object(obj_id, name, text, x, y, size, colour, visible=True, font_family="yg-jalnan"):
    return {
        "id": obj_id,
        "name": name,
        "script": "[]",
        "objectType": "textBox",
        "rotateMethod": "none",
        "scene": SCENE_ID,
        "sprite": {"pictures": [], "sounds": []},
        "text": text,
        "lock": False,
        "entity": {
            "x": x,
            "y": y,
            "regX": 0,
            "regY": 0,
            "scaleX": 1,
            "scaleY": 1,
            "rotation": 0,
            "direction": 90,
            "width": 40,
            "height": size + 4,
            "font": f"{size}px {font_family}",
            "visible": visible,
            "colour": colour,
            "text": text,
            "textAlign": 0,
            "lineBreak": False,
            "bgColor": "transparent",
            "underLine": False,
            "strike": False,
            "fontSize": size,
        },
    }


# ================================================================ 오브젝트 id / 그림
OID = {k: gid() for k in [
    "manager", "overlay", "result", "score", "best", "dist",
    "mk_me", "mk_best", "mk_poison", "poison", "player", "piece", "floor", "bg",
]}

STATES = art.piece_states()  # 19가지 (종류, 회전, 칸, 폭, 높이)

PIC = {}
PIC["manager"] = [A.picture("게임기", art.manager_icon())]
PIC["overlay"] = [
    A.picture("타이틀", art.title_card(False)),
    A.picture("타이틀_깜빡", art.title_card(True)),
    A.picture("셋", art.countdown_image("3", (255, 150, 210, 255), (255, 80, 140, 255))),
    A.picture("둘", art.countdown_image("2", (255, 230, 120, 255), (255, 170, 40, 255))),
    A.picture("하나", art.countdown_image("1", (140, 245, 255, 255), (70, 160, 255, 255))),
    A.picture("출발", art.countdown_image("GO!", (170, 255, 140, 255), (60, 200, 80, 255))),
    A.picture("게임오버_독극물", art.gameover_card("독극물에 빠졌어요!", (120, 245, 100, 255))),
    A.picture("게임오버_블록", art.gameover_card("블록에 깔렸어요!", (255, 150, 205, 255))),
]
PIC["mk_me"] = [A.picture("나", art.marker_player())]
PIC["mk_best"] = [A.picture("최고", art.marker_best())]
PIC["mk_poison"] = [A.picture("독극물", art.marker_poison())]
PIC["poison"] = [A.picture(f"독극물_{i + 1}", art.poison_image(i)) for i in range(4)]
PIC["player"] = [
    A.picture("오른쪽", art.player_image(1, False)),
    A.picture("왼쪽", art.player_image(-1, False)),
    A.picture("점프_오른쪽", art.player_image(1, True)),
    A.picture("점프_왼쪽", art.player_image(-1, True)),
    A.picture("쓰러짐", art.player_image(1, False, dead=True)),
]
_falling, _landed = [], []
for kind, rot, cells, w, h in STATES:
    color = art.PIECE_COLORS[kind]
    _falling.append(A.picture(f"{kind}{rot + 1}_낙하", art.piece_image(cells, w, h, color, trail=True)))
    _landed.append(A.picture(f"{kind}{rot + 1}", art.piece_image(cells, w, h, color, trail=False)))
PIC["piece"] = _falling + _landed  # 1~19: 떨어지는 중(잔상), 20~38: 쌓인 뒤
PIC["floor"] = [A.picture("바닥", art.floor_image())]
PIC["bg"] = [A.picture("배경", art.background_image())]

SND = {
    "manager": [A.sound("점프"), A.sound("게임오버"), A.sound("신기록")],
    "overlay": [A.sound("삐"), A.sound("출발")],
    "piece": [A.sound("착지")],
}


def pic_id(obj, name):
    return next(p["id"] for p in PIC[obj] if p["name"] == name)


def snd_id(obj, name):
    return next(s["id"] for s in SND[obj] if s["name"] == name)


# ================================================================ 변수 / 리스트 / 신호
GLOBAL_VARS = [
    ("상태", 0), ("점수", 0), ("최고점수", 0), ("신기록", 0),
    ("플레이어X", 108), ("플레이어Y", 18), ("방향", 1), ("땅에닿음", 1),
    ("카메라Y", 0), ("독극물Y", -45), ("맨위줄", -1), ("최고블록줄", 0),
    ("낙하속도", 1.5), ("죽음원인", 0), ("게이지최대", 40), ("프레임", 0),
]
# 게임 관리자의 함수들이 쓰는 계산용 변수 (함수는 모든 오브젝트에서 보이므로 전역 변수로 둔다)
GLOBAL_VARS += [(n, 0) for n in [
    "속도X", "속도Y", "목표속도", "점프누름", "점프버퍼", "코요테", "새X", "새Y", "칸", "왼칸", "오른칸",
    "줄", "기준", "줄아래", "줄위", "기준아래", "기준위", "줄기준", "채움값", "필요높이", "현재높이",
    "목표카메라", "독극물속도",
]]
for name, value in GLOBAL_VARS:
    add_variable(name, value)

LOCAL_VARS = {
    "piece": ["블록모양", "블록폭", "블록높이", "블록열", "바닥Y", "다음Y", "기준줄", "블록상태",
              "칸X1", "칸X2", "칸X3", "칸X4", "칸Y1", "칸Y2", "칸Y3", "칸Y4", "중심Y", "윗면",
              "생성거리", "다음생성거리", "마지막블록Y", "생성Y", "기둥높이"],
    "overlay": ["깜빡"],
    "score": ["표시점수"],
    "best": ["표시최고"],
    "dist": ["거리타이머"],
    "mk_me": ["비율_나"],
    "mk_best": ["비율_최고"],
    "mk_poison": ["비율_독"],
    "poison": ["물결타이머"],
    "player": ["모양번호", "이전모양"],
}
for obj, names in LOCAL_VARS.items():
    for name in names:
        add_variable(name, 0, object_id=OID[obj])

# 격자: 96줄 x 12칸. 양 끝 칸(0, 11)은 항상 1(벽)
add_list("격자", ([1] + [0] * 10 + [1]) * RING)
# 열높이: 각 세로줄(0~11번 칸)에 쌓인 가장 높은 줄 번호. 새 블록은 그 위에서만 생긴다
add_list("열높이", [0] * COLS)
add_list("모양X", [x for _, _, cells, _, _ in STATES for x, _ in cells])
add_list("모양Y", [y for _, _, cells, _, _ in STATES for _, y in cells])
add_list("모양폭", [w for *_, w, _ in STATES])
add_list("모양높이", [h for *_, h in STATES])

for m in ["타이틀", "게임 준비", "카운트다운", "게임 시작", "게임 끝"]:
    add_message(m)


# ================================================================ 코드 조각
def jump_key():
    return or_(key(KEY_SPACE), key(KEY_UP))


def slot_base(row_expr):
    """row 번째 줄의 0번 칸이 격자 리스트에서 몇 번째 항목인지 (1부터 시작)."""
    return add(mul(mod(row_expr, RING), COLS), 1)


def grid_at(base_var, col_var):
    return item("격자", add(v(base_var), v(col_var)))


# ---------------------------------------------------------------- 게임 관리자의 함수들
def fn_alloc_row():
    """맨위줄을 한 줄 올리고, 그 줄(순환 버퍼 칸)을 비운다. 0번 줄은 바닥이라 1로 채운다."""
    blocks = [
        chg("맨위줄", 1),
        setv("줄기준", slot_base(v("맨위줄"))),
        setv("채움값", 0),
        if_(eq(v("맨위줄"), 0), [setv("채움값", 1)]),
    ]
    for c in range(1, 11):
        blocks.append(set_item("격자", add(v("줄기준"), c), v("채움값")))
    define_function("새 줄 준비하기", blocks)


def fn_reset():
    define_function(
        "게임 변수 초기화",
        [
            setv("점수", 0),
            setv("프레임", 0),
            setv("플레이어X", 6 * CELL),
            setv("플레이어Y", CELL),
            setv("속도X", 0),
            setv("속도Y", 0),
            setv("땅에닿음", 1),
            setv("방향", 1),
            setv("점프버퍼", 0),
            setv("코요테", 0),
            setv("카메라Y", 0),
            setv("목표카메라", 0),
            setv("독극물Y", POISON_START),
            setv("독극물속도", 0.05),
            setv("최고블록줄", 0),
            setv("맨위줄", -1),
            setv("낙하속도", 1.5),
            setv("죽음원인", 0),
            setv("게이지최대", 40),
            *[set_item("열높이", c + 1, 0) for c in range(1, 11)],
        ],
    )


def fn_input():
    """방향키로 목표 속도를 정하고, 점프 키는 '누른 순간'을 6프레임 동안 기억한다(점프 버퍼).
    땅에서 떨어진 직후 6프레임 동안도 점프할 수 있다(코요테 타임). 점프 키를 일찍 떼면 낮게 뛴다."""
    define_function(
        "키 입력 처리",
        [
            setv("목표속도", 0),
            if_(key(KEY_LEFT), [chg("목표속도", -MOVE_V)]),
            if_(key(KEY_RIGHT), [chg("목표속도", MOVE_V)]),
            setv("속도X", add(v("속도X"), mul(sub(v("목표속도"), v("속도X")), 0.45))),
            if_(lt(abs_(v("속도X")), 0.05), [setv("속도X", 0)]),
            if_(lt(v("목표속도"), 0), [setv("방향", -1)]),
            if_(gt(v("목표속도"), 0), [setv("방향", 1)]),
            if_else(
                jump_key(),
                [if_(eq(v("점프누름"), 0), [setv("점프버퍼", 6)]), setv("점프누름", 1)],
                [setv("점프누름", 0), if_(gt(v("속도Y"), 2.5), [setv("속도Y", mul(v("속도Y"), 0.55))])],
            ),
            chg("점프버퍼", -1),
            if_else(eq(v("땅에닿음"), 1), [setv("코요테", 6)], [chg("코요테", -1)]),
            if_(
                and_(gt(v("점프버퍼"), 0), gt(v("코요테"), 0)),
                [
                    setv("속도Y", JUMP_V),
                    setv("점프버퍼", 0),
                    setv("코요테", 0),
                    play(snd_id("manager", "점프")),
                ],
            ),
        ],
    )


def fn_move_x():
    """새 x 위치의 앞쪽 가장자리가 들어가는 칸을 격자에서 확인해서, 막혀 있으면 벽에 붙여 세운다."""
    define_function(
        "좌우로 움직이기",
        [
            setv("줄아래", floor(div(v("플레이어Y"), CELL))),
            setv("줄위", floor(div(add(v("플레이어Y"), PLAYER_H - 0.1), CELL))),
            setv("기준아래", slot_base(v("줄아래"))),
            setv("기준위", slot_base(v("줄위"))),
            setv("새X", add(v("플레이어X"), v("속도X"))),
            if_(
                gt(v("속도X"), 0),
                [
                    setv("칸", floor(div(add(v("새X"), HALF_W - 0.1), CELL))),
                    if_(
                        gt(add(grid_at("기준아래", "칸"), grid_at("기준위", "칸")), 0),
                        [setv("새X", sub(mul(v("칸"), CELL), HALF_W)), setv("속도X", 0)],
                    ),
                ],
            ),
            if_(
                lt(v("속도X"), 0),
                [
                    setv("칸", floor(div(sub(v("새X"), HALF_W - 0.1), CELL))),
                    if_(
                        gt(add(grid_at("기준아래", "칸"), grid_at("기준위", "칸")), 0),
                        [setv("새X", add(mul(add(v("칸"), 1), CELL), HALF_W)), setv("속도X", 0)],
                    ),
                ],
            ),
            setv("플레이어X", v("새X")),
        ],
    )


def fn_move_y():
    """중력을 더하고, 떨어질 때는 발밑 칸, 올라갈 때는 머리 위 칸을 확인한다."""
    define_function(
        "점프와 중력",
        [
            setv("속도Y", sub(v("속도Y"), GRAVITY)),
            if_(lt(v("속도Y"), -MAX_FALL), [setv("속도Y", -MAX_FALL)]),
            setv("새Y", add(v("플레이어Y"), v("속도Y"))),
            setv("왼칸", floor(div(sub(v("플레이어X"), HALF_W - 0.1), CELL))),
            setv("오른칸", floor(div(add(v("플레이어X"), HALF_W - 0.1), CELL))),
            setv("땅에닿음", 0),
            if_else(
                le(v("속도Y"), 0),
                [
                    setv("줄", floor(div(v("새Y"), CELL))),
                    setv("기준", slot_base(v("줄"))),
                    if_(
                        gt(add(grid_at("기준", "왼칸"), grid_at("기준", "오른칸")), 0),
                        [setv("새Y", mul(add(v("줄"), 1), CELL)), setv("속도Y", 0), setv("땅에닿음", 1)],
                    ),
                ],
                [
                    setv("줄", floor(div(add(v("새Y"), PLAYER_H - 0.1), CELL))),
                    setv("기준", slot_base(v("줄"))),
                    if_(
                        gt(add(grid_at("기준", "왼칸"), grid_at("기준", "오른칸")), 0),
                        [setv("새Y", sub(mul(v("줄"), CELL), PLAYER_H)), setv("속도Y", 0)],
                    ),
                ],
            ),
            setv("플레이어Y", v("새Y")),
        ],
    )


def fn_camera():
    define_function(
        "점수와 카메라",
        [
            setv("현재높이", sub(floor(div(v("플레이어Y"), CELL)), 1)),
            if_(gt(v("현재높이"), v("점수")), [setv("점수", v("현재높이"))]),
            # 땅에 서 있을 때의 높이를 기준으로 카메라가 부드럽게 따라간다
            if_(eq(v("땅에닿음"), 1), [setv("목표카메라", sub(v("플레이어Y"), 95))]),
            if_(lt(sub(v("플레이어Y"), v("목표카메라")), 40), [setv("목표카메라", sub(v("플레이어Y"), 40))]),
            if_(gt(sub(v("플레이어Y"), v("목표카메라")), 190), [setv("목표카메라", sub(v("플레이어Y"), 190))]),
            if_(lt(v("목표카메라"), 0), [setv("목표카메라", 0)]),
            setv("카메라Y", add(v("카메라Y"), mul(sub(v("목표카메라"), v("카메라Y")), 0.1))),
            # 오른쪽 높이 지도의 눈금 최댓값
            setv("게이지최대", add(v("최고점수"), 10)),
            if_(lt(v("게이지최대"), add(v("점수"), 10)), [setv("게이지최대", add(v("점수"), 10))]),
            if_(lt(v("게이지최대"), 40), [setv("게이지최대", 40)]),
        ],
    )


def fn_poison():
    """독극물은 시간이 지날수록 빨라진다. 화면 아래로 너무 멀어지면 따라붙는다."""
    define_function(
        "독극물 올리기",
        [
            setv("독극물속도", add(0.05, div(v("프레임"), 90000))),
            if_(gt(v("독극물속도"), 0.32), [setv("독극물속도", 0.32)]),
            setv("독극물Y", add(v("독극물Y"), v("독극물속도"))),
            if_(
                lt(v("독극물Y"), sub(v("카메라Y"), 70)),
                [setv("독극물Y", add(v("독극물Y"), mul(sub(sub(v("카메라Y"), 70), v("독극물Y")), 0.03)))],
            ),
            if_(lt(v("독극물Y"), sub(v("카메라Y"), 150)), [setv("독극물Y", sub(v("카메라Y"), 150))]),
            if_(lt(add(v("플레이어Y"), 5), v("독극물Y")), [setv("죽음원인", 1), setv("상태", OVER)]),
        ],
    )


def fn_rows():
    define_function(
        "위쪽 줄 미리 만들기",
        [
            setv("필요높이", add(v("카메라Y"), 270)),
            if_(gt(mul(v("최고블록줄"), CELL), v("필요높이")), [setv("필요높이", mul(v("최고블록줄"), CELL))]),
            if_(lt(v("맨위줄"), floor(div(add(v("필요높이"), 170), CELL))), [call("새 줄 준비하기")]),
        ],
    )


# ---------------------------------------------------------------- 블록 오브젝트의 코드 조각
def cell_index(i):
    """i 번째 칸이 격자 리스트에서 몇 번째 항목인지."""
    return add(mul(mod(add(v("기준줄"), v(f"칸Y{i}")), RING), COLS), v(f"칸X{i}"))


def cell_hits_player(i):
    x0 = mul(sub(v(f"칸X{i}"), 1), CELL)
    x1 = mul(v(f"칸X{i}"), CELL)
    y0 = add(v("바닥Y"), mul(v(f"칸Y{i}"), CELL))
    y1 = add(v("바닥Y"), mul(add(v(f"칸Y{i}"), 1), CELL))
    return and_(
        and_(gt(add(v("플레이어X"), 5), x0), lt(sub(v("플레이어X"), 5), x1)),
        and_(gt(add(v("플레이어Y"), 12), y0), lt(add(v("플레이어Y"), 1), y1)),
    )


def piece_pick_blocks():
    """새 블록의 모양·세로줄·칸 위치·생성 높이를 정한다 (30%는 플레이어 머리 위를 노린다)."""
    return [
            setv("블록모양", rand(0, len(STATES) - 1)),
            setv("블록폭", item("모양폭", add(v("블록모양"), 1))),
            setv("블록높이", item("모양높이", add(v("블록모양"), 1))),
            if_else(
                le(rand(1, 100), TARGET_PERCENT),
                [
                    setv("블록열", sub(floor(div(v("플레이어X"), CELL)), floor(div(sub(v("블록폭"), 1), 2)))),
                    if_(lt(v("블록열"), 1), [setv("블록열", 1)]),
                    if_(gt(v("블록열"), sub(11, v("블록폭"))), [setv("블록열", sub(11, v("블록폭")))]),
                ],
                [setv("블록열", rand(1, sub(11, v("블록폭"))))],
            ),
            *[
                setv(f"칸X{i}", add(add(v("블록열"), item("모양X", add(mul(v("블록모양"), 4), i))), 1))
                for i in range(1, 5)
            ],
            *[setv(f"칸Y{i}", item("모양Y", add(mul(v("블록모양"), 4), i))) for i in range(1, 5)],
            # 이 블록이 떨어질 세로줄들 중 가장 높이 쌓인 줄 → 그보다 위에서 생긴다
            setv("기둥높이", item("열높이", v("칸X1"))),
            *[
                if_(gt(item("열높이", v(f"칸X{i}")), v("기둥높이")), [setv("기둥높이", item("열높이", v(f"칸X{i}")))])
                for i in range(2, 5)
            ],
            setv("생성Y", add(v("카메라Y"), 290)),
            if_(gt(mul(add(v("기둥높이"), 2), CELL), v("생성Y")), [setv("생성Y", mul(add(v("기둥높이"), 2), CELL))]),
            # 바로 전에 생긴 블록과 겹치지 않게 90px 이상 띄운다
            if_(gt(add(v("마지막블록Y"), 90), v("생성Y")), [setv("생성Y", add(v("마지막블록Y"), 90))]),
    ]


def piece_fall_blocks():
    """아래 칸이 막혀 있으면 딱 맞게 내려앉아 격자와 열높이에 기록하고, 아니면 한 걸음 내려간다."""
    lookups = [item("격자", cell_index(i)) for i in range(1, 5)]
    landed_top = add(v("기준줄"), sub(v("블록높이"), 1))
    return [
            setv("다음Y", sub(v("바닥Y"), v("낙하속도"))),
            setv("기준줄", floor(div(v("다음Y"), CELL))),
            if_else(
                gt(add(add(lookups[0], lookups[1]), add(lookups[2], lookups[3])), 0),
                [
                    chg("기준줄", 1),
                    setv("바닥Y", mul(v("기준줄"), CELL)),
                    *[set_item("격자", cell_index(i), 1) for i in range(1, 5)],
                    *[
                        if_(
                            gt(add(v("기준줄"), v(f"칸Y{i}")), item("열높이", v(f"칸X{i}"))),
                            [set_item("열높이", v(f"칸X{i}"), add(v("기준줄"), v(f"칸Y{i}")))],
                        )
                        for i in range(1, 5)
                    ],
                    if_(gt(landed_top, v("최고블록줄")), [setv("최고블록줄", landed_top)]),
                    setv("블록상태", 1),
                ],
                [setv("바닥Y", v("다음Y"))],
            ),
    ]


def piece_hit_blocks():
    """떨어지는 블록의 네 칸 중 하나라도 플레이어와 겹치면 게임 끝 (먼저 전체 네모로 빠르게 거른다)."""
    coarse = and_(
        and_(
            gt(add(v("플레이어X"), 5), mul(v("블록열"), CELL)),
            lt(sub(v("플레이어X"), 5), mul(add(v("블록열"), v("블록폭")), CELL)),
        ),
        and_(
            gt(add(v("플레이어Y"), 12), v("바닥Y")),
            lt(add(v("플레이어Y"), 1), add(v("바닥Y"), mul(v("블록높이"), CELL))),
        ),
    )
    fine = or_(or_(cell_hits_player(1), cell_hits_player(2)), or_(cell_hits_player(3), cell_hits_player(4)))
    return [if_(coarse, [if_(fine, [setv("죽음원인", 2), setv("상태", OVER)])])]


def define_all_functions():
    fn_alloc_row()
    fn_reset()
    fn_input()
    fn_move_x()
    fn_move_y()
    fn_camera()
    fn_poison()
    fn_rows()


# ================================================================ 오브젝트별 코드
def scripts_manager():
    main = [
        when_run(),
        hide(),
        setv("최고점수", 0),
        setv("신기록", 0),
        call("게임 변수 초기화"),
        setv("상태", TITLE),
        broadcast("타이틀"),
        wait_until(jump_key()),
        forever(
            [
                setv("상태", READY),
                broadcast("게임 준비"),
                call("게임 변수 초기화"),
                setv("점프누름", 1),
                repeat(26, [call("새 줄 준비하기")]),
                broadcast_wait("카운트다운"),
                setv("상태", PLAYING),
                broadcast("게임 시작"),
                # 한 바퀴 = 한 프레임 (1초에 60번)
                repeat_while(
                    eq(v("상태"), PLAYING),
                    [
                        chg("프레임", 1),
                        call("키 입력 처리"),
                        call("좌우로 움직이기"),
                        call("점프와 중력"),
                        call("점수와 카메라"),
                        call("독극물 올리기"),
                        call("위쪽 줄 미리 만들기"),
                    ],
                ),
                play(snd_id("manager", "게임오버")),
                setv("신기록", 0),
                if_(gt(v("점수"), v("최고점수")), [setv("신기록", 1), setv("최고점수", v("점수"))]),
                broadcast("게임 끝"),
                wait(1.2),
                if_(eq(v("신기록"), 1), [play(snd_id("manager", "신기록"))]),
                wait_until(not_(jump_key())),
                wait_until(jump_key()),
            ]
        ),
    ]
    return [thread(40, 40, main)]


def scripts_overlay():
    t_run = [when_run(), hide()]
    t_title = [
        when_message("타이틀"),
        locate_xy(0, 5),
        shape_id(pic_id("overlay", "타이틀")),
        show(),
        setv("깜빡", 0),
        repeat_while(
            eq(v("상태"), TITLE),
            [
                chg("깜빡", 1),
                if_(eq(v("깜빡"), 30), [shape_id(pic_id("overlay", "타이틀_깜빡"))]),
                if_(ge(v("깜빡"), 60), [shape_id(pic_id("overlay", "타이틀")), setv("깜빡", 0)]),
            ],
        ),
    ]
    t_ready = [when_message("게임 준비"), hide()]
    beep = snd_id("overlay", "삐")
    t_count = [
        when_message("카운트다운"),
        locate_xy(0, 30),
        shape_id(pic_id("overlay", "셋")),
        show(),
        play(beep),
        wait(0.6),
        shape_id(pic_id("overlay", "둘")),
        play(beep),
        wait(0.6),
        shape_id(pic_id("overlay", "하나")),
        play(beep),
        wait(0.6),
        shape_id(pic_id("overlay", "출발")),
        play(snd_id("overlay", "출발")),
    ]
    t_start = [when_message("게임 시작"), wait(0.6), if_(eq(v("상태"), PLAYING), [hide()])]
    t_over = [
        when_message("게임 끝"),
        wait(0.8),
        locate_xy(0, 10),
        if_else(
            eq(v("죽음원인"), 1),
            [shape_id(pic_id("overlay", "게임오버_독극물"))],
            [shape_id(pic_id("overlay", "게임오버_블록"))],
        ),
        show(),
    ]
    return [
        thread(40, 40, t_run),
        thread(40, 140, t_title),
        thread(40, 420, t_ready),
        thread(420, 40, t_count),
        thread(420, 520, t_start),
        thread(420, 660, t_over),
    ]


def scripts_result():
    return [
        thread(40, 40, [when_run(), hide()]),
        thread(40, 140, [when_message("게임 준비"), hide()]),
        thread(
            40,
            240,
            [
                when_message("게임 끝"),
                wait(0.8),
                if_else(
                    eq(v("신기록"), 1),
                    [write_text(join("신기록! ", v("점수")))],
                    [write_text(join("기록 ", v("점수")))],
                ),
                show(),
            ],
        ),
    ]


def scripts_number(var_name, shown_var):
    return [
        thread(
            40,
            40,
            [
                when_run(),
                setv(shown_var, -1),
                forever([if_(ne(v(var_name), v(shown_var)), [write_text(v(var_name)), setv(shown_var, v(var_name))])]),
            ],
        )
    ]


def scripts_dist():
    return [
        thread(
            40,
            40,
            [
                when_run(),
                write_text("-"),
                forever(
                    [
                        if_(
                            eq(v("상태"), PLAYING),
                            [
                                chg("거리타이머", 1),
                                if_(
                                    ge(v("거리타이머"), 6),
                                    [
                                        setv("거리타이머", 0),
                                        write_text(
                                            join(div(round_(div(sub(v("플레이어Y"), v("독극물Y")), 1.8)), 10), "m")
                                        ),
                                    ],
                                ),
                            ],
                        )
                    ]
                ),
            ],
        )
    ]


GAUGE_RANGE = art.GAUGE_TOP - art.GAUGE_BOTTOM


def gauge_loop(ratio_var, height_expr, x, hide_when_zero=None):
    body = []
    if hide_when_zero:
        body.append(if_else(gt(v(hide_when_zero), 0), [show()], [hide()]))
    body += [
        setv(ratio_var, div(height_expr, v("게이지최대"))),
        if_(lt(v(ratio_var), 0), [setv(ratio_var, 0)]),
        if_(gt(v(ratio_var), 1), [setv(ratio_var, 1)]),
        locate_y(add(art.GAUGE_BOTTOM, mul(v(ratio_var), GAUGE_RANGE))),
    ]
    return [thread(40, 40, [when_run(), locate_x(x), forever(body)])]


def scripts_poison():
    top_to_center = art.POISON_H / 2 - art.POISON_SURFACE  # 수면에서 그림 중심까지
    return [
        thread(
            40,
            40,
            [
                when_run(),
                locate_x(0),
                forever(
                    [
                        locate_y(sub(v("독극물Y"), add(v("카메라Y"), 135 + top_to_center))),
                        chg("물결타이머", 1),
                        if_(ge(v("물결타이머"), 7), [setv("물결타이머", 0), next_shape()]),
                    ]
                ),
            ],
        )
    ]


def scripts_player():
    main = [
        when_run(),
        clear_effects(),
        show(),
        setv("이전모양", 0),
        forever(
            [
                locate_xy(sub(v("플레이어X"), -X_OFF), sub(v("플레이어Y"), add(v("카메라Y"), 135 - 8))),
                setv("모양번호", 1),
                if_(lt(v("방향"), 0), [setv("모양번호", 2)]),
                if_(eq(v("땅에닿음"), 0), [chg("모양번호", 2)]),
                if_(eq(v("상태"), OVER), [setv("모양번호", 5)]),
                if_(ne(v("모양번호"), v("이전모양")), [shape(v("모양번호")), setv("이전모양", v("모양번호"))]),
            ]
        ),
    ]
    sink = [
        when_message("게임 끝"),
        if_(
            eq(v("죽음원인"), 1),
            [repeat(40, [setv("플레이어Y", sub(v("플레이어Y"), 0.35)), add_effect("transparency", 2.5)])],
        ),
    ]
    reset = [when_message("게임 준비"), clear_effects()]
    return [thread(40, 40, main), thread(40, 330, sink), thread(40, 470, reset)]


def scripts_piece():
    spawner = [
        when_run(),
        hide(),
        setv("생성거리", 70),
        setv("다음생성거리", 100),
        setv("마지막블록Y", -1000),
        forever(
            [
                if_(
                    eq(v("상태"), PLAYING),
                    [
                        setv("생성거리", add(v("생성거리"), v("낙하속도"))),
                        setv("마지막블록Y", sub(v("마지막블록Y"), v("낙하속도"))),
                        if_(
                            ge(v("생성거리"), v("다음생성거리")),
                            [
                                *piece_pick_blocks(),
                                # 화면보다 너무 높은 곳(높은 탑 위)이거나 격자 줄이 아직 준비 안 됐으면 다음 프레임에 다시 고른다
                                if_(
                                    and_(
                                        le(v("생성Y"), add(v("카메라Y"), 330)),
                                        ge(v("맨위줄"), add(floor(div(v("생성Y"), CELL)), add(v("블록높이"), 1))),
                                    ),
                                    [
                                        setv("바닥Y", v("생성Y")),
                                        setv("마지막블록Y", v("생성Y")),
                                        create_clone_self(),
                                        setv("생성거리", 0),
                                        setv("다음생성거리", sub(115, div(v("프레임"), 300))),
                                        if_(lt(v("다음생성거리"), 90), [setv("다음생성거리", 90)]),
                                        setv("다음생성거리", add(v("다음생성거리"), rand(0, 24))),
                                    ],
                                ),
                            ],
                        ),
                        # 시간이 지날수록 빨리 떨어진다
                        setv("낙하속도", add(1.5, div(v("프레임"), 10000))),
                        if_(gt(v("낙하속도"), 2.8), [setv("낙하속도", 2.8)]),
                    ],
                )
            ]
        ),
    ]

    screen_y = sub(add(v("바닥Y"), mul(v("블록높이"), CELL / 2)), add(v("카메라Y"), 135))
    clone = [
        when_clone(),
        setv("블록상태", 0),
        shape(add(v("블록모양"), 1)),
        locate_x(add(add(mul(v("블록열"), CELL), mul(v("블록폭"), CELL / 2)), X_OFF)),
        locate_y(screen_y),
        show(),
        # 떨어지는 동안 (한 바퀴 = 한 프레임)
        repeat_while(
            eq(v("블록상태"), 0),
            [
                if_(
                    eq(v("상태"), PLAYING),
                    [
                        *piece_fall_blocks(),
                        # 떨어지는 블록에 깔렸는지 검사
                        *piece_hit_blocks(),
                        if_(
                            lt(add(v("바닥Y"), mul(v("블록높이"), CELL)), sub(v("독극물Y"), 8)),
                            [delete_clone()],
                        ),
                    ],
                ),
                locate_y(screen_y),
            ],
        ),
        # 내려앉은 뒤: 잔상 없는 모양으로 바꾸고, 반짝인 다음 카메라에 맞춰 움직이기만 한다
        shape(add(v("블록모양"), len(STATES) + 1)),
        play(snd_id("piece", "착지")),
        setv("중심Y", sub(add(v("바닥Y"), mul(v("블록높이"), CELL / 2)), 135)),
        setv("윗면", add(add(v("바닥Y"), mul(v("블록높이"), CELL)), 24)),
        set_effect("brightness", 45),
        repeat(5, [add_effect("brightness", -9), locate_y(sub(v("중심Y"), v("카메라Y")))]),
        set_effect("brightness", 0),
        forever(
            [
                if_(lt(v("윗면"), v("독극물Y")), [delete_clone()]),
                locate_y(sub(v("중심Y"), v("카메라Y"))),
            ]
        ),
    ]
    reset = [
        when_message("게임 준비"),
        delete_clone(),
        setv("생성거리", 70),
        setv("다음생성거리", 100),
        setv("마지막블록Y", -1000),
    ]
    return [thread(40, 40, spawner), thread(760, 40, clone), thread(40, 1300, reset)]


def scripts_floor():
    return [thread(40, 40, [when_run(), locate_x(0), forever([locate_y(sub(CELL / 2 - 135, v("카메라Y")))])])]


# ================================================================ 조립
def build_project():
    define_all_functions()
    gx = art.GAUGE_X
    objects = []

    def add_obj(obj, scripts):
        obj["script"] = json.dumps(scripts, ensure_ascii=False, separators=(",", ":"))
        objects.append(obj)

    add_obj(sprite_object(OID["manager"], "게임 관리자", PIC["manager"], SND["manager"], visible=False), scripts_manager())
    add_obj(text_object(OID["result"], "결과 글상자", "기록 0", 0, -2, 24, "#ffffff", visible=False), scripts_result())
    add_obj(sprite_object(OID["overlay"], "안내 화면", PIC["overlay"], SND["overlay"], 0, 5), scripts_overlay())
    add_obj(text_object(OID["score"], "점수 글상자", "0", -165, 27, 34, "#ffffff"), scripts_number("점수", "표시점수"))
    add_obj(text_object(OID["best"], "최고기록 글상자", "0", -165, -27, 20, "#ffd84a"), scripts_number("최고점수", "표시최고"))
    add_obj(text_object(OID["dist"], "독극물거리 글상자", "-", 165, 95, 20, "#7cf86a"), scripts_dist())
    add_obj(
        sprite_object(OID["mk_me"], "높이표시_나", PIC["mk_me"], [], gx + 8, art.GAUGE_BOTTOM),
        gauge_loop("비율_나", sub(div(v("플레이어Y"), CELL), 1), gx + 8),
    )
    add_obj(
        sprite_object(OID["mk_best"], "높이표시_최고", PIC["mk_best"], [], gx - 12, art.GAUGE_BOTTOM, visible=False),
        gauge_loop("비율_최고", v("최고점수"), gx - 12, hide_when_zero="최고점수"),
    )
    add_obj(
        sprite_object(OID["mk_poison"], "높이표시_독극물", PIC["mk_poison"], [], gx - 12, art.GAUGE_BOTTOM),
        gauge_loop("비율_독", sub(div(v("독극물Y"), CELL), 1), gx - 12),
    )
    add_obj(sprite_object(OID["poison"], "독극물", PIC["poison"], [], 0, -300), scripts_poison())
    add_obj(sprite_object(OID["player"], "플레이어", PIC["player"], [], 0, -109), scripts_player())
    add_obj(sprite_object(OID["piece"], "블록", PIC["piece"], SND["piece"], 0, 200, visible=False), scripts_piece())
    add_obj(sprite_object(OID["floor"], "바닥", PIC["floor"], [], 0, -126), scripts_floor())
    add_obj(sprite_object(OID["bg"], "배경", PIC["bg"], [], 0, 0), [])

    variables = [dict(vv) for vv in R.vars.values()] + [dict(ll) for ll in R.lists.values()]
    variables += [
        {"name": "초시계", "id": "brih", "visible": False, "value": "0", "variableType": "timer",
         "isCloud": False, "isRealTime": False, "cloudDate": False, "object": None, "x": 134, "y": -70},
        {"name": " 대답 ", "id": "1vu8", "visible": False, "value": "0", "variableType": "answer",
         "isCloud": False, "isRealTime": False, "cloudDate": False, "object": None, "x": 150, "y": -100},
    ]
    return {
        "name": "테트로 클라임",
        "objects": objects,
        "scenes": [{"id": SCENE_ID, "name": "장면 1"}],
        "variables": variables,
        "messages": [{"id": mid, "name": name} for name, mid in R.messages.items()],
        "functions": FUNCTIONS,
        "tables": [],
        "speed": 60,
        "interface": {"menuWidth": 280, "canvasWidth": 480, "object": OID["manager"]},
        "expansionBlocks": [],
        "aiUtilizeBlocks": [],
        "hardwareLiteBlocks": [],
        "externalModules": [],
        "externalModulesLite": [],
    }


def write_ent(project, ent_path, unpacked_dir=None):
    files = dict(A.files)
    files["temp/project.json"] = json.dumps(project, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    now = int(time.time())
    dirs = set()
    for path in files:
        parts = path.split("/")[:-1]
        for i in range(1, len(parts) + 1):
            dirs.add("/".join(parts[:i]))
    with tarfile.open(ent_path, "w:gz", format=tarfile.USTAR_FORMAT, compresslevel=6) as tar:
        for d in sorted(dirs):
            ti = tarfile.TarInfo(d + "/")
            ti.type = tarfile.DIRTYPE
            ti.mode = 0o755
            ti.mtime = now
            tar.addfile(ti)
        for path in sorted(files):
            data = files[path]
            ti = tarfile.TarInfo(path)
            ti.size = len(data)
            ti.mode = 0o644
            ti.mtime = now
            tar.addfile(ti, io.BytesIO(data))
    if unpacked_dir:
        for path, data in files.items():
            full = os.path.join(unpacked_dir, path)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, "wb") as f:
                f.write(data)


def count_blocks(project):
    total = 0

    def walk(b):
        nonlocal total
        if isinstance(b, dict) and "type" in b:
            total += 1
            for p in b.get("params", []):
                walk(p)
            for st in b.get("statements", []):
                for x in st:
                    walk(x)

    for o in project["objects"]:
        for th in json.loads(o["script"]):
            for b in th:
                walk(b)
    for f in project["functions"]:
        for th in json.loads(f["content"]):
            for b in th:
                walk(b)
    return total


if __name__ == "__main__":
    out = os.path.join(ROOT, "tetro_climb.ent")
    unpacked = sys.argv[1] if len(sys.argv) > 1 else None
    proj = build_project()
    write_ent(proj, out, unpacked)
    print(f"{out}  ({os.path.getsize(out) / 1024:.0f} KB, 오브젝트 {len(proj['objects'])}개, 블록 {count_blocks(proj)}개)")
