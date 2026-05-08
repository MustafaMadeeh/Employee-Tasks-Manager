import os
import re
import time
import sqlite3
import psutil
import threading
import datetime
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from collections import defaultdict
import math
#Mustafa Madeeh

APP_NAME = "Auto Tasks Logger"
DB_FILE = "work_journal_auto.db"
REPORTS_DIR = "reports"

TRACK_INTERVAL = 1
AUTO_GENERATE_EVERY_SECONDS = 15
MIN_ACTIVITY_SECONDS = 1
MIN_TASK_SECONDS = 5
TASK_GAP_SECONDS = 10 * 60
IDLE_AFTER_SECONDS = 10 * 60
MERGE_SIMILAR_THRESHOLD = 0.18

IGNORE_APPS = {
    "whatsapp", "telegram", "discord", "signal", "messenger",
    "spotify", "vlc", "wmplayer", "winamp"
}

STOP_WORDS = {
    "google", "chrome", "edge", "firefox", "mozilla", "visual", "studio",
    "code", "window", "file", "edit", "view", "new", "tab", "microsoft",
    "windows", "localhost", "default", "home", "search", "open", "save",
    "application", "untitled", "start", "null", "none", "true", "false",
    "loading", "please", "wait", "error", "warning", "info"
}

TASK_RULES = [
    ("Manual Task", ["manual task", "manual entry"]),
    ("Remote Support Session", ["anydesk", "teamviewer", "rustdesk", "remote desktop", "quick assist", "ultraviewer", "supremo"]),
    ("Database Work", ["mysql", "mariadb", "phpmyadmin", "heidisql", "sqlyog", "navicat", "dbeaver", "sql", "query", "select from", "update set", "insert into", "delete from", "table structure", "database"]),
    ("VOIP / PBX Configuration", ["voip", "sip", "pbx", "3cx", "asterisk", "microsip", "extension", "trunk", "yealink", "grandstream", "fanvil", "polycom", "softphone"]),
    ("Network / Firewall Configuration", ["mikrotik", "winbox", "router", "switch", "dhcp", "dns", "nat", "firewall", "gateway", "vlan", "fortigate", "pfsense", "opnsense", "ubiquiti", "unifi", "cisco", "netmask", "subnet", "routing"]),
    ("Software Development", ["laravel", "php", "python", "django", "flask", "fastapi", "blade", "controller", "route", "model", "html", "css", "javascript", "typescript", "react", "vue", "node", ".php", ".py", ".js", ".ts", ".jsx", ".tsx", "function", "class", "import", "export"]),
    ("Bug Fixing / Debugging", ["error", "exception", "traceback", "debug", "fix", "bug", "stacktrace", "undefined", "syntax", "null pointer", "console.log", "breakpoint", "inspect element"]),
    ("Server / Linux Administration", ["ssh", "putty", "winscp", "terminal", "cmd", "powershell", "bash", "linux", "apache", "nginx", "systemctl", "journalctl", "cpanel", "plesk", "centos", "ubuntu", "alma", "debian", "sudo", "chmod", "crontab", "htaccess"]),
    ("Email / Helpdesk Work", ["gmail", "outlook", "thunderbird", "email", "mail", "inbox", "ticket", "helpdesk", "reply", "support", "zendesk", "freshdesk", "compose"]),
    ("Document / Report Work", ["word", "excel", "powerpoint", "libreoffice", "pdf", "report", "document", ".docx", ".xlsx", ".pptx", ".odt", ".ods"]),
    ("File Management", ["explorer", "total commander", "winrar", "7-zip", "winscp", "filezilla", "ftp", "sftp"]),
    ("Web Browsing / Research", ["chrome", "firefox", "edge", "opera", "brave", "safari"]),
]

TASK_CONTEXT = {
    "Manual Task": "This task was entered manually by the user from the floating quick-add form.",
    "Remote Support Session": "A remote desktop or support tool was actively used, suggesting assistance was being provided to a client or colleague.",
    "Database Work": "Database queries, schema edits, or data management tasks were detected.",
    "VOIP / PBX Configuration": "VOIP phone system or PBX configuration work was detected.",
    "Network / Firewall Configuration": "Network device configuration or firewall rule management was detected.",
    "Software Development": "Active code editing or development activity was detected across one or more programming files or frameworks.",
    "Bug Fixing / Debugging": "Debugging activity was detected including error tracing, log analysis, or code correction.",
    "Server / Linux Administration": "Server-side administration was detected, including SSH sessions, system service management, or web server configuration.",
    "Email / Helpdesk Work": "Email composition, ticket handling, or helpdesk communication was actively taking place.",
    "Document / Report Work": "Document creation, editing, or review was detected.",
    "File Management": "File system operations such as organizing, transferring, or archiving files were detected.",
    "Web Browsing / Research": "Extended web browsing or online research was detected.",
}

TASK_ICONS = {
    "Manual Task": "➕",
    "Remote Support Session": "🖥",
    "Database Work": "🗄",
    "VOIP / PBX Configuration": "📞",
    "Network / Firewall Configuration": "🌐",
    "Software Development": "💻",
    "Bug Fixing / Debugging": "🐛",
    "Server / Linux Administration": "⚙",
    "Email / Helpdesk Work": "📧",
    "Document / Report Work": "📄",
    "File Management": "📁",
    "Web Browsing / Research": "🔍",
}

TASK_COLORS = {
    "Manual Task": ("#22c55e", "#14532d"),
    "Remote Support Session": ("#0ea5e9", "#0c4a6e"),
    "Database Work": ("#a855f7", "#3b0764"),
    "VOIP / PBX Configuration": ("#22c55e", "#14532d"),
    "Network / Firewall Configuration": ("#f59e0b", "#451a03"),
    "Software Development": ("#3b82f6", "#1e3a8a"),
    "Bug Fixing / Debugging": ("#ef4444", "#7f1d1d"),
    "Server / Linux Administration": ("#14b8a6", "#134e4a"),
    "Email / Helpdesk Work": ("#f97316", "#431407"),
    "Document / Report Work": ("#8b5cf6", "#2e1065"),
    "File Management": ("#64748b", "#1e293b"),
    "Web Browsing / Research": ("#06b6d4", "#0c4a6e"),
}

DEFAULT_COLORS = ("#6366f1", "#1e1b4b")


def today_str():
    return datetime.datetime.now().strftime("%Y-%m-%d")


def now_dt():
    return datetime.datetime.now()


