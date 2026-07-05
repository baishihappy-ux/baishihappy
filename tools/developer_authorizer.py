import tkinter as tk
from tkinter import messagebox, simpledialog
from pathlib import Path
import sys
import json
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from python.auth.license_codec import generate_authorization_code


AUTHORIZE_PASSWORD = "88888888"
LOCK_DURATIONS_SECONDS = {
    3: 10 * 60,
    4: 30 * 60,
    5: 2 * 60 * 60,
    6: 24 * 60 * 60,
}


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


def require_password(root):
    state = read_lock_state()
    now = time.time()
    if state.get("locked_until", 0) > now:
        messagebox.showerror("Locked", f"Try again in {format_remaining(state['locked_until'] - now)}.")
        root.destroy()
        return False

    password = simpledialog.askstring("Developer Authorizer", "Password:", show="*", parent=root)
    if password != AUTHORIZE_PASSWORD:
        failed_attempts = int(state.get("failed_attempts", 0)) + 1
        duration = lock_duration_for(failed_attempts)
        next_state = {"failed_attempts": failed_attempts, "locked_until": now + duration if duration else 0}
        write_lock_state(next_state)
        if duration:
            messagebox.showerror("Locked", f"Invalid password. Locked for {format_remaining(duration)}.")
        else:
            messagebox.showerror("Locked", f"Invalid password. {max(0, 3 - failed_attempts)} attempt(s) before lock.")
        root.destroy()
        return False
    write_lock_state({"failed_attempts": 0, "locked_until": 0})
    return True


def build_app():
    root = tk.Tk()
    root.title("Developer Authorizer")
    root.geometry("760x520")
    root.withdraw()
    if not require_password(root):
        return root
    root.deiconify()

    fields = {}
    rows = [
        ("machine_code", "Machine Code"),
        ("valid_days", "Valid Days"),
        ("max_concurrency", "Max Concurrency / Windows"),
        ("do_token", ".do API Token"),
    ]

    for index, (key, label) in enumerate(rows):
        tk.Label(root, text=label, anchor="w").grid(row=index, column=0, sticky="w", padx=16, pady=8)
        entry = tk.Entry(root, width=80, show="*" if key == "do_token" else "")
        entry.grid(row=index, column=1, sticky="ew", padx=16, pady=8)
        fields[key] = entry

    fields["valid_days"].insert(0, "30")
    fields["max_concurrency"].insert(0, "32")

    output = tk.Text(root, height=10, wrap="word")
    output.grid(row=5, column=0, columnspan=2, sticky="nsew", padx=16, pady=12)

    def generate():
        try:
            code = generate_authorization_code(
                fields["machine_code"].get(),
                int(fields["valid_days"].get()),
                int(fields["max_concurrency"].get()),
                fields["do_token"].get(),
            )
        except Exception as exc:
            messagebox.showerror("Generate failed", str(exc))
            return
        output.delete("1.0", tk.END)
        output.insert(tk.END, code)

    def copy():
        text = output.get("1.0", tk.END).strip()
        if not text:
            return
        root.clipboard_clear()
        root.clipboard_append(text)
        messagebox.showinfo("Copied", "Authorization code copied.")

    buttons = tk.Frame(root)
    buttons.grid(row=4, column=0, columnspan=2, sticky="e", padx=16, pady=8)
    tk.Button(buttons, text="Generate Authorization Code", command=generate).pack(side="left", padx=6)
    tk.Button(buttons, text="Copy", command=copy).pack(side="left", padx=6)

    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(5, weight=1)
    return root


if __name__ == "__main__":
    build_app().mainloop()
