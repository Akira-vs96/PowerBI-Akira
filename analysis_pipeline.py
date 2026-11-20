"""Подготовка данных и воспроизводимый анализ валютного риска USD/KZT.

Запуск:
    python analysis_pipeline.py

Скрипт читает исходники из текущей папки и создаёт каталоги data/, results/
и figures/. Все таблицы результатов предназначены для импорта в Power BI.
"""

from pathlib import Path
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (accuracy_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error,
                             precision_score, r2_score, recall_score,
                             silhouette_score)
from sklearn.model_selection import TimeSeriesSplit
from sklearn.naive_bayes import GaussianNB
from sklearn.neighbors import KNeighborsClassifier
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from mlxtend.frequent_patterns import apriori, association_rules

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
FIGURES = ROOT / "figures"
DATA.mkdir(exist_ok=True)
RESULTS.mkdir(exist_ok=True)
FIGURES.mkdir(exist_ok=True)


def save_result(frame: pd.DataFrame, name: str) -> None:
    """Сохраняет CSV и Excel-копию результата."""
    frame.to_csv(RESULTS / f"{name}.csv", index=False, encoding="utf-8-sig")
    frame.to_excel(RESULTS / f"{name}.xlsx", index=False)


def read_bis() -> pd.DataFrame:
    path = ROOT / "bis_dp_search_export_20261030-113354.csv"
    # В BIS-заголовке TIME_PERIOD занимает отдельную строку без второго имени.
    raw = pd.read_csv(path, skiprows=11, header=None, names=["date", "usd_kzt"])
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["usd_kzt"] = pd.to_numeric(raw["usd_kzt"], errors="coerce")
    return raw[["date", "usd_kzt"]].dropna().drop_duplicates("date")


def read_brent() -> pd.DataFrame:
    path = ROOT / "RBRTEd.xls"
    raw = pd.read_excel(path, sheet_name="Data 1", skiprows=2)
    raw = raw.rename(columns={raw.columns[0]: "date", raw.columns[1]: "brent_usd"})
    raw["date"] = pd.to_datetime(raw["date"], errors="coerce")
    raw["brent_usd"] = pd.to_numeric(raw["brent_usd"], errors="coerce")
    raw = raw[["date", "brent_usd"]].dropna().drop_duplicates("date")
    return raw.groupby(raw["date"].dt.to_period("M"))["brent_usd"].mean().rename("brent_usd").to_frame()


def read_cpi() -> tuple[pd.DataFrame, pd.DataFrame]:
    region_path = ROOT / "Index_of_prices_and_tariffs_for_consumer_goods_and_services_by_region.xlsx"
    region = pd.read_excel(region_path, sheet_name="CPI", header=None)
    years = pd.to_numeric(region.iloc[2, 1:], errors="coerce")
    # В таблице первая строка Республики Казахстан находится после служебных строк.
    kz_rows = region.index[region.apply(
        lambda row: row.astype(str).str.strip().eq("Republic of Kazakhstan").any(), axis=1
    )].tolist()
    if not kz_rows:
        raise ValueError("Не найдена строка Republic of Kazakhstan в CPI.")
    kz = pd.to_numeric(region.iloc[kz_rows[0], 1:], errors="coerce")
    annual = pd.DataFrame({"year": years, "cpi_total": kz}).dropna()

    groups_path = ROOT / "Price_index_for_the_main_groups_of_consumer_goods_and_services_.xlsx"
    groups = pd.read_excel(groups_path, sheet_name=0, header=None)
    group_years = pd.to_numeric(groups.iloc[2, 1:], errors="coerce")
    rows = {}
    labels = {
        "Goods and services": "cpi_goods_services",
        "Food products": "cpi_food",
        "Non-food products": "cpi_nonfood",
        "Paid services": "cpi_services",
    }
    for row_index, label in enumerate(groups.iloc[:, 0].astype(str)):
        clean_label = str(label).strip()
        if clean_label in labels:
            rows[labels[clean_label]] = pd.to_numeric(groups.iloc[row_index, 1:], errors="coerce")
    group_frame = pd.DataFrame({"year": group_years, **rows}).dropna(subset=["year"])
    return annual, group_frame


