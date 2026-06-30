import TelegramBotAPI from 'node-telegram-bot-api';
import * as fs from 'fs';
import * as path from 'path';
import { v4 as uuidv4 } from 'uuid';
import axios from 'axios';
import { WVetroBudgetAgent } from '../agents/wvetro-budget';
import { logger } from '../utils/logger';

const UPLOADS_DIR = path.join(process.cwd(), 'uploads');
fs.mkdirSync(UPLOADS_DIR, { recursive: true });

const MSG_BOAS_VINDAS = `🏗️ *Agente de Orçamento W-Vetro*
_Egemap Esquadrias_

Envie a *planta baixa em PDF* e eu faço o orçamento completo automaticamente!

*O que faço:*
🔍 Leio a planta e identifico todas as esquadrias
📐 Calculo quantidades por ambiente
📋 Gero relatório Excel detalhado
🖥️ Preencho o orçamento no W-Vetro

*Especificações aplicadas automaticamente:*
• Alumínio *branco Linha 25* em tudo
• Vidro *temperado 6mm* — janelas comuns
• Vidro *temperado 8mm* — dormitórios e portas
• *Persiana com motor* — dormitórios
• *Maxim-Ar + mini boreal 4mm* — banheiros

📎 *Envie o PDF da planta para começar!*`;

const MSG_PROCESSANDO = `📋 *Planta recebida!*

Iniciando análise... ⏳

_Este processo leva cerca de 1-3 minutos._
_Vou te avisar quando terminar!_`;

export class TelegramBot {
  private bot: TelegramBotAPI;
  private agent: WVetroBudgetAgent;
  private emProcessamento = new Set<number>();

  constructor() {
    const token = process.env.TELEGRAM_BOT_TOKEN;
    if (!token) throw new Error('TELEGRAM_BOT_TOKEN não configurado no .env');

    this.bot = new TelegramBotAPI(token, { polling: true });
    this.agent = new WVetroBudgetAgent();
  }

  start(): void {
    this.bot.on('message', (msg) => this.handleMessage(msg).catch((e) => logger.error('Erro handleMessage:', e)));
    this.bot.on('document', (msg) => this.handleDocument(msg).catch((e) => logger.error('Erro handleDocument:', e)));
    this.bot.on('polling_error', (err) => logger.error('Polling error:', err));

    logger.info('Bot Telegram iniciado (modo polling)');
  }

  private async handleMessage(msg: TelegramBotAPI.Message): Promise<void> {
    if (msg.document) return; // tratado em handleDocument

    const chatId = msg.chat.id;
    const text = (msg.text || '').trim();

    if (['/start', '/ajuda', '/help'].includes(text)) {
      await this.bot.sendMessage(chatId, MSG_BOAS_VINDAS, { parse_mode: 'Markdown' });
      return;
    }

    if (text === '/modelos') {
      await this.listarModelos(chatId);
      return;
    }

    if (text && !text.startsWith('/')) {
      await this.bot.sendMessage(
        chatId,
        '📎 Envie o arquivo da planta em *PDF* para eu analisar.',
        { parse_mode: 'Markdown' }
      );
    }
  }

  private async listarModelos(chatId: number): Promise<void> {
    await this.bot.sendMessage(chatId, '🔍 Consultando modelos disponíveis no OpenRouter...');
    try {
      const apiKey = process.env.OPENROUTER_API_KEY;
      const res = await axios.get('https://openrouter.ai/api/v1/models', {
        headers: { Authorization: `Bearer ${apiKey}` },
        timeout: 15000,
      });
      const modelos: Array<{ id: string; pricing?: { prompt?: string }; architecture?: { modality?: string } }> =
        res.data?.data ?? [];
      const gratuitos = modelos.filter(
        (m) => m.id.endsWith(':free') && (
          m.architecture?.modality?.includes('image') ||
          m.id.includes('vision') ||
          m.id.includes('vl') ||
          m.id.includes('pixtral') ||
          m.id.includes('gemini') ||
          m.id.includes('phi-4')
        )
      );
      if (gratuitos.length === 0) {
        await this.bot.sendMessage(chatId, '⚠️ Nenhum modelo gratuito com visão encontrado.\n\nModelos gratuitos disponíveis:\n' +
          modelos.filter(m => m.id.endsWith(':free')).slice(0, 20).map(m => `• ${m.id}`).join('\n'));
      } else {
        await this.bot.sendMessage(chatId,
          `✅ *Modelos gratuitos com visão (${gratuitos.length}):*\n` +
          gratuitos.map(m => `• \`${m.id}\``).join('\n'),
          { parse_mode: 'Markdown' }
        );
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      await this.bot.sendMessage(chatId, `❌ Erro ao consultar modelos: ${msg}`);
    }
  }

  private async handleDocument(msg: TelegramBotAPI.Message): Promise<void> {
    const chatId = msg.chat.id;
    const doc = msg.document;
    if (!doc) return;

    if (!doc.mime_type?.includes('pdf')) {
      await this.bot.sendMessage(chatId, '❌ Por favor, envie a planta em formato *PDF*.', {
        parse_mode: 'Markdown',
      });
      return;
    }

    if (this.emProcessamento.has(chatId)) {
      await this.bot.sendMessage(
        chatId,
        '⏳ Ainda estou processando sua planta anterior. Aguarde um momento...'
      );
      return;
    }

    this.emProcessamento.add(chatId);
    const sessionId = uuidv4().split('-')[0];
    const pdfPath = path.join(UPLOADS_DIR, `${chatId}_${sessionId}.pdf`);

    try {
      await this.bot.sendMessage(chatId, MSG_PROCESSANDO, { parse_mode: 'Markdown' });

      // Baixa o PDF do Telegram
      await this.bot.sendMessage(chatId, '📥 _Baixando arquivo..._', { parse_mode: 'Markdown' });
      const fileLink = await this.bot.getFileLink(doc.file_id);
      const res = await axios.get(fileLink, { responseType: 'arraybuffer', timeout: 60000 });
      fs.writeFileSync(pdfPath, res.data);
      logger.info(`[${sessionId}] PDF baixado: ${pdfPath} (${Math.round(res.data.byteLength / 1024)} KB)`);

      await this.bot.sendMessage(chatId, '🔍 _Analisando planta com IA... quase lá!_', {
        parse_mode: 'Markdown',
      });

      // Processa a planta
      const resultado = await this.agent.processarPlanta(pdfPath, sessionId);

      // Envia o resumo de texto
      await this.bot.sendMessage(chatId, resultado.telegramMessage, { parse_mode: 'Markdown' });

      // Envia o Excel
      if (resultado.excelPath && fs.existsSync(resultado.excelPath)) {
        await this.bot.sendDocument(chatId, resultado.excelPath, {
          caption: '📊 Relatório de quantitativos completo',
        });
      }
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logger.error(`[${sessionId}] Erro fatal:`, error);
      await this.bot.sendMessage(
        chatId,
        `❌ *Ocorreu um erro ao processar a planta:*\n\`${msg.substring(0, 200)}\`\n\nTente novamente ou entre em contato com o suporte.`,
        { parse_mode: 'Markdown' }
      );
    } finally {
      this.emProcessamento.delete(chatId);
      if (fs.existsSync(pdfPath)) fs.unlinkSync(pdfPath);
    }
  }
}
