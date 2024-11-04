import sys
import numpy as np
import pandas as pd
import serial
from PyQt5.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, QPushButton, 
                             QSpinBox, QCheckBox, QLabel, QMessageBox, QFileDialog)
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QIcon
import pyqtgraph as pg

timerPeriod = 10

class PlotWindow(QMainWindow):
    def __init__(self, num_curves, port, baudrate):
        super().__init__()
        self.num_curves = num_curves
        self.serial_port = serial.Serial(port, baudrate, timeout=1) # Reabre a porta serial
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

    # def start_experiment(self):
    #     if not self.experiment_running:
    #         if not self.serial_port or not self.serial_port.is_open:
    #             QMessageBox.critical(self, "Erro", "Nenhuma porta serial conectada corretamente.")
    #             return
            
    #         self.serial_port.reset_input_buffer()  # Limpa o buffer de entrada
    #         self.experiment_running = True
    #         self.experiment_paused = False
    #         self.timer.start(timerPeriod)  # Atualizar a cada 100ms
    #     if self.experiment_paused:
    #         self.experiment_paused = False
    #         self.timer.start(timerPeriod)

    def start_experiment(self):
        if not self.experiment_running:
            if not self.serial_port or not self.serial_port.is_open:
                QMessageBox.critical(self, "Erro", "Nenhuma porta serial conectada corretamente.")
                return

            self.serial_port.reset_input_buffer()  # Limpa o buffer de entrada
            self.experiment_running = True
            self.experiment_paused = False
            self.timer.start(timerPeriod)  # Atualizar continuamente

        # Se o experimento já está rodando e apenas pausado, basta reiniciar o timer
        if self.experiment_paused:
            self.experiment_paused = False
            self.timer.start(timerPeriod)

    def pause_experiment(self):
        if self.experiment_running and not self.experiment_paused:
            self.experiment_paused = True
            self.timer.stop()
        elif self.experiment_running and self.experiment_paused:
            self.experiment_paused = False
            self.timer.start(timerPeriod)

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
        self.timer.start(timerPeriod)  # Retoma o experimento após a gravação

    def save_data_to_csv(self):
        options = QFileDialog.Options()
        file_path, _ = QFileDialog.getSaveFileName(self, "Salvar Dados", "", "CSV Files (*.csv);;All Files (*)", options=options)
        if file_path:
            df = pd.DataFrame({'Tempo (s)': self.time_data})
            for i, curve_data in enumerate(self.data):
                df[f'Curva {i + 1} (V)'] = curve_data
            df.to_csv(file_path, index=False)
            QMessageBox.information(self, "Gravação Concluída", f"Os dados foram salvos em {file_path}", QMessageBox.Ok)

    # def update_plot(self):
    #     if not self.experiment_paused:
    #         try:
    #             expected_bytes = self.num_curves * 3  # 3 bytes por canal (1 byte ID + 2 bytes ADC)
    #             if self.serial_port.in_waiting >= expected_bytes:
    #                 raw_data = self.serial_port.read(expected_bytes)
    #                 channel_data = {i: None for i in range(self.num_curves)}  # Dicionário para armazenar dados do canal

    #                 # Processa os dados em blocos de 3 bytes
    #                 for i in range(0, len(raw_data), 3):
    #                     channel_id = raw_data[i]  # 1º byte é o ID do canal
    #                     if channel_id < self.num_curves:
    #                         # Obtém os bytes para o valor ADC e converte para decimal
    #                         lsb, msb  = raw_data[i+1], raw_data[i+2]
    #                         adc_value = int.from_bytes([lsb, msb], byteorder='little')  # Converte os 2 bytes para um valor de 16 bits
                                    
    #                         # Converte cada byte para uma string binária de 8 bits
    #                         msb_binary = f"{msb:08b}"  # Representação de 8 bits do MSB
    #                         lsb_binary = f"{lsb:08b}"  # Representação de 8 bits do LSB

    #                         # Imprime os bits e o valor decimal
    #                         print(f"Channel ID: {channel_id}, LSB bits: {lsb_binary}, MSB bits: {msb_binary}, ADC decimal: {adc_value}")
    #                         channel_data[channel_id] = self.convert_adc_to_voltage(adc_value)

    #                 # Atualize o gráfico se todos os canais tiverem dados válidos
    #                 if all(val is not None for val in channel_data.values()):
    #                     time = len(self.time_data) * (timerPeriod / 1000)  # Simula tempo em segundos
    #                     self.time_data.append(time)

    #                     for i, voltage in channel_data.items():
    #                         self.data[i].append(voltage)
    #                         self.curves[i].setData(self.time_data, self.data[i])

    #                     self.plot_widget.setXRange(max(0, time - 10), time)  # Mantém o eixo X constante

    #         except serial.SerialException as e:
    #             QMessageBox.critical(self, "Erro", f"Erro ao ler dados da porta serial: {e}")
    #             self.stop_experiment()

    def update_plot(self):
        if not self.experiment_paused and self.serial_port.is_open:
            try:
                raw_data = self.serial_port.read(self.serial_port.in_waiting or 1)
                channel_data = {i: None for i in range(self.num_curves)}

                # Processa os dados em blocos de 3 bytes
                for i in range(0, len(raw_data), 3):
                    if len(raw_data) - i < 3:
                        break

                    channel_id = raw_data[i]
                    if channel_id < self.num_curves:
                        lsb, msb = raw_data[i + 1], raw_data[i + 2]
                        adc_value = int.from_bytes([lsb, msb], byteorder='little')
                        channel_data[channel_id] = self.convert_adc_to_voltage(adc_value)

                # Adiciona dados sincronizados
                time = len(self.time_data) * (timerPeriod / 1000)
                self.time_data.append(time)

                for i in range(self.num_curves):
                    if channel_data[i] is not None:
                        self.data[i].append(channel_data[i])
                    else:
                        # Repete o último valor para manter o comprimento igual
                        self.data[i].append(self.data[i][-1] if self.data[i] else 0)
                    self.curves[i].setData(self.time_data, self.data[i])

                # Ajuste do eixo X
                self.plot_widget.setXRange(max(0, time - 10), time)

            except serial.SerialException as e:
                QMessageBox.critical(self, "Erro", f"Erro ao ler dados da porta serial: {e}")
                self.stop_experiment()

    def convert_adc_to_voltage(self, adc_value):
        # Converte valor ADC (0-4095) para tensão (0V-3.3V ou faixa equivalente)
        # TODO: Fazer a conversão considerando o valor real e não acondicionado (-10V/+10V)
        return (adc_value / 4095.0) * 3.3

    def closeEvent(self, event):
        # Certifique-se de fechar a porta serial ao fechar a janela
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PlotWindow()
    window.show()
    
    sys.exit(app.exec_())