def dt_str(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(v):
    return datetime.datetime.strptime(v, "%Y-%m-%d %H:%M:%S")


def clean_text(t):
    return re.sub(r"\s+", " ", str(t or "")).strip()


def seconds_to_text(s):
    s = int(s)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m"
    return f"{sec}s"


def get_idle_seconds():
    try:
        import ctypes

        class LASTINPUTINFO(ctypes.Structure):
            _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

        lii = LASTINPUTINFO()
        lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
        ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
        return (ctypes.windll.kernel32.GetTickCount() - lii.dwTime) / 1000
    except Exception:
        return 0


def get_active_window_info():
    try:
        import ctypes
        from ctypes import wintypes

        u = ctypes.windll.user32
        hwnd = u.GetForegroundWindow()

        ln = u.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(ln + 1)
        u.GetWindowTextW(hwnd, buf, ln + 1)
        title = clean_text(buf.value)

        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        app = "Unknown"
        try:
            app = clean_text(psutil.Process(pid.value).name())
        except Exception:
            pass

        return app, title or "No Window Title"
    except Exception:
        return "Unknown", "Could not read active window"


class Database:
    def __init__(self):
        self.conn = sqlite3.connect(DB_FILE, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                app_name TEXT NOT NULL,
                window_title TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL
            )
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS task_reports(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                title TEXT NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT NOT NULL,
                duration_seconds INTEGER NOT NULL,
                apps TEXT,
                summary TEXT,
                problem TEXT,
                actions TEXT,
                result TEXT,
                confidence INTEGER,
                unique_key TEXT UNIQUE
            )
        """)

        self.conn.commit()

    def insert_activity(self, started_at, ended_at, app_name, window_title, dur):
        with self._lock:
            self.conn.execute(
                """
                INSERT INTO activity_logs(started_at, ended_at, app_name, window_title, duration_seconds)
                VALUES (?, ?, ?, ?, ?)
                """,
                (started_at, ended_at, app_name, window_title, dur)
            )
            self.conn.commit()

    def get_today_activities(self):
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "SELECT * FROM activity_logs WHERE started_at LIKE ? ORDER BY started_at",
                (today_str() + "%",)
            )
            return c.fetchall()

    def upsert_task(self, t):
        with self._lock:
            self.conn.execute("""
                INSERT OR REPLACE INTO task_reports
                (report_date, title, started_at, ended_at, duration_seconds,
                 apps, summary, problem, actions, result, confidence, unique_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                today_str(),
                t["title"],
                t["started_at"],
                t["ended_at"],
                t["duration_seconds"],
                t["apps"],
                t["summary"],
                t["problem"],
                t["actions"],
                t["result"],
                t["confidence"],
                t["unique_key"]
            ))
            self.conn.commit()

    def get_today_reports(self):
        with self._lock:
            c = self.conn.cursor()
            c.execute(
                "SELECT * FROM task_reports WHERE report_date=? ORDER BY started_at",
                (today_str(),)
            )
            return c.fetchall()

    def clear_today_reports(self):
        with self._lock:
            self.conn.execute("DELETE FROM task_reports WHERE report_date=?", (today_str(),))
            self.conn.commit()

    def clear_today_all(self):
        with self._lock:
            self.conn.execute("DELETE FROM task_reports WHERE report_date=?", (today_str(),))
            self.conn.execute("DELETE FROM activity_logs WHERE started_at LIKE ?", (today_str() + "%",))
            self.conn.commit()

    def insert_manual_task(self, task_name, task_info, task_minutes, task_for):
        task_minutes = int(task_minutes)
        end = datetime.datetime.now()
        start = end - datetime.timedelta(minutes=task_minutes)

        title = f"Manual Task: {task_name}"
        unique_key = dt_str(start) + "|" + title

        self.upsert_task({
            "title": title,
            "started_at": dt_str(start),
            "ended_at": dt_str(end),
            "duration_seconds": task_minutes * 60,
            "apps": "Manual Entry",
            "summary": task_info,
            "problem": f"Task For: {task_for}",
            "actions": (
                f"Manual task entered by user:\n"
                f"  • Task Name: {task_name}\n"
                f"  • Task For: {task_for}\n"
                f"  • Time: {task_minutes} minute(s)\n"
                f"  • Info: {task_info}"
            ),
            "result": "Manual task was saved successfully.",
            "confidence": 100,
            "unique_key": unique_key
        })


class ActivityTracker:
    def __init__(self, db):
        self.db = db
        self.running = False
        self.thread = None
        self._lock = threading.Lock()

        self.current_app = None
        self.current_title = None
        self.current_start = None

        self.last_app = None
        self.last_title = None
        self.is_idle = False

    def _ignored(self, app, title):
        return any(x in f"{app} {title}".lower() for x in IGNORE_APPS)

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False
        self.flush(force=True)

    def _loop(self):
        while self.running:
            if get_idle_seconds() >= IDLE_AFTER_SECONDS:
                if not self.is_idle:
                    self.flush(force=True)
                    self.is_idle = True
                time.sleep(TRACK_INTERVAL)
                continue

            self.is_idle = False
            app, title = get_active_window_info()

            if self._ignored(app, title):
                self.flush(force=True)
                time.sleep(TRACK_INTERVAL)
                continue

            with self._lock:
                if self.current_app is None:
                    self.current_app = app
                    self.current_title = title
                    self.current_start = now_dt()
                elif app != self.current_app or title != self.current_title:
                    self._flush_locked()
                    self.current_app = app
                    self.current_title = title
                    self.current_start = now_dt()

                self.last_app = app
                self.last_title = title

            time.sleep(TRACK_INTERVAL)

    def flush(self, force=False):
        with self._lock:
            self._flush_locked(force)

    def _flush_locked(self, force=False):
        if not self.current_app or not self.current_start:
            return

        end = now_dt()
        dur = int((end - self.current_start).total_seconds())

        if dur >= MIN_ACTIVITY_SECONDS:
            self.db.insert_activity(
                dt_str(self.current_start),
                dt_str(end),
                self.current_app,
                self.current_title,
                dur
            )

        self.current_app = None
        self.current_title = None
        self.current_start = None


