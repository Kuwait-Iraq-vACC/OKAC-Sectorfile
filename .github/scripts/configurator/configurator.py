import os, sys, json, time
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageTk

RED      = "#C8102E"
RED_HOV  = "#A50D26"
BLACK    = "#0D0D0D"
SURFACE  = "#161616"
INPUT_BG = "#1F1F1F"
INPUT_BOR= "#2E2E2E"
WHITE    = "#F0F0F0"
MUTED    = "#7A7A7A"
SUCCESS  = "#4CAF50"
WARN     = "#E0A500"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def resource_path(filename):
    if getattr(sys, "frozen", False):
        bases = [sys._MEIPASS, os.path.dirname(sys.executable)]
    else:
        bases = [os.path.dirname(os.path.abspath(__file__))]
    for base in bases:
        p = os.path.join(base, filename)
        if os.path.exists(p):
            return p
    return os.path.join(bases[0], filename)

if getattr(sys, "frozen", False):
    _EXE_DIR = os.path.dirname(sys.executable)
else:
    _EXE_DIR = os.path.dirname(os.path.abspath(__file__))

OPTIONS_PATH = os.path.join(_EXE_DIR, "configurator_config.json")

def _find_okac_root():
    candidate = _EXE_DIR
    for _ in range(12):
        if os.path.basename(candidate).upper() == "OKAC":
            parent = os.path.dirname(candidate)
            if os.path.basename(parent).upper() == "OKAC":
                return parent
            return candidate
        okac = os.path.join(candidate, "OKAC")
        if os.path.isdir(okac):
            return okac
        candidate = os.path.dirname(candidate)
    return os.path.abspath(os.path.join(_EXE_DIR, "..", ".."))

OKAC_ROOT = _find_okac_root()

