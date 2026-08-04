'use strict';

const { chromium } = require('playwright');
const readline = require('readline');
const path = require('path');
require('dotenv').config();

const rl  = readline.createInterface({ input: process.stdin, output: process.stdout });
const ask = (p) => new Promise(r => rl.question(p, r));

// ── Login ─────────────────────────────────────────────────────────────────────

async function fazerLogin(page) {
  await page.waitForTimeout(3000);
  const temLogin = page.url().includes('login') ||
    await page.locator('input[type="password"]').isVisible({ timeout: 4000 }).catch(() => false);
  if (!temLogin) return;

  let usuario = process.env.WVETRO_USUARIO;
  let senha   = process.env.WVETRO_SENHA;
  let licenca = process.env.WVETRO_LICENCA;

  if (!usuario || !senha) {
    console.log('\n── Informe seu login do W-vetro ──');
    if (!usuario) usuario = (await ask('  Usuário: ')).trim();
    if (!senha)   senha   = (await ask('  Senha:   ')).trim();
    if (!licenca) licenca = (await ask('  Licença: ')).trim();
    console.log('─────────────────────────────────\n');
  }

  const campoUsuario = page.locator('input').filter({ hasNot: page.locator('[type="password"]') }).first();
  if (await campoUsuario.isVisible({ timeout: 2000 }).catch(() => false)) await campoUsuario.fill(usuario);
  await page.locator('input[type="password"]').first().fill(senha);
  if (licenca) {
    const campos = page.locator('input');
    const n = await campos.count();
    if (n >= 3) await campos.nth(2).fill(licenca);
  }
  await page.getByRole('button', { name: /entrar|login|acessar/i }).click({ timeout: 5000 });
  await page.waitForLoadState('networkidle', { timeout: 20000 }).catch(() => {});
  console.log('  → Login realizado!\n');
}

// ── Encontra <select> pelo texto do label ─────────────────────────────────────

async function selectPorLabel(page, ...labels) {
  for (const label of labels) {
    const re = new RegExp(label.replace(/[|/]/g, '.'), 'i');
    const byLabel = page.getByLabel(re);
    if (await byLabel.isVisible({ timeout: 500 }).catch(() => false)) return byLabel;
    const row = page.locator('tr').filter({ hasText: re }).first();
    if (await row.isVisible({ timeout: 500 }).catch(() => false)) {
      const sel = row.locator('select').first();
      if (await sel.isVisible({ timeout: 500 }).catch(() => false)) return sel;
    }
    const tdSel = page.locator(`td:has-text("${label}") + td select`).first();
    if (await tdSel.isVisible({ timeout: 500 }).catch(() => false)) return tdSel;
  }
  return null;
}

async function escolherOpcao(sel, valor) {
  if (!sel || !valor) return false;
  const re = new RegExp(valor, 'i');
  const opts = await sel.locator('option').allTextContents().catch(() => []);
  const match = opts.find(o => re.test(o));
  if (match) { await sel.selectOption({ label: match }); return true; }
  console.log(`  ⚠  "${valor}" não encontrado nas opções. Opções disponíveis:`);
  opts.forEach((o, i) => console.log(`     ${i + 1}. ${o}`));
  await ask('  Escolha manualmente e pressione ENTER… ');
  return false;
}

// ── EDITAR ITEM ───────────────────────────────────────────────────────────────

async function editarItem(page, campos) {
  // Aguarda o modal abrir (o usuário já clicou em "Editar Item do Orç.")
  console.log('  Aguardando modal abrir…');
  await page.waitForSelector('select', { timeout: 15000 });
  await page.waitForTimeout(800);
  console.log('  → Modal aberto!\n');

  if (campos.vidro) {
    const sel = await selectPorLabel(page, 'VIDRO COR', 'VIDRO');
    if (sel) await escolherOpcao(sel, campos.vidro);
    else { console.log('  ⚠  Campo VIDRO não encontrado — preencha manualmente.'); await ask('  ENTER após preencher… '); }
  }

  if (campos.cor) {
    const sel = await selectPorLabel(page, 'ALUMÍNIO/PERFIL', 'ALUMINIO/PERFIL', 'COR ALUMÍNIO | PERFIL', 'FOLHA TÊMPERA', 'FOLHA TEMPERA');
    if (sel) await escolherOpcao(sel, campos.cor);
    else { console.log('  ⚠  Campo COR/PERFIL não encontrado — preencha manualmente.'); await ask('  ENTER após preencher… '); }
  }

  if (campos.ferragens) {
    const sel = await selectPorLabel(page, 'FERRAGENS/ACESSÓRIOS', 'FERRAGENS');
    if (sel) await escolherOpcao(sel, campos.ferragens);
  }

  // Clica em Salvar/Confirmar
  for (const nome of [/^salvar$/i, /^confirmar$/i, /^gravar$/i, /^ok$/i, /^aplicar$/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 1500 }).catch(() => false)) { await btn.click(); break; }
  }
  await page.waitForLoadState('networkidle', { timeout: 10000 }).catch(() => {});
  console.log('  ✓ Item salvo!\n');
}

