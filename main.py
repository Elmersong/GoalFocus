import sys
import os
import json
import uuid
from datetime import datetime

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QTextEdit,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QAbstractItemView,
    QMenu,
    QSpinBox,
    QScrollArea,
    QDialog,
    QFormLayout,
    QDialogButtonBox,
    QFrame,
    QSystemTrayIcon,
    QSizePolicy,
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    QUrl,
    QSize,
    QRect,
    QPropertyAnimation,
)
from PySide6.QtGui import QCloseEvent, QPixmap, QMovie, QColor, QBrush, QIcon
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    import winsound
except ImportError:
    winsound = None


# =========================
#  应用名称
# =========================

APP_NAME = "GoalFocus"


# =========================
#  多语言配置
# =========================

LANG_ZH = "zh"
LANG_EN = "en"


def get_data_dir() -> str:
    """
    数据目录选择逻辑：
    - 打包 EXE（PyInstaller）：使用用户目录
        - Windows: %APPDATA%\\GoalFocus
        - 其他系统: ~/.goalfocus
    - 开发环境（python main.py）：使用 main.py 所在项目目录
    """
    if getattr(sys, "frozen", False):
        # 打包后的 EXE
        if sys.platform.startswith("win"):
            base_dir = os.getenv("APPDATA") or os.path.expanduser("~")
            data_dir = os.path.join(base_dir, APP_NAME)
        else:
            base_dir = os.path.expanduser("~")
            data_dir = os.path.join(base_dir, f".{APP_NAME.lower()}")
    else:
        # 开发环境：main.py 所在目录
        data_dir = os.path.dirname(os.path.abspath(__file__))

    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def get_settings_file() -> str:
    """
    语言等设置文件：与数据文件同目录，名为 settings.json
    - EXE: 用户目录
    - 开发环境: 项目目录
    """
    return os.path.join(get_data_dir(), "settings.json")


SETTINGS_FILE = get_settings_file()


def load_settings() -> dict:
    default = {"language": LANG_ZH}
    if not os.path.exists(SETTINGS_FILE):
        return default
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
            if isinstance(raw, dict):
                default.update(raw)
    except Exception:
        pass
    return default


def save_settings(settings: dict):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving settings: {e}", file=sys.stderr)


SETTINGS = load_settings()
CURRENT_LANG = SETTINGS.get("language", LANG_ZH)


def set_language(lang: str):
    global CURRENT_LANG, SETTINGS
    if lang not in (LANG_ZH, LANG_EN):
        return
    CURRENT_LANG = lang
    SETTINGS["language"] = lang
    save_settings(SETTINGS)


def L(zh: str, en: str) -> str:
    """
    简单的双语选择函数：
    - CURRENT_LANG == zh -> 返回中文
    - 否则返回英文
    """
    return zh if CURRENT_LANG == LANG_ZH else en


# =========================
#  数据文件位置
# =========================


def get_data_file() -> str:
    """
    返回数据文件 goals_data.json 的绝对路径：
    - 打包 EXE：用户目录
    - 开发环境：项目目录
    """
    return os.path.join(get_data_dir(), "goals_data.json")


DATA_FILE = get_data_file()


def resource_path(relative_path: str) -> str:
    base_path = getattr(sys, "_MEIPASS", "")
    if base_path:
        candidate = os.path.join(base_path, relative_path)
        if os.path.exists(candidate):
            return candidate
    base_path = os.path.dirname(os.path.abspath(sys.argv[0]))
    return os.path.join(base_path, relative_path)


REWARD_ANIMATION_GIF_PATH = resource_path("success.gif")
REWARD_BADGE_PATH = resource_path("pic.png")
REWARD_SOUND_PATH = resource_path("sound.mp3")
APP_ICON_PATH = resource_path("logo.ico")


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def strip_leading_number(text: str) -> str:
    text = text.strip()
    parts = text.split(".", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        return parts[1].lstrip()
    return text


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def lerp_color_hex(c1: str, c2: str, t: float) -> str:
    t = clamp(t, 0.0, 1.0)
    c1 = c1.lstrip("#")
    c2 = c2.lstrip("#")
    r1, g1, b1 = int(c1[0:2], 16), int(c1[2:4], 16), int(c1[4:6], 16)
    r2, g2, b2 = int(c2[0:2], 16), int(c2[2:4], 16), int(c2[4:6], 16)
    r = int(lerp(r1, r2, t))
    g = int(lerp(g1, g2, t))
    b = int(lerp(b1, b2, t))
    return f"#{r:02X}{g:02X}{b:02X}"


def text_color_for_bg(hex_color: str) -> str:
    c = hex_color.lstrip("#")
    r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    luminance = (0.299 * r + 0.587 * g + 0.114 * b) / 255.0
    return "#111111" if luminance > 0.62 else "#FFFFFF"


def finalize_store(store: dict) -> dict:
    store.setdefault("active_goal", None)
    store.setdefault("archive", [])
    store.setdefault("total_completed_count", len(store["archive"]))
    store.setdefault("delete_tokens_used", 0)
    store.setdefault("long_term_goals", [])
    store.setdefault("templates", [])
    return store


def load_data():
    if not os.path.exists(DATA_FILE):
        return finalize_store({"active_goal": None, "archive": []})
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return finalize_store({"active_goal": None, "archive": []})

    def ensure_goal_fields(goal: dict) -> dict:
        if "id" not in goal:
            goal["id"] = str(uuid.uuid4())
        goal.setdefault("long_term", "")
        goal.setdefault("long_term_goal_id", None)
        goal.setdefault("long_term_goal_ids", [])
        if not goal["long_term_goal_ids"] and goal.get("long_term_goal_id"):
            goal["long_term_goal_ids"] = [goal["long_term_goal_id"]]

        goal.setdefault("current_goal", "")
        goal.setdefault("done", False)
        goal.setdefault("created_at", now_str())
        goal.setdefault("completed_at", None)

        actions = goal.get("actions") or []
        fixed_actions = []
        for a in actions:
            if "id" not in a:
                a["id"] = str(uuid.uuid4())
            a.setdefault("text", "")
            a.setdefault("done", False)
            a.setdefault("created_at", now_str())
            a.setdefault("completed_at", None)
            fixed_actions.append(a)
        goal["actions"] = fixed_actions
        return goal

    def ensure_long_term_goal_fields(g: dict) -> dict:
        if "id" not in g:
            g["id"] = str(uuid.uuid4())
        g.setdefault("title", "")
        g.setdefault("target_count", 100)
        g.setdefault("completed_count", 0)
        g.setdefault("created_at", now_str())
        g.setdefault("completed_at", None)
        return g

    def ensure_template_fields(t: dict) -> dict:
        if "id" not in t:
            t["id"] = str(uuid.uuid4())
        t.setdefault("name", "")
        t.setdefault("long_term_text", "")
        t.setdefault("long_term_goal_id", None)
        t.setdefault("long_term_goal_ids", [])
        if not t["long_term_goal_ids"] and t.get("long_term_goal_id"):
            t["long_term_goal_ids"] = [t["long_term_goal_id"]]
        t.setdefault("current_goal", "")
        t.setdefault("actions_texts", [])
        t.setdefault("created_at", now_str())
        return t

    if isinstance(raw, dict):
        active = raw.get("active_goal")
        archive = raw.get("archive", [])
        if active is not None:
            active = ensure_goal_fields(active)
        fixed_archive = [ensure_goal_fields(g) for g in archive]

        base = {
            "active_goal": active,
            "archive": fixed_archive,
            "long_term_goals": [ensure_long_term_goal_fields(x) for x in (raw.get("long_term_goals") or [])],
            "templates": [ensure_template_fields(x) for x in (raw.get("templates") or [])],
        }
        if "total_completed_count" in raw:
            base["total_completed_count"] = raw["total_completed_count"]
        if "delete_tokens_used" in raw:
            base["delete_tokens_used"] = raw["delete_tokens_used"]
        return finalize_store(base)

    if isinstance(raw, list):
        active = None
        archive = []
        for g in raw:
            g = ensure_goal_fields(g)
            if not g.get("done") and active is None:
                active = g
            else:
                archive.append(g)
        return finalize_store({"active_goal": active, "archive": archive})

    return finalize_store({"active_goal": None, "archive": []})


def save_data(store):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(store, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving data: {e}", file=sys.stderr)


class ActionListWidget(QListWidget):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        self.setAlternatingRowColors(True)
        self.setStyleSheet(
            """
            QListWidget {
                font-size: 17px;
                border: none;
                outline: none;
            }
            QListWidget::item:selected {
                background: #e0f2ff;
            }
            """
        )
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            item = self.currentItem()
            if item is not None:
                action_id = item.data(Qt.UserRole)
                if action_id:
                    self.app.delete_action_from_card(action_id)
                    return
        super().keyPressEvent(event)

    def dropEvent(self, event):
        super().dropEvent(event)
        ordered_ids = []
        for i in range(self.count()):
            item = self.item(i)
            aid = item.data(Qt.UserRole)
            if aid:
                ordered_ids.append(aid)
        self.app.reorder_actions_from_card(ordered_ids)

    def contextMenuEvent(self, event):
        pos = event.pos()
        item = self.itemAt(pos)
        if item is None:
            return
        action_id = item.data(Qt.UserRole)
        if not action_id:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(L("删除此关键动作", "Delete this action"))
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == delete_action:
            self.app.delete_action_from_card(action_id)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            self.app.add_action_from_card("")
            last_row = self.count() - 1
            if last_row >= 0:
                new_item = self.item(last_row)
                self.setCurrentItem(new_item)
                self.editItem(new_item)
        else:
            super().mouseDoubleClickEvent(event)


class FocusWindow(QWidget):
    """
    悬浮卡片：
    - 使用系统自带窗口边框 + 标题栏（只有这一层标题栏）
    - 置顶（WindowStaysOnTopHint）
    - 支持系统原生的四向/斜向缩放
    - 最小尺寸 15x15
    """

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.resize(520, 360)
        self.setMinimumSize(15, 15)

        # 使用系统标题栏 + 边框
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)


        self.card = None
        self.current_label = None
        self.long_term_label = None
        self.action_list = None
        self.toggle_all_button = None
        self.finish_button = None

        self.build_ui()
        self.apply_language()

    def minimumSizeHint(self) -> QSize:
        return QSize(15, 15)

    def apply_language(self):
        self.setWindowTitle(L("专注卡片", "Focus Card"))
        if self.toggle_all_button is not None:
            self.toggle_all_button.setText(L("全选", "Toggle all"))
        if self.finish_button is not None:
            self.finish_button.setText(L("完成卡片", "Finish card"))

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(0)

        card = QWidget()
        self.card = card
        card.setStyleSheet(
            """
            QWidget {
                background-color: #ffffff;
                border-radius: 8px;
                border: 1px solid #DDDDDD;
            }
            """
        )
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 10)
        card_layout.setSpacing(6)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(6)

        self.current_label = QLabel("")
        self.current_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.current_label.setWordWrap(True)
        self.current_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        self.long_term_label = QLabel("")
        self.long_term_label.setStyleSheet("color: #666666; font-size: 16px;")
        self.long_term_label.setWordWrap(True)
        self.long_term_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        content_layout.addWidget(self.current_label)
        content_layout.addWidget(self.long_term_label)

        self.action_list = ActionListWidget(self.app)
        self.action_list.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        content_layout.addWidget(self.action_list, stretch=1)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(8)
        bottom_layout.addStretch()

        self.toggle_all_button = QPushButton()
        self.finish_button = QPushButton()
        for btn in (self.toggle_all_button, self.finish_button):
            btn.setMinimumHeight(24)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
            btn.setStyleSheet("QPushButton { font-size: 13px; padding: 2px 8px; }")

        self.toggle_all_button.clicked.connect(self.app.toggle_all_actions_from_card)
        self.finish_button.clicked.connect(self.app.finish_goal_if_completed_from_card)

        bottom_layout.addWidget(self.toggle_all_button)
        bottom_layout.addWidget(self.finish_button)
        content_layout.addLayout(bottom_layout)

        card_layout.addLayout(content_layout)
        main_layout.addWidget(card)

        self.action_list.itemChanged.connect(self.on_item_changed)

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()

    def refresh(self):
        goal = self.app.get_active_goal()
        self.action_list.blockSignals(True)
        self.action_list.clear()

        if goal is None:
            self.current_label.setText(L("当前没有进行中的专注卡片。", "No active focus card."))
            self.long_term_label.setText("")
            self.toggle_all_button.setText(L("全选", "Toggle all"))
            self.action_list.blockSignals(False)
            return

        self.current_label.setText(goal["current_goal"])
        self.long_term_label.setText(L("长期目标：", "Long-term: ") + goal["long_term"])
        any_undone = False

        for idx2, action in enumerate(goal["actions"]):
            display_text = f"{idx2 + 1}. {action['text']}"
            item = QListWidgetItem(display_text)
            item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsUserCheckable
                | Qt.ItemIsEditable
                | Qt.ItemIsDragEnabled
            )
            item.setCheckState(Qt.Checked if action.get("done") else Qt.Unchecked)
            item.setData(Qt.UserRole, action["id"])

            font = item.font()
            if action.get("done"):
                font.setStrikeOut(True)
                item.setFont(font)
                item.setForeground(QBrush(QColor("#999999")))
            else:
                font.setStrikeOut(False)
                item.setFont(font)
                item.setForeground(QBrush(QColor("#222222")))
                any_undone = True

            self.action_list.addItem(item)

        self.toggle_all_button.setText(L("全选", "Toggle all") if any_undone else L("全清", "Clear all"))
        self.action_list.blockSignals(False)

    def on_item_changed(self, item: QListWidgetItem):
        action_id = item.data(Qt.UserRole)
        if not action_id:
            return
        raw = item.text()
        text = strip_leading_number(raw)
        done = item.checkState() == Qt.Checked
        self.app.modify_action_from_card(action_id, text=text, done=done)


