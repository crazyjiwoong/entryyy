"""엔트리(playentry.org) 블록 JSON 을 파이썬으로 만들기 위한 작은 DSL.

엔트리 작품의 코드는 "스레드(블록 묶음)의 배열"이고, 각 블록은
{id, type, params, statements, ...} 형태의 딕셔너리다.
여기 있는 함수들은 실제 엔트리 블록 정의(entryjs)의 params 순서를 그대로 따른다.
"""

import random
import string

_rng = random.Random(20260926)
_used_ids = set()


def gid(n=4):
    """엔트리식 4글자 id (숫자만으로 된 id 는 모양 번호와 헷갈리므로 제외)."""
    alphabet = string.ascii_lowercase + string.digits
    while True:
        s = "".join(_rng.choice(alphabet) for _ in range(n))
        if s not in _used_ids and not s.isdigit() and s[0].isalpha():
            _used_ids.add(s)
            return s


def B(type_, params=None, statements=None):
    return {
        "id": gid(),
        "x": 0,
        "y": 0,
        "type": type_,
        "params": params if params is not None else [],
        "statements": statements if statements is not None else [],
        "movable": None,
        "deletable": 1,
        "emphasized": False,
        "readOnly": None,
        "copyable": True,
        "assemble": True,
        "extensions": [],
    }


class Registry:
    """변수/리스트/신호 이름 -> id 매핑."""

    def __init__(self):
        self.vars = {}
        self.lists = {}
        self.messages = {}

    def var_id(self, name):
        return self.vars[name]["id"]

    def list_id(self, name):
        return self.lists[name]["id"]

    def msg_id(self, name):
        return self.messages[name]


R = Registry()


def add_variable(name, value=0, object_id=None, visible=False, x=0, y=0):
    R.vars[name] = {
        "name": name,
        "id": gid(),
        "visible": visible,
        "value": value,
        "variableType": "variable",
        "isCloud": False,
        "isRealTime": False,
        "cloudDate": False,
        "object": object_id,
        "x": x,
        "y": y,
    }


def add_list(name, array, object_id=None, visible=False, x=0, y=0):
    R.lists[name] = {
        "name": name,
        "id": gid(),
        "visible": visible,
        "value": 0,
        "variableType": "list",
        "isCloud": False,
        "isRealTime": False,
        "cloudDate": False,
        "object": object_id,
        "x": x,
        "y": y,
        "width": 100,
        "height": 120,
        "array": [{"data": a} for a in array],
    }


def add_message(name):
    R.messages[name] = gid()


# ---------------------------------------------------------------- 값 블록
def _val(x):
    if isinstance(x, dict):
        return x
    if isinstance(x, bool):
        raise TypeError("bool 은 값 블록이 아님")
    if isinstance(x, (int, float)):
        return num(x)
    if isinstance(x, str):
        return txt(x)
    raise TypeError(repr(x))


def num(x):
    if isinstance(x, float) and x.is_integer():
        x = int(x)
    return B("number", [x])


def txt(s):
    return B("text", [s])


def v(name):
    """변수 값 (get_variable)."""
    return B("get_variable", [R.var_id(name), None])


def calc(a, op, b):
    return B("calc_basic", [_val(a), op, _val(b)])


def add(a, b):
    return calc(a, "PLUS", b)


def sub(a, b):
    return calc(a, "MINUS", b)


def mul(a, b):
    return calc(a, "MULTI", b)


def div(a, b):
    return calc(a, "DIVIDE", b)


def op(a, name):
    """calc_operation: floor, ceil, round, abs, root ..."""
    return B("calc_operation", [None, _val(a), None, name])


def floor(a):
    return op(a, "floor")


def round_(a):
    return op(a, "round")


def abs_(a):
    return op(a, "abs")


def mod(a, b):
    return B("quotient_and_mod", [None, _val(a), None, _val(b), None, "MOD"])


def rand(a, b):
    return B("calc_rand", [None, _val(a), None, _val(b), None])


def join(a, b):
    return B("combine_something", [None, _val(a), None, _val(b), None])


def item(list_name, index):
    return B("value_of_index_from_list", [None, R.list_id(list_name), None, _val(index), None])


def list_len(list_name):
    return B("length_of_list", [None, R.list_id(list_name), None])


def sin_(a):
    """sin (각도는 도 단위)."""
    return op(a, "sin")


def self_value(kind):
    """자신의 x좌표값 / y좌표값 / 크기 / 방향 ... (coordinate_object)."""
    return B("coordinate_object", [None, "self", None, kind])


def picture(pid):
    return B("get_pictures", [pid])


def sound_ref(sid):
    return B("get_sounds", [sid])


# ---------------------------------------------------------------- 판단 블록
def cmp(a, operator, b):
    return B("boolean_basic_operator", [_val(a), operator, _val(b)])


def eq(a, b):
    return cmp(a, "EQUAL", b)


def ne(a, b):
    return cmp(a, "NOT_EQUAL", b)


def gt(a, b):
    return cmp(a, "GREATER", b)


def lt(a, b):
    return cmp(a, "LESS", b)


