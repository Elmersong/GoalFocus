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
)
from PySide6.QtCore import (
    Qt,
    QTimer,
    QUrl,
    QSize,
    QPoint,
    QRect,
    QPropertyAnimation,
    QEvent,
)
from PySide6.QtGui import QCloseEvent, QPixmap, QMovie, QColor, QBrush
from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

try:
    import winsound  # Windows 下兜底 beep
except ImportError:
    winsound = None

DATA_FILE = "goals_data.json"

# ====== 素材路径 ======
REWARD_ANIMATION_GIF_PATH = r"E:\practice\GoalFocus\success.gif"
REWARD_BADGE_PATH         = r"E:\practice\GoalFocus\pic.png"
REWARD_SOUND_PATH         = r"E:\practice\GoalFocus\sound.mp3"
# ======================


def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def strip_leading_number(text: str) -> str:
    """
    把 '1. xxx' -> 'xxx'，其它情况原样去掉左右空格。
    """
    text = text.strip()
    parts = text.split(".", 1)
    if len(parts) == 2 and parts[0].strip().isdigit():
        return parts[1].lstrip()
    return text


def finalize_store(store: dict) -> dict:
    store.setdefault("active_goal", None)
    store.setdefault("archive", [])
    store.setdefault("total_completed_count", len(store["archive"]))
    store.setdefault("delete_tokens_used", 0)
    return store


def load_data():
    """从本地 JSON 文件载入数据，兼容老版本结构。"""
    if not os.path.exists(DATA_FILE):
        return finalize_store({"active_goal": None, "archive": []})
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception:
        return finalize_store({"active_goal": None, "archive": []})

    def ensure_goal_fields(goal):
        if "id" not in goal:
            goal["id"] = str(uuid.uuid4())
        goal.setdefault("long_term", "")
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

    # 新结构：dict
    if isinstance(raw, dict):
        active = raw.get("active_goal")
        archive = raw.get("archive", [])
        if active is not None:
            active = ensure_goal_fields(active)
        fixed_archive = [ensure_goal_fields(g) for g in archive]
        base = {"active_goal": active, "archive": fixed_archive}
        if "total_completed_count" in raw:
            base["total_completed_count"] = raw["total_completed_count"]
        if "delete_tokens_used" in raw:
            base["delete_tokens_used"] = raw["delete_tokens_used"]
        return finalize_store(base)

    # 老结构：list
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


# --------- 悬浮卡片里的动作列表 ---------
class ActionListWidget(QListWidget):
    """
    悬浮卡片中的关键动作列表：
    - 双击空白：新增空动作并进入编辑
    - 双击文字：编辑
    - 右键：删除
    - 拖拽：调整顺序
    """
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
        delete_action = menu.addAction("删除此关键动作")
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == delete_action:
            self.app.delete_action_from_card(action_id)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            # 双击空白区域：新增空动作并进入编辑
            self.app.add_action_from_card("")
            last_row = self.count() - 1
            if last_row >= 0:
                new_item = self.item(last_row)
                self.setCurrentItem(new_item)
                self.editItem(new_item)
        else:
            super().mouseDoubleClickEvent(event)


