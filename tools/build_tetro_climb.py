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
    add,
    add_list,
    add_message,
    add_variable,
    and_,
    broadcast,
    call,
    chg,
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
    not_,
    or_,
    play,
    rand,
    remove_dialog,
    repeat,
    repeat_while,
    round_,
    say,
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
JUMP_V = 7.6  # 첫 점프
AIR_JUMP_V = 7.0  # 공중에서 한 번 더 (2단 점프)
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


def sprite_object(obj_id, name, pictures, sounds, x=0, y=0, visible=True, scale=1):
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


def text_object(obj_id, name, text, x, y, size, visible=True, bg="#ffffff", width=None, height=None):
    """엔트리 기본 글꼴(나눔고딕) 글상자. width 를 주면 여러 줄 글상자가 된다."""
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
            "width": width or 40,
            "height": height or size + 8,
            "font": f"{size}px Nanum Gothic",
            "visible": visible,
            "colour": "#000000",
            "text": text,
            "textAlign": 0,
            "lineBreak": width is not None,
            "bgColor": bg,
            "underLine": False,
            "strike": False,
            "fontSize": size,
        },
    }


# ================================================================ 오브젝트 id / 그림 / 소리
OID = {k: gid() for k in [
    "manager", "title", "result", "guide", "howto", "keys", "poison", "piece", "player", "floor", "bg",
]}

STATES = art.piece_states()  # 19가지 (종류, 회전, 칸, 폭, 높이)

PIC = {
    "manager": [A.picture("관리자", art.blank())],
    "poison": [A.picture("독극물", art.poison_image())],
    "player": [A.picture("오른쪽", art.player_image(1)), A.picture("왼쪽", art.player_image(-1))],
    # 모양 1~19: I1, I2, O1, T1 ... (블록모양 + 1 번째 모양)
    "piece": [
        A.picture(f"{kind}{rot + 1}", art.piece_image(cells, w, h, art.PIECE_COLORS[kind]))
        for kind, rot, cells, w, h in STATES
    ],
    "floor": [A.picture("바닥", art.floor_image())],
    "bg": [A.picture("배경", art.background_image())],
}
SND = {"manager": [A.sound("점프"), A.sound("게임오버")]}


def pic_id(obj, name):
    return next(p["id"] for p in PIC[obj] if p["name"] == name)


def snd_id(obj, name):
    return next(s["id"] for s in SND[obj] if s["name"] == name)


