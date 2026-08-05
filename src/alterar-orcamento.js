'use strict';

const { chromium } = require('playwright');
const readline = require('readline');
const path = require('path');
require('dotenv').config();

const URL_HOME  = 'https://sistema.wvetro.com.br/concept/app.wvetro.home';
const URL_LISTA = 'https://sistema.wvetro.com.br/concept/app.core.wworcamento';

const rl  = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (p) => new Promise(r => rl.question(p, r));

// ── Aguardar página estabilizar ───────────────────────────────────────────────

async function esperar(page, ms = 2000) {
  await page.waitForTimeout(ms);
  await page.waitForLoadState('networkidle', { timeout: 8000 }).catch(() => {});
}

// ── Login ─────────────────────────────────────────────────────────────────────

async function fazerLogin(page) {
  await page.waitForTimeout(3000);
  const temLogin = page.url().includes('login') ||
    await page.locator('input[type="password"]').isVisible({ timeout: 5000 }).catch(() => false);
  if (!temLogin) { console.log('  → Sessão ativa.'); return; }

  let usuario = process.env.WVETRO_USUARIO;
  let senha   = process.env.WVETRO_SENHA;
  let licenca = process.env.WVETRO_LICENCA;

  if (!usuario || !senha) {
    console.log('\n── Login W-vetro ──────────────');
    if (!usuario) usuario = (await ask('  Usuário: ')).trim();
    if (!senha)   senha   = (await ask('  Senha:   ')).trim();
    if (!licenca) licenca = (await ask('  Licença: ')).trim();
    console.log('───────────────────────────────\n');
  }

  const inputs = page.locator('input');
  const n = await inputs.count();
  if (n >= 1) await inputs.nth(0).fill(usuario);
  if (n >= 2) await inputs.nth(1).fill(senha);
  if (n >= 3 && licenca) await inputs.nth(2).fill(licenca);

  await page.getByRole('button', { name: /entrar|login|acessar/i }).click({ timeout: 5000 });
  await esperar(page, 3000);
  console.log('  → Login realizado!\n');
}

// ── Abrir orçamento pelo número ───────────────────────────────────────────────

async function abrirOrcamento(page, numero) {
  console.log(`  Navegando para lista de orçamentos…`);
  await page.goto(URL_LISTA, { waitUntil: 'commit', timeout: 60000 });
  await esperar(page, 3000);

  // Seleciona "Nro.Orçamento" no dropdown de filtro
  const selects = page.locator('select');
  const qtd = await selects.count();
  for (let i = 0; i < qtd; i++) {
    const sel = selects.nth(i);
    const opts = await sel.locator('option').allTextContents().catch(() => []);
    const opt  = opts.find(o => /nro|número|numero/i.test(o) && /or[çc]/i.test(o));
    if (opt) { await sel.selectOption({ label: opt }); await page.waitForTimeout(500); break; }
  }

  // Preenche o número no campo de valor (último input visível)
  const allInputs = page.locator('input[type="text"], input[type="number"], input:not([type])');
  const nInputs = await allInputs.count();
  for (let i = nInputs - 1; i >= 0; i--) {
    const inp = allInputs.nth(i);
    if (await inp.isVisible({ timeout: 300 }).catch(() => false)) {
      await inp.clear();
      await inp.fill(numero);
      break;
    }
  }

  // Clica em Procurar
  const btnProcurar = page.locator('button, a, input[type="submit"]').filter({ hasText: /procurar/i }).first();
  if (await btnProcurar.isVisible({ timeout: 3000 }).catch(() => false)) {
    await btnProcurar.click();
  } else {
    await page.keyboard.press('Enter');
  }
  await esperar(page, 2000);

  // Encontra a linha e clica no link do cliente (nome azul) para abrir o orçamento
  const linha = page.locator('tbody tr').filter({ hasText: numero }).first();
  if (!await linha.isVisible({ timeout: 8000 }).catch(() => false)) {
    throw new Error(`Orçamento ${numero} não encontrado na lista.`);
  }

  const link = linha.locator('a').first();
  if (await link.isVisible({ timeout: 2000 }).catch(() => false)) {
    await link.click();
  } else {
    await linha.click();
  }

  await page.waitForURL(/detalheorcamento/i, { timeout: 25000 });
  await esperar(page, 3000);
  console.log(`  → Orçamento ${numero} aberto!`);
}

