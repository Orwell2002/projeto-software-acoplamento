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
#define START_MARKER '<'
#define END_MARKER '>'
#define ADC_BUFFER_SIZE 8  // Buffer para 8 canais do ADC
#define PCF8574_BASE_ADDRESS 0x40  // Endereço base do PCF8574 (A2, A1, A0 = 000)
/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
ADC_HandleTypeDef hadc1;
DMA_HandleTypeDef hdma_adc1;

I2C_HandleTypeDef hi2c1;

/* USER CODE BEGIN PV */
uint8_t buffer[64];
uint8_t full_buffer[1024];
volatile uint8_t dataComplete = 0;
volatile uint8_t receivingData = 0;
uint16_t adc_buffer[ADC_BUFFER_SIZE];  // Buffer para armazenar os valores do ADC
volatile uint8_t adc_conversion_complete = 0;
volatile uint8_t config_complete = 0;  // Flag indicando que a configuração foi concluída
float matrix[ADC_BUFFER_SIZE][ADC_BUFFER_SIZE];
uint8_t matrixSize = 0;
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
void SystemClock_Config(void);
static void MX_GPIO_Init(void);
static void MX_DMA_Init(void);
static void MX_ADC1_Init(void);
static void MX_I2C1_Init(void);
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

// Função para imprimir matriz na serial (usada no debug)
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

void HAL_ADC_ConvCpltCallback(ADC_HandleTypeDef* hadc)
{
    if (hadc->Instance == ADC1)
    {
        adc_conversion_complete = 1;  // Flag para indicar que a conversão terminou
    }
}

// Verifica se I2C está pronto
HAL_StatusTypeDef I2C_IsDeviceReady(uint8_t i)
{
    return HAL_I2C_IsDeviceReady(&hi2c1, PCF8574_BASE_ADDRESS + i, 3, HAL_MAX_DELAY);
}

// Envia dados do ADC pela serial
void Send_ADC_USB(void)
{
    uint8_t usb_tx_buffer[ADC_BUFFER_SIZE * 3];  // 3 bytes por canal (1 byte para o ID e 2 bytes para o valor do ADC)
    for (int i = 0; i < ADC_BUFFER_SIZE; i++)
    {
        usb_tx_buffer[i * 3] = i;  // ID do canal (0-7)
        usb_tx_buffer[i * 3 + 1] = adc_buffer[i] & 0xFF;  // LSB do valor do ADC
        usb_tx_buffer[i * 3 + 2] = (adc_buffer[i] >> 8) & 0xFF;  // MSB do valor do ADC
    }
    CDC_Transmit_FS(usb_tx_buffer, sizeof(usb_tx_buffer));
}

// Função para processar um byte recebido
void Process_Byte(uint8_t byte)
{
    static uint8_t row = 0;
    static uint8_t col = 0;

    if (byte == START_MARKER) {
    	Reset_Matrix();
        row = 0;
        col = 0;
        receivingData = 1;
        return;
    }

    if (byte == END_MARKER) {
        receivingData = 0;
        dataComplete = 1;
        matrixSize = row + 1;	 // Adiciona +1 pois a última linha também conta
        return;
    }

    if (receivingData) {
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
  /* USER CODE BEGIN 2 */

  // Pequeno delay para estabilização do I2C
  HAL_Delay(100);

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
  HAL_ADC_Start_DMA(&hadc1, (uint32_t*)adc_buffer, ADC_BUFFER_SIZE);

  /* USER CODE END 2 */

  /* Infinite loop */
  /* USER CODE BEGIN WHILE */
  while (1)
  {
    /* USER CODE END WHILE */

    /* USER CODE BEGIN 3 */
	    if (dataComplete) {
	    	Update_I2C_Outputs();
	        dataComplete = 0;
	        config_complete = 1;
	    }

	    if (config_complete && adc_conversion_complete)
	    {
	        Send_ADC_USB();
	        adc_conversion_complete = 0;
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