def load_previous_options():
    try:
        with open(OPTIONS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_options(options):
    with open(OPTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(options, f, indent=4)

def validate_cid(cid):
    if not cid:
        return "CID is required."
    if not cid.isdigit():
        return "CID must contain digits only."
    if len(cid) < 6:
        return f"CID is too short ({len(cid)} digits) - must be 6 or 7 digits."
    if len(cid) > 7:
        return f"CID is too long ({len(cid)} digits) - must be 6 or 7 digits."
    return None

# Ratings stored as EuroScope/VATSIM numeric codes
RATINGS = [
    ("Observer (BS)",             "0"),
    ("Developing Controller (S1)", "1"),
    ("Aerodrome Controller (S2)",  "2"),
    ("Terminal Controller (S3)",   "3"),
    ("Enroute Controller (C1)",    "4"),
    ("Senior Controller (C3)",     "6"),
    ("Instructor (I1)",            "7"),
    ("Senior Instructor (I3)",     "9"),
    ("Supervisor (SUP)",           "10"),
    ("Administrator (ADM)",        "11"),
]
RATING_DISPLAY = [r[0] for r in RATINGS]
RATING_CODE    = {r[0]: r[1] for r in RATINGS}
RATING_DEFAULT = "0"

STEPS = [
    {"key": "name",     "title": "Full name",         "hint": "Enter your preferred name convention.\n(VATSIM Code of Conduct A4(B))",         "placeholder": "e.g. John Smith",  "type": "entry"},
    {"key": "initials", "title": "Callsign initials", "hint": "Enter your callsign initials, e.g. AB or JS.\n(VATSIM Code of Conduct A4(B))",  "placeholder": "e.g. JS",          "type": "entry"},
    {"key": "rating",   "title": "Controller rating", "hint": "Select your current VATSIM controller rating.",                                   "type": "combo"},
    {"key": "cid",      "title": "VATSIM CID",        "hint": "Enter your CID - must be 6 or 7 digits.",                                        "placeholder": "e.g. 1234567",     "type": "entry"},
    {"key": "password", "title": "Network password",  "hint": "Enter your VATSIM network password.",                                            "placeholder": "........",         "type": "password"},
    {"key": "cpdlcc",   "title": "ACARS logon code",  "hint": "Enter your Hoppie ACARS logon code for CPDLC.\nLeave blank if not required.",    "placeholder": "e.g. ABCDE12345",  "type": "entry"},
]

# Business logic

def patch_prf_file(file_path, options):
    with open(file_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    cid         = options.get("cid", "")
    rating_code = options.get("rating", RATING_DEFAULT)
    name        = options.get("name", "")
    password    = options.get("password", "")
    callsign    = ""

    found = {k: False for k in ("realname", "certificate", "rating", "callsign", "password", "server")}
    new = []
    for line in lines:
        if line.startswith("LastSession\trealname\t"):
            line = f"LastSession\trealname\t{name}\n"; found["realname"] = True
        elif line.startswith("LastSession\tcertificate\t"):
            line = f"LastSession\tcertificate\t{cid}\n"; found["certificate"] = True
        elif line.startswith("LastSession\trating\t"):
            line = f"LastSession\trating\t{rating_code}\n"; found["rating"] = True
        elif line.startswith("LastSession\tcallsign\t"):
            line = f"LastSession\tcallsign\t{callsign}\n"; found["callsign"] = True
        elif line.startswith("LastSession\tpassword\t"):
            line = f"LastSession\tpassword\t{password}\n"; found["password"] = True
        elif line.startswith("LastSession\tserver\t"):
            line = "LastSession\tserver\tAUTOMATIC\n"; found["server"] = True
            new.append(line)
            if not found["realname"]:    new.append(f"LastSession\trealname\t{name}\n")
            if not found["certificate"]: new.append(f"LastSession\tcertificate\t{cid}\n")
            if not found["rating"]:      new.append(f"LastSession\trating\t{rating_code}\n")
            if not found["callsign"]:    new.append(f"LastSession\tcallsign\t{callsign}\n")
            if not found["password"]:    new.append(f"LastSession\tpassword\t{password}\n")
            continue
        new.append(line)

    if not found["server"]:
        new += [
            "LastSession\tserver\tAUTOMATIC\n",
            f"LastSession\trealname\t{name}\n",
            f"LastSession\tcertificate\t{cid}\n",
            f"LastSession\trating\t{rating_code}\n",
            f"LastSession\tcallsign\t{callsign}\n",
            f"LastSession\tpassword\t{password}\n",
        ]

    with open(file_path, "w", encoding="utf-8", errors="replace") as f:
        f.writelines(new)

def patch_topsky_cpdlc(options):
    """Write Hoppie code to ALL TopSkyCPDLChoppieCode.txt files found under OKAC root.
    Covers both Plugins\\TopSky and Plugins\\TopSky - Light automatically."""
    code = options.get("cpdlcc", "").strip()
    if not code:
        return 0
    updated = 0
    for root, dirs, files in os.walk(OKAC_ROOT):
        for f in files:
            if f == "TopSkyCPDLChoppieCode.txt":
                try:
                    with open(os.path.join(root, f), "w", encoding="utf-8") as fh:
                        fh.write(code)
                    updated += 1
                except Exception:
                    pass
    return updated

def apply_configuration(options):
    if not os.path.isdir(OKAC_ROOT):
        raise ValueError(
            f"Could not find the OKAC folder.\n"
            f"Looked at: {OKAC_ROOT}\n"
            f"Exe directory: {_EXE_DIR}\n\n"
            f"Place Configurator.exe inside or next to the OKAC folder."
        )
    patched_files = []
    errors = []
    for root, dirs, files in os.walk(OKAC_ROOT):
        for file in files:
            fp = os.path.join(root, file)
            if file.endswith(".prf"):
                try:
                    patch_prf_file(fp, options)
                    patched_files.append(os.path.basename(fp))
                except Exception as e:
                    errors.append((os.path.basename(fp), str(e)))
    cpdlc_updated = patch_topsky_cpdlc(options)
    return patched_files, cpdlc_updated, errors

# UI helpers

def _set_icon(window):
    try:
        ico = resource_path("logo.ico")
        def _apply():
            try:
                window.wm_iconbitmap(ico)
            except Exception:
                pass
        window.after(250, _apply)
    except Exception:
        pass

# Main window

class Configurator(ctk.CTk):
    W     = 460
    H     = 370
    H_MAX = 600

    def __init__(self):
        super().__init__()
        self.title("Kuwait FIR - OKAC Configurator")
        self.geometry(f"{self.W}x{self.H}")
        self.resizable(False, False)
        self.configure(fg_color=BLACK)
        _set_icon(self)

        self._banner_img = None
        try:
            img    = Image.open(resource_path("banner.png"))
            aspect = img.width / img.height
            new_w  = int(68 * aspect)
            img    = img.resize((new_w, 68), Image.LANCZOS)
            self._banner_img = ImageTk.PhotoImage(img)
        except Exception:
            pass

        self._step    = 0
        self._answers = {}
        self._build_shell()
        self._center()
        self.protocol("WM_DELETE_WINDOW", lambda: (self.destroy(), sys.exit()))

        prev = load_previous_options()
        if prev:
            self.after(120, lambda: self._ask_load_prev(prev))
        else:
            self.after(120, self._show_step)

    def _build_shell(self):
        HDR_H = 76 if self._banner_img else 56
        self._header = ctk.CTkFrame(self, fg_color="#000000", height=HDR_H, corner_radius=0)
        self._header.pack(fill="x")
        self._header.pack_propagate(False)

        if self._banner_img:
            tk.Label(self._header, image=self._banner_img, bg="#000000", bd=0, highlightthickness=0).place(x=16, rely=0.5, anchor="w")
        else:
            ctk.CTkLabel(self._header, text="Kuwait FIR - OKAC Configurator", font=("Segoe UI", 14, "bold"), text_color=WHITE, anchor="w").place(x=20, y=18)

        self._step_var = tk.StringVar(value="")
        ctk.CTkLabel(self._header, textvariable=self._step_var, font=("Segoe UI", 10), text_color="#AAAAAA", anchor="e").place(relx=1.0, x=-16, rely=0.5, anchor="e")

        self._prog_canvas = tk.Canvas(self, height=3, bg=SURFACE, highlightthickness=0, bd=0)
        self._prog_canvas.pack(fill="x")

        self._body = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        self._body.pack(fill="both", expand=True)

        self._q_var    = tk.StringVar()
        self._q_lbl    = ctk.CTkLabel(self._body, textvariable=self._q_var, font=("Segoe UI", 20, "bold"), text_color=WHITE, anchor="w", wraplength=400)
        self._hint_var = tk.StringVar()
        self._hint_lbl = ctk.CTkLabel(self._body, textvariable=self._hint_var, font=("Segoe UI", 10), text_color=MUTED, anchor="w", justify="left", wraplength=400)
        self._entry_var = ctk.StringVar()
        self._entry = ctk.CTkEntry(self._body, textvariable=self._entry_var, font=("Segoe UI", 12), height=40, width=404, fg_color=INPUT_BG, border_color=INPUT_BOR, border_width=1, text_color=WHITE, placeholder_text_color="#555555")
        self._combo = ctk.CTkComboBox(self._body, values=RATING_DISPLAY, font=("Segoe UI", 12), height=40, width=404, fg_color=INPUT_BG, border_color=INPUT_BOR, border_width=1, button_color=RED, button_hover_color=RED_HOV, dropdown_fg_color="#1A1A1A", text_color=WHITE, state="readonly")
        self._err_var  = tk.StringVar()
        self._err_lbl  = ctk.CTkLabel(self._body, textvariable=self._err_var, font=("Segoe UI", 10), text_color="#FF6B6B", anchor="w")
        self._footer   = ctk.CTkFrame(self._body, fg_color="transparent")
        self._back_btn = ctk.CTkButton(self._footer, text="< Back", font=("Segoe UI", 11), width=90, height=34, fg_color="transparent", hover_color="#1F1F1F", border_color=INPUT_BOR, border_width=1, text_color=MUTED, command=self._go_back)
        self._back_btn.pack(side="left", padx=(0, 10))
        self._next_btn = ctk.CTkButton(self._footer, text="Next >", font=("Segoe UI", 11, "bold"), width=110, height=34, fg_color=RED, hover_color=RED_HOV, text_color=WHITE, command=self._go_next)
        self._next_btn.pack(side="left")
        self.bind("<Return>", lambda e: self._go_next())

    def _show_step(self):
        for w in self._body.winfo_children():
            if w not in (self._q_lbl, self._hint_lbl, self._entry, self._combo, self._err_lbl, self._footer):
                w.destroy()
        step = STEPS[self._step]
        n    = len(STEPS)
        self._step_var.set(f"Step {self._step + 1} of {n}")
        self._q_var.set(step["title"])
        self._hint_var.set(step["hint"])
        self._err_var.set("")
        self._hint_lbl.configure(text_color=MUTED)
        self.update_idletasks()
        cw = self._prog_canvas.winfo_width() or self.W
        pct = (self._step + 1) / n
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(0, 0, cw, 3, fill=SURFACE, outline="")
        self._prog_canvas.create_rectangle(0, 0, int(cw * pct), 3, fill=RED, outline="")
        self._q_lbl.place(x=28, y=24)
        self._hint_lbl.place(x=28, y=74)
        self._err_lbl.place(x=28, y=178)
        self._footer.place(relx=1.0, rely=1.0, x=-28, y=-22, anchor="se")
        if not self._back_btn.winfo_ismapped():
            self._back_btn.pack(side="left", padx=(0, 10))
        self._back_btn.configure(
            state="disabled" if self._step == 0 else "normal",
            text_color="#333333" if self._step == 0 else MUTED,
            border_color="#222222" if self._step == 0 else INPUT_BOR,
        )
        self._next_btn.configure(text="Apply >" if self._step == n - 1 else "Next >", fg_color=RED, hover_color=RED_HOV, command=self._go_next)
        self._set_height(self.H)
        self._entry.place_forget()
        self._combo.place_forget()
        if step["type"] == "combo":
            self._combo.place(x=28, y=118)
            saved_code = self._answers.get("rating", RATING_DEFAULT)
            for display, code in RATING_CODE.items():
                if code == saved_code:
                    self._combo.set(display)
                    break
            else:
                self._combo.set(RATING_DISPLAY[0])
            self._combo.focus_set()
        else:
            self._entry.configure(show="*" if step["type"] == "password" else "", placeholder_text=step.get("placeholder", ""))
            self._entry_var.set(self._answers.get(step["key"], ""))
            self._entry.place(x=28, y=118)
            self._entry.focus_set()
            self._entry.icursor("end")

    def _go_next(self):
        step = STEPS[self._step]
        self._err_var.set("")
        if step["type"] == "combo":
            self._answers["rating"] = RATING_CODE.get(self._combo.get(), RATING_DEFAULT)
        else:
            val = self._entry_var.get().strip()
            if step["key"] == "name" and not val:
                self._err_var.set("Name is required."); return
            if step["key"] == "initials" and not val:
                self._err_var.set("Initials are required."); return
            if step["key"] == "cid":
                err = validate_cid(val)
                if err:
                    self._err_var.set(err); return
            if step["key"] == "password" and not val:
                self._err_var.set("Password is required."); return
            self._answers[step["key"]] = val
        if self._step < len(STEPS) - 1:
            self._step += 1
            self._show_step()
        else:
            self._run_apply()

    def _go_back(self):
        if self._step > 0:
            self._step -= 1
            self._show_step()

    def _ask_load_prev(self, prev):
        dlg = ctk.CTkToplevel(self)
        dlg.title("Kuwait FIR - OKAC Configurator")
        dlg.geometry("400x200")
        dlg.resizable(False, False)
        dlg.configure(fg_color=BLACK)
        dlg.transient(self)
        dlg.grab_set()
        dlg.attributes("-topmost", True)
        _set_icon(dlg)

        tk.Frame(dlg, bg=RED, height=3).pack(fill="x")
        ctk.CTkLabel(dlg, text="Load previous settings?", font=("Segoe UI", 15, "bold"), text_color=WHITE).pack(pady=(22, 4))
        ctk.CTkLabel(dlg, text="A saved configuration was found from a previous run.", font=("Segoe UI", 10), text_color=MUTED).pack()
        tk.Frame(dlg, bg=INPUT_BOR, height=1).pack(fill="x", pady=(18, 0))

        btn_row = ctk.CTkFrame(dlg, fg_color="#0A0A0A", corner_radius=0)
        btn_row.pack(fill="x")

        def do_skip():
            dlg.destroy()
            self._show_step()

        def do_load():
            for k in ("name", "initials", "cid", "password", "cpdlcc", "rating"):
                self._answers[k] = prev.get(k, RATING_DEFAULT if k == "rating" else "")
            dlg.destroy()
            self._show_step()

        ctk.CTkButton(btn_row, text="Start fresh", font=("Segoe UI", 11), height=42, fg_color="transparent", hover_color="#161616", border_width=0, text_color=MUTED, command=do_skip).pack(side="left", fill="x", expand=True)
        tk.Frame(btn_row, bg=INPUT_BOR, width=1).pack(side="left", fill="y")
        ctk.CTkButton(btn_row, text="Load", font=("Segoe UI", 11, "bold"), height=42, fg_color=RED, hover_color=RED_HOV, border_width=0, text_color=WHITE, corner_radius=0, command=do_load).pack(side="left", fill="x", expand=True)

        self._center_child(dlg)
        self.wait_window(dlg)

    def _run_apply(self):
        self._next_btn.configure(state="disabled", text="Applying...")
        self._back_btn.configure(state="disabled")
        self._q_var.set("Applying configuration...")
        self._hint_var.set(f"OKAC root:  {OKAC_ROOT}")
        self._hint_lbl.configure(text_color=MUTED)
        self._entry.place_forget()
        self._combo.place_forget()
        self._step_var.set("")
        self.update()
        try:
            save_options(self._answers)
            patched_files, cpdlc_updated, errors = apply_configuration(self._answers)
            summary = [f"{len(patched_files)} profile{'s' if len(patched_files) != 1 else ''} updated"]
            if cpdlc_updated:
                summary.append(f"Hoppie ACARS code updated ({cpdlc_updated} file{'s' if cpdlc_updated != 1 else ''})")
            else:
                summary.append("Hoppie ACARS code - skipped (left blank)")
            self._show_result(
                title="Done" if not errors else "Warning",
                summary=summary,
                bar_color=SUCCESS if not errors else WARN,
                success_items=patched_files,
                error_items=[f"{n}: {e}" for n, e in errors],
            )
        except Exception as e:
            self._show_result(title="Error", summary=[str(e)], bar_color=WARN, success_items=[], error_items=[], is_hard_error=True)

    def _show_result(self, title, summary, bar_color, success_items, error_items, is_hard_error=False):
        cw = self._prog_canvas.winfo_width() or self.W
        self._prog_canvas.delete("all")
        self._prog_canvas.create_rectangle(0, 0, cw, 3, fill=bar_color, outline="")
        for attr in ("_q_lbl", "_hint_lbl", "_err_lbl", "_entry", "_combo", "_footer"):
            getattr(self, attr).place_forget()
        self._back_btn.pack_forget()
        self._step_var.set("")
        for widget in self._body.winfo_children():
            if widget not in (self._q_lbl, self._hint_lbl, self._entry, self._combo, self._err_lbl, self._footer):
                widget.destroy()

        container = ctk.CTkFrame(self._body, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=28, pady=(20, 0))

        title_color = WHITE if bar_color == SUCCESS else (WARN if bar_color == WARN else "#FF6B6B")
        ctk.CTkLabel(container, text=title, font=("Segoe UI", 20, "bold"), text_color=title_color, anchor="w").pack(anchor="w")
        ctk.CTkLabel(container, text="\n".join(summary), font=("Segoe UI", 10), text_color=MUTED, anchor="w", justify="left", wraplength=400).pack(anchor="w", pady=(6, 10))

        if success_items:
            self._collapsible(container, f"Successful ({len(success_items)})", success_items, SUCCESS)
        if error_items:
            self._collapsible(container, f"Errors ({len(error_items)})", error_items, "#FF6B6B", start_open=True)

        btn_bar = ctk.CTkFrame(self._body, fg_color="transparent")
        btn_bar.pack(side="bottom", anchor="e", padx=28, pady=(6, 14))
        if is_hard_error:
            ctk.CTkButton(btn_bar, text="Retry", font=("Segoe UI", 11, "bold"), width=110, height=34, fg_color=RED, hover_color=RED_HOV, text_color=WHITE, command=self._show_step).pack()
        else:
            bc = SUCCESS if bar_color == SUCCESS else WARN
            bh = "#388E3C" if bar_color == SUCCESS else "#B88200"
            ctk.CTkButton(btn_bar, text="Close", font=("Segoe UI", 11, "bold"), width=110, height=34, fg_color=bc, hover_color=bh, text_color=WHITE, command=lambda: (self.destroy(), sys.exit())).pack()

    def _collapsible(self, parent, label, items, color, start_open=False):
        outer = ctk.CTkFrame(parent, fg_color="transparent")
        outer.pack(fill="x", pady=(0, 4))
        is_open = tk.BooleanVar(value=start_open)
        content = ctk.CTkFrame(outer, fg_color="#111111", corner_radius=4)
        rows = min(len(items), 5)
        txt = tk.Text(content, height=rows, bg="#111111", fg=color, font=("Courier New", 9), relief="flat", bd=0, wrap="word", state="disabled", highlightthickness=0, selectbackground="#1F1F1F")
        txt.pack(fill="x", padx=8, pady=6)
        txt.configure(state="normal")
        txt.insert("end", "\n".join(items))
        txt.configure(state="disabled")

        def toggle():
            if is_open.get():
                content.pack_forget()
                btn.configure(text=f"> {label}")
                is_open.set(False)
            else:
                content.pack(fill="x", pady=(2, 0))
                btn.configure(text=f"v {label}")
                is_open.set(True)
            self._fit_height()

        btn = ctk.CTkButton(outer, text=f"{'v' if start_open else '>'} {label}", font=("Segoe UI", 10, "bold"), anchor="w", fg_color="transparent", hover_color="#1F1F1F", border_width=0, text_color=color, height=26, command=toggle)
        btn.pack(fill="x")
        if start_open:
            content.pack(fill="x", pady=(2, 0))

    def _fit_height(self):
        self.update_idletasks()
        hdr  = self._header.winfo_height()
        body = self._body.winfo_reqheight()
        new_h = max(self.H, min(hdr + 3 + body + 10, self.H_MAX))
        self.geometry(f"{self.W}x{new_h}+{self.winfo_x()}+{self.winfo_y()}")

    def _set_height(self, h):
        self.geometry(f"{self.W}x{h}+{self.winfo_x()}+{self.winfo_y()}")

    def _center(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{self.W}x{self.H}+{(sw-self.W)//2}+{(sh-self.H)//2}")

    def _center_child(self, w):
        w.update_idletasks()
        cw, ch = w.winfo_width(), w.winfo_height()
        px = self.winfo_x() + (self.W - cw) // 2
        py = self.winfo_y() + (self.H - ch) // 2
        w.geometry(f"{cw}x{ch}+{px}+{py}")


def main():
    lockfile = os.path.join(_EXE_DIR, "configurator.lock")
    if os.path.exists(lockfile):
        root = ctk.CTk()
        root.title("OKAC Configurator")
        root.geometry("320x120")
        root.resizable(False, False)
        root.configure(fg_color=SURFACE)
        _set_icon(root)
        ctk.CTkLabel(root, text="Already running", font=("Segoe UI", 14, "bold"), text_color=WHITE).pack(pady=(28, 4))
        ctk.CTkLabel(root, text="The configurator is already open.", font=("Segoe UI", 10), text_color=MUTED).pack()
        ctk.CTkButton(root, text="OK", width=80, height=30, fg_color=RED, hover_color=RED_HOV, font=("Segoe UI", 11, "bold"), text_color=WHITE, command=root.destroy).pack(pady=14)
        root.mainloop()
        return
    try:
        with open(lockfile, "w") as f:
            f.write(str(os.getpid()))
        app = Configurator()
        app.mainloop()
    finally:
        time.sleep(0.2)
        try:
            os.remove(lockfile)
        except Exception:
            pass


if __name__ == "__main__":
    main()