// ── Clicar no botão ≡ e escolher ação no menu dropdown ───────────────────────
//
// Estrutura confirmada da linha de item (página detalheorcamento):
//   td[1]: botão ">"  (expandir a linha)
//   td[2]: checkbox □
//   td[3]: botão "≡"  ← abre o menu de ações (aparece ao hover)
//   td[4]: número de ordem
//   td[5]: nome do projeto
//   ...
//
// Menu dropdown (HTML comum, não Bootstrap Select):
//   - Alterar Foto
//   - Editar Item do Orç.
//   - Excluir
//   - Duplicar o Projeto
//   - Editar Variáveis
//   - Custo Projeto
//   - Editar Tipologia
//   - Alterar Valor
//   - Substituir Projeto

async function selecionarAcao(page, itemIdx, textoAcao) {
  await page.waitForSelector('tbody tr', { timeout: 15000 });
  await page.waitForTimeout(1500);

  const linhas = page.locator('tbody tr');
  const total  = await linhas.count();
  if (total <= itemIdx) throw new Error(`Item ${itemIdx + 1} não encontrado (${total} itens na tabela).`);

  const linha = linhas.nth(itemIdx);
  await linha.scrollIntoViewIfNeeded();

  // Hover para revelar o botão ≡ (aparece só quando o mouse está sobre a linha)
  await linha.hover();
  await page.waitForTimeout(1000);   // aguarda transição CSS

  // Clica no botão ≡ — está na 3ª célula da linha
  // Tenta vários seletores do mais específico ao mais genérico
  let clicou = false;
  for (const sel of [
    'td:nth-child(3) button',
    'td:nth-child(3) a',
    'td:nth-child(3) [role="button"]',
    'td:nth-child(3) i',
    'td:nth-child(3) span',
    'td:nth-child(3)',
    'td:nth-child(1) button',
    'td:nth-child(1) i',
    'button',
    'i[class*="bars"], i[class*="list"], i[class*="menu"]',
  ]) {
    const el = linha.locator(sel).first();
    if (await el.isVisible({ timeout: 600 }).catch(() => false)) {
      await el.click();
      await page.waitForTimeout(800);

      // Verifica se o menu abriu (qualquer opção do menu está visível)
      const menuAbriu = await page.getByText(/editar item|substituir projeto|alterar foto|duplicar/i)
        .isVisible({ timeout: 1500 }).catch(() => false);
      if (menuAbriu) { clicou = true; break; }
    }
  }

  if (!clicou) {
    throw new Error(`Não consegui abrir o menu do item ${itemIdx + 1}. Me mande um print da tela para eu ajustar.`);
  }

  // Clica na opção desejada no dropdown
  const reAcao = new RegExp(textoAcao.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'i');
  const opcao = page.getByText(reAcao).first();
  if (await opcao.isVisible({ timeout: 4000 }).catch(() => false)) {
    await opcao.click();
    await page.waitForTimeout(500);
    return;
  }

  throw new Error(`Opção "${textoAcao}" não apareceu no menu do item ${itemIdx + 1}.`);
}

// ── Encontra <select> pelo label ──────────────────────────────────────────────

async function selectPorLabel(page, ...labels) {
  for (const label of labels) {
    const re = new RegExp(label.replace(/[|/]/g, '.'), 'i');

    // 1. getByLabel (Playwright associa label → input/select automaticamente)
    const byLabel = page.getByLabel(re);
    if (await byLabel.isVisible({ timeout: 400 }).catch(() => false)) return byLabel;

    // 2. Linha <tr> que contém o label → select dentro dela
    const row = page.locator('tr').filter({ hasText: re }).first();
    if (await row.isVisible({ timeout: 400 }).catch(() => false)) {
      const sel = row.locator('select').first();
      if (await sel.isVisible({ timeout: 400 }).catch(() => false)) return sel;
    }

    // 3. Célula com texto do label seguida de célula com select
    const tdSel = page.locator(`td:has-text("${label}") + td select`).first();
    if (await tdSel.isVisible({ timeout: 400 }).catch(() => false)) return tdSel;

    // 4. <label> com texto → select associado pelo "for"
    const labelEl = page.locator('label').filter({ hasText: re }).first();
    if (await labelEl.isVisible({ timeout: 400 }).catch(() => false)) {
      const forAttr = await labelEl.getAttribute('for').catch(() => null);
      if (forAttr) {
        const assocSel = page.locator(`select#${forAttr}`);
        if (await assocSel.isVisible({ timeout: 400 }).catch(() => false)) return assocSel;
      }
    }
  }
  return null;
}

