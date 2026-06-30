'use strict';

const { chromium } = require('playwright');
const readline = require('readline');
const path = require('path');
require('dotenv').config();

const URL_BASE     = 'https://sistema.wvetro.com.br';
const URL_HOME     = `${URL_BASE}/concept/app.wvetro.home`;
const URL_LISTA    = `${URL_BASE}/concept/app.core.orcorcamento`;

// ── Utilitários ───────────────────────────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (prompt) => new Promise(res => rl.question(prompt, res));
const log = (msg)    => console.log(`[${new Date().toLocaleTimeString('pt-BR')}] ${msg}`);

async function aguardar(page, timeout = 12000) {
  try { await page.waitForLoadState('networkidle', { timeout }); } catch { /* ok */ }
}

// ── Login ─────────────────────────────────────────────────────────────────────

async function handleLogin(page) {
  const senhaInput = page.locator('input[type="password"]');
  if (!await senhaInput.isVisible({ timeout: 4000 }).catch(() => false)) {
    log('Sessão ativa, continuando…');
    return;
  }

  log('Tela de login detectada.');
  const senha = process.env.WVETRO_SENHA;
  if (senha) {
    await senhaInput.fill(senha);
    await page.keyboard.press('Enter');
    await aguardar(page);
    log('Login realizado automaticamente.');
  } else {
    console.log('\n⚠️  Faça login no Chrome que abriu.');
    await ask('Pressione ENTER depois de entrar no sistema… ');
    log('Continuando após login manual.');
  }
}

// ── Abrir orçamento pelo número ───────────────────────────────────────────────

async function abrirOrcamento(page, numero) {
  log('Abrindo lista de orçamentos…');
  await page.goto(URL_LISTA, { waitUntil: 'domcontentloaded', timeout: 30000 });
  await aguardar(page);

  log(`Filtrando por orçamento ${numero}…`);

  // ── 1. Seleciona "Nro Orçamento" no combo "Filter por" ────────────────────
  // O select fica na área de filtros. Tentamos pelo texto das options.
  const selects = page.locator('select');
  const qtdSelects = await selects.count();
  let filtroSelecionado = false;

  for (let i = 0; i < qtdSelects; i++) {
    const sel = selects.nth(i);
    const options = await sel.locator('option').allTextContents().catch(() => []);
    const temOpcao = options.some(t => /nro.orçamento|nr.orçamento|número/i.test(t));
    if (temOpcao) {
      await sel.selectOption({ label: options.find(t => /nro.orçamento|nr.orçamento/i.test(t)) || options[0] });
      filtroSelecionado = true;
      log('Filtro "Nro Orçamento" selecionado.');
      break;
    }
  }

  if (!filtroSelecionado) {
    log('⚠️  Combo "Filter por" não encontrado — tentando busca direta.');
  }

  // ── 2. Preenche o valor do filtro (campo de texto ao lado) ────────────────
  // Após selecionar o filtro, o campo de input aparece para o valor.
  // Aguarda um momento para o campo aparecer.
  await page.waitForTimeout(400);

  const campoValor = page.locator('input[type="text"]').last();
  if (await campoValor.isVisible({ timeout: 3000 }).catch(() => false)) {
    await campoValor.click();
    await campoValor.fill(numero);
  } else {
    log('⚠️  Campo de filtro não encontrado, tentando campo de busca geral…');
    const buscaGeral = page.locator('input[placeholder*="buscar" i], input[placeholder*="pesquisar" i]').first();
    if (await buscaGeral.isVisible({ timeout: 2000 }).catch(() => false)) {
      await buscaGeral.fill(numero);
    }
  }

  // ── 3. Clica em "Procurar" ────────────────────────────────────────────────
  await page.getByRole('button', { name: /procurar/i }).click({ timeout: 8000 });
  await aguardar(page);

  // ── 4. Clica na linha do resultado ────────────────────────────────────────
  const linhaResultado = page.locator('tr').filter({ hasText: numero }).first();
  if (!await linhaResultado.isVisible({ timeout: 8000 }).catch(() => false)) {
    throw new Error(`Orçamento ${numero} não encontrado na lista. Verifique o número.`);
  }
  await linhaResultado.click();
  await aguardar(page);

  log(`Orçamento ${numero} aberto.`);
}