# ================================================================ 변수 / 리스트 / 신호
# 엔트리는 변수를 '변수 목록 앞에서부터' 찾기 때문에, 매 프레임 많은 복제본이 읽는 변수를 앞에 둔다.
# (이름, 처음 값, 지역 변수라면 오브젝트)
VARIABLES = [
    ("카메라Y", 0, None),
    ("독극물Y", POISON_START, None),
    ("중심Y", 0, "piece"),
    ("윗면", 0, "piece"),
    ("블록상태", 0, "piece"),
    ("상태", 0, None),
    ("바닥Y", 0, "piece"),
    ("블록높이", 0, "piece"),
    ("낙하속도", 1.5, None),
    ("플레이어X", 108, None),
    ("플레이어Y", 18, None),
    ("블록열", 0, "piece"),
    ("블록폭", 0, "piece"),
    ("다음Y", 0, "piece"),
    ("기준줄", 0, "piece"),
    *[(f"칸X{i}", 0, "piece") for i in range(1, 5)],
    *[(f"칸Y{i}", 0, "piece") for i in range(1, 5)],
    ("속도X", 0, None),
    ("속도Y", 0, None),
    ("땅에닿음", 1, None),
    ("새X", 0, None),
    ("새Y", 0, None),
    ("줄", 0, None),
    ("기준", 0, None),
    ("칸", 0, None),
    ("왼칸", 0, None),
    ("오른칸", 0, None),
    ("줄아래", 0, None),
    ("줄위", 0, None),
    ("기준아래", 0, None),
    ("기준위", 0, None),
    ("점프누름", 0, None),
    ("점프횟수", 0, None),
    ("이전플레이어Y", 18, None),
    ("목표카메라", 0, None),
    ("현재높이", 0, None),
    ("점수", 0, None),
    ("최고점수", 0, None),
    ("독극물속도", 0.06, None),
    ("맨위줄", -1, None),
    ("필요높이", 0, None),
    ("최고블록줄", 0, None),
    ("프레임", 0, None),
    # 떨어지는 블록이 플레이어를 밀어낼 때 쓰는 계산용 변수
    ("칸왼쪽", 0, None),
    ("칸아래", 0, None),
    ("밀위", 0, None),
    ("밀아래", 0, None),
    ("밀왼", 0, None),
    ("밀오른", 0, None),
    ("밀방향", 0, None),
    ("최소밀기", 0, None),
    ("끼임줄1", 0, None),
    ("끼임줄2", 0, None),
    ("끼임칸1", 0, None),
    ("끼임칸2", 0, None),
    ("줄기준", 0, None),
    ("채움값", 0, None),
    # 블록 원본이 새 블록을 고를 때만 쓰는 변수
    ("블록모양", 0, "piece"),
    ("생성거리", 0, "piece"),
    ("다음생성거리", 0, "piece"),
    ("마지막블록Y", 0, "piece"),
    ("생성Y", 0, "piece"),
    ("기둥높이", 0, "piece"),
    # 플레이어가 보는 방향 (1 오른쪽, -1 왼쪽)
    ("보는방향", 1, "player"),
]
# 무대에 보이는 변수 (엔트리 기본 변수 창). 좌표는 변수 창의 왼쪽 위 근처, y 는 아래로 갈수록 커진다
SHOWN = {"점수": (-228, -112), "최고점수": (-228, -84)}
for name, value, obj in VARIABLES:
    sx, sy = SHOWN.get(name, (0, 0))
    add_variable(name, value, object_id=OID[obj] if obj else None, visible=name in SHOWN, x=sx, y=sy)

# 격자: 96줄 x 12칸. 양 끝 칸(0, 11)은 항상 1(벽)
add_list("격자", ([1] + [0] * 10 + [1]) * RING)
# 열높이: 각 세로줄(0~11번 칸)에 쌓인 가장 높은 줄 번호. 새 블록은 그 위에서만 생긴다
add_list("열높이", [0] * COLS)
add_list("모양X", [x for _, _, cells, _, _ in STATES for x, _ in cells])
add_list("모양Y", [y for _, _, cells, _, _ in STATES for _, y in cells])
add_list("모양폭", [w for *_, w, _ in STATES])
add_list("모양높이", [h for *_, h in STATES])

for m in ["게임 준비", "게임 시작", "게임 끝"]:
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
            setv("점프횟수", 0),
            setv("이전플레이어Y", CELL),
            setv("카메라Y", 0),
            setv("목표카메라", 0),
            setv("독극물Y", POISON_START),
            setv("독극물속도", 0.06),
            setv("최고블록줄", 0),
            setv("맨위줄", -1),
            setv("낙하속도", 1.5),
            *[set_item("열높이", c + 1, 0) for c in range(1, 11)],
        ],
    )


