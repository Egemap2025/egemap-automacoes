import 'dotenv/config';
import { TelegramBot } from './bot/telegram';
import { logger } from './utils/logger';

async function main(): Promise<void> {
  logger.info('=== Egemap Automações iniciando ===');

  const bot = new TelegramBot();
  bot.start();

  logger.info('Agente W-Vetro ativo — aguardando plantas no Telegram...');

  // Graceful shutdown
  process.on('SIGINT', () => {
    logger.info('Encerrando...');
    process.exit(0);
  });

  process.on('SIGTERM', () => {
    logger.info('Encerrando...');
    process.exit(0);
  });
}

main().catch((err) => {
  logger.error('Erro fatal na inicialização:', err);
  process.exit(1);
});