def read_official_current() -> pd.DataFrame:
    path = ROOT / "Официальные (рыночные) курсы валют.xlsx"
    df = pd.read_excel(path)
    df.columns = ["date", "usd_quant", "usd_kzt"]
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df["usd_kzt"] = pd.to_numeric(df["usd_kzt"], errors="coerce")
    return df.dropna(subset=["date", "usd_kzt"]).drop_duplicates("date")


def prepare_dataset() -> pd.DataFrame:
    """Объединяет месячный курс, Brent и годовые CPI без искусственного заполнения."""
    fx = read_bis()
    brent = read_brent().reset_index()
    brent["date"] = brent["date"].dt.to_timestamp("M")
    annual, groups = read_cpi()
    cpi = annual.merge(groups, on="year", how="outer")

    monthly = fx.merge(brent, on="date", how="left")
    monthly["year"] = monthly["date"].dt.year
    monthly = monthly.merge(cpi, on="year", how="left")
    monthly = monthly.sort_values("date").drop_duplicates("date")
    monthly["usd_kzt_mom_pct"] = monthly["usd_kzt"].pct_change() * 100
    monthly["usd_kzt_yoy_pct"] = monthly["usd_kzt"].pct_change(12) * 100
    monthly["volatility_12m"] = monthly["usd_kzt_mom_pct"].rolling(12, min_periods=6).std()
    monthly["brent_lag1"] = monthly["brent_usd"].shift(1)
    monthly["brent_lag3"] = monthly["brent_usd"].shift(3)
    monthly["cpi_total_lag1"] = monthly["cpi_total"].shift(1)
    monthly["devaluation_event"] = (monthly["usd_kzt_mom_pct"].abs() >= 5).astype("Int64")
    monthly["risk_high"] = (monthly["volatility_12m"] >= monthly["volatility_12m"].quantile(.75)).astype("Int64")
    monthly["period"] = monthly["date"].dt.to_period("M").astype(str)
    monthly.to_csv(DATA / "cleaned_monthly_dataset.csv", index=False, encoding="utf-8-sig")
    monthly.to_excel(DATA / "cleaned_monthly_dataset.xlsx", index=False)
    current = read_official_current()
    current.to_csv(DATA / "official_current_usd_kzt.csv", index=False, encoding="utf-8-sig")
    current.to_excel(DATA / "official_current_usd_kzt.xlsx", index=False)
    return monthly


def model_frame(df: pd.DataFrame, columns: list[str], target: str) -> pd.DataFrame:
    return df[columns + [target]].dropna().reset_index(drop=True)


def regression(df: pd.DataFrame) -> None:
    d = model_frame(df, ["brent_usd", "cpi_total", "cpi_food", "cpi_nonfood"], "usd_kzt")
    split = int(len(d) * .8)
    x, y = d.drop(columns="usd_kzt"), d["usd_kzt"]
    model = LinearRegression().fit(x.iloc[:split], y.iloc[:split])
    pred = model.predict(x.iloc[split:])
    save_result(pd.DataFrame({
        "date": df.loc[d.index[split:], "date"].values,
        "actual_usd_kzt": y.iloc[split:].values,
        "predicted_usd_kzt": pred,
        "residual": y.iloc[split:].values - pred,
    }), "method_01_regression_predictions")
    metrics = pd.DataFrame([{
        "model": "Python LinearRegression",
        "r2": r2_score(y.iloc[split:], pred),
        "mae": mean_absolute_error(y.iloc[split:], pred),
        "rmse": np.sqrt(mean_squared_error(y.iloc[split:], pred)),
        "n_train": split, "n_test": len(y) - split,
    }, {
        "model": "Excel LINEST equivalent (OLS)",
        "r2": r2_score(y.iloc[split:], pred),
        "mae": mean_absolute_error(y.iloc[split:], pred),
        "rmse": np.sqrt(mean_squared_error(y.iloc[split:], pred)),
        "n_train": split, "n_test": len(y) - split,
    }])
    save_result(metrics, "method_01_regression_metrics")
    save_result(pd.DataFrame({"feature": x.columns, "coefficient": model.coef_}), "method_01_regression_coefficients")


