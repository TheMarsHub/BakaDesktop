import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect, QSize
from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont, QPen, QImage


class SizeEditor(QWidget):
    size_changed = pyqtSignal(int)

    def __init__(self, current_size, pos, text_dict, lang_code):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.resize(250, 245)
        self.move(pos.x() + 180, pos.y())

        self.text_dict = text_dict

        self.bg_pix = QPixmap(os.path.join('data', 'img', "size_bg.png"))
        self.handle_pix = QPixmap(os.path.join('data', 'img', "slider_handle.png"))
        self.text_bg_pix = QPixmap(os.path.join('data', 'img', "text_bg.png"))
        self.icon_pix = QPixmap(os.path.join('data', 'img', "fumo_icon.png"))
        if not self.icon_pix.isNull():
            self.icon_pix.setMask(self.icon_pix.createMaskFromColor(Qt.black, Qt.MaskInColor))
        if not self.handle_pix.isNull():
            self.handle_pix.setMask(self.handle_pix.createMaskFromColor(Qt.black, Qt.MaskInColor))

        self.min_s = 64
        self.max_s = 664
        self.cur_size = current_size

        self.slider_rect = QRect(25, 110, 200, 4)
        self.update_handle_pos()

        self.dragging_slider = False
        self.dragging_win = False
        self.drag_pos = QPoint()

    def remove_black_background(self, path):
        return QPixmap(path)

    def update_handle_pos(self):
        ratio = (self.cur_size - self.min_s) / (self.max_s - self.min_s)
        self.handle_x = int(self.slider_rect.x() + ratio * self.slider_rect.width())

    def update_from_mouse(self, x):
        x_min = self.slider_rect.x()
        x_max = self.slider_rect.right()
        x_clamped = max(x_min, min(x_max, x))

        ratio = (x_clamped - x_min) / self.slider_rect.width()
        current_pct = int(ratio * 100)

        new_size = self.min_s + (current_pct * 6)

        if new_size != self.cur_size:
            self.cur_size = int(new_size)
            self.handle_x = x_min + int(current_pct * self.slider_rect.width() / 100)
            self.size_changed.emit(self.cur_size)
            self.update()

    def get_percentage(self):
        return (self.cur_size - 64) // 6

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if not self.bg_pix.isNull():
            p.drawPixmap(self.rect(), self.bg_pix)
        else:
            p.fillRect(self.rect(), Qt.white)

        # Панель
        header_h = 35
        p.fillRect(0, 0, self.width(), header_h, Qt.black)

        if not self.icon_pix.isNull():
            p.drawPixmap(10, 8, 20, 20, self.icon_pix)

        p.setPen(Qt.white)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(40, 23, self.text_dict.get('size_title', 'Размер Фумо'))

        # ЖИРНЫЙ КРЕСТИК
        p.setFont(QFont("Verdana", 14, QFont.Black))
        p.drawText(self.width() - 35, 25, "✖")

        # Ползунок
        line_y = self.slider_rect.y()
        p.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.slider_rect.left(), line_y, self.slider_rect.right(), line_y)
        p.setPen(QPen(QColor(100, 200, 255), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.slider_rect.left(), line_y, self.handle_x, line_y)

        # Ручка
        h_w, h_h = 34, 52
        handle_rect = QRect(self.handle_x - h_w // 2, line_y - h_h // 2, h_w, h_h)
        if not self.handle_pix.isNull():
            p.drawPixmap(handle_rect, self.handle_pix)

        p.setPen(QPen(Qt.black, 2))
        p.drawRoundedRect(handle_rect, 6, 6)

        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.drawText(handle_rect, Qt.AlignCenter, f"{self.get_percentage()}%")

        # Кристалл
        text_rect = QRect(0, 165, 250, 100)
        if not self.text_bg_pix.isNull():
            p.save()
            p.setClipRect(text_rect)
        draw_area = QRect(-10, 160, 270, 110)
        p.drawPixmap(draw_area, self.text_bg_pix)
        p.restore()

        p.setPen(Qt.black)
        p.setFont(QFont("Verdana", 24, QFont.Bold))
        text_move_up = -18
        p.drawText(text_rect.adjusted(0, text_move_up, 0, text_move_up), Qt.AlignCenter,
                   f"{self.cur_size} x {self.cur_size}")

    def mousePressEvent(self, event):
        if event.y() < 35:
            if event.x() > self.width() - 45:
                self.close()
            else:
                self.dragging_win = True
                self.drag_pos = event.globalPos() - self.pos()
        elif abs(event.y() - self.slider_rect.y()) < 30:
            self.dragging_slider = True
            self.update_from_mouse(event.x())

    def mouseMoveEvent(self, event):
        if self.dragging_win:
            self.move(event.globalPos() - self.drag_pos)
        elif self.dragging_slider:
            self.update_from_mouse(event.x())

    def mouseReleaseEvent(self, event):
        self.dragging_win = self.dragging_slider = False