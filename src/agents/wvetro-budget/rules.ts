import { Abertura } from './analyzer';

export interface ProdutoEsquadria {
  ambiente: string;
  descricao: string;
  linha: string;
  cor: string;
  tipo_vidro: string;
  espessura_vidro_mm: number;
  persiana_motor: boolean;
  largura_cm: number;
  altura_cm: number;
  quantidade: number;
}

/**
 * Regras Egemap Esquadrias:
 * - Alumínio branco Linha 25 em tudo
 * - Janelas comuns: vidro temperado 6mm
 * - Dormitórios: vidro temperado 8mm + persiana com motor
 * - Portas: vidro temperado 8mm
 * - Banheiros: Maxim-Ar + vidro mini boreal 4mm
 */
export function aplicarRegras(aberturas: Abertura[]): ProdutoEsquadria[] {
  const produtos: ProdutoEsquadria[] = [];

  for (const abertura of aberturas) {
    const resultado = converterAbertura(abertura);
    produtos.push(...resultado);
  }

  return produtos;
}

function converterAbertura(abertura: Abertura): ProdutoEsquadria[] {
  const { tipo, tipo_ambiente, largura_cm, altura_cm, quantidade, ambiente } = abertura;

  // Banheiro → Maxim-Ar com mini boreal 4mm
  if (tipo_ambiente === 'banheiro') {
    return [
      {
        ambiente,
        descricao: 'Maxim-Ar',
        linha: '25',
        cor: 'Branco',
        tipo_vidro: 'Mini Boreal',
        espessura_vidro_mm: 4,
        persiana_motor: false,
        largura_cm,
        altura_cm,
        quantidade,
      },
    ];
  }

  // Dormitório: janela/porta-janela → 8mm temperado + persiana com motor
  if (tipo_ambiente === 'dormitorio' && (tipo === 'janela' || tipo === 'porta-janela')) {
    return [
      {
        ambiente,
        descricao: tipo === 'porta-janela' ? 'Porta-Janela' : 'Janela',
        linha: '25',
        cor: 'Branco',
        tipo_vidro: 'Temperado',
        espessura_vidro_mm: 8,
        persiana_motor: false,
        largura_cm,
        altura_cm,
        quantidade,
      },
      {
        ambiente,
        descricao: 'Persiana com Motor',
        linha: '25',
        cor: 'Branco',
        tipo_vidro: '-',
        espessura_vidro_mm: 0,
        persiana_motor: true,
        largura_cm,
        altura_cm,
        quantidade,
      },
    ];
  }

  // Porta → 8mm temperado
  if (tipo === 'porta' || tipo === 'porta-janela') {
    return [
      {
        ambiente,
        descricao: tipo === 'porta-janela' ? 'Porta-Janela' : 'Porta',
        linha: '25',
        cor: 'Branco',
        tipo_vidro: 'Temperado',
        espessura_vidro_mm: 8,
        persiana_motor: false,
        largura_cm,
        altura_cm,
        quantidade,
      },
    ];
  }

  // Demais janelas (sala, cozinha, área de serviço, etc.) → 6mm temperado
  return [
    {
      ambiente,
      descricao: 'Janela',
      linha: '25',
      cor: 'Branco',
      tipo_vidro: 'Temperado',
      espessura_vidro_mm: 6,
      persiana_motor: false,
      largura_cm,
      altura_cm,
      quantidade,
    },
  ];
}