def fn_input():
    """방향키로 좌우 속도를 정하고, 점프 키를 '새로 누른 순간'에 점프한다. 공중에서는 한 번 더 뛸 수 있다."""
    define_function(
        "키 입력 처리",
        [
            setv("속도X", 0),
            if_(key(KEY_LEFT), [setv("속도X", -MOVE_V)]),
            if_(key(KEY_RIGHT), [setv("속도X", MOVE_V)]),
            if_(eq(v("땅에닿음"), 1), [setv("점프횟수", 0)]),
            if_else(
                jump_key(),
                [
                    if_(
                        eq(v("점프누름"), 0),
                        [
                            setv("점프누름", 1),
                            if_else(
                                eq(v("땅에닿음"), 1),
                                [setv("속도Y", JUMP_V), setv("점프횟수", 1), play(snd_id("manager", "점프"))],
                                [
                                    # 2단 점프
                                    if_(
                                        lt(v("점프횟수"), 2),
                                        [setv("속도Y", AIR_JUMP_V), setv("점프횟수", 2), play(snd_id("manager", "점프"))],
                                    )
                                ],
                            ),
                        ],
                    )
                ],
                [setv("점프누름", 0)],
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
            # 땅에 서 있을 때의 높이를 기준으로 카메라가 따라간다
            if_(eq(v("땅에닿음"), 1), [setv("목표카메라", sub(v("플레이어Y"), 95))]),
            if_(lt(sub(v("플레이어Y"), v("목표카메라")), 40), [setv("목표카메라", sub(v("플레이어Y"), 40))]),
            if_(gt(sub(v("플레이어Y"), v("목표카메라")), 190), [setv("목표카메라", sub(v("플레이어Y"), 190))]),
            if_(lt(v("목표카메라"), 0), [setv("목표카메라", 0)]),
            setv("카메라Y", add(v("카메라Y"), mul(sub(v("목표카메라"), v("카메라Y")), 0.1))),
        ],
    )


def fn_poison():
    """독극물은 시간이 지날수록 빨라진다. 화면 아래로 너무 멀어지면 따라붙는다."""
    define_function(
        "독극물 올리기",
        [
            setv("독극물속도", add(0.06, div(v("프레임"), 90000))),
            if_(gt(v("독극물속도"), 0.32), [setv("독극물속도", 0.32)]),
            setv("독극물Y", add(v("독극물Y"), v("독극물속도"))),
            if_(
                lt(v("독극물Y"), sub(v("카메라Y"), 70)),
                [setv("독극물Y", add(v("독극물Y"), mul(sub(sub(v("카메라Y"), 70), v("독극물Y")), 0.03)))],
            ),
            if_(lt(v("독극물Y"), sub(v("카메라Y"), 150)), [setv("독극물Y", sub(v("카메라Y"), 150))]),
            if_(lt(add(v("플레이어Y"), 5), v("독극물Y")), [setv("상태", OVER)]),
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
    def landed_top():
        return add(v("기준줄"), sub(v("블록높이"), 1))

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
                if_(gt(landed_top(), v("최고블록줄")), [setv("최고블록줄", landed_top())]),
                setv("블록상태", 1),
            ],
            [setv("바닥Y", v("다음Y"))],
        ),
    ]


def piece_push_blocks():
    """떨어지는 블록 전체 네모가 플레이어와 겹칠 때만, 네 칸 각각에 대해 '플레이어 밀어내기'를 한다."""
    coarse = and_(
        and_(
            gt(add(v("플레이어X"), HALF_W), mul(v("블록열"), CELL)),
            lt(sub(v("플레이어X"), HALF_W), mul(add(v("블록열"), v("블록폭")), CELL)),
        ),
        and_(
            gt(add(v("플레이어Y"), PLAYER_H), v("바닥Y")),
            lt(v("플레이어Y"), add(v("바닥Y"), mul(v("블록높이"), CELL))),
        ),
    )
    body = []
    for i in range(1, 5):
        body += [
            setv("칸왼쪽", mul(sub(v(f"칸X{i}"), 1), CELL)),
            setv("칸아래", add(v("바닥Y"), mul(v(f"칸Y{i}"), CELL))),
            call("플레이어 밀어내기"),
        ]
    return [if_(coarse, body)]


