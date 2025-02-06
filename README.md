# Controle de Rede de Osciladores de Quadratura

## Descrição

A aplicação é uma ferramenta desktop desenvolvida para Windows, projetada para o controle e análise de redes de osciladores de quadratura. A aplicação permite definir a topologia da rede, configurar os parâmetros dos nós e realizar comunicação serial com um microcontrolador STM32 para o gerenciamento dos experimentos. Na pasta "software-microcontrolador" é possível encontrar o software em C responsável por receber os dados da interface no microcontrolador, definir as topologias de forma automática e realizar as medições de frequência dos sinais.

## Funcionalidades

- **Definição de Topologia**: Adicione e configure nós em um grafo interativo. Cada nó pode ser posicionado manualmente e possui parâmetros ajustáveis, como frequência de oscilação e cor.

- **Configuração de Conexões**: Crie conexões direcionadas ou bidirecionais entre os nós.

- **Comunicação Serial**: Conecte-se ao microcontrolador STM32 via UART/USART para enviar dados da topologia e receber medições das senoides de saída.

- **Ajuste de Frequências**: Visualize frequência do sinal de saída dos osciladores em tempo real, auxiliando no ajuste da frequência desejada para os nós da rede.

- **Armazenamento de Topologias**: Salve e carregue topologias de redes para futuras análises. Suporte para configurações e ajustes persistentes.

- **Interface Intuitiva**: A interface gráfica permite adicionar, mover e editar nós com facilidade.

## Instalação

1. **Clone o Repositório**:

   ```bash
   git clone https://github.com/Orwell2002/projeto-software-acoplamento.git

2. **Instale as Dependências**:

    Certifique-se de ter Python 3.8 ou superior instalado. Navegue até o diretório do projeto e instale as dependências com:

    ```bash
    pip install -r requirements.txt
    
3. **Execute a Aplicação**:

    No diretório do projeto, execute:

    ```bash
    python main.py
    ```
    
    Isso abrirá a interface gráfica da aplicação.

4. **Gravação do Microcontrolador**:

   Na pasta software-microcontrolador, abra o projeto tcc.ioc no programa STM32CubeIDE e grave o firmware no microcontrolador.

## Uso

1. **Configuração Inicial**: No canto superior esquerdo, clique no botão de configurações para definir parâmetros iniciais e conectar-se ao microcontrolador.

2. **Adicionar Nós**: Clique no botão de adicionar nó no canto superior direito para inserir novos nós na rede. Posicione-os clicando na tela e ajuste seus parâmetros conforme necessário.

3. **Editar Nós**: Clique com o botão direito em um nó para acessar as opções de edição, incluindo alteração da frequência, cor, e ID.

4. **Conectar Nós**: Clique e arraste entre dois nós para criar uma conexão. Defina se a conexão é direcionada ou bidirecional conforme necessário.

5. **Iniciar Experimento**: Clique no botão "Iniciar" para converter a topologia em uma matriz de acoplamento e enviar os dados para o microcontrolador.

6. **Ajustar Frequência**: Selecione um nó e acompanhe a frequência de oscilação em tempo real, com alta precisão, auxiliando no ajuste para a frequência desejada.
