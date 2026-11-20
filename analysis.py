"""USD/KZT және Brent деректерін уақыттық қатар әдісімен талдау."""
from __future__ import annotations

import glob
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import STL
from statsmodels.tsa.stattools import adfuller

START = pd.Timestamp("2006-11-01")
END = pd.Timestamp("2026-10-31")
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "output"


def fail(message: str) -> None:
    raise RuntimeError(message)


def load_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    xlsx = sorted(ROOT.glob("*.xlsx"))
    bis_files = sorted(ROOT.glob("bis_dp_search_export_*.csv"))
    brent_files = sorted(ROOT.glob("Europe_Brent_Spot_Price_FOB.csv"))
    if not xlsx or not bis_files or not brent_files:
        fail("Кіріс файлдары табылмады: XLSX, BIS CSV және Brent CSV қажет.")

    raw = pd.read_excel(xlsx[0], sheet_name="Sheet1")
    required = {"Date", "USD_quant", "USD"}
    if not required.issubset(raw.columns):
        fail(f"XLSX бағандары қате. Күтілгені: {sorted(required)}")
    raw["Date"] = pd.to_datetime(raw["Date"], dayfirst=True, errors="coerce")
    raw["USD"] = pd.to_numeric(raw["USD"].astype(str).str.replace(",", ".", regex=False), errors="coerce")
    daily = raw[["Date", "USD"]].rename(columns={"USD": "USD_KZT"}).dropna(subset=["Date", "USD_KZT"])
    q1, q3 = daily.USD_KZT.quantile([.25, .75])
    iqr_outliers = int(((daily.USD_KZT < q1 - 1.5 * (q3 - q1)) |
                        (daily.USD_KZT > q3 + 1.5 * (q3 - q1))).sum())
    print(f"XLSX тексеру: жолдар={len(raw)}, бос күндер={raw['Date'].isna().sum()}, "
          f"бос курс={raw['USD'].isna().sum()}, дубликат күндер={daily['Date'].duplicated().sum()}, "
          f"IQR выбросы={iqr_outliers}, курс диапазоны=[{daily.USD_KZT.min():.4f}, {daily.USD_KZT.max():.4f}]")
    daily = daily.drop_duplicates("Date").sort_values("Date")

    bis = pd.read_csv(bis_files[0], skiprows=11, header=None, names=["Date", "BIS_KZT"])
    bis["Date"] = pd.to_datetime(bis["Date"], errors="coerce")
    bis["BIS_KZT"] = pd.to_numeric(bis["BIS_KZT"], errors="coerce")
    bis = bis.dropna(subset=["Date", "BIS_KZT"]).sort_values("Date")
    print(f"BIS тексеру: жолдар={len(bis)}, бос мәндер={bis['BIS_KZT'].isna().sum()}, "
          f"дубликаттар={bis['Date'].duplicated().sum()}")

    brent = pd.read_csv(brent_files[0], skiprows=4)
    brent.columns = ["Month", "Brent_USD_bbl"]
    brent["Date"] = pd.to_datetime(brent["Month"], format="%b %Y", errors="coerce")
    brent["Brent_USD_bbl"] = pd.to_numeric(brent["Brent_USD_bbl"], errors="coerce")
    brent = brent.dropna(subset=["Date", "Brent_USD_bbl"]).sort_values("Date")
    print(f"Brent тексеру: жолдар={len(brent)}, бос мәндер={brent['Brent_USD_bbl'].isna().sum()}, "
          f"диапазон=[{brent.Date.min().date()}, {brent.Date.max().date()}]")
    return daily, bis[["Date", "BIS_KZT"]], brent[["Date", "Brent_USD_bbl"]]


def adf_line(series: pd.Series, label: str) -> None:
    result = adfuller(series.dropna(), autolag="AIC", result_object=False)
    print(f"ADF ({label}): statistic={result[0]:.4f}, p-value={result[1]:.6f} -> "
          f"{'стационарлы' if result[1] < .05 else 'стационарлы емес'}")


