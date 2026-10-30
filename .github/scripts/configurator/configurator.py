import os
import sys
import json
import time
import tkinter as tk
from tkinter import messagebox, ttk
import tkinter.simpledialog as simpledialog

# ── Monkey-patch Dialog icon ───────────────────────────────────────────────────
_original_init = simpledialog.Dialog.__init__

def _custom_init(self, master, title=None):
    _original_init(self, master, title)
    try:
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.wm_iconbitmap(icon_path)
    except Exception:
        pass

simpledialog.Dialog.__init__ = _custom_init

# ── Paths ──────────────────────────────────────────────────────────────────────
def resource_path(filename):
    """Path to a bundled resource (works frozen and unfrozen)."""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, filename)

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Configurator\ → Plugins\ → OKAC\ → repo root
# e.g. C:\GitHub\OKAC-Sectorfile\OKAC\Plugins\Configurator\  →  C:\GitHub\OKAC-Sectorfile\
PACK_ROOT = os.path.abspath(os.path.join(BASE_DIR, "..", "..", ".."))

# configurator_config.json lives next to the exe in the Configurator folder
OPTIONS_PATH = os.path.join(BASE_DIR, "configurator_config.json")

# ── Helpers ────────────────────────────────────────────────────────────────────
def center_window(win):
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = (win.winfo_screenwidth() // 2) - (w // 2)
    y = (win.winfo_screenheight() // 2) - (h // 2)
    win.geometry(f"{w}x{h}+{x}+{y}")

def on_close():
    try:
        if tk._default_root:
            for w in tk._default_root.children.values():
                w.destroy()
            tk._default_root.destroy()
    except Exception:
        pass
    sys.exit()

def is_valid_cid(cid):
    return cid.isdigit() and 6 <= len(cid) <= 7

def walk_pack(top):
    """os.walk that skips dot-folders (.git, .github, .data, .archive …)."""
    for root, dirs, files in os.walk(top):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        yield root, dirs, files

# ── Config persistence ─────────────────────────────────────────────────────────
DEFAULT_FIELDS = {
    "name": "",
    "rating": "",
    "cid": "",
    "password": "",
    "initials": "",
    "cpdlc": "",
}

BASIC_FIELDS = ["name", "rating", "cid", "password", "initials", "cpdlc"]

def load_previous_options():
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
                options = json.load(f)
        except Exception:
            return {}
        # Older OKAC configurator builds saved the Hoppie code as "cpdlcc"
        if "cpdlc" not in options and "cpdlcc" in options:
            options["cpdlc"] = options.pop("cpdlcc")
        return options
    return {}

def save_options(options):
    with open(OPTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=2)

# ── GUI widgets ────────────────────────────────────────────────────────────────
def ask_string(prompt, default="", show=None):
    result = None
    dialog = tk.Toplevel()
    try:
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)
    except Exception:
        pass
    dialog.title("OKAC Sectorfile Configurator")
    dialog.resizable(False, False)
    dialog.protocol("WM_DELETE_WINDOW", on_close)

    ttk.Label(dialog, text=prompt, wraplength=360, justify="left").pack(padx=20, pady=(15, 5))
    entry_var = tk.StringVar(value=default)
    entry_kwargs = {"width": 40}
    if show:
        entry_kwargs["show"] = show
    entry = ttk.Entry(dialog, textvariable=entry_var, **entry_kwargs)
    entry.pack(padx=20, pady=5)

    def submit(event=None):
        nonlocal result
        result = entry_var.get()
        dialog.destroy()

    def cancel(event=None):
        dialog.destroy()

    bf = ttk.Frame(dialog)
    bf.pack(pady=15)
    ttk.Button(bf, text="OK", command=submit).pack(side="left", padx=5)
    ttk.Button(bf, text="Cancel", command=cancel).pack(side="left", padx=5)

    dialog.bind("<Return>", submit)
    dialog.bind("<Escape>", cancel)
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    entry.focus_set()
    dialog.wait_window()
    return result

def ask_yesno(prompt, title="OKAC Sectorfile Configurator"):
    result = None
    dialog = tk.Toplevel()
    try:
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)
    except Exception:
        pass
    dialog.title(title)
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.resizable(False, False)

    frame = ttk.Frame(dialog, padding=20)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text=prompt, wraplength=350, justify="left").pack(pady=(0, 15))

    def yes():
        nonlocal result
        result = True
        dialog.destroy()

    def no():
        nonlocal result
        result = False
        dialog.destroy()

    bf = ttk.Frame(frame)
    bf.pack()
    ttk.Button(bf, text="Yes", command=yes).pack(side="left", padx=10)
    ttk.Button(bf, text="No", command=no).pack(side="left", padx=10)

    dialog.bind("<Return>", lambda e: yes())
    dialog.bind("<Escape>", lambda e: no())
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    dialog.wait_window()
    return result

