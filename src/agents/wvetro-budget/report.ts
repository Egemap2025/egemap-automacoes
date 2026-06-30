import ExcelJS from 'exceljs';
import * as path from 'path';
import * as fs from 'fs';
import { ProdutoEsquadria } from './rules';
import { AnaliseFloorPlan } from './analyzer';
import { logger } from '../../utils/logger';

const OUTPUTS_DIR = path.join(process.cwd(), 'outputs');
fs.mkdirSync(OUTPUTS_DIR, { recursive: true });

export interface ReportResult {
  excelPath: string;
  resumoTexto: string;
}

export async function gerarRelatorio(
  produtos: ProdutoEsquadria[],
  analise: AnaliseFloorPlan,
  sessionId: string
): Promise<ReportResult> {
  const excelPath = path.join(OUTPUTS_DIR, `orcamento_${sessionId}.xlsx`);

  const workbook = new ExcelJS.Workbook();
  workbook.creator = 'Egemap Automações';
  workbook.created = new Date();

  const sheet = workbook.addWorksheet('Quantitativos', {
    pageSetup: { paperSize: 9, orientation: 'landscape', fitToPage: true },
  });

  // Cabeçalho principal
  sheet.mergeCells('A1:I1');
  const titulo = sheet.getCell('A1');
  titulo.value = 'EGEMAP ESQUADRIAS — ORÇAMENTO AUTOMÁTICO';
  titulo.font = { bold: true, size: 14, color: { argb: 'FFFFFFFF' } };
  titulo.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF1E3A5F' } };
  titulo.alignment = { horizontal: 'center', vertical: 'middle' };
  sheet.getRow(1).height = 36;

  // Data e confiança
  sheet.mergeCells('A2:I2');
  const info = sheet.getCell('A2');
  const confiancaTexto = { alta: '✓ Alta', media: '⚠ Média', baixa: '✗ Baixa' }[analise.confianca];
  info.value = `Gerado em: ${new Date().toLocaleString('pt-BR')}   |   Confiança da leitura: ${confiancaTexto}`;
  info.font = { italic: true, size: 9, color: { argb: 'FF555555' } };
  info.alignment = { horizontal: 'right' };
  sheet.getRow(2).height = 18;

  // Linha em branco
  sheet.addRow([]);

  // Cabeçalho das colunas
  const colHeaders = ['Ambiente', 'Descrição', 'Linha', 'Cor', 'Larg. (cm)', 'Alt. (cm)', 'Tipo de Vidro', 'Esp. (mm)', 'Qtd'];
  const headerRow = sheet.addRow(colHeaders);
  headerRow.height = 22;
  headerRow.eachCell((cell) => {
    cell.font = { bold: true, size: 10, color: { argb: 'FFFFFFFF' } };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FF2E5090' } };
    cell.alignment = { horizontal: 'center', vertical: 'middle', wrapText: true };
    cell.border = {
      top: { style: 'thin' },
      bottom: { style: 'thin' },
      left: { style: 'thin' },
      right: { style: 'thin' },
    };
  });

  // Larguras das colunas
  sheet.getColumn(1).width = 22; // Ambiente
  sheet.getColumn(2).width = 22; // Descrição
  sheet.getColumn(3).width = 8;  // Linha
  sheet.getColumn(4).width = 10; // Cor
  sheet.getColumn(5).width = 12; // Largura
  sheet.getColumn(6).width = 12; // Altura
  sheet.getColumn(7).width = 18; // Tipo vidro
  sheet.getColumn(8).width = 10; // Espessura
  sheet.getColumn(9).width = 8;  // Qtd

  // Linhas de dados
  let totalItens = 0;
  produtos.forEach((p, i) => {
    const row = sheet.addRow([
      p.ambiente,
      p.persiana_motor ? `${p.descricao} ⚡` : p.descricao,
      p.linha,
      p.cor,
      p.largura_cm,
      p.altura_cm,
      p.tipo_vidro,
      p.espessura_vidro_mm > 0 ? p.espessura_vidro_mm : '—',
      p.quantidade,
    ]);

    const bgColor = i % 2 === 0 ? 'FFF5F8FF' : 'FFFFFFFF';
    row.eachCell((cell, colNum) => {
      cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: bgColor } };
      cell.border = {
        top: { style: 'hair', color: { argb: 'FFCCCCCC' } },
        bottom: { style: 'hair', color: { argb: 'FFCCCCCC' } },
        left: { style: 'hair', color: { argb: 'FFCCCCCC' } },
        right: { style: 'hair', color: { argb: 'FFCCCCCC' } },
      };
      cell.font = { size: 10 };
      if (colNum >= 5) cell.alignment = { horizontal: 'center' };

      // Destaque para persiana
      if (p.persiana_motor && colNum === 2) {
        cell.font = { size: 10, color: { argb: 'FF1A5FAB' } };
      }
    });

    totalItens += p.quantidade;
  });

  // Linha de total
  const totalRow = sheet.addRow(['', 'TOTAL GERAL', '', '', '', '', '', '', totalItens]);
  totalRow.eachCell((cell) => {
    cell.font = { bold: true, size: 11, color: { argb: 'FF1E3A5F' } };
    cell.fill = { type: 'pattern', pattern: 'solid', fgColor: { argb: 'FFD6E4F7' } };
    cell.border = {
      top: { style: 'medium', color: { argb: 'FF2E5090' } },
      bottom: { style: 'medium', color: { argb: 'FF2E5090' } },
    };
  });
  totalRow.getCell(9).alignment = { horizontal: 'center' };

  // Observações
  if (analise.observacoes) {
    sheet.addRow([]);
    const obsRow = sheet.addRow([`📋 Observações da IA: ${analise.observacoes}`]);
    obsRow.getCell(1).font = { italic: true, size: 9, color: { argb: 'FF666666' } };
    sheet.mergeCells(`A${obsRow.number}:I${obsRow.number}`);
  }

  await workbook.xlsx.writeFile(excelPath);
  logger.info(`Relatório Excel gerado: ${excelPath}`);

  return {
    excelPath,
    resumoTexto: construirResumo(produtos, analise, totalItens),
  };
}

function construirResumo(produtos: ProdutoEsquadria[], analise: AnaliseFloorPlan, totalItens: number): string {
  const emoji = { alta: '🟢', media: '🟡', baixa: '🔴' }[analise.confianca];

  // Agrupa por descrição + espessura para o resumo
  const grupos = new Map<string, number>();
  for (const p of produtos) {
    const chave = p.persiana_motor
      ? `Persiana com Motor ⚡`
      : `${p.descricao} — ${p.tipo_vidro}${p.espessura_vidro_mm > 0 ? ` ${p.espessura_vidro_mm}mm` : ''}`;
    grupos.set(chave, (grupos.get(chave) || 0) + p.quantidade);
  }

  let msg = `✅ *Análise da planta concluída!*\n`;
  msg += `${emoji} Confiança da leitura: *${analise.confianca}*\n\n`;
  msg += `📐 *QUANTITATIVO — LINHA 25 BRANCO*\n`;
  msg += `${'━'.repeat(28)}\n`;

  for (const [desc, qtd] of grupos) {
    msg += `• *${qtd}x* ${desc}\n`;
  }

  msg += `${'━'.repeat(28)}\n`;
  msg += `📦 *Total: ${totalItens} itens*\n`;

  if (analise.observacoes) {
    msg += `\n📝 _${analise.observacoes}_\n`;
  }

  return msg;
}
