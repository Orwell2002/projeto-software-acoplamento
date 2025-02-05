/* USER CODE BEGIN Header */
/**
  ******************************************************************************
  * @file           : main.c
  * @brief          : Main program body
  ******************************************************************************
  * @attention
  *
  * Copyright (c) 2024 STMicroelectronics.
  * All rights reserved.
  *
  * This software is licensed under terms that can be found in the LICENSE file
  * in the root directory of this software component.
  * If no LICENSE file comes with this software, it is provided AS-IS.
  *
  ******************************************************************************
  */
/* USER CODE END Header */
/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "usb_device.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "usbd_cdc_if.h"
#include "string.h"
#include <stdio.h>
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN PTD */

/* USER CODE END PTD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */
#define START_MARKER '<'			// Marcador de inicio de matriz
#define END_MARKER '>'				// Marcador de fim de matriz
#define MODE_MATRIX 0				// Definir 0 como modo de operação para configuração de matrizes
#define MODE_FREQUENCY 1			// Definir 1 como modo de operação para ajuste de frequência
#define START_FREQ_CMD 0xF0    		// Comando para iniciar modo de frequência
#define STOP_FREQ_CMD 0xF1     		// Comando para parar modo de frequência
#define ADC_BUFFER_SIZE 8  			// Buffer para 8 canais do ADC
#define FREQ_BUFFER_SIZE 10			// Buffer frequência para cálculo da média móvel
#define FREQ_MULTIPLIER 100  		// Para manter 2 casas decimais
#define PCF8574_BASE_ADDRESS 0x40  	// Endereço base do PCF8574 (A2, A1, A0 = 000)
#define HYSTERESIS_HIGH 1850  // ~55% de 4095
#define HYSTERESIS_LOW 1750   // ~45% de 4095
#define MOVING_AVG_SIZE 10
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;
ADC_HandleTypeDef hadc2;
DMA_HandleTypeDef hdma_adc1;

I2C_HandleTypeDef hi2c1;

TIM_HandleTypeDef htim3;

/* USER CODE BEGIN PV */
// Variávies do acoplamento de rede
volatile uint8_t dataComplete = 0;				// Indica que matriz terminou de ser recebida
volatile uint8_t receivingMatrix = 0;			// Indica que matriz está sendo recebida
volatile uint8_t config_complete = 0;			// Indica que configuração de matriz foi completa
float matrix[ADC_BUFFER_SIZE][ADC_BUFFER_SIZE];	// Matriz de adjascencia da rede
uint8_t matrixSize = 0;							// Tamanho da matriz

// Variáveis da medição de frequência
volatile uint8_t operating_mode = MODE_MATRIX;	// Define tipo de operação, inicializa como definição de matriz
uint32_t last_rising_edge = 0;					// Tempo da última borda de descida
uint32_t periods[MOVING_AVG_SIZE];				// Vetor de períodos de oscilação
uint8_t period_index = 0;						// Índice do último período
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_ADC1_Init(void);
static void MX_I2C1_Init(void);
static void MX_ADC2_Init(void);
static void MX_TIM3_Init(void);
/* USER CODE BEGIN PFP */

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

// Função para resetar todos os PCF8574
void Reset_All_PCF8574(void)
{
    uint8_t resetValue = 0x00;  // Desligar todos os LEDs
    for (uint8_t i = 0; i < ADC_BUFFER_SIZE; i++)
    {
        HAL_StatusTypeDef status = HAL_I2C_Master_Transmit(&hi2c1, PCF8574_BASE_ADDRESS + i, &resetValue, 1, HAL_MAX_DELAY);
        if (status != HAL_OK)
        {
            // Opcional: Adicione um log ou tratamento de erro
            HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
            HAL_Delay(10);
            HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
        }
    }
}

// Função para resetar matriz de adjascencia antes de receber nova
void Reset_Matrix(void) {
    for(uint8_t i = 0; i < ADC_BUFFER_SIZE; i++) {
        for(uint8_t j = 0; j < ADC_BUFFER_SIZE; j++) {
            matrix[i][j] = 0;
        }
    }
}

