from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "APP.py"


def must_contain(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"NÃO ENCONTRADO: {needle!r}")


def main() -> None:
    text = APP.read_text(encoding="utf-8")

    # 1) Média móvel no gráfico Valor Recebido
    must_contain(text, "Média Móvel")
    must_contain(text, "rolling(")
    must_contain(text, "go.Scatter")

    # 2) Top 10 em Consolidação (subtab investimento)
    must_contain(text, "# Bloco Top 10 Maiores Altas")
    must_contain(text, "cons_top10_altas")

    # 3) Distribuição por Fonte no Dividendos BR
    must_contain(text, "div_br_pie_fonte")
    must_contain(text, "Distribuição por Fonte")
    must_contain(text, "px.colors.sequential.Blues[::-1]")

    # 4) Top pagadores mensal azul (BR e Consolidados)
    must_contain(text, "tipo_periodo == \"Mensal\"")
    must_contain(text, "px.colors.sequential.Blues[::-1] if tipo_periodo == \"Mensal\"")

    print("OK: padrões de modificações encontrados no APP.py")


if __name__ == "__main__":
    main()
