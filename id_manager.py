class IdManager:
    """
    Gerencia os ids dos nós.
    
    Atributos:
        used_ids (object): Número de ids utilizados.
        available_ids (list): Pilha de ids disponíveis.
    """

    def __init__(self):
        self.used_ids = set()
        self.available_ids = []
        
    def get_next_id(self):
        """
        Retorna o próximo ID disponível mantendo a sequência
        """
        if self.available_ids:
            return min(self.available_ids)
        return len(self.used_ids) + 1
    
    def add_id(self, id):
        """
        Adiciona um ID ao conjunto de IDs usados
        """
        self.used_ids.add(id)
        if id in self.available_ids:
            self.available_ids.remove(id)
            
    def release_id(self, id):
        """
        Libera um ID para reutilização
        """
        if id in self.used_ids:
            self.used_ids.remove(id)
            self.available_ids.append(id)
            
    def swap_ids(self, id1, id2):
        """
        Troca dois IDs garantindo que ambos existam
        """
        if id1 in self.used_ids and id2 in self.used_ids:
            return True
        return False
    
    def is_valid_id(self, new_id):
        """
        Verifica se um novo ID é válido (sequencial)
        """
        if new_id <= 0:
            return False
        max_id = max(self.used_ids) if self.used_ids else 0
        return new_id <= max_id + 1