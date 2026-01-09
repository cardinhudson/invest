import pandas as pd

from modules.historico_acoes_manuais import expand_lotes_para_posicao_mensal


def main():
    # Cenário: compra em 01/2024, venda parcial em 03/2024, nova compra em 06/2024
    df = pd.DataFrame(
        [
            {
                "Usuário": "U1",
                "Ticker": "TEST",
                "Ticker_YF": "TEST",
                "Moeda": "BRL",
                "Mês Compra": "01/2024",
                "Quantidade Compra": 10,
                "Mês Venda": "03/2024",
                "Quantidade Venda": 4,
            },
            {
                "Usuário": "U1",
                "Ticker": "TEST",
                "Ticker_YF": "TEST",
                "Moeda": "BRL",
                "Mês Compra": "06/2024",
                "Quantidade Compra": 5,
                "Mês Venda": "",
                "Quantidade Venda": 0,
            },
        ]
    )

    ate = pd.Period("2026-01", freq="M")
    pos = expand_lotes_para_posicao_mensal(df, ate_periodo=ate)

    assert not pos.empty

    # checagens de meses/quantidade
    def q(mmyyyy: str) -> float:
        p = pd.Period(f"{mmyyyy[3:]}-{mmyyyy[:2]}", freq="M")
        s = pos[(pos["Periodo"] == p) & (pos["Ticker"] == "TEST")]["Quantidade"]
        return float(s.iloc[0]) if not s.empty else 0.0

    assert q("01/2024") == 10
    assert q("02/2024") == 10
    assert q("03/2024") == 6  # venda parcial no mês
    assert q("04/2024") == 6
    assert q("06/2024") == 11  # nova compra soma
    assert q("01/2026") == 11

    # Agora valida Valor = Quantidade * Preço (simulando fechamento mensal)
    # Preços artificiais: preço = 2 * número do mês (só para checar cálculo)
    preços = (
        pd.DataFrame({"Periodo": pos["Periodo"].unique()})
        .assign(Preço=lambda d: d["Periodo"].astype(str).str[-2:].astype(int) * 2.0)
    )
    m = pos.merge(preços, on="Periodo", how="left")
    m["Valor"] = m["Quantidade"] * m["Preço"]

    # valida um ponto
    # 03/2024 mês=3 => preço=6; qtd=6 => valor=36
    p_032024 = pd.Period("2024-03", freq="M")
    row = m[m["Periodo"] == p_032024].iloc[0]
    assert float(row["Valor"]) == 36.0

    print("OK: posição mensal e valor mês a mês (teste sintético)")


if __name__ == "__main__":
    main()
