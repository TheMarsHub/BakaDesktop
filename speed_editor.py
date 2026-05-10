import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import Qt, pyqtSignal, QPoint, QRect
from PyQt5.QtGui import QPainter, QPixmap, QColor, QFont, QPen


class SpeedEditor(QWidget):
    speed_changed = pyqtSignal(int)

    def __init__(self, current_pct, pos, text_dict):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.resize(250, 245)
        self.move(pos.x() + 180, pos.y())

        self.text_dict = text_dict
        self.cur_pct = current_pct

        self.bg_pix = QPixmap(os.path.join('data', 'img', "size_bg.png"))
        self.handle_pix = QPixmap(os.path.join('data', 'img', "slider_handle.png"))
        self.text_bg_pix = QPixmap(os.path.join('data', 'img', "text_bg.png"))
        self.icon_pix = QPixmap(os.path.join('data', 'img', "fumo_icon.png"))

        if not self.icon_pix.isNull():
            self.icon_pix.setMask(self.icon_pix.createMaskFromColor(Qt.black, Qt.MaskInColor))
        if not self.handle_pix.isNull():
            self.handle_pix.setMask(self.handle_pix.createMaskFromColor(Qt.black, Qt.MaskInColor))

        self.slider_rect = QRect(25, 110, 200, 4)
        self.update_handle_pos()

        self.dragging_slider = False
        self.dragging_win = False
        self.drag_pos = QPoint()

    def update_handle_pos(self):
        ratio = self.cur_pct / 99.0
        self.handle_x = int(self.slider_rect.x() + ratio * self.slider_rect.width())

    def update_from_mouse(self, x):
        x_min = self.slider_rect.x()
        x_max = self.slider_rect.right()
        x_clamped = max(x_min, min(x_max, x))
        ratio = (x_clamped - x_min) / self.slider_rect.width()
        new_pct = round(ratio * 99)

        if new_pct != self.cur_pct:
            self.cur_pct = new_pct
            self.update_handle_pos()
            self.speed_changed.emit(self.cur_pct)
            self.update()

    def get_speed_label(self):
        captions = self.text_dict.get('speed_captions', ["", "", "", "", "", ""])
        p = self.cur_pct
        if p < 10: return captions[0]
        if p < 50: return captions[1]
        if p == 50: return captions[2]
        if p <= 70: return captions[3]
        if p <= 90: return captions[4]
        return captions[5]  #⑨

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)

        if not self.bg_pix.isNull():
            p.drawPixmap(self.rect(), self.bg_pix)
        header_h = 35
        p.fillRect(0, 0, self.width(), header_h, Qt.black)
        if not self.icon_pix.isNull():
            p.drawPixmap(10, 8, 20, 20, self.icon_pix)

        p.setPen(Qt.white)
        p.setFont(QFont("Arial", 10, QFont.Bold))
        p.drawText(40, 23, self.text_dict.get('speed_title', 'Speed'))

        p.setFont(QFont("Verdana", 14, QFont.Black))
        p.drawText(self.width() - 35, 25, "✖")
        line_y = self.slider_rect.y()
        p.setPen(QPen(Qt.black, 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.slider_rect.left(), line_y, self.slider_rect.right(), line_y)
        p.setPen(QPen(QColor(100, 200, 255), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(self.slider_rect.left(), line_y, self.handle_x, line_y)
        h_w, h_h = 34, 52
        handle_rect = QRect(self.handle_x - h_w // 2, line_y - h_h // 2, h_w, h_h)
        if not self.handle_pix.isNull():
            p.drawPixmap(handle_rect, self.handle_pix)

        p.setPen(QPen(Qt.black, 2))
        p.drawRoundedRect(handle_rect, 6, 6)
        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.drawText(handle_rect, Qt.AlignCenter, f"{self.cur_pct}%")
        text_rect = QRect(0, 165, 250, 100)
        if not self.text_bg_pix.isNull():
            p.save()
            p.setClipRect(text_rect)
            draw_area = QRect(-10, 160, 270, 110)
            p.drawPixmap(draw_area, self.text_bg_pix)
            p.restore()

        p.setPen(Qt.black)
        p.setFont(QFont("Verdana", 18, QFont.Bold))
        p.drawText(text_rect.adjusted(0, -18, 0, -18), Qt.AlignCenter, self.get_speed_label())

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