import ctypes
import json
import sys
import time
from ctypes import wintypes
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python.auth.license_codec import generate_authorization_code


AUTHORIZE_PASSWORD = "88888888"
LOCK_DURATIONS_SECONDS = {
    3: 10 * 60,
    4: 30 * 60,
    5: 2 * 60 * 60,
    6: 24 * 60 * 60,
}

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)

WS_OVERLAPPEDWINDOW = 0x00CF0000
WS_EX_APPWINDOW = 0x00040000
WS_CAPTION = 0x00C00000
WS_SYSMENU = 0x00080000
WS_MINIMIZEBOX = 0x00020000
WS_VISIBLE = 0x10000000
WS_CHILD = 0x40000000
WS_TABSTOP = 0x00010000
WS_BORDER = 0x00800000
WS_VSCROLL = 0x00200000
ES_LEFT = 0x0000
ES_PASSWORD = 0x0020
ES_MULTILINE = 0x0004
ES_AUTOVSCROLL = 0x0040
ES_READONLY = 0x0800
BS_PUSHBUTTON = 0x00000000
CW_USEDEFAULT = -2147483648
CS_HREDRAW = 0x0002
CS_VREDRAW = 0x0001
WM_DESTROY = 0x0002
WM_ERASEBKGND = 0x0014
WM_COMMAND = 0x0111
WM_SETFONT = 0x0030
WM_CTLCOLORBTN = 0x0135
WM_CTLCOLOREDIT = 0x0133
WM_CTLCOLORSTATIC = 0x0138
EM_SETSEL = 0x00B1
EM_REPLACESEL = 0x00C2
MB_OK = 0x00000000
MB_ICONERROR = 0x00000010
MB_ICONINFORMATION = 0x00000040
TRANSPARENT = 1
OPAQUE = 2
RDW_INVALIDATE = 0x0001
RDW_ERASE = 0x0004
RDW_ALLCHILDREN = 0x0080
RDW_UPDATENOW = 0x0100
COLOR_BG = 0x00100D09
COLOR_PANEL = 0x00201810
COLOR_GOLD = 0x0037AFD4
COLOR_TEXT = 0x00F4F0E8

ID_PASSWORD = 1001
ID_UNLOCK = 1002
ID_EXIT = 1003
ID_MACHINE = 2001
ID_DAYS = 2002
ID_WINDOWS = 2003
ID_TOKEN = 2004
ID_GENERATE = 2005
ID_COPY = 2006
ID_OUTPUT = 2007

controls = {}
child_windows = []
last_code = ""
transitioning_window = False
window_class_registered = False
bg_brush = gdi32.CreateSolidBrush(COLOR_BG)
panel_brush = gdi32.CreateSolidBrush(COLOR_PANEL)

user32.CreateWindowExW.restype = wintypes.HWND
user32.CreateWindowExW.argtypes = [
    wintypes.DWORD,
    wintypes.LPCWSTR,
    wintypes.LPCWSTR,
    wintypes.DWORD,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    ctypes.c_int,
    wintypes.HWND,
    wintypes.HMENU,
    wintypes.HINSTANCE,
    wintypes.LPVOID,
]
LRESULT = ctypes.c_ssize_t
user32.DefWindowProcW.restype = LRESULT
user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.RegisterClassW.restype = wintypes.ATOM
user32.RegisterClassW.argtypes = [ctypes.c_void_p]
user32.LoadCursorW.restype = wintypes.HANDLE
user32.LoadCursorW.argtypes = [wintypes.HINSTANCE, ctypes.c_void_p]
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UpdateWindow.argtypes = [wintypes.HWND]
user32.InvalidateRect.argtypes = [wintypes.HWND, ctypes.c_void_p, wintypes.BOOL]
user32.RedrawWindow.argtypes = [wintypes.HWND, ctypes.c_void_p, ctypes.c_void_p, wintypes.UINT]
user32.OpenClipboard.restype = wintypes.BOOL
user32.OpenClipboard.argtypes = [wintypes.HWND]
user32.EmptyClipboard.restype = wintypes.BOOL
user32.SetClipboardData.restype = wintypes.HANDLE
user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
user32.CloseClipboard.restype = wintypes.BOOL
kernel32.GlobalAlloc.restype = wintypes.HANDLE
kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
kernel32.GlobalLock.restype = ctypes.c_void_p
kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
kernel32.GlobalUnlock.restype = wintypes.BOOL
kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]


def lock_state_path():
    root = Path.home() / ".workspace_authorizer"
    root.mkdir(parents=True, exist_ok=True)
    return root / "authorizer-lock.json"


def read_lock_state():
    try:
        return json.loads(lock_state_path().read_text(encoding="utf-8"))
    except Exception:
        return {"failed_attempts": 0, "locked_until": 0}