# --------- 悬浮卡片窗口（无边框 + 圆角卡片 + 顶部悬停才显示标题 + 自定义缩放） ---------
class FocusWindow(QWidget):
    RESIZE_MARGIN = 10  # 边缘热区更宽，方便斜向缩放

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.setWindowTitle("专注卡片")
        self.resize(520, 360)
        # 无边框 + 置顶 + 透明背景，用圆角卡片
        self.setWindowFlags(
            Qt.Window | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._drag_pos: QPoint | None = None
        self._resizing = False
        self._resize_dir: str | None = None
        self._start_geom: QRect | None = None
        self._start_mouse_pos: QPoint | None = None

        self.card = None  # 圆角卡片容器引用

        self.build_ui()

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 圆角卡片容器
        card = QWidget()
        self.card = card
        card.setStyleSheet(
            """
            QWidget {
                background-color: #ffffff;
                border-radius: 12px;
                border: 1px solid #DDDDDD;
            }
            """
        )
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(1, 1, 1, 1)
        card_layout.setSpacing(0)

        # 自定义标题栏（默认隐藏，只在鼠标在顶部区域时显示）
        self.header = QWidget()
        self.header.setFixedHeight(30)
        self.header.setStyleSheet(
            """
            QWidget {
                background-color: #ffffff;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                border-bottom: 1px solid #EEEEEE;
            }
            QPushButton {
                border: none;
                min-width: 26px;
                max-width: 26px;
                min-height: 22px;
                max-height: 22px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #EEEEEE;
            }
            QPushButton#closeButton:hover {
                background-color: #FF6666;
                color: white;
            }
            """
        )
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(8, 0, 6, 0)
        header_layout.setSpacing(4)

        title_label = QLabel("专注卡片")
        title_label.setStyleSheet("font-size: 13px;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        btn_min = QPushButton("—")
        btn_max = QPushButton("▢")
        btn_close = QPushButton("×")
        btn_close.setObjectName("closeButton")

        btn_min.clicked.connect(self.showMinimized)

        def toggle_max():
            if self.isMaximized():
                self.showNormal()
            else:
                self.showMaximized()

        btn_max.clicked.connect(toggle_max)
        btn_close.clicked.connect(self.hide)

        header_layout.addWidget(btn_min)
        header_layout.addWidget(btn_max)
        header_layout.addWidget(btn_close)

        card_layout.addWidget(self.header)

        # 内容区域
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(12, 10, 12, 12)
        content_layout.setSpacing(6)

        # 当下目标（主标题）
        self.current_label = QLabel("")
        self.current_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.current_label.setWordWrap(True)

        # 长期目标（副标题）
        self.long_term_label = QLabel("")
        self.long_term_label.setStyleSheet("color: #666666; font-size: 16px;")
        self.long_term_label.setWordWrap(True)

        content_layout.addWidget(self.current_label)
        content_layout.addWidget(self.long_term_label)

        # 关键动作列表（大号字体，去边框）
        self.action_list = ActionListWidget(self.app)
        content_layout.addWidget(self.action_list, stretch=1)

        # 底部按钮行：全选/全清 + 完成卡片
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.toggle_all_button = QPushButton("全选")
        self.finish_button = QPushButton("完成卡片")
        for btn in (self.toggle_all_button, self.finish_button):
            btn.setMinimumHeight(32)
            btn.setStyleSheet(
                """
                QPushButton {
                    font-size: 13px;
                    padding: 4px 10px;
                }
                """
            )
        self.toggle_all_button.clicked.connect(self.app.toggle_all_actions_from_card)
        self.finish_button.clicked.connect(self.app.finish_goal_if_completed_from_card)

        bottom_layout.addStretch()
        bottom_layout.addWidget(self.toggle_all_button)
        bottom_layout.addWidget(self.finish_button)

        content_layout.addLayout(bottom_layout)

        card_layout.addWidget(content)
        main_layout.addWidget(card)
        self.setLayout(main_layout)

        self.header.hide()  # 默认隐藏标题栏

        self.action_list.itemChanged.connect(self.on_item_changed)

        # 让卡片自己也能收到鼠标事件，用于缩放/拖动
        self.card.setMouseTracking(True)
        self.setMouseTracking(True)
        self.card.installEventFilter(self)

    # --- 顶部悬停时才显示标题栏 ---
    def _update_header_visibility(self, pos_in_window: QPoint):
        """
        只有鼠标在窗口顶部区域时显示标题栏；拖动/缩放过程中保持显示。
        """
        if self._resizing or self._drag_pos is not None:
            self.header.show()
            return
        if pos_in_window.y() <= self.header.height() + 28:
            self.header.show()
        else:
            self.header.hide()

    def leaveEvent(self, event):
        # 鼠标离开整个窗口则隐藏标题栏
        self.header.hide()
        super().leaveEvent(event)

    # --- 命中测试：判断鼠标是否在边缘用于缩放 ---
    def _hit_test(self, pos: QPoint) -> str:
        w = self.width()
        h = self.height()
        m = self.RESIZE_MARGIN

        left = pos.x() <= m
        right = pos.x() >= w - m
        top = pos.y() <= m
        bottom = pos.y() >= h - m

        if top and left:
            return "topleft"
        if top and right:
            return "topright"
        if bottom and left:
            return "bottomleft"
        if bottom and right:
            return "bottomright"
        if top:
            return "top"
        if bottom:
            return "bottom"
        if left:
            return "left"
        if right:
            return "right"
        return ""

    # --- 把原来的 mousePress/move/release 逻辑抽成通用方法 ---
    def _handle_mouse_press_at(self, pos_in_window: QPoint, global_pos: QPoint, button: Qt.MouseButton):
        if button == Qt.LeftButton:
            dir_ = self._hit_test(pos_in_window)
            if dir_ and not self.isMaximized():
                # 开始缩放（支持角落斜向）
                self._resizing = True
                self._resize_dir = dir_
                self._start_geom = self.geometry()
                self._start_mouse_pos = global_pos
            else:
                # 拖动移动
                self._drag_pos = global_pos - self.frameGeometry().topLeft()
        self._update_header_visibility(pos_in_window)

    def _handle_mouse_move_at(self, pos_in_window: QPoint, global_pos: QPoint, buttons: Qt.MouseButtons):
        if buttons & Qt.LeftButton:
            if self._resizing and self._start_geom is not None and self._start_mouse_pos is not None:
                delta = global_pos - self._start_mouse_pos
                geom = QRect(self._start_geom)

                # 非常小的下限，基本等于随意缩放
                min_w, min_h = 50, 40

                dir_ = self._resize_dir or ""
                if "right" in dir_:
                    new_w = max(min_w, geom.width() + delta.x())
                    geom.setWidth(new_w)
                if "bottom" in dir_:
                    new_h = max(min_h, geom.height() + delta.y())
                    geom.setHeight(new_h)
                if "left" in dir_:
                    new_x = geom.x() + delta.x()
                    new_w = max(min_w, geom.width() - delta.x())
                    geom.setX(new_x)
                    geom.setWidth(new_w)
                if "top" in dir_:
                    new_y = geom.y() + delta.y()
                    new_h = max(min_h, geom.height() - delta.y())
                    geom.setY(new_y)
                    geom.setHeight(new_h)

                self.setGeometry(geom)
            elif self._drag_pos is not None:
                self.move(global_pos - self._drag_pos)

        # 不改光标形状，保持箭头
        self._update_header_visibility(pos_in_window)

    def _handle_mouse_release_at(self, pos_in_window: QPoint):
        self._drag_pos = None
        self._resizing = False
        self._resize_dir = None
        self._start_geom = None
        self._start_mouse_pos = None
        self._update_header_visibility(pos_in_window)

    # --- 重载顶层窗口的鼠标事件（用于点击透明区） ---
    def mousePressEvent(self, event):
        pos_win = event.position().toPoint()
        global_pos = event.globalPosition().toPoint()
        self._handle_mouse_press_at(pos_win, global_pos, event.button())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        pos_win = event.position().toPoint()
        global_pos = event.globalPosition().toPoint()
        self._handle_mouse_move_at(pos_win, global_pos, event.buttons())
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        pos_win = event.position().toPoint()
        self._handle_mouse_release_at(pos_win)
        super().mouseReleaseEvent(event)

    # --- 针对 card 的事件过滤（让边缘缩放在卡片上也能用） ---
    def eventFilter(self, obj, event):
        if obj is self.card:
            if event.type() == QEvent.MouseButtonPress:
                mouse = event
                pos_card = mouse.position().toPoint()
                pos_win = self.card.mapToParent(pos_card)
                global_pos = mouse.globalPosition().toPoint()
                self._handle_mouse_press_at(pos_win, global_pos, mouse.button())
                if self._resizing or self._drag_pos is not None:
                    return True
            elif event.type() == QEvent.MouseMove:
                mouse = event
                pos_card = mouse.position().toPoint()
                pos_win = self.card.mapToParent(pos_card)
                global_pos = mouse.globalPosition().toPoint()
                self._handle_mouse_move_at(pos_win, global_pos, mouse.buttons())
                if self._resizing or self._drag_pos is not None:
                    return True
            elif event.type() == QEvent.MouseButtonRelease:
                mouse = event
                pos_card = mouse.position().toPoint()
                pos_win = self.card.mapToParent(pos_card)
                self._handle_mouse_release_at(pos_win)
                if self._resizing or self._drag_pos is not None:
                    return True
        return super().eventFilter(obj, event)

    def closeEvent(self, event: QCloseEvent):
        event.ignore()
        self.hide()

    def refresh(self):
        """根据当前 active_goal 刷新整个卡片 UI。"""
        goal = self.app.get_active_goal()
        self.action_list.blockSignals(True)
        self.action_list.clear()

        if goal is None:
            self.current_label.setText("当前没有进行中的专注卡片。")
            self.long_term_label.setText("")
            self.action_list.blockSignals(False)
            self.toggle_all_button.setText("全选")
            return

        self.current_label.setText(goal["current_goal"])
        self.long_term_label.setText(f"长期目标：{goal['long_term']}")

        any_undone = False

        for idx, action in enumerate(goal["actions"]):
            display_text = f"{idx + 1}. {action['text']}"
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

            if not action.get("done"):
                any_undone = True

            self.action_list.addItem(item)

        self.toggle_all_button.setText("全选" if any_undone else "全清")
        self.action_list.blockSignals(False)

    def on_item_changed(self, item: QListWidgetItem):
        """
        勾选状态或文本变化时，仅把变化同步到数据层；
        视觉样式由 refresh() 统一更新，避免访问已经被删除的 item。
        """
        action_id = item.data(Qt.UserRole)
        if not action_id:
            return
        raw = item.text()
        text = strip_leading_number(raw)
        done = item.checkState() == Qt.Checked
        self.app.modify_action_from_card(action_id, text=text, done=done)


# --------- 创建页的“已添加动作列表”（支持拖拽 + 右键删除 + 双击空白新增） ---------
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
        delete_action = menu.addAction("删除此关键动作")
        chosen = menu.exec_(self.mapToGlobal(pos))
        if chosen == delete_action:
            row = self.row(item)
            self.takeItem(row)
            self.app.renumber_pending_actions()

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        if item is None:
            # 双击空白区域：新增一行并进入编辑
            new_item = QListWidgetItem("新关键动作")
            new_item.setFlags(
                Qt.ItemIsEnabled
                | Qt.ItemIsSelectable
                | Qt.ItemIsEditable
                | Qt.ItemIsDragEnabled
            )
            self.addItem(new_item)
            self.app.renumber_pending_actions()
            self.setCurrentItem(new_item)
            self.editItem(new_item)
        else:
            super().mouseDoubleClickEvent(event)


# --------- 主窗口（规划 + 归档） ---------
class GoalApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("专注目标")
        self.resize(780, 540)

        self.store = load_data()
        self.focus_window: FocusWindow | None = None
        self._celebration_overlay = None

        self._audio_output = QAudioOutput()
        self._player = QMediaPlayer()
        self._player.setAudioOutput(self._audio_output)

        self.build_ui()
        self.refresh_main_state()

    # --- 构建 UI ---
    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(10, 10, 10, 10)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        self.plan_tab = QWidget()
        self.archive_tab = QWidget()
        self.tabs.addTab(self.plan_tab, "规划")
        self.tabs.addTab(self.archive_tab, "归档")

        self.build_plan_tab()
        self.build_archive_tab()

    def build_plan_tab(self):
        w = self.plan_tab
        layout = QVBoxLayout(w)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        title = QLabel("设计你下一件最重要的事")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        # --- 输入区域 ---
        input_group = QGroupBox("新建专注卡片")
        input_layout = QVBoxLayout(input_group)
        input_layout.setSpacing(6)

        # 行 1：长期目标
        lt_layout = QHBoxLayout()
        lt_label = QLabel("长期目标：")
        lt_label.setStyleSheet("font-size: 12px;")
        self.long_term_edit = QLineEdit()
        self.long_term_edit.setPlaceholderText("例如：成为能自由使用英语工作的自己")
        self.long_term_edit.setStyleSheet("font-size: 12px;")
        lt_layout.addWidget(lt_label)
        lt_layout.addWidget(self.long_term_edit)
        input_layout.addLayout(lt_layout)

        # 行 2：当下目标
        cg_layout = QHBoxLayout()
        cg_label = QLabel("当下目标：")
        cg_label.setStyleSheet("font-size: 12px;")
        self.current_goal_edit = QLineEdit()
        self.current_goal_edit.setPlaceholderText("例如：今天完成一次 30 分钟口语练习")
        self.current_goal_edit.setStyleSheet("font-size: 12px;")
        cg_layout.addWidget(cg_label)
        cg_layout.addWidget(self.current_goal_edit)
        input_layout.addLayout(cg_layout)

        # 行 3：关键动作输入
        action_input_layout = QHBoxLayout()
        action_label = QLabel("关键动作：")
        action_label.setStyleSheet("font-size: 12px;")
        self.action_input_edit = QLineEdit()
        self.action_input_edit.setPlaceholderText("输入关键动作，回车添加")
        self.action_input_edit.setStyleSheet("font-size: 12px;")
        # 回车：按照输入框内容添加，并清空（恢复之前行为）
        self.action_input_edit.returnPressed.connect(self.add_pending_action_from_text)
        self.add_action_btn = QPushButton("添加动作")
        self.add_action_btn.setStyleSheet("font-size: 12px;")
        # 按钮也改回“按输入框内容添加，并清空”
        self.add_action_btn.clicked.connect(self.add_pending_action_from_text)
        action_input_layout.addWidget(action_label)
        action_input_layout.addWidget(self.action_input_edit)
        action_input_layout.addWidget(self.add_action_btn)
        input_layout.addLayout(action_input_layout)

        # 行 4：已添加的关键动作列表
        pa_group = QGroupBox("已添加的关键动作（优先级 1 / 2 / 3 ...）")
        pa_layout = QVBoxLayout(pa_group)

        hint_label = QLabel("提示：双击空白新增行，双击文字编辑，拖拽调整顺序，右键删除。")
        hint_label.setStyleSheet("color: #777777; font-size: 11px;")
        pa_layout.addWidget(hint_label)

        list_and_button_layout = QHBoxLayout()
        self.pending_actions_list = PendingActionListWidget(self)
        list_and_button_layout.addWidget(self.pending_actions_list)

        self.remove_pending_action_btn = QPushButton("删除选中")
        self.remove_pending_action_btn.setStyleSheet("font-size: 12px;")
        self.remove_pending_action_btn.clicked.connect(self.remove_selected_pending_action)
        list_and_button_layout.addWidget(self.remove_pending_action_btn)

        pa_layout.addLayout(list_and_button_layout)

        self.pending_actions_list.itemChanged.connect(self.on_pending_item_changed)

        input_layout.addWidget(pa_group)

        # 行 5：创建按钮 + 提示
        bottom_layout = QHBoxLayout()
        self.status_label = QLabel("一次只能有一张进行中的专注卡片，完成后才能创建新的。")
        self.status_label.setStyleSheet("color: #777777; font-size: 11px;")
        self.create_btn = QPushButton("创建专注卡片")
        self.create_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.create_btn.clicked.connect(self.create_goal_from_input)
        bottom_layout.addWidget(self.status_label)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.create_btn)

        input_layout.addLayout(bottom_layout)
        layout.addWidget(input_group)

        # --- 当前专注卡片概要 + 进度 ---
        summary_group = QGroupBox("当前专注卡片")
        summary_layout = QVBoxLayout(summary_group)
        summary_layout.setSpacing(4)

        self.summary_title_label = QLabel("当前没有进行中的专注卡片。")
        self.summary_title_label.setStyleSheet("font-size: 13px;")
        self.summary_title_label.setWordWrap(True)

        self.summary_progress_bar = QProgressBar()
        self.summary_progress_bar.setMinimum(0)
        self.summary_progress_bar.setMaximum(100)

        self.summary_progress_text = QLabel("")
        self.summary_progress_text.setStyleSheet("color: #666666; font-size: 11px;")

        self.summary_actions_label = QLabel("")
        self.summary_actions_label.setWordWrap(True)
        self.summary_actions_label.setStyleSheet("color: #444444; font-size: 11px;")

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.open_focus_btn = QPushButton("打开专注卡片")
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

        title = QLabel("已完成的专注卡片")
        title.setStyleSheet("font-size: 15px; font-weight: bold;")
        layout.addWidget(title)

        self.token_info_label = QLabel("")
        self.token_info_label.setStyleSheet("color: #555555; font-size: 11px;")
        layout.addWidget(self.token_info_label)

        self.archive_table = QTableWidget(0, 4)
        self.archive_table.setHorizontalHeaderLabels(
            ["长期目标", "当下目标", "创建时间", "完成时间"]
        )
        self.archive_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.archive_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.archive_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.archive_table.itemSelectionChanged.connect(self.on_archive_selection_changed)
        self.archive_table.setStyleSheet("font-size: 12px;")
        layout.addWidget(self.archive_table, stretch=1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.delete_with_token_btn = QPushButton("使用删除机会删除选中卡片")
        self.delete_with_token_btn.setStyleSheet("font-size: 12px; padding: 4px 10px;")
        self.delete_with_token_btn.clicked.connect(self.delete_archive_item_with_token)
        btn_layout.addWidget(self.delete_with_token_btn)
        layout.addLayout(btn_layout)

        detail_group = QGroupBox("卡片详情")
        d_layout = QVBoxLayout(detail_group)
        self.archive_detail = QTextEdit()
        self.archive_detail.setReadOnly(True)
        self.archive_detail.setStyleSheet("font-size: 12px;")
        d_layout.addWidget(self.archive_detail)
        layout.addWidget(detail_group, stretch=1)

    # --- 工具方法 ---
    def get_active_goal(self):
        return self.store.get("active_goal")

    # --- 规划 Tab：待创建动作列表 ---
    def add_pending_action_from_text(self):
        """使用输入框内容添加动作，并清空输入框。"""
        text = self.action_input_edit.text().strip()
        if not text:
            return
        item = QListWidgetItem(text)
        item.setFlags(
            Qt.ItemIsEnabled
            | Qt.ItemIsSelectable
            | Qt.ItemIsEditable
            | Qt.ItemIsDragEnabled
        )
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

    # --- 主状态刷新 ---
    def refresh_main_state(self):
        goal = self.get_active_goal()

        if goal is None:
            self.status_label.setText("一次只能有一张进行中的专注卡片，当前没有进行中的卡片。")
            self.create_btn.setEnabled(True)

            self.summary_title_label.setText("当前没有进行中的专注卡片。")
            self.summary_progress_bar.setValue(0)
            self.summary_progress_text.setText("")
            self.summary_actions_label.setText("")
            self.open_focus_btn.setEnabled(False)
        else:
            self.status_label.setText("已经有一张进行中的卡片，完成后才能创建新的。")
            self.create_btn.setEnabled(False)

            title = f"{goal['long_term']} → {goal['current_goal']}"
            self.summary_title_label.setText(title)

            total = len(goal["actions"])
            done = sum(1 for a in goal["actions"] if a.get("done"))
            ratio = int((done / total) * 100) if total > 0 else 0
            self.summary_progress_bar.setValue(ratio)
            self.summary_progress_text.setText(f"{done} / {total} 个关键动作已完成")

            undone = [a["text"] for a in goal["actions"] if not a.get("done")]
            if undone:
                lines = ["正在进行中的关键动作："]
                for idx, t in enumerate(undone, start=1):
                    lines.append(f"{idx}. {t}")
                self.summary_actions_label.setText("\n".join(lines))
            else:
                self.summary_actions_label.setText("所有关键动作已完成，可以在专注卡片中点击「完成卡片」。")

            self.open_focus_btn.setEnabled(True)

        self.refresh_archive_tab()

        if self.focus_window is not None and self.focus_window.isVisible():
            self.focus_window.refresh()

    # --- 创建新卡片 ---
    def create_goal_from_input(self):
        if self.get_active_goal() is not None:
            QMessageBox.information(
                self,
                "已有进行中的卡片",
                "你当前已经有一张进行中的专注卡片，请先完成它，再创建新的。",
            )
            return

        long_term = self.long_term_edit.text().strip()
        current_goal = self.current_goal_edit.text().strip()

        if not long_term or not current_goal:
            QMessageBox.warning(self, "信息不完整", "请填写【长期目标】和【当下目标】。")
            return

        actions_texts = []
        for i in range(self.pending_actions_list.count()):
            raw = self.pending_actions_list.item(i).text()
            t = strip_leading_number(raw)
            if t:
                actions_texts.append(t)

        if not actions_texts:
            QMessageBox.warning(self, "没有关键动作", "请至少添加一个【关键动作】。")
            return

        actions = []
        for text in actions_texts:
            actions.append(
                {
                    "id": str(uuid.uuid4()),
                    "text": text,
                    "done": False,
                    "created_at": now_str(),
                    "completed_at": None,
                }
            )

        goal = {
            "id": str(uuid.uuid4()),
            "long_term": long_term,
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

        self.refresh_main_state()
        self.open_focus_window()

    # --- 悬浮卡片 ---
    def open_focus_window(self):
        goal = self.get_active_goal()
        if goal is None:
            QMessageBox.information(self, "没有卡片", "当前没有进行中的专注卡片。")
            return

        if self.focus_window is None:
            self.focus_window = FocusWindow(self)

        self.focus_window.refresh()
        self.focus_window.show()
        self.focus_window.raise_()
        self.focus_window.activateWindow()

    def add_action_from_card(self, text: str):
        goal = self.get_active_goal()
        if goal is None:
            return
        goal["actions"].append(
            {
                "id": str(uuid.uuid4()),
                "text": text,
                "done": False,
                "created_at": now_str(),
                "completed_at": None,
            }
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
        # 单个关键动作完成 -> 小窗口动效
        if celebrate_action:
            self.show_celebration(kind="action", goal=goal)

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
                "删除卡片",
                "这是最后一个关键动作，如果删除，将一起删除整张专注卡片。\n确定要继续吗？",
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
        # 一键全选时不连环放烟花

    def finish_goal_if_completed_from_card(self):
        goal = self.get_active_goal()
        if goal is None:
            return
        if not goal["actions"]:
            QMessageBox.warning(self, "无法完成", "这张卡片没有任何关键动作，无法标记为完成。")
            return
        if not all(a.get("done") for a in goal["actions"]):
            QMessageBox.information(
                self,
                "尚未完成",
                "还有关键动作没有完成，请先勾选完成全部关键动作。",
            )
            return

        goal["done"] = True
        goal["completed_at"] = now_str()

        self.store.setdefault("archive", []).insert(0, goal)
        self.store["total_completed_count"] = self.store.get("total_completed_count", 0) + 1
        self.store["active_goal"] = None
        save_data(self.store)

        # 整张卡片完成 -> 全屏动效
        self.show_celebration(kind="card", goal=goal)
        self.refresh_main_state()

        # 自动关闭悬浮窗，并切回规划页面
        if self.focus_window is not None:
            self.focus_window.hide()
        self.tabs.setCurrentWidget(self.plan_tab)

    # --- 播放 mp3 音效 ---
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

    # --- 小窗口 & 全屏庆祝动画 ---
    def show_celebration(self, kind: str, goal: dict | None = None):
        """
        kind = "action" -> 小窗口动效（GIF + 奖杯 + 文案），不再给 pic.png 加黑色底板
        kind = "card"   -> 全屏动效（GIF 全屏 + 奖杯 + 文案），透明叠在桌面上
        """
        self.play_reward_sound()

        # 先把之前的遮罩关掉
        if self._celebration_overlay is not None:
            self._celebration_overlay.close()
            self._celebration_overlay = None

        if kind == "action":
            # 小窗口：居中显示 GIF + 奖杯 + 文案，不再有整体黑色卡片，只给文字小块黑底
            overlay = QWidget(
                None,
                Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
            )
            overlay.setAttribute(Qt.WA_TranslucentBackground, True)

            # 放大小通知窗口尺寸
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

            # GIF 动效（尺寸加大）
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

            # 奖杯图片（背景透明，不加黑底）
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

            # 文案：用小块半透明黑底，避免影响 pic.png 透明区域
            msg = QLabel("关键动作完成，继续保持节奏！")
            msg.setStyleSheet(
            "color: white; font-size: 16px; background-color: rgba(255,183,60,180); padding: 10px 20px; border-radius: 12px;"
            )
            msg.setWordWrap(True)
            msg.setAlignment(Qt.AlignCenter)
            msg.setMinimumWidth(480)
            msg.setMaximumWidth(700)
            root_layout.addWidget(msg, alignment=Qt.AlignCenter)

            overlay.setWindowOpacity(1.0)
            self._celebration_overlay = overlay
            overlay.show()

            # 使用淡出动画，让消失不那么突然
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

            QTimer.singleShot(3200, start_fade_out)
            return

        # ========== kind != "action"，视为整张卡片完成，全屏动效 ==========
        overlay = QWidget(
            None,
            Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool,
        )
        # 透明背景，只显示 GIF + 奖杯 + 文案
        overlay.setAttribute(Qt.WA_TranslucentBackground, True)
        overlay.showFullScreen()

        root_layout = QVBoxLayout(overlay)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setAlignment(Qt.AlignCenter)

        screen = QApplication.primaryScreen()
        screen_size = screen.size() if screen is not None else QSize(1920, 1080)

        # 全屏 GIF（透明窗口，不盖黑幕）
        if REWARD_ANIMATION_GIF_PATH and os.path.exists(REWARD_ANIMATION_GIF_PATH):
            anim_label = QLabel(overlay)
            anim_label.setMinimumSize(screen_size)
            anim_label.setMaximumSize(screen_size)
            anim_label.setScaledContents(True)
            movie = QMovie(REWARD_ANIMATION_GIF_PATH)
            movie.setScaledSize(screen_size)
            anim_label.setMovie(movie)
            movie.start()
            overlay._movie = movie
            root_layout.addWidget(anim_label, alignment=Qt.AlignCenter)
        else:
            anim_label = QLabel("🎉", overlay)
            anim_label.setStyleSheet("font-size: 72px; color: white;")
            anim_label.setAlignment(Qt.AlignCenter)
            root_layout.addWidget(anim_label, alignment=Qt.AlignCenter)

        # 中央叠一块奖杯 + 文案（覆盖在 GIF 上）
        info_box = QWidget(overlay)
        info_box.setAttribute(Qt.WA_TranslucentBackground, True)
        info_layout = QVBoxLayout(info_box)
        info_layout.setContentsMargins(16, 16, 16, 16)
        info_layout.setSpacing(10)
        info_layout.setAlignment(Qt.AlignCenter)

        badge_shown = False
        if REWARD_BADGE_PATH and os.path.exists(REWARD_BADGE_PATH):
            pix = QPixmap(REWARD_BADGE_PATH)
            if not pix.isNull():
                badge_label = QLabel()
                pix = pix.scaled(160, 160, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                badge_label.setPixmap(pix)
                badge_label.setAlignment(Qt.AlignCenter)
                badge_label.setStyleSheet("background: transparent;")
                info_layout.addWidget(badge_label, alignment=Qt.AlignCenter)
                badge_shown = True
        if not badge_shown:
            fallback_label = QLabel("🏆")
            fallback_label.setAlignment(Qt.AlignCenter)
            fallback_label.setStyleSheet("font-size: 56px; background: transparent;")
            info_layout.addWidget(fallback_label, alignment=Qt.AlignCenter)

        msg_label = QLabel()
        msg_label.setStyleSheet(
            "color: white; font-size: 19px; background-color: rgba(255,128,0,200); padding: 10px 20px; border-radius: 12px;"
        )
        msg_label.setWordWrap(True)
        msg_label.setMinimumWidth(440)
        msg_label.setMaximumWidth(680)
        msg_label.setAlignment(Qt.AlignCenter)

        if goal is not None:
            msg_label.setText(f"专注卡片完成：{goal.get('current_goal', '')}")
        else:
            msg_label.setText("专注卡片完成，干得漂亮！")

        info_layout.addWidget(msg_label, alignment=Qt.AlignCenter)

        info_box.adjustSize()
        # 居中放置 info_box
        screen_w = screen_size.width()
        screen_h = screen_size.height()
        box_w = info_box.width()
        box_h = info_box.height()
        info_box.setGeometry(
            (screen_w - box_w) // 2,
            (screen_h - box_h) // 2,
            box_w,
            box_h,
        )
        info_box.raise_()  # 确保在 GIF 上层

        self._celebration_overlay = overlay

        def close_overlay():
            if self._celebration_overlay is not None:
                self._celebration_overlay.close()
                self._celebration_overlay = None

        QTimer.singleShot(3300, close_overlay)

    # --- 归档 ---
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
            f"累计完成 {total_completed} 张专注卡片，可用删除机会：{available_tokens} 次。"
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
            QMessageBox.information(self, "没有删除机会", "当前没有可用的删除机会。")
            return

        rows = self.archive_table.selectionModel().selectedRows()
        if not rows:
            QMessageBox.information(self, "未选择卡片", "请先在列表中选择一条要删除的卡片。")
            return
        row = rows[0].row()
        if row < 0 or row >= len(archive):
            return

        g = archive[row]
        reply = QMessageBox.question(
            self,
            "确认删除",
            f"将消耗一次删除机会，删除卡片：\n\n{g.get('current_goal','')}\n\n确定要删除吗？",
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
        lines.append(f"长期目标：{g.get('long_term','')}")
        lines.append(f"当下目标：{g.get('current_goal','')}")
        lines.append(f"创建时间：{g.get('created_at','')}")
        lines.append(f"完成时间：{g.get('completed_at','')}")
        lines.append("")
        lines.append("关键动作：")
        for idx, a in enumerate(g.get("actions", []), start=1):
            text = a.get("text", "")
            if a.get("completed_at"):
                lines.append(f"{idx}. {text}（完成于 {a['completed_at']}）")
            else:
                lines.append(f"{idx}. {text}")
        self.archive_detail.setPlainText("\n".join(lines))


def main():
    app = QApplication(sys.argv)
    QApplication.setStyle("Fusion")
    window = GoalApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