def ask_rating(current=None):
    ratings_display = [
        'Observer (OBS)',
        'Developing Controller (S1)',
        'Aerodrome Controller (S2)',
        'Terminal Controller (S3)',
        'Enroute Controller (C1)',
        'Senior Controller (C3)',
        'Instructor (I1)',
        'Senior Instructor (I3)',
        'SUP',
        'ADM'
    ]
    # Maps display index → original .prf index (skipping C2=5 and I2=8)
    prf_index_map = [0, 1, 2, 3, 4, 6, 7, 9, 10, 11]

    try:
        prf_val = int(current)
        if prf_val == 5:
            prf_val = 4
        elif prf_val == 8:
            prf_val = 7
        display_index = prf_index_map.index(prf_val) if prf_val in prf_index_map else 0
    except (ValueError, TypeError):
        display_index = 0

    selected = tk.StringVar(value=ratings_display[display_index])

    def submit():
        dialog.quit()
        dialog.destroy()

    dialog = tk.Toplevel()
    try:
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            dialog.iconbitmap(icon_path)
    except Exception:
        pass
    dialog.minsize(320, 200)
    dialog.title("OKAC Sectorfile Configurator")
    ttk.Label(dialog, text="Select your rating:").pack(pady=5)
    dropdown = ttk.Combobox(
        dialog,
        textvariable=selected,
        values=ratings_display,
        state="readonly",
        width=max(len(r) for r in ratings_display) + 2
    )
    dropdown.pack(pady=5, padx=15)
    ttk.Button(dialog, text="OK", command=submit).pack()
    dialog.protocol("WM_DELETE_WINDOW", on_close)
    dialog.transient()
    dialog.grab_set()
    dialog.attributes("-topmost", True)
    dialog.focus_force()
    center_window(dialog)
    dialog.mainloop()

    chosen_display_index = ratings_display.index(selected.get())
    return str(prf_index_map[chosen_display_index])

# ── Field prompts ──────────────────────────────────────────────────────────────
FIELD_DESCRIPTIONS = {
    "name":     "Enter your preferred name convention. (Code of Conduct A4(B))",
    "rating":   "Select your controller rating.",
    "cid":      "Enter your CID.",
    "password": "Enter your password.",
    "initials": "Enter your observer initials (e.g. AB, JS) (Code of Conduct C3).",
    "cpdlc":    "Enter your ACARS logon code."
}

def prompt_for_field(key, current):
    desc = FIELD_DESCRIPTIONS.get(key, f"Enter {key.replace('_', ' ')}")
    if key == "rating":
        return ask_rating(current)
    else:
        show = "*" if key == "password" else None
        while True:
            response = ask_string(desc, current, show=show)
            if response is None:
                sys.exit()
            if key == "cid" and not is_valid_cid(response):
                messagebox.showerror("Invalid CID", "CID must be a 6 or 7 digit number.")
                continue
            return response

# ── Config collection ──────────────────────────────────────────────────────────
def collect_basic_config():
    root = tk.Tk()
    root.title("OKAC Sectorfile Configurator")
    try:
        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            root.iconbitmap(icon_path)
    except Exception:
        pass
    root.withdraw()
    tk._default_root = root

    previous_options = load_previous_options()
    options = {}

    if previous_options:
        if ask_yesno("Do you want to load your previous options?"):
            options.update(previous_options)
            for key in BASIC_FIELDS:
                if key not in options:
                    options[key] = prompt_for_field(key, "")
        # else: start fresh

    for key in BASIC_FIELDS:
        if key not in options or not options[key]:
            options[key] = prompt_for_field(key, "")

    return options

# ── File patchers ──────────────────────────────────────────────────────────────
# Unlike ORBB, OKAC's .prf files stay where they are in the package root, so
# there is no restructure step and no \OKAC\ → \..\OKAC\ path rewrite: the
# paths inside the .prf files are already correct for that location.

def read_text_keep_encoding(file_path):
    """Read a text file as UTF-8, falling back to cp1252 (common for EuroScope
    files). Returns (text, encoding) so it can be written back the same way."""
    for encoding in ("utf-8", "cp1252"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                return f.read(), encoding
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("utf-8/cp1252", b"", 0, 1, f"could not decode {file_path}")

def patch_prf_file(file_path, name, initials, cid, rating, password):
    try:
        content, encoding = read_text_keep_encoding(file_path)
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return
    lines = content.splitlines(keepends=True)

    # Remove any existing LastSession credential lines (including server, so we always
    # write a clean canonical block)
    lines = [l for l in lines if not (
            l.startswith("LastSession\trealname") or
            l.startswith("LastSession\tcertificate") or
            l.startswith("LastSession\trating") or
            l.startswith("LastSession\tcallsign") or
            l.startswith("LastSession\tpassword") or
            l.startswith("LastSession\tserver")
    )]

    # Drop trailing blank lines so repeated runs don't keep growing the file
    while lines and not lines[-1].strip():
        lines.pop()
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"

    # Write credentials in the required order:
    # real name → rating → certificate → password → callsign → server
    new_lines = [
        f"LastSession\trealname\t{name}\n",
        f"LastSession\trating\t{rating}\n",
        f"LastSession\tcertificate\t{cid}\n",
        f"LastSession\tpassword\t{password}\n",
        f"LastSession\tcallsign\t{initials}_OBS\n",
        f"LastSession\tserver\tAUTOMATIC\n",
    ]
    lines += ["\n"] + new_lines

    try:
        with open(file_path, "w", encoding=encoding) as f:
            f.writelines(lines)
    except Exception as e:
        print(f"Failed to write {file_path}: {e}")

def patch_profiles_file(file_path, cid):
    """
    Applies all replacements defined in the [profiles_replacements] section of
    configurator_config.json to any .txt file that contains a matching string
    (e.g. Profiles.txt, Profiles - ACC.txt, Profiles - TMA.txt).

    Default replacement (always applied):
        "Submit feedback at vats.im/kwiq-fb"
        → "Submit feedback at kwiq.cc/<CID>"
    """
    try:
        content, encoding = read_text_keep_encoding(file_path)
    except Exception as e:
        print(f"Failed to read {file_path}: {e}")
        return

    # Built-in default replacement
    replacements = {
        "Submit feedback at vats.im/kwiq-fb":
            f"Submit feedback at kwiq.cc/{cid}"
    }

    # Merge in any user-defined replacements from the saved config
    saved = load_previous_options()
    user_replacements = saved.get("profiles_replacements", {})
    for find, replace in user_replacements.items():
        replacements[find] = replace.replace("{cid}", cid)

    # Only rewrite the file if something actually matched
    if not any(find in content for find in replacements):
        return

    for find, replace in replacements.items():
        content = content.replace(find, replace)

    try:
        with open(file_path, "w", encoding=encoding) as f:
            f.write(content)
    except Exception as e:
        print(f"Failed to write {file_path}: {e}")

OKAC_DIR     = os.path.join(PACK_ROOT, "OKAC")
SETTINGS_DIR = os.path.join(OKAC_DIR, "Settings")

def patch_topsky_cpdlc(cpdlc_code):
    """Write the Hoppie code to every TopSkyCPDLChoppieCode.txt in the package
    (TopSky, TopSky - Light and TopSky Aerodrome)."""
    for root, _, files in walk_pack(OKAC_DIR):
        for file in files:
            if file == "TopSkyCPDLChoppieCode.txt":
                full_path = os.path.join(root, file)
                try:
                    with open(full_path, "w", encoding="utf-8") as f:
                        f.write(cpdlc_code)
                except Exception as e:
                    print(f"Failed to write {full_path}: {e}")

# ── Main apply ─────────────────────────────────────────────────────────────────
def apply_configuration(name, initials, cid, rating, password, cpdlc):
    """Walk the package root and patch all relevant files."""
    for root, _, files in walk_pack(PACK_ROOT):
        for file in files:
            if file.endswith(".prf"):
                patch_prf_file(os.path.join(root, file), name, initials, cid, rating, password)

    if os.path.isdir(SETTINGS_DIR):
        for root, _, files in walk_pack(SETTINGS_DIR):
            for file in files:
                if file.endswith(".txt"):
                    patch_profiles_file(os.path.join(root, file), cid)
    else:
        print(f"Settings folder not found at {SETTINGS_DIR}")

    patch_topsky_cpdlc(cpdlc)

# ── Entry point ────────────────────────────────────────────────────────────────
def main():
    if not tk._default_root:
        root = tk.Tk()
        root.withdraw()
        tk._default_root = root

    lockfile = os.path.join(BASE_DIR, "configurator.lock")
    if os.path.exists(lockfile):
        messagebox.showerror("Already Running", "Configurator is already running.")
        sys.exit()

    with open(lockfile, "w") as f:
        f.write(str(os.getpid()))

    try:
        # 1. Collect options via GUI
        options = collect_basic_config()

        # 2. Patch all files (.prf files are left where they are)
        apply_configuration(
            name=options["name"],
            initials=options["initials"],
            cid=options["cid"],
            rating=options["rating"],
            password=options["password"],
            cpdlc=options["cpdlc"],
        )

        # 3. Persist options for next run
        save_options(options)

        messagebox.showinfo("Complete", "Profile configuration complete.")
        time.sleep(1.5)

    finally:
        if os.path.exists(lockfile):
            os.remove(lockfile)

if __name__ == "__main__":
    try:
        main()
    finally:
        try:
            if tk._default_root:
                for w in tk._default_root.children.values():
                    w.destroy()
                tk._default_root.destroy()
        except Exception:
            pass
        if getattr(sys, "frozen", False):
            os._exit(0)
        else:
            sys.exit(0)