class PendingActionListWidget(QListWidget):
    def __init__(self, app, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.app = app
        self.setAlternatingRowColors(True)
        self.setStyleSheet(
            """
            QListWidget {
                font-size: 12px;
                outline: none;
            }
            QListWidget::item:selected {
                background: #e0f2ff;
            }
            """
        )
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setEditTriggers(
            QAbstractItemView.DoubleClicked
            | QAbstractItemView.SelectedClicked
            | QAbstractItemView.EditKeyPressed
        )

    def dropEvent(self, event):
        super().dropEvent(event)
        self.app.renumber_pending_actions()

    def contextMenuEvent(self, event):
        pos = event.pos()
        item = self.itemAt(pos)
        if item is None:
            return
        menu = QMenu(self)
        delete_action = menu.addAction(L("删除此关键动作", "Delete this action"))
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == delete_action:
            row = self.row(item)
            self.takeItem(row)
            self.app.renumber_pending_actions()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            new_item = QListWidgetItem(L("新关键动作", "New action"))
            new_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled)
            self.addItem(new_item)
            self.app.renumber_pending_actions()
            self.setCurrentItem(new_item)
            self.editItem(new_item)
        else:
            super().mouseDoubleClickEvent(event)


class LongTermGoalDialog(QDialog):
    def __init__(self, parent, title: str = "", target_count: int = 100):
        super().__init__(parent)
        self.setWindowTitle(L("长期目标", "Long-term goal"))
        self.resize(420, 160)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.title_edit = QLineEdit(title)
        self.target_spin = QSpinBox()
        self.target_spin.setRange(1, 999999)
        self.target_spin.setValue(int(target_count) if target_count else 100)

        form.addRow(L("目标名称：", "Name:"), self.title_edit)
        form.addRow(L("目标次数：", "Target count:"), self.target_spin)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_values(self):
        """
        返回：
        - title: 长期目标名称（去掉首尾空格）
        - target: 目标次数（int）
        """
        return self.title_edit.text().strip(), int(self.target_spin.value())


class TemplateNameDialog(QDialog):
    def __init__(self, parent, default_name: str):
        super().__init__(parent)
        self.setWindowTitle(L("保存为工作流模板", "Save as workflow template"))
        self.resize(420, 140)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(default_name)
        form.addRow(L("模板名称：", "Template name:"), self.name_edit)
        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_name(self) -> str:
        return self.name_edit.text().strip()


