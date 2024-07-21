from qdarktheme import load_stylesheet

def apply_styles(app):
    """
    Aplica o tema escuro à aplicação PyQt5.

    Essa função carrega o stylesheet do tema escuro usando o qdarktheme e aplica esse stylesheet
    à aplicação fornecida.

    Args:
        app (QApplication): Instância da aplicação PyQt5 à qual o tema será aplicado.
    """
    # Carrega o stylesheet do tema escuro
    stylesheet = load_stylesheet()
    
    # Aplica o stylesheet à aplicação
    app.setStyleSheet(stylesheet)
