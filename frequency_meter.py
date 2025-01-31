from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QDialog)
from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
from PyQt5.QtGui import QPainter, QPen, QColor, QBrush, QPainterPath, QFont, QTransform
import math
import serial

class FrequencyTunerDialog(QDialog):
    def __init__(self, target_frequency, serial_port, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ajuste de Frequência")
        self.setMinimumSize(600, 500)
        
        # Configurações iniciais
        self.target_frequency = target_frequency
        self.current_frequency = target_frequency
        self.range = 0.5  # Range de ±0.5 Hz
        self.serial_port = serial_port
        self.serial_port.timeout = 1
        
        # Setup da UI
        self.setup_ui()
        
        # Timer para atualização da leitura
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_frequency)
        self.update_timer.start(100)  # Atualiza a cada 100ms
        
        # Inicia a leitura serial
        self.start_reading()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Label para frequência alvo
        self.target_label = QLabel(f"Frequência Desejada: {self.target_frequency:.2f} Hz")
        self.target_label.setAlignment(Qt.AlignCenter)
        self.target_label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(self.target_label)
        
        # Widget customizado para o galvanômetro
        self.meter = MeterWidget(self)
        layout.addWidget(self.meter)
        self.meter.set_target(self.target_frequency)
        
        # Label para frequência atual
        self.current_label = QLabel("Frequência Atual: 0.00 Hz")
        self.current_label.setAlignment(Qt.AlignCenter)
        self.current_label.setStyleSheet("font-size: 18px; color: white;")
        layout.addWidget(self.current_label)
        
        # Label para mensagem de ajuste
        self.message_label = QLabel("Aguardando leitura...")
        self.message_label.setAlignment(Qt.AlignCenter)
        self.message_label.setStyleSheet("font-size: 16px; color: white;")
        layout.addWidget(self.message_label)
        
        # Estilo da janela
        self.setStyleSheet("background-color: #1e1e1e;")
    
    def start_reading(self):
        if self.serial_port and self.serial_port.is_open:
            # Envia comando para iniciar leitura
            self.serial_port.write(b'\xF0')
    
    def stop_reading(self):
        if self.serial_port and self.serial_port.is_open:
            # Envia comando para parar leitura
            self.serial_port.write(b'\xF1')
    
    def update_frequency(self):
        if self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting:
                    data = self.serial_port.readline().decode().strip()
                    
                    # Verifica se a mensagem está no formato correto
                    if data.startswith('#FRQ:') and data.endswith('$'):
                        # Extrai o valor da frequência
                        freq_str = data[5:-1]  # Remove '#FRQ:' e '$'
                        try:
                            self.current_frequency = float(freq_str)
                            print(f"Frequência: {self.current_frequency} Hz")
                            self.update_display()
                        except ValueError:
                            print(f"Erro ao converter frequência: {freq_str}")
            except Exception as e:
                print(f"Erro na leitura serial: {e}")
    
    def update_display(self):
        # Atualiza a frequência atual
        self.current_label.setText(f"Frequência Atual: {self.current_frequency:.2f} Hz")
        
        # Calcula a diferença percentual
        diff = self.current_frequency - self.target_frequency
        percent_diff = (diff / self.range) * 100
        percent_diff = max(-100, min(100, percent_diff))
        
        # Atualiza o galvanômetro
        self.meter.set_value(percent_diff)
        
        # Atualiza a mensagem e cores
        color = self.get_color(abs(percent_diff))
        if abs(diff) < 0.01:
            message = "Frequência ajustada!"
        elif diff > 0:
            message = "Diminua a frequência"
        else:
            message = "Aumente a frequência"
        
        self.message_label.setText(message)
        self.message_label.setStyleSheet(f"font-size: 16px; color: {color};")
        self.current_label.setStyleSheet(f"font-size: 18px; color: {color};")
    
    def get_color(self, percent_diff):
        if percent_diff > 80:
            return "#ff4444"  # Vermelho
        elif percent_diff > 40:
            return "#ffaa00"  # Laranja
        elif percent_diff > 10:
            return "#ffFF00"  # Amarelo
        return "#44ff44"  # Verde
    
    def closeEvent(self, event):
        self.stop_reading()
        self.update_timer.stop()
        super().closeEvent(event)

class MeterWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.target_frequency = 0
        self.setMinimumSize(300, 300)  # Aumentada a altura mínima
    
    def set_value(self, value):
        self.value = max(-100, min(100, value))
        self.update()

    def set_target(self, value):
        self.target_frequency = value
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Desenha o fundo do medidor
        rect = self.rect()
        
        # Ajusta o centro para considerar apenas o semicírculo superior
        center = QPointF(rect.center().x(), rect.bottom() - rect.height()/3 + 50)
        radius = min(rect.width(), rect.height()) * 0.8  # Ajusta o raio proporcionalmente
        
        # Define o retângulo para o arco
        arc_rect = QRectF(
            center.x() - radius,
            center.y() - radius,
            radius * 2,
            radius * 2
        )
        
        # Desenha o arco de fundo
        painter.setPen(QPen(QColor(60, 60, 60), 20))
        painter.drawArc(arc_rect, 180 * 16, -180 * 16)
        
        # Desenha as marcações
        painter.setPen(QPen(Qt.white, 2))
        for i in range(0, 181, 15):
            angle = math.radians(180 - i)
            x1 = center.x() + (radius - 15) * math.cos(angle)
            y1 = center.y() - (radius - 15) * math.sin(angle)
            x2 = center.x() + (radius - 30) * math.cos(angle)
            y2 = center.y() - (radius - 30) * math.sin(angle)
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            
            # Adiciona os números nas marcações principais
            if i % 30 == 0:
                text_radius = radius - 45
                text_x = center.x() + text_radius * math.cos(angle)
                text_y = center.y() - text_radius * math.sin(angle)
                
                # Calcula o valor da escala baseado na frequência alvo
                # Mapeia de -0.5 a +0.5 Hz em torno da frequência alvo
                scale_value = self.target_frequency + (-0.5 + (i / 180) * 1.0)
                
                # Configura a fonte
                font = painter.font()
                if i == 90:
                    font.setBold(True)
                font.setPointSize(8)
                font.setBold(False)
                painter.setFont(font)
                
                # Centraliza o texto na posição
                metrics = painter.fontMetrics()
                text = f"{scale_value:.2f}"
                text_width = metrics.width(text)
                text_height = metrics.height()
                
                painter.drawText(
                    int(text_x - text_width/2),
                    int(text_y + text_height/4),
                    text
                )
        
        # Calcula o ângulo do ponteiro
        angle = math.radians(180 - ((self.value + 100) / 200 * 180))
        
        # Desenha o ponteiro
        pointer_length = radius - 40
        
        painter.setPen(QPen(Qt.white, 4))
        painter.drawLine(
            center,
            QPointF(center.x() + pointer_length * math.cos(angle),
                   center.y() - pointer_length * math.sin(angle))
        )
        
        # Desenha o centro do ponteiro
        painter.setBrush(QBrush(Qt.white))
        painter.drawEllipse(center, 5, 5)
        
        # Adiciona o texto da frequência alvo no centro
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        
        target_text = f"{self.target_frequency:.1f} Hz"
        metrics = painter.fontMetrics()
        text_width = metrics.width(target_text)
        
        painter.drawText(
            int(center.x() - text_width/2),
            int(center.y() + radius/2),
            target_text
        )