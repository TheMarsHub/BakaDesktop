import sys
import locale
import pygame
import os
import json
import winreg
import numpy as np
import pyaudiowpatch as pyaudio
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QMenu, QSystemTrayIcon, QAction
from PyQt5.QtCore import Qt, QTimer, QPoint, QSize
from PyQt5.QtGui import QPixmap, QImage, QFont, QPainter, QColor, QMovie, QIcon
from PIL import Image
from Language import TRANSLATIONS
from size_editor import SizeEditor
from speed_editor import SpeedEditor


class Explosion(QWidget):
    def __init__(self, pos, size):
        super().__init__()
        self.explosion_size = int(size * 2)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        offset = (self.explosion_size - size) // 2
        self.setGeometry(pos.x() - offset, pos.y() - offset, self.explosion_size, self.explosion_size)
        self.label = QLabel(self)
        self.label.setFixedSize(self.explosion_size, self.explosion_size)
        self.label.setStyleSheet("background:transparent;")
        self.movie = QMovie(os.path.join('data', 'img', "explosion.gif"))
        self.setAttribute(Qt.WA_TranslucentBackground)

        if self.movie.isValid():
            self.movie.setScaledSize(QSize(self.explosion_size, self.explosion_size))
            self.label.setMovie(self.movie)
            self.movie.finished.connect(QApplication.instance().quit)
            self.movie.start()
        else:
            QTimer.singleShot(1000, QApplication.instance().quit)
        QTimer.singleShot(1140, QApplication.instance().quit)

class PersistentMenu(QMenu):
    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action:
            if action.menu() is None:
                action.trigger()
                if isinstance(self.parent(), QMenu):
                    return
        super().mouseReleaseEvent(event)

