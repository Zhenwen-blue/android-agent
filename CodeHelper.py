import customtkinter as ctk
from tkinter import ttk, filedialog, messagebox
import os, shutil, json, re, fnmatch, datetime, threading, queue, paramiko, sys, time
from typing import Dict, Optional, Any

# ================== 配置文件路径 ==================
THEME_CONFIG_FILE = "theme_config.json"
API_CONFIG_FILE = "api_config.json"
SERVER_CONFIG_FILE = "server_config.json"

# ---------- 默认配置（全部占位符，无真实数据） ----------
DEFAULT_API_CONFIG = {
    "configs": [
        {
            "name": "示例配置",
            "api_type": "zhipu",
            "api_key": "your-api-key-here",
            "model": "glm-4",
            "base_url": None,
            "extra_params": {}
        }
    ],
    "active_index": 0
}

DEFAULT_SERVER_CONFIG = {
    "host": "192.168.1.100",
    "port": 22,
    "user": "root",
    "password": "",
    "remote_root": "/home/project"
}

def load_config(file_path: str, default: dict) -> dict:
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return default.copy()

def save_config(file_path: str, config: dict) -> None:
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

# 加载配置（内存中）
api_config_data: dict = load_config(API_CONFIG_FILE, DEFAULT_API_CONFIG)
server_config: dict = load_config(SERVER_CONFIG_FILE, DEFAULT_SERVER_CONFIG)
theme_data: dict = load_config(THEME_CONFIG_FILE, {"theme": "深邃蓝"})
theme_name: str = theme_data.get("theme", "深邃蓝")

# ---------- 多平台客户端工厂 ----------
def create_client(config: dict):
    api_type = config.get("api_type", "zhipu")
    api_key = config.get("api_key", "")
    base_url = config.get("base_url")
    if not api_key or api_key == "your-api-key-here":
        return None
    if api_type == "zhipu":
        from zai import ZhipuAiClient
        return ZhipuAiClient(api_key=api_key, base_url=base_url)
    elif api_type == "openai":
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url)
    elif api_type == "deepseek":
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url or "https://api.deepseek.com")
    else:
        from openai import OpenAI
        return OpenAI(api_key=api_key, base_url=base_url)

active_idx: int = api_config_data.get("active_index", 0)
active_config: dict = api_config_data["configs"][active_idx]
client = create_client(active_config)

VERSIONS_DIR = ".ai_assistant_versions"
META_FILE = "meta.json"

IGNORE_LIST = ['.git', '.gradle', 'build', '__pycache__', '*.iml', '.idea', 'local.properties', VERSIONS_DIR, '.DS_Store']
IGNORE_PATTERNS = shutil.ignore_patterns(*IGNORE_LIST)
IGNORE_DIRS = {'build', '.gradle', '.idea', '.git', '__pycache__', VERSIONS_DIR}
ALLOWED_EXTENSIONS = {'.kt', '.kts', '.java', '.xml', '.gradle', '.properties', '.pro', '.txt', '.json'}

AVAILABLE_THEMES: Dict[str, Dict[str, str]] = {
    "深邃蓝": {
        "appearance_mode": "dark",
        "color_theme": "blue",
        "user_bg": "#1f5382",
        "ai_bg": "#2b2b2b",
        "thinking_fg": "#569cd6",
        "system_fg": "#808080",
        "tree_bg": "#1e1e1e",
        "tree_fg": "#d4d4d4",
        "tree_select": "#0e639c"
    },
    "暗夜绿": {
        "appearance_mode": "dark",
        "color_theme": "green",
        "user_bg": "#0e4a2e",
        "ai_bg": "#1e1e1e",
        "thinking_fg": "#4ec9b0",
        "system_fg": "#6a6a6a",
        "tree_bg": "#121212",
        "tree_fg": "#9cdcfe",
        "tree_select": "#1a6b4b"
    },
    "典雅紫": {
        "appearance_mode": "dark",
        "color_theme": "purple",
        "user_bg": "#3a1f6e",
        "ai_bg": "#252526",
        "thinking_fg": "#c586c0",
        "system_fg": "#808080",
        "tree_bg": "#1b1a2a",
        "tree_fg": "#d4d4d4",
        "tree_select": "#5a3e9c"
    },
    "暗橙": {
        "appearance_mode": "dark",
        "color_theme": "orange",
        "user_bg": "#8b3a0a",
        "ai_bg": "#1e1e1e",
        "thinking_fg": "#d7ba7d",
        "system_fg": "#6e6e6e",
        "tree_bg": "#1c1c1c",
        "tree_fg": "#d4d4d4",
        "tree_select": "#b85c1e"
    },
    "浅色蓝": {
        "appearance_mode": "light",
        "color_theme": "blue",
        "user_bg": "#d0e6ff",
        "ai_bg": "#f0f0f0",
        "thinking_fg": "#0451a5",
        "system_fg": "#555555",
        "tree_bg": "#ffffff",
        "tree_fg": "#000000",
        "tree_select": "#007acc"
    },
    "浅色绿": {
        "appearance_mode": "light",
        "color_theme": "green",
        "user_bg": "#d5f5e3",
        "ai_bg": "#f4f4f4",
        "thinking_fg": "#1b7a3d",
        "system_fg": "#606060",
        "tree_bg": "#fcfcfc",
        "tree_fg": "#1a1a1a",
        "tree_select": "#2e8b57"
    }
}

DEEP_THINKING_DEFAULTS = {
    "zhipu": {"thinking": {"type": "enabled"}},
    "deepseek": {"thinking": {"type": "enabled"}},
    "openai": {},
    "custom": {}
}

def ensure_dir(path: str) -> None:
    if not os.path.exists(path):
        os.makedirs(path)