def write_lock_state(state):
    lock_state_path().write_text(json.dumps(state, indent=2), encoding="utf-8")


def lock_duration_for(attempts):
    if attempts >= 6:
        return LOCK_DURATIONS_SECONDS[6]
    return LOCK_DURATIONS_SECONDS.get(attempts, 0)


def format_remaining(seconds):
    seconds = max(1, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def message(hwnd, text, title="Developer Authorizer", error=False):
    flags = MB_OK | (MB_ICONERROR if error else MB_ICONINFORMATION)
    user32.MessageBoxW(hwnd, text, title, flags)


def get_text(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value


def set_text(hwnd, text):
    user32.SetWindowTextW(hwnd, text)


def copy_to_clipboard(hwnd, text):
    if not text:
        return
    if not user32.OpenClipboard(hwnd):
        message(hwnd, "Clipboard is busy. Try again.", "Copy failed", True)
        return
    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16le") + b"\x00\x00"
        handle = kernel32.GlobalAlloc(0x0042, len(data))
        ptr = kernel32.GlobalLock(handle)
        if not ptr:
            message(hwnd, "Unable to allocate clipboard memory.", "Copy failed", True)
            return
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(handle)
        if not user32.SetClipboardData(13, handle):
            message(hwnd, "Unable to write clipboard data.", "Copy failed", True)
            return
    finally:
        user32.CloseClipboard()


def loword(value):
    return value & 0xFFFF


def create_control(parent, class_name, text, style, x, y, width, height, control_id=0):
    hwnd = user32.CreateWindowExW(
        0,
        class_name,
        text,
        WS_CHILD | WS_VISIBLE | style,
        x,
        y,
        width,
        height,
        parent,
        control_id,
        None,
        None,
    )
    child_windows.append(hwnd)
    return hwnd


def clear_controls():
    controls.clear()
    while child_windows:
        hwnd = child_windows.pop()
        if hwnd:
            user32.ShowWindow(hwnd, 0)
            user32.DestroyWindow(hwnd)


def refresh_window(hwnd):
    user32.RedrawWindow(hwnd, None, None, RDW_INVALIDATE | RDW_ERASE | RDW_ALLCHILDREN | RDW_UPDATENOW)
    user32.UpdateWindow(hwnd)


def render_login(hwnd):
    clear_controls()
    refresh_window(hwnd)
    create_control(hwnd, "STATIC", "Developer Authorizer", 0, 34, 28, 300, 24)
    create_control(hwnd, "STATIC", "Password", 0, 64, 96, 120, 22)
    controls["password"] = create_control(
        hwnd, "EDIT", "", WS_BORDER | WS_TABSTOP | ES_PASSWORD, 185, 92, 280, 30, ID_PASSWORD
    )
    create_control(hwnd, "BUTTON", "Unlock", WS_TABSTOP | BS_PUSHBUTTON, 485, 91, 100, 32, ID_UNLOCK)
    create_control(
        hwnd,
        "STATIC",
        "Wrong password locks: 3rd=10m, 4th=30m, 5th=2h, 6th+=24h.",
        0,
        64,
        148,
        560,
        22,
    )


def render_authorizer(hwnd):
    clear_controls()
    refresh_window(hwnd)
    create_control(hwnd, "STATIC", "Developer Authorizer", 0, 34, 24, 300, 24)
    rows = [
        ("machine", "Machine Code", ID_MACHINE, ""),
        ("days", "Valid Days", ID_DAYS, "30"),
        ("windows", "Max Windows", ID_WINDOWS, "32"),
        ("token", "Provider Token", ID_TOKEN, ""),
    ]
    y = 74
    for key, label, control_id, value in rows:
        create_control(hwnd, "STATIC", label, 0, 64, y + 5, 150, 22)
        controls[key] = create_control(hwnd, "EDIT", value, WS_BORDER | WS_TABSTOP | ES_LEFT, 210, y, 430, 30, control_id)
        y += 46
    create_control(hwnd, "BUTTON", "Generate", WS_TABSTOP | BS_PUSHBUTTON, 210, y, 120, 32, ID_GENERATE)
    create_control(hwnd, "BUTTON", "Copy", WS_TABSTOP | BS_PUSHBUTTON, 344, y, 90, 32, ID_COPY)
    y += 50
    create_control(hwnd, "STATIC", "Authorization Code", 0, 64, y, 180, 22)
    controls["output"] = create_control(
        hwnd,
        "EDIT",
        "",
        WS_BORDER | WS_VSCROLL | ES_MULTILINE | ES_AUTOVSCROLL | ES_READONLY,
        64,
        y + 28,
        576,
        150,
        ID_OUTPUT,
    )


def handle_unlock(hwnd):
    global transitioning_window
    state = read_lock_state()
    now = time.time()
    if state.get("locked_until", 0) > now:
        message(hwnd, f"Try again in {format_remaining(state['locked_until'] - now)}.", "Locked", True)
        return
    if get_text(controls["password"]) != AUTHORIZE_PASSWORD:
        failed_attempts = int(state.get("failed_attempts", 0)) + 1
        duration = lock_duration_for(failed_attempts)
        write_lock_state({"failed_attempts": failed_attempts, "locked_until": now + duration if duration else 0})
        if duration:
            message(hwnd, f"Invalid password. Locked for {format_remaining(duration)}.", "Locked", True)
        else:
            message(hwnd, f"Invalid password. {max(0, 3 - failed_attempts)} attempt(s) before lock.", "Locked", True)
        return
    write_lock_state({"failed_attempts": 0, "locked_until": 0})
    transitioning_window = True
    user32.DestroyWindow(hwnd)
    transitioning_window = False
    create_window("authorizer")


def handle_generate(hwnd):
    global last_code
    try:
        last_code = generate_authorization_code(
            get_text(controls["machine"]),
            int(get_text(controls["days"])),
            int(get_text(controls["windows"])),
            get_text(controls["token"]),
        )
    except Exception as exc:
        message(hwnd, str(exc), "Generate failed", True)
        return
    set_text(controls["output"], last_code)


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)


class WNDCLASS(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HANDLE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HANDLE),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


@WNDPROC
def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_ERASEBKGND:
        rect = wintypes.RECT()
        user32.GetClientRect(hwnd, ctypes.byref(rect))
        user32.FillRect(wparam, ctypes.byref(rect), bg_brush)
        return 1
    if msg == WM_COMMAND:
        command_id = loword(wparam)
        if command_id == ID_UNLOCK:
            handle_unlock(hwnd)
        elif command_id == ID_EXIT:
            user32.DestroyWindow(hwnd)
        elif command_id == ID_GENERATE:
            handle_generate(hwnd)
        elif command_id == ID_COPY:
            output = controls.get("output")
            copy_to_clipboard(hwnd, get_text(output) if output else last_code)
            message(hwnd, "Authorization code copied.")
        return 0
    if msg == WM_CTLCOLORSTATIC:
        gdi32.SetTextColor(wparam, COLOR_GOLD)
        gdi32.SetBkMode(wparam, OPAQUE)
        gdi32.SetBkColor(wparam, COLOR_BG)
        return bg_brush
    if msg == WM_CTLCOLOREDIT:
        gdi32.SetTextColor(wparam, COLOR_TEXT)
        gdi32.SetBkColor(wparam, COLOR_PANEL)
        return panel_brush
    if msg == WM_CTLCOLORBTN:
        gdi32.SetTextColor(wparam, COLOR_GOLD)
        gdi32.SetBkColor(wparam, COLOR_BG)
        return bg_brush
    if msg == WM_DESTROY:
        if not transitioning_window:
            user32.PostQuitMessage(0)
        return 0
    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)