def clustering(df: pd.DataFrame) -> None:
    cols = ["usd_kzt_mom_pct", "volatility_12m", "brent_usd", "cpi_total"]
    d = df[["date"] + cols].dropna().copy()
    z = StandardScaler().fit_transform(d[cols])
    model = KMeans(n_clusters=4, random_state=42, n_init=20).fit(z)
    d["cluster"] = model.labels_
    d["cluster_name"] = d.groupby("cluster")["usd_kzt_mom_pct"].transform("mean").rank(method="dense").map(
        {1: "стабильный", 2: "восстановление", 3: "напряженный", 4: "девальвационный"}
    )
    save_result(d, "method_02_clustering_periods")
    save_result(pd.DataFrame([{"silhouette_score": silhouette_score(z, model.labels_), "n_clusters": 4}]),
                "method_02_clustering_metrics")
    comparison = []
    for k in (2, 3, 4, 5):
        labels = KMeans(n_clusters=k, random_state=42, n_init=20).fit_predict(z)
        comparison.append({"n_clusters": k, "silhouette_score": silhouette_score(z, labels)})
    save_result(pd.DataFrame(comparison), "method_02_clustering_comparison")


def classification(df: pd.DataFrame) -> None:
    # Волатильность используется для формирования метки, поэтому не включаем
    # её напрямую в признаки и избегаем утечки целевой переменной.
    cols = ["usd_kzt_mom_pct", "brent_usd", "cpi_total"]
    d = df[["date"] + cols + ["risk_high"]].dropna().copy()
    split = int(len(d) * .8)
    x = d[cols]
    y = d["risk_high"].astype(int)
    model = LinearRegression()  # заменяется ниже на логистическую модель без лишней зависимости
    from sklearn.linear_model import LogisticRegression
    model = LogisticRegression(max_iter=2000).fit(x.iloc[:split], y.iloc[:split])
    pred = model.predict(x.iloc[split:])
    metrics = pd.DataFrame([{
        "accuracy": accuracy_score(y.iloc[split:], pred),
        "precision": precision_score(y.iloc[split:], pred, zero_division=0),
        "recall": recall_score(y.iloc[split:], pred, zero_division=0),
        "f1": f1_score(y.iloc[split:], pred, zero_division=0),
    }])
    save_result(metrics, "method_03_classification_metrics")
    tn, fp, fn, tp = confusion_matrix(y.iloc[split:], pred, labels=[0, 1]).ravel()
    save_result(pd.DataFrame({"actual": [0, 0, 1, 1], "predicted": [0, 1, 0, 1],
                              "count": [tn, fp, fn, tp]}), "method_03_classification_confusion_matrix")
    save_result(pd.DataFrame({"date": d.iloc[split:]["date"], "actual_risk": y.iloc[split:].values,
                              "predicted_risk": pred}), "method_03_classification_predictions")


def association(df: pd.DataFrame) -> None:
    d = df[["period", "usd_kzt_mom_pct", "brent_usd", "cpi_total"]].copy()
    d["fx_jump"] = d["usd_kzt_mom_pct"].abs() >= d["usd_kzt_mom_pct"].abs().quantile(.8)
    d["oil_jump"] = d["brent_usd"].pct_change().abs() >= d["brent_usd"].pct_change().abs().quantile(.8)
    d["inflation_high"] = d["cpi_total"] >= d["cpi_total"].quantile(.8)
    basket = d[["fx_jump", "oil_jump", "inflation_high"]].fillna(False)
    freq = apriori(basket, min_support=.01, use_colnames=True)
    rules = association_rules(freq, metric="confidence", min_threshold=.2)
    rules = rules.sort_values(["lift", "confidence"], ascending=False).head(20)
    save_result(rules, "method_04_association_rules")


