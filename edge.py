from PyQt5.QtWidgets import QGraphicsLineItem, QMenu, QStyle
from PyQt5.QtCore import Qt, QPointF, QLineF
from PyQt5.QtGui import QPen, QColor, QPainter, QPolygonF, QIcon
import math

class Edge(QGraphicsLineItem):
    """
    Representa uma aresta entre dois nós em uma cena gráfica.

    Args:
        start_node (Node): O nó inicial da aresta.
        end_node (Node): O nó final da aresta.
        main_window (MainWindow): Referência para a janela principal.
        bidirectional (bool): Se a aresta é bidirecional. Default é False.
    """
    
    def __init__(self, start_node, end_node, main_window, bidirectional=False):
        super().__init__()
        self.main_window = main_window
        self.start_node = start_node
        self.end_node = end_node
        self.bidirectional = bidirectional
        self.setPen(QPen(QColor(255, 255, 255), 2))
        self.update_position()
    
    def update_position(self):
        """
        Atualiza a posição da aresta para manter a tangência aos nós.
        """
        line = QLineF(self.start_node.pos(), self.end_node.pos())
        self.setLine(self.get_tangent_line(line, self.start_node, self.end_node))
        self.update()

    def get_tangent_line(self, line, start_node, end_node):
        """
        Calcula a linha tangente entre os nós.

        Args:
            line (QLineF): A linha entre os dois nós.
            start_node (Node): O nó inicial.
            end_node (Node): O nó final.

        Returns:
            QLineF: A linha tangente ajustada entre os nós.
        """
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
        """
        Sobrescreve o método paint para desenhar a aresta e, se necessário, a seta.

        Args:
            painter (QPainter): O pintor usado para desenhar.
            option (QStyleOptionGraphicsItem): Opções de estilo.
            widget (QWidget): O widget que está sendo pintado.
        """
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
        """
        Desenha uma linha com uma seta na ponta.

        Args:
            painter (QPainter): O pintor usado para desenhar.
            line (QLineF): A linha na qual a seta será desenhada.
        """
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
        """
        Manipula o evento de clique do mouse para selecionar a aresta.

        Args:
            event (QGraphicsSceneMouseEvent): O evento de clique do mouse.
        """
        if event.button() == Qt.LeftButton:
            self.main_window.select_edge(self)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        """
        Cria um menu de contexto para manipular a aresta.

        Args:
            event (QGraphicsSceneContextMenuEvent): O evento de menu de contexto.
        """
        menu = QMenu()
        
        # Se a aresta for bidirecional, adiciona opção para tornar direcional
        if self.bidirectional:
            toggle_direction_text = "Tornar Direcional"
            toggle_direction_icon = QIcon('icons/unidirectional_arrow.svg')
        # Caso contrário, adiciona opção para tornar bidirecional
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
    
    def paint(self, painter, option, widget=None):
        """
        Substitui a renderização padrão para remover a seleção visual (borda de seleção azul quadrada).
        """
        option.state &= ~QStyle.State_Selected  # Remove a seleção
        super().paint(painter, option, widget)
