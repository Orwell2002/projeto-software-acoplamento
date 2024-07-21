import sys
import math
import json
from PyQt5.QtWidgets import (QApplication, QAction, QMainWindow, QPushButton, QGraphicsScene, QGraphicsItem, QGraphicsView,
                             QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsLineItem, QInputDialog, QFileDialog, 
                             QColorDialog, QMenu, QVBoxLayout, QHBoxLayout, QWidget, QComboBox)
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QFont, QIcon, QTransform, QPainter, QPolygonF, QKeySequence
from qdarktheme import load_stylesheet

import serial
import serial.tools.list_ports

class Node(QGraphicsEllipseItem):
    def __init__(self, x, y, id, main_window, parent=None):
        QGraphicsEllipseItem.__init__(self, parent)
        self.main_window = main_window

        self.setRect(-23, -23, 43, 43)
        self.default_color = QColor(100, 100, 255, 150)
        self.setBrush(self.default_color)
        self.update_border_color()

        self.setPos(x, y)

        self.id = id
        self.frequency = None

        font = QFont("Arial", 14)
        font.setBold(True)
        self.text = QGraphicsTextItem(str(self.id), self)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        self.update_text_position()

        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        frequency_font = QFont("Arial", 10)
        self.frequency_text = QGraphicsTextItem('', self)
        self.frequency_text.setFont(frequency_font)
        self.frequency_text.setDefaultTextColor(QColor(255, 255, 255))
        self.update_frequency_text_position()
    
    def set_color(self, color):
        self.default_color = color
        self.setBrush(color)
        self.update_border_color()

    def update_border_color(self):
        darker_color = self.default_color.darker(150)
        self.setPen(QPen(darker_color, 4))

    def update_text_position(self):
        rect = self.boundingRect()
        text_rect = self.text.boundingRect()
        self.text.setPos(rect.center() - text_rect.center())

    def update_frequency_text_position(self):
        rect = self.boundingRect()
        text_rect = self.frequency_text.boundingRect()
        self.frequency_text.setPos(rect.center().x() - text_rect.width() / 2, rect.bottom() + 5)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_window.select_node(self)
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemPositionChange:
            self.main_window.update_graph()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        menu = QMenu()

        edit_frequency_action = menu.addAction(QIcon('icons/edit_frequency.svg'), "Editar Frequência")
        edit_node_color_action = menu.addAction(QIcon('icons/edit_node_color.svg'), "Editar Cor do Nó")
        edit_node_id_action = menu.addAction(QIcon('icons/edit_node_id.svg'), "Editar ID do Nó")
        delete_node_action = menu.addAction(QIcon('icons/delete.svg'), "Excluir Nó")

        action = menu.exec_(event.screenPos())
        if action == edit_frequency_action:
            self.main_window.edit_frequency(self)
        elif action == edit_node_color_action:
            self.main_window.edit_node_color(self)
        elif action == edit_node_id_action:
            self.main_window.edit_node_id(self)
        elif action == delete_node_action:
            self.main_window.delete_node(self)
    
    def set_frequency(self, frequency):
        self.frequency = frequency
        self.update_frequency_text()
    
    def update_frequency_text(self):
        if self.frequency is not None:
            self.frequency_text.setPlainText(f'{self.frequency:.2f} Hz')
        else:
            self.frequency_text.setPlainText('')