def timeseries(df: pd.DataFrame) -> None:
    s = df.set_index("date")["usd_kzt"].dropna().asfreq("ME").ffill()
    horizon = 12
    model = ExponentialSmoothing(s, trend="add", damped_trend=True, initialization_method="estimated").fit()
    future = model.forecast(horizon)
    out = pd.DataFrame({"date": future.index, "forecast_usd_kzt": future.values,
                        "method": "Holt damped trend"})
    save_result(out, "method_05_time_series_forecast")
    backtest_rows = []
    for test_size in (6, 12):
        train, test = s.iloc[:-test_size], s.iloc[-test_size:]
        fitted = ExponentialSmoothing(
            train, trend="add", damped_trend=True,
            initialization_method="estimated"
        ).fit()
        forecast = fitted.forecast(test_size)
        backtest_rows.append({
            "test_months": test_size,
            "mae": mean_absolute_error(test, forecast),
            "rmse": np.sqrt(mean_squared_error(test, forecast)),
        })
    save_result(pd.DataFrame(backtest_rows), "method_05_time_series_backtest")


def pca(df: pd.DataFrame) -> None:
    cols = ["usd_kzt", "brent_usd", "cpi_total", "cpi_food", "cpi_nonfood", "cpi_services"]
    d = df[["date"] + cols].dropna()
    z = StandardScaler().fit_transform(d[cols])
    pca_model = PCA().fit(z)
    scores = pca_model.transform(z)
    loadings = pd.DataFrame(pca_model.components_.T, index=cols,
                            columns=[f"PC{i+1}" for i in range(len(cols))]).reset_index(names="feature")
    variance = pd.DataFrame({"component": [f"PC{i+1}" for i in range(len(cols))],
                             "explained_variance_ratio": pca_model.explained_variance_ratio_})
    save_result(loadings, "method_06_pca_loadings")
    save_result(variance, "method_06_pca_variance")
    save_result(pd.DataFrame(scores[:, :3], columns=["PC1", "PC2", "PC3"]).assign(date=d["date"].values),
                "method_06_pca_scores")


def anomaly(df: pd.DataFrame) -> None:
    d = df[["date", "usd_kzt_mom_pct", "volatility_12m"]].dropna().copy()
    z = (d["usd_kzt_mom_pct"] - d["usd_kzt_mom_pct"].mean()) / d["usd_kzt_mom_pct"].std()
    q1, q3 = d["usd_kzt_mom_pct"].quantile([.25, .75])
    iqr_flag = (d["usd_kzt_mom_pct"] < q1 - 1.5 * (q3-q1)) | (d["usd_kzt_mom_pct"] > q3 + 1.5 * (q3-q1))
    iso = IsolationForest(contamination=.05, random_state=42).fit_predict(d[["usd_kzt_mom_pct", "volatility_12m"]])
    d["zscore_anomaly"] = z.abs() > 3
    d["iqr_anomaly"] = iqr_flag
    d["isolation_forest_anomaly"] = iso == -1
    save_result(d, "method_07_anomaly_detection")
    save_result(pd.DataFrame({"method": ["Z-score", "IQR", "Isolation Forest"],
                              "anomaly_count": [d.zscore_anomaly.sum(), d.iqr_anomaly.sum(),
                                                d.isolation_forest_anomaly.sum()]}),
                "method_07_anomaly_metrics")