async function escolherOpcao(sel, valor) {
  const re = new RegExp(valor, 'i');
  const opts = await sel.locator('option').allTextContents().catch(() => []);
  const match = opts.find(o => re.test(o));
  if (match) { await sel.selectOption({ label: match }); return; }
  console.log(`  ⚠  "${valor}" não encontrado. Opções disponíveis: ${opts.slice(0, 8).join(' | ')}`);
}

// ── EDITAR ITEM ───────────────────────────────────────────────────────────────
//
// Abre modal "Altera Medida da Esquadria do Orçamento"
// Campos: FERRAGENS/ACESSÓRIOS, ALUMÍNIO/PERFIL, VIDRO COR

async function editarItem(page, itemIdx, campos) {
  console.log(`\n  Abrindo menu → "Editar Item do Orç." (item ${itemIdx + 1})…`);
  await selecionarAcao(page, itemIdx, 'editar item do orç');

  await page.waitForSelector('select', { timeout: 12000 });
  await page.waitForTimeout(800);
  console.log('  → Modal de edição aberto!');

  if (campos.vidro) {
    const sel = await selectPorLabel(page, 'VIDRO COR', 'VIDRO');
    if (sel) { await escolherOpcao(sel, campos.vidro); console.log(`     Vidro: ${campos.vidro}`); }
    else console.log('  ⚠  Campo VIDRO COR não encontrado no modal.');
  }

  if (campos.cor) {
    const sel = await selectPorLabel(page, 'ALUMÍNIO/PERFIL', 'ALUMINIO/PERFIL', 'COR ALUMÍNIO', 'FOLHA TÊMPERA');
    if (sel) { await escolherOpcao(sel, campos.cor); console.log(`     Alumínio: ${campos.cor}`); }
    else console.log('  ⚠  Campo ALUMÍNIO/PERFIL não encontrado no modal.');
  }

  if (campos.ferragens) {
    const sel = await selectPorLabel(page, 'FERRAGENS/ACESSÓRIOS', 'FERRAGENS');
    if (sel) { await escolherOpcao(sel, campos.ferragens); console.log(`     Ferragens: ${campos.ferragens}`); }
    else console.log('  ⚠  Campo FERRAGENS/ACESSÓRIOS não encontrado no modal.');
  }

  // Clica em Salvar
  for (const nome of [/^salvar$/i, /^gravar$/i, /^confirmar$/i, /^ok$/i, /salvar/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 1000 }).catch(() => false)) { await btn.click(); break; }
  }
  await esperar(page);
  console.log(`  ✓ Item ${itemIdx + 1} salvo!`);
}

// ── SUBSTITUIR PROJETO ────────────────────────────────────────────────────────

async function substituirProjeto(page, itemIdx, dados) {
  const urlOrcamento = page.url();
  console.log(`\n  Abrindo menu → "Substituir Projeto" (item ${itemIdx + 1})…`);
  await selecionarAcao(page, itemIdx, 'substituir projeto');

  await page.waitForURL(/selecioneprojeto/i, { timeout: 20000 });
  await esperar(page, 2000);
  console.log('  → Página de seleção de projeto!');

  if (dados.linha) {
    const sel = await selectPorLabel(page, 'LINHA');
    if (sel) { await escolherOpcao(sel, dados.linha); await page.waitForTimeout(800); }
  }
  if (dados.modelo) {
    const sel = await selectPorLabel(page, 'MODELO');
    if (sel) await escolherOpcao(sel, dados.modelo);
  }

  await page.getByRole('button', { name: /pesquisar/i }).click({ timeout: 5000 });
  await esperar(page, 2000);

  // Se aparecer lista de resultados, clica no primeiro
  if (!await page.getByText(/DADOS DO PROJETO/i).isVisible({ timeout: 2000 }).catch(() => false)) {
    const primeiraLinha = page.locator('tbody tr').first();
    if (await primeiraLinha.isVisible({ timeout: 3000 }).catch(() => false)) {
      await primeiraLinha.click();
      await esperar(page, 2000);
    }
  }

  await page.waitForSelector('select', { timeout: 15000 });
  console.log('  → Detalhes do projeto!');

  if (dados.vidro) {
    const sel = await selectPorLabel(page, 'VIDRO COR', 'VIDRO');
    if (sel) await escolherOpcao(sel, dados.vidro);
  }
  if (dados.cor) {
    const sel = await selectPorLabel(page, 'ALUMÍNIO/PERFIL', 'COR ALUMÍNIO', 'ALUMINIO/PERFIL');
    if (sel) await escolherOpcao(sel, dados.cor);
  }

  await page.getByRole('button', { name: /incluir item no orçamento/i }).click({ timeout: 8000 });
  await page.waitForTimeout(2000);

  // Modal de variáveis (ex: persiana)
  if (await page.getByText(/informe as variáveis/i).isVisible({ timeout: 4000 }).catch(() => false)) {
    if (dados.persiana) {
      const row = page.locator('tr').filter({ hasText: /ACIONAMENTO DA ESTEIRA/i }).first();
      if (await row.isVisible({ timeout: 2000 }).catch(() => false)) {
        await escolherOpcao(row.locator('select').first(), dados.persiana);
      }
    }
    await page.getByRole('button', { name: /confirmar/i }).click({ timeout: 5000 });
    await page.waitForTimeout(2000);
  }

  const calcBtn = page.getByRole('button', { name: /calcular o orçamento/i });
  if (await calcBtn.isVisible({ timeout: 5000 }).catch(() => false)) {
    await calcBtn.click();
    await esperar(page, 3000);
  }

  for (const nome of [/fechar/i, /^ok$/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) { await btn.click(); break; }
  }

  if (!page.url().includes('detalhe')) {
    await page.goto(urlOrcamento, { waitUntil: 'commit', timeout: 60000 });
    await esperar(page, 2000);
  }
  console.log(`  ✓ Projeto substituído!`);
}