def register_window_class(instance):
    global window_class_registered
    if window_class_registered:
        return
    class_name = "DeveloperAuthorizerWindow"
    wc = WNDCLASS()
    wc.style = CS_HREDRAW | CS_VREDRAW
    wc.lpfnWndProc = wnd_proc
    wc.hInstance = instance
    wc.lpszClassName = class_name
    wc.hCursor = user32.LoadCursorW(None, ctypes.c_void_p(32512))
    wc.hbrBackground = bg_brush
    user32.RegisterClassW(ctypes.byref(wc))
    window_class_registered = True


def create_window(view):
    instance = kernel32.GetModuleHandleW(None)
    class_name = "DeveloperAuthorizerWindow"
    register_window_class(instance)
    hwnd = user32.CreateWindowExW(
        WS_EX_APPWINDOW,
        class_name,
        "Developer Authorizer",
        WS_OVERLAPPEDWINDOW | WS_VISIBLE,
        CW_USEDEFAULT,
        CW_USEDEFAULT,
        740,
        500,
        None,
        None,
        instance,
        None,
    )
    if not hwnd:
        error_code = ctypes.get_last_error()
        user32.MessageBoxW(None, f"CreateWindowEx failed: {error_code}", "Developer Authorizer", MB_OK | MB_ICONERROR)
        return None
    if view == "authorizer":
        render_authorizer(hwnd)
    else:
        render_login(hwnd)
    user32.ShowWindow(hwnd, 1)
    user32.UpdateWindow(hwnd)
    return hwnd


def main():
    create_window("login")
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))


if __name__ == "__main__":
    main()