class GoalApp(QMainWindow):
    def __init__(self):
        super().__init__()

        if APP_ICON_PATH and os.path.exists(APP_ICON_PATH):
            self.setWindowIcon(QIcon(APP_ICON_PATH))

        self.store = load_data()
        self.focus_window: FocusWindow | None = None
        self._celebration_overlay = None

        self._audio_output = QAudioOutput()
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        # 多选长期目标：保留“点击顺序”
        self.selected_long_term_goal_ids: list[str] = []

        self.tray: QSystemTrayIcon | None = None

        # 先构建 UI
        self.build_ui()
        # 初始化菜单和托盘
        self.init_language_menu()
        self.init_tray()
        # 应用当前语言到所有控件
        self.apply_language()
        # 刷新状态
        self.refresh_main_state()

    # ---------- 语言切换：菜单 ----------
    def init_language_menu(self):
        menubar = self.menuBar()
        lang_menu = menubar.addMenu(L("语言", "Language"))
        act_zh = lang_menu.addAction("中文")
        act_en = lang_menu.addAction("English")

        act_zh.setCheckable(True)
        act_en.setCheckable(True)
        if CURRENT_LANG == LANG_ZH:
            act_zh.setChecked(True)
        else:
            act_en.setChecked(True)

        act_zh.triggered.connect(lambda: self.change_language(LANG_ZH))
        act_en.triggered.connect(lambda: self.change_language(LANG_EN))

    def change_language(self, lang: str):
        if lang not in (LANG_ZH, LANG_EN):
            return
        if lang == CURRENT_LANG:
            return

        set_language(lang)

        # 更新 UI 文案
        self.apply_language()
        self.refresh_main_state()

        # 悬浮卡片
        if self.focus_window is not None:
            self.focus_window.apply_language()
            self.focus_window.refresh()

        # 托盘菜单重建
        if self.tray is not None:
            self.tray.hide()
        self.init_tray()

        # 菜单栏重建
        self.menuBar().clear()
        self.init_language_menu()

    def update_lang_toggle_button(self):
        if hasattr(self, "lang_toggle_btn") and self.lang_toggle_btn is not None:
            if CURRENT_LANG == LANG_ZH:
                self.lang_toggle_btn.setText("中 / EN")
            else:
                self.lang_toggle_btn.setText("EN / 中")

    def on_lang_toggle_clicked(self):
        new_lang = LANG_EN if CURRENT_LANG == LANG_ZH else LANG_ZH
        self.change_language(new_lang)

    # ---------- 托盘 ----------
    def init_tray(self):
        icon = QIcon(APP_ICON_PATH) if (APP_ICON_PATH and os.path.exists(APP_ICON_PATH)) else QIcon()
        tray = QSystemTrayIcon(icon, self)
        tray.setToolTip("GoalFocus")

        menu = QMenu()
        act_toggle_focus = menu.addAction(L("显示/隐藏专注卡片", "Show / hide focus card"))
        act_show_main = menu.addAction(L("显示主窗口", "Show main window"))
        menu.addSeparator()
        act_quit = menu.addAction(L("退出", "Quit"))

        act_toggle_focus.triggered.connect(self.tray_toggle_focus_window)
        act_show_main.triggered.connect(self.tray_show_main_window)
        act_quit.triggered.connect(QApplication.quit)

        tray.setContextMenu(menu)
        tray.activated.connect(self.on_tray_activated)
        tray.show()
        self.tray = tray

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.tray_toggle_focus_window()

    def tray_show_main_window(self):
        self.show()
        self.raise_()
        self.activateWindow()

    def tray_toggle_focus_window(self):
        goal = self.get_active_goal()
        if goal is None:
            QMessageBox.information(
                self,
                L("没有卡片", "No card"),
                L("当前没有进行中的专注卡片。", "No active focus card."),
            )
            return
        if self.focus_window is None:
            self.focus_window = FocusWindow(self)
            self.focus_window.refresh()

        if self.focus_window.isVisible():
            self.focus_window.hide()
        else:
            self.focus_window.refresh()
            self.focus_window.show()
            self.focus_window.raise_()
            self.focus_window.activateWindow()

    # ---------- UI ----------
    def build_ui(self):
        self.setWindowTitle(L("专注目标", "Goal Focus"))
        self.resize(860, 620)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.plan_tab = QWidget()
        self.archive_tab = QWidget()
        self.goal_tab = QWidget()

        self.tabs.addTab(self.plan_tab, L("规划", "Plan"))
        self.tabs.addTab(self.archive_tab, L("归档", "Archive"))
        self.tabs.addTab(self.goal_tab, L("目标", "Goals"))

        self.build_plan_tab()
        self.build_archive_tab()
        self.build_goal_tab()

    def build_plan_tab(self):
        w = self.plan_tab
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # 顶部一行：标题 + 右侧小语言切换按钮
        title_row = QHBoxLayout()
        title = QLabel(L("设计你下一件最重要的事", "Design your next most important task"))
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.plan_title_label = title
        title_row.addWidget(title)

        title_row.addStretch()

        self.lang_toggle_btn = QPushButton()
        self.lang_toggle_btn.setFixedHeight(22)
        self.lang_toggle_btn.setStyleSheet(
            "QPushButton { font-size: 11px; padding: 2px 6px; color:#555555; }"
        )
        self.lang_toggle_btn.clicked.connect(self.on_lang_toggle_clicked)
        self.update_lang_toggle_button()
        title_row.addWidget(self.lang_toggle_btn)

        layout.addLayout(title_row)

        # 长期目标预设
        lt_quick_group = QGroupBox(L("长期目标预设（可多选；颜色越橙=激活越多）",
                                     "Long-term goals (multi-select; more orange = more progress)"))
        self.lt_quick_group = lt_quick_group
        ltq_layout = QVBoxLayout(lt_quick_group)
        ltq_layout.setSpacing(6)

        top_row = QHBoxLayout()
        self.lt_quick_hint = QLabel(
            L("提示：可勾选多个长期目标，一张卡片完成时会为所有勾选的目标 +1。",
              "Tip: You can select multiple long-term goals; completing one card adds +1 to all selected goals.")
        )
        self.lt_quick_hint.setStyleSheet("color:#777777; font-size: 11px;")
        top_row.addWidget(self.lt_quick_hint)
        top_row.addStretch()
        self.manage_lt_btn = QPushButton(L("管理长期目标", "Manage long-term goals"))
        self.manage_lt_btn.setStyleSheet("font-size: 12px; padding: 3px 10px;")
        self.manage_lt_btn.clicked.connect(self.open_manage_long_term_goals)
        top_row.addWidget(self.manage_lt_btn)
        ltq_layout.addLayout(top_row)

        self.lt_button_container = QWidget()
        self.lt_button_layout = QHBoxLayout(self.lt_button_container)
        self.lt_button_layout.setContentsMargins(0, 0, 0, 0)
        self.lt_button_layout.setSpacing(8)
        self.lt_button_layout.addStretch()

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setWidget(self.lt_button_container)
        scroll.setFixedHeight(58)
        ltq_layout.addWidget(scroll)
        layout.addWidget(lt_quick_group)

        # 新建卡片
        input_group = QGroupBox(L("新建专注卡片", "Create focus card"))
        self.input_group = input_group
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(6)

        lt_layout = QHBoxLayout()
        lt_label = QLabel(L("长期目标描述：", "Long-term goal:"))
        self.long_term_label = lt_label
        lt_label.setStyleSheet("font-size: 12px;")
        self.long_term_edit = QLineEdit()
        self.long_term_edit.setPlaceholderText(
            L("可写一段描述，或通过上方按钮多选长期目标", "Describe or select from the buttons above")
        )
        self.long_term_edit.setStyleSheet("font-size: 12px;")
        lt_layout.addWidget(lt_label)
        lt_layout.addWidget(self.long_term_edit)
        input_layout.addLayout(lt_layout)

        cg_layout = QHBoxLayout()
        cg_label = QLabel(L("当下目标：", "Current focus:"))
        self.current_goal_label = cg_label
        cg_label.setStyleSheet("font-size: 12px;")
        self.current_goal_edit = QLineEdit()
        self.current_goal_edit.setPlaceholderText(
            L("例如：今天完成一次 30 分钟口语练习",
              "Example: Do a 30-minute speaking practice today")
        )
        self.current_goal_edit.setStyleSheet("font-size: 12px;")
        cg_layout.addWidget(cg_label)
        cg_layout.addWidget(self.current_goal_edit)
        input_layout.addLayout(cg_layout)

        action_input_layout = QHBoxLayout()
        action_label = QLabel(L("关键动作：", "Key action:"))
        self.action_label = action_label
        action_label.setStyleSheet("font-size: 12px;")
        self.action_input_edit = QLineEdit()
        self.action_input_edit.setPlaceholderText(
            L("输入关键动作，回车添加", "Type an action and press Enter")
        )
        self.action_input_edit.setStyleSheet("font-size: 12px;")
        self.action_input_edit.returnPressed.connect(self.add_pending_action_from_text)
        self.add_action_btn = QPushButton(L("添加动作", "Add action"))
        self.add_action_btn.setStyleSheet("font-size: 12px;")
        self.add_action_btn.clicked.connect(self.add_pending_action_from_text)
        action_input_layout.addWidget(action_label)
        action_input_layout.addWidget(self.action_input_edit)
        action_input_layout.addWidget(self.add_action_btn)
        input_layout.addLayout(action_input_layout)

        pa_group = QGroupBox(
            L("已添加的关键动作（优先级 1 / 2 / 3 ...）", "Added key actions (priority 1 / 2 / 3 ...)")
        )
        self.pa_group = pa_group
        pa_layout = QVBoxLayout(pa_group)
        hint_label = QLabel(
            L("提示：双击空白新增行，双击文字编辑，拖拽调整顺序，右键删除。",
              "Tip: Double-click blank to add, double-click text to edit, drag to reorder, right-click to delete.")
        )
        self.pending_hint_label = hint_label
        hint_label.setStyleSheet("color: #777777; font-size: 11px;")
        pa_layout.addWidget(hint_label)

        list_and_button_layout = QHBoxLayout()
        self.pending_actions_list = PendingActionListWidget(self)
        list_and_button_layout.addWidget(self.pending_actions_list)

        self.remove_pending_action_btn = QPushButton(L("删除选中", "Remove selected"))
        self.remove_pending_action_btn.setStyleSheet("font-size: 12px;")
        self.remove_pending_action_btn.clicked.connect(self.remove_selected_pending_action)
        list_and_button_layout.addWidget(self.remove_pending_action_btn)
        pa_layout.addLayout(list_and_button_layout)

        self.pending_actions_list.itemChanged.connect(self.on_pending_item_changed)
        input_layout.addWidget(pa_group)

        bottom_layout = QHBoxLayout()
        self.status_label = QLabel(
            L("一次只能有一张进行中的专注卡片，当前没有进行中的卡片。",
              "Only one active focus card is allowed; currently you have none.")
        )
        self.status_label.setStyleSheet("color: #777777; font-size: 11px;")
        self.create_btn = QPushButton(L("创建专注卡片", "Create focus card"))
        self.create_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.create_btn.clicked.connect(self.create_goal_from_input)
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.create_btn)
        input_layout.addLayout(bottom_layout)

        layout.addWidget(input_group)

        # 当前专注卡片摘要
        summary_group = QGroupBox(L("当前专注卡片", "Current focus card"))
        self.summary_group = summary_group
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setSpacing(4)

        self.summary_title_label = QLabel(L("当前没有进行中的专注卡片。", "No active focus card."))
        self.summary_title_label.setStyleSheet("font-size: 13px;")
        self.summary_title_label.setWordWrap(True)

        self.summary_progress_bar = QProgressBar()
        self.summary_progress_bar.setMinimum(0)
        self.summary_progress_bar.setMaximum(100)
        self.summary_progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 1px solid #DDDDDD;
                border-radius: 6px;
                text-align: center;
                height: 18px;
                font-size: 11px;
            }
            QProgressBar::chunk {
                background-color: #FF9013;
                border-radius: 6px;
            }
            """
        )

        self.summary_progress_text = QLabel("")
        self.summary_progress_text.setStyleSheet("color: #666666; font-size: 11px;")

        self.summary_actions_label = QLabel("")
        self.summary_actions_label.setWordWrap(True)
        self.summary_actions_label.setStyleSheet("color: #444444; font-size: 11px;")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.open_focus_btn = QPushButton(L("打开专注卡片", "Open focus card"))
        self.open_focus_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.open_focus_btn.clicked.connect(self.open_focus_window)
        btn_layout.addWidget(self.open_focus_btn)

        summary_layout.addWidget(self.summary_title_label)
        summary_layout.addWidget(self.summary_progress_bar)
        summary_layout.addWidget(self.summary_progress_text)
        summary_layout.addWidget(self.summary_actions_label)
        summary_layout.addLayout(btn_layout)

        layout.addWidget(summary_group)

    def build_archive_tab(self):
        w = self.archive_tab
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)

        title = QLabel(L("已完成的专注卡片", "Completed focus cards"))
        self.archive_title_label = title
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        self.token_info_label = QLabel("")
        self.token_info_label.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(self.token_info_label)

        self.archive_table = QTableWidget(0, 4)
        self.archive_table.setHorizontalHeaderLabels(
            [
                L("长期目标", "Long-term goal"),
                L("当下目标", "Current goal"),
                L("创建时间", "Created at"),
                L("完成时间", "Completed at"),
            ]
        )
        self.archive_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.archive_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.archive_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.archive_table.itemSelectionChanged.connect(self.on_archive_selection_changed)
        self.archive_table.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.archive_table, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_template_from_archive_btn = QPushButton(
            L("将选中卡片保存为工作流模板", "Save selected card as workflow template")
        )
        self.save_template_from_archive_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.save_template_from_archive_btn.clicked.connect(self.save_selected_archive_as_template)
        btn_layout.addWidget(self.save_template_from_archive_btn)

        self.delete_with_token_btn = QPushButton(
            L("使用删除机会删除选中卡片", "Delete selected card using a delete chance")
        )
        self.delete_with_token_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.delete_with_token_btn.clicked.connect(self.delete_archive_item_with_token)
        btn_layout.addWidget(self.delete_with_token_btn)

        layout.addLayout(btn_layout)

        detail_group = QGroupBox(L("卡片详情", "Card details"))
        self.archive_detail_group = detail_group
        d_layout = QVBoxLayout(detail_group)
        self.archive_detail = QTextEdit()
        self.archive_detail.setReadOnly(True)
        self.archive_detail.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.archive_detail)
        layout.addWidget(detail_group, stretch=1)

    def build_goal_tab(self):
        w = self.goal_tab
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel(L("长期目标与工作流模板", "Long-term goals & workflow templates"))
        self.goal_title_label = title
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        lt_group = QGroupBox(L("长期目标（颜色越橙=激活越多）", "Long-term goals (more orange = more progress)"))
        self.lt_group = lt_group
        lt_layout = QVBoxLayout(lt_group)
        self.lt_list = QListWidget()
        self.lt_list.setStyleSheet("font-size: 12px;")
        lt_layout.addWidget(self.lt_list)

        lt_btn_row = QHBoxLayout()
        lt_btn_row.addStretch()
        self.lt_add_btn = QPushButton(L("新增长期目标", "Add long-term goal"))
        self.lt_add_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.lt_add_btn.clicked.connect(self.add_long_term_goal)
        self.lt_edit_btn = QPushButton(L("编辑选中", "Edit selected"))
        self.lt_edit_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.lt_edit_btn.clicked.connect(self.edit_selected_long_term_goal)
        self.lt_del_btn = QPushButton(L("删除选中", "Delete selected"))
        self.lt_del_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.lt_del_btn.clicked.connect(self.delete_selected_long_term_goal)
        lt_btn_row.addWidget(self.lt_add_btn)
        lt_btn_row.addWidget(self.lt_edit_btn)
        lt_btn_row.addWidget(self.lt_del_btn)
        lt_layout.addLayout(lt_btn_row)
        layout.addWidget(lt_group, stretch=1)

        tpl_group = QGroupBox(
            L("已保存的工作流模板（支持一键启动）",
              "Saved workflow templates (one-click start)")
        )
        self.tpl_group = tpl_group
        tpl_layout = QVBoxLayout(tpl_group)
        self.template_list = QListWidget()
        self.template_list.setStyleSheet("font-size: 12px;")
        self.template_list.setSelectionMode(QAbstractItemView.SingleSelection)
        tpl_layout.addWidget(self.template_list)

        tpl_btn_row = QHBoxLayout()
        tpl_btn_row.addStretch()
        self.start_template_btn = QPushButton(L("一键启动选中模板", "Start selected template"))
        self.start_template_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.start_template_btn.clicked.connect(self.start_selected_template)
        self.delete_template_btn = QPushButton(L("删除选中模板", "Delete selected template"))
        self.delete_template_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.delete_template_btn.clicked.connect(self.delete_selected_template)
        tpl_btn_row.addWidget(self.start_template_btn)
        tpl_btn_row.addWidget(self.delete_template_btn)
        tpl_layout.addLayout(tpl_btn_row)

        layout.addWidget(tpl_group, stretch=1)

    # ---------- 语言应用到全部控件 ----------
    def apply_language(self):
        # 窗口标题
        self.setWindowTitle(L("专注目标", "Goal Focus"))

        # Tab 标题
        self.tabs.setTabText(self.tabs.indexOf(self.plan_tab), L("规划", "Plan"))
        self.tabs.setTabText(self.tabs.indexOf(self.archive_tab), L("归档", "Archive"))
        self.tabs.setTabText(self.tabs.indexOf(self.goal_tab), L("目标", "Goals"))

        # 规划页
        self.plan_title_label.setText(L("设计你下一件最重要的事", "Design your next most important task"))
        self.lt_quick_group.setTitle(
            L("长期目标预设（可多选；颜色越橙=激活越多）",
              "Long-term goals (multi-select; more orange = more progress)")
        )
        self.lt_quick_hint.setText(
            L("提示：可勾选多个长期目标，一张卡片完成时会为所有勾选的目标 +1。",
              "Tip: You can select multiple long-term goals; completing one card adds +1 to all selected goals.")
        )
        self.manage_lt_btn.setText(L("管理长期目标", "Manage long-term goals"))

        self.input_group.setTitle(L("新建专注卡片", "Create focus card"))
        self.long_term_label.setText(L("长期目标描述：", "Long-term goal:"))
        self.long_term_edit.setPlaceholderText(
            L("可写一段描述，或通过上方按钮多选长期目标", "Describe or select from the buttons above")
        )
        self.current_goal_label.setText(L("当下目标：", "Current focus:"))
        self.current_goal_edit.setPlaceholderText(
            L("例如：今天完成一次 30 分钟口语练习",
              "Example: Do a 30-minute speaking practice today")
        )
        self.action_label.setText(L("关键动作：", "Key action:"))
        self.action_input_edit.setPlaceholderText(
            L("输入关键动作，回车添加", "Type an action and press Enter")
        )
        self.add_action_btn.setText(L("添加动作", "Add action"))

        self.pa_group.setTitle(
            L("已添加的关键动作（优先级 1 / 2 / 3 ...）",
              "Added key actions (priority 1 / 2 / 3 ...)")
        )
        self.pending_hint_label.setText(
            L("提示：双击空白新增行，双击文字编辑，拖拽调整顺序，右键删除。",
              "Tip: Double-click blank to add, double-click text to edit, drag to reorder, right-click to delete.")
        )
        self.remove_pending_action_btn.setText(L("删除选中", "Remove selected"))

        self.create_btn.setText(L("创建专注卡片", "Create focus card"))
        self.summary_group.setTitle(L("当前专注卡片", "Current focus card"))

        self.open_focus_btn.setText(L("打开专注卡片", "Open focus card"))
        self.update_lang_toggle_button()

        # 归档页
        self.archive_title_label.setText(L("已完成的专注卡片", "Completed focus cards"))
        self.archive_detail_group.setTitle(L("卡片详情", "Card details"))
        self.save_template_from_archive_btn.setText(
            L("将选中卡片保存为工作流模板", "Save selected card as workflow template")
        )
        self.delete_with_token_btn.setText(
            L("使用删除机会删除选中卡片", "Delete selected card using a delete chance")
        )
        self.archive_table.setHorizontalHeaderLabels(
            [
                L("长期目标", "Long-term goal"),
                L("当下目标", "Current goal"),
                L("创建时间", "Created at"),
                L("完成时间", "Completed at"),
            ]
        )

        # 目标页
        self.goal_title_label.setText(
            L("长期目标与工作流模板", "Long-term goals & workflow templates")
        )
        self.lt_group.setTitle(
            L("长期目标（颜色越橙=激活越多）", "Long-term goals (more orange = more progress)")
        )
        self.lt_add_btn.setText(L("新增长期目标", "Add long-term goal"))
        self.lt_edit_btn.setText(L("编辑选中", "Edit selected"))
        self.lt_del_btn.setText(L("删除选中", "Delete selected"))

        self.tpl_group.setTitle(
            L("已保存的工作流模板（支持一键启动）",
              "Saved workflow templates (one-click start)")
        )
        self.start_template_btn.setText(L("一键启动选中模板", "Start selected template"))
        self.delete_template_btn.setText(L("删除选中模板", "Delete selected template"))

    # ---------- 数据访问 ----------
    def get_active_goal(self):
        return self.store.get("active_goal")

    def get_long_term_goals(self) -> list[dict]:
        return self.store.get("long_term_goals", [])

    def get_templates(self) -> list[dict]:
        return self.store.get("templates", [])

    def find_long_term_goal(self, goal_id: str | None) -> dict | None:
        if not goal_id:
            return None
        for g in self.get_long_term_goals():
            if g.get("id") == goal_id:
                return g
        return None

    def find_template(self, template_id: str | None) -> dict | None:
        if not template_id:
            return None
        for t in self.get_templates():
            if t.get("id") == template_id:
                return t
        return None

    # ---------- 长期目标快捷按钮 ----------
    def open_manage_long_term_goals(self):
        self.tabs.setCurrentWidget(self.goal_tab)

    def refresh_long_term_quick_buttons(self):
        while self.lt_button_layout.count() > 0:
            item = self.lt_button_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

        goals = self.get_long_term_goals()
        if not goals:
            empty = QLabel(
                L("尚未设定长期目标。请到「目标」页新增 3-5 个。",
                  "No long-term goals yet. Please add 3–5 in the Goals tab.")
            )
            empty.setStyleSheet("color:#777777; font-size: 12px;")
            self.lt_button_layout.addWidget(empty)
            self.lt_button_layout.addStretch()
            return

        blue = "#2D7FF9"
        orange = "#FF8A1F"

        for g in goals:
            title = g.get("title", "")
            target = int(g.get("target_count", 100) or 100)
            done = int(g.get("completed_count", 0) or 0)
            ratio = done / target if target > 0 else 1.0
            ratio = clamp(ratio, 0.0, 1.0)
            bg = lerp_color_hex(blue, orange, ratio)
            fg = text_color_for_bg(bg)

            btn = QPushButton(f"{title}")
            btn.setCheckable(True)
            gid = g.get("id")
            btn.setChecked(gid in self.selected_long_term_goal_ids)
            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {bg};
                    color: {fg};
                    border-radius: 10px;
                    border: 1px solid transparent;
                    padding: 6px 12px;
                    font-size: 12px;
                }}
                QPushButton:checked {{
                    border: 2px solid #FF9013;
                }}
                """
            )
            btn.setProperty("lt_id", gid)
            btn.clicked.connect(self.on_long_term_quick_clicked)
            self.lt_button_layout.addWidget(btn)

        self.lt_button_layout.addStretch()

    def _sync_long_term_edit_from_selection(self):
        titles = []
        for lt_id in self.selected_long_term_goal_ids:
            g = self.find_long_term_goal(lt_id)
            if g:
                t = g.get("title", "").strip()
                if t:
                    titles.append(t)
        if titles:
            self.long_term_edit.setText("；".join(titles) if CURRENT_LANG == LANG_ZH else "; ".join(titles))
        else:
            self.long_term_edit.clear()

    def on_long_term_quick_clicked(self):
        btn = self.sender()
        if not isinstance(btn, QPushButton):
            return
        lt_id = btn.property("lt_id")
        if not lt_id:
            return

        if lt_id in self.selected_long_term_goal_ids:
            self.selected_long_term_goal_ids = [
                x for x in self.selected_long_term_goal_ids if x != lt_id
            ]
        else:
            self.selected_long_term_goal_ids.append(lt_id)

        self._sync_long_term_edit_from_selection()
        self.refresh_long_term_quick_buttons()

    # ---------- 规划：待创建动作 ----------
    def add_pending_action_from_text(self):
        text = self.action_input_edit.text().strip()
        if not text:
            return
        item = QListWidgetItem(text)
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsDragEnabled)
        self.pending_actions_list.addItem(item)
        self.action_input_edit.clear()
        self.renumber_pending_actions()

    def remove_selected_pending_action(self):
        row = self.pending_actions_list.currentRow()
        if row < 0:
            return
        self.pending_actions_list.takeItem(row)
        self.renumber_pending_actions()

    def renumber_pending_actions(self):
        self.pending_actions_list.blockSignals(True)
        for i in range(self.pending_actions_list.count()):
            item = self.pending_actions_list.item(i)
            base = strip_leading_number(item.text())
            item.setText(f"{i + 1}. {base}")
        self.pending_actions_list.blockSignals(False)

    def on_pending_item_changed(self, item: QListWidgetItem):
        self.renumber_pending_actions()

    # ---------- 模板 ----------
    def refresh_template_list(self):
        self.template_list.clear()
        templates = self.get_templates()
        if not templates:
            self.template_list.addItem(
                L("（暂无模板。请在「归档」里将已完成卡片保存为模板。）",
                  "(No templates yet. Save completed cards as templates in the Archive tab.)")
            )
            self.template_list.setEnabled(False)
            self.start_template_btn.setEnabled(False)
            self.delete_template_btn.setEnabled(False)
            return

        self.template_list.setEnabled(True)
        self.start_template_btn.setEnabled(True)
        self.delete_template_btn.setEnabled(True)

        for t in templates:
            name = t.get("name") or t.get("current_goal") or L("未命名模板", "Unnamed template")
            lt_text = t.get("long_term_text", "")
            actions_count = len(t.get("actions_texts") or [])
            item = QListWidgetItem(
                L(
                    f"{name}  |  {lt_text}  |  动作 {actions_count} 个",
                    f"{name}  |  {lt_text}  |  {actions_count} actions",
                )
            )
            item.setData(Qt.UserRole, t.get("id"))
            self.template_list.addItem(item)

    def make_goal_from_template(self, t: dict) -> dict:
        actions = []
        for text in (t.get("actions_texts") or []):
            actions.append(
                {"id": str(uuid.uuid4()), "text": text, "done": False, "created_at": now_str(), "completed_at": None}
            )
        lt_ids = t.get("long_term_goal_ids") or []
        if not lt_ids and t.get("long_term_goal_id"):
            lt_ids = [t["long_term_goal_id"]]
        return {
            "id": str(uuid.uuid4()),
            "long_term": t.get("long_term_text", ""),
            "long_term_goal_id": lt_ids[0] if lt_ids else None,
            "long_term_goal_ids": lt_ids,
            "current_goal": t.get("current_goal", ""),
            "actions": actions,
            "done": False,
            "created_at": now_str(),
            "completed_at": None,
        }

    def start_selected_template(self):
        if self.get_active_goal() is not None:
            QMessageBox.information(
                self,
                L("已有进行中的卡片", "Active card exists"),
                L("你当前已经有一张进行中的专注卡片，请先完成它，再启动模板。",
                  "You already have an active focus card. Please finish it before starting a template."),
            )
            return
        item = self.template_list.currentItem()
        if item is None:
            return
        tid = item.data(Qt.UserRole)
        t = self.find_template(tid)
        if not t:
            return
        goal = self.make_goal_from_template(t)
        self.store["active_goal"] = goal
        save_data(self.store)
        self.refresh_main_state()
        self.open_focus_window()
        self.tabs.setCurrentWidget(self.plan_tab)

    def delete_selected_template(self):
        item = self.template_list.currentItem()
        if not item:
            return
        tid = item.data(Qt.UserRole)
        t = self.find_template(tid)
        if not t:
            return
        reply = QMessageBox.question(
            self,
            L("确认删除", "Confirm delete"),
            L(
                f"确定删除模板：\n\n{t.get('name','')}\n\n删除后不可恢复。",
                f"Delete template:\n\n{t.get('name','')}\n\nThis cannot be undone.",
            ),
        )
        if reply != QMessageBox.Yes:
            return
        self.store["templates"] = [x for x in self.get_templates() if x.get("id") != tid]
        save_data(self.store)
        self.refresh_main_state()

    # ---------- 主状态刷新 ----------
    def refresh_main_state(self):
        self.refresh_long_term_quick_buttons()
        self.refresh_goal_tab()
        self.refresh_template_list()

        goal = self.get_active_goal()

        if goal is None:
            self.status_label.setText(
                L("一次只能有一张进行中的专注卡片，当前没有进行中的卡片。",
                  "Only one active focus card is allowed; currently you have none.")
            )
            self.create_btn.setEnabled(True)

            self.summary_title_label.setText(L("当前没有进行中的专注卡片。", "No active focus card."))
            self.summary_progress_bar.setValue(0)
            self.summary_progress_text.setText("")
            self.summary_actions_label.setText("")
            self.open_focus_btn.setEnabled(False)
        else:
            self.status_label.setText(
                L("已经有一张进行中的卡片，完成后才能创建新的。",
                  "You already have an active focus card; complete it before creating a new one.")
            )
            self.create_btn.setEnabled(False)

            title = L(
                f"{goal['long_term']} → {goal['current_goal']}",
                f"{goal['long_term']} → {goal['current_goal']}",
            )
            self.summary_title_label.setText(title)

            total = len(goal["actions"])
            done = sum(1 for a in goal["actions"] if a.get("done"))
            ratio = int((done / total) * 100) if total > 0 else 0
            self.summary_progress_bar.setValue(ratio)
            self.summary_progress_text.setText(
                L(
                    f"{done} / {total} 个关键动作已完成",
                    f"{done} / {total} key actions completed",
                )
            )

            undone = [a["text"] for a in goal["actions"] if not a.get("done")]
            if undone:
                if CURRENT_LANG == LANG_ZH:
                    lines = ["正在进行中的关键动作："]
                    for idx2, t in enumerate(undone, start=1):
                        lines.append(f"{idx2}. {t}")
                else:
                    lines = ["Key actions in progress:"]
                    for idx2, t in enumerate(undone, start=1):
                        lines.append(f"{idx2}. {t}")
                self.summary_actions_label.setText("\n".join(lines))
            else:
                self.summary_actions_label.setText(
                    L(
                        "所有关键动作已完成，可以在专注卡片中点击「完成卡片」。",
                        "All key actions are done. You can click “Finish card” in the focus card window.",
                    )
                )

            self.open_focus_btn.setEnabled(True)

        self.refresh_archive_tab()

        if self.focus_window is not None and self.focus_window.isVisible():
            self.focus_window.refresh()
            self.focus_window.apply_language()

    # ---------- 创建新卡片 ----------
    def create_goal_from_input(self):
        if self.get_active_goal() is not None:
            QMessageBox.information(
                self,
                L("已有进行中的卡片", "Active card exists"),
                L("你当前已经有一张进行中的专注卡片，请先完成它，再创建新的。",
                  "You already have an active focus card. Please finish it before creating a new one."),
            )
            return

        long_term = self.long_term_edit.text().strip()
        current_goal = self.current_goal_edit.text().strip()

        if not long_term or not current_goal:
            QMessageBox.warning(
                self,
                L("信息不完整", "Incomplete information"),
                L("请填写【长期目标描述】和【当下目标】。",
                  "Please fill in both the long-term description and current focus."),
            )
            return

        actions_texts = []
        for i in range(self.pending_actions_list.count()):
            raw = self.pending_actions_list.item(i).text()
            t = strip_leading_number(raw)
            if t:
                actions_texts.append(t)

        if not actions_texts:
            QMessageBox.warning(
                self,
                L("没有关键动作", "No key action"),
                L("请至少添加一个【关键动作】。", "Please add at least one key action."),
            )
            return

        lt_ids = self.selected_long_term_goal_ids[:]

        actions = []
        for text in actions_texts:
            actions.append(
                {"id": str(uuid.uuid4()), "text": text, "done": False, "created_at": now_str(), "completed_at": None}
            )

        goal = {
            "id": str(uuid.uuid4()),
            "long_term": long_term,
            "long_term_goal_id": lt_ids[0] if lt_ids else None,
            "long_term_goal_ids": lt_ids,
            "current_goal": current_goal,
            "actions": actions,
            "done": False,
            "created_at": now_str(),
            "completed_at": None,
        }

        self.store["active_goal"] = goal
        save_data(self.store)

        self.current_goal_edit.clear()
        self.pending_actions_list.clear()
        self.action_input_edit.clear()

        self.refresh_main_state()
        self.open_focus_window()

    # ---------- 悬浮卡片交互 ----------
    def open_focus_window(self):
        goal = self.get_active_goal()
        if goal is None:
            QMessageBox.information(
                self,
                L("没有卡片", "No card"),
                L("当前没有进行中的专注卡片。", "No active focus card."),
            )
            return
        if self.focus_window is None:
            self.focus_window = FocusWindow(self)
        self.focus_window.refresh()
        self.focus_window.apply_language()
        self.focus_window.show()
        self.focus_window.raise_()
        self.focus_window.activateWindow()

    def add_action_from_card(self, text: str):
        goal = self.get_active_goal()
        if goal is None:
            return
        goal["actions"].append(
            {"id": str(uuid.uuid4()), "text": text, "done": False, "created_at": now_str(), "completed_at": None}
        )
        save_data(self.store)
        self.refresh_main_state()

    def modify_action_from_card(self, action_id: str, text: str | None = None, done: bool | None = None):
        goal = self.get_active_goal()
        if goal is None:
            return
        celebrate_action = False
        for a in goal["actions"]:
            if a["id"] == action_id:
                if text is not None:
                    a["text"] = text
                if done is not None:
                    old_done = a.get("done", False)
                    a["done"] = done
                    if done:
                        a["completed_at"] = now_str()
                        if not old_done:
                            celebrate_action = True
                    else:
                        a["completed_at"] = None
                break
        save_data(self.store)
        self.refresh_main_state()
        if celebrate_action:
            self.show_celebration(
                kind="action",
                text=L("关键动作完成，继续保持节奏！", "Mission accomplished! Well done!")
            )

    def reorder_actions_from_card(self, ordered_ids: list[str]):
        goal = self.get_active_goal()
        if goal is None:
            return
        id_to_action = {a["id"]: a for a in goal["actions"]}
        new_actions = []
        for aid in ordered_ids:
            if aid in id_to_action:
                new_actions.append(id_to_action[aid])
        for a in goal["actions"]:
            if a["id"] not in ordered_ids:
                new_actions.append(a)
        goal["actions"] = new_actions
        save_data(self.store)
        self.refresh_main_state()

    def delete_action_from_card(self, action_id: str):
        goal = self.get_active_goal()
        if goal is None:
            return
        actions = goal["actions"]
        if len(actions) <= 1:
            reply = QMessageBox.question(
                self,
                L("删除卡片", "Delete card"),
                L(
                    "这是最后一个关键动作，如果删除，将一起删除整张专注卡片。\n确定要继续吗？",
                    "This is the last key action. Deleting it will delete the entire card.\nContinue?",
                ),
            )
            if reply == QMessageBox.Yes:
                self.store["active_goal"] = None
                save_data(self.store)
                self.refresh_main_state()
            return
        goal["actions"] = [a for a in actions if a["id"] != action_id]
        save_data(self.store)
        self.refresh_main_state()

    def toggle_all_actions_from_card(self):
        goal = self.get_active_goal()
        if goal is None:
            return
        actions = goal["actions"]
        if not actions:
            return
        any_undone = any(not a.get("done") for a in actions)
        target_done = True if any_undone else False
        for a in actions:
            a["done"] = target_done
            a["completed_at"] = now_str() if target_done else None
        save_data(self.store)
        self.refresh_main_state()

    def finish_goal_if_completed_from_card(self):
        goal = self.get_active_goal()
        if goal is None:
            return
        if not goal["actions"]:
            QMessageBox.warning(
                self,
                L("无法完成", "Cannot finish"),
                L("这张卡片没有任何关键动作，无法标记为完成。",
                  "This card has no key actions and cannot be marked as completed."),
            )
            return
        if not all(a.get("done") for a in goal["actions"]):
            QMessageBox.information(
                self,
                L("尚未完成", "Not finished"),
                L("还有关键动作没有完成，请先勾选完成全部关键动作。",
                  "Some key actions are not completed. Please finish them first."),
            )
            return

        goal["done"] = True
        goal["completed_at"] = now_str()

        self.store.setdefault("archive", []).insert(0, goal)
        self.store["total_completed_count"] = self.store.get("total_completed_count", 0) + 1

        self.increment_long_term_progress(goal)

        self.store["active_goal"] = None
        save_data(self.store)

        self.show_celebration(
            kind="card",
            text=L("本次目标已成功实现，干得漂亮！", "Success unlocked! Party time!")
        )
        self.refresh_main_state()

        if self.focus_window is not None:
            self.focus_window.hide()
        self.tabs.setCurrentWidget(self.plan_tab)

    def increment_long_term_progress(self, goal: dict):
        lt_ids = goal.get("long_term_goal_ids") or []
        if not lt_ids and goal.get("long_term_goal_id"):
            lt_ids = [goal["long_term_goal_id"]]
        if not lt_ids:
            return

        for lt_id in lt_ids:
            g = self.find_long_term_goal(lt_id)
            if not g:
                continue
            g["completed_count"] = int(g.get("completed_count", 0) or 0) + 1

            target = int(g.get("target_count", 100) or 100)
            done = int(g.get("completed_count", 0) or 0)
            if done >= target and not g.get("completed_at"):
                g["completed_at"] = now_str()

        save_data(self.store)

    # ---------- 庆祝动画 & 全局通知 ----------
    def play_reward_sound(self):
        if REWARD_SOUND_PATH and os.path.exists(REWARD_SOUND_PATH):
            try:
                url = QUrl.fromLocalFile(REWARD_SOUND_PATH)
                self._player.setSource(url)
                self._audio_output.setVolume(1.0)
                self._player.play()
                return
            except Exception:
                pass
        if winsound:
            winsound.MessageBeep()

    def show_celebration(self, kind: str, text: str):
        self.play_reward_sound()

        if self._celebration_overlay is not None:
            self._celebration_overlay.close()
            self._celebration_overlay = None

        # 单个动作完成的轻量弹窗
        if kind == "action":
            overlay = QWidget(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
            overlay.setAttribute(Qt.WA_TranslucentBackground, True)

            w, h = 900, 520
            screen = QApplication.primaryScreen()
            if screen is not None:
                rect = screen.availableGeometry()
                x = rect.x() + (rect.width() - w) // 2
                y = rect.y() + (rect.height() - h) // 2
            else:
                x, y = 300, 200
            overlay.setGeometry(x, y, w, h)

            root_layout = QVBoxLayout(overlay)
            root_layout.setContentsMargins(0, 0, 0, 0)
            root_layout.setSpacing(10)
            root_layout.setAlignment(Qt.AlignCenter)

            if REWARD_ANIMATION_GIF_PATH and os.path.exists(REWARD_ANIMATION_GIF_PATH):
                anim_label = QLabel()
                anim_label.setMinimumSize(640, 360)
                anim_label.setMaximumSize(640, 360)
                anim_label.setScaledContents(True)
                movie = QMovie(REWARD_ANIMATION_GIF_PATH)
                movie.setScaledSize(QSize(640, 360))
                anim_label.setMovie(movie)
                movie.start()
                overlay._movie = movie
                root_layout.addWidget(anim_label, alignment=Qt.AlignCenter)
            else:
                txt = QLabel("🎉")
                txt.setStyleSheet("font-size: 44px; color: white;")
                root_layout.addWidget(txt, alignment=Qt.AlignCenter)

            badge_shown = False
            if REWARD_BADGE_PATH and os.path.exists(REWARD_BADGE_PATH):
                pix = QPixmap(REWARD_BADGE_PATH)
                if not pix.isNull():
                    badge_label = QLabel()
                    pix = pix.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                    badge_label.setPixmap(pix)
                    badge_label.setAlignment(Qt.AlignCenter)
                    badge_label.setStyleSheet("background: transparent;")
                    root_layout.addWidget(badge_label, alignment=Qt.AlignCenter)
                    badge_shown = True
            if not badge_shown:
                fallback_label = QLabel("🏆")
                fallback_label.setAlignment(Qt.AlignCenter)
                fallback_label.setStyleSheet("font-size: 44px; background: transparent;")
                root_layout.addWidget(fallback_label, alignment=Qt.AlignCenter)

            msg = QLabel(text)
            msg.setStyleSheet(
                "color: #F5F1DC; font-size: 22px; "
                "background-color: rgba(255,144,19,230); "
                "padding: 14px 28px; border-radius: 14px;"
            )
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignCenter)
            msg.setMinimumWidth(520)
            msg.setMaximumWidth(920)
            root_layout.addWidget(msg, alignment=Qt.AlignCenter)

            overlay.setWindowOpacity(1.0)
            self._celebration_overlay = overlay
            overlay.show()
            overlay.raise_()

            def start_fade_out():
                if self._celebration_overlay is None:
                    return
                anim = QPropertyAnimation(overlay, b"windowOpacity")
                anim.setDuration(600)
                anim.setStartValue(1.0)
                anim.setEndValue(0.0)

                def on_finished():
                    if self._celebration_overlay is overlay:
                        self._celebration_overlay = None
                    overlay.close()

                anim.finished.connect(on_finished)
                overlay._anim = anim
                anim.start()

            QTimer.singleShot(2600, start_fade_out)
            return

        # 整张卡片完成的全屏庆祝
        overlay = QWidget(None, Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        overlay.setAttribute(Qt.WA_TranslucentBackground, True)

        screen = QApplication.primaryScreen()
        if screen is not None:
            screen_rect = screen.geometry()
        else:
            screen_rect = QRect(0, 0, 1920, 1080)

        screen_w = screen_rect.width()
        screen_h = screen_rect.height()
        overlay.setGeometry(screen_rect)

        if REWARD_ANIMATION_GIF_PATH and os.path.exists(REWARD_ANIMATION_GIF_PATH):
            bg_label = QLabel(overlay)
            bg_label.setGeometry(0, 0, screen_w, screen_h)
            bg_label.setScaledContents(True)
            movie = QMovie(REWARD_ANIMATION_GIF_PATH)
            movie.setScaledSize(QSize(screen_w, screen_h))
            bg_label.setMovie(movie)
            movie.start()
            overlay._movie = movie
        else:
            bg_label = QLabel("🎉", overlay)
            bg_label.setGeometry(0, 0, screen_w, screen_h)
            bg_label.setAlignment(Qt.AlignCenter)
            bg_label.setStyleSheet("font-size: 72px; color: white;")

        info_box = QWidget(overlay)
        info_box.setAttribute(Qt.WA_TranslucentBackground, True)

        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(18)
        info_layout.setAlignment(Qt.AlignCenter)

        badge_shown = False
        if REWARD_BADGE_PATH and os.path.exists(REWARD_BADGE_PATH):
            pix = QPixmap(REWARD_BADGE_PATH)
            if not pix.isNull():
                badge_label = QLabel(info_box)
                pix = pix.scaled(720, 720, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                badge_label.setPixmap(pix)
                badge_label.setAlignment(Qt.AlignCenter)
                badge_label.setStyleSheet("background: transparent;")
                info_layout.addWidget(badge_label, alignment=Qt.AlignCenter)
                badge_shown = True
        if not badge_shown:
            fallback_label = QLabel("🏆", info_box)
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet("font-size: 64px; background: transparent;")
            info_layout.addWidget(fallback_label, alignment=Qt.AlignCenter)

        msg_label = QLabel(info_box)
        msg_label.setText(text)
        msg_label.setWordWrap(True)
        msg_label.setAlignment(Qt.AlignCenter)
        msg_label.setMinimumWidth(int(screen_w * 0.45))
        msg_label.setMaximumWidth(int(screen_w * 0.96))
        msg_label.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)
        msg_label.setStyleSheet(
            "color: #F5F1DC; font-size: 45px; font-weight: 700; "
            "background-color: rgba(255,144,19,240); "
            "padding: 26px 44px; border-radius: 18px;"
        )
        msg_label.adjustSize()
        info_layout.addWidget(msg_label, alignment=Qt.AlignCenter)

        info_box.adjustSize()
        box_w = info_box.width()
        box_h = info_box.height()
        center_x = screen_rect.x() + (screen_w - box_w) // 2
        center_y = screen_rect.y() + (screen_h - box_h) // 2 + 30
        info_box.setGeometry(center_x, center_y, box_w, box_h)
        info_box.raise_()

        self._celebration_overlay = overlay
        overlay.show()
        overlay.raise_()

        def close_overlay():
            if self._celebration_overlay is overlay:
                self._celebration_overlay.close()
                self._celebration_overlay = None

        QTimer.singleShot(3920, close_overlay)

    # ---------- 归档 & 目标 ----------
    def refresh_archive_tab(self):
        archive = self.store.get("archive", [])
        self.archive_table.setRowCount(len(archive))
        for row, g in enumerate(archive):
            self.archive_table.setItem(row, 0, QTableWidgetItem(g.get("long_term", "")))
            self.archive_table.setItem(row, 1, QTableWidgetItem(g.get("current_goal", "")))
            self.archive_table.setItem(row, 2, QTableWidgetItem(g.get("created_at", "")))
            self.archive_table.setItem(row, 3, QTableWidgetItem(g.get("completed_at", "")))

        total_completed = self.store.get("total_completed_count", len(archive))
        tokens_used = self.store.get("delete_tokens_used", 0)
        tokens_total = total_completed // 5
        available_tokens = max(tokens_total - tokens_used, 0)

        self.token_info_label.setText(
            L(
                f"累计完成 {total_completed} 张专注卡片，可用删除机会：{available_tokens} 次（每累计完成 5 张卡片获得 1 次删除机会）。",
                f"Completed {total_completed} cards in total. Delete chances available: {available_tokens}. (You earn 1 delete chance for every 5 completed cards.)",
            )
        )
        self.delete_with_token_btn.setEnabled(available_tokens > 0 and len(archive) > 0)
        self.archive_detail.clear()

    def delete_archive_item_with_token(self):
        archive = self.store.get("archive", [])
        total_completed = self.store.get("total_completed_count", len(archive))
        tokens_used = self.store.get("delete_tokens_used", 0)
        tokens_total = total_completed // 5
        available_tokens = max(tokens_total - tokens_used, 0)

        if available_tokens <= 0:
            QMessageBox.information(
                self,
                L("没有删除机会", "No delete chance"),
                L("当前没有可用的删除机会。", "No delete chance available now."),
            )
            return

        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self,
                L("未选择卡片", "No card selected"),
                L("请先在列表中选择一条要删除的卡片。", "Please select a card in the list first."),
            )
            return
        row = rows[0].row()
        if row < 0 or row >= len(archive):
            return

        g = archive[row]
        reply = QMessageBox.question(
            self,
            L("确认删除", "Confirm delete"),
            L(
                f"将消耗一次删除机会，删除卡片：\n\n{g.get('current_goal','')}\n\n确定要删除吗？",
                f"This will consume one delete chance and delete card:\n\n{g.get('current_goal','')}\n\nDelete?",
            ),
        )
        if reply != QMessageBox.Yes:
            return

        del archive[row]
        self.store["archive"] = archive
        self.store["delete_tokens_used"] = tokens_used + 1
        save_data(self.store)
        self.refresh_archive_tab()

    def on_archive_selection_changed(self):
        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        archive = self.store.get("archive", [])
        if row < 0 or row >= len(archive):
            return
        g = archive[row]

        lines = []
        if CURRENT_LANG == LANG_ZH:
            lines.append(f"长期目标：{g.get('long_term','')}")
            lines.append(f"当下目标：{g.get('current_goal','')}")
            lines.append(f"创建时间：{g.get('created_at','')}")
            lines.append(f"完成时间：{g.get('completed_at','')}")
            lines.append("")
            lines.append("关键动作：")
        else:
            lines.append(f"Long-term: {g.get('long_term','')}")
            lines.append(f"Current goal: {g.get('current_goal','')}")
            lines.append(f"Created at: {g.get('created_at','')}")
            lines.append(f"Completed at: {g.get('completed_at','')}")
            lines.append("")
            lines.append("Key actions:")

        for idx, a in enumerate(g.get("actions", []), start=1):
            text = a.get("text", "")
            if a.get("completed_at"):
                if CURRENT_LANG == LANG_ZH:
                    lines.append(f"{idx}. {text}（完成于 {a['completed_at']}）")
                else:
                    lines.append(f"{idx}. {text} (completed at {a['completed_at']})")
            else:
                lines.append(f"{idx}. {text}")
        self.archive_detail.setPlainText("\n".join(lines))

    def save_selected_archive_as_template(self):
        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(
                self,
                L("未选择卡片", "No card selected"),
                L("请先在归档列表中选择一条要保存为模板的卡片。",
                  "Please select a card in the archive table to save as a template."),
            )
            return
        row = rows[0].row()
        archive = self.store.get("archive", [])
        if row < 0 or row >= len(archive):
            return
        g = archive[row]

        default_name = g.get("current_goal", "").strip() or L("未命名模板", "Unnamed template")
        dlg = TemplateNameDialog(self, default_name=default_name)
        if dlg.exec() != QDialog.Accepted:
            return
        name = dlg.get_name()
        if not name:
            QMessageBox.warning(
                self,
                L("名称为空", "Empty name"),
                L("请输入模板名称。", "Please enter a template name."),
            )
            return

        actions_texts = [a.get("text", "").strip() for a in (g.get("actions") or []) if a.get("text", "").strip()]
        if not actions_texts:
            QMessageBox.warning(
                self,
                L("无法保存", "Cannot save"),
                L("该卡片没有有效的关键动作，无法保存为模板。",
                  "This card has no valid key actions and cannot be saved as a template."),
            )
            return

        lt_ids = g.get("long_term_goal_ids") or []
        if not lt_ids and g.get("long_term_goal_id"):
            lt_ids = [g["long_term_goal_id"]]

        existing = None
        for t in self.get_templates():
            if (t.get("name") or "").strip() == name.strip():
                existing = t
                break

        if existing:
            reply = QMessageBox.question(
                self,
                L("覆盖模板？", "Overwrite template?"),
                L(
                    f"已存在同名模板「{name}」。\n\n是否覆盖为这张卡片的内容？",
                    f"A template named “{name}” already exists.\n\nOverwrite with this card?",
                ),
            )
            if reply != QMessageBox.Yes:
                return
            existing["long_term_text"] = g.get("long_term", "")
            existing["long_term_goal_id"] = lt_ids[0] if lt_ids else None
            existing["long_term_goal_ids"] = lt_ids
            existing["current_goal"] = g.get("current_goal", "")
            existing["actions_texts"] = actions_texts
            save_data(self.store)
        else:
            t = {
                "id": str(uuid.uuid4()),
                "name": name,
                "long_term_text": g.get("long_term", ""),
                "long_term_goal_id": lt_ids[0] if lt_ids else None,
                "long_term_goal_ids": lt_ids,
                "current_goal": g.get("current_goal", ""),
                "actions_texts": actions_texts,
                "created_at": now_str(),
            }
            self.store.setdefault("templates", []).insert(0, t)
            save_data(self.store)

        QMessageBox.information(
            self,
            L("已保存", "Saved"),
            L(f"已保存为工作流模板：{name}", f"Saved as workflow template: {name}"),
        )
        self.refresh_main_state()
        self.tabs.setCurrentWidget(self.goal_tab)

    def refresh_goal_tab(self):
        self.lt_list.clear()
        goals = self.get_long_term_goals()
        if not goals:
            self.lt_list.addItem(
                L("（暂无长期目标。点击下方“新增长期目标”。建议 3-5 个。）",
                  "(No long-term goals yet. Click “Add long-term goal” below. 3–5 suggested.)")
            )
            return

        blue = "#2D7FF9"
        orange = "#FF8A1F"
        for g in goals:
            title = g.get("title", "")
            target = int(g.get("target_count", 100) or 100)
            done = int(g.get("completed_count", 0) or 0)
            ratio = done / target if target > 0 else 1.0
            ratio = clamp(ratio, 0.0, 1.0)
            color = lerp_color_hex(blue, orange, ratio)

            extra = ""
            if done > target:
                extra = L(f"（超额 +{done - target}）", f" (over by +{done - target})")
            done_at = g.get("completed_at")
            if done_at:
                done_tag = L(f" | 达成于 {done_at}", f" | Completed at {done_at}")
            else:
                done_tag = ""

            text = L(
                f"{title}  |  {done}/{target} {extra}{done_tag}",
                f"{title}  |  {done}/{target}{extra}{done_tag}",
            )
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, g.get("id"))
            item.setForeground(QBrush(QColor(color)))
            self.lt_list.addItem(item)

    def add_long_term_goal(self):
        dlg = LongTermGoalDialog(self, title="", target_count=100)
        if dlg.exec() != QDialog.Accepted:
            return
        title, target = dlg.get_values()
        if not title:
            QMessageBox.warning(
                self,
                L("信息不完整", "Incomplete information"),
                L("请输入长期目标名称。", "Please enter long-term goal name."),
            )
            return
        g = {
            "id": str(uuid.uuid4()),
            "title": title,
            "target_count": int(target),
            "completed_count": 0,
            "created_at": now_str(),
            "completed_at": None,
        }
        self.store.setdefault("long_term_goals", []).insert(0, g)
        save_data(self.store)
        self.refresh_main_state()

    def edit_selected_long_term_goal(self):
        item = self.lt_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.UserRole)
        g = self.find_long_term_goal(gid)
        if not g:
            return
        dlg = LongTermGoalDialog(self, title=g.get("title", ""), target_count=g.get("target_count", 100))
        if dlg.exec() != QDialog.Accepted:
            return
        title, target = dlg.get_values()
        if not title:
            QMessageBox.warning(
                self,
                L("信息不完整", "Incomplete information"),
                L("请输入长期目标名称。", "Please enter long-term goal name."),
            )
            return
        g["title"] = title
        g["target_count"] = int(target)
        save_data(self.store)
        self.refresh_main_state()

    def delete_selected_long_term_goal(self):
        item = self.lt_list.currentItem()
        if not item:
            return
        gid = item.data(Qt.UserRole)
        g = self.find_long_term_goal(gid)
        if not g:
            return
        reply = QMessageBox.question(
            self,
            L("确认删除", "Confirm delete"),
            L(
                f"确定删除长期目标：\n\n{g.get('title','')}\n\n（不会删除历史归档记录，但新卡片不会再绑定它。）",
                f"Delete long-term goal:\n\n{g.get('title','')}\n\n(This will not delete history, but new cards won't bind to it.)",
            ),
        )
        if reply != QMessageBox.Yes:
            return
        self.store["long_term_goals"] = [x for x in self.get_long_term_goals() if x.get("id") != gid]
        save_data(self.store)
        self.refresh_main_state()


def main():
    app = QApplication(sys.argv)
    QApplication.setStyle("Fusion")
    window = GoalApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
