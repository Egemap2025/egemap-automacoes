import { chromium } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';
import axios from 'axios';
import { logger } from '../../utils/logger';

export type TipoAbertura = 'janela' | 'porta' | 'maxim-ar' | 'porta-janela';
export type TipoAmbiente = 'dormitorio' | 'banheiro' | 'sala' | 'cozinha' | 'area-servico' | 'outro';

export interface Abertura {
  tipo: TipoAbertura;
  largura_cm: number;
  altura_cm: number;
  quantidade: number;
  ambiente: string;
  tipo_ambiente: TipoAmbiente;
}

export interface AnaliseFloorPlan {
  aberturas: Abertura[];
  observacoes: string;
  confianca: 'alta' | 'media' | 'baixa';
}

const PROMPT_ANALISE = `Você é especialista em análise de plantas baixas arquitetônicas para orçamento de esquadrias de alumínio no Brasil.

Analise esta planta baixa e identifique TODAS as aberturas (janelas, portas, maxim-ar, porta-janela).

REFERÊNCIAS VISUAIS em plantas brasileiras:
- Janela: 3 linhas paralelas interrompendo a parede, com arco ou sem
- Porta: arco de 90° indicando a folha, com linha indicando a abertura
- Maxim-Ar: janela pequena geralmente em banheiro (basculante ou maxim-ar)
- As cotas podem estar em cm ou m (ex: 1,20 = 1,20m = 120cm)
- Leia os ambientes pelos textos na planta: "DORM", "BANHEIRO", "SALA", "COZINHA", etc.

RETORNE APENAS JSON VÁLIDO, sem markdown, sem texto extra:
{
  "aberturas": [
    {
      "tipo": "janela",
      "largura_cm": 120,
      "altura_cm": 120,
      "quantidade": 1,
      "ambiente": "Dormitório 1",
      "tipo_ambiente": "dormitorio"
    },
    {
      "tipo": "maxim-ar",
      "largura_cm": 60,
      "altura_cm": 60,
      "quantidade": 1,
      "ambiente": "Banheiro Social",
      "tipo_ambiente": "banheiro"
    },
    {
      "tipo": "porta",
      "largura_cm": 90,
      "altura_cm": 210,
      "quantidade": 1,
      "ambiente": "Entrada Principal",
      "tipo_ambiente": "outro"
    }
  ],
  "observacoes": "Casa com 2 dormitórios, 1 banheiro social, sala e cozinha integradas.",
  "confianca": "alta"
}

REGRAS:
- tipo_ambiente deve ser um de: "dormitorio", "banheiro", "sala", "cozinha", "area-servico", "outro"
- tipo deve ser um de: "janela", "porta", "maxim-ar", "porta-janela"
- Se não conseguir ler dimensão exata, estime com base nas proporções
- confianca: "alta" se planta clara, "media" se algumas dúvidas, "baixa" se planta ilegível
- Agrupe aberturas iguais no mesmo ambiente (use quantidade > 1)
- Portas internas de madeira NÃO incluir (apenas portas de alumínio externas/principais)`;

const OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions';
// Modelo gratuito no OpenRouter com boa capacidade de visão
const MODEL = 'google/gemini-flash-1.5:free';

export class FloorPlanAnalyzer {
  private apiKey: string;

  constructor() {
    const apiKey = process.env.OPENROUTER_API_KEY;
    if (!apiKey) throw new Error('OPENROUTER_API_KEY não configurado no .env');
    this.apiKey = apiKey;
  }

  async analisar(pdfPath: string): Promise<AnaliseFloorPlan> {
    logger.info(`Analisando planta: ${pdfPath}`);

    // Converte PDF para imagem usando o Chromium já instalado
    const imagemBase64 = await this.pdfParaImagem(pdfPath);

    logger.info('Enviando imagem para análise com IA...');

    const response = await axios.post(
      OPENROUTER_URL,
      {
        model: MODEL,
        messages: [
          {
            role: 'user',
            content: [
              {
                type: 'image_url',
                image_url: {
                  url: `data:image/png;base64,${imagemBase64}`,
                },
              },
              {
                type: 'text',
                text: PROMPT_ANALISE,
              },
            ],
          },
        ],
        max_tokens: 4096,
      },
      {
        headers: {
          Authorization: `Bearer ${this.apiKey}`,
          'Content-Type': 'application/json',
          'HTTP-Referer': 'https://github.com/Egemap2025/egemap-automacoes',
          'X-Title': 'Egemap Automações',
        },
        timeout: 120000,
      }
    );

    const rawText: string = response.data.choices[0]?.message?.content?.trim() ?? '';

    try {
      const parsed = JSON.parse(rawText) as AnaliseFloorPlan;
      logger.info(`Análise concluída: ${parsed.aberturas.length} grupos, confiança: ${parsed.confianca}`);
      return parsed;
    } catch {
      const match = rawText.match(/\{[\s\S]*\}/);
      if (match) {
        return JSON.parse(match[0]) as AnaliseFloorPlan;
      }
      throw new Error(`Resposta inválida da IA: ${rawText.substring(0, 300)}`);
    }
  }

  private async pdfParaImagem(pdfPath: string): Promise<string> {
    logger.info('Convertendo PDF para imagem via Chromium...');

    const browser = await chromium.launch({
      headless: true,
      executablePath: process.env.CHROMIUM_PATH || undefined,
      args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu'],
    });

    try {
      const page = await browser.newPage();
      // Viewport largo para capturar planta inteira com boa resolução
      await page.setViewportSize({ width: 1920, height: 2560 });

      const fileUrl = `file://${path.resolve(pdfPath)}`;
      await page.goto(fileUrl, { waitUntil: 'networkidle', timeout: 30000 });

      // Aguarda o PDF renderizar completamente no Chromium
      await page.waitForTimeout(3000);

      const screenshot = await page.screenshot({
        fullPage: true,
        type: 'png',
      });

      const base64 = screenshot.toString('base64');
      logger.info(`Imagem gerada: ${Math.round(base64.length / 1024)} KB`);
      return base64;
    } finally {
      await browser.close();
    }
  }
}