// ── SUBSTITUIR PROJETO ────────────────────────────────────────────────────────

async function substituirProjeto(page, dados) {
  // Aguarda a página de seleção de projeto (o usuário já clicou em "Substituir Projeto")
  console.log('  Aguardando página de seleção de projeto…');
  await page.waitForURL(/selecioneprojeto/i, { timeout: 20000 });
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  console.log('  → Página aberta!\n');

  if (dados.linha) {
    const sel = await selectPorLabel(page, 'LINHA');
    if (sel) { await escolherOpcao(sel, dados.linha); await page.waitForTimeout(800); }
    else { console.log('  ⚠  Campo LINHA não encontrado.'); await ask('  Selecione manualmente e pressione ENTER… '); }
  }

  if (dados.modelo) {
    const sel = await selectPorLabel(page, 'MODELO');
    if (sel) await escolherOpcao(sel, dados.modelo);
    else { console.log('  ⚠  Campo MODELO não encontrado.'); await ask('  Selecione manualmente e pressione ENTER… '); }
  }

  await page.getByRole('button', { name: /pesquisar/i }).click({ timeout: 5000 });
  await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});

  // Se aparecer lista de resultados clica no primeiro
  const tabela = page.locator('tbody tr').first();
  if (await tabela.isVisible({ timeout: 3000 }).catch(() => false) &&
      !await page.getByText(/DADOS DO PROJETO/i).isVisible({ timeout: 1000 }).catch(() => false)) {
    await tabela.click();
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  }

  // Página de detalhes
  await page.waitForSelector('select', { timeout: 15000 });
  console.log('  → Página de detalhes do projeto!\n');

  if (dados.vidro) {
    const sel = await selectPorLabel(page, 'VIDRO');
    if (sel) await escolherOpcao(sel, dados.vidro);
    else { console.log('  ⚠  Campo VIDRO não encontrado — selecione manualmente!'); await ask('  ENTER após selecionar… '); }
  } else {
    await ask('  Selecione o VIDRO manualmente e pressione ENTER… ');
  }

  if (dados.cor) {
    const sel = await selectPorLabel(page, 'COR ALUMÍNIO | PERFIL', 'ALUMÍNIO/PERFIL', 'COR ALUMÍNIO');
    if (sel) await escolherOpcao(sel, dados.cor);
  }

  await page.getByRole('button', { name: /incluir item no orçamento/i }).click({ timeout: 8000 });
  await page.waitForTimeout(2000);

  // Modal de variáveis (persiana)
  const temModal = await page.getByText(/informe as variáveis/i).isVisible({ timeout: 4000 }).catch(() => false);
  if (temModal) {
    console.log('  → Modal de variáveis aberto.');
    if (dados.persiana) {
      const row = page.locator('tr').filter({ hasText: /ACIONAMENTO DA ESTEIRA/i }).first();
      if (await row.isVisible({ timeout: 2000 }).catch(() => false)) {
        await escolherOpcao(row.locator('select').first(), dados.persiana);
      } else { await ask('  Configure o ACIONAMENTO manualmente e pressione ENTER… '); }
    }
    await page.getByRole('button', { name: /confirmar/i }).click({ timeout: 5000 });
    await page.waitForTimeout(2000);
  }

  // Calcular
  const btnCalc = page.getByRole('button', { name: /calcular o orçamento/i });
  if (await btnCalc.isVisible({ timeout: 5000 }).catch(() => false)) {
    await btnCalc.click();
    await page.waitForLoadState('networkidle', { timeout: 15000 }).catch(() => {});
  }

  // Fecha avisos
  for (const nome of [/fechar/i, /^ok$/i]) {
    const btn = page.getByRole('button', { name: nome });
    if (await btn.isVisible({ timeout: 3000 }).catch(() => false)) { await btn.click(); break; }
  }

  console.log('  ✓ Projeto substituído!\n');
}

