'use strict';

const { chromium } = require('playwright');
const readline = require('readline');
const path = require('path');
require('dotenv').config();

const URL_WVETRO = 'https://sistema.wvetro.com.br/concept/app.wvetro.home';

// ── Utilitários ───────────────────────────────────────────────────────────────

const rl = readline.createInterface({ input: process.stdin, output: process.stdout });

function ask(prompt) {
  return new Promise(res => rl.question(prompt, res));
}

function log(msg) {
  console.log(`[${new Date().toLocaleTimeString('pt-BR')}] ${msg}`);
}

async function aguardarCarregar(page, timeout = 12000) {
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch {
    // timeout aceitável — sistemas com polling contínuo nunca ficam totalmente idle
  }
}

// ── Login ─────────────────────────────────────────────────────────────────────

async function handleLogin(page) {
  const senhaInput = page.locator('input[type="password"]');
  const precisaLogin = await senhaInput.isVisible({ timeout: 4000 }).catch(() => false);

  if (!precisaLogin) {
    log('Sessão ativa encontrada. Continuando…');
    return;
  }

  log('Tela de login detectada.');
  const senha = process.env.WVETRO_SENHA;

  if (senha) {
    await senhaInput.fill(senha);
    await page.keyboard.press('Enter');
    await aguardarCarregar(page);
    log('Login realizado automaticamente.');
  } else {
    console.log('\n⚠️  Faça o login no Chrome que abriu.');
    await ask('Pressione ENTER aqui depois de entrar no sistema… ');
    log('Continuando após login manual.');
  }
}

// ── Navegar até o orçamento ───────────────────────────────────────────────────

async function abrirOrcamento(page, numero) {
  log(`Buscando orçamento ${numero}…`);

  // Tenta campo de busca
  const seletoresBusca = [
    'input[placeholder*="buscar" i]',
    'input[placeholder*="pesquisar" i]',
    'input[placeholder*="orçamento" i]',
    'input[placeholder*="número" i]',
    'input[type="search"]',
    '[class*="search"] input',
    '[class*="busca"] input',
  ];

  for (const sel of seletoresBusca) {
    const campo = page.locator(sel).first();
    if (await campo.isVisible({ timeout: 1500 }).catch(() => false)) {
      await campo.click();
      await campo.fill(numero);
      await page.keyboard.press('Enter');
      await aguardarCarregar(page);
      break;
    }
  }

  // Clica no orçamento encontrado
  const link = page.locator(`text="${numero}"`).or(page.locator(`[title="${numero}"]`)).first();
  await link.click({ timeout: 10000 });
  await aguardarCarregar(page);
  log('Orçamento aberto.');
}

// ── Abrir menu de 3 pontos do item ───────────────────────────────────────────

async function abrirMenuItem(page, itemIdx) {
  // Seletores comuns para botão de "mais opções" (⋮ / 3 pontos)
  const seletores = [
    'button[mat-icon-button]',
    'button.mat-icon-button',
    'button[matIconButton]',
    'mat-icon-button',
    '[class*="more-vert"]',
    'button[aria-label*="opções" i]',
    'button[aria-label*="mais" i]',
    'button[aria-label*="menu" i]',
    '[class*="kebab"]',
    '[class*="opcoes"]',
    'button:has(mat-icon)',
  ];

  for (const sel of seletores) {
    const botoes = page.locator(sel);
    const qtd = await botoes.count().catch(() => 0);
    if (qtd > itemIdx) {
      const botao = botoes.nth(itemIdx);
      await botao.scrollIntoViewIfNeeded();
      await botao.click();
      await page.waitForTimeout(500);
      return;
    }
  }

  throw new Error(
    `Botão de opções (⋮) do item ${itemIdx + 1} não encontrado.\n` +
    `Verifique se o número do item está correto e se o orçamento está aberto.`
  );
}

// ── Substituir projeto ────────────────────────────────────────────────────────

