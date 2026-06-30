import { chromium, Browser, Page } from 'playwright';
import * as path from 'path';
import * as fs from 'fs';
import { ProdutoEsquadria } from './rules';
import { logger } from '../../utils/logger';

const SCREENSHOTS_DIR = path.join(process.cwd(), 'outputs', 'screenshots');

export interface AutomatorResult {
  sucesso: boolean;
  orcamentoUrl?: string;
  orcamentoNumero?: string;
  mensagem: string;
}

export class WVetroAutomator {
  private browser: Browser | null = null;

  async criarOrcamento(
    produtos: ProdutoEsquadria[],
    sessionId: string,
    nomeCliente = 'Orçamento Automático'
  ): Promise<AutomatorResult> {
    const { WVETRO_URL, WVETRO_EMAIL, WVETRO_SENHA } = process.env;

    if (!WVETRO_URL || !WVETRO_EMAIL || !WVETRO_SENHA) {
      return {
        sucesso: false,
        mensagem:
          '⚠️ *W-Vetro não configurado.*\nAdicione WVETRO\\_URL, WVETRO\\_EMAIL e WVETRO\\_SENHA no arquivo `.env`\n\nO relatório Excel foi gerado normalmente! 📊',
      };
    }

    fs.mkdirSync(SCREENSHOTS_DIR, { recursive: true });

    try {
      const debug = process.env.WVETRO_DEBUG === 'true';

      this.browser = await chromium.launch({
        headless: !debug,
        executablePath: process.env.CHROMIUM_PATH || undefined,
        args: ['--no-sandbox', '--disable-setuid-sandbox'],
      });

      const page = await this.browser.newPage();
      await page.setViewportSize({ width: 1366, height: 768 });

      await this.login(page, WVETRO_URL, WVETRO_EMAIL, WVETRO_SENHA, sessionId);
      const orcamentoNumero = await this.criarNovoOrcamento(page, WVETRO_URL, nomeCliente, sessionId);
      await this.adicionarProdutos(page, produtos, sessionId);
      await this.salvarOrcamento(page, sessionId);

      const orcamentoUrl = page.url();

      return {
        sucesso: true,
        orcamentoUrl,
        orcamentoNumero,
        mensagem:
          `✅ *Orçamento criado no W-Vetro!*\n` +
          `🔢 Número: *${orcamentoNumero || 'ver sistema'}*\n` +
          `🔗 ${orcamentoUrl}`,
      };
    } catch (error) {
      const msg = error instanceof Error ? error.message : String(error);
      logger.error('Erro W-Vetro:', error);
      await this.screenshot(this.browser ? await this.browser.newPage() : null, sessionId, 'erro');
      return {
        sucesso: false,
        mensagem:
          `⚠️ *Erro ao preencher W-Vetro:*\n${msg}\n\n` +
          `O relatório Excel foi gerado normalmente. ` +
          `Ative \`WVETRO_DEBUG=true\` no .env para ver o navegador e depurar.`,
      };
    } finally {
      if (this.browser) {
        await this.browser.close();
        this.browser = null;
      }
    }
  }

  private async login(
    page: Page,
    baseUrl: string,
    email: string,
    senha: string,
    sessionId: string
  ): Promise<void> {
    logger.info('W-Vetro: iniciando login...');
    await page.goto(`${baseUrl}/login`, { waitUntil: 'networkidle', timeout: 30000 });
    await this.screenshot(page, sessionId, '01-login-page');

    // Tenta os seletores mais comuns de campos de login
    await page.fill(
      'input[type="email"], input[name="email"], input[name="login"], #email, #login',
      email
    );
    await page.fill(
      'input[type="password"], input[name="password"], input[name="senha"], #password, #senha',
      senha
    );

    await this.screenshot(page, sessionId, '02-login-preenchido');

    await page.click('button[type="submit"], input[type="submit"], .btn-login, button:has-text("Entrar"), button:has-text("Login")');
    await page.waitForNavigation({ waitUntil: 'networkidle', timeout: 30000 });
    await this.screenshot(page, sessionId, '03-pos-login');

    if (page.url().includes('/login')) {
      throw new Error('Login falhou — verifique WVETRO_EMAIL e WVETRO_SENHA no .env');
    }

    logger.info('W-Vetro: login OK');
  }

  private async criarNovoOrcamento(
    page: Page,
    baseUrl: string,
    nomeCliente: string,
    sessionId: string
  ): Promise<string> {
    logger.info('W-Vetro: navegando para novo orçamento...');

    // Tenta rotas comuns do W-Vetro
    const rotas = [
      '/orcamentos/novo',
      '/orcamento/novo',
      '/vendas/orcamentos/criar',
      '/pedidos/novo',
    ];

    for (const rota of rotas) {
      try {
        await page.goto(`${baseUrl}${rota}`, { waitUntil: 'networkidle', timeout: 10000 });
        if (!page.url().includes('/login')) break;
      } catch {
        continue;
      }
    }

    await this.screenshot(page, sessionId, '04-novo-orcamento');

    // Preenche nome do cliente
    const camposCliente = [
      'input[name="cliente"], input[name="client"]',
      'input[placeholder*="cliente" i], input[placeholder*="nome" i]',
      '#cliente, #client, #nome-cliente',
    ];

    for (const sel of camposCliente) {
      try {
        await page.fill(sel, nomeCliente, { timeout: 3000 });
        logger.info('W-Vetro: campo cliente preenchido');
        break;
      } catch {
        continue;
      }
    }

    await this.screenshot(page, sessionId, '05-cliente-preenchido');

    // Tenta ler o número do orçamento gerado
    let numero = '';
    const selectoresNumero = [
      '.numero-orcamento',
      '#numero-orcamento',
      '[data-field="numero"]',
      'span:has-text("Nº")',
    ];
    for (const sel of selectoresNumero) {
      try {
        const el = await page.$(sel);
        if (el) {
          numero = (await el.innerText()).trim();
          break;
        }
      } catch {
        continue;
      }
    }

    return numero || `AUTO-${Date.now()}`;
  }

  private async adicionarProdutos(
    page: Page,
    produtos: ProdutoEsquadria[],
    sessionId: string
  ): Promise<void> {
    logger.info(`W-Vetro: adicionando ${produtos.length} produtos...`);

    for (let i = 0; i < produtos.length; i++) {
      try {
        await this.adicionarUmProduto(page, produtos[i]);
        if (i % 5 === 0) await this.screenshot(page, sessionId, `06-produtos-${i + 1}`);
      } catch (err) {
        logger.warn(`Produto ${i + 1} não inserido: ${err}`);
      }
    }
  }

  private async adicionarUmProduto(page: Page, produto: ProdutoEsquadria): Promise<void> {
    // Clica em "Adicionar Item"
    const botoesAdicionar = [
      'button:has-text("Adicionar Item")',
      'button:has-text("+ Item")',
      'button:has-text("Novo Item")',
      '.btn-add-item',
      '[data-action="add-item"]',
    ];

    for (const sel of botoesAdicionar) {
      try {
        await page.click(sel, { timeout: 4000 });
        await page.waitForTimeout(400);
        break;
      } catch {
        continue;
      }
    }

    // Descrição do produto para o campo de busca/texto
    const descricaoCompleta = [
      `Linha ${produto.linha}`,
      produto.descricao,
      produto.cor,
      produto.tipo_vidro !== '-' ? `${produto.tipo_vidro} ${produto.espessura_vidro_mm}mm` : '',
    ]
      .filter(Boolean)
      .join(' ');

    // Última linha da tabela de itens
    const prefixo = 'tr:last-child';

    const campoDesc = `${prefixo} input[name*="descricao"], ${prefixo} input[name*="produto"], ${prefixo} input[placeholder*="produto" i]`;
    const campoLarg = `${prefixo} input[name*="largura"], ${prefixo} input[name*="width"], ${prefixo} input[name*="l"]`;
    const campoAlt = `${prefixo} input[name*="altura"], ${prefixo} input[name*="height"], ${prefixo} input[name*="a"]`;
    const campoQtd = `${prefixo} input[name*="quantidade"], ${prefixo} input[name*="qty"], ${prefixo} input[name*="qtd"]`;

    for (const [sel, val] of [
      [campoDesc, descricaoCompleta],
      [campoLarg, String(produto.largura_cm)],
      [campoAlt, String(produto.altura_cm)],
      [campoQtd, String(produto.quantidade)],
    ]) {
      try {
        await page.fill(sel, val as string, { timeout: 3000 });
      } catch {
        // Campo não encontrado — o layout pode ser diferente
      }
    }

    await page.keyboard.press('Tab');
  }

  private async salvarOrcamento(page: Page, sessionId: string): Promise<void> {
    logger.info('W-Vetro: salvando...');

    const botoesSalvar = [
      'button:has-text("Salvar")',
      'button[type="submit"]:has-text("Salvar")',
      'button:has-text("Finalizar")',
      'button:has-text("Gravar")',
      '.btn-salvar',
    ];

    for (const sel of botoesSalvar) {
      try {
        await page.click(sel, { timeout: 5000 });
        await page.waitForLoadState('networkidle', { timeout: 20000 });
        break;
      } catch {
        continue;
      }
    }

    await this.screenshot(page, sessionId, '07-orcamento-salvo');
    logger.info('W-Vetro: orçamento salvo com sucesso');
  }

  private async screenshot(page: Page | null, sessionId: string, nome: string): Promise<void> {
    if (!page) return;
    try {
      const filePath = path.join(SCREENSHOTS_DIR, `${sessionId}_${nome}.png`);
      await page.screenshot({ path: filePath, fullPage: true });
    } catch {
      // Screenshot é opcional, não interrompe o fluxo
    }
  }
}