// DEBUG -> Função para imprimir matriz na serial
void Print_Matrix_USB(void) {
    char line_buffer[128]; // Buffer para armazenar uma linha da matriz
    CDC_Transmit_FS((uint8_t *)"\n", 1); // Linha vazia para separação
    for (uint8_t i = 0; i < matrixSize; i++) {
        int pos = 0; // Posicionamento no buffer
        for (uint8_t j = 0; j < matrixSize; j++) {
            pos += sprintf(&line_buffer[pos], "%d ", (int)matrix[i][j]); // Concatena valores na linha
        }
        line_buffer[pos++] = '\n'; // Adiciona quebra de linha
        line_buffer[pos] = '\0';   // Finaliza a string
        CDC_Transmit_FS((uint8_t *)line_buffer, strlen(line_buffer)); // Envia a linha via USB
        HAL_Delay(50); // Pequeno delay para evitar sobrecarga de dados no Hercules
    }
    CDC_Transmit_FS((uint8_t *)"\n", 1); // Linha vazia para separação
}

// Verifica se I2C está pronto
HAL_StatusTypeDef I2C_IsDeviceReady(uint8_t i)
{
    return HAL_I2C_IsDeviceReady(&hi2c1, PCF8574_BASE_ADDRESS + i, 3, HAL_MAX_DELAY);
}

// Função para processar um byte recebido
void Process_Byte(uint8_t byte)
{
    static uint8_t row = 0;
    static uint8_t col = 0;

    // Verificar comandos de modo primeiro
    if (byte == START_FREQ_CMD) {
        operating_mode = MODE_FREQUENCY;
        // Iniciar timer e ADC2 para medição de frequência
        HAL_TIM_Base_Start(&htim3);
        HAL_ADC_Start_IT(&hadc2);
        // Enviar confirmação
        uint8_t msg[] = "Starting frequency measurement mode\r\n";
        CDC_Transmit_FS(msg, strlen((char*)msg));
        return;
    }
    else if (byte == STOP_FREQ_CMD) {
        operating_mode = MODE_MATRIX;
        // Parar timer e ADC2
        HAL_TIM_Base_Stop(&htim3);
        HAL_ADC_Stop_IT(&hadc2);
        // Enviar confirmação
        uint8_t msg[] = "Stopping frequency measurement mode\r\n";
        CDC_Transmit_FS(msg, strlen((char*)msg));
        return;
    }

    // Processamento normal da matriz se estiver no modo matriz
    if (operating_mode == MODE_MATRIX) {
        if (byte == START_MARKER) {
            Reset_Matrix();
            row = 0;
            col = 0;
            receivingMatrix = 1;
            return;
        }

        if (byte == END_MARKER) {
            receivingMatrix = 0;
            dataComplete = 1;
            matrixSize = row + 1;
            return;
        }

        if (receivingMatrix) {
            if (byte == '1') {
                matrix[row][col] = 1;
            } else if (byte == '0') {
                matrix[row][col] = 0;
            } else if (byte == ',') {
                col++;
            } else if (byte == ';') {
                row++;
                col = 0;
            }
        }
    }
}


