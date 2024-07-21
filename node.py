from PyQt5.QtWidgets import QGraphicsEllipseItem, QGraphicsTextItem, QGraphicsItem, QMenu
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor, QPen, QIcon

class Node(QGraphicsEllipseItem):
    """
    Representa um nó em um grafo visualizado usando QGraphicsEllipseItem.

    Atributos:
        id (int): Identificador do nó.
        frequency (float): Frequência associada ao nó (inicialmente None).
        main_window (MainWindow): Referência para a janela principal da aplicação.
        default_color (QColor): Cor padrão do nó.
        text (QGraphicsTextItem): Texto exibido com o ID do nó.
        frequency_text (QGraphicsTextItem): Texto exibido com a frequência do nó.
    """

    def __init__(self, x, y, id, main_window, parent=None):
        """
        Inicializa um novo nó no grafo.

        Args:
            x (float): Coordenada X do nó.
            y (float): Coordenada Y do nó.
            id (int): Identificador do nó.
            main_window (MainWindow): Referência para a janela principal da aplicação.
            parent (QGraphicsItem, optional): Item pai para o nó. Padrão é None.
        """
        QGraphicsEllipseItem.__init__(self, parent)
        self.main_window = main_window

        # Configura o retângulo do nó
        self.setRect(-23, -23, 43, 43)
        self.default_color = QColor(100, 100, 255, 150)
        self.setBrush(self.default_color)
        self.update_border_color()

        # Define a posição inicial do nó
        self.setPos(x, y)

        self.id = id
        self.frequency = None

        # Configura o texto do ID do nó
        font = QFont("Arial", 14)
        font.setBold(True)
        self.text = QGraphicsTextItem(str(self.id), self)
        self.text.setFont(font)
        self.text.setDefaultTextColor(QColor(255, 255, 255))
        self.update_text_position()

        # Configura o nó para ser movível e aceitar eventos de hover
        self.setFlag(QGraphicsItem.ItemIsMovable)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.ItemSendsGeometryChanges)

        # Configura o texto da frequência do nó
        frequency_font = QFont("Arial", 10)
        self.frequency_text = QGraphicsTextItem('', self)
        self.frequency_text.setFont(frequency_font)
        self.frequency_text.setDefaultTextColor(QColor(255, 255, 255))
        self.update_frequency_text_position()
    
    def set_color(self, color):
        """
        Define a cor do nó e atualiza a borda.

        Args:
            color (QColor): Nova cor para o nó.
        """
        self.default_color = color
        self.setBrush(color)
        self.update_border_color()

    def update_border_color(self):
        """
        Atualiza a cor da borda do nó para um tom mais escuro da cor padrão.
        """
        darker_color = self.default_color.darker(150)
        self.setPen(QPen(darker_color, 4))

    def update_text_position(self):
        """
        Atualiza a posição do texto do ID do nó para centralizá-lo no nó.
        """
        rect = self.boundingRect()
        text_rect = self.text.boundingRect()
        self.text.setPos(rect.center() - text_rect.center())

    def update_frequency_text_position(self):
        """
        Atualiza a posição do texto da frequência para que fique logo abaixo do nó.
        """
        rect = self.boundingRect()
        text_rect = self.frequency_text.boundingRect()
        self.frequency_text.setPos(rect.center().x() - text_rect.width() / 2, rect.bottom() + 5)

    def mousePressEvent(self, event):
        """
        Manipula o evento de clique do mouse. Seleciona o nó quando o botão esquerdo do mouse é pressionado.

        Args:
            event (QGraphicsSceneMouseEvent): Evento de clique do mouse.
        """
        if event.button() == Qt.LeftButton:
            self.main_window.select_node(self)
        super().mousePressEvent(event)

    def itemChange(self, change, value):
        """
        Manipula mudanças no item, como a mudança de posição. Atualiza o grafo se a posição do nó mudar.

        Args:
            change (QGraphicsItem.GraphicsItemChange): Tipo de mudança no item.
            value (QVariant): Novo valor da mudança.

        Returns:
            QVariant: Valor modificado pelo item.
        """
        if change == QGraphicsItem.ItemPositionChange:
            self.main_window.update_graph()
        return super().itemChange(change, value)

    def contextMenuEvent(self, event):
        """
        Exibe o menu de contexto quando o botão direito do mouse é clicado sobre o nó.

        Args:
            event (QGraphicsSceneContextMenuEvent): Evento de menu de contexto.
        """
        menu = QMenu()

        # Adiciona ações ao menu de contexto
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
        """
        Define a frequência do nó e atualiza o texto da frequência.

        Args:
            frequency (float): Nova frequência para o nó.
        """
        self.frequency = frequency
        self.update_frequency_text()
    
    def update_frequency_text(self):
        """
        Atualiza o texto exibido com a frequência do nó. Se a frequência for None, o texto é limpo.
        """
        if self.frequency is not None:
            self.frequency_text.setPlainText(f'{self.frequency:.2f} Hz')
        else:
            self.frequency_text.setPlainText('')