def fn_push():
    """떨어지는 블록의 한 칸(왼쪽 x = 칸왼쪽, 아래 y = 칸아래)과 플레이어가 겹치면, 가장 조금 움직이는 쪽으로 밀어낸다.
    위로 밀리면 블록 위에 올라탄 것(같이 내려감), 아래로 밀리면 머리에 부딪힌 것. 밀린 곳이 막혀 있으면 끼여서 게임 끝."""
    def px():
        return v("플레이어X")

    def py():
        return v("플레이어Y")

    overlap = and_(
        and_(gt(add(px(), HALF_W), add(v("칸왼쪽"), 0.01)), lt(sub(px(), HALF_W), add(v("칸왼쪽"), CELL - 0.01))),
        and_(gt(add(py(), PLAYER_H), add(v("칸아래"), 0.01)), lt(py(), add(v("칸아래"), CELL - 0.01))),
    )
    define_function(
        "플레이어 밀어내기",
        [
            if_(
                overlap,
                [
                    setv("밀위", sub(add(v("칸아래"), CELL), v("플레이어Y"))),
                    setv("밀아래", sub(add(v("플레이어Y"), PLAYER_H), v("칸아래"))),
                    setv("밀왼", sub(add(v("플레이어X"), HALF_W), v("칸왼쪽"))),
                    setv("밀오른", sub(add(v("칸왼쪽"), CELL + HALF_W), v("플레이어X"))),
                    setv("밀방향", 1),
                    setv("최소밀기", v("밀위")),
                    if_(lt(v("밀아래"), v("최소밀기")), [setv("최소밀기", v("밀아래")), setv("밀방향", 2)]),
                    if_(lt(v("밀왼"), v("최소밀기")), [setv("최소밀기", v("밀왼")), setv("밀방향", 3)]),
                    if_(lt(v("밀오른"), v("최소밀기")), [setv("밀방향", 4)]),
                    # 바닥에 선 채로 머리 위에서 블록이 내려올 때: 몸이 절반도 안 걸쳤으면 깔리지 않고 옆으로 밀려난다
                    if_(
                        and_(eq(v("밀방향"), 2), eq(v("땅에닿음"), 1)),
                        [
                            if_else(
                                lt(v("밀왼"), v("밀오른")),
                                [if_(lt(v("밀왼"), HALF_W + 1), [setv("밀방향", 3)])],
                                [if_(lt(v("밀오른"), HALF_W + 1), [setv("밀방향", 4)])],
                            )
                        ],
                    ),
                    # 바로 전 프레임에 블록 위쪽에 있었다면 무조건 올라탄다
                    if_(
                        ge(v("이전플레이어Y"), sub(add(v("칸아래"), CELL), 0.5)),
                        [setv("밀방향", 1)],
                    ),
                    if_(
                        eq(v("밀방향"), 1),
                        [
                            setv("플레이어Y", add(v("플레이어Y"), v("밀위"))),
                            if_(lt(v("속도Y"), mul(v("낙하속도"), -1)), [setv("속도Y", mul(v("낙하속도"), -1))]),
                            setv("땅에닿음", 1),
                        ],
                    ),
                    if_(
                        eq(v("밀방향"), 2),
                        [
                            setv("플레이어Y", sub(v("플레이어Y"), v("밀아래"))),
                            if_(gt(v("속도Y"), mul(v("낙하속도"), -1)), [setv("속도Y", mul(v("낙하속도"), -1))]),
                        ],
                    ),
                    if_(eq(v("밀방향"), 3), [setv("플레이어X", sub(v("플레이어X"), v("밀왼"))), setv("속도X", 0)]),
                    if_(eq(v("밀방향"), 4), [setv("플레이어X", add(v("플레이어X"), v("밀오른"))), setv("속도X", 0)]),
                    call("끼임 검사"),
                ],
            )
        ],
    )


def fn_crush():
    """밀려난 플레이어 자리에 이미 쌓인 블록이 있으면 = 블록 사이에 끼인 것."""
    define_function(
        "끼임 검사",
        [
            setv("끼임줄1", slot_base(floor(div(v("플레이어Y"), CELL)))),
            setv("끼임줄2", slot_base(floor(div(add(v("플레이어Y"), PLAYER_H - 0.1), CELL)))),
            setv("끼임칸1", floor(div(sub(v("플레이어X"), HALF_W - 0.1), CELL))),
            setv("끼임칸2", floor(div(add(v("플레이어X"), HALF_W - 0.1), CELL))),
            if_(
                gt(
                    add(
                        add(grid_at("끼임줄1", "끼임칸1"), grid_at("끼임줄1", "끼임칸2")),
                        add(grid_at("끼임줄2", "끼임칸1"), grid_at("끼임줄2", "끼임칸2")),
                    ),
                    0,
                ),
                [setv("상태", OVER)],
            ),
        ],
    )