// Função para atualizar as saídas I2C baseada na matriz
void Update_I2C_Outputs(void) {
    Print_Matrix_USB(); // Chama a função para imprimir a matriz na serial
    for (uint8_t i = 0; i < matrixSize; i++) {
        uint8_t outputByte = 0;

        // Converte cada linha da matriz em um byte para o PCF8574
        for (uint8_t j = 0; j < matrixSize; j++) {
            if (matrix[i][j]) {
                outputByte |= (1 << j);
            }
        }

        // Envia o byte para o PCF8574 correspondente
        HAL_I2C_Master_Transmit(&hi2c1, PCF8574_BASE_ADDRESS + i, &outputByte, 1, HAL_MAX_DELAY);
    }

    // uint8_t outputBytes[2] = {0, 0}; // Dois módulos PCF8574
    
    // // Mapeamento manual para a nova configuração 3x3
    // outputBytes[0] |= (matrix[0][0] << 0); // P0  -> matriz[0][0]
    // outputBytes[0] |= (matrix[0][1] << 1); // P1  -> matriz[0][1]
    // outputBytes[0] |= (matrix[0][2] << 2); // P2  -> matriz[0][2]
    // outputBytes[0] |= (matrix[1][0] << 3); // P3  -> matriz[1][0]
    // outputBytes[0] |= (matrix[1][1] << 4); // P4  -> matriz[1][1]
    // outputBytes[0] |= (matrix[1][2] << 5); // P5  -> matriz[1][2]
    // outputBytes[0] |= (matrix[2][0] << 6); // P6  -> matriz[2][0]
    // outputBytes[0] |= (matrix[2][1] << 7); // P7  -> matriz[2][1]
    
    // outputBytes[1] |= (matrix[2][2] << 0); // P0 (segundo módulo) -> matriz[2][2]
    
    // // Envia os bytes para os dois módulos PCF8574
    // HAL_I2C_Master_Transmit(&hi2c1, PCF8574_BASE_ADDRESS + 0, &outputBytes[0], 1, HAL_MAX_DELAY);
    // HAL_I2C_Master_Transmit(&hi2c1, PCF8574_BASE_ADDRESS + 1, &outputBytes[1], 1, HAL_MAX_DELAY);

    // Piscar LED para indicação
    HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
    HAL_Delay(50);
    HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
    HAL_Delay(100);
    HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
    HAL_Delay(100);
    HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);

    // Envia confirmação pela USB
    uint8_t ack[] = "ACK\n";
    CDC_Transmit_FS(ack, 5);
}

// Detecção de borda com histerese
uint8_t Detect_Rising_Edge(uint16_t current_value, uint16_t *last_value) {
    static uint8_t state = 0;  // 0: baixo, 1: alto

    if (state == 0 && current_value > HYSTERESIS_HIGH) {
        state = 1;
        *last_value = current_value;
        return 1;
    }
    else if (state == 1 && current_value < HYSTERESIS_LOW) {
        state = 0;
    }

    *last_value = current_value;
    return 0;
}

// Cálculo de frequência com média móvel
float Calculate_Frequency(uint32_t new_period) {
    periods[period_index] = new_period;
    period_index = (period_index + 1) % MOVING_AVG_SIZE;

    uint32_t avg_period = 0;
    for(uint8_t i = 0; i < MOVING_AVG_SIZE; i++) {
        avg_period += periods[i];
    }
    avg_period /= MOVING_AVG_SIZE;

    // Converte período em ms para frequência em Hz
    if(avg_period > 0) {
        return 1000.0f / avg_period;
    }
    return 0.0f;
}

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
//    if (hadc->Instance == ADC1)
//    {
//        adc_conversion_complete = 1;
//    }
    if(hadc->Instance == ADC2 && operating_mode == MODE_FREQUENCY) {
        static uint16_t last_value = 0;
        uint16_t current_value = HAL_ADC_GetValue(hadc);

        // Detecta borda de subida com histerese
        if(Detect_Rising_Edge(current_value, &last_value)) {
            uint32_t current_time = HAL_GetTick();

            if(last_rising_edge > 0) {
                uint32_t period = current_time - last_rising_edge;
                float freq = Calculate_Frequency(period);

                char freq_str[50];
                int32_t int_part = (int32_t)freq;
                int32_t dec_part = (int32_t)((freq - int_part) * 100);
                sprintf(freq_str, "#FRQ:%ld.%02ld$\r\n", int_part, dec_part);
                CDC_Transmit_FS((uint8_t*)freq_str, strlen(freq_str));
            }
            last_rising_edge = current_time;
        }

        HAL_ADC_Start_IT(hadc);
    }
}
/* USER CODE END 0 */

/**
  * @brief  The application entry point.
  * @retval int
  */
int main(void)
{
  /* USER CODE BEGIN 1 */

  /* USER CODE END 1 */

  /* MCU Configuration--------------------------------------------------------*/

  /* Reset of all peripherals, Initializes the Flash interface and the Systick. */
  HAL_Init();

  /* USER CODE BEGIN Init */

  /* USER CODE END Init */

  /* Configure the system clock */
  SystemClock_Config();

  /* USER CODE BEGIN SysInit */

  /* USER CODE END SysInit */

  /* Initialize all configured peripherals */
  MX_GPIO_Init();
  MX_DMA_Init();
  MX_USB_DEVICE_Init();
  MX_ADC1_Init();
  MX_I2C1_Init();
  MX_ADC2_Init();
  MX_TIM3_Init();
  /* USER CODE BEGIN 2 */

  // Pequeno delay para estabilização do I2C
  HAL_Delay(100);

  HAL_ADC_Start(&hadc2);

  // Verifica se o PCF8574 está respondendo
//  if (I2C_IsDeviceReady(0) != HAL_OK)
//  {
//      // Dispositivo não encontrado - piscar LED de erro
//      while(I2C_IsDeviceReady(0) != HAL_OK)
//      {
//          HAL_GPIO_TogglePin(LED_GPIO_Port, LED_Pin);
//          HAL_Delay(100);
//      }
//  }

  // Reseta todos os PCF8574 para desligar LEDs
  Reset_All_PCF8574();

  // Inicialização do ADC
  // HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, ADC_BUFFER_SIZE);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
      if (operating_mode == MODE_MATRIX) {
          if (dataComplete) {
              Update_I2C_Outputs();
              dataComplete = 0;
              config_complete = 1;
          }
      }

	}
  /* USER CODE END 3 */
}

/**
  * @brief System Clock Configuration
  * @retval None
  */
void SystemClock_Config(void)
{
  RCC_OscInitTypeDef RCC_OscInitStruct = {0};
  RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};
  RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};

  /** Initializes the RCC Oscillators according to the specified parameters
  * in the RCC_OscInitTypeDef structure.
  */
  RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSE;
  RCC_OscInitStruct.HSEState = RCC_HSE_ON;
  RCC_OscInitStruct.HSEPredivValue = RCC_HSE_PREDIV_DIV1;
  RCC_OscInitStruct.HSIState = RCC_HSI_ON;
  RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
  RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSE;
  RCC_OscInitStruct.PLL.PLLMUL = RCC_PLL_MUL6;
  if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
  {
    Error_Handler();
  }

  /** Initializes the CPU, AHB and APB buses clocks
  */
  RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK|RCC_CLOCKTYPE_SYSCLK
                              |RCC_CLOCKTYPE_PCLK1|RCC_CLOCKTYPE_PCLK2;
  RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
  RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
  RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV2;
  RCC_ClkInitStruct.APB2CLKDivider = RCC_HCLK_DIV1;

  if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_1) != HAL_OK)
  {
    Error_Handler();
  }
  PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_ADC|RCC_PERIPHCLK_USB;
  PeriphClkInit.AdcClockSelection = RCC_ADCPCLK2_DIV4;
  PeriphClkInit.UsbClockSelection = RCC_USBCLKSOURCE_PLL;
  if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
  {
    Error_Handler();
  }
}

/**
  * @brief ADC1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC1_Init(void)
{

  /* USER CODE BEGIN ADC1_Init 0 */

  /* USER CODE END ADC1_Init 0 */

  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC1_Init 1 */

  /* USER CODE END ADC1_Init 1 */

  /** Common config
  */
  hadc1.Instance = ADC1;
  hadc1.Init.ScanConvMode = ADC_SCAN_ENABLE;
  hadc1.Init.ContinuousConvMode = ENABLE;
  hadc1.Init.DiscontinuousConvMode = DISABLE;
  hadc1.Init.ExternalTrigConv = ADC_SOFTWARE_START;
  hadc1.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc1.Init.NbrOfConversion = 8;
  if (HAL_ADC_Init(&hadc1) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_1;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_71CYCLES_5;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_2;
  sConfig.Rank = ADC_REGULAR_RANK_2;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_3;
  sConfig.Rank = ADC_REGULAR_RANK_3;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_4;
  sConfig.Rank = ADC_REGULAR_RANK_4;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_5;
  sConfig.Rank = ADC_REGULAR_RANK_5;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_6;
  sConfig.Rank = ADC_REGULAR_RANK_6;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_7;
  sConfig.Rank = ADC_REGULAR_RANK_7;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_8;
  sConfig.Rank = ADC_REGULAR_RANK_8;
  if (HAL_ADC_ConfigChannel(&hadc1, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC1_Init 2 */

  /* USER CODE END ADC1_Init 2 */

}

/**
  * @brief ADC2 Initialization Function
  * @param None
  * @retval None
  */
static void MX_ADC2_Init(void)
{

  /* USER CODE BEGIN ADC2_Init 0 */

  /* USER CODE END ADC2_Init 0 */

  ADC_ChannelConfTypeDef sConfig = {0};

  /* USER CODE BEGIN ADC2_Init 1 */

  /* USER CODE END ADC2_Init 1 */

  /** Common config
  */
  hadc2.Instance = ADC2;
  hadc2.Init.ScanConvMode = ADC_SCAN_DISABLE;
  hadc2.Init.ContinuousConvMode = DISABLE;
  hadc2.Init.DiscontinuousConvMode = DISABLE;
  hadc2.Init.ExternalTrigConv = ADC_EXTERNALTRIGCONV_T3_TRGO;
  hadc2.Init.DataAlign = ADC_DATAALIGN_RIGHT;
  hadc2.Init.NbrOfConversion = 1;
  if (HAL_ADC_Init(&hadc2) != HAL_OK)
  {
    Error_Handler();
  }

  /** Configure Regular Channel
  */
  sConfig.Channel = ADC_CHANNEL_9;
  sConfig.Rank = ADC_REGULAR_RANK_1;
  sConfig.SamplingTime = ADC_SAMPLETIME_71CYCLES_5;
  if (HAL_ADC_ConfigChannel(&hadc2, &sConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN ADC2_Init 2 */

  /* USER CODE END ADC2_Init 2 */

}

/**
  * @brief I2C1 Initialization Function
  * @param None
  * @retval None
  */
static void MX_I2C1_Init(void)
{

  /* USER CODE BEGIN I2C1_Init 0 */

  /* USER CODE END I2C1_Init 0 */

  /* USER CODE BEGIN I2C1_Init 1 */

  /* USER CODE END I2C1_Init 1 */
  hi2c1.Instance = I2C1;
  hi2c1.Init.ClockSpeed = 100000;
  hi2c1.Init.DutyCycle = I2C_DUTYCYCLE_2;
  hi2c1.Init.OwnAddress1 = 0;
  hi2c1.Init.AddressingMode = I2C_ADDRESSINGMODE_7BIT;
  hi2c1.Init.DualAddressMode = I2C_DUALADDRESS_DISABLE;
  hi2c1.Init.OwnAddress2 = 0;
  hi2c1.Init.GeneralCallMode = I2C_GENERALCALL_DISABLE;
  hi2c1.Init.NoStretchMode = I2C_NOSTRETCH_DISABLE;
  if (HAL_I2C_Init(&hi2c1) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN I2C1_Init 2 */

  /* USER CODE END I2C1_Init 2 */

}

/**
  * @brief TIM3 Initialization Function
  * @param None
  * @retval None
  */
static void MX_TIM3_Init(void)
{

  /* USER CODE BEGIN TIM3_Init 0 */

  /* USER CODE END TIM3_Init 0 */

  TIM_ClockConfigTypeDef sClockSourceConfig = {0};
  TIM_MasterConfigTypeDef sMasterConfig = {0};

  /* USER CODE BEGIN TIM3_Init 1 */

  /* USER CODE END TIM3_Init 1 */
  htim3.Instance = TIM3;
  htim3.Init.Prescaler = 4800-1;
  htim3.Init.CounterMode = TIM_COUNTERMODE_UP;
  htim3.Init.Period = 10-1;
  htim3.Init.ClockDivision = TIM_CLOCKDIVISION_DIV1;
  htim3.Init.AutoReloadPreload = TIM_AUTORELOAD_PRELOAD_DISABLE;
  if (HAL_TIM_Base_Init(&htim3) != HAL_OK)
  {
    Error_Handler();
  }
  sClockSourceConfig.ClockSource = TIM_CLOCKSOURCE_INTERNAL;
  if (HAL_TIM_ConfigClockSource(&htim3, &sClockSourceConfig) != HAL_OK)
  {
    Error_Handler();
  }
  sMasterConfig.MasterOutputTrigger = TIM_TRGO_UPDATE;
  sMasterConfig.MasterSlaveMode = TIM_MASTERSLAVEMODE_DISABLE;
  if (HAL_TIMEx_MasterConfigSynchronization(&htim3, &sMasterConfig) != HAL_OK)
  {
    Error_Handler();
  }
  /* USER CODE BEGIN TIM3_Init 2 */

  /* USER CODE END TIM3_Init 2 */

}

/**
  * Enable DMA controller clock
  */
static void MX_DMA_Init(void)
{

  /* DMA controller clock enable */
  __HAL_RCC_DMA1_CLK_ENABLE();

  /* DMA interrupt init */
  /* DMA1_Channel1_IRQn interrupt configuration */
  HAL_NVIC_SetPriority(DMA1_Channel1_IRQn, 0, 0);
  HAL_NVIC_EnableIRQ(DMA1_Channel1_IRQn);

}

/**
  * @brief GPIO Initialization Function
  * @param None
  * @retval None
  */
static void MX_GPIO_Init(void)
{
  GPIO_InitTypeDef GPIO_InitStruct = {0};
/* USER CODE BEGIN MX_GPIO_Init_1 */
/* USER CODE END MX_GPIO_Init_1 */

  /* GPIO Ports Clock Enable */
  __HAL_RCC_GPIOC_CLK_ENABLE();
  __HAL_RCC_GPIOD_CLK_ENABLE();
  __HAL_RCC_GPIOA_CLK_ENABLE();
  __HAL_RCC_GPIOB_CLK_ENABLE();

  /*Configure GPIO pin Output Level */
  HAL_GPIO_WritePin(LED_GPIO_Port, LED_Pin, GPIO_PIN_SET);

  /*Configure GPIO pin : LED_Pin */
  GPIO_InitStruct.Pin = LED_Pin;
  GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
  HAL_GPIO_Init(LED_GPIO_Port, &GPIO_InitStruct);

  /*Configure GPIO pin : PA0 */
  GPIO_InitStruct.Pin = GPIO_PIN_0;
  GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
  GPIO_InitStruct.Pull = GPIO_NOPULL;
  HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

/* USER CODE BEGIN MX_GPIO_Init_2 */
/* USER CODE END MX_GPIO_Init_2 */
}

/* USER CODE BEGIN 4 */

/* USER CODE END 4 */

/**
  * @brief  This function is executed in case of error occurrence.
  * @retval None
  */
void Error_Handler(void)
{
  /* USER CODE BEGIN Error_Handler_Debug */
  /* User can add his own implementation to report the HAL error return state */
  __disable_irq();
  while (1)
  {
  }
  /* USER CODE END Error_Handler_Debug */
}

#ifdef  USE_FULL_ASSERT
/**
  * @brief  Reports the name of the source file and the source line number
  *         where the assert_param error has occurred.
  * @param  file: pointer to the source file name
  * @param  line: assert_param error line source number
  * @retval None
  */
void assert_failed(uint8_t *file, uint32_t line)
{
  /* USER CODE BEGIN 6 */
  /* User can add his own implementation to report the file name and line number,
     ex: printf("Wrong parameters value: file %s on line %d\r\n", file, line) */
  /* USER CODE END 6 */
}
#endif /* USE_FULL_ASSERT */