// ── Main ──────────────────────────────────────────────────────────────────────

async function main() {
  console.log('\n╔══════════════════════════════════════════════╗');
  console.log('║   W-vetro — Editor de Orçamentos            ║');
  console.log('╚══════════════════════════════════════════════╝\n');

  // Coleta as alterações desejadas
  const alteracoes = [];
  let continuar = true;

  while (continuar) {
    console.log('Tipo de alteração:');
    console.log('  1 - Substituir projeto  (nova linha/modelo)');
    console.log('  2 - Editar item         (vidro, cor, ferragens)');
    const tipo = (await ask('Escolha [1 ou 2]: ')).trim();

    const itemNum = parseInt((await ask('Número do item no orçamento (1, 2, 3…): ')).trim(), 10);

    let dados = { tipo, itemIdx: itemNum - 1 };

    if (tipo === '1') {
      dados.linha    = (await ask('LINHA    (ex: PERFISUD): ')).trim();
      dados.modelo   = (await ask('MODELO   (ex: JANELA DE CORRER 02 FOLHAS): ')).trim();
      dados.vidro    = (await ask('VIDRO    (ex: INCOLOR 06MM - TEMPERADO): ')).trim();
      const cor = (await ask('COR ALUMÍNIO / PERFIL  (Enter para pular): ')).trim();
      if (cor) dados.cor = cor;
      const per = (await ask('ACIONAMENTO PERSIANA  (RECOLHEDOR FITA / MOTOR / Enter para pular): ')).trim();
      if (per) dados.persiana = per;
    } else {
      const vidro = (await ask('VIDRO COR          (Enter para não alterar): ')).trim();
      if (vidro) dados.vidro = vidro;
      const cor = (await ask('ALUMÍNIO / PERFIL  (Enter para não alterar): ')).trim();
      if (cor) dados.cor = cor;
      const ferr = (await ask('FERRAGENS          (Enter para não alterar): ')).trim();
      if (ferr) dados.ferragens = ferr;
    }

    alteracoes.push(dados);
    continuar = (await ask('\nAdicionar outra alteração? [s/n]: ')).trim().toLowerCase() === 's';
  }

  // Abre o Chrome
  console.log('\nAbrindo Chrome…');
  const browser = await chromium.launch({ channel: 'chrome', headless: false })
    .catch(() => chromium.launch({ headless: false }));
  const page = await browser.newContext({ viewport: null }).then(c => c.newPage());

  await page.goto('https://sistema.wvetro.com.br/concept/app.wvetro.home', { waitUntil: 'commit', timeout: 60000 });
  await fazerLogin(page);

  // Pede ao usuário para navegar ao orçamento
  console.log('═══════════════════════════════════════════════');
  console.log('  No Chrome, abra o orçamento normalmente.');
  console.log('  (Vendas → Vendas/Orçamentos → Procurar → clique no orçamento)');
  console.log('═══════════════════════════════════════════════');
  await ask('  Pressione ENTER quando o orçamento estiver aberto… ');
  await page.waitForTimeout(1000);

  // Executa as alterações
  for (const alt of alteracoes) {
    console.log(`\n── Item ${alt.itemIdx + 1} ──────────────────────────────────`);
    if (alt.tipo === '1') {
      console.log(`  No Chrome, clique nos 3 pontos do item ${alt.itemIdx + 1} e escolha "Substituir Projeto".`);
      await ask('  Pressione ENTER depois de clicar em "Substituir Projeto"… ');
      await substituirProjeto(page, alt);
    } else {
      console.log(`  No Chrome, clique nos 3 pontos do item ${alt.itemIdx + 1} e escolha "Editar Item do Orç.".`);
      await ask('  Pressione ENTER depois de clicar em "Editar Item do Orç."… ');
      await editarItem(page, alt);
    }
  }

  rl.close();
  console.log('✅  Concluído! Chrome fica aberto para revisão.\n');
}

main().catch(err => {
  console.error('\n❌  Erro:', err.message);
  rl.close();
});
