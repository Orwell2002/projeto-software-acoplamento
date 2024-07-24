import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                             QSpinBox, QCheckBox, QLabel, QMessageBox, QFileDialog)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
import pyqtgraph as pg
import random

class PlotWindow(QMainWindow):
    def __init__(self, num_curves):
        super().__init__()
        self.num_curves = num_curves
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle('Leitura Analógica em Tempo Real')
        self.setWindowIcon(QIcon('icons/icon_black.png'))
        self.setGeometry(100, 100, 800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        
        self.top_layout = QHBoxLayout()
        self.layout.addLayout(self.top_layout)

        self.recording_time_label = QLabel('Tempo de Gravação (s):', self)
        self.top_layout.addWidget(self.recording_time_label)
        
        self.recording_time_spinbox = QSpinBox(self)
        self.recording_time_spinbox.setRange(1, 3600)  # 1 second to 1 hour
        self.top_layout.addWidget(self.recording_time_spinbox)

        self.start_button = QPushButton(self)
        self.start_button.setIcon(QIcon('icons/start.svg'))
        self.start_button.clicked.connect(self.start_experiment)
        self.top_layout.addWidget(self.start_button)

        self.pause_button = QPushButton(self)
        self.pause_button.setIcon(QIcon('icons/pause.svg'))
        self.pause_button.clicked.connect(self.pause_experiment)
        self.top_layout.addWidget(self.pause_button)

        self.stop_button = QPushButton(self)
        self.stop_button.setIcon(QIcon('icons/stop.svg'))
        self.stop_button.clicked.connect(self.stop_experiment)
        self.top_layout.addWidget(self.stop_button)

        self.record_button = QPushButton('Gravar', self)
        self.record_button.clicked.connect(self.start_recording)
        self.top_layout.addWidget(self.record_button)
        
        self.plot_widget = pg.PlotWidget()
        self.layout.addWidget(self.plot_widget)
        
        self.curves = []
        self.checkboxes = []
        self.data = []
        self.time_data = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_plot)

        self.create_curves(self.num_curves)

        self.experiment_running = False
        self.experiment_paused = False

    def create_curves(self, num_curves):
        for i in range(num_curves):
            curve = self.plot_widget.plot(pen=pg.mkPen(color=pg.intColor(i), width=2))
            self.curves.append(curve)
            checkbox = QCheckBox(f'Curva {i + 1}', self)
            checkbox.setChecked(True)
            checkbox.stateChanged.connect(self.update_visibility)
            self.top_layout.addWidget(checkbox)
            self.checkboxes.append(checkbox)
            self.data.append([])

    def update_visibility(self):
        for i, checkbox in enumerate(self.checkboxes):
            self.curves[i].setVisible(checkbox.isChecked())

    def start_experiment(self):
        if not self.experiment_running:
            self.experiment_running = True
            self.experiment_paused = False
            self.timer.start(100)  # Atualizar a cada 100ms
        if self.experiment_paused:
            self.experiment_paused = False
            self.timer.start(100)

    def pause_experiment(self):
        if self.experiment_running and not self.experiment_paused:
            self.experiment_paused = True
            self.timer.stop()
        elif self.experiment_running and self.experiment_paused:
            self.experiment_paused = False
            self.timer.start(100)

    def stop_experiment(self):
        if self.experiment_running:
            self.experiment_running = False
            self.experiment_paused = False
            self.timer.stop()
            self.time_data.clear()
            for curve_data in self.data:
                curve_data.clear()
            #self.plot_widget.clear()

    def start_recording(self):
        if self.experiment_running:
            recording_time = self.recording_time_spinbox.value()
            QTimer.singleShot(recording_time * 1000, self.stop_recording)

    def stop_recording(self):
        self.timer.stop()
        self.save_data_to_csv()
        self.timer.start(100)  # Retoma o experimento após a gravação

    def save_data_to_csv(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar Dados", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            df = pd.DataFrame({'Tempo (s)': self.time_data})
            for i, curve_data in enumerate(self.data):
                df[f'Curva {i + 1} (V)'] = curve_data
            df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Gravação Concluída", f"Os dados foram salvos em {file_path}", QMessageBox.Ok)

    def update_plot(self):
        if not self.experiment_paused:
            time = len(self.time_data) * 0.1  # Simula tempo em segundos
            self.time_data.append(time)
            for i, curve in enumerate(self.curves):
                voltage = self.generate_sine_wave(time, frequency=(i + 1) * 0.5)  # Gera onda senoidal para teste
                self.data[i].append(voltage)
                curve.setData(self.time_data, self.data[i])
            self.plot_widget.setXRange(max(0, time - 10), time)  # Mantém o eixo Y constante

    def generate_sine_wave(self, time, frequency=1, amplitude=1):
        return amplitude * np.sin(2 * np.pi * frequency * time)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PlotWindow()
    window.show()
    sys.exit(app.exec_())