def ge(a, b):
    return cmp(a, "GREATER_OR_EQUAL", b)


def le(a, b):
    return cmp(a, "LESS_OR_EQUAL", b)


def and_(a, b):
    return B("boolean_and_or", [a, "AND", b])


def or_(a, b):
    return B("boolean_and_or", [a, "OR", b])


def not_(a):
    return B("boolean_not", [None, a, None])


def key(code):
    return B("is_press_some_key", [str(code), None])


# ---------------------------------------------------------------- 명령 블록
def setv(name, value):
    return B("set_variable", [R.var_id(name), _val(value), None])


def chg(name, value):
    return B("change_variable", [R.var_id(name), _val(value), None])


def set_item(list_name, index, value):
    return B("change_value_list_index", [R.list_id(list_name), _val(index), _val(value), None])


def push_item(list_name, value):
    """리스트 맨 뒤에 항목 추가."""
    return B("add_value_to_list", [_val(value), R.list_id(list_name), None])


def remove_item(list_name, index):
    return B("remove_value_from_list", [_val(index), R.list_id(list_name), None])


def if_(cond, body):
    return B("_if", [cond, None], [body])


def if_else(cond, body, else_body):
    return B("if_else", [cond, None, None], [body, else_body])


def forever(body):
    return B("repeat_inf", [None], [body])


def repeat(times, body):
    return B("repeat_basic", [_val(times), None], [body])


def repeat_while(cond, body):
    """조건이 참인 동안 반복 (한 바퀴 = 한 프레임)."""
    return B("repeat_while_true", [cond, "while", None], [body])


def wait_until(cond):
    return B("wait_until_true", [cond, None])


def wait(seconds):
    return B("wait_second", [_val(seconds), None])


def broadcast(name):
    return B("message_cast", [R.msg_id(name), None])


def broadcast_wait(name):
    return B("message_cast_wait", [R.msg_id(name), None])


def create_clone_self():
    return B("create_clone", ["self", None])


def delete_clone():
    return B("delete_clone", [None])


def locate_xy(x, y):
    return B("locate_xy", [_val(x), _val(y), None])


def locate_x(x):
    return B("locate_x", [_val(x), None])


def locate_y(y):
    return B("locate_y", [_val(y), None])


def show():
    return B("show", [None])


def hide():
    return B("hide", [None])


def shape(value):
    """모양 바꾸기: 숫자(모양 번호) 또는 모양 이름 블록."""
    return B("change_to_some_shape", [_val(value), None])


def shape_id(pid):
    return B("change_to_some_shape", [picture(pid), None])


def next_shape():
    return B("change_to_next_shape", ["next", None])


def set_size(value):
    return B("set_scale_size", [_val(value), None])


def change_size(value):
    return B("change_scale_size", [_val(value), None])


def rotate_to(value):
    """방향을 ~(으)로 정하기 (회전 방식이 '자유 회전'일 때 그림이 돌아간다)."""
    return B("rotate_absolute", [_val(value), None])


def set_effect(effect, value):
    return B("change_effect_amount", [effect, _val(value), None])


def add_effect(effect, value):
    return B("add_effect_amount", [effect, _val(value), None])


def clear_effects():
    return B("erase_all_effects", [None])


def to_front():
    return B("change_object_index", ["FRONT", None])


def write_text(value):
    return B("text_write", [_val(value), None])


def play(sound_id):
    return B("sound_something_with_block", [sound_ref(sound_id), None])


def say(value, seconds=None):
    """~을(를) 말하기. seconds 를 주면 그 시간 동안 말한 뒤 다음 블록으로 넘어간다."""
    if seconds is None:
        return B("dialog", [_val(value), "speak", None])
    return B("dialog_time", [_val(value), _val(seconds), "speak", None])


def remove_dialog():
    return B("remove_dialog", [None])


# ---------------------------------------------------------------- 이벤트 블록
def when_run():
    return B("when_run_button_click", [None])


def when_clone():
    return B("when_clone_start", [None])


def when_message(name):
    return B("when_message_cast", [None, R.msg_id(name)])


def thread(x, y, blocks):
    """스레드 = 블록 목록. 첫 블록에 작업실 좌표를 준다."""
    blocks = list(blocks)
    blocks[0]["x"] = x
    blocks[0]["y"] = y
    return blocks


# ---------------------------------------------------------------- 함수
FUNCTIONS = []  # 작품의 functions 배열
_FN_IDS = {}


def define_function(name, body):
    """이름표만 있는 (매개변수 없는) 일반 함수를 만든다. 반복문이 없는 함수는 한 프레임 안에 끝난다."""
    import json

    fid = gid()
    head = B("function_create", [B("function_field_label", [name, None]), None], [body])
    head["x"], head["y"] = 40, 40
    FUNCTIONS.append(
        {
            "id": fid,
            "type": "normal",
            "localVariables": [],
            "useLocalVariables": False,
            "content": json.dumps([[head]], ensure_ascii=False, separators=(",", ":")),
        }
    )
    _FN_IDS[name] = fid
    return fid


def call(name):
    return B(f"func_{_FN_IDS[name]}", [None])
