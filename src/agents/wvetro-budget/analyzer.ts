import { GoogleGenerativeAI } from '@google/generative-ai';
import { GoogleAIFileManager } from '@google/generative-ai/server';
import * as fs from 'fs';
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

export class FloorPlanAnalyzer {
  private genAI: GoogleGenerativeAI;
  private fileManager: GoogleAIFileManager;

  constructor() {
    const apiKey = process.env.GOOGLE_AI_API_KEY;
    if (!apiKey) throw new Error('GOOGLE_AI_API_KEY não configurado no .env');
    this.genAI = new GoogleGenerativeAI(apiKey);
    this.fileManager = new GoogleAIFileManager(apiKey);
  }

  async analisar(pdfPath: string): Promise<AnaliseFloorPlan> {
    logger.info(`Analisando planta: ${pdfPath}`);

    // Envia o PDF para o Google AI File API
    logger.info('Fazendo upload do PDF para o Google AI...');
    const uploadResult = await this.fileManager.uploadFile(pdfPath, {
      mimeType: 'application/pdf',
      displayName: 'Planta Baixa',
    });

    logger.info(`Upload concluído: ${uploadResult.file.uri}`);

    // Aguarda o processamento do arquivo
    let file = uploadResult.file;
    while (file.state === 'PROCESSING') {
      await new Promise((r) => setTimeout(r, 2000));
      file = await this.fileManager.getFile(file.name);
    }

    if (file.state === 'FAILED') {
      throw new Error('Falha ao processar o PDF no Google AI');
    }

    // Analisa com Gemini 1.5 Flash (gratuito)
    const model = this.genAI.getGenerativeModel({ model: 'gemini-1.5-flash' });

    const result = await model.generateContent([
      {
        fileData: {
          mimeType: uploadResult.file.mimeType,
          fileUri: uploadResult.file.uri,
        },
      },
      { text: PROMPT_ANALISE },
    ]);

    const rawText = result.response.text().trim();

    // Remove o arquivo após análise
    try {
      await this.fileManager.deleteFile(uploadResult.file.name);
    } catch {
      // Limpeza opcional, não interrompe o fluxo
    }

    try {
      const parsed = JSON.parse(rawText) as AnaliseFloorPlan;
      logger.info(`Análise concluída: ${parsed.aberturas.length} grupos, confiança: ${parsed.confianca}`);
      return parsed;
    } catch {
      const match = rawText.match(/\{[\s\S]*\}/);
      if (match) {
        return JSON.parse(match[0]) as AnaliseFloorPlan;
      }
      throw new Error(`Resposta inválida do Gemini: ${rawText.substring(0, 300)}`);
    }
  }
}