// ── Coleta de dados ───────────────────────────────────────────────────────────

async function coletarDados() {
  console.log('\n╔══════════════════════════════════════════════╗');
  console.log('║   W-vetro — Editor de Orçamentos            ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  const numero = (await ask('Número do orçamento: ')).trim();
  const alteracoes = [];
  let continuar = true;

  while (continuar) {
    console.log('\nTipo:  1-Substituir projeto   2-Editar item (vidro/cor/ferragens)');
    const tipo = (await ask('Escolha [1 ou 2]: ')).trim();
    const itemIdx = parseInt((await ask('Número do item (1, 2, 3…): ')).trim(), 10) - 1;
    const dados = { tipo, itemIdx };

    if (tipo === '1') {
      dados.linha  = (await ask('LINHA  (ex: PERFISUD): ')).trim();
      dados.modelo = (await ask('MODELO (ex: JANELA DE CORRER 02 FOLHAS): ')).trim();
      dados.vidro  = (await ask('VIDRO  (ex: INCOLOR 06MM - TEMPERADO): ')).trim();
      const cor = (await ask('COR ALUMÍNIO (Enter para pular): ')).trim(); if (cor) dados.cor = cor;
      const per = (await ask('PERSIANA — ACIONAMENTO (Enter para pular): ')).trim(); if (per) dados.persiana = per;
    } else {
      console.log('  (deixe em branco para não alterar o campo)');
      const v = (await ask('VIDRO COR         : ')).trim(); if (v) dados.vidro = v;
      const c = (await ask('ALUMÍNIO / PERFIL : ')).trim(); if (c) dados.cor = c;
      const f = (await ask('FERRAGENS         : ')).trim(); if (f) dados.ferragens = f;
    }

    alteracoes.push(dados);
    continuar = (await ask('\nOutra alteração? [s/n]: ')).trim().toLowerCase() === 's';
  }

  return { numero, alteracoes };
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  const { numero, alteracoes } = await coletarDados();

  console.log('\nAbrindo Chrome…');
  const browser = await chromium.launch({ channel: 'chrome', headless: false, slowMo: 80 })
    .catch(() => chromium.launch({ headless: false, slowMo: 80 }));
  const page = await browser.newContext({ viewport: null }).then(c => c.newPage());

  try {
    await page.goto(URL_HOME, { waitUntil: 'commit', timeout: 60000 });
    await fazerLogin(page);
    rl.close(); // fecha readline depois do login (não precisa mais de input)
    await abrirOrcamento(page, numero);

    for (const alt of alteracoes) {
      if (alt.tipo === '1') await substituirProjeto(page, alt.itemIdx, alt);
      else                   await editarItem(page, alt.itemIdx, alt);
    }

    console.log('\n✅  Tudo concluído! Chrome fica aberto para revisão.\n');
  } catch (err) {
    console.error('\n❌  Erro:', err.message);
    const ss = path.join(process.cwd(), 'erro-wvetro.png');
    await page.screenshot({ path: ss, fullPage: true }).catch(() => {});
    console.log(`   Screenshot salvo em: ${ss}`);
    console.log('   Me mande esse screenshot para eu corrigir.\n');
  }
}

main().catch(console.error);