class Edge(QGraphicsLineItem):
    def __init__(self, start_node, end_node, main_window, bidirectional=False):
        super().__init__()
        self.main_window = main_window
        self.start_node = start_node
        self.end_node = end_node
        self.bidirectional = bidirectional
        self.setPen(QPen(QColor(255, 255, 255), 2))  # Defina a cor e largura da linha
        self.update_position()
    
    def update_position(self):
        line = QLineF(self.start_node.pos(), self.end_node.pos())
        self.setLine(self.get_tangent_line(line, self.start_node, self.end_node))
        self.update()

    def get_tangent_line(self, line, start_node, end_node):
        # Calcula o ponto de tangência entre o círculo e a linha
        start_pos = start_node.pos()
        end_pos = end_node.pos()

        radius = start_node.rect().width() / 2
        line_length = QLineF(start_pos, end_pos).length()
        
        if line_length == 0:
            return QLineF(start_pos, end_pos)  # Nos casos onde os nós estão no mesmo lugar

        # Normaliza o vetor direção
        direction = (end_pos - start_pos) / line_length

        # Calcula os pontos de tangência
        tangent_start = start_pos + direction * radius
        tangent_end = end_pos - direction * radius

        return QLineF(tangent_start, tangent_end)

    def paint(self, painter, option, widget):
        super().paint(painter, option, widget)
        if self.bidirectional:
            return

        # Obtém as posições dos nós
        start_pos = self.start_node.pos()
        end_pos = self.end_node.pos()

        # Obtém a linha tangente entre os nós
        tangent_line = self.get_tangent_line(QLineF(end_pos, start_pos), self.end_node, self.start_node)

        # Desenha a linha
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.drawLine(tangent_line)

        # Desenha a seta
        self.draw_line_with_arrow(painter, tangent_line)

    def draw_line_with_arrow(self, painter, line):
        arrow_size = 10  # Tamanho da cabeça da seta
        painter.setPen(QPen(QColor(255, 255, 255), 2))
        painter.setBrush(QColor(255, 255, 255))

        angle = math.atan2(-line.dy(), line.dx())
        arrow_p1 = line.p1() + QPointF(math.sin(angle + math.pi / 3) * arrow_size,
                                       math.cos(angle + math.pi / 3) * arrow_size)
        arrow_p2 = line.p1() + QPointF(math.sin(angle + math.pi - math.pi / 3) * arrow_size,
                                       math.cos(angle + math.pi - math.pi / 3) * arrow_size)

        arrow_head = QPolygonF()
        arrow_head << line.p1() << arrow_p1 << arrow_p2

        painter.drawPolygon(arrow_head)
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.main_window.select_edge(self)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        menu = QMenu()

        if self.bidirectional:
            toggle_direction_text = "Tornar Direcional"
            toggle_direction_icon = QIcon('icons/unidirectional_arrow.svg')
        else:
            toggle_direction_text = "Tornar Bidirecional"
            toggle_direction_icon = QIcon('icons/bidirectional_arrow.svg')

        toggle_direction_action = menu.addAction(toggle_direction_icon, toggle_direction_text)
        invert_direction_action = menu.addAction(QIcon('icons/invert_direction.svg'), "Inverter Aresta")
        delete_edge_action = menu.addAction(QIcon('icons/delete.svg'), "Excluir Aresta")

        action = menu.exec_(event.screenPos())
        if action == toggle_direction_action:
            self.main_window.toggle_edge_direction(self)
        elif action == delete_edge_action:
            self.main_window.delete_edge(self)
        elif action == invert_direction_action:
            self.main_window.invert_edge_direction(self)

class CustomGraphicsScene(QGraphicsScene):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent

    def mousePressEvent(self, event):
        item = self.itemAt(event.scenePos(), QTransform())
        if isinstance(item, Edge):
            self.main_window.select_edge(item)
        elif not isinstance(item, Node):
            self.main_window.deselect_item()
        super().mousePressEvent(event)

class HistoryManager:
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def add_action(self, action):
        self.undo_stack.append(action)
        self.redo_stack.clear()  # Limpa o redo stack após uma nova ação

    def undo(self):
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        action.undo()
        self.redo_stack.append(action)

    def redo(self):
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        action.redo()
        self.undo_stack.append(action)

class Action:
    def undo(self):
        raise NotImplementedError

    def redo(self):
        raise NotImplementedError

class AddNodeAction(Action):
    def __init__(self, node, scene, nodes):
        self.node = node
        self.scene = scene
        self.nodes = nodes

    def undo(self):
        self.scene.removeItem(self.node)
        self.nodes.remove(self.node)

    def redo(self):
        self.scene.addItem(self.node)
        self.nodes.append(self.node)

class RemoveNodeAction(Action):
    def __init__(self, node, scene, nodes):
        self.node = node
        self.scene = scene
        self.nodes = nodes

    def undo(self):
        self.scene.addItem(self.node)
        self.nodes.append(self.node)

    def redo(self):
        self.scene.removeItem(self.node)
        self.nodes.remove(self.node)

class AddEdgeAction(Action):
    def __init__(self, edge, scene, edges):
        self.edge = edge
        self.scene = scene
        self.edges = edges

    def undo(self):
        self.scene.removeItem(self.edge)
        self.edges.remove(self.edge)

    def redo(self):
        self.scene.addItem(self.edge)
        self.edges.append(self.edge)