// ── Clicar no botão de ações da linha do item (ícone de lista, 3ª coluna) ────

async function abrirMenuDoItem(page, itemIdx) {
  // Aguarda a tabela de detalhe carregar
  await page.waitForSelector('text=/detalhe do orçamento/i', { timeout: 10000 }).catch(() => {});
  await page.waitForTimeout(300);

  // Cada linha da tabela tem na 3ª célula (td:nth-child(3)) o botão de ações
  // (ícone de documento/lista). Localizamos a linha pelo índice e clicamos nesse botão.
  const linhas = page.locator('tbody tr');
  const qtdLinhas = await linhas.count().catch(() => 0);

  if (qtdLinhas > itemIdx) {
    const linha = linhas.nth(itemIdx);
    await linha.scrollIntoViewIfNeeded();

    // Tenta o botão na 3ª coluna primeiro (padrão W-vetro)
    const btnColuna3 = linha.locator('td:nth-child(3) button, td:nth-child(3) [role="button"]').first();
    const temBtn3 = await btnColuna3.isVisible({ timeout: 1500 }).catch(() => false);

    if (temBtn3) {
      await btnColuna3.click();
    } else {
      // Fallback: qualquer botão na linha
      const btnLinha = linha.locator('button, [role="button"]').first();
      const temBtnLinha = await btnLinha.isVisible({ timeout: 1500 }).catch(() => false);
      if (temBtnLinha) {
        await btnLinha.click();
      } else {
        // Último recurso: clique direito na linha
        await linha.click({ button: 'right' });
      }
    }

    await page.waitForTimeout(600);

    // Verifica se o menu abriu
    const menu = page.locator('[role="menu"], .mat-menu-panel, [class*="dropdown"]').first();
    if (await menu.isVisible({ timeout: 2000 }).catch(() => false)) {
      return; // ✓
    }
  }

  throw new Error(
    `Não consegui abrir o menu do item ${itemIdx + 1}.\n` +
    `Verifique se o número do item está correto e se o orçamento está aberto.`
  );
}

// ── Editar item (VIDRO COR + FOLHA TÊMPERA + persiana) ───────────────────────

async function editarItem(page, itemIdx, campos) {
  log(`Editando item ${itemIdx + 1}…`);
  await abrirMenuDoItem(page, itemIdx);

  // Clica em "Editar Item do Orç." (nome exato do menu no W-vetro)
  const opcaoEditar = page
    .getByRole('menuitem', { name: /editar item do orç/i })
    .or(page.getByText(/editar item do orç/i).first());
  await opcaoEditar.click({ timeout: 6000 });

  // Aguarda modal "Altera Medida da Esquadria do Orçamento"
  await page.waitForSelector('text=/altera medida da esquadria/i', { timeout: 10000 });
  await page.waitForTimeout(400);
  log('Modal de edição aberto.');

  // ── VIDRO COR ─────────────────────────────────────────────────────────────
  if (campos.vidro) {
    log(`  → VIDRO COR: ${campos.vidro}`);
    await preencherSelect(page, 'vidro cor', campos.vidro);
  }

  // ── FOLHA TÊMPERA (cor / madeira / pintura) ───────────────────────────────
  if (campos.cor) {
    log(`  → FOLHA TÊMPERA: ${campos.cor}`);
    await preencherSelect(page, 'folha têmpera', campos.cor);
  }

  // ── PERSIANA (acionamento) ────────────────────────────────────────────────
  if (campos.persiana) {
    log(`  → PERSIANA / ACIONAMENTO: ${campos.persiana}`);
    // O campo de persiana pode ter label diferente dependendo da versão do W-vetro.
    // Tentamos pelos labels mais comuns.
    const tentou = await preencherSelect(page, 'persiana', campos.persiana, false)
                || await preencherSelect(page, 'acionamento', campos.persiana, false)
                || await preencherSelect(page, 'comando', campos.persiana, false);
    if (!tentou) {
      log('  ⚠️  Campo de persiana não encontrado automaticamente.');
      await ask('  Selecione a opção de persiana manualmente no navegador e pressione ENTER… ');
    }
  }

  await clicarSalvar(page);
  log(`✓ Item ${itemIdx + 1} editado e salvo.`);
}

// ── Substituir projeto ────────────────────────────────────────────────────────

async function substituirProjeto(page, itemIdx, novoProjeto) {
  log(`Substituindo projeto do item ${itemIdx + 1} → "${novoProjeto}"…`);
  await abrirMenuDoItem(page, itemIdx);

  const opcaoSubst = page
    .getByRole('menuitem', { name: /substituir projeto/i })
    .or(page.getByText(/substituir projeto/i).first());
  await opcaoSubst.click({ timeout: 6000 });
  await aguardar(page);

  // Modal de substituição: busca pelo nome/código do projeto
  const campoBusca = page
    .locator('mat-dialog-container input, [role="dialog"] input, .modal input')
    .first();

  if (await campoBusca.isVisible({ timeout: 5000 }).catch(() => false)) {
    await campoBusca.fill(novoProjeto);
    await page.waitForTimeout(800);

    // Tenta clicar na opção que aparecer
    const opcao = page
      .getByRole('option', { name: new RegExp(novoProjeto, 'i') })
      .or(page.locator('mat-option, li[role="option"]').filter({ hasText: new RegExp(novoProjeto, 'i') }))
      .first();

    if (await opcao.isVisible({ timeout: 4000 }).catch(() => false)) {
      await opcao.click();
    } else {
      log('⚠️  Opção não encontrada automaticamente — selecione manualmente.');
      await ask('  Selecione o projeto no navegador e pressione ENTER… ');
    }
  } else {
    log('⚠️  Campo de busca do modal não encontrado — preencha manualmente.');
    await ask('  Selecione o projeto no navegador e pressione ENTER… ');
  }

  await clicarSalvar(page);
  log(`✓ Projeto substituído.`);
}

// ── Preencher <select> pelo label ─────────────────────────────────────────────

async function preencherSelect(page, labelTexto, valor, obrigatorio = true) {
  // Estratégia 1: getByLabel()
  const byLabel = page.getByLabel(new RegExp(labelTexto, 'i'));
  if (await byLabel.isVisible({ timeout: 1500 }).catch(() => false)) {
    await byLabel.selectOption({ label: new RegExp(valor, 'i') }).catch(async () => {
      // Se selectOption falhar (custom dropdown), tenta clicar + selecionar
      await byLabel.click();
      await page.waitForTimeout(400);
      await page.locator(`text="${valor}"`).first().click().catch(() => {});
    });
    return true;
  }

  // Estratégia 2: label → select adjacente (label:has-text + select)
  const labelEl = page.locator(`label`).filter({ hasText: new RegExp(labelTexto, 'i') }).first();
  if (await labelEl.isVisible({ timeout: 1500 }).catch(() => false)) {
    // Tenta select filho ou irmão
    for (const xsel of [
      `label:has-text("${labelTexto}") select`,
      `label:has-text("${labelTexto}") ~ select`,
      `label:has-text("${labelTexto}") + select`,
    ]) {
      const sel = page.locator(xsel).first();
      if (await sel.isVisible({ timeout: 800 }).catch(() => false)) {
        await sel.selectOption({ label: new RegExp(valor, 'i') });
        return true;
      }
    }

    // Tenta via atributo "for"
    const forAttr = await labelEl.getAttribute('for').catch(() => null);
    if (forAttr) {
      const sel = page.locator(`#${forAttr}`);
      if (await sel.isVisible({ timeout: 800 }).catch(() => false)) {
        await sel.selectOption({ label: new RegExp(valor, 'i') });
        return true;
      }
    }
  }

  // Estratégia 3: qualquer select que contenha a opção desejada
  const todosSelects = page.locator('select');
  const qtd = await todosSelects.count().catch(() => 0);
  for (let i = 0; i < qtd; i++) {
    const sel = todosSelects.nth(i);
    const opts = await sel.locator('option').allTextContents().catch(() => []);
    const optMatch = opts.find(o => new RegExp(valor, 'i').test(o));
    if (optMatch) {
      await sel.selectOption({ label: optMatch });
      return true;
    }
  }

  if (obrigatorio) {
    log(`  ⚠️  Campo "${labelTexto}" não encontrado. Preencha manualmente.`);
    await ask(`  Preencha "${labelTexto}" no navegador e pressione ENTER… `);
    return true;
  }
  return false;
}