async function substituirProjeto(page, itemIdx, novoProjeto) {
  log(`Substituindo projeto do item ${itemIdx + 1} por "${novoProjeto}"…`);

  await abrirMenuItem(page, itemIdx);

  // Clica na opção do menu
  await page
    .getByRole('menuitem', { name: /substituir projeto/i })
    .or(page.getByText(/substituir projeto/i).first())
    .click({ timeout: 5000 });
  await aguardarCarregar(page);

  // Dentro do modal: busca e seleciona o novo projeto
  const dialog = page.locator('mat-dialog-container, [role="dialog"]').first();
  const campoBusca = dialog.locator('input').first();
  await campoBusca.fill(novoProjeto);
  await page.waitForTimeout(800);

  const opcao = page
    .getByRole('option', { name: new RegExp(novoProjeto, 'i') })
    .or(page.locator('mat-option').filter({ hasText: new RegExp(novoProjeto, 'i') }))
    .first();
  await opcao.click({ timeout: 5000 });
  await aguardarCarregar(page);

  await clicarSalvar(page);
  log(`✓ Projeto substituído.`);
}

// ── Editar item (vidro / cor / madeira / persiana) ────────────────────────────

async function editarItem(page, itemIdx, campos) {
  log(`Editando item ${itemIdx + 1}…`);

  await abrirMenuItem(page, itemIdx);

  await page
    .getByRole('menuitem', { name: /editar item/i })
    .or(page.getByText(/editar item do orça/i).first())
    .click({ timeout: 5000 });
  await aguardarCarregar(page);

  const dialog = page.locator('mat-dialog-container, [role="dialog"]').first();

  if (campos.vidro) {
    log(`  → Vidro: ${campos.vidro}`);
    await preencherCampo(page, dialog, ['vidro', 'glass', 'tipo_vidro', 'tipovid'], campos.vidro);
  }

  if (campos.cor) {
    log(`  → Cor / madeira: ${campos.cor}`);
    await preencherCampo(page, dialog, ['cor', 'madeira', 'color', 'acabamento', 'revestimento'], campos.cor);
  }

  if (campos.persiana) {
    log(`  → Persiana: ${campos.persiana}`);
    await preencherCampo(page, dialog, ['persiana', 'acionamento', 'motor', 'fita', 'comando'], campos.persiana);
  }

  await clicarSalvar(page);
  log(`✓ Item ${itemIdx + 1} salvo.`);
}

// ── Preencher campo (select ou input) ────────────────────────────────────────

async function preencherCampo(page, dialog, palavras, valor) {
  // Monta seletor com as palavras-chave nos atributos mais comuns
  const partes = palavras.flatMap(p => [
    `[formcontrolname*="${p}" i]`,
    `[placeholder*="${p}" i]`,
    `[aria-label*="${p}" i]`,
    `[name*="${p}" i]`,
    `[id*="${p}" i]`,
  ]);
  const attrSel = partes.join(', ');

  // 1) Tenta mat-select (dropdown Angular Material)
  const selects = dialog.locator('mat-select');
  const qtdSelects = await selects.count().catch(() => 0);
  for (let i = 0; i < qtdSelects; i++) {
    const sel = selects.nth(i);
    // Verifica se o atributo ou label do select contém uma das palavras
    const labelEl = dialog.locator(`mat-label`).nth(i);
    const labelText = await labelEl.innerText().catch(() => '');
    const temPalavra = palavras.some(p => labelText.toLowerCase().includes(p));
    if (temPalavra) {
      await sel.click();
      await page.waitForTimeout(400);
      await page
        .getByRole('option', { name: new RegExp(valor, 'i') })
        .or(page.locator('mat-option').filter({ hasText: new RegExp(valor, 'i') }))
        .first()
        .click({ timeout: 4000 });
      return;
    }
  }

  // 2) Tenta pelo atributo direto
  const campo = dialog.locator(attrSel).first();
  if (await campo.isVisible({ timeout: 2000 }).catch(() => false)) {
    const tagName = await campo.evaluate(el => el.tagName.toLowerCase()).catch(() => 'input');
    if (tagName === 'mat-select' || tagName === 'select') {
      await campo.click();
      await page.waitForTimeout(400);
      await page
        .getByRole('option', { name: new RegExp(valor, 'i') })
        .first()
        .click({ timeout: 4000 });
    } else {
      await campo.fill(valor);
      await page.waitForTimeout(600);
      const opcao = page.getByRole('option', { name: new RegExp(valor, 'i') }).first();
      if (await opcao.isVisible({ timeout: 1500 }).catch(() => false)) {
        await opcao.click();
      }
    }
    return;
  }

  log(`  ⚠️  Campo "${palavras[0]}" não encontrado automaticamente. Você precisará preencher manualmente no navegador.`);
  await ask(`  Preencha "${palavras[0]}" no navegador e pressione ENTER para continuar… `);
}

// ── Botão Salvar / Confirmar ──────────────────────────────────────────────────

async function clicarSalvar(page) {
  const nomes = [/salvar/i, /confirmar/i, /aplicar/i, /ok/i, /concluir/i, /gravar/i];
  for (const nome of nomes) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 1500 }).catch(() => false)) {
      await btn.click();
      await aguardarCarregar(page);
      return;
    }
  }
  throw new Error('Botão Salvar/Confirmar não encontrado. Verifique o modal aberto no navegador.');
}

// ── Coleta de dados via terminal ──────────────────────────────────────────────

async function coletarDados() {
  console.log('\n╔══════════════════════════════════════════════════════╗');
  console.log('║   Automação W-vetro — Alteração de Orçamentos       ║');
  console.log('╚══════════════════════════════════════════════════════╝\n');

  const numero = (await ask('Número do orçamento: ')).trim();
  const alteracoes = [];
  let continuar = true;

  while (continuar) {
    console.log('\n┌─ Nova alteração ─────────────────────────────────────┐');
    console.log('│  1  Substituir projeto  (janela/porta linha diferente)│');
    console.log('│  2  Editar item         (vidro, cor, madeira, persiana)│');
    console.log('└───────────────────────────────────────────────────────┘');
    const tipo = (await ask('Tipo (1 ou 2): ')).trim();

    const itemRaw = (await ask('Número do item no orçamento (ex: 1, 2, 3…): ')).trim();
    const itemIdx = parseInt(itemRaw, 10) - 1;
    if (isNaN(itemIdx) || itemIdx < 0) {
      console.log('Número inválido, tente de novo.\n');
      continue;
    }

    if (tipo === '1') {
      const novoProjeto = (await ask('Nome/código do novo projeto ou linha: ')).trim();
      if (!novoProjeto) { console.log('Nome obrigatório.\n'); continue; }
      alteracoes.push({ tipo: 'substituir', itemIdx, novoProjeto });
    } else {
      const campos = {};
      const v = (await ask('Tipo de vidro        (Enter = não alterar): ')).trim();
      if (v) campos.vidro = v;
      const c = (await ask('Cor / madeira        (Enter = não alterar): ')).trim();
      if (c) campos.cor = c;
      const p = (await ask('Persiana motor/fita  (Enter = não alterar): ')).trim();
      if (p) campos.persiana = p;

      if (!Object.keys(campos).length) {
        console.log('Nenhum campo informado. Pulando.\n');
        continue;
      }
      alteracoes.push({ tipo: 'editar', itemIdx, campos });
    }

    const mais = (await ask('\nAdicionar mais uma alteração? (s/n): ')).trim().toLowerCase();
    continuar = mais === 's';
  }

  rl.close();
  return { numero, alteracoes };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const { numero, alteracoes } = await coletarDados();

  if (!alteracoes.length) {
    console.log('\nNenhuma alteração informada. Encerrando.');
    return;
  }

  log(`\nAbrindo Chrome… (${alteracoes.length} alteração(ões) para o orçamento ${numero})`);

  // Tenta usar o Chrome instalado; se não encontrar, usa o Chromium do Playwright
  const browser = await chromium
    .launch({ headless: false, channel: 'chrome', args: ['--start-maximized'] })
    .catch(() => chromium.launch({ headless: false, args: ['--start-maximized'] }));

  const ctx = await browser.newContext({ viewport: null });
  const page = await ctx.newPage();

  try {
    await page.goto(URL_WVETRO, { waitUntil: 'domcontentloaded', timeout: 30000 });
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
    console.log('   O navegador ficará aberto para você revisar antes de fechar.\n');
  } catch (err) {
    console.error('\n❌  Erro durante a automação:', err.message);
    const ss = path.join(process.cwd(), 'erro-wvetro.png');
    await page.screenshot({ path: ss, fullPage: true }).catch(() => {});
    console.log(`   Screenshot salvo em: ${ss}`);
    console.log('   O navegador ficará aberto para você ver onde parou.\n');
  }
}

main().catch(console.error);
