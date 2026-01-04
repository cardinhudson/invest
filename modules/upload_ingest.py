"""Upload unificado (PDF Avenue/Apex + Excel).

Este módulo centraliza:
- salvamento de arquivos em pastas padrão
- opção de sobrescrever vs. apenas adicionar novos
- detecção de tipo (PDF/Excel)
- inferência de usuário e mês/ano a partir do nome
- encaminhamento para os pipelines existentes (com deduplicações/validações atuais)

A página Streamlit deve chamar `processar_uploads`.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

import pandas as pd

from modules.usuarios import carregar_usuarios
from modules.upload_relatorio import (
    ACOES_PATH,
    PROVENTOS_PATH,
    RENDA_FIXA_PATH,
    UPLOADS_DIR,
    extrair_mes_ano_nome,
    ler_relatorio_excel,
    salvar_tipo_parquet,
)
from modules.upload_pdf_avenue import (
    ACOES_PDF_PATH,
    DIVIDENDOS_PDF_PATH,
    extrair_mes_ano_pdf,
    processar_pdf_individual,
    salvar_acoes_pdf_parquet,
    salvar_dividendos_pdf_parquet,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def pdf_dest_dir() -> Path:
    # Requisito: salvar PDFs em C:\GIT\invest\Relatorios\Avenue
    # Usamos caminho relativo ao repo para não depender do cwd.
    return _repo_root() / "Relatorios" / "Avenue"


def excel_dest_dir() -> Path:
    # Requisito: manter o caminho já utilizado no projeto.
    return _repo_root() / UPLOADS_DIR


def _normalize_text(s: str) -> str:
    s = (s or "").lower().strip()
    for ch in ["_", "-", "."]:
        s = s.replace(ch, " ")
    repl = (
        ("ç", "c"),
        ("ã", "a"),
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("õ", "o"),
        ("ú", "u"),
    )
    for a, b in repl:
        s = s.replace(a, b)
    return s


def inferir_usuario_do_nome(nome_arquivo: str) -> Optional[str]:
    """Tenta inferir o usuário pelo nome do arquivo.

    Regra: se o nome do arquivo contém o nome (normalizado) de exatamente um usuário cadastrado,
    retorna esse usuário. Caso contrário, retorna None.
    """
    df_usuarios = carregar_usuarios()
    if df_usuarios.empty or "Nome" not in df_usuarios.columns:
        return None

    nome_norm = _normalize_text(nome_arquivo)
    candidatos: List[str] = []
    for usuario in sorted(df_usuarios["Nome"].dropna().unique().tolist()):
        u_norm = _normalize_text(str(usuario))
        if not u_norm:
            continue
        if u_norm in nome_norm:
            candidatos.append(str(usuario))

    if len(candidatos) == 1:
        return candidatos[0]
    return None


def inferir_mes_ano(nome_arquivo: str) -> Optional[str]:
    """Extrai MM/AAAA do nome do arquivo (PDF ou Excel)."""
    nome_low = (nome_arquivo or "").lower()
    if nome_low.endswith(".pdf"):
        # Avenue costuma vir como Stmt_YYYYMMDD; Apex pode variar.
        return extrair_mes_ano_pdf(nome_arquivo) or extrair_mes_ano_nome(nome_arquivo)
    if nome_low.endswith(".xlsx") or nome_low.endswith(".xls"):
        return extrair_mes_ano_nome(nome_arquivo)
    return None


@dataclass
class ResultadoArquivo:
    nome: str
    tipo: str  # 'pdf' | 'excel'
    destino: Optional[str]
    status_salvamento: str  # 'saved' | 'skipped_exists'
    usuario: Optional[str]
    mes_ano: Optional[str]
    linhas_acoes: int = 0
    linhas_rf: int = 0
    linhas_proventos: int = 0
    linhas_dividendos: int = 0
    erro: Optional[str] = None


def salvar_upload(
    uploaded_file,
    dest_dir: Path,
    overwrite: bool,
) -> Tuple[Optional[Path], str]:
    """Salva um arquivo do Streamlit no diretório destino.

    Retorna (caminho_destino ou None, status).
    status: 'saved' | 'skipped_exists'
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    nome = getattr(uploaded_file, "name", None) or "upload"
    destino = dest_dir / nome

    if destino.exists() and not overwrite:
        return None, "skipped_exists"

    # Escreve bytes do upload
    with open(destino, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return destino, "saved"


def processar_excel(caminho_excel: Path, usuario: str, mes_ano: str) -> Tuple[int, int, int]:
    df_acoes, df_rf, df_prov = ler_relatorio_excel(str(caminho_excel), usuario, mes_ano)

    total_a = total_rf = total_p = 0

    if not df_acoes.empty:
        salvar_tipo_parquet(
            df_acoes,
            ACOES_PATH,
            chaves_substituicao=["Mês/Ano", "Usuário"],
            dedup_subset=["Mês/Ano", "Usuário", "Produto"],
        )
        total_a = len(df_acoes)

    if not df_rf.empty:
        salvar_tipo_parquet(
            df_rf,
            RENDA_FIXA_PATH,
            chaves_substituicao=["Mês/Ano", "Usuário"],
            dedup_subset=["Mês/Ano", "Usuário", "Produto", "Código"],
        )
        total_rf = len(df_rf)

    if not df_prov.empty:
        salvar_tipo_parquet(
            df_prov,
            PROVENTOS_PATH,
            chaves_substituicao=["Mês/Ano", "Usuário"],
            dedup_subset=["Mês/Ano", "Usuário", "Produto", "Data de Pagamento", "Valor Líquido"],
        )
        total_p = len(df_prov)

    return total_a, total_rf, total_p


def processar_pdf(caminho_pdf: Path, usuario: str, mes_ano: Optional[str]) -> Tuple[int, int]:
    df_acoes_pdf, df_divid_pdf = processar_pdf_individual(str(caminho_pdf), usuario=usuario, mes_ano=mes_ano)

    total_a = total_d = 0
    if not df_acoes_pdf.empty:
        salvar_acoes_pdf_parquet(df_acoes_pdf, ACOES_PDF_PATH)
        total_a = len(df_acoes_pdf)

    if not df_divid_pdf.empty:
        salvar_dividendos_pdf_parquet(df_divid_pdf, DIVIDENDOS_PDF_PATH)
        total_d = len(df_divid_pdf)

    return total_a, total_d


def processar_uploads(uploaded_files: Sequence, overwrite: bool) -> List[ResultadoArquivo]:
    """Processa uma lista de uploads (PDF/Excel) com roteamento automático."""
    resultados: List[ResultadoArquivo] = []

    for f in uploaded_files:
        nome = getattr(f, "name", "upload")
        nome_low = nome.lower()

        if nome_low.endswith(".pdf"):
            tipo = "pdf"
            dest_dir = pdf_dest_dir()
        elif nome_low.endswith(".xlsx") or nome_low.endswith(".xls"):
            tipo = "excel"
            dest_dir = excel_dest_dir()
        else:
            resultados.append(
                ResultadoArquivo(
                    nome=nome,
                    tipo="desconhecido",
                    destino=None,
                    status_salvamento="skipped_exists",
                    usuario=None,
                    mes_ano=None,
                    erro="Tipo de arquivo não suportado (use PDF ou Excel).",
                )
            )
            continue

        usuario = inferir_usuario_do_nome(nome)
        mes_ano = inferir_mes_ano(nome)

        # Requisito: auto-detectar mês/ano e usuário conforme padrão atual.
        if not usuario:
            resultados.append(
                ResultadoArquivo(
                    nome=nome,
                    tipo=tipo,
                    destino=None,
                    status_salvamento="skipped_exists",
                    usuario=None,
                    mes_ano=mes_ano,
                    erro="Não foi possível identificar o usuário pelo nome do arquivo.",
                )
            )
            continue
        if not mes_ano:
            resultados.append(
                ResultadoArquivo(
                    nome=nome,
                    tipo=tipo,
                    destino=None,
                    status_salvamento="skipped_exists",
                    usuario=usuario,
                    mes_ano=None,
                    erro="Não foi possível identificar o mês/ano pelo nome do arquivo (esperado MM/AAAA).",
                )
            )
            continue

        caminho_salvo, status = salvar_upload(f, dest_dir=dest_dir, overwrite=overwrite)
        if status == "skipped_exists":
            resultados.append(
                ResultadoArquivo(
                    nome=nome,
                    tipo=tipo,
                    destino=str(dest_dir / nome),
                    status_salvamento=status,
                    usuario=usuario,
                    mes_ano=mes_ano,
                )
            )
            continue

        res = ResultadoArquivo(
            nome=nome,
            tipo=tipo,
            destino=str(caminho_salvo) if caminho_salvo else None,
            status_salvamento=status,
            usuario=usuario,
            mes_ano=mes_ano,
        )

        try:
            if tipo == "excel":
                a, rf, p = processar_excel(caminho_salvo, usuario=usuario, mes_ano=mes_ano)
                res.linhas_acoes = a
                res.linhas_rf = rf
                res.linhas_proventos = p
            else:
                a, d = processar_pdf(caminho_salvo, usuario=usuario, mes_ano=mes_ano)
                res.linhas_acoes = a
                res.linhas_dividendos = d
        except Exception as exc:
            res.erro = str(exc)

        resultados.append(res)

    return resultados