def supervised_models(df: pd.DataFrame) -> None:
    cols = ["brent_usd", "cpi_total", "usd_kzt_mom_pct"]
    d = df[["date"] + cols + ["risk_high"]].dropna().reset_index(drop=True)
    split = int(len(d) * .8)
    x_train, x_test = d[cols].iloc[:split], d[cols].iloc[split:]
    y_train, y_test = d["risk_high"].astype(int).iloc[:split], d["risk_high"].astype(int).iloc[split:]
    scaler = StandardScaler().fit(x_train)
    results = []
    model_outputs = {}
    for name, model in [
        ("MLP", MLPClassifier(hidden_layer_sizes=(32, 16), max_iter=2000, random_state=42, early_stopping=True)),
        ("Naive Bayes", GaussianNB()),
        ("kNN k=3", KNeighborsClassifier(n_neighbors=3)),
        ("kNN k=5", KNeighborsClassifier(n_neighbors=5)),
        ("kNN k=7", KNeighborsClassifier(n_neighbors=7)),
    ]:
        model.fit(scaler.transform(x_train), y_train)
        pred = model.predict(scaler.transform(x_test))
        results.append({"model": name, "accuracy": accuracy_score(y_test, pred),
                        "precision": precision_score(y_test, pred, zero_division=0),
                        "recall": recall_score(y_test, pred, zero_division=0),
                        "f1": f1_score(y_test, pred, zero_division=0)})
        model_outputs[name] = results[-1]
    save_result(pd.DataFrame(results), "method_08_09_10_supervised_metrics")
    save_result(pd.DataFrame([model_outputs["MLP"]]), "method_08_neural_network_metrics")
    save_result(pd.DataFrame([model_outputs["Naive Bayes"]]), "method_09_naive_bayes_metrics")
    save_result(pd.DataFrame([model_outputs["kNN k=3"], model_outputs["kNN k=5"],
                              model_outputs["kNN k=7"]]), "method_10_knn_metrics")


def excel_calculations(df: pd.DataFrame) -> None:
    """Создаёт проверяемый Excel-лист с формулами, требуемыми методичкой."""
    sample = df[["date", "usd_kzt", "brent_usd", "cpi_total",
                 "usd_kzt_mom_pct", "volatility_12m", "risk_high"]].copy()
    path = DATA / "excel_calculations.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        sample.to_excel(writer, sheet_name="Monthly_Data", index=False)
        ws = writer.book.create_sheet("Excel_Calculations")
        ws.append(["Показатель", "Формула Excel", "Результат"])
        formulas = [
            ("Средний курс", "=AVERAGE(Monthly_Data!B:B)", "=AVERAGE(Monthly_Data!B:B)"),
            ("Минимальный курс", "=MIN(Monthly_Data!B:B)", "=MIN(Monthly_Data!B:B)"),
            ("Максимальный курс", "=MAX(Monthly_Data!B:B)", "=MAX(Monthly_Data!B:B)"),
            ("Высокий риск", '=COUNTIF(Monthly_Data!G:G,1)', '=COUNTIF(Monthly_Data!G:G,1)'),
            ("Волатильность", "=STDEV.S(Monthly_Data!E:E)", "=STDEV.S(Monthly_Data!E:E)"),
            ("Корреляция Brent и курса", "=CORREL(Monthly_Data!B:B,Monthly_Data!C:C)",
             "=CORREL(Monthly_Data!B:B,Monthly_Data!C:C)"),
            ("Наклон LINEST", "=SLOPE(Monthly_Data!B:B,Monthly_Data!C:C)",
             "=SLOPE(Monthly_Data!B:B,Monthly_Data!C:C)"),
            ("Свободный член", "=INTERCEPT(Monthly_Data!B:B,Monthly_Data!C:C)",
             "=INTERCEPT(Monthly_Data!B:B,Monthly_Data!C:C)"),
            ("Прогноз FORECAST.LINEAR", "=FORECAST.LINEAR(395,Monthly_Data!B:B,ROW(Monthly_Data!B:B))",
             "=FORECAST.LINEAR(395,Monthly_Data!B:B,ROW(Monthly_Data!B:B))"),
            ("Квартиль курса", "=QUARTILE.INC(Monthly_Data!B:B,3)",
             "=QUARTILE.INC(Monthly_Data!B:B,3)"),
        ]
        for row, values in enumerate(formulas, start=1):
            ws.append(list(values))
        ws.column_dimensions["A"].width = 28
        ws.column_dimensions["B"].width = 62
        ws.column_dimensions["C"].width = 62


def main() -> None:
    df = prepare_dataset()
    regression(df)
    clustering(df)
    classification(df)
    association(df)
    timeseries(df)
    pca(df)
    anomaly(df)
    supervised_models(df)
    excel_calculations(df)
    print(f"Done: {len(df)} monthly observations; results: {RESULTS}")


if __name__ == "__main__":
    main()