def define_all_functions():
    fn_crush()
    fn_push()
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
        call("게임 변수 초기화"),
        setv("상태", TITLE),
        wait_until(jump_key()),
        forever(
            [
                setv("상태", READY),
                broadcast("게임 준비"),
                call("게임 변수 초기화"),
                setv("점프누름", 1),
                repeat(26, [call("새 줄 준비하기")]),
                setv("상태", PLAYING),
                broadcast("게임 시작"),
                # 한 바퀴 = 한 프레임 (1초에 60번)
                repeat_while(
                    eq(v("상태"), PLAYING),
                    [
                        chg("프레임", 1),
                        setv("이전플레이어Y", v("플레이어Y")),
                        call("키 입력 처리"),
                        call("좌우로 움직이기"),
                        call("점프와 중력"),
                        call("점수와 카메라"),
                        call("독극물 올리기"),
                        call("위쪽 줄 미리 만들기"),
                    ],
                ),
                play(snd_id("manager", "게임오버")),
                if_(gt(v("점수"), v("최고점수")), [setv("최고점수", v("점수"))]),
                broadcast("게임 끝"),
                wait(1),
                wait_until(not_(jump_key())),
                wait_until(jump_key()),
            ]
        ),
    ]
    return [thread(40, 40, main)]


def scripts_message_box(title_text, over_text):
    """처음과 게임 오버 때 보이고, 게임 중에는 숨는 글상자. 게임 오버 글자는 플레이어가 "으악!" 한 뒤(1초)에 나온다."""
    first = [when_run(), hide()] if title_text is None else [when_run(), write_text(title_text), show()]
    return [
        thread(40, 40, first),
        thread(40, 160, [when_message("게임 시작"), hide()]),
        thread(40, 260, [when_message("게임 끝"), wait(1), write_text(over_text), show()]),
    ]


def scripts_player():
    def face_right():
        return [setv("보는방향", 1), shape_id(pic_id("player", "오른쪽"))]

    main = [
        when_run(),
        *face_right(),
        show(),
        forever(
            [
                # 누른 방향키 쪽을 보게 모양을 바꾼다
                if_(and_(key(KEY_LEFT), eq(v("보는방향"), 1)), [setv("보는방향", -1), shape_id(pic_id("player", "왼쪽"))]),
                if_(and_(key(KEY_RIGHT), eq(v("보는방향"), -1)), face_right()),
                # 그림 맨 아래(발)가 판정 상자 바닥(플레이어Y)에 오도록 그림 높이의 절반만큼 올려서 그린다.
                # 엔트리 캔버스 한 칸(무대 0.75px) 단위로 반올림해서 그림이 흐려지지 않게 한다
                locate_xy(
                    mul(round_(mul(sub(v("플레이어X"), -X_OFF), 4 / 3)), 0.75),
                    mul(round_(mul(sub(v("플레이어Y"), add(v("카메라Y"), 135 - art.PLAYER_SIZE / 2)), 4 / 3)), 0.75),
                ),
            ]
        ),
    ]
    return [
        thread(40, 40, main),
        thread(40, 300, [when_message("게임 시작"), say("출발!", 1)]),
        thread(40, 400, [when_message("게임 끝"), say("으악!", 1)]),
        thread(40, 500, [when_message("게임 준비"), remove_dialog(), *face_right()]),
    ]


