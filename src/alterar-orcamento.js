'use strict';

const { chromium } = require('playwright');
const readline = require('readline');
const path = require('path');
require('dotenv').config();

const URL_BASE  = 'https://sistema.wvetro.com.br';
const URL_HOME  = `${URL_BASE}/concept/app.wvetro.home`;
const URL_LISTA = `${URL_BASE}/concept/app.core.orcorcamento`;

// ── Utilitários ───────────────────────────────────────────────────────────────

const rl  = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (p) => new Promise(r => rl.question(p, r));
const log = (m) => console.log(`[${new Date().toLocaleTimeString('pt-BR')}] ${m}`);

async function aguardar(page, timeout = 12000) {
  try { await page.waitForLoadState('networkidle', { timeout }); } catch {}
}

// ── Login ─────────────────────────────────────────────────────────────────────

async function handleLogin(page) {
  const pwd = page.locator('input[type="password"]');
  if (!await pwd.isVisible({ timeout: 4000 }).catch(() => false)) {
    log('Sessão ativa, continuando…'); return;
  }
  log('Tela de login detectada.');
  const senha = process.env.WVETRO_SENHA;
  if (senha) {
    await pwd.fill(senha);
    await page.keyboard.press('Enter');
    await aguardar(page);
    log('Login realizado.');
  } else {
    console.log('\n⚠️  Faça login no Chrome que abriu.');
    await ask('Pressione ENTER depois de entrar no sistema… ');
  }
}

// ── Abrir orçamento pelo número ───────────────────────────────────────────────

async function abrirOrcamento(page, numero) {
  log('Abrindo lista de orçamentos…');
  await page.goto(URL_LISTA, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await aguardar(page);
  log(`Filtrando por orçamento ${numero}…`);

  // Encontra o select "Filter por" e seleciona "Nro Orçamento"
  const selects = page.locator('select');
  const qtd = await selects.count();
  for (let i = 0; i < qtd; i++) {
    const sel = selects.nth(i);
    const opts = await sel.locator('option').allTextContents().catch(() => []);
    const opt  = opts.find(o => /nro.orçamento|nr.orçamento/i.test(o));
    if (opt) { await sel.selectOption({ label: opt }); break; }
  }

  // Preenche o valor do filtro
  await page.waitForTimeout(400);
  const valorInput = page.locator('input[type="text"]').last();
  if (await valorInput.isVisible({ timeout: 2000 }).catch(() => false)) {
    await valorInput.fill(numero);
  }

  // Procura
  await page.getByRole('button', { name: /procurar/i }).click({ timeout: 8000 });
  await aguardar(page);

  // Clica na linha do resultado
  const linhaResult = page.locator('tr').filter({ hasText: numero }).first();
  if (!await linhaResult.isVisible({ timeout: 8000 }).catch(() => false)) {
    throw new Error(`Orçamento ${numero} não encontrado na lista.`);
  }
  await linhaResult.click();
  await aguardar(page);
  log(`Orçamento ${numero} aberto.`);
}

// ── Botão de ações (ícone de lista, 3ª coluna de cada linha) ─────────────────

async function abrirMenuDoItem(page, itemIdx) {
  await page.waitForSelector('text=/detalhe do orçamento/i', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(300);

  const linhas = page.locator('tbody tr');
  const total  = await linhas.count();
  if (total <= itemIdx) {
    throw new Error(`Item ${itemIdx + 1} não encontrado (tabela tem ${total} item(ns)).`);
  }

  const linha = linhas.nth(itemIdx);
  await linha.scrollIntoViewIfNeeded();

  // O botão de ações fica na 3ª célula da linha
  const btn = linha.locator('td:nth-child(3) button, td:nth-child(3) [role="button"]').first();
  if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
    await btn.click();
  } else {
    // Fallback: primeiro botão visível na linha
    await linha.locator('button').first().click({ timeout: 3000 });
  }

  await page.waitForTimeout(600);

  const menu = page.locator('[role="menu"], ul.dropdown-menu, .mat-menu-panel').first();
  if (!await menu.isVisible({ timeout: 2000 }).catch(() => false)) {
    throw new Error(`Menu do item ${itemIdx + 1} não abriu.`);
  }
}

// ── EDITAR ITEM DO ORÇ. (modal "Altera Medida da Esquadria") ─────────────────

async function editarItem(page, itemIdx, campos) {
  log(`Editando item ${itemIdx + 1}…`);
  await abrirMenuDoItem(page, itemIdx);

  await page.getByText(/editar item do orç/i).first().click({ timeout: 5000 });
  await page.waitForSelector('text=/altera medida da esquadria/i', { timeout: 10000 });
  await page.waitForTimeout(400);
  log('Modal aberto.');

  // VIDRO COR
  if (campos.vidro) {
    log(`  → VIDRO COR: ${campos.vidro}`);
    const sel = await selectPorLabel(page, 'VIDRO COR', 'VIDRO');
    if (sel) {
      await sel.selectOption({ label: new RegExp(campos.vidro, 'i') });
    } else {
      log('  ⚠️  Campo VIDRO COR não encontrado. Preencha manualmente.');
      await ask('  Pressione ENTER após preencher… ');
    }
  }

  // ALUMÍNIO/PERFIL  (janelas alumínio) ou  FOLHA TÊMPERA (portas madeira)
  if (campos.cor) {
    log(`  → COR/PERFIL: ${campos.cor}`);
    const sel = await selectPorLabel(page,
      'ALUMÍNIO/PERFIL', 'ALUMINIO/PERFIL', 'COR ALUMÍNIO | PERFIL',
      'FOLHA TÊMPERA', 'FOLHA TEMPERA');
    if (sel) {
      await sel.selectOption({ label: new RegExp(campos.cor, 'i') });
    } else {
      log('  ⚠️  Campo de cor/perfil não encontrado. Preencha manualmente.');
      await ask('  Pressione ENTER após preencher… ');
    }
  }

  // FERRAGENS/ACESSÓRIOS
  if (campos.ferragens) {
    log(`  → FERRAGENS: ${campos.ferragens}`);
    const sel = await selectPorLabel(page, 'FERRAGENS/ACESSÓRIOS', 'FERRAGENS');
    if (sel) await sel.selectOption({ label: new RegExp(campos.ferragens, 'i') });
  }

  await clicarSalvar(page);
  log(`✓ Item ${itemIdx + 1} editado e salvo.`);
}

// ── SUBSTITUIR PROJETO (fluxo em nova página) ─────────────────────────────────
//
// Fluxo completo:
//   menu → "Substituir Projeto"
//   → página /selecioneprojeto   (escolhe LINHA + MODELO + clica Pesquisar)
//   → página /confirmadosprojeto (preenche VIDRO + clica "Incluir item no orçamento")
//   → modal "Informe as variáveis" (configura ACIONAMENTO DA ESTEIRA se necessário + CONFIRMAR)
//   → botão "Calcular o Orçamento" → fecha avisos → volta para DADOS DO ORÇAMENTO

async function substituirProjeto(page, itemIdx, dados) {
  const urlOrcamento = page.url(); // guarda para poder voltar
  log(`Substituindo projeto do item ${itemIdx + 1}…`);

  await abrirMenuDoItem(page, itemIdx);

  // "Substituir Projeto" fica no final do menu — Playwright rola e clica
  await page.getByText(/substituir projeto/i).first().click({ timeout: 6000 });

  // ── Página: ESCOLHA O DESENHO | PROJETO ──────────────────────────────────
  await page.waitForURL(/selecioneprojeto/i, { timeout: 15000 });
  await aguardar(page);
  log('Página de seleção de projeto aberta.');

  if (dados.linha) {
    log(`  → LINHA: ${dados.linha}`);
    const sel = await selectPorLabel(page, 'LINHA');
    if (sel) {
      await sel.selectOption({ label: new RegExp(dados.linha, 'i') });
      await page.waitForTimeout(600); // MODELO precisa atualizar após trocar LINHA
    } else {
      log('  ⚠️  Campo LINHA não encontrado. Selecione manualmente.');
      await ask('  Pressione ENTER após selecionar a linha… ');
    }
  }

  if (dados.modelo) {
    log(`  → MODELO: ${dados.modelo}`);
    const sel = await selectPorLabel(page, 'MODELO');
    if (sel) {
      await sel.selectOption({ label: new RegExp(dados.modelo, 'i') });
    } else {
      log('  ⚠️  Campo MODELO não encontrado. Selecione manualmente.');
      await ask('  Pressione ENTER após selecionar o modelo… ');
    }
  }

  await page.getByRole('button', { name: /pesquisar/i }).click({ timeout: 5000 });
  await aguardar(page);

  // Se aparecer lista de resultados, clica no primeiro
  if (!await page.locator('text=DADOS DO PROJETO PARA O ORÇAMENTO').isVisible({ timeout: 3000 }).catch(() => false)) {
    const primeiro = page.locator('tbody tr').first();
    if (await primeiro.isVisible({ timeout: 5000 }).catch(() => false)) {
      await primeiro.click();
      await aguardar(page);
    }
  }

  // ── Página: DADOS DO PROJETO PARA O ORÇAMENTO ────────────────────────────
  await page.waitForSelector('text=DADOS DO PROJETO PARA O ORÇAMENTO', { timeout: 15000 });
  log('Página de detalhes do projeto aberta.');

  // VIDRO (obrigatório — começa como "Selecione uma Cor")
  if (dados.vidro) {
    log(`  → VIDRO: ${dados.vidro}`);
    const sel = await selectPorLabel(page, 'VIDRO');
    if (sel) {
      await sel.selectOption({ label: new RegExp(dados.vidro, 'i') });
    } else {
      log('  ⚠️  Campo VIDRO não encontrado. Selecione manualmente!');
      await ask('  Pressione ENTER após selecionar o vidro… ');
    }
  } else {
    log('  ⚠️  VIDRO não informado — selecione manualmente!');
    await ask('  Selecione o VIDRO no navegador e pressione ENTER… ');
  }

  // COR ALUMÍNIO | PERFIL (opcional)
  if (dados.cor) {
    log(`  → COR ALUMÍNIO | PERFIL: ${dados.cor}`);
    const sel = await selectPorLabel(page, 'COR ALUMÍNIO | PERFIL', 'COR ALUMÍNIO', 'ALUMÍNIO/PERFIL');
    if (sel) await sel.selectOption({ label: new RegExp(dados.cor, 'i') });
  }

  // Incluir item no orçamento
  await page.getByRole('button', { name: /incluir item no orçamento/i }).click({ timeout: 8000 });

  // ── Modal: Informe as variáveis ───────────────────────────────────────────
  const temVariaveis = await page
    .waitForSelector('text=Informe as variáveis', { timeout: 8000 })
    .then(() => true).catch(() => false);

  if (temVariaveis) {
    log('Modal de variáveis aberto.');

    // AE — ACIONAMENTO DA ESTEIRA (persiana: RECOLHEDOR FITA ou MOTOR)
    if (dados.persiana) {
      log(`  → ACIONAMENTO DA ESTEIRA: ${dados.persiana}`);
      const aeRow = page.locator('tr').filter({ hasText: /ACIONAMENTO DA ESTEIRA/i }).first();
      if (await aeRow.isVisible({ timeout: 2000 }).catch(() => false)) {
        const aeSel = aeRow.locator('select').first();
        if (await aeSel.isVisible({ timeout: 1000 }).catch(() => false)) {
          await aeSel.selectOption({ label: new RegExp(dados.persiana, 'i') });
        }
      } else {
        log('  ⚠️  Variável AE não encontrada no modal. Configure manualmente.');
        await ask('  Pressione ENTER após configurar… ');
      }
    }

    await page.getByRole('button', { name: /confirmar/i }).click({ timeout: 5000 });
    await page.waitForTimeout(1500);
  }

  // "Calcular o Orçamento" aparece após confirmar as variáveis
  const calcBtn = page.getByRole('button', { name: /calcular o orçamento/i });
  if (await calcBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    log('Calculando orçamento…');
    await calcBtn.click();
    await aguardar(page);
  }

  // Fecha qualquer aviso (ex: "itens sem valor de venda")
  for (const nome of [/fechar/i, /^ok$/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await btn.click();
      await aguardar(page);
      break;
    }
  }

  // Volta para o orçamento se necessário
  if (!await page.locator('text=DADOS DO ORÇAMENTO').isVisible({ timeout: 3000 }).catch(() => false)) {
    log('Voltando para o orçamento…');
    await page.goto(urlOrcamento, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await aguardar(page);
  }

  log(`✓ Projeto substituído com sucesso.`);
}

// ── Encontra <select> pelo texto do label ─────────────────────────────────────
// Tenta: getByLabel → linha da tabela (<tr>) → célula adjacente (<td> + <td>)

async function selectPorLabel(page, ...labels) {
  for (const label of labels) {
    const re = new RegExp(label.replace(/[|/]/g, '.'), 'i');

    // 1. getByLabel (label com atributo for="id")
    const byLabel = page.getByLabel(re);
    if (await byLabel.isVisible({ timeout: 500 }).catch(() => false)) return byLabel;

    // 2. Linha da tabela contendo o texto → primeiro select da linha
    const row = page.locator('tr').filter({ hasText: re }).first();
    if (await row.isVisible({ timeout: 500 }).catch(() => false)) {
      const sel = row.locator('select').first();
      if (await sel.isVisible({ timeout: 500 }).catch(() => false)) return sel;
    }

    // 3. <td> com o texto → próximo <td> com select
    const tdSel = page.locator(`td:has-text("${label}") + td select`).first();
    if (await tdSel.isVisible({ timeout: 500 }).catch(() => false)) return tdSel;
  }
  return null;
}

// ── Salvar / Confirmar ────────────────────────────────────────────────────────

async function clicarSalvar(page) {
  for (const nome of [/^salvar$/i, /^confirmar$/i, /^aplicar$/i, /^gravar$/i, /^ok$/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 1500 }).catch(() => false)) {
      await btn.click();
      await aguardar(page);
      return;
    }
  }
  throw new Error('Botão Salvar/Confirmar não encontrado no modal.');
}

// ── Calcular orçamento (botão "Calcular" na página do orçamento) ──────────────

async function calcularOrcamento(page) {
  log('Calculando orçamento…');
  const btn = page.getByRole('button', { name: /^calcular$/i });
  if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) {
    await btn.click();
    await aguardar(page);
    for (const nome of [/fechar/i, /^ok$/i]) {
      const b = page.getByRole('button', { name: nome });
      if (await b.isVisible({ timeout: 3000 }).catch(() => false)) { await b.click(); break; }
    }
    log('✓ Orçamento calculado.');
  } else {
    log('Botão "Calcular" não encontrado — calcule manualmente se necessário.');
  }
}

// ── Coleta de dados via terminal ──────────────────────────────────────────────

async function coletarDados() {
  console.log('\n╔══════════════════════════════════════════════════════════════╗');
  console.log('║       Automação W-vetro — Alteração de Orçamentos           ║');
  console.log('╚══════════════════════════════════════════════════════════════╝\n');

  const numero = (await ask('Número do orçamento: ')).trim();
  const alteracoes = [];
  let continuar = true;

  while (continuar) {
    console.log('\n┌─ Tipo de alteração ──────────────────────────────────────────────┐');
    console.log('│  1  Substituir projeto  (nova linha/modelo — abre outra página)   │');
    console.log('│  2  Editar item         (vidro, cor, ferragens — no mesmo modal)  │');
    console.log('└──────────────────────────────────────────────────────────────────┘');
    const tipo = (await ask('Tipo (1 ou 2): ')).trim();

    const itemRaw = (await ask('Número do item no orçamento (1, 2, 3…): ')).trim();
    const itemIdx = parseInt(itemRaw, 10) - 1;
    if (isNaN(itemIdx) || itemIdx < 0) { console.log('Número inválido.\n'); continue; }

    if (tipo === '1') {
      // ── SUBSTITUIR PROJETO ──────────────────────────────────────────────
      console.log('\n  ── Filtros: página "Escolha o Desenho | Projeto" ──');
      const linha  = (await ask('  LINHA  (ex: PERFISUD | VERSATIC 25 - QUADRADA): ')).trim();
      const modelo = (await ask('  MODELO (ex: JANELA DE CORRER 02 FOLHAS): ')).trim();

      console.log('\n  ── Página de detalhes do projeto ──');
      console.log('  Exemplos: INCOLOR 06MM - TEMPERADO  |  LAMINADO INCOLOR 3+3 - LAPIDADO');
      const vidro = (await ask('  VIDRO  (obrigatório): ')).trim();
      const cor   = (await ask('  COR ALUMÍNIO | PERFIL  (Enter = manter atual): ')).trim();

      console.log('\n  ── Modal "Informe as variáveis" — persiana ──');
      console.log('  Opções: RECOLHEDOR FITA  |  MOTOR  (deixe em branco se não tiver persiana)');
      const persiana = (await ask('  ACIONAMENTO DA ESTEIRA (Enter = manter padrão): ')).trim();

      alteracoes.push({
        tipo: 'substituir', itemIdx,
        dados: { linha, modelo, vidro, cor: cor || null, persiana: persiana || null }
      });

    } else {
      // ── EDITAR ITEM ──────────────────────────────────────────────────────
      const campos = {};

      console.log('\n  Exemplos vidro    : INCOLOR 06MM - TEMPERADO, LAMINADO INCOLOR 3+3 - LAPIDADO');
      const v = (await ask('  VIDRO COR          (Enter = não alterar): ')).trim();
      if (v) campos.vidro = v;

      console.log('  Exemplos cor/perf : PINTURA PRETO, BRANCO, NATURAL, PINTURA BRANCO BRILHANTE');
      const c = (await ask('  ALUMÍNIO / PERFIL  (Enter = não alterar): ')).trim();
      if (c) campos.cor = c;

      const f = (await ask('  FERRAGENS          (Enter = não alterar): ')).trim();
      if (f) campos.ferragens = f;

      if (!Object.keys(campos).length) { console.log('Nenhum campo informado.\n'); continue; }
      alteracoes.push({ tipo: 'editar', itemIdx, campos });
    }

    const mais = (await ask('\nOutra alteração neste orçamento? (s/n): ')).trim().toLowerCase();
    continuar = mais === 's';
  }

  const calc = (await ask('\nCalcular o orçamento ao finalizar? (s/n): ')).trim().toLowerCase();
  rl.close();
  return { numero, alteracoes, calcular: calc === 's' };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const { numero, alteracoes, calcular } = await coletarDados();
  if (!alteracoes.length) { console.log('\nNenhuma alteração informada. Encerrando.'); return; }

  log(`\nAbrindo Chrome… (${alteracoes.length} alteração(ões) para orçamento ${numero})`);

  const browser = await chromium
    .launch({ headless: false, channel: 'chrome', args: ['--start-maximized'] })
    .catch(() => chromium.launch({ headless: false, args: ['--start-maximized'] }));

  const ctx  = await browser.newContext({ viewport: null });
  const page = await ctx.newPage();

  try {
    await page.goto(URL_HOME, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await handleLogin(page);
    await abrirOrcamento(page, numero);

    for (const alt of alteracoes) {
      if (alt.tipo === 'substituir') {
        await substituirProjeto(page, alt.itemIdx, alt.dados);
      } else {
        await editarItem(page, alt.itemIdx, alt.campos);
      }
    }

    if (calcular) await calcularOrcamento(page);

    console.log('\n✅  Todas as alterações concluídas!');
    console.log('   Navegador aberto para revisão.\n');

  } catch (err) {
    console.error('\n❌  Erro:', err.message);
    const ss = path.join(process.cwd(), 'erro-wvetro.png');
    await page.screenshot({ path: ss, fullPage: true }).catch(() => {});
    console.log(`   Screenshot salvo: ${ss}\n`);
  }
}

main().catch(console.error);
