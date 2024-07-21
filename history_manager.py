class HistoryManager:
    """
    Gerencia as ações de desfazer (undo) e refazer (redo) em uma pilha de ações.
    
    Atributos:
        undo_stack (list): Pilha de ações para desfazer.
        redo_stack (list): Pilha de ações para refazer.
    """
    
    def __init__(self):
        self.undo_stack = []
        self.redo_stack = []

    def add_action(self, action):
        """
        Adiciona uma nova ação à pilha de desfazer e limpa a pilha de refazer.

        Args:
            action (Action): A ação a ser adicionada.
        """
        self.undo_stack.append(action)
        self.redo_stack.clear()  # Limpa o redo stack após uma nova ação

    def undo(self):
        """
        Desfaz a última ação se houver uma ação para desfazer.
        """
        if not self.undo_stack:
            return
        action = self.undo_stack.pop()
        action.undo()
        self.redo_stack.append(action)

    def redo(self):
        """
        Refaz a última ação desfeita se houver uma ação para refazer.
        """
        if not self.redo_stack:
            return
        action = self.redo_stack.pop()
        action.redo()
        self.undo_stack.append(action)

class Action:
    """
    Classe base para todas as ações que podem ser desfeitas ou refeitas.
    """
    
    def undo(self):
        """
        Desfaz a ação. Deve ser implementado pelas subclasses.
        """
        raise NotImplementedError

    def redo(self):
        """
        Refaz a ação. Deve ser implementado pelas subclasses.
        """
        raise NotImplementedError

class AddNodeAction(Action):
    """
    Ação para adicionar um nó à cena.

    Args:
        node (QGraphicsEllipseItem): O nó a ser adicionado.
        scene (QGraphicsScene): A cena à qual o nó será adicionado.
        nodes (list): A lista de nós.
    """
    
    def __init__(self, node, scene, nodes):
        self.node = node
        self.scene = scene
        self.nodes = nodes

    def undo(self):
        """
        Desfaz a adição do nó removendo-o da cena e da lista de nós.
        """
        self.scene.removeItem(self.node)
        self.nodes.remove(self.node)

    def redo(self):
        """
        Refaz a adição do nó adicionando-o novamente à cena e à lista de nós.
        """
        self.scene.addItem(self.node)
        self.nodes.append(self.node)

class RemoveNodeAction(Action):
    """
    Ação para remover um nó da cena.

    Args:
        node (QGraphicsEllipseItem): O nó a ser removido.
        scene (QGraphicsScene): A cena da qual o nó será removido.
        nodes (list): A lista de nós.
    """
    
    def __init__(self, node, scene, nodes):
        self.node = node
        self.scene = scene
        self.nodes = nodes

    def undo(self):
        """
        Desfaz a remoção do nó adicionando-o de volta à cena e à lista de nós.
        """
        self.scene.addItem(self.node)
        self.nodes.append(self.node)

    def redo(self):
        """
        Refaz a remoção do nó removendo-o novamente da cena e da lista de nós.
        """
        self.scene.removeItem(self.node)
        self.nodes.remove(self.node)

class AddEdgeAction(Action):
    """
    Ação para adicionar uma aresta à cena.

    Args:
        edge (QGraphicsLineItem): A aresta a ser adicionada.
        scene (QGraphicsScene): A cena à qual a aresta será adicionada.
        edges (list): A lista de arestas.
    """
    
    def __init__(self, edge, scene, edges):
        self.edge = edge
        self.scene = scene
        self.edges = edges

    def undo(self):
        """
        Desfaz a adição da aresta removendo-a da cena e da lista de arestas.
        """
        self.scene.removeItem(self.edge)
        self.edges.remove(self.edge)

    def redo(self):
        """
        Refaz a adição da aresta adicionando-a novamente à cena e à lista de arestas.
        """
        self.scene.addItem(self.edge)
        self.edges.append(self.edge)

class RemoveEdgeAction(Action):
    """
    Ação para remover uma aresta da cena.

    Args:
        edge (QGraphicsLineItem): A aresta a ser removida.
        scene (QGraphicsScene): A cena da qual a aresta será removida.
        edges (list): A lista de arestas.
    """
    
    def __init__(self, edge, scene, edges):
        self.edge = edge
        self.scene = scene
        self.edges = edges

    def undo(self):
        """
        Desfaz a remoção da aresta adicionando-a de volta à cena e à lista de arestas.
        """
        self.scene.addItem(self.edge)
        self.edges.append(self.edge)

    def redo(self):
        """
        Refaz a remoção da aresta removendo-a novamente da cena e da lista de arestas.
        """
        self.scene.removeItem(self.edge)
        self.edges.remove(self.edge)