class RemoveEdgeAction(Action):
    def __init__(self, edge, scene, edges):
        self.edge = edge
        self.scene = scene
        self.edges = edges

    def undo(self):
        self.scene.addItem(self.edge)
        self.edges.append(self.edge)

    def redo(self):
        self.scene.removeItem(self.edge)
        self.edges.remove(self.edge)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Controle de Rede de Osciladores')
        self.setWindowIcon(QIcon('icons/icon-black.png'))
        self.setGeometry(100, 100, 800, 600)
        
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        menu = self.menuBar()
        file_menu = menu.addMenu('&Arquivo')
        file_menu.addAction(QIcon('icons/save.svg'), 'Salvar').triggered.connect(self.save_current_configuration)
        file_menu.addAction(QIcon('icons/load.svg'), 'Abrir Arquivo...').triggered.connect(self.load_existing_configuration)
        system_menu = menu.addMenu('&Sistema')
        system_menu.addAction('Configurar Porta Serial').triggered.connect(self.open_config_dialog)
        
        self.layout = QVBoxLayout(self.central_widget)

        self.top_layout = QHBoxLayout()
        self.layout.addLayout(self.top_layout)
        
        # Criar ações para undo e redo
        self.undo_action = QAction('Desfazer', self)
        self.undo_action.setIcon(QIcon('icons/undo.svg'))
        self.undo_action.setShortcut(QKeySequence.Undo)
        self.undo_action.triggered.connect(self.undo)

        self.redo_action = QAction('Refazer', self)
        self.redo_action.setIcon(QIcon('icons/redo.svg'))
        self.redo_action.setShortcut(QKeySequence.Redo)
        self.redo_action.triggered.connect(self.redo)

        # Adicionar ações ao menu
        self.add_actions_to_menus()

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
        
        self.start_button = QPushButton('Iniciar', self)
        self.start_button.clicked.connect(self.start_experiment)
        self.top_layout.addWidget(self.start_button)
        
        self.scene = CustomGraphicsScene(self)
        self.scene.setBackgroundBrush(QColor(30, 30, 30))
        self.view = QGraphicsView(self.scene, self)
        self.layout.addWidget(self.view)
        
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
        
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.keyPressEvent = self.keyPressEvent
    
    def open_config_dialog(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        port, ok = QInputDialog.getItem(self, "Configuração Serial", "Selecione a porta:", ports, 0, False)
        if ok and port:
            baudrate, ok = QInputDialog.getInt(self, "Configuração Serial", "Digite o baudrate:", 9600, 1200, 115200, 1)
            if ok:
                self.serial_port = open_serial_connection(port, baudrate)
    
    def start_experiment(self):
        matrix = self.generate_coupling_matrix()
        print("Matriz de Acoplamento:")
        for row in matrix:
            print(row)
        if self.serial_port:
            send_data_to_microcontroller(self.serial_port, str(matrix))
    
    def add_node(self):
        frequency, ok = QInputDialog.getDouble(self, "Adicionar Nó", "Frequência de Oscilação:", 1.00, 0.01, 100.0, 2)
        if ok:
            if self.available_ids:
                node_id = self.available_ids.pop(0)
            else:
                node_id = self.node_id_counter
                self.node_id_counter += 1
            new_node = Node(100, 100, node_id, self)
            new_node.set_frequency(frequency)
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
                # Deselect the previously selected node
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
        n = len(self.nodes)
        matrix = [[0]*n for _ in range(n)]
        for edge in self.edges:
            start_index = self.nodes.index(edge.start_node)
            end_index = self.nodes.index(edge.end_node)
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
        new_id, ok = QInputDialog.getInt(self, "Editar ID do Nó", "Novo ID:", node.id, 1, 999)
        if ok:
            node.id = new_id
            node.text.setPlainText(str(new_id))  # Atualiza o texto do nó com o novo ID

    def delete_node(self, node):
        if node in self.nodes:
            self.available_ids.append(node.id)
            self.nodes.remove(node)
            self.scene.removeItem(node)
            edges_to_remove = [edge for edge in self.edges if edge.start_node == node or edge.end_node == node]
            for edge in edges_to_remove:
                self.scene.removeItem(edge)
                self.edges.remove(edge)
            self.update_graph()
            self.history_manager.add_action(RemoveNodeAction(node, self.scene, self.nodes))
            for edge in edges_to_remove:
                self.history_manager.add_action(RemoveEdgeAction(edge, self.scene, self.edges))

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
        
        # Clear existing nodes and edges
        for node in self.nodes:
            self.scene.removeItem(node)
        self.nodes.clear()
        for edge in self.edges:
            self.scene.removeItem(edge)
        self.edges.clear()

        # Add nodes
        for node_data in config['nodes']:
            node = Node(node_data['x'], node_data['y'], node_data['id'], self)
            node.set_frequency(node_data['frequency'])
            node.set_color(QColor(node_data['color']))
            self.scene.addItem(node)
            self.nodes.append(node)

        # Add edges
        for edge_data in config['edges']:
            start_node = next(node for node in self.nodes if node.id == edge_data['start_node'])
            end_node = next(node for node in self.nodes if node.id == edge_data['end_node'])
            edge = Edge(start_node, end_node, bidirectional=edge_data['bidirectional'])
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

def open_serial_connection(port, baudrate):
    try:
        ser = serial.Serial(port, baudrate)
        return ser
    except serial.SerialException as e:
        print(f'Erro ao abrir a porta serial: {e}')
        return None

def send_data_to_microcontroller(ser, data):
    if ser:
        try:
            ser.write(data.encode())
        except serial.SerialException as e:
            print(f'Erro ao enviar dados: {e}')

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(load_stylesheet())
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