class AndroidAIAssistant(ctk.CTk):
    def __init__(self, startup_theme: Optional[str] = None):
        super().__init__()
        if startup_theme is None:
            startup_theme = theme_name
        self.current_theme_name: str = startup_theme
        self.theme_config: Dict[str, str] = AVAILABLE_THEMES.get(startup_theme, AVAILABLE_THEMES["深邃蓝"])
        self.apply_theme(startup_theme)

        self.default_width = 1400
        self.default_height = 750
        self.center_window_on_screen()
        self.title("Android AI 开发助手")
        self.minsize(1100, 650)

        self.project_path: Optional[str] = None
        self.current_version = 0
        self.versions_meta = {}
        self.msg_queue = queue.Queue()
        self.is_streaming = False
        self.package_name: Optional[str] = None
        self.last_usage = None
        self.current_extracted_files = {}

        self.api_config_data = api_config_data
        self.active_api_index = self.api_config_data.get("active_index", 0)
        self.api_config_list = self.api_config_data.get("configs", [])
        self.server_config = server_config
        self.client = client

        self.ssh_client = None
        self.ssh_channel = None
        self.terminal_thread = None
        self.terminal_running = False
        self.terminal_interacted = False
        self.connecting_flag = False
        self.pending_commands = queue.Queue()

        self.command_running = False
        self.command_history = []
        self.history_index = -1

        self.api_list_buttons = []
        self.api_list_buttons_parent = None
        self.api_selected_index = -1

        self.running = True
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        self.setup_ui()
        self.after(50, self.process_queue)

    def on_closing(self):
        self.running = False
        self.disconnect_ssh_terminal()
        self.destroy()

    def apply_theme(self, theme_name: str):
        self.theme_config = AVAILABLE_THEMES.get(theme_name, AVAILABLE_THEMES["深邃蓝"])
        ctk.set_appearance_mode(self.theme_config["appearance_mode"])
        ctk.set_default_color_theme(self.theme_config["color_theme"])
        self.appearance_mode = self.theme_config["appearance_mode"]

    def center_window_on_screen(self):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w = min(self.default_width, int(sw * 0.9))
        h = min(self.default_height, int(sh * 0.85))
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def center_toplevel(self, dialog, w, h):
        dialog.update_idletasks()
        sw = dialog.winfo_screenwidth()
        sh = dialog.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        dialog.geometry(f"{w}x{h}+{x}+{y}")

    # ---------- UI 构建 ----------
    def setup_ui(self):
        toolbar = ctk.CTkFrame(self, corner_radius=12, fg_color=("gray90", "gray17"))
        toolbar.pack(fill="x", padx=12, pady=(12, 0))

        path_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        path_frame.pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkLabel(path_frame, text="📁 项目路径:", font=("Segoe UI", 12, "bold")).pack(side="left", padx=(5, 2))
        self.path_entry = ctk.CTkEntry(path_frame, height=32, font=("Consolas", 12), placeholder_text="点击右侧按钮选择项目...")
        self.path_entry.pack(side="left", fill="x", expand=True, padx=2, pady=5)
        self.path_entry.bind("<Return>", lambda e: self.load_project_from_entry())

        btn_frame = ctk.CTkFrame(toolbar, fg_color="transparent")
        btn_frame.pack(side="right", padx=5)
        ctk.CTkButton(btn_frame, text="📂 选择项目", width=110, command=self.select_and_load_project, font=("Segoe UI", 12), corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="🕒 版本历史", width=110, command=self.show_version_history, font=("Segoe UI", 12), corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(btn_frame, text="⚙️ 设置", width=80, command=self.open_settings, font=("Segoe UI", 12), corner_radius=8).pack(side="left", padx=2)

        self.include_context_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(toolbar, text="自动附加项目文件", variable=self.include_context_var, font=("Segoe UI", 12), corner_radius=6).pack(side="right", padx=8)
        self.token_label = ctk.CTkLabel(toolbar, text="🔢 Token: 0", font=("Segoe UI", 12), width=120)
        self.token_label.pack(side="right", padx=8)

        main = ctk.CTkFrame(self, corner_radius=12)
        main.pack(fill="both", expand=True, padx=12, pady=10)

        self.left_panel = ctk.CTkFrame(main, width=240, corner_radius=12, fg_color=("gray95", "gray13"))
        self.left_panel.pack(side="left", fill="y", padx=(0, 6))
        self.left_panel.pack_propagate(False)
        ctk.CTkLabel(self.left_panel, text="📂 项目文件", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 4))
        tc = ctk.CTkFrame(self.left_panel, corner_radius=8, fg_color=("gray90", "gray17"))
        tc.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.style_file_tree()
        self.file_tree = ttk.Treeview(tc, show='tree', selectmode='browse')
        self.file_tree.pack(side="left", fill="both", expand=True)
        ctk.CTkScrollbar(tc, command=self.file_tree.yview).pack(side="right", fill="y")
        ctk.CTkScrollbar(self.left_panel, orientation="horizontal", command=self.file_tree.xview).pack(side="bottom", fill="x", padx=10, pady=(0, 8))
        self.file_tree.configure(yscrollcommand=tc.winfo_children()[1].set, xscrollcommand=self.left_panel.winfo_children()[-1].set)

        cp = ctk.CTkFrame(main, corner_radius=12)
        cp.pack(side="left", fill="both", expand=True, padx=(6, 6))
        self.chat_frame = ctk.CTkFrame(cp, corner_radius=12, fg_color=("gray95", "gray13"))
        self.chat_frame.pack(fill="both", expand=True, pady=(0, 6))
        ctk.CTkLabel(self.chat_frame, text="💬 对话历史", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=15, pady=(12, 6))
        self.chat_area = ctk.CTkTextbox(self.chat_frame, wrap="word", font=("Segoe UI", 12), corner_radius=8)
        self.chat_area.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.chat_area.configure(state="disabled")
        self.setup_chat_tags()

        bf = ctk.CTkFrame(cp, corner_radius=12, fg_color=("gray90", "gray17"))
        bf.pack(fill="x", side="bottom", pady=(6, 0))
        self.input_text = ctk.CTkTextbox(bf, height=65, font=("Segoe UI", 12), corner_radius=8)
        self.input_text.pack(side="left", fill="x", expand=True, padx=10, pady=10)
        self.input_text.bind("<Return>", self.on_input_return)
        self.input_text.bind("<Shift-Return>", self.on_input_shift_return)
        bb = ctk.CTkFrame(bf, fg_color="transparent")
        bb.pack(side="right", padx=10, pady=10)
        ctk.CTkButton(bb, text="发送", width=70, command=self.send_message, font=("Segoe UI", 12, "bold"), corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(bb, text="部署后端", width=90, command=self.deploy_to_server, font=("Segoe UI", 12), corner_radius=8).pack(side="left", padx=2)
        ctk.CTkButton(bb, text="清除对话", width=90, command=self.confirm_clear_chat, font=("Segoe UI", 12), corner_radius=8).pack(side="left", padx=2)

        self.right_panel = ctk.CTkFrame(main, width=300, corner_radius=12, fg_color=("gray95", "gray13"))
        self.right_panel.pack(side="right", fill="y", padx=(6, 0))
        self.right_panel.pack_propagate(False)
        ctk.CTkLabel(self.right_panel, text="🖥️ SSH 终端", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=15, pady=(12, 6))
        self.terminal_output = ctk.CTkTextbox(self.right_panel, wrap="word", font=("Consolas", 12, "bold"), corner_radius=8)
        self.terminal_output.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        if self.appearance_mode == "dark": out_fg = "white"
        else: out_fg = "black"
        self.terminal_output._textbox.tag_configure("output", foreground=out_fg, font=("Consolas", 12, "bold"))
        self.terminal_output._textbox.tag_configure("error", foreground="red", font=("Consolas", 12, "bold"))
        self.terminal_output._textbox.tag_configure("system_msg", foreground="gray", font=("Consolas", 12, "bold"))

        cmd_frame = ctk.CTkFrame(self.right_panel, fg_color="transparent")
        cmd_frame.pack(fill="x", padx=12, pady=(0, 8))
        self.cmd_entry = ctk.CTkEntry(cmd_frame, height=28, font=("Consolas", 12), placeholder_text="输入命令...")
        self.cmd_entry.pack(side="left", fill="x", expand=True, padx=(0, 4))
        self.cmd_entry.bind("<Return>", lambda e: self.execute_ssh_command_input())
        self.cmd_entry.bind("<Prior>", self.on_page_up)
        self.cmd_entry.bind("<Next>", self.on_page_down)
        ctk.CTkButton(cmd_frame, text="执行", width=50, command=self.execute_ssh_command_input, font=("Segoe UI", 12), corner_radius=8).pack(side="right", padx=2)
        ctk.CTkButton(cmd_frame, text="Ctrl+C", width=50, command=self.send_ctrl_c, font=("Segoe UI", 12), corner_radius=8).pack(side="right", padx=2)
        self.update_terminal_status()

        self.status = ctk.CTkLabel(self, text="✅ 就绪", anchor="w", corner_radius=8, fg_color=("gray85", "gray20"), padx=15, pady=5, font=("Segoe UI", 12))
        self.status.pack(fill="x", padx=12, pady=(0, 8))

    def style_file_tree(self):
        cfg = self.theme_config
        st = ttk.Style()
        st.theme_use('clam')
        st.configure("Treeview", background=cfg["tree_bg"], foreground=cfg["tree_fg"],
                     fieldbackground=cfg["tree_bg"], borderwidth=0, font=("Segoe UI", 13))
        st.configure("Treeview.Heading", background=cfg["tree_bg"], foreground=cfg["tree_fg"],
                     borderwidth=0, font=("Segoe UI", 13, "bold"))
        st.map("Treeview", background=[("selected", cfg["tree_select"])])

    def setup_chat_tags(self):
        cfg = self.theme_config
        u_fg = "white" if cfg["appearance_mode"] == "dark" else "black"
        a_fg = "white" if cfg["appearance_mode"] == "dark" else "black"
        self.chat_area._textbox.tag_configure("user", foreground=u_fg, background=cfg["user_bg"],
                                              font=("Segoe UI", 12), lmargin1=10, lmargin2=10, rmargin=10, spacing1=5, spacing3=5)
        self.chat_area._textbox.tag_configure("ai", foreground=a_fg, background=cfg["ai_bg"],
                                              font=("Segoe UI", 12), lmargin1=10, lmargin2=10, rmargin=10, spacing1=5, spacing3=5)
        self.chat_area._textbox.tag_configure("thinking", foreground=cfg["thinking_fg"], font=("Segoe UI", 12))
        self.chat_area._textbox.tag_configure("system", foreground=cfg["system_fg"], font=("Segoe UI", 12, "italic"))
        self.chat_area._textbox.tag_configure("bold", font=("Segoe UI", 12, "bold"))

    def on_input_return(self, ev): self.send_message(); return "break"
    def on_input_shift_return(self, ev): self.input_text.insert("insert", "\n")

    # ---------- 项目加载 ----------
    def select_and_load_project(self):
        path = filedialog.askdirectory(title="选择Android项目根目录")
        if path:
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, path)
            self.load_project(path)

    def load_project_from_entry(self):
        path = self.path_entry.get().strip()
        if path:
            self.load_project(path)

    def load_project(self, path=None):
        if not path:
            path = self.path_entry.get().strip()
        if not path or not os.path.isdir(path):
            return
        self.project_path = path
        self.package_name = self.detect_package_name()
        self.status.configure(text=f"📌 项目: {path}  |  📦 包名: {self.package_name or '未知'}")
        self.init_version_control()
        self.refresh_file_tree()
        self.update_status_version()
        self.display_system_message(f"✅ 项目已加载: {path}\n检测到包名: {self.package_name or '未检测到'}")

    def detect_package_name(self):
        if not self.project_path:
            return None
        for f in ['app/build.gradle', 'app/build.gradle.kts']:
            fp = os.path.join(self.project_path, f)
            if os.path.exists(fp):
                try:
                    with open(fp, 'r', encoding='utf-8') as f:
                        c = f.read()
                    m = re.search(r'namespace\s*[= ]\s*["\']([^"\']+)["\']', c)
                    if m: return m.group(1)
                    m = re.search(r'applicationId\s*["\']([^"\']+)["\']', c)
                    if m: return m.group(1)
                except:
                    pass
        mp = os.path.join(self.project_path, 'app/src/main/AndroidManifest.xml')
        if os.path.exists(mp):
            try:
                with open(mp, 'r', encoding='utf-8') as f:
                    c = f.read()
                m = re.search(r'package\s*=\s*["\']([^"\']+)["\']', c)
                if m: return m.group(1)
            except:
                pass
        return None

    def refresh_file_tree(self):
        for i in self.file_tree.get_children():
            self.file_tree.delete(i)
        if not self.project_path:
            return
        root = self.file_tree.insert("", "end", text=os.path.basename(self.project_path), open=True)
        self._scan_dir(self.project_path, root)

    def _scan_dir(self, path, parent):
        try:
            for e in os.listdir(path):
                full = os.path.join(path, e)
                if e.startswith('.') and e != '.gitignore':
                    continue
                if e in IGNORE_DIRS:
                    continue
                if os.path.isdir(full):
                    node = self.file_tree.insert(parent, "end", text=e, open=False)
                    self._scan_dir(full, node)
                else:
                    self.file_tree.insert(parent, "end", text=e, open=False)
        except PermissionError:
            pass

    def collect_project_info(self):
        if not self.project_path:
            return "项目未加载。"
        lines = ["以下是当前Android项目的完整文件结构和所有文件内容：\n"]
        for root, dirs, files in os.walk(self.project_path):
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith('.')]
            for f in files:
                if f.startswith('.') and f != '.gitignore':
                    continue
                ext = os.path.splitext(f)[1].lower()
                if ext not in ALLOWED_EXTENSIONS:
                    continue
                fp = os.path.join(root, f)
                rp = os.path.relpath(fp, self.project_path)
                try:
                    with open(fp, 'r', encoding='utf-8', errors='ignore') as ff:
                        c = ff.read()
                    if len(c) > 100000:
                        lines.append(f"--- 文件: {rp} (内容过长，省略) ---\n")
                    else:
                        lines.append(f"--- 文件: {rp} ---\n" + c + "\n")
                except Exception as e:
                    lines.append(f"--- 文件: {rp} (读取错误: {e}) ---\n")
        return "\n".join(lines)

    # ---------- 版本控制 ----------
    def init_version_control(self):
        if not self.project_path:
            return
        vdir = os.path.join(self.project_path, VERSIONS_DIR)
        ensure_dir(vdir)
        mp = os.path.join(vdir, META_FILE)
        if os.path.exists(mp):
            with open(mp, 'r', encoding='utf-8') as f:
                self.versions_meta = json.load(f)
            self.current_version = self.versions_meta.get("current_version", 0)
        else:
            self.versions_meta = {"current_version": 0, "versions": []}
            self.current_version = 0
            self._save_meta()

    def _save_meta(self):
        if not self.project_path:
            return
        mp = os.path.join(self.project_path, VERSIONS_DIR, META_FILE)
        with open(mp, 'w', encoding='utf-8') as f:
            json.dump(self.versions_meta, f, indent=2, ensure_ascii=False)

    def update_status_version(self):
        self.status.configure(text=f"📌 当前版本: {self.current_version}  |  项目: {self.project_path}")

    def save_version(self, description=""):
        if not self.project_path:
            return
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        vname = f"v{self.current_version}_{ts}"
        vdir = os.path.join(self.project_path, VERSIONS_DIR, vname)
        ensure_dir(vdir)
        try:
            shutil.copytree(self.project_path, vdir, ignore=IGNORE_PATTERNS, dirs_exist_ok=True)
        except Exception as e:
            messagebox.showerror("备份失败", str(e))
            return
        self.current_version += 1
        self.versions_meta["current_version"] = self.current_version
        self.versions_meta.setdefault("versions", []).append({
            "name": vname, "timestamp": ts, "description": description, "directory": vdir
        })
        self._save_meta()
        self.update_status_version()
        self.display_system_message(f"💾 版本已保存: {vname}")

    def rollback_to_version(self, vname):
        if not self.project_path:
            return
        self.save_version("回退前的自动保存")
        vdir = os.path.join(self.project_path, VERSIONS_DIR, vname)
        if not os.path.exists(vdir):
            messagebox.showerror("错误", "版本目录不存在")
            return
        if not messagebox.askyesno("确认", f"确定回退到 {vname} ？"):
            return
        for item in os.listdir(self.project_path):
            if item == VERSIONS_DIR:
                continue
            if any(fnmatch.fnmatch(item, p) for p in IGNORE_LIST):
                continue
            ip = os.path.join(self.project_path, item)
            try:
                if os.path.isfile(ip) or os.path.islink(ip):
                    os.unlink(ip)
                elif os.path.isdir(ip):
                    shutil.rmtree(ip)
            except Exception as e:
                print(f"删除失败: {ip}, {e}")
        for item in os.listdir(vdir):
            src = os.path.join(vdir, item)
            dst = os.path.join(self.project_path, item)
            if os.path.isdir(src):
                shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
            else:
                shutil.copy2(src, dst)
        self.refresh_file_tree()
        self.display_system_message(f"⏪ 已回退到版本: {vname}")
        self.save_version("回退后状态")

    def show_version_history(self):
        if not self.project_path:
            messagebox.showwarning("提示", "请先加载项目")
            return
        win = ctk.CTkToplevel(self)
        win.title("版本历史")
        w, h = 700, 450
        self.center_toplevel(win, w, h)
        win.transient(self)
        win.grab_set()
        fr = ctk.CTkFrame(win, corner_radius=8)
        fr.pack(fill="both", expand=True, padx=10, pady=10)
        cols = ("timestamp", "desc")
        tv = ttk.Treeview(fr, columns=cols, show='headings', selectmode='browse')
        tv.heading("#0", text="版本")
        tv.heading("timestamp", text="时间")
        tv.heading("desc", text="描述")
        tv.column("#0", width=180)
        tv.column("timestamp", width=160)
        tv.column("desc", width=260)
        tv.pack(fill="both", expand=True, side="left")
        sb = ctk.CTkScrollbar(fr, command=tv.yview)
        sb.pack(side="right", fill="y")
        tv.configure(yscrollcommand=sb.set)
        for v in reversed(self.versions_meta.get("versions", [])):
            try:
                dt = datetime.datetime.strptime(v["timestamp"], "%Y%m%d_%H%M%S")
                tstr = dt.strftime("%Y-%m-%d %H:%M")
            except:
                tstr = v["timestamp"]
            tv.insert("", "end", text=v["name"], values=(tstr, v.get("description", "")))
        def rollback():
            sel = tv.selection()
            if sel:
                vn = tv.item(sel[0], "text")
                win.destroy()
                self.rollback_to_version(vn)
        bfr = ctk.CTkFrame(win, corner_radius=0, fg_color="transparent")
        bfr.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(bfr, text="回退到此版本", command=rollback, font=("Segoe UI", 12)).pack(side="right", padx=5)
        ctk.CTkButton(bfr, text="关闭", command=win.destroy, font=("Segoe UI", 12)).pack(side="right", padx=5)

    # ---------- 设置页面 ----------
    def open_settings(self, active_tab="API管理"):
        win = ctk.CTkToplevel(self)
        win.title("设置")
        w, h = 720, 720
        self.center_toplevel(win, w, h)
        win.transient(self)
        win.grab_set()
        tv = ctk.CTkTabview(win, corner_radius=10)
        tv.pack(fill="both", expand=True, padx=10, pady=10)
        tab_api = tv.add("API管理")
        tab_server = tv.add("服务器配置")
        tab_theme = tv.add("主题选择")
        tab_help = tv.add("使用说明")
        tv.set(active_tab)

        # ---------- API 管理 ----------
        frame_api = ctk.CTkFrame(tab_api, fg_color="transparent")
        frame_api.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(frame_api, text="当前激活的 API 配置", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        self.active_label = ctk.CTkLabel(frame_api, text="", font=("Segoe UI", 12), fg_color=("gray85", "gray20"), corner_radius=6, padx=10)
        self.active_label.pack(fill="x", pady=5)

        list_container = ctk.CTkScrollableFrame(frame_api, label_text="API 配置列表", height=180)
        list_container.pack(fill="both", expand=True, pady=5)
        self.api_list_buttons_parent = list_container

        btn_row = ctk.CTkFrame(frame_api, fg_color="transparent")
        btn_row.pack(side="bottom", fill="x", pady=5)
        ctk.CTkButton(btn_row, text="添加配置", command=lambda: self.add_or_edit_api(win, None)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="编辑", command=lambda: self.edit_api(win)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="删除", command=lambda: self.delete_api(win)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="设为激活", command=lambda: self.activate_api(win)).pack(side="left", padx=2)
        ctk.CTkButton(btn_row, text="测试配置", command=self.test_current_api, font=("Segoe UI", 12)).pack(side="right", padx=2)

        self.refresh_api_list()

        # ---------- 服务器配置 ----------
        sv = ctk.CTkScrollableFrame(tab_server, label_text="服务器连接信息")
        sv.pack(fill="both", expand=True, padx=10, pady=10)
        fields = [
            ("主机地址", self.server_config.get("host", "")),
            ("端口", str(self.server_config.get("port", 22))),
            ("用户名", self.server_config.get("user", "")),
            ("密码", self.server_config.get("password", "")),
        ]
        self.server_entries = {}
        for label, val in fields:
            ctk.CTkLabel(sv, text=label, font=("Segoe UI", 12)).pack(anchor="w", pady=(8, 2))
            entry = ctk.CTkEntry(sv, justify='center')
            entry.insert(0, val)
            if "密码" in label:
                entry.configure(show="*")
            entry.pack(fill="x", padx=10)
            self.server_entries[label] = entry
        ctk.CTkLabel(sv, text="远程项目根目录", font=("Segoe UI", 12)).pack(anchor="w", pady=(8, 2))
        self.remote_root_entry = ctk.CTkEntry(sv)
        self.remote_root_entry.insert(0, self.server_config.get("remote_root", ""))
        self.remote_root_entry.pack(fill="x", padx=10)

        server_btn_frame = ctk.CTkFrame(sv, fg_color="transparent")
        server_btn_frame.pack(fill="x", pady=10)
        ctk.CTkButton(server_btn_frame, text="测试连接", command=self.test_server_connection, font=("Segoe UI", 12)).pack(side="left", padx=5)
        ctk.CTkButton(server_btn_frame, text="保存配置", command=self.save_server_config, font=("Segoe UI", 12)).pack(side="right", padx=5)

        self.server_test_result = ctk.CTkLabel(sv, text="", font=("Segoe UI", 11))
        self.server_test_result.pack(anchor="w", pady=5, padx=10)

        # ---------- 主题 ----------
        ctk.CTkLabel(tab_theme, text="选择主题（切换后需重启生效）", font=("Segoe UI", 13)).pack(pady=15, padx=10)
        tv_theme = ctk.StringVar(value=self.current_theme_name)
        ctk.CTkOptionMenu(tab_theme, values=list(AVAILABLE_THEMES.keys()), variable=tv_theme, font=("Segoe UI", 12)).pack(padx=10, pady=5)
        def apply_t():
            nt = tv_theme.get()
            save_config(THEME_CONFIG_FILE, {"theme": nt})
            if messagebox.askyesno("主题", f"主题“{nt}”已保存。是否立即重启？"):
                self.restart_app(nt)
        ctk.CTkButton(tab_theme, text="应用主题", command=apply_t).pack(pady=15)

        # ---------- 使用说明 ----------
        help_text = """
【Android AI 开发助手 — 使用说明】

📌 1. 加载项目
    - 点击“选择项目”按钮，选择您的 Android 项目根目录（包含 app/ 等文件夹）。
    - 工具会自动检测包名并在界面显示。

💬 2. AI 对话
    - 在下方输入框输入需求，点击“发送”或按 Ctrl+Enter。
    - 勾选“自动附加项目文件”会让 AI 读取项目所有代码文件作为上下文（大型项目可能消耗较多 Token）。
    - AI 回复会包含“思考”过程和最终答案。如果 AI 提供了代码块，工具会自动提取并应用到项目中。

📂 3. 代码应用与版本控制
    - AI 回复中的代码块必须包含文件路径注释（如 // file: app/src/main/java/.../Main.kt）。
    - 工具会解析这些注释，将代码写入对应的文件（若文件已存在则覆盖）。
    - 每次应用前会自动保存一个版本（存储在项目根目录下的 .ai_assistant_versions/ 中）。
    - 点击“版本历史”可查看所有版本，选择任一版本可回退到该状态。

☁️ 4. 后端部署
    - 当 AI 生成 backend/ 目录下的 Python 文件（如 backend/main.py）时，点击“部署后端”可将这些文件上传到远程服务器。
    - 部署前需在“设置 > 服务器配置”中填写 SSH 连接信息并保存。
    - 部署时会自动根据当前 Android 项目的包名在远程根目录下创建子目录，将 backend/ 文件放入其中。

🖥️ 5. SSH 终端
    - 右侧面板提供交互式终端，可执行任意命令（如 adb、git 等）。
    - 输入命令后点击“执行”或按 Enter，工具会自动连接服务器（首次执行时）。
    - 连接过程在后台进行，不会阻塞界面；若命令执行过程中可按“Ctrl+C”中断。
    - 支持命令历史（↑/↓键翻页）。

⚙️ 6. 设置
    - API 管理：可配置多个 AI 服务商（智谱、OpenAI、DeepSeek 等），自由切换，并可测试连接。
    - 服务器配置：填写 SSH 主机、端口、用户名、密码及远程根目录。
    - 主题选择：内置多种深色/浅色主题，切换后需重启应用生效。

💡 注意事项
    - 请确保 API Key 有效，否则 AI 功能不可用。
    - 项目版本备份会占用磁盘空间，请定期清理不需要的版本（手动删除 .ai_assistant_versions/ 下的文件夹）。
    - SSH 终端使用 paramiko，若连接失败请检查网络和防火墙设置。

如有任何问题，欢迎反馈！
作者联系方式
QQ:1371918568 微信:qian08zg
"""
        help_box = ctk.CTkTextbox(tab_help, wrap="word", font=("Segoe UI", 12), corner_radius=8)
        help_box.pack(fill="both", expand=True, padx=15, pady=15)
        help_box.insert("1.0", help_text)
        help_box.configure(state="disabled")

    # ---------- API 列表操作 ----------
    def refresh_api_list(self):
        if not self.api_list_buttons_parent:
            return
        for btn in self.api_list_buttons:
            btn.destroy()
        self.api_list_buttons.clear()
        self.api_selected_index = -1
        active_idx = self.api_config_data.get("active_index", 0)
        configs = self.api_config_data.get("configs", [])
        for i, config in enumerate(configs):
            text = f"{config.get('name', '未命名')} ({config.get('model','')}) [{config.get('api_type','')}]"
            btn = ctk.CTkButton(master=self.api_list_buttons_parent, text=text,
                                anchor="w", font=("Segoe UI", 12), corner_radius=6,
                                fg_color=("gray80", "gray25"),
                                hover_color=("gray70", "gray35"),
                                command=lambda idx=i: self.select_api_item(idx))
            btn.pack(fill="x", padx=5, pady=2)
            self.api_list_buttons.append(btn)
        self.api_selected_index = active_idx
        self._update_api_buttons_highlight()
        self._update_active_label()

    def select_api_item(self, idx: int):
        self.api_selected_index = idx
        self._update_api_buttons_highlight()

    def _update_api_buttons_highlight(self):
        active_idx = self.api_config_data.get("active_index", 0)
        selected_idx = self.api_selected_index
        for i, btn in enumerate(self.api_list_buttons):
            if i == selected_idx:
                btn.configure(fg_color=("#3a7ebf", "#1f5382"))
            elif i == active_idx and i != selected_idx:
                btn.configure(fg_color=("#4a8ed6", "#2a5a8c"))
            else:
                btn.configure(fg_color=("gray80", "gray25"))

    def _update_active_label(self):
        active_idx = self.api_config_data.get("active_index", 0)
        configs = self.api_config_data.get("configs", [])
        if 0 <= active_idx < len(configs):
            cfg = configs[active_idx]
            self.active_label.configure(text=f"✅ {cfg.get('name','')} — {cfg.get('model','')} (类型: {cfg.get('api_type','')})")
        else:
            self.active_label.configure(text="无激活配置")

    def add_or_edit_api(self, win, index=None):
        dialog = ctk.CTkToplevel(win)
        dialog.title("编辑 API 配置" if index is not None else "新建 API 配置")
        w, h = 480, 580
        self.center_toplevel(dialog, w, h)
        dialog.transient(win)
        dialog.grab_set()
        configs = self.api_config_data["configs"]
        current = configs[index] if index is not None and 0 <= index < len(configs) else {
            "name": "", "api_type": "zhipu", "api_key": "", "model": "", "base_url": "", "extra_params": {}
        }

        ctk.CTkLabel(dialog, text="名称", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        name_entry = ctk.CTkEntry(dialog); name_entry.insert(0, current.get("name","")); name_entry.pack(fill="x", padx=15)

        ctk.CTkLabel(dialog, text="API 类型", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        type_var = ctk.StringVar(value=current.get("api_type","zhipu"))
        type_menu = ctk.CTkOptionMenu(dialog, values=["zhipu", "openai", "deepseek", "custom"], variable=type_var)
        type_menu.pack(fill="x", padx=15)

        ctk.CTkLabel(dialog, text="API Key", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        key_entry = ctk.CTkEntry(dialog, show="*"); key_entry.insert(0, current.get("api_key","")); key_entry.pack(fill="x", padx=15)

        ctk.CTkLabel(dialog, text="模型", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        model_entry = ctk.CTkEntry(dialog); model_entry.insert(0, current.get("model","")); model_entry.pack(fill="x", padx=15)

        ctk.CTkLabel(dialog, text="Base URL (可选)", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        url_entry = ctk.CTkEntry(dialog); url_entry.insert(0, current.get("base_url","") or ""); url_entry.pack(fill="x", padx=15)

        ctk.CTkLabel(dialog, text="额外参数 (JSON, 可选)", font=("Segoe UI", 12)).pack(anchor="w", padx=15, pady=(10,2))
        extra_text = ctk.CTkTextbox(dialog, height=80, font=("Consolas", 11))
        if index is None and not current.get("extra_params"):
            api_type = current.get("api_type", "zhipu")
            default_extra = DEEP_THINKING_DEFAULTS.get(api_type, {})
            extra_text.insert("1.0", json.dumps(default_extra, indent=2, ensure_ascii=False))
        else:
            extra_text.insert("1.0", json.dumps(current.get("extra_params", {}), indent=2, ensure_ascii=False))
        extra_text.pack(fill="x", padx=15)

        def on_type_change(choice):
            try:
                current_extra = json.loads(extra_text.get("1.0", "end").strip())
            except:
                current_extra = {}
            if current_extra == {} or current_extra == DEEP_THINKING_DEFAULTS.get(current.get("api_type"), {}):
                default_extra = DEEP_THINKING_DEFAULTS.get(choice, {})
                extra_text.delete("1.0", "end")
                extra_text.insert("1.0", json.dumps(default_extra, indent=2, ensure_ascii=False))
        type_var.trace_add("write", lambda *args: on_type_change(type_var.get()))

        test_result_label = ctk.CTkLabel(dialog, text="", font=("Segoe UI", 11))
        test_result_label.pack(pady=5)

        def test_api_connection():
            api_type = type_var.get()
            api_key = key_entry.get().strip()
            model = model_entry.get().strip()
            base_url = url_entry.get().strip() or None
            if not api_key or not model:
                test_result_label.configure(text="请填写 API Key 和模型", text_color="red")
                return
            try:
                extra = json.loads(extra_text.get("1.0", "end").strip())
            except:
                extra = {}
            test_result_label.configure(text="⏳ 测试中...", text_color="gray")
            def do_test():
                try:
                    tmp_config = {
                        "api_type": api_type,
                        "api_key": api_key,
                        "model": model,
                        "base_url": base_url,
                        "extra_params": extra
                    }
                    tmp_client = create_client(tmp_config)
                    if tmp_client is None:
                        raise Exception("API Key 无效")
                    kwargs = {"model": model, "messages": [{"role":"user","content":"ping"}], "max_tokens": 5}
                    kwargs.update(extra)
                    tmp_client.chat.completions.create(**kwargs)
                    self.after(0, lambda: test_result_label.configure(text="✅ 连接成功！", text_color="green"))
                except Exception as e:
                    self.after(0, lambda: test_result_label.configure(text=f"❌ 失败：{str(e)}", text_color="red"))
            threading.Thread(target=do_test, daemon=True).start()

        def save():
            name = name_entry.get().strip()
            api_type = type_var.get()
            api_key = key_entry.get().strip()
            model = model_entry.get().strip()
            base_url = url_entry.get().strip() or None
            try:
                extra = json.loads(extra_text.get("1.0", "end").strip())
            except:
                messagebox.showwarning("错误", "额外参数 JSON 格式错误")
                return
            if not name or not api_key or not model:
                messagebox.showwarning("提示", "名称、API Key、模型不能为空")
                return
            new_config = {
                "name": name,
                "api_type": api_type,
                "api_key": api_key,
                "model": model,
                "base_url": base_url,
                "extra_params": extra
            }
            if index is not None:
                configs[index] = new_config
            else:
                configs.append(new_config)
                self.api_config_data["active_index"] = len(configs) - 1
            self.save_api_config()
            dialog.destroy()
            self.refresh_api_list()
            self.reload_client()

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(side="bottom", fill="x", padx=15, pady=10)
        ctk.CTkButton(btn_frame, text="测试连接", command=test_api_connection, font=("Segoe UI", 12)).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="保存", command=save, font=("Segoe UI", 12)).pack(side="right", padx=5)

    def edit_api(self, win):
        if self.api_selected_index == -1:
            messagebox.showwarning("提示", "请先选择一个配置")
            return
        self.add_or_edit_api(win, index=self.api_selected_index)

    def delete_api(self, win):
        if self.api_selected_index == -1:
            messagebox.showwarning("提示", "请先选择一个配置")
            return
        if len(self.api_config_data["configs"]) <= 1:
            messagebox.showwarning("提示", "至少保留一个配置")
            return
        del self.api_config_data["configs"][self.api_selected_index]
        if self.api_config_data["active_index"] >= len(self.api_config_data["configs"]):
            self.api_config_data["active_index"] = 0
        self.save_api_config()
        self.refresh_api_list()
        self.reload_client()

    def activate_api(self, win):
        if self.api_selected_index == -1:
            messagebox.showwarning("提示", "请先选择一个配置")
            return
        self.api_config_data["active_index"] = self.api_selected_index
        self.save_api_config()
        self.api_selected_index = self.api_config_data["active_index"]
        self.refresh_api_list()
        self.reload_client()
        messagebox.showinfo("成功", f"已激活 {self.api_config_data['configs'][self.api_selected_index]['name']}")

    def save_api_config(self):
        save_config(API_CONFIG_FILE, self.api_config_data)

    def reload_client(self):
        global client
        idx = self.api_config_data["active_index"]
        config = self.api_config_data["configs"][idx]
        self.client = create_client(config)
        client = self.client

    def test_current_api(self):
        if self.client is None:
            messagebox.showwarning("提示", "当前未配置有效的 API 客户端")
            return
        config = self.api_config_data["configs"][self.api_config_data.get("active_index", 0)]
        model = config.get("model", "")
        extra = config.get("extra_params", {})
        threading.Thread(target=self._do_test_api, args=(config, model, extra), daemon=True).start()

    def _do_test_api(self, config, model, extra):
        try:
            if self.client is None:
                self.after(0, lambda: messagebox.showwarning("提示", "API 客户端无效"))
                return
            kwargs = {"model": model, "messages": [{"role":"user","content":"ping"}], "max_tokens": 5}
            kwargs.update(extra)
            self.client.chat.completions.create(**kwargs)
            self.after(0, lambda: messagebox.showinfo("成功", f"✅ 当前 API ({config.get('name','')}) 连接正常！"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("失败", f"❌ 连接失败：{str(e)}"))

    # ---------- 服务器配置 ----------
    def save_server_config(self):
        try: port = int(self.server_entries["端口"].get())
        except: messagebox.showerror("错误","端口必须是数字"); return
        self.server_config["host"] = self.server_entries["主机地址"].get()
        self.server_config["port"] = port
        self.server_config["user"] = self.server_entries["用户名"].get()
        self.server_config["password"] = self.server_entries["密码"].get()
        self.server_config["remote_root"] = self.remote_root_entry.get()
        save_config(SERVER_CONFIG_FILE, self.server_config)
        messagebox.showinfo("成功","服务器配置已保存。")
        self.disconnect_ssh_terminal()
        self.terminal_interacted = False
        self.update_terminal_status()

    def test_server_connection(self):
        host = self.server_entries["主机地址"].get()
        port_str = self.server_entries["端口"].get()
        user = self.server_entries["用户名"].get()
        password = self.server_entries["密码"].get()
        try: port = int(port_str)
        except: self.server_test_result.configure(text="端口号无效", text_color="red"); return
        self.server_test_result.configure(text="⏳ 测试中...", text_color="gray")
        def do_test():
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            try:
                ssh.connect(host, port=port, username=user, password=password, timeout=8)
                ssh.exec_command("echo test")
                self.after(0, lambda: self.server_test_result.configure(text="✅ 连接成功！", text_color="green"))
            except Exception as e:
                self.after(0, lambda: self.server_test_result.configure(text=f"❌ 失败：{str(e)}", text_color="red"))
            finally:
                ssh.close()
        threading.Thread(target=do_test, daemon=True).start()

    # ================== SSH 终端（异步连接，不阻塞） ==================
    @staticmethod
    def strip_ansi(text):
        return re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])').sub('', text)

    def update_terminal_status(self):
        """更新终端初始提示，不显示示例配置为已连接"""
        if self.terminal_interacted:
            return
        self.terminal_output.configure(state="normal")
        self.terminal_output.delete("1.0","end")
        host = self.server_config.get("host", "")
        # 检查是否配置了有效的主机（非空且不是示例）
        if host and host != "192.168.1.100":
            self.terminal_output.insert("end", f"已配置服务器 {host}，输入命令将自动连接...\n", "system_msg")
        else:
            self.terminal_output.insert("end", "⚠️ 未配置服务器，请前往设置配置。\n", "error")
            # 使用 _textbox 进行 tag 配置
            self.terminal_output._textbox.tag_configure("link", foreground="blue", underline=True)
            self.terminal_output.insert("end", "👉 点击此处前往配置", ("link",))
            self.terminal_output._textbox.tag_bind("link", "<Button-1>", lambda e: self.open_settings("服务器配置"))
        self.terminal_output.configure(state="disabled")

    def on_page_up(self, event=None): self.navigate_history(-1); return "break"
    def on_page_down(self, event=None): self.navigate_history(1); return "break"

    def navigate_history(self, direction):
        if not self.command_history: return
        if direction == -1:
            if self.history_index == -1: self.history_index = len(self.command_history) - 1
            elif self.history_index > 0: self.history_index -= 1
            else: return
        else:
            if self.history_index == -1: return
            elif self.history_index < len(self.command_history) - 1: self.history_index += 1
            else:
                self.history_index = -1
                self.cmd_entry.delete(0, 'end')
                return
        command = self.command_history[self.history_index]
        self.cmd_entry.delete(0, 'end')
        self.cmd_entry.insert(0, command)

    def execute_ssh_command_input(self):
        if self.command_running:
            messagebox.showwarning("提示", "命令正在执行，请等待完成。")
            return
        cmd = self.cmd_entry.get().strip()
        if not cmd: return
        self.command_history.append(cmd)
        self.history_index = -1
        self.cmd_entry.delete(0, "end")
        self.execute_ssh_command(cmd)

    def execute_ssh_command(self, cmd):
        """异步执行命令，若未连接则自动后台连接，不阻塞界面"""
        if not cmd:
            return
        host = self.server_config.get("host", "")
        if not host or host == "192.168.1.100":
            messagebox.showwarning("提示", "请先配置有效的服务器地址。")
            return
        if self.command_running:
            messagebox.showwarning("提示", "命令正在执行，请等待完成。")
            return

        # 如果已连接，直接发送
        if self.ssh_channel and self.terminal_running:
            self.lock_cmd_entry()
            self.ssh_channel.send(cmd + "\n")
            return

        # 未连接，尝试后台连接
        if self.connecting_flag:
            self.pending_commands.put(cmd)
            self.display_system_message("⏳ 正在连接服务器，命令已排队...")
            return

        self.connecting_flag = True
        self.display_system_message("⏳ 正在连接服务器...")
        threading.Thread(target=self._connect_and_execute, args=(cmd,), daemon=True).start()

    def _connect_and_execute(self, first_cmd):
        """后台连接线程，连接成功后执行命令，并处理队列中的其他命令"""
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(
                self.server_config["host"],
                port=self.server_config["port"],
                username=self.server_config["user"],
                password=self.server_config["password"],
                timeout=10
            )
            channel = ssh.invoke_shell(width=120, height=40)
            # 成功
            self.ssh_client = ssh
            self.ssh_channel = channel
            self.terminal_running = True
            self.terminal_interacted = True
            # 清空终端旧内容并显示连接成功
            self.after(0, lambda: self._terminal_append("✅ SSH 连接成功！\n", "system_msg"))
            # 启动输出读取线程
            self.terminal_thread = threading.Thread(target=self._read_terminal_output, daemon=True)
            self.terminal_thread.start()
            # 发送第一个命令
            self.lock_cmd_entry()
            channel.send(first_cmd + "\n")
            # 处理队列中的其他命令
            while not self.pending_commands.empty():
                cmd = self.pending_commands.get()
                channel.send(cmd + "\n")
        except Exception as e:
            self.after(0, lambda: self._terminal_append(f"❌ 连接失败: {str(e)}\n", "error"))
            self.disconnect_ssh_terminal()
        finally:
            self.connecting_flag = False

    def _read_terminal_output(self):
        buff = b""
        while self.terminal_running and self.ssh_channel:
            try:
                if self.ssh_channel.recv_ready():
                    chunk = self.ssh_channel.recv(1024)
                    if not chunk: break
                    buff += chunk
                    text = buff.decode('utf-8', errors='replace')
                    buff = b""
                    self.msg_queue.put(('terminal_out', self.strip_ansi(text)))
                else:
                    time.sleep(0.05)
            except Exception as e:
                self.msg_queue.put(('system', f"终端读取错误: {str(e)}"))
                break
        self.after(0, self._on_terminal_disconnected)

    def _on_terminal_disconnected(self):
        if self.terminal_running:
            self._terminal_append("\n⚠️ 终端连接已断开\n", "error")
        self.disconnect_ssh_terminal()

    def disconnect_ssh_terminal(self):
        self.terminal_running = False
        self.connecting_flag = False
        # 清空待执行命令队列
        while not self.pending_commands.empty():
            self.pending_commands.get()
        if self.ssh_channel:
            try: self.ssh_channel.close()
            except: pass
            self.ssh_channel = None
        if self.ssh_client:
            try: self.ssh_client.close()
            except: pass
            self.ssh_client = None
        self.unlock_cmd_entry()

    def send_ctrl_c(self):
        if self.ssh_channel and self.terminal_running:
            self.ssh_channel.send('\x03')
            self._terminal_append("^C\n", "system_msg")
        self.unlock_cmd_entry()

    def lock_cmd_entry(self):
        self.command_running = True
        self.cmd_entry.configure(state="disabled")

    def unlock_cmd_entry(self):
        if self.command_running:
            self.command_running = False
            self.cmd_entry.configure(state="normal")
            self.cmd_entry.focus_set()

    def _check_prompt_in_output(self, text):
        pattern = r'[$#]\s*$'
        return bool(re.search(pattern, text.rstrip()))

    def _terminal_append(self, text, tag="output"):
        if not self.running: return
        self.terminal_output.configure(state="normal")
        self.terminal_output.insert("end", text, tag)
        self.terminal_output.see("end")
        self.terminal_output.configure(state="disabled")

    # ---------- 消息队列处理 ----------
    def process_queue(self):
        if not self.running: return
        try:
            while True:
                msg_type, data = self.msg_queue.get_nowait()
                if msg_type == 'thinking':
                    self.chat_area.configure(state="normal"); self.chat_area.insert("end", data, "thinking"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")
                elif msg_type == 'answer_start':
                    self.chat_area.configure(state="normal"); self.chat_area.insert("end", "\n🤖 AI回复:\n", "bold"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")
                elif msg_type == 'answer':
                    self.chat_area.configure(state="normal"); self.chat_area.insert("end", data, "ai"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")
                elif msg_type == 'usage':
                    self.last_usage = data
                    if hasattr(data, 'total_tokens'): self.token_label.configure(text=f"🔢 Token: {data.total_tokens}")
                elif msg_type == 'done':
                    self.is_streaming = False; self.display_system_message("✅ 回复完成，正在应用代码..."); self.apply_code_from_response(data)
                elif msg_type == 'error':
                    self.is_streaming = False; self.display_system_message(f"❌ 错误: {data}")
                elif msg_type == 'stream_end': self.is_streaming = False
                elif msg_type == 'system': self.display_system_message(data)
                elif msg_type == 'terminal_out':
                    self._terminal_append(data, "output")
                    if self.command_running and self._check_prompt_in_output(data): self.unlock_cmd_entry()
        except queue.Empty: pass
        if self.running: self.after(50, self.process_queue)

    # ---------- AI 对话 ----------
    def send_message(self, custom_message=None):
        if self.client is None:
            self.display_system_message("⚠️ 未配置有效的 API 客户端，请在设置中配置并测试连接。")
            return
        if self.is_streaming: return
        if custom_message: user_text = custom_message
        else:
            user_text = self.input_text.get("1.0","end").strip()
            if not user_text: return
            self.input_text.delete("1.0","end")
        if not self.project_path: messagebox.showwarning("提示","请先加载项目"); return
        self.display_user_message(user_text)

        system_prompt = (
            "你是一个专业的Android开发助手，同时能够编写配套的后端Python服务。请严格遵守以下规则：\n"
            "1. 当你需要提供任何代码文件时，必须使用markdown代码块，并在代码块的第一行使用注释标明文件的**相对路径（相对于项目根目录）**。\n"
            "   - Kotlin/Java: // file: app/src/main/java/com/example/.../File.kt\n"
            "   - XML: <!-- file: app/src/main/res/layout/.../activity_main.xml -->\n"
            "   - Python: # file: backend/main.py\n"
            "   - 配置文件: # file: backend/requirements.txt\n"
            "2. 代码块之外的内容，绝对不要包含任何看起来像文件路径的注释。\n"
            "3. 所有后端（服务器端）代码必须放在 backend/ 目录下。\n"
            "4. **你必须给出每个文件的完整代码，不能省略或引用“保持不变”的部分**，即使之前提供过也要完整输出。\n"
            "5. 回复中可以包含文字说明，但只有带有正确路径注释的代码块才会被应用到项目中。\n"
            "6. 如果需要对现有文件进行修改，请仍然提供完整的新代码，并注明相同的路径，程序会直接覆盖旧文件。\n"
        )

        messages = [{"role": "system", "content": system_prompt}]
        if self.include_context_var.get():
            project_info = self.collect_project_info()
            package_note = f"\n当前包名: {self.package_name}\n请使用此包名，保证代码兼容。" if self.package_name else ""
            messages[0]["content"] += "\n\n" + project_info + package_note
        messages.append({"role": "user", "content": user_text})

        self.is_streaming = True
        self.display_system_message("🤔 AI思考中...")
        idx = self.api_config_data["active_index"]
        config = self.api_config_data["configs"][idx]
        extra = config.get("extra_params", {})
        threading.Thread(target=self.stream_ai_response, args=(messages, extra), daemon=True).start()

    def stream_ai_response(self, messages, extra):
        try:
            idx = self.api_config_data["active_index"]
            config = self.api_config_data["configs"][idx]
            model = config.get("model", "glm-4")
            kwargs = {"model": model, "messages": messages, "stream": True}
            kwargs.update(extra)
            completion = self.client.chat.completions.create(**kwargs)
            full = ""; first = True
            for chunk in completion:
                if not chunk.choices:
                    if hasattr(chunk,'usage') and chunk.usage: self.msg_queue.put(('usage', chunk.usage))
                    continue
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    self.msg_queue.put(('thinking', delta.reasoning_content))
                if hasattr(delta,"content") and delta.content:
                    if first:
                        first=False
                        self.msg_queue.put(('answer_start', None))
                    full += delta.content
                    self.msg_queue.put(('answer', delta.content))
            self.msg_queue.put(('done', full))
        except Exception as e:
            self.msg_queue.put(('error', str(e)))
        finally:
            self.msg_queue.put(('stream_end', None))

    # ---------- 代码提取与应用 ----------
    def _extract_path_from_line(self, line: str) -> Optional[str]:
        line = line.strip()
        patterns = [
            r'//\s*file\s*:\s*(.+)',
            r'#\s*file\s*:\s*(.+)',
            r'<!--\s*file\s*:\s*(.+?)\s*-->',
            r'/\*\s*file\s*:\s*(.+?)\s*\*/',
            r'文件路径[：:]\s*(.+)'
        ]
        for pat in patterns:
            m = re.match(pat, line, re.I)
            if m:
                return m.group(1).strip().strip('\'"')
        if ('/' in line or '\\' in line) and re.search(r'\.(kt|xml|java|kts|gradle|properties|txt|py|html|css|js)$', line, re.I):
            return line.strip().strip('\'"')
        return None

    def extract_code_files(self, text: str) -> dict:
        files = {}
        pattern = re.compile(r'```(?:\w+)?\s*\n(.*?)```', re.DOTALL)
        for match in pattern.finditer(text):
            code = match.group(1)
            first_line = code.split('\n')[0].strip()
            path = self._extract_path_from_line(first_line)
            if path:
                code_body = code.split('\n', 1)[1].strip() if '\n' in code else ''
                files[path] = code_body
            else:
                code_start = match.start()
                preceding = text[:code_start].rstrip()
                if preceding:
                    last_line = preceding.split('\n')[-1].strip()
                    path = self._extract_path_from_line(last_line)
                    if path:
                        files[path] = code.strip()
        return files

    def apply_code_from_response(self, response_text):
        files = self.extract_code_files(response_text)
        if not files:
            self.display_system_message("⚠️ 未找到有效代码文件。")
            return
        self.save_version("AI代码应用前")
        applied = []
        for rp, code in files.items():
            rp = rp.replace('\\', '/')
            safe = os.path.normpath(rp)
            if safe.startswith('..') or os.path.isabs(safe):
                continue
            full = os.path.join(self.project_path, safe)
            ensure_dir(os.path.dirname(full))
            with open(full, 'w', encoding='utf-8') as f:
                f.write(code)
            applied.append(safe)
        self.refresh_file_tree()
        self.display_system_message(f"✅ 已应用 {len(applied)} 个文件：{', '.join(applied)}")
        self.current_extracted_files = files
        self.save_version("AI代码应用后")

    # ---------- 部署后端 ----------
    def deploy_to_server(self):
        if not self.current_extracted_files: messagebox.showwarning("提示","没有可部署文件。"); return
        if not self.server_config.get("host") or self.server_config.get("host") == "192.168.1.100":
            self.open_settings("服务器配置")
            return
        bkf = {p:c for p,c in self.current_extracted_files.items() if p.replace('\\','/').startswith('backend/')}
        if not bkf: messagebox.showwarning("提示","未检测到 backend/ 文件。"); return
        if not self.package_name:
            messagebox.showwarning("提示", "未检测到项目包名，无法创建对应目录。")
            return
        self.display_system_message("☁️ 正在部署...")
        threading.Thread(target=self._ssh_deploy, args=(bkf,), daemon=True).start()

    def _ssh_deploy(self, files):
        ssh = paramiko.SSHClient(); ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            ssh.connect(self.server_config["host"], port=self.server_config["port"],
                        username=self.server_config["user"], password=self.server_config["password"], timeout=10)
            sftp = ssh.open_sftp()
            remote_root = self.server_config["remote_root"]
            package_dir = os.path.join(remote_root, self.package_name).replace('\\','/')
            try:
                sftp.stat(package_dir)
            except:
                self._sftp_mkdir_p(sftp, package_dir)
            for rp, content in files.items():
                remote = os.path.join(package_dir, rp).replace('\\','/')
                rd = os.path.dirname(remote)
                try: sftp.stat(rd)
                except: self._sftp_mkdir_p(sftp, rd)
                with sftp.file(remote, 'w') as f: f.write(content)
                self.msg_queue.put(('system', f"📤 已上传: {rp}"))
            sftp.close()
            self.msg_queue.put(('system', "🎉 部署完成！"))
        except Exception as e: self.msg_queue.put(('system', f"❌ 部署失败: {e}"))
        finally: ssh.close()

    def _sftp_mkdir_p(self, sftp, rd):
        if rd == '/': return
        try: sftp.stat(rd)
        except:
            parent = os.path.dirname(rd)
            self._sftp_mkdir_p(sftp, parent)
            sftp.mkdir(rd)

    def display_user_message(self, text):
        self.chat_area.configure(state="normal"); self.chat_area.insert("end", "\n👤 你:\n", ("user","bold")); self.chat_area.insert("end", text+"\n", "user"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")

    def display_system_message(self, text):
        self.chat_area.configure(state="normal"); self.chat_area.insert("end", text+"\n", "system"); self.chat_area.see("end"); self.chat_area.configure(state="disabled")

    def confirm_clear_chat(self):
        if messagebox.askyesno("确认清除","确定要清除本次对话内容吗？"): self.clear_chat()

    def clear_chat(self):
        self.chat_area.configure(state="normal"); self.chat_area.delete("1.0","end"); self.chat_area.configure(state="disabled")

    def restart_app(self, new_theme=None):
        if new_theme is None: new_theme = self.current_theme_name
        self.running = False
        self.disconnect_ssh_terminal()
        self.destroy()
        app = AndroidAIAssistant(startup_theme=new_theme)
        if hasattr(self, 'project_path') and self.project_path:
            app.path_entry.delete(0,"end"); app.path_entry.insert(0, self.project_path); app.load_project(self.project_path)
        app.mainloop()
        sys.exit()

if __name__ == "__main__":
    app = AndroidAIAssistant()
    app.mainloop()