// ── Botão Salvar / Confirmar ──────────────────────────────────────────────────

async function clicarSalvar(page) {
  const nomes = [/salvar/i, /confirmar/i, /aplicar/i, /gravar/i, /concluir/i, /^ok$/i];
  for (const nome of nomes) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 1500 }).catch(() => false)) {
      await btn.click();
      await aguardar(page);
      return;
    }
  }
  throw new Error('Botão Salvar/Confirmar não encontrado. Verifique o modal no navegador.');
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
    console.log('\n┌─ Nova alteração ────────────────────────────────────────────────┐');
    console.log('│  1  Substituir projeto  (janela/porta com linha diferente)       │');
    console.log('│  2  Editar item         (vidro, cor/madeira, persiana)           │');
    console.log('└─────────────────────────────────────────────────────────────────┘');
    const tipo = (await ask('Tipo (1 ou 2): ')).trim();

    const itemRaw = (await ask('Número do item no orçamento (1, 2, 3…): ')).trim();
    const itemIdx = parseInt(itemRaw, 10) - 1;
    if (isNaN(itemIdx) || itemIdx < 0) { console.log('Número inválido.\n'); continue; }

    if (tipo === '1') {
      const novoProjeto = (await ask('Nome ou código do novo projeto/linha: ')).trim();
      if (!novoProjeto) { console.log('Nome obrigatório.\n'); continue; }
      alteracoes.push({ tipo: 'substituir', itemIdx, novoProjeto });

    } else {
      const campos = {};

      console.log('\n  Exemplos de vidro: INCOLOR 06MM - TEMPERADO, FUME 08MM - TEMPERADO, BRONZE 10MM - TEMPERADO');
      const v = (await ask('  VIDRO COR         (Enter = não alterar): ')).trim();
      if (v) campos.vidro = v;

      console.log('  Exemplos de cor  : BRANCO, NATURAL, PINTURA BRANCO BRILHANTE, MADEIRA GRAPIA, ANODIZADO BRONZE');
      const c = (await ask('  FOLHA TÊMPERA     (Enter = não alterar): ')).trim();
      if (c) campos.cor = c;

      console.log('  Exemplos persiana: motor, recolher fita, sem persiana');
      const p = (await ask('  PERSIANA          (Enter = não alterar): ')).trim();
      if (p) campos.persiana = p;

      if (!Object.keys(campos).length) { console.log('Nenhum campo informado.\n'); continue; }
      alteracoes.push({ tipo: 'editar', itemIdx, campos });
    }

    const mais = (await ask('\nAdicionar outra alteração neste orçamento? (s/n): ')).trim().toLowerCase();
    continuar = mais === 's';
  }

  rl.close();
  return { numero, alteracoes };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const { numero, alteracoes } = await coletarDados();
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
        await substituirProjeto(page, alt.itemIdx, alt.novoProjeto);
      } else {
        await editarItem(page, alt.itemIdx, alt.campos);
      }
    }

    console.log('\n✅  Todas as alterações concluídas com sucesso!');
    console.log('   Navegador aberto para você revisar antes de fechar.\n');

  } catch (err) {
    console.error('\n❌  Erro durante a automação:', err.message);
    const ss = path.join(process.cwd(), 'erro-wvetro.png');
    await page.screenshot({ path: ss, fullPage: true }).catch(() => {});
    console.log(`   Screenshot salvo em: ${ss}`);
    console.log('   Navegador aberto para investigação.\n');
  }
}

main().catch(console.error);