def scripts_poison():
    top_to_center = art.POISON_H / 2 - art.POISON_SURFACE  # 수면에서 그림 중심까지
    return [
        thread(
            40,
            40,
            [
                when_run(),
                locate_x(0),
                forever([locate_y(sub(v("독극물Y"), add(v("카메라Y"), 135 + top_to_center)))]),
            ],
        )
    ]


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

    def screen_y():
        return sub(add(v("바닥Y"), mul(v("블록높이"), CELL / 2)), add(v("카메라Y"), 135))

    clone = [
        when_clone(),
        setv("블록상태", 0),
        shape(add(v("블록모양"), 1)),
        locate_x(add(add(mul(v("블록열"), CELL), mul(v("블록폭"), CELL / 2)), X_OFF)),
        locate_y(screen_y()),
        show(),
        # 떨어지는 동안 (한 바퀴 = 한 프레임)
        repeat_while(
            eq(v("블록상태"), 0),
            [
                if_(
                    eq(v("상태"), PLAYING),
                    [
                        *piece_fall_blocks(),
                        # 떨어지는 블록은 단단하다: 옆에서 막히고, 위에 올라탈 수 있고, 바닥과 사이에 끼면 끝
                        *piece_push_blocks(),
                        if_(
                            lt(add(v("바닥Y"), mul(v("블록높이"), CELL)), sub(v("독극물Y"), 8)),
                            [delete_clone()],
                        ),
                    ],
                ),
                locate_y(screen_y()),
            ],
        ),
        # 내려앉은 뒤에는 카메라에 맞춰 움직이기만 한다
        setv("중심Y", sub(add(v("바닥Y"), mul(v("블록높이"), CELL / 2)), 135)),
        setv("윗면", add(add(v("바닥Y"), mul(v("블록높이"), CELL)), 24)),
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
GUIDE_TEXT = "[게임 방법]\n떨어지는 블록을 밟고\n위로 올라가세요!\n\n독극물에 빠지거나\n블록에 깔리면\n게임 오버!"
KEYS_TEXT = "[조작법]\n← → : 좌우 이동\n스페이스 : 점프\n\n공중에서 스페이스를\n한 번 더 누르면\n2단 점프!"


def build_project():
    define_all_functions()
    objects = []

    def add_obj(obj, scripts):
        obj["script"] = json.dumps(scripts, ensure_ascii=False, separators=(",", ":"))
        objects.append(obj)

    add_obj(sprite_object(OID["manager"], "게임 관리자", PIC["manager"], SND["manager"], visible=False), scripts_manager())
    add_obj(
        text_object(OID["title"], "제목 글상자", "테트로 클라임", 0, 45, 28),
        scripts_message_box("테트로 클라임", "게임 오버!"),
    )
    add_obj(
        text_object(OID["result"], "점수 글상자", "점수", 0, 12, 18, visible=False),
        scripts_message_box(None, join(join("점수 : ", v("점수")), "점")),
    )
    add_obj(
        text_object(OID["guide"], "안내 글상자", "스페이스바를 누르면 시작", 0, -20, 13),
        scripts_message_box("스페이스바를 누르면 시작", "스페이스바를 누르면 다시 시작"),
    )
    add_obj(text_object(OID["howto"], "게임 방법", GUIDE_TEXT, -166, -40, 12, width=126, height=120), [])
    add_obj(text_object(OID["keys"], "조작법", KEYS_TEXT, 166, 20, 12, width=126, height=120), [])
    add_obj(sprite_object(OID["poison"], "독극물", PIC["poison"], [], 0, -300), scripts_poison())
    # 블록이 플레이어를 밀어낸 다음에 플레이어를 그리도록, 플레이어는 블록보다 목록 아래(뒤)에 둔다
    add_obj(sprite_object(OID["piece"], "블록", PIC["piece"], [], 0, 200, visible=False), scripts_piece())
    add_obj(
        sprite_object(OID["player"], "플레이어", PIC["player"], [], 0, CELL - 135 + art.PLAYER_SIZE / 2, scale=art.PLAYER_SCALE),
        scripts_player(),
    )
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
    """블록 수를 센다. 같은 블록(id)을 두 곳에 넣으면 엔트리에서 고칠 때 꼬이므로 겹치면 멈춘다."""
    total = 0
    seen = set()

    def walk(b):
        nonlocal total
        if isinstance(b, dict) and "type" in b:
            total += 1
            if b["id"] in seen:
                raise ValueError(f"블록 id 가 겹침: {b['id']} ({b['type']})")
            seen.add(b["id"])
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
    n_blocks = count_blocks(proj)
    write_ent(proj, out, unpacked)
    print(f"{out}  ({os.path.getsize(out) / 1024:.0f} KB, 오브젝트 {len(proj['objects'])}개, 블록 {n_blocks}개)")