class Baka(QWidget):
    def __init__(self, sprite_path):
        super().__init__()
        system_lang = locale.getdefaultlocale()[0][:2].lower()
        self.current_lang = system_lang if system_lang in TRANSLATIONS else 'en'
        self.load_settings()
        self.mode = 'funky'
        self.sprite_path = sprite_path
        self.dance_frames = []
        self.static_frames = []
        self.bottle_frame = None
        self.current_frame_idx = 0
        self.is_dragging = False
        self.drag_position = QPoint()
        pygame.mixer.init()
        self.current_sound = None
        self.is_looping = False
        self.active_sound_name = ""
        self.speed_window = None
        self.orig_dance_frames = []

        self.audio_volume = 0
        self.audio_threshold = 0.01
        self.p = pyaudio.PyAudio()
        self.stream = None
        try:
            wasapi_info = self.p.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self.p.get_default_output_device_info()
            loopback_device = self.p.get_loopback_device_info_generator()

            target_device = None
            for device in loopback_device:
                if default_speakers["name"] in device["name"]:
                    target_device = device
                    break

            if not target_device:
                target_device = self.p.get_default_wasapi_loopback()

            self.stream = self.p.open(
                format=pyaudio.paFloat32,
                channels=target_device["maxInputChannels"],
                rate=int(target_device["defaultSampleRate"]),
                input=True,
                input_device_index=target_device["index"],
                stream_callback=self.audio_callback
            )
        except:
            pass

        self.orig_dance_frames = []
        self.orig_static_frames = []
        self.orig_bottle_frame = None
        self.size_window = None
        self.initUI()
        self.loadSprites()
        self.initAnimation()
        self.rainbow_enabled = False
        self.shadow_history = []
        self.shadow_colors = [
            Qt.red, Qt.darkYellow, Qt.yellow, Qt.green,
            Qt.cyan, Qt.blue, Qt.magenta
        ]
        self.blue_shadow_enabled = False
        self.cirno_blue = QColor("#B2EBF2")
        if hasattr(self, 'saved_pos') and self.saved_pos:
            self.move(self.saved_pos)
        self.init_tray()
        self.show()

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)

        self.resize(154, 154)
        self.label.resize(154, 154)

    def pil_to_pixmap(self, pil_img):
        if pil_img.mode != "RGBA":
            pil_img = pil_img.convert("RGBA")

        data = pil_img.tobytes("raw", "RGBA")
        qim = QImage(data, pil_img.size[0], pil_img.size[1], QImage.Format_RGBA8888)
        return QPixmap.fromImage(qim)

    def loadSprites(self):
        try:
            img = Image.open(self.sprite_path).convert("RGBA")
        except:
            sys.exit()

        L = img.convert('L')
        mask = L.point(lambda x: 0 if x < 10 else 255, '1')
        img.putalpha(mask)
        cols = 8
        rows = 10
        w, h = img.size
        frame_w = w // cols
        frame_h = h // rows

        for c in range(cols):
            box = (c * frame_w, 0, (c + 1) * frame_w, frame_h)
            frame = img.crop(box)
            self.orig_static_frames.append(self.pil_to_pixmap(frame))

        for r in range(1, 9):
            for c in range(cols):
                box = (c * frame_w, r * frame_h, (c + 1) * frame_w, (r + 1) * frame_h)
                frame = img.crop(box)
                self.orig_dance_frames.append(self.pil_to_pixmap(frame))

        box_bottle = (0, 9 * frame_h, frame_w, 10 * frame_h)
        bottle_img = img.crop(box_bottle)
        self.orig_bottle_frame = self.pil_to_pixmap(bottle_img)

        self.apply_fumo_size(self.current_fumo_size)

    def audio_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=np.float32)
        if len(audio_data) > 0:
            self.audio_volume = np.linalg.norm(audio_data) / np.sqrt(len(audio_data))
        return (None, pyaudio.paContinue)

    def play_sfx(self, sound_name):
        if not isinstance(sound_name, str):
            return
        if self.current_sound:
            self.current_sound.stop()
        try:
            full_path = os.path.join('data', 'sound', f"{sound_name}.mp3")
            self.current_sound = pygame.mixer.Sound(full_path)
            loops = -1 if self.is_looping else 0
            self.current_sound.play(loops=loops)
            self.active_sound_name = sound_name
        except:
            pass

    def toggle_loop(self):
        self.is_looping = not self.is_looping
        if self.current_sound and self.active_sound_name:
            self.play_sfx(self.active_sound_name)

    def initAnimation(self):
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.updateFrame)
        interval = 70 + (50 - self.current_speed_pct)
        self.timer.start(interval)

    def updateFrame(self):
        if self.is_dragging:
            return

        if self.rainbow_enabled or self.blue_shadow_enabled:
            self.shadow_history.insert(0, (self.pos(), self.label.pixmap().copy()))
            if len(self.shadow_history) > len(self.shadow_colors):
                self.shadow_history.pop()
            self.update()

        if self.mode == 'funky':
            if self.dance_frames:
                self.current_frame_idx = (self.current_frame_idx + 1) % len(self.dance_frames)
                self.label.setPixmap(self.dance_frames[self.current_frame_idx])

        elif self.mode == 'sound':
            if (self.audio_volume * 10) > self.audio_threshold:
                if self.dance_frames:
                    self.current_frame_idx = (self.current_frame_idx + 1) % len(self.dance_frames)
                    self.label.setPixmap(self.dance_frames[self.current_frame_idx])
            else:
                if self.static_frames:
                    self.label.setPixmap(self.static_frames[0])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            self.label.setPixmap(self.bottle_frame)

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.is_dragging:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
            if self.dance_frames:
                self.label.setPixmap(self.dance_frames[self.current_frame_idx])
            self.save_settings()
            event.accept()

    def contextMenuEvent(self, event):
        self.show_custom_menu(event.globalPos())

    def show_custom_menu(self, pos):
        if self.active_sound_name != "" and not pygame.mixer.get_busy() and not self.is_looping:
            self.active_sound_name = ""

        text = TRANSLATIONS[self.current_lang]
        menu = PersistentMenu(self)

        bold_font = QFont()
        bold_font.setBold(True)
        normal_font = QFont()

        def add_item(target_menu, title, callback, is_selected):
            prefix = "⑨    " if is_selected else "         "
            action = target_menu.addAction(f"{prefix}{title}")
            action.setFont(bold_font if is_selected else normal_font)

            def handle_trigger():
                callback()
                if self.isVisible():
                    self.update_menu_icons(menu)

            action.triggered.connect(handle_trigger)

        self.build_menu_tree(menu, add_item, text)
        menu.exec_(pos)

    def build_menu_tree(self, menu, add_item, text):
        m_menu = PersistentMenu(text['mode'], menu)
        menu.addMenu(m_menu)
        add_item(m_menu, "Funky", lambda: setattr(self, 'mode', 'funky'), self.mode == 'funky')
        add_item(m_menu, text['sound'], lambda: setattr(self, 'mode', 'sound'), self.mode == 'sound')

        l_menu = PersistentMenu(text['layers'], menu)
        menu.addMenu(l_menu)
        ontop = bool(self.windowFlags() & Qt.WindowStaysOnTopHint)
        add_item(l_menu, text['on_top'], lambda: self.set_on_top(True), ontop)
        add_item(l_menu, text['standard'], lambda: self.set_on_top(False), not ontop)

        shadow_menu = PersistentMenu(text['shadow'], menu)
        menu.addMenu(shadow_menu)
        add_item(shadow_menu, text['rainbow'], self.toggle_rainbow, self.rainbow_enabled)
        add_item(shadow_menu, text['blue_shadow'], self.toggle_blue_shadow, self.blue_shadow_enabled)

        s_menu = PersistentMenu(text['sound_play'], menu)
        menu.addMenu(s_menu)
        s_list = [
            ("Baka", "Baka"),
            ("Funky", "Funky"),
            ("Chi Chi Miru", "Chi_Chi_Miru"),
            ("Scarlet Police on Ghetto Patrol", "Scarlet_Police_on_Ghetto_Patrol"),
            ("Cirno Perfect Math Class", "Cirno_Perfect_Math_Class")
        ]
        for d_name, f_name in s_list:
            add_item(s_menu, d_name, lambda n=f_name: self.play_sfx(n), self.active_sound_name == f_name)

        s_menu.addSeparator()
        add_item(s_menu, text['loop'], self.toggle_loop, self.is_looping)

        add_item(menu, text['speed'], self.open_speed_editor, False)

        add_item(menu, text['size'], self.open_size_editor, False)

        lang_menu = PersistentMenu(text['language'], menu)
        menu.addMenu(lang_menu)
        for code, data in TRANSLATIONS.items():
            add_item(lang_menu, data['system'], lambda c=code: self.change_lang(c), self.current_lang == code)

        auto_menu = PersistentMenu(text['autostart'], menu)
        menu.addMenu(auto_menu)
        add_item(auto_menu, text['autostart'], self.toggle_autostart, self.autostart_enabled)

        menu.addSeparator()
        def handle_exit():
            menu.close()
            if menu.parent():
                menu.parent().hide()
            if self.current_sound:
                self.current_sound.stop()
            self.explosion_win = Explosion(self.pos(), self.current_fumo_size)
            self.explosion_win.show()
            QApplication.processEvents()
            self.explosive_exit()

        add_item(menu, text['exit'], handle_exit, False)

    def update_menu_icons(self, menu):
        text = TRANSLATIONS[self.current_lang]
        self.active_menu_pos = menu.pos()
        menu.close()
        QTimer.singleShot(1, lambda: self.show_custom_menu(self.active_menu_pos))

    def set_on_top(self, enable):
        if enable:
            self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        else:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowStaysOnTopHint)
        self.show()

    def change_lang(self, lang_code):
        self.current_lang = lang_code

    def set_mode(self, mode):
        self.mode = mode
        if mode == 'sound':
            self.current_frame_idx = 0

    def closeEvent(self, event):
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()
        event.accept()

    def toggle_rainbow(self):
        self.rainbow_enabled = not self.rainbow_enabled
        if self.rainbow_enabled:
            self.blue_shadow_enabled = False
        else:
            self.shadow_history.clear()
        self.update()

    def toggle_blue_shadow(self):
        self.blue_shadow_enabled = not self.blue_shadow_enabled
        if self.blue_shadow_enabled:
            self.rainbow_enabled = False
        else:
            self.shadow_history.clear()
        self.update()

    def paintEvent(self, event):
        if not (self.rainbow_enabled or self.blue_shadow_enabled) or not self.shadow_history:
            return

        painter = QPainter(self)
        for i, (old_pos, pixmap) in enumerate(self.shadow_history):
            offset = old_pos - self.pos()
            color = self.shadow_colors[i] if self.rainbow_enabled else self.cirno_blue

            temp_pixmap = QPixmap(pixmap.size())
            temp_pixmap.fill(Qt.transparent)

            p2 = QPainter(temp_pixmap)
            p2.drawPixmap(0, 0, pixmap)
            p2.setCompositionMode(QPainter.CompositionMode_SourceIn)
            p2.fillRect(temp_pixmap.rect(), color)
            p2.end()

            painter.setOpacity(0.3 - (i * 0.04))
            painter.drawPixmap(offset, temp_pixmap)
        painter.end()

    def apply_fumo_size(self, size):
        self.current_fumo_size = size
        self.static_frames = [px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation) for px in
                              self.orig_static_frames]
        self.dance_frames = [px.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation) for px in
                             self.orig_dance_frames]

        if self.orig_bottle_frame:
            self.bottle_frame = self.orig_bottle_frame.scaled(size, size, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.setFixedSize(size, size)
        self.label.setFixedSize(size, size)
        if self.mode == 'funky' and self.dance_frames:
            self.label.setPixmap(self.dance_frames[self.current_frame_idx])
        elif self.static_frames:
            self.label.setPixmap(self.static_frames[0])

        self.update()
        self.save_settings()

    def open_size_editor(self):
        if self.size_window is None or not self.size_window.isVisible():
            self.size_window = SizeEditor(self.current_fumo_size, self.pos(), TRANSLATIONS[self.current_lang], self.current_lang)
            self.size_window.size_changed.connect(self.apply_fumo_size)
            self.size_window.show()
        else:
            self.size_window.close()

    def apply_speed(self, pct):
        self.current_speed_pct = pct
        new_interval = 70 + (50 - pct)
        self.timer.setInterval(max(1, new_interval))
        self.save_settings()

    def open_speed_editor(self):
        if self.speed_window is None or not self.speed_window.isVisible():
            self.speed_window = SpeedEditor(
                self.current_speed_pct,
                self.pos(),
                TRANSLATIONS[self.current_lang]
            )
            self.speed_window.speed_changed.connect(self.apply_speed)
            self.speed_window.show()
        else:
            self.speed_window.close()

    def explosive_exit(self):
        if self.current_sound:
            self.current_sound.stop()
        self.save_settings()
        self.hide()
        QApplication.processEvents()
        self.explosion_win = Explosion(self.pos(), self.current_fumo_size)
        self.explosion_win.show()
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            self.p.terminate()
        except:
            pass

    def load_settings(self):
        self.settings_file = "config.json"
        self.current_fumo_size = 154
        self.current_speed_pct = 50
        self.autostart_enabled = False
        self.saved_pos = None

        if os.path.exists(self.settings_file):
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.current_fumo_size = data.get("size", 154)
                    self.current_speed_pct = data.get("speed", 50)
                    self.autostart_enabled = data.get("autostart", False)
                    pos_x = data.get("pos_x")
                    pos_y = data.get("pos_y")
                    if pos_x is not None and pos_y is not None:
                        self.saved_pos = QPoint(pos_x, pos_y)
            except:
                pass

    def save_settings(self):
        data = {
            "size": self.current_fumo_size,
            "speed": self.current_speed_pct,
            "autostart": self.autostart_enabled,
            "pos_x": self.x(),
            "pos_y": self.y()
        }
        try:
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
        except:
            pass

    def toggle_autostart(self):
        self.autostart_enabled = not self.autostart_enabled
        self.save_settings()
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_ALL_ACCESS)
            app_name = "BakaDekstop"

            if self.autostart_enabled:
                if getattr(sys, 'frozen', False):
                    exec_path = f'"{sys.executable}"'
                else:
                    exec_path = f'"{sys.executable}" "{os.path.abspath(__file__)}"'

                winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exec_path)
            else:
                winreg.DeleteValue(key, app_name)

            winreg.CloseKey(key)
        except Exception as e:
            pass

    def init_tray(self):
        self.tray_icon = QSystemTrayIcon(self)
        if os.path.exists("fumo.png"):
            self.tray_icon.setIcon(QIcon("fumo.png"))
        else:
            if self.orig_static_frames:
                self.tray_icon.setIcon(QIcon(self.orig_static_frames[0]))
        tray_menu = QMenu()
        exit_action = tray_menu.addAction("Exit")
        exit_action.triggered.connect(self.explosive_exit)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.setToolTip("⑨")
        self.tray_icon.show()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    fumo = Baka('data/img/sprite.png')
    fumo.show()
    sys.exit(app.exec_())