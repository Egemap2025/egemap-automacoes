import { FloorPlanAnalyzer } from './analyzer';
import { aplicarRegras } from './rules';
import { gerarRelatorio } from './report';
import { WVetroAutomator } from './automator';
import { logger } from '../../utils/logger';

export interface BudgetResult {
  telegramMessage: string;
  excelPath?: string;
}

export class WVetroBudgetAgent {
  private analyzer = new FloorPlanAnalyzer();
  private automator = new WVetroAutomator();

  async processarPlanta(pdfPath: string, sessionId: string, nomeCliente?: string): Promise<BudgetResult> {
    logger.info(`[${sessionId}] === INICIANDO PROCESSAMENTO ===`);

    // 1. IA lê a planta e identifica aberturas
    logger.info(`[${sessionId}] Etapa 1/4: Analisando planta com IA...`);
    const analise = await this.analyzer.analisar(pdfPath);

    if (analise.aberturas.length === 0) {
      return {
        telegramMessage:
          '⚠️ *Não encontrei aberturas na planta.*\n\n' +
          'Possíveis motivos:\n' +
          '• A planta está em baixa qualidade\n' +
          '• O arquivo tem só plantas de localização (sem detalhes)\n\n' +
          'Tente enviar uma planta baixa com mais detalhes.',
      };
    }

    // 2. Aplica as regras de produtos Egemap
    logger.info(`[${sessionId}] Etapa 2/4: Aplicando regras de produtos...`);
    const produtos = aplicarRegras(analise.aberturas);

    // 3. Gera relatório Excel
    logger.info(`[${sessionId}] Etapa 3/4: Gerando relatório Excel...`);
    const report = await gerarRelatorio(produtos, analise, sessionId);

    // 4. Automatiza o W-Vetro
    logger.info(`[${sessionId}] Etapa 4/4: Preenchendo W-Vetro...`);
    const wvetro = await this.automator.criarOrcamento(produtos, sessionId, nomeCliente);

    const mensagemFinal = `${report.resumoTexto}\n\n${wvetro.mensagem}`;

    logger.info(`[${sessionId}] === PROCESSAMENTO CONCLUÍDO ===`);

    return {
      telegramMessage: mensagemFinal,
      excelPath: report.excelPath,
    };
  }
}
