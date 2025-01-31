import sys
import json
import serial
import serial.tools.list_ports

from node import Node
from edge import Edge
from history_manager import HistoryManager, AddEdgeAction, AddNodeAction, RemoveEdgeAction, RemoveNodeAction, CompositeAction
from id_manager import IdManager
from frequency_meter import FrequencyTunerDialog
from styles import apply_styles
from plot_window import PlotWindow

from PyQt5.QtWidgets import (QApplication, QAction, QMessageBox, QMainWindow, QPushButton, QGraphicsScene, 
                             QGraphicsItem, QInputDialog, QFileDialog, QColorDialog, QVBoxLayout, QHBoxLayout, 
                             QGraphicsRectItem, QWidget, QComboBox, QGraphicsView, )
from PyQt5.QtCore import Qt, QRectF
from PyQt5.QtGui import QPen, QColor, QIcon, QTransform, QKeySequence, QFont

class CustomGraphicsScene(QGraphicsScene):
    """
    Cena gráfica personalizada para lidar com eventos de clique e seleção de itens.

    Atributos:
        main_window (QMainWindow): Referência para a janela principal.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.selection_rect = None
        self.selection_rect_start = None
        self.setSceneRect(-1250, -1350, 2600, 2550)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            item = self.itemAt(event.scenePos(), QTransform())
            if item is None:
                self.clearSelection()
                self.main_window.deselect_item()
                self.selection_rect_start = event.scenePos()
                self.selection_rect = QGraphicsRectItem()
                self.selection_rect.setPen(QPen(QColor(138, 180, 247, 200)))
                self.selection_rect.setBrush(QColor(138, 180, 247, 10))
                self.addItem(self.selection_rect)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.selection_rect is not None:
            current_pos = event.scenePos()
            rect = QRectF(self.selection_rect_start, current_pos).normalized()
            self.selection_rect.setRect(rect)
            self.update_selection(rect)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.selection_rect is not None:
            self.removeItem(self.selection_rect)
            self.selection_rect = None
            self.selection_rect_start = None
        super().mouseReleaseEvent(event)

    def update_selection(self, rect):
        self.clearSelection()

        for item in self.items():
            if isinstance(item, Node) or isinstance(item, Edge):
                if rect.intersects(item.sceneBoundingRect()):
                    item.setSelected(True)
                    if isinstance(item, Node):
                        self.main_window.highlight_node(item, True)
                    elif isinstance(item, Edge):
                        self.main_window.highlight_edge(item, True)
                else:
                    item.setSelected(False)
                    if isinstance(item, Node):
                        self.main_window.highlight_node(item, False)
                    elif isinstance(item, Edge):
                        self.main_window.highlight_edge(item, False)

class CustomGraphicsView(QGraphicsView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragMode(QGraphicsView.NoDrag)
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.AnchorUnderMouse)
        self.setInteractive(True)
        self.middle_mouse_button_pressed = False

    def wheelEvent(self, event):
        factor = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
        self.scale(factor, factor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MiddleButton:
            self.middle_mouse_button_pressed = True
            self.setDragMode(QGraphicsView.ScrollHandDrag)
            self.setInteractive(False)
            self.viewport().setCursor(Qt.ClosedHandCursor)
            self.middle_mouse_button_pos = event.pos()
            self.viewport().grabMouse()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.middle_mouse_button_pressed:
            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - (event.x() - self.middle_mouse_button_pos.x())
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - (event.y() - self.middle_mouse_button_pos.y())
            )
            self.middle_mouse_button_pos = event.pos()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MiddleButton and self.middle_mouse_button_pressed:
            self.middle_mouse_button_pressed = False
            self.setDragMode(QGraphicsView.NoDrag)
            self.setInteractive(True)
            self.viewport().setCursor(Qt.ArrowCursor)
            self.viewport().releaseMouse()
        else:
            super().mouseReleaseEvent(event)




class MainWindow(QMainWindow):
    """
    Janela principal da aplicação, contendo a interface gráfica e as funcionalidades principais.

    Atributos:
        nodes (list): Lista de nós na cena.
        edges (list): Lista de arestas na cena.
        selected_node (Node): Nó atualmente selecionado.
        selected_edge (Edge): Aresta atualmente selecionada.
        node_id_counter (int): Contador para gerar IDs de nós.
        available_ids (list): Lista de IDs disponíveis para reutilização.
        adding_edge (bool): Indicador de adição de arestas.
        start_node (Node): Nó de início para adição de arestas.
        serial_port (Serial): Conexão serial.
        history_manager (HistoryManager): Gerenciador de ações de desfazer/refazer.
    """

    def __init__(self):
        super().__init__()
        self.init_ui()
        self.init_actions()
        self.init_scene()
        self.init_variables()

    # Inicializa a iterface gráfica do usuário
    def init_ui(self):
        self.setWindowTitle('Controle de Rede de Osciladores')
        self.setWindowIcon(QIcon('icons/icon_black.png'))
        self.setGeometry(100, 100, 800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)
        self.top_layout = QHBoxLayout()
        self.layout.addLayout(self.top_layout)

        self.add_node_button = QPushButton('Adicionar Nó', self)
        self.add_node_button.clicked.connect(self.add_node)
        self.top_layout.addWidget(self.add_node_button)

        self.add_edge_button = QPushButton('Adicionar Aresta', self)
        self.add_edge_button.setCheckable(True)
        self.add_edge_button.clicked.connect(self.toggle_adding_edge)
        self.top_layout.addWidget(self.add_edge_button)

        self.edge_type_selector = QComboBox(self)
        self.edge_type_selector.addItems(["Bidirecional", "Direcional"])
        self.top_layout.addWidget(self.edge_type_selector)

        self.tune_button = QPushButton('Ajustar Frequência', self)
        self.tune_button.clicked.connect(self.open_tuner)
        self.top_layout.addWidget(self.tune_button)

        self.start_button = QPushButton('Iniciar', self)
        self.start_button.clicked.connect(self.start_experiment)
        self.top_layout.addWidget(self.start_button)

    # Inicializa as ações do menu
    def init_actions(self):
        menu = self.menuBar()

        file_menu = menu.addMenu('&Arquivo')
        file_menu.addAction(QIcon('icons/save.svg'), 'Salvar', self.save_current_configuration)
        file_menu.addAction(QIcon('icons/load.svg'), 'Abrir Arquivo...', self.load_existing_configuration)

        system_menu = menu.addMenu('&Sistema')
        self.serial_action = QAction('Nenhuma COM Conectada', self)
        self.serial_action.triggered.connect(self.toggle_serial_connection)
        system_menu.addAction(self.serial_action)
        system_menu.addAction('Configurar Serial...', self.open_config_dialog)

        edit_menu = menu.addMenu('&Editar')

        self.undo_action = QAction('Desfazer', self)
        self.undo_action.setIcon(QIcon('icons/undo.svg'))
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction('Refazer', self)
        self.redo_action.setIcon(QIcon('icons/redo.svg'))
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)

        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

    # Inicializa a cena gráfica onde serão visualizados os nós e arestas do grafo
    def init_scene(self):
        self.scene = CustomGraphicsScene(self)
        self.scene.setBackgroundBrush(QColor(30, 30, 30))
        self.view = CustomGraphicsView(self.scene)
        self.layout.addWidget(self.view)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.keyPressEvent = self.keyPressEvent

    # Inicializa as variáveis da aplicação
    def init_variables(self):
        self.nodes = []
        self.edges = []
        self.selected_node = None
        self.selected_edge = None
        self.node_id_counter = 1
        self.available_ids = []
        self.adding_edge = False
        self.start_node = None
        self.serial_port = None
        self.history_manager = HistoryManager()
        self.id_manager = IdManager() 
    
    def open_config_dialog(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        port, ok = QInputDialog.getItem(self, "Configuração Serial", "Selecione a porta:", ports, 0, False)
        if ok and port:
            baudrate, ok = QInputDialog.getInt(self, "Configuração Serial", "Digite o baudrate:", 115200, 1200, 115200, 1)
            if ok:
                self.serial_port = open_serial_connection(port, baudrate)
                if self.serial_port:
                    QMessageBox.information(self, "Conectado", f"Porta serial {port} conectada com sucesso.")
                    self.serial_action.setText(f'{port} Conectada')
                    self.serial_action.setIcon(QIcon('icons/connect.svg'))
    
    def start_experiment(self):
        if not self.serial_port or not self.serial_port.is_open:
            QMessageBox.critical(self, "Erro", "Nenhuma porta serial conectada corretamente.")
            return
        
        matrix = self.generate_coupling_matrix()
        if self.send_data_to_microcontroller(matrix):
            response = self.serial_port.read_until(b"ACK\n")
            if b"ACK" in response:
                QMessageBox.information(self, "Configuração Concluída", "A matriz de acoplamento foi enviada e recebida com sucesso.", QMessageBox.Ok)
                # self.open_plot_window()
            else:
                QMessageBox.critical(self, "Erro", "Falha ao receber confirmação do microcontrolador.")
        else:
            QMessageBox.critical(self, "Erro", "Falha ao enviar a matriz de acoplamento para o microcontrolador.")
    
    def add_node(self):
        frequency, ok = QInputDialog.getDouble(self, "Adicionar Nó", "Frequência de Oscilação:", 1.00, 0.01, 99.99, 2)
        if ok:
            node_id = self.id_manager.get_next_id()
            new_node = Node(self.scene.sceneRect().center().x(), self.scene.sceneRect().center().y(), node_id, self)
            self.id_manager.add_id(node_id)
            new_node = Node(self.scene.sceneRect().center().x(), self.scene.sceneRect().center().y(), node_id, self)
            new_node.set_frequency(frequency)
            new_node.setFlag(QGraphicsItem.ItemIsSelectable, True)
            self.scene.addItem(new_node)
            self.nodes.append(new_node)
            new_node.update_text_position()
            new_node.update_frequency_text_position()
            self.update_graph()
            self.history_manager.add_action(AddNodeAction(new_node, self.scene, self.nodes))
    
    def update_graph(self):
        for edge in self.edges:
            edge.update_position()

    def toggle_adding_edge(self):
        self.adding_edge = not self.adding_edge
        if self.adding_edge:
            self.view.setCursor(Qt.CrossCursor)
            self.set_nodes_movable(False)
            self.add_edge_button.setText('Clique para adicionar aresta')
        else:
            self.view.setCursor(Qt.ArrowCursor)
            self.set_nodes_movable(True)
            self.add_edge_button.setText('Adicionar Aresta')
    
    def toggle_edge_direction(self, edge):
        edge.bidirectional = not edge.bidirectional
        self.update_graph()

    def invert_edge_direction(self, edge):
        if not edge.bidirectional:
            edge.start_node, edge.end_node = edge.end_node, edge.start_node
            self.update_graph()

    def select_node(self, node):
        if self.adding_edge:
            if not self.start_node:
                # Primeiro nó selecionado
                self.start_node = node
                self.highlight_node(node, True)  # Destaque o nó selecionado
                self.set_nodes_movable(False)  # Bloqueie o movimento dos nós até o final da adição da aresta
            else:
                # Segundo nó selecionado
                self.add_edge_to_nodes(self.start_node, node)
                self.start_node = None
                self.set_nodes_movable(True)
                self.adding_edge = False
                self.add_edge_button.setChecked(False)
                self.view.setCursor(Qt.ArrowCursor)
                self.highlight_node(node, False)  # Remove o destaque do nó
        else:
            if self.selected_node and self.selected_node != node:
                # Desseleciona o nó selecionado anteriormente
                self.deselect_node()
            self.highlight_node(node, True)  # Destaque o nó selecionado
            self.selected_node = node
    
    def select_edge(self, edge):
        if self.selected_edge and self.selected_edge != edge:
            self.deselect_edge()
        self.highlight_edge(edge, True)
        self.selected_edge = edge

    def highlight_node(self, node, highlight):
        if highlight:
            node.setPen(QPen(Qt.white, 4))  # Destaque o nó com uma borda branca
        else:
            node.setPen(QPen(node.default_color.darker(150), 4))  # Restaura a borda padrão
    
    def highlight_edge(self, edge, highlight):
        if highlight:
            edge.setPen(QPen(Qt.yellow, 4))  # Destaque a aresta com uma cor amarela
        else:
            edge.setPen(QPen(QColor(255, 255, 255), 2))  # Restaura a cor padrão

    def deselect_node(self):
        if self.selected_node:
            self.highlight_node(self.selected_node, False)
            self.selected_node = None
    
    def deselect_edge(self):
        if self.selected_edge:
            self.highlight_edge(self.selected_edge, False)
            self.selected_edge = None

    def deselect_item(self):
        self.deselect_node()
        self.deselect_edge()
    
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            if self.selected_node:
                self.delete_node(self.selected_node)
            elif self.selected_edge:
                self.delete_edge(self.selected_edge)
    
    def node_clicked(self, node):
        if self.adding_edge and self.selected_node and self.selected_node != node:
            self.add_edge_to_nodes(self.selected_node, node)
            self.deselect_node()
            self.view.setCursor(Qt.ArrowCursor)
            self.set_nodes_movable(True)
            self.adding_edge = False
            self.add_edge_button.setChecked(False)
    
    def add_edge_to_nodes(self, start_node, end_node):
        if any(edge.start_node == start_node and edge.end_node == end_node or
            edge.start_node == end_node and edge.end_node == start_node for edge in self.edges):
            self.toggle_adding_edge()
            return 
        
        if start_node == end_node:
            self.toggle_adding_edge()
            return 

        bidirectional = self.edge_type_selector.currentText() == "Bidirecional"
        edge = Edge(start_node, end_node, self, bidirectional=bidirectional)
        edge.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.edges.append(edge)
        self.scene.addItem(edge)
        self.highlight_node(start_node, False)
        self.highlight_node(end_node, False)
        self.toggle_adding_edge()
        self.update_graph()
        self.history_manager.add_action(AddEdgeAction(edge, self.scene, self.edges))
    
    def set_nodes_movable(self, movable):
        for node in self.nodes:
            node.setFlag(QGraphicsItem.ItemIsMovable, movable)
    
    def generate_coupling_matrix(self):
        # Ordenar nós por ID antes de gerar a matriz
        sorted_nodes = sorted(self.nodes, key=lambda x: x.id)
        n = len(sorted_nodes)
        matrix = [[0]*n for _ in range(n)]
        
        for edge in self.edges:
            start_index = sorted_nodes.index(edge.start_node)
            end_index = sorted_nodes.index(edge.end_node)
            matrix[start_index][end_index] = 1
            if edge.bidirectional:
                matrix[end_index][start_index] = 1
        return matrix
    
    def edit_frequency(self, node):
        new_frequency, ok = QInputDialog.getDouble(self, "Editar Frequência", "Nova Frequência:", node.frequency, 0.01, 100.00, 2)
        if ok:
            node.set_frequency(new_frequency)
            node.update_frequency_text()
            self.update_graph()

    def edit_node_color(self, node):
        new_color = QColorDialog.getColor(node.brush().color(), self, "Escolha a Cor do Nó")
        new_color.setAlpha(200)
        if new_color.isValid():
            node.set_color(new_color)
            self.update_graph()

    def edit_node_id(self, node):
        new_id, ok = QInputDialog.getInt(self, "Editar ID do Nó", "Novo ID:", node.id, 1, max(self.id_manager.used_ids) + 1)
        if ok:
            if self.id_manager.is_valid_id(new_id):
                old_id = node.id
                self.id_manager.release_id(old_id)
                self.id_manager.add_id(new_id)
                node.id = new_id
                node.text.setPlainText(str(new_id))
            else:
                QMessageBox.warning(self, "ID Inválido", "O ID deve ser sequencial e único.")

    def delete_node(self, node):
        if node in self.nodes:
            self.id_manager.release_id(node.id)
            self.nodes.remove(node)
            self.scene.removeItem(node)

            edges_to_remove = [edge for edge in self.edges if edge.start_node == node or edge.end_node == node]
            actions = [RemoveNodeAction(node, self.scene, self.nodes)]
            
            for edge in edges_to_remove:
                self.scene.removeItem(edge)
                self.edges.remove(edge)
                actions.append(RemoveEdgeAction(edge, self.scene, self.edges))

            composite_action = CompositeAction(actions)
            self.history_manager.add_action(composite_action)
            self.update_graph()

    def delete_edge(self, edge):
        if edge in self.edges:
            self.edges.remove(edge)
            self.scene.removeItem(edge)
            self.update_graph()
            self.history_manager.add_action(RemoveEdgeAction(edge, self.scene, self.edges))

    def save_current_configuration(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Salvar Rede", "", "Network Files (*.net)")
        if filename:
            self.save_configuration(filename)
    
    def load_existing_configuration(self):
        filename, _ = QFileDialog.getOpenFileName(self, "Carregar Rede", "", "Network Files (*.net);;Json Files (*.json)")
        if filename:
            self.load_configuration(filename)

    def save_configuration(self, filename):
        config = {
            'nodes': [{'id': node.id, 'x': node.pos().x(), 'y': node.pos().y(), 'frequency': node.frequency, 'color': node.default_color.name()} for node in self.nodes],
            'edges': [{'start_node': edge.start_node.id, 'end_node': edge.end_node.id, 'bidirectional': edge.bidirectional} for edge in self.edges]
        }
        with open(filename, 'w') as f:
            json.dump(config, f)

    def load_configuration(self, filename):
        with open(filename, 'r') as f:
            config = json.load(f)
        
        # Limpar o gerenciador de IDs
        self.id_manager = IdManager()

        # Limpar nós e arestas existentes
        for node in self.nodes:
            self.scene.removeItem(node)
        self.nodes.clear()
        for edge in self.edges:
            self.scene.removeItem(edge)
        self.edges.clear()

        # Adicionar nós
        for node_data in config['nodes']:
            node = Node(node_data['x'], node_data['y'], node_data['id'], self)
            self.id_manager.add_id(node_data['id'])
            node.set_frequency(node_data['frequency'])
            node.set_color(QColor(node_data['color']))
            self.scene.addItem(node)
            self.nodes.append(node)

        # Adicionar arestas
        for edge_data in config['edges']:
            start_node = next(node for node in self.nodes if node.id == edge_data['start_node'])
            end_node = next(node for node in self.nodes if node.id == edge_data['end_node'])
            edge = Edge(start_node, end_node, self, bidirectional=edge_data['bidirectional'])
            self.edges.append(edge)
            self.scene.addItem(edge)
        
        self.update_graph()

    def add_actions_to_menus(self):
        edit_menu = self.menuBar().addMenu('&Editar')
        edit_menu.addAction(self.undo_action)
        edit_menu.addAction(self.redo_action)

    def undo(self):
        self.history_manager.undo()
    
    def redo(self):
        self.history_manager.redo()

    def send_data_to_microcontroller(self, matrix):
        """
        Envia a matriz de adjacência pela serial em formato simples e eficiente.
        Formato: <0,1,0;1,0,1;0,1,0>
        """
        # Converte a matriz em string
        matrix_str = '<'
        for i, row in enumerate(matrix):
            matrix_str += ','.join(str(int(val)) for val in row)
            if i < len(matrix) - 1:
                matrix_str += ';'
        matrix_str += '>'
        
        # Envia pela serial
        try:
            self.serial_port.write(matrix_str.encode())
            print(matrix_str.encode())
            return True
        except serial.SerialException as e:
            print(f'Erro ao enviar dados: {e}')
            return False

    def receive_confirmation(self, ser, timeout=5):
        ser.timeout = timeout
        try:
            response = ser.readline().decode().strip()
            return response
        except serial.SerialException as e:
            print(f'Erro ao receber confirmação: {e}')
            return None
    
    def disconnect_serial(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_port = None
            self.serial_action.setText('Nenhuma Porta COM Conectada')
            QMessageBox.information(self, "Desconectado", "Desconectado da porta serial com sucesso.")
        else:
            QMessageBox.warning(self, "Aviso", "Nenhuma porta serial está conectada.")

    def toggle_serial_connection(self):
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            self.serial_action.setText(f'{self.serial_port.port} Desconectada')
            self.serial_action.setIcon(QIcon('icons/disconnect.svg'))
        elif self.serial_port and not self.serial_port.is_open:
            self.serial_port.open()
            self.serial_action.setText(f'{self.serial_port.port} Conectada')
            self.serial_action.setIcon(QIcon('icons/connect.svg'))
        else:
            self.open_config_dialog()

    # def open_plot_window(self):
    #     if not self.serial_port or not self.serial_port.is_open:
    #         QMessageBox.critical(self, "Erro", "Nenhuma porta serial conectada corretamente.")
    #         return
        
    #     num_nodes = len(self.nodes)
        
    #     # Desconecta a serial da tela principal
    #     self.serial_port.close()
        
    #     # Passa a porta serial para a janela de plotagem
    #     self.plot_window = PlotWindow(num_nodes, self.serial_port.port, self.serial_port.baudrate)
    #     self.plot_window.show()
    
    def open_freqmeter_window(self):
        if not self.serial_port or not self.serial_port.is_open:
            QMessageBox.critical(self, "Erro", "Nenhuma porta serial conectada corretamente.")
            return
        
        frequency = self.selected_node.frequency
    
        # Desconecta a serial da tela principal
        self.serial_port.close()
        
        # Abre a porte de ajuste de frequência com frequência do oscilador selecionado
        tuner = FrequencyTunerDialog(frequency, self.serial_port.port, self.serial_port.baudrate, self)
        tuner.exec_()
    
    def open_tuner(self):
        if self.selected_node and self.serial_port and self.serial_port.is_open:
            self.open_freqmeter_window()
        else:
            QMessageBox.warning(self, "Aviso", "Selecione um nó e verifique a conexão serial.")


def open_serial_connection(port, baudrate):
    try:
        ser = serial.Serial(port, baudrate)
        return ser
    except serial.SerialException as e:
        print(f'Erro ao abrir a porta serial: {e}')
        QMessageBox.critical(None, "Erro", f"Não foi possível abrir a porta serial {port}. Verifique a conexão e tente novamente.")
        return None

if __name__ == "__main__":
    app = QApplication(sys.argv)
    apply_styles(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