def main() -> None:
    OUT.mkdir(exist_ok=True)
    daily, bis, brent = load_inputs()
    daily = daily[(daily.Date >= START) & (daily.Date <= END)].copy()
    if daily.empty:
        fail("Талдау кезеңіне арналған күнделікті дерек жоқ.")
    daily.to_csv(OUT / "usd_kzt_daily.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8")

    d = daily.set_index("Date")["USD_KZT"].resample("ME").agg(["mean", "min", "max", "last"])
    d.columns = ["AvgRate", "MinRate", "MaxRate", "EndRate"]
    d.index.name = "Date"
    monthly = d.reset_index()
    monthly["Month"] = monthly.Date.dt.to_period("M").dt.to_timestamp()
    bis_m = bis.assign(Month=bis.Date.dt.to_period("M").dt.to_timestamp()).groupby("Month", as_index=False)["BIS_KZT"].last()
    brent_m = brent.assign(Month=brent.Date.dt.to_period("M").dt.to_timestamp())[["Month", "Brent_USD_bbl"]]
    monthly = monthly.merge(brent_m, on="Month", how="left").merge(bis_m, on="Month", how="left")
    # Бір баррельдің теңгедегі құны: Brent (USD/barrel) × USD/KZT.
    monthly["Brent_KZT_bbl"] = monthly["Brent_USD_bbl"] * monthly["EndRate"]
    monthly["Brent_MoM_Pct"] = monthly["Brent_USD_bbl"].pct_change() * 100
    monthly["Brent_KZT_MoM_Pct"] = monthly["Brent_KZT_bbl"].pct_change() * 100
    monthly["BIS_DiffPct"] = (monthly.EndRate - monthly.BIS_KZT) / monthly.BIS_KZT * 100
    monthly["MoM_Pct"] = monthly.EndRate.pct_change() * 100
    monthly["YoY_Pct"] = monthly.EndRate.pct_change(12) * 100
    monthly["LogReturn"] = np.log(monthly.EndRate / monthly.EndRate.shift(1))
    for window in (3, 6, 12):
        monthly[f"MA{window}"] = monthly.EndRate.rolling(window).mean()
    monthly["Volatility12"] = monthly["LogReturn"].rolling(12).std() * np.sqrt(12) * 100
    monthly["Year"] = monthly.Date.dt.year
    monthly["Quarter"] = "Q" + monthly.Date.dt.quarter.astype(str)
    monthly["MonthNum"] = monthly.Date.dt.month
    monthly.to_csv(OUT / "usd_kzt_monthly.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8")
    monthly[["Date", "Brent_USD_bbl", "EndRate", "Brent_KZT_bbl",
             "Brent_MoM_Pct", "Brent_KZT_MoM_Pct"]].to_csv(
        OUT / "brent_kzt_linked.csv", index=False, date_format="%Y-%m-%d", encoding="utf-8")
    joint = monthly[["Date", "EndRate", "Brent_USD_bbl", "Brent_KZT_bbl",
                     "MoM_Pct", "Brent_MoM_Pct", "Brent_KZT_MoM_Pct"]].copy()
    joint = joint.rename(columns={"EndRate": "USD_KZT", "MoM_Pct": "USD_KZT_MoM_Pct"})
    joint["USD_KZT_Vol12"] = joint["USD_KZT_MoM_Pct"].rolling(12).std() * np.sqrt(12)
    joint["Brent_USD_Vol12"] = joint["Brent_MoM_Pct"].rolling(12).std() * np.sqrt(12)
    joint["Brent_KZT_Vol12"] = joint["Brent_KZT_MoM_Pct"].rolling(12).std() * np.sqrt(12)
    joint["StressCount"] = (
        (joint["USD_KZT_MoM_Pct"].abs() >= joint["USD_KZT_MoM_Pct"].abs().quantile(.95)).astype(int)
        + (joint["Brent_MoM_Pct"].abs() >= joint["Brent_MoM_Pct"].abs().quantile(.95)).astype(int)
        + (joint["Brent_KZT_MoM_Pct"].abs() >= joint["Brent_KZT_MoM_Pct"].abs().quantile(.95)).astype(int)
    )
    joint["JointRiskLevel"] = np.select(
        [joint["StressCount"] >= 2, joint["StressCount"] == 1],
        ["Жоғары", "Орташа"], default="Төмен")
    joint.loc[joint[["USD_KZT", "Brent_USD_bbl", "Brent_KZT_bbl"]].isna().any(axis=1),
              "JointRiskLevel"] = "Дерек жоқ"
    joint.to_csv(OUT / "joint_currency_oil_risk.csv", index=False,
                 date_format="%Y-%m-%d", encoding="utf-8")
    print(f"Өлшемдер: daily={daily.shape}, monthly={monthly.shape}; Brent merge бос={monthly.Brent_USD_bbl.isna().sum()}")

    adf_line(monthly.EndRate, "деңгей")
    adf_line(monthly.LogReturn, "лог-доходность")
    stl = STL(monthly.set_index("Date")["EndRate"], period=12, robust=True).fit()
    pd.DataFrame({"Date": monthly.Date, "Trend": stl.trend.values, "Seasonal": stl.seasonal.values,
                  "Residual": stl.resid.values}).to_csv(OUT / "decomposition.csv", index=False, date_format="%Y-%m-%d")

    series = monthly.set_index("Date")["EndRate"].asfreq("ME").dropna()
    validation_n = min(12, max(6, len(series) // 10))
    train, actual = series.iloc[:-validation_n], series.iloc[-validation_n:]
    model = ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal="add",
                                  seasonal_periods=12, initialization_method="estimated").fit(optimized=True)
    predicted = model.forecast(validation_n)
    naive = pd.Series(train.iloc[-1], index=actual.index)
    mae = float(np.mean(np.abs(actual - predicted)))
    rmse = float(np.sqrt(np.mean((actual - predicted) ** 2)))
    mape = float(np.mean(np.abs((actual - predicted) / actual)) * 100)
    naive_mape = float(np.mean(np.abs((actual - naive) / actual)) * 100)
    pd.DataFrame({"Date": actual.index, "Actual": actual.values, "Predicted": predicted.values}).to_csv(
        OUT / "forecast_validation.csv", index=False, date_format="%Y-%m-%d")
    print(f"Болжам метрикалары: MAE={mae:.4f}, RMSE={rmse:.4f}, MAPE={mape:.2f}%, Naive MAPE={naive_mape:.2f}%")

    final_model = ExponentialSmoothing(series, trend="add", damped_trend=True, seasonal="add",
                                       seasonal_periods=12, initialization_method="estimated").fit(optimized=True)
    future_idx = pd.date_range(series.index[-1] + pd.offsets.MonthEnd(1), periods=12, freq="ME")
    fc = final_model.forecast(12)
    # 95% интервалы: валидация қалдықтарының эмпирикалық стандартты ауытқуы.
    resid_std = float(np.std(train - model.fittedvalues, ddof=1))
    horizon = np.arange(1, 13)
    margin = 1.96 * resid_std * np.sqrt(horizon)
    forecast = pd.DataFrame({"Date": future_idx, "Forecast": fc.values,
                             "Lower95": fc.values - margin, "Upper95": fc.values + margin})
    forecast.to_csv(OUT / "forecast.csv", index=False, date_format="%Y-%m-%d")
    scenarios = pd.concat([
        forecast[["Date", "Forecast"]].rename(columns={"Forecast": "USD_KZT"}).assign(Scenario="Базалық"),
        forecast[["Date", "Lower95"]].rename(columns={"Lower95": "USD_KZT"}).assign(Scenario="Оптимистік (теңге күштірек)"),
        forecast[["Date", "Upper95"]].rename(columns={"Upper95": "USD_KZT"}).assign(Scenario="Пессимистік (теңге әлсізірек)"),
    ], ignore_index=True)[["Date", "Scenario", "USD_KZT"]]
    scenarios.to_csv(OUT / "scenarios.csv", index=False, date_format="%Y-%m-%d")

    monthly["DrawdownPct"] = (monthly.EndRate / monthly.EndRate.cummax() - 1) * 100
    risk = monthly.groupby("Year").agg(AvgRate=("EndRate", "mean"), Volatility=("LogReturn", lambda x: x.std() * np.sqrt(12) * 100),
                                       MaxDrawdownPct=("DrawdownPct", "min"), MaxMonthlyChangePct=("MoM_Pct", lambda x: x.abs().max())).reset_index()
    q1, q2 = risk.Volatility.quantile([.33, .67])
    risk["RiskLevel"] = np.select([risk.Volatility <= q1, risk.Volatility <= q2], ["Төмен", "Орташа"], default="Жоғары")
    risk.to_csv(OUT / "risk_yearly.csv", index=False, encoding="utf-8")
    changes = monthly.dropna(subset=["MoM_Pct"]).copy()
    var = pd.DataFrame({"Confidence": ["95%", "99%"],
                        "VaR_Pct": [-changes.MoM_Pct.quantile(.05), -changes.MoM_Pct.quantile(.01)]})
    var["Loss_KZT_per_1m_USD"] = var.VaR_Pct / 100 * 1_000_000 * monthly.EndRate.iloc[-1]
    var.to_csv(OUT / "risk_var.csv", index=False)
    corr = monthly[["Date", "EndRate", "Brent_USD_bbl", "Brent_KZT_bbl",
                    "MoM_Pct", "Brent_MoM_Pct", "Brent_KZT_MoM_Pct"]].dropna()
    corr["Correlation24M_USD"] = corr.EndRate.rolling(24, min_periods=12).corr(corr.Brent_USD_bbl)
    corr["Correlation24M_BrentKZT"] = corr.EndRate.rolling(24, min_periods=12).corr(corr.Brent_KZT_bbl)
    corr["ChangeCorrelation24M_USD"] = corr.MoM_Pct.rolling(24, min_periods=12).corr(corr.Brent_MoM_Pct)
    corr["ChangeCorrelation24M_BrentKZT"] = corr.MoM_Pct.rolling(24, min_periods=12).corr(corr.Brent_KZT_MoM_Pct)
    corr.to_csv(OUT / "corr_brent.csv", index=False, date_format="%Y-%m-%d")
    shocks = changes.assign(AbsChange=changes.MoM_Pct.abs()).nlargest(10, "AbsChange")
    shocks[["Date", "EndRate", "MoM_Pct", "AbsChange"]].rename(columns={"MoM_Pct": "ChangePct"}).to_csv(OUT / "shocks.csv", index=False, date_format="%Y-%m-%d")
    print(f"VaR: 95%={var.iloc[0].VaR_Pct:.2f}% ({var.iloc[0].Loss_KZT_per_1m_USD:,.0f} тг), "
          f"99%={var.iloc[1].VaR_Pct:.2f}%; Brent USD корреляция={corr.EndRate.corr(corr.Brent_USD_bbl):.4f}; "
          f"баррель KZT корреляция={corr.EndRate.corr(corr.Brent_KZT_bbl):.4f}; "
          f"өзгерістер корреляциясы={corr.MoM_Pct.corr(corr.Brent_MoM_Pct):.4f}")

    # Power BI-ге дейін нәтижені көзбен тексеруге арналған төрт панель.
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    monthly.plot(x="Date", y="EndRate", ax=axes[0, 0], title="Курс USD/KZT")
    forecast.plot(x="Date", y=["Forecast", "Lower95", "Upper95"], ax=axes[0, 0], style=["r--", "r:", "r:"])
    monthly.plot(x="Date", y=["MA3", "MA6", "MA12"], ax=axes[0, 1], title="Жылжымалы орташа")
    risk.plot.bar(x="Year", y="Volatility", ax=axes[1, 0], title="Жылдық волатильдік", legend=False)
    ax_oil = axes[1, 1]
    oil = monthly.dropna(subset=["Brent_USD_bbl", "Brent_KZT_bbl"]).copy()
    oil.plot(x="Date", y="Brent_USD_bbl", ax=ax_oil, color="#555555", title="Мұнай бағасы және курс")
    ax_oil.set_ylabel("Brent, USD/баррель")
    ax_oil_twin = ax_oil.twinx()
    oil.plot(x="Date", y="Brent_KZT_bbl", ax=ax_oil_twin, color="#D62728", legend=True)
    ax_oil_twin.set_ylabel("Brent, теңге/баррель")
    fig.tight_layout(); fig.savefig(OUT / "report_preview.png", dpi=150); plt.close(fig)
    print("Жасалған файлдар:")
    for path in sorted(OUT.iterdir()):
        print(f"  {path.name} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ҚАТЕ: {exc}", file=sys.stderr)
        raise