class SmartTaskEngine:
    def tokens(self, text):
        parts = re.findall(r"[a-zA-Z0-9_.@#:/\\-]+", clean_text(text).lower())
        return {x.replace(".exe", "") for x in parts if len(x) >= 3 and x not in STOP_WORDS}

    def score_rule(self, text, kws):
        t = text.lower()
        return sum(1 + len(kw.split()) * 0.5 for kw in kws if kw.lower() in t)

    def best_rule(self, group):
        weighted = ""
        for x in group:
            w = max(1, int(x["duration_seconds"]) // 5)
            weighted += f" {x['app_name']} {x['window_title']}" * w

        scores = [(title, self.score_rule(weighted, kws)) for title, kws in TASK_RULES]
        scores = [(t, s) for t, s in scores if s > 0]

        if not scores:
            return self._dynamic_title(group), 42

        scores.sort(key=lambda x: x[1], reverse=True)
        best, bscore = scores[0]

        if len(scores) >= 2 and scores[1][1] >= scores[0][1] * 0.75 and "Remote" not in best:
            best = f"{best} + {scores[1][0]}"

        conf = min(97, 55 + int(bscore) * 7)
        return best, conf

    def similarity(self, a, b):
        ta = self.tokens(a["app_name"] + " " + a["window_title"])
        tb = self.tokens(b["app_name"] + " " + b["window_title"])

        if not ta or not tb:
            return 0.0

        j = len(ta & tb) / max(1, len(ta | tb))
        return min(1.0, j + (0.15 if a["app_name"] == b["app_name"] else 0))

    def same_family(self, a, b):
        ta = f"{a['app_name']} {a['window_title']}".lower()
        tb = f"{b['app_name']} {b['window_title']}".lower()

        for _, kws in TASK_RULES:
            if self.score_rule(ta, kws) > 0 and self.score_rule(tb, kws) > 0:
                return True

        return False

    def group_activities(self, activities):
        groups = []
        current = []

        for act in activities:
            if not current:
                current.append(act)
                continue

            last = current[-1]
            gap = (parse_dt(act["started_at"]) - parse_dt(last["ended_at"])).total_seconds()

            if (
                gap <= TASK_GAP_SECONDS
                or self.similarity(last, act) >= MERGE_SIMILAR_THRESHOLD
                or self.same_family(last, act)
            ):
                current.append(act)
            else:
                groups.append(current)
                current = [act]

        if current:
            groups.append(current)

        merged = []
        for g in groups:
            if merged and self._should_merge(merged[-1], g):
                merged[-1] += g
            else:
                merged.append(g)

        return merged

    def _should_merge(self, g1, g2):
        if not g1 or not g2:
            return False

        gap = (parse_dt(g2[0]["started_at"]) - parse_dt(g1[-1]["ended_at"])).total_seconds()
        return gap <= TASK_GAP_SECONDS * 1.5 and self.same_family(g1[-1], g2[0])

    def _dynamic_title(self, group):
        freq = defaultdict(int)

        for x in group:
            for tok in self.tokens(x["app_name"] + " " + x["window_title"]):
                if len(tok) >= 4:
                    freq[tok] += x["duration_seconds"]

        top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
        return "Work on " + ", ".join(w for w, _ in top) if top else "General Work Session"

    def build_actions(self, group):
        app_time = defaultdict(int)

        for x in group:
            app_time[x["app_name"]] += x["duration_seconds"]

        lines = ["Apps used (by time):"]
        for app, secs in sorted(app_time.items(), key=lambda x: x[1], reverse=True)[:6]:
            lines.append(f"  • {app} — {seconds_to_text(secs)}")

        lines.append("")
        lines.append("Window activity:")

        seen = set()
        for x in group:
            key = x["app_name"] + "|" + x["window_title"][:80]
            if key in seen:
                continue

            seen.add(key)
            lines.append(f"  [{seconds_to_text(x['duration_seconds'])}] {x['app_name']}: {x['window_title'][:120]}")

            if len(lines) > 25:
                break

        return "\n".join(lines)

    def make_task(self, group):
        dur = sum(int(x["duration_seconds"]) for x in group)
        apps = sorted(set(x["app_name"] for x in group))
        title, conf = self.best_rule(group)

        combined = " ".join(f"{x['app_name']} {x['window_title']}" for x in group).lower()
        if "anydesk" in combined and "remote" not in title.lower():
            title = "Remote Support + " + title
            conf = max(conf, 82)

        started_at = group[0]["started_at"]
        ended_at = group[-1]["ended_at"]

        app_time = defaultdict(int)
        for x in group:
            app_time[x["app_name"]] += x["duration_seconds"]

        top_app = max(app_time.items(), key=lambda x: x[1])[0] if app_time else "Unknown"
        context_key = next((t for t in TASK_CONTEXT if t in title), None)

        return {
            "title": title,
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_seconds": dur,
            "apps": ", ".join(apps),
            "summary": f"Detected '{title}' session lasting {seconds_to_text(dur)}. Primary app: {top_app}. {len(apps)} app(s), {len(group)} windows tracked.",
            "problem": TASK_CONTEXT.get(context_key, "A continuous work session was detected from application and window activity."),
            "actions": self.build_actions(group),
            "result": f"Session logged and categorized with {conf}% confidence. Total time: {seconds_to_text(dur)}.",
            "confidence": conf,
            "unique_key": started_at[:16] + "|" + title[:40]
        }

    def generate_tasks(self, activities):
        return [
            self.make_task(g)
            for g in self.group_activities(activities)
            if sum(int(x["duration_seconds"]) for x in g) >= MIN_TASK_SECONDS
        ]


class ManualTaskWindow:
    def __init__(self, root, db, on_saved):
        self.root = root
        self.db = db
        self.on_saved = on_saved

        self.win = tk.Toplevel(root)
        self.win.title("➕ Add Manual Task")
        self.win.geometry("460x580")
        self.win.configure(bg="#0d1626")
        self.win.attributes("-topmost", True)
        self.win.resizable(False, False)

        self._build()

    def _label(self, text):
        tk.Label(
            self.win,
            text=text,
            bg="#0d1626",
            fg="#93c5fd",
            font=("Segoe UI", 10, "bold")
        ).pack(anchor="w", padx=24, pady=(10, 4))

    def _entry(self):
        e = tk.Entry(
            self.win,
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="white",
            relief="flat",
            font=("Segoe UI", 11)
        )
        e.pack(fill="x", padx=24, ipady=8)
        return e

    def _build(self):
        tk.Label(
            self.win,
            text="➕ Add Manual Task",
            bg="#0d1626",
            fg="#f8fafc",
            font=("Segoe UI", 18, "bold")
        ).pack(anchor="w", padx=24, pady=(20, 12))

        self._label("Task Name")
        self.task_name = self._entry()

        self._label("Task For Who")
        self.task_for = self._entry()

        self._label("Task Time In Minutes")
        self.task_minutes = self._entry()

        self._label("Task Info")
        self.task_info = tk.Text(
            self.win,
            height=6,
            bg="#020617",
            fg="#e5e7eb",
            insertbackground="white",
            relief="flat",
            font=("Segoe UI", 10),
            wrap="word"
        )
        self.task_info.pack(fill="x", padx=24)

        buttons = tk.Frame(self.win, bg="#0d1626")
        buttons.pack(fill="x", padx=24, pady=22)

        tk.Button(
            buttons,
            text="Save Task",
            command=self.save,
            bg="#16a34a",
            fg="white",
            relief="flat",
            padx=18,
            pady=9,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2"
        ).pack(side="left")

        tk.Button(
            buttons,
            text="Cancel",
            command=self.win.destroy,
            bg="#1e293b",
            fg="#cbd5e1",
            relief="flat",
            padx=18,
            pady=9,
            font=("Segoe UI", 11, "bold"),
            cursor="hand2"
        ).pack(side="right")

    def save(self):
        name = self.task_name.get().strip()
        task_for = self.task_for.get().strip()
        minutes = self.task_minutes.get().strip()
        info = self.task_info.get("1.0", tk.END).strip()

        if not name or not task_for or not minutes or not info:
            messagebox.showwarning("Manual Task", "Please fill all fields.")
            return

        if not minutes.isdigit() or int(minutes) <= 0:
            messagebox.showwarning("Manual Task", "Task time must be a valid number in minutes.")
            return

        self.db.insert_manual_task(name, info, int(minutes), task_for)
        self.on_saved()
        self.win.destroy()


class FloatingWidget:
    def __init__(self, root, on_toggle, on_open, on_manual):
        self.root = root
        self.on_toggle = on_toggle
        self.on_open = on_open
        self.on_manual = on_manual

        self.tracking = True
        self._drag_x = 0
        self._drag_y = 0
        self._pulse = 0
        self._elapsed = 0
        self._session_start = time.time()

        self.win = tk.Toplevel(root)
        self.win.overrideredirect(True)
        self.win.attributes("-topmost", True)
        self.win.attributes("-alpha", 0.94)
        self.win.configure(bg="#0a0f1e")

        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        self.win.geometry(f"250x64+{sw - 270}+{sh - 120}")

        self._build()
        self._animate()

    def _build(self):
        outer = tk.Frame(self.win, bg="#0a0f1e", bd=0)
        outer.pack(fill="both", expand=True)

        self.cv = tk.Canvas(outer, width=250, height=64, bg="#0a0f1e", highlightthickness=0, bd=0)
        self.cv.pack()

        self._draw_pill()

        self.ring = self.cv.create_oval(12, 18, 30, 36, outline="#22c55e", width=2)
        self.dot = self.cv.create_oval(16, 22, 26, 32, fill="#22c55e", outline="")

        self.cv.create_text(50, 20, text="⚡", font=("Segoe UI", 11), fill="#f8fafc", anchor="w")

        self.status_txt = self.cv.create_text(
            70, 20,
            text="TRACKING",
            font=("Segoe UI", 8, "bold"),
            fill="#22c55e",
            anchor="w"
        )

        self.timer_txt = self.cv.create_text(
            50, 40,
            text="00:00:00",
            font=("Consolas", 11, "bold"),
            fill="#f8fafc",
            anchor="w"
        )

        self.btn_manual = self.cv.create_text(
            158, 20,
            text="✚",
            font=("Segoe UI", 15, "bold"),
            fill="#22c55e",
            anchor="w",
            tags="manual"
        )

        self.btn_toggle = self.cv.create_text(
            185, 20,
            text="⏸",
            font=("Segoe UI", 14),
            fill="#fbbf24",
            anchor="w",
            tags="toggle"
        )

        self.btn_open = self.cv.create_text(
            213, 20,
            text="🗖",
            font=("Segoe UI", 13),
            fill="#93c5fd",
            anchor="w",
            tags="open"
        )

        self.cv.tag_bind("manual", "<Button-1>", lambda e: self.on_manual())
        self.cv.tag_bind("toggle", "<Button-1>", lambda e: self._toggle())
        self.cv.tag_bind("open", "<Button-1>", lambda e: self.on_open())

        self.cv.bind("<Button-1>", self._start_drag)
        self.cv.bind("<B1-Motion>", self._do_drag)
        self.cv.bind("<Double-Button-1>", lambda e: self.on_open())

    def _draw_pill(self):
        r = 18
        x1, y1, x2, y2 = 4, 4, 246, 60

        pts = [
            x1 + r, y1, x2 - r, y1,
            x2, y1, x2, y1 + r,
            x2, y2 - r, x2, y2,
            x2 - r, y2, x1 + r, y2,
            x1, y2, x1, y2 - r,
            x1, y1 + r, x1, y1
        ]

        self.cv.create_polygon(
            pts,
            fill="#111827",
            outline="#1e3a5f",
            width=1.5,
            smooth=True
        )

    def _start_drag(self, e):
        self._drag_x = e.x_root - self.win.winfo_x()
        self._drag_y = e.y_root - self.win.winfo_y()

    def _do_drag(self, e):
        x = e.x_root - self._drag_x
        y = e.y_root - self._drag_y
        self.win.geometry(f"+{x}+{y}")

    def _toggle(self):
        self.tracking = not self.tracking
        if self.tracking:
            self._session_start = time.time()
        self.on_toggle(self.tracking)

    def _animate(self):
        self._pulse = (self._pulse + 1) % 20
        alpha = 0.4 + 0.6 * abs(math.sin(self._pulse * math.pi / 10))

        if self.tracking:
            self._elapsed = int(time.time() - self._session_start)
            h = self._elapsed // 3600
            m = (self._elapsed % 3600) // 60
            s = self._elapsed % 60
            timer = f"{h:02d}:{m:02d}:{s:02d}"

            green = int(alpha * 200 + 55)
            color = f"#{0:02x}{green:02x}{0:02x}"

            self.cv.itemconfig(self.dot, fill="#22c55e")
            self.cv.itemconfig(self.ring, outline=color)
            self.cv.itemconfig(self.status_txt, text="TRACKING", fill="#22c55e")
            self.cv.itemconfig(self.btn_toggle, text="⏸")
        else:
            timer = "PAUSED"
            self.cv.itemconfig(self.dot, fill="#ef4444")
            self.cv.itemconfig(self.ring, outline="#ef4444")
            self.cv.itemconfig(self.status_txt, text="PAUSED", fill="#ef4444")
            self.cv.itemconfig(self.btn_toggle, text="▶")

        self.cv.itemconfig(self.timer_txt, text=timer)
        self.win.after(100, self._animate)

    def set_tracking(self, state: bool):
        self.tracking = state
        if state:
            self._session_start = time.time()


class TaskCardWindow:
    def __init__(self, root, task, index):
        self.win = tk.Toplevel(root)
        self.win.attributes("-topmost", False)
        self.win.overrideredirect(False)

        title_key = next((t for t in TASK_COLORS if t in task["title"]), None)
        accent, bg_deep = TASK_COLORS.get(title_key, DEFAULT_COLORS)
        icon = TASK_ICONS.get(title_key, "📌")

        self.win.title(f"{icon} {task['title']}")
        self.win.configure(bg="#0d1626")
        self.win.geometry(f"560x520+{80 + (index % 4) * 30}+{80 + (index % 4) * 30}")
        self.win.resizable(True, True)

        self._build(task, accent, bg_deep, icon)

    def _build(self, task, accent, bg_deep, icon):
        conf = int(task["confidence"])
        conf_color = "#22c55e" if conf >= 85 else ("#f59e0b" if conf >= 65 else "#ef4444")

        header = tk.Frame(self.win, bg=bg_deep, pady=14)
        header.pack(fill="x")

        tk.Label(
            header,
            text=f"{icon}  {task['title']}",
            bg=bg_deep,
            fg="#f8fafc",
            font=("Segoe UI", 14, "bold"),
            padx=16
        ).pack(side="left")

        tk.Label(
            header,
            text=f"{conf}%",
            bg=conf_color,
            fg="white",
            font=("Segoe UI", 11, "bold"),
            padx=10,
            pady=4
        ).pack(side="right", padx=12)

        meta = tk.Frame(self.win, bg="#111827", pady=10)
        meta.pack(fill="x")

        meta_items = [
            ("🕐 Start", task["started_at"][11:16]),
            ("🕐 End", task["ended_at"][11:16]),
            ("⏱ Duration", seconds_to_text(task["duration_seconds"])),
        ]

        for label, value in meta_items:
            col = tk.Frame(meta, bg="#111827")
            col.pack(side="left", expand=True)
            tk.Label(col, text=label, bg="#111827", fg="#64748b", font=("Segoe UI", 8, "bold")).pack()
            tk.Label(col, text=value, bg="#111827", fg="#f8fafc", font=("Segoe UI", 13, "bold")).pack()

        bar_frame = tk.Frame(self.win, bg="#0d1626", pady=6, padx=14)
        bar_frame.pack(fill="x")

        bar_bg = tk.Canvas(bar_frame, height=8, bg="#1e293b", highlightthickness=0, bd=0)
        bar_bg.pack(fill="x")
        bar_bg.update_idletasks()

        w = bar_bg.winfo_width() or 520
        fill_w = max(8, int(w * conf / 100))
        bar_bg.create_rectangle(0, 0, fill_w, 6, fill=accent, outline="")

        body = scrolledtext.ScrolledText(
            self.win,
            bg="#080d18",
            fg="#cbd5e1",
            font=("Consolas", 9),
            wrap="word",
            relief="flat",
            padx=14,
            pady=10,
            insertbackground="white"
        )
        body.pack(fill="both", expand=True, padx=6, pady=6)

        sections = [
            ("📋 Summary", task["summary"]),
            ("🔍 Context", task["problem"]),
            ("⚙ Actions", task["actions"]),
            ("✅ Result", task["result"]),
            ("🖥 Apps Used", task["apps"]),
        ]

        for heading, content in sections:
            body.insert(tk.END, f"\n{heading}\n", "heading")
            body.insert(tk.END, f"{content}\n\n")

        body.tag_config("heading", foreground=accent, font=("Segoe UI", 10, "bold"))
        body.config(state="disabled")

        foot = tk.Frame(self.win, bg="#0d1626", pady=8)
        foot.pack(fill="x")

        tk.Button(
            foot,
            text="Close",
            command=self.win.destroy,
            bg="#1e293b",
            fg="#94a3b8",
            relief="flat",
            padx=16,
            pady=6,
            font=("Segoe UI", 9),
            cursor="hand2"
        ).pack(side="right", padx=12)


class ReportExporter:
    def __init__(self, db):
        self.db = db

    def export_html(self):
        os.makedirs(REPORTS_DIR, exist_ok=True)
        path = os.path.abspath(os.path.join(REPORTS_DIR, f"{today_str()}-report.html"))

        reports = self.db.get_today_reports()
        total = sum(int(r["duration_seconds"]) for r in reports)
        cards = ""

        for r in reports:
            conf = int(r["confidence"])
            cc = "#22c55e" if conf >= 85 else ("#f59e0b" if conf >= 65 else "#ef4444")

            title_key = next((t for t in TASK_COLORS if t in r["title"]), None)
            accent, _ = TASK_COLORS.get(title_key, DEFAULT_COLORS)
            icon = TASK_ICONS.get(title_key, "📌")

            w = min(100, max(5, int(int(r["duration_seconds"]) / max(1, total) * 100)))
            actions = str(r["actions"]).replace("\n", "<br>")

            cards += f"""
<div class="task">
  <div class="task-head" style="border-left:4px solid {accent}">
    <span class="icon">{icon}</span>
    <h2>{r['title']}</h2>
    <span class="conf" style="background:{cc}">{conf}%</span>
  </div>
  <p class="summary">{r['summary']}</p>
  <div class="bar"><div style="width:{w}%;background:{accent}"></div></div>
  <div class="meta">
    <span>🕐 {r['started_at'][11:16]} → {r['ended_at'][11:16]}</span>
    <span>⏱ {seconds_to_text(r['duration_seconds'])}</span>
    <span>🖥 {r['apps']}</span>
  </div>
  <h3>🔍 Context</h3><p>{r['problem']}</p>
  <h3>⚙ Actions</h3><p>{actions}</p>
  <h3>✅ Result</h3><p>{r['result']}</p>
</div>
"""

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Work Journal {today_str()}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Segoe UI',sans-serif;background:#020617;color:#e2e8f0;min-height:100vh}}
.hero{{padding:40px;background:linear-gradient(135deg,#0f172a,#1e1b4b);border-bottom:1px solid #1e293b}}
.hero h1{{font-size:32px;color:#f8fafc}}
.hero p{{color:#64748b;margin-top:4px}}
.stats{{display:flex;gap:20px;margin-top:24px;flex-wrap:wrap}}
.stat{{padding:18px 24px;background:rgba(255,255,255,.05);border-radius:16px;border:1px solid rgba(255,255,255,.08)}}
.stat small{{color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.06em;display:block}}
.stat b{{font-size:28px;color:#f8fafc;display:block;margin-top:4px}}
.cards{{max-width:1100px;margin:40px auto;padding:0 30px}}
.task{{margin:24px 0;padding:28px;background:#0d1626;border-radius:20px;border:1px solid #1e293b;box-shadow:0 8px 32px rgba(0,0,0,.4)}}
.task-head{{display:flex;align-items:center;gap:12px;margin-bottom:14px;padding-left:12px}}
.task-head .icon{{font-size:24px}}
.task-head h2{{flex:1;font-size:18px;color:#f8fafc}}
.conf{{padding:5px 14px;border-radius:999px;font-size:13px;font-weight:700;color:#000}}
.summary{{color:#94a3b8;line-height:1.7;margin-bottom:14px}}
.bar{{height:8px;background:#1e293b;border-radius:999px;overflow:hidden;margin-bottom:16px}}
.bar div{{height:100%;border-radius:999px}}
.meta{{display:flex;gap:20px;color:#64748b;font-size:13px;margin-bottom:20px;flex-wrap:wrap}}
h3{{color:#93c5fd;font-size:13px;text-transform:uppercase;letter-spacing:.05em;margin:16px 0 6px}}
p{{color:#cbd5e1;line-height:1.75;font-size:14px}}
</style>
</head>
<body>
<div class="hero">
  <h1>📋 Daily Work Journal</h1>
  <p>{today_str()} · Auto Tasks Logger · Generated {datetime.datetime.now().strftime('%H:%M')}</p>
  <div class="stats">
    <div class="stat"><small>Total Work Time</small><b>{seconds_to_text(total)}</b></div>
    <div class="stat"><small>Tasks Detected</small><b>{len(reports)}</b></div>
    <div class="stat"><small>Report Date</small><b>{today_str()}</b></div>
  </div>
</div>
<div class="cards">{cards or "<p style='color:#64748b;text-align:center;padding:60px'>No tasks yet.</p>"}</div>
</body>
</html>
"""

        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

        return path


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_NAME)
        self.root.geometry("1400x880")
        self.root.configure(bg="#080d18")

        self.db = Database()
        self.tracker = ActivityTracker(self.db)
        self.engine = SmartTaskEngine()
        self.exporter = ReportExporter(self.db)

        self.tracking_on = True
        self.last_auto_gen = 0
        self.open_card_windows = {}

        self._build_ui()

        self.tracker.start()

        self.float_widget = FloatingWidget(
            self.root,
            on_toggle=self._float_toggle,
            on_open=self._show_main,
            on_manual=self._open_manual_task
        )

        self._refresh_loop()

    def _float_toggle(self, now_tracking: bool):
        self.tracking_on = now_tracking

        if now_tracking:
            self.tracker.start()
            self.status_lbl.config(text="● Tracking", bg="#14532d")
            self.toggle_btn.config(text="⏸ Pause", bg="#dc2626")
        else:
            self.tracker.stop()
            self.status_lbl.config(text="⏸ Paused", bg="#7f1d1d")
            self.toggle_btn.config(text="▶ Resume", bg="#16a34a")
            self._do_generate()

    def _show_main(self):
        self.root.deiconify()
        self.root.lift()

    def _open_manual_task(self):
        ManualTaskWindow(self.root, self.db, self._refresh_all)

    def _build_ui(self):
        style = ttk.Style()
        style.theme_use("clam")

        style.configure(
            "Treeview",
            background="#0d1626",
            foreground="#e2e8f0",
            rowheight=34,
            fieldbackground="#0d1626",
            borderwidth=0
        )

        style.configure(
            "Treeview.Heading",
            background="#111827",
            foreground="#93c5fd",
            font=("Segoe UI", 10, "bold"),
            relief="flat"
        )

        style.map("Treeview", background=[("selected", "#1e3a5f")])

        style.configure(
            "TNotebook",
            background="#080d18",
            borderwidth=0
        )

        style.configure(
            "TNotebook.Tab",
            padding=[18, 10],
            font=("Segoe UI", 10, "bold"),
            background="#0d1626",
            foreground="#64748b"
        )

        style.map(
            "TNotebook.Tab",
            background=[("selected", "#111827")],
            foreground=[("selected", "#f8fafc")]
        )

        hdr = tk.Frame(self.root, bg="#080d18")
        hdr.pack(fill="x", padx=22, pady=14)

        tk.Label(
            hdr,
            text="⚡ Auto Tasks Logger",
            bg="#080d18",
            fg="#f8fafc",
            font=("Segoe UI", 22, "bold")
        ).pack(side="left")

        self.status_lbl = tk.Label(
            hdr,
            text="● Tracking",
            bg="#14532d",
            fg="white",
            padx=14,
            pady=6,
            font=("Segoe UI", 11, "bold")
        )
        self.status_lbl.pack(side="right")

        bar = tk.Frame(self.root, bg="#080d18")
        bar.pack(fill="x", padx=22, pady=4)

        self.toggle_btn = tk.Button(
            bar,
            text="⏸ Pause",
            command=self._toggle_tracking,
            bg="#dc2626",
            fg="white",
            relief="flat",
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        )
        self.toggle_btn.pack(side="left", padx=4)

        self._btn(bar, "➕ Add Manual Task", self._open_manual_task, "#16a34a")
        self._btn(bar, "🔄 Generate Now", self._manual_generate, "#2563eb")
        self._btn(bar, "🌐 HTML Report", self._open_html, "#7c3aed")
        self._btn(bar, "📂 Open Cards", self._open_all_cards, "#0891b2")
        self._btn(bar, "🗑 Clear Today", self._clear_today, "#b45309")

        self.live_lbl = tk.Label(
            self.root,
            text="  ● Current: —",
            bg="#0d1626",
            fg="#64748b",
            font=("Segoe UI", 9),
            anchor="w",
            padx=12,
            pady=5
        )
        self.live_lbl.pack(fill="x", padx=22, pady=2)

        self.nb = ttk.Notebook(self.root)
        self.nb.pack(fill="both", expand=True, padx=22, pady=8)

        self.tab_dash = tk.Frame(self.nb, bg="#080d18")
        self.tab_tasks = tk.Frame(self.nb, bg="#080d18")
        self.tab_logs = tk.Frame(self.nb, bg="#080d18")
        self.tab_rpt = tk.Frame(self.nb, bg="#080d18")

        self.nb.add(self.tab_dash, text="  📊 Dashboard  ")
        self.nb.add(self.tab_tasks, text="  ✅ Tasks  ")
        self.nb.add(self.tab_logs, text="  📝 Logs  ")
        self.nb.add(self.tab_rpt, text="  📄 Report  ")

        self._build_dashboard()
        self._build_tasks_tab()
        self._build_logs_tab()
        self._build_report_tab()

    def _btn(self, p, txt, cmd, bg):
        tk.Button(
            p,
            text=txt,
            command=cmd,
            bg=bg,
            fg="white",
            relief="flat",
            padx=14,
            pady=8,
            font=("Segoe UI", 10, "bold"),
            cursor="hand2"
        ).pack(side="left", padx=4)

    def _build_dashboard(self):
        kf = tk.Frame(self.tab_dash, bg="#080d18")
        kf.pack(fill="x", pady=12, padx=8)

        self.kpi_total = self._kpi(kf, "Total Work Time", "0m")
        self.kpi_tasks = self._kpi(kf, "Tasks Detected", "0")
        self.kpi_logs = self._kpi(kf, "Log Entries", "0")
        self.kpi_top = self._kpi(kf, "Top App", "—")
        self.kpi_conf = self._kpi(kf, "Avg Confidence", "—")

        self.canvas = tk.Canvas(self.tab_dash, bg="#040810", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=8, pady=8)

    def _kpi(self, parent, title, val):
        box = tk.Frame(parent, bg="#0d1626", padx=16, pady=14)
        box.pack(side="left", fill="x", expand=True, padx=5)

        tk.Label(
            box,
            text=title,
            bg="#0d1626",
            fg="#64748b",
            font=("Segoe UI", 9, "bold")
        ).pack(anchor="w")

        lbl = tk.Label(
            box,
            text=val,
            bg="#0d1626",
            fg="#f8fafc",
            font=("Segoe UI", 20, "bold")
        )
        lbl.pack(anchor="w", pady=(4, 0))

        return lbl

    def _build_tasks_tab(self):
        cols = [
            ("icon", "", 36),
            ("title", "Task", 310),
            ("time", "Window", 175),
            ("dur", "Duration", 88),
            ("apps", "Apps", 240),
            ("conf", "Confidence", 95)
        ]

        self.task_tree = ttk.Treeview(
            self.tab_tasks,
            columns=[c[0] for c in cols],
            show="headings"
        )

        for col, txt, w in cols:
            self.task_tree.heading(col, text=txt)
            self.task_tree.column(col, width=w, minwidth=30)

        sb = ttk.Scrollbar(self.tab_tasks, orient="vertical", command=self.task_tree.yview)
        self.task_tree.configure(yscrollcommand=sb.set)

        sb.pack(side="right", fill="y")
        self.task_tree.pack(fill="both", expand=True, padx=4, pady=4)

        self.task_tree.tag_configure("high", foreground="#22c55e")
        self.task_tree.tag_configure("mid", foreground="#f59e0b")
        self.task_tree.tag_configure("low", foreground="#ef4444")

        self.task_tree.bind("<Double-1>", self._open_card_from_tree)

        tk.Label(
            self.tab_tasks,
            text="💡 Double-click any task to open its detail card",
            bg="#080d18",
            fg="#475569",
            font=("Segoe UI", 9)
        ).pack(pady=4)

    def _build_logs_tab(self):
        cols = [
            ("time", "Time", 148),
            ("app", "App", 155),
            ("title", "Window Title", 690),
            ("dur", "Duration", 78)
        ]

        self.log_tree = ttk.Treeview(
            self.tab_logs,
            columns=[c[0] for c in cols],
            show="headings"
        )

        for col, txt, w in cols:
            self.log_tree.heading(col, text=txt)
            self.log_tree.column(col, width=w, minwidth=40)

        sb = ttk.Scrollbar(self.tab_logs, orient="vertical", command=self.log_tree.yview)
        self.log_tree.configure(yscrollcommand=sb.set)

        sb.pack(side="right", fill="y")
        self.log_tree.pack(fill="both", expand=True, padx=4, pady=4)

    def _build_report_tab(self):
        self.rpt_box = scrolledtext.ScrolledText(
            self.tab_rpt,
            bg="#040810",
            fg="#e2e8f0",
            font=("Consolas", 10),
            wrap="word",
            relief="flat",
            padx=14,
            pady=12,
            insertbackground="white"
        )
        self.rpt_box.pack(fill="both", expand=True, padx=4, pady=4)

    def _toggle_tracking(self):
        self.tracking_on = not self.tracking_on
        self.float_widget.set_tracking(self.tracking_on)

        if self.tracking_on:
            self.tracker.start()
            self.status_lbl.config(text="● Tracking", bg="#14532d")
            self.toggle_btn.config(text="⏸ Pause", bg="#dc2626")
            self.last_auto_gen = 0
        else:
            self.tracker.stop()
            self.status_lbl.config(text="⏸ Paused", bg="#7f1d1d")
            self.toggle_btn.config(text="▶ Resume", bg="#16a34a")
            self._do_generate()

    def _manual_generate(self):
        self._do_generate(show_msg=True)

    def _do_generate(self, show_msg=False):
        self.tracker.flush(force=True)

        acts = self.db.get_today_activities()

        if acts:
            tasks = self.engine.generate_tasks(acts)
            auto_task_keys = set()

            for t in tasks:
                auto_task_keys.add(t["unique_key"])

            existing = self.db.get_today_reports()
            manual_tasks = [dict(r) for r in existing if str(r["title"]).startswith("Manual Task:")]

            self.db.clear_today_reports()

            for t in tasks:
                self.db.upsert_task(t)

            for m in manual_tasks:
                self.db.upsert_task(m)

            self._refresh_all()

            if show_msg:
                messagebox.showinfo(APP_NAME, f"Generated {len(tasks)} automatic task(s).")
        else:
            self._refresh_all()
            if show_msg:
                messagebox.showinfo(APP_NAME, "No activity yet. Start using your PC.")

    def _open_html(self):
        self._do_generate()
        path = self.exporter.export_html()
        webbrowser.open("file://" + path)

    def _clear_today(self):
        if messagebox.askyesno(APP_NAME, "Clear today's logs and reports?"):
            self.db.clear_today_all()
            self.open_card_windows.clear()
            self._refresh_all()

    def _open_all_cards(self):
        reports = self.db.get_today_reports()

        if not reports:
            messagebox.showinfo(APP_NAME, "No tasks yet. Click Generate Now first.")
            return

        for i, r in enumerate(reports):
            key = r["unique_key"]
            if key not in self.open_card_windows or not self.open_card_windows[key].win.winfo_exists():
                self.open_card_windows[key] = TaskCardWindow(self.root, dict(r), i)

    def _open_card_from_tree(self, event):
        sel = self.task_tree.selection()
        if not sel:
            return

        item = self.task_tree.item(sel[0])
        title = item["values"][1]

        reports = self.db.get_today_reports()

        for i, r in enumerate(reports):
            if r["title"] == title:
                key = r["unique_key"]
                if key not in self.open_card_windows or not self.open_card_windows[key].win.winfo_exists():
                    self.open_card_windows[key] = TaskCardWindow(self.root, dict(r), i)
                else:
                    self.open_card_windows[key].win.lift()
                break

    def _refresh_all(self):
        self._load_logs()
        self._load_tasks()
        self._load_report()
        self._draw_dashboard()

    def _load_logs(self):
        for r in self.log_tree.get_children():
            self.log_tree.delete(r)

        for a in self.db.get_today_activities()[-600:]:
            self.log_tree.insert("", "end", values=(
                a["started_at"][11:16] + " – " + a["ended_at"][11:16],
                a["app_name"],
                a["window_title"][:190],
                seconds_to_text(a["duration_seconds"])
            ))

        ch = self.log_tree.get_children()
        if ch:
            self.log_tree.see(ch[-1])

    def _load_tasks(self):
        for r in self.task_tree.get_children():
            self.task_tree.delete(r)

        for r in self.db.get_today_reports():
            conf = int(r["confidence"])
            tag = "high" if conf >= 85 else ("mid" if conf >= 65 else "low")

            title_key = next((t for t in TASK_ICONS if t in r["title"]), None)
            icon = TASK_ICONS.get(title_key, "📌")

            self.task_tree.insert("", "end", tags=(tag,), values=(
                icon,
                r["title"],
                r["started_at"][11:16] + " – " + r["ended_at"][11:16],
                seconds_to_text(r["duration_seconds"]),
                r["apps"][:55],
                f"{conf}%"
            ))

    def _load_report(self):
        reports = self.db.get_today_reports()

        self.rpt_box.config(state="normal")
        self.rpt_box.delete("1.0", tk.END)

        if not reports:
            self.rpt_box.insert(
                tk.END,
                "No tasks yet.\n\nTracking is active — tasks generate every 15 seconds automatically.\nUse the ✚ button in the floating widget to add a manual task."
            )
            self.rpt_box.config(state="disabled")
            return

        for i, r in enumerate(reports, 1):
            title_key = next((t for t in TASK_ICONS if t in r["title"]), None)
            icon = TASK_ICONS.get(title_key, "📌")

            self.rpt_box.insert(tk.END, f"""
{'═' * 76}
{icon} [{i}] {r['title']}
{'═' * 76}
Time      : {r['started_at']} → {r['ended_at']}
Duration  : {seconds_to_text(r['duration_seconds'])}
Apps      : {r['apps']}
Confidence: {r['confidence']}%

Summary:
{r['summary']}

Context:
{r['problem']}

Actions:
{r['actions']}

Result:
{r['result']}

""")

        self.rpt_box.config(state="disabled")
#Mustafa Madeeh
    def _draw_dashboard(self):
        acts = self.db.get_today_activities()
        reports = self.db.get_today_reports()

        total = sum(int(r["duration_seconds"]) for r in reports)

        self.kpi_total.config(text=seconds_to_text(total))
        self.kpi_tasks.config(text=str(len(reports)))
        self.kpi_logs.config(text=str(len(acts)))

        app_time = defaultdict(int)
        for a in acts:
            app_time[a["app_name"]] += int(a["duration_seconds"])

        top = max(app_time.items(), key=lambda x: x[1])[0] if app_time else "—"
        self.kpi_top.config(text=top[:20])

        if reports:
            avg_c = int(sum(int(r["confidence"]) for r in reports) / len(reports))
            self.kpi_conf.config(text=f"{avg_c}%")
        else:
            self.kpi_conf.config(text="—")

        cv = self.canvas
        cv.delete("all")
        w = max(900, cv.winfo_width())

        cv.create_text(
            22,
            22,
            anchor="w",
            fill="#f8fafc",
            font=("Segoe UI", 14, "bold"),
            text="Live Task Timeline"
        )

        if not reports:
            cv.create_text(
                22,
                65,
                anchor="w",
                fill="#334155",
                font=("Segoe UI", 11),
                text="Tracking active — tasks appear automatically every 15 seconds"
            )
            return

        max_dur = max(int(r["duration_seconds"]) for r in reports)
        color_list = ["#3b82f6", "#22c55e", "#a855f7", "#f59e0b", "#ef4444", "#06b6d4", "#f97316", "#14b8a6"]

        y = 50

        for idx, r in enumerate(reports):
            dur = int(r["duration_seconds"])
            bar_w = max(10, int((dur / max_dur) * (w - 430)))
            y += 50
            color = color_list[idx % len(color_list)]

            title_key = next((t for t in TASK_ICONS if t in r["title"]), None)
            icon = TASK_ICONS.get(title_key, "📌")

            cv.create_text(
                22,
                y,
                anchor="w",
                fill=color,
                font=("Segoe UI", 12),
                text=icon
            )

            cv.create_text(
                42,
                y,
                anchor="w",
                fill="#e2e8f0",
                font=("Segoe UI", 10, "bold"),
                text=r["title"][:38]
            )

            cv.create_rectangle(295, y - 10, 295 + bar_w, y + 10, fill=color, outline="")
            cv.create_rectangle(295, y - 10, 295 + bar_w, y + 10, fill="", outline=color, width=1)

            cv.create_text(
                303 + bar_w,
                y,
                anchor="w",
                fill="#94a3b8",
                font=("Segoe UI", 9),
                text=f"{seconds_to_text(dur)}  {r['confidence']}%"
            )

    def _refresh_loop(self):
        if self.tracking_on:
            la = self.tracker.last_app or "—"
            lt = (self.tracker.last_title or "—")[:160]

            self.live_lbl.config(text=f"  ● {la}  |  {lt}", fg="#22c55e")

            if time.time() - self.last_auto_gen >= AUTO_GENERATE_EVERY_SECONDS:
                self._do_generate()
                self.last_auto_gen = time.time()
            else:
                self._refresh_all()
        else:
            self.live_lbl.config(text="  ⏸ Tracking paused", fg="#64748b")
            self._refresh_all()

        self.root.after(2000, self._refresh_loop)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    app = App(root)
    root.deiconify()
    root.mainloop()