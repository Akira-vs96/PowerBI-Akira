# Инструкция по завершению курсового проекта

Тема: **«Доллар және теңге бағамының өзгерісін талдау және валюталық тәуекелдерді бағалау»**.

## 1. Что уже сделано

| Требование | Статус | Подтверждение |
|---|---|---|
| Собраны BIS USD/KZT, Brent, CPI и официальный курс НБРК | Сделано | Исходные файлы в папке проекта |
| Месячная агрегация USD/KZT | Сделано | `data/cleaned_monthly_dataset.xlsx` |
| Месячная агрегация Brent | Сделано | Поле `brent_usd` |
| Merge курса, нефти и CPI | Сделано | Основной датасет объединяет USD/KZT, Brent и общий/групповой CPI; для ранних лет CPI остаётся пропущенным по источнику |
| MoM и YoY изменение курса | Сделано | `usd_kzt_mom_pct`, `usd_kzt_yoy_pct` |
| Скользящая волатильность | Сделано | `volatility_12m` |
| Девальвационные события | Сделано | `devaluation_event`, порог 5% за месяц |
| Лаги нефти и инфляции | Сделано | `brent_lag1`, `brent_lag3`, `cpi_total_lag1` |
| Regression | Сделано | Метрики, коэффициенты и фактические/прогнозные значения выгружаются; отрицательный тестовый R² интерпретируется честно |
| K-Means Clustering | Сделано | 4 режима, Silhouette Score и сравнение k=2,3,4,5 выгружаются |
| Classification | Сделано | Logistic Regression, Accuracy/Precision/Recall/F1 и confusion matrix |
| Association Rules | Сделано | После снижения порогов выгружается 9 правил с support/confidence/lift; правила трактуются как совместные события, не причинность |
| Time Series | Сделано | Python-прогноз на 12 месяцев и backtesting на 6/12 месяцев выгружаются; Excel-формулы добавлены в `data/excel_calculations.xlsx` |
| PCA | Сделано | Стандартизация, компоненты, loadings, explained variance и scores |
| Anomaly Detection | Сделано | Z-score, IQR и Isolation Forest |
| Neural Network | Сделано частично | MLP и метрики есть; слабый Recall требует описания ограничений и не позволяет использовать модель как единственный сигнал |
| Naive Bayes | Сделано | GaussianNB и метрики есть |
| k-NN | Сделано | Сравнение k=3, 5, 7 есть |
| Импорт результатов в Power BI | Сделано частично | Основная таблица, CPI и визуал USD/KZT+Brent есть; таблицы ML-результатов ещё нужно загрузить в PBIP |
| DAX measures | Сделано | 7 KPI measures добавлены в `CleanedMonthlyDataset.tmdl`; после Apply external changes нужно проверить Fields |
| Визуальный дашборд Power BI | Сделано частично | Page 1 содержит рабочий график USD/KZT+Brent; полноценные 7 страниц и KPI-карточки ещё не собраны |
| Сценарийный анализ | Не сделано | Нужно добавить what-if parameter или отдельную страницу сценариев |
| Стратегический план, 5-тарау | Не сделано в файлах проекта | Нужно оформить выводы, риски, рекомендации и ожидаемый эффект в тексте курсовой |

## 2. Какие файлы использовать

Главная таблица:

`data/cleaned_monthly_dataset.csv`

Для Power BI импортируйте также:

| Файл | Назначение |
|---|---|
| `data/official_current_usd_kzt.csv` | Актуальный официальный курс |
| `results/method_02_clustering_periods.csv` | Кластеры периодов |
| `results/method_02_clustering_metrics.csv` | Silhouette Score |
| `results/method_03_classification_predictions.csv` | Фактический и предсказанный риск |
| `results/method_03_classification_confusion_matrix.csv` | Confusion Matrix |
| `results/method_04_association_rules.csv` | Support, Confidence, Lift |
| `results/method_05_time_series_forecast.csv` | Прогноз на 12 месяцев |
| `results/method_06_pca_scores.csv` | PC1, PC2, PC3 |
| `results/method_06_pca_variance.csv` | Explained Variance Ratio |
| `results/method_07_anomaly_detection.csv` | Флаги аномалий |
| `results/method_07_anomaly_metrics.csv` | Сравнение методов аномалий |
| `results/method_08_neural_network_metrics.csv` | MLP |
| `results/method_09_naive_bayes_metrics.csv` | Naive Bayes |
| `results/method_10_knn_metrics.csv` | k=3, 5, 7 |

Полный список находится в `powerbi_import_manifest.csv`.

## 3. Как импортировать данные в Power BI

1. Откройте `AkiraDollarTenge.pbip`.
2. На панели **Home** нажмите **Transform data**.
3. В Power Query выберите **New source → Text/CSV**.
4. Импортируйте `data/cleaned_monthly_dataset.csv`.
5. Проверьте типы:
   - `date` — Date;
   - `usd_kzt`, `brent_usd`, CPI и проценты — Decimal number;
   - `devaluation_event`, `risk_high` — Whole number.
6. Нажмите **Close & Apply**.
7. Повторите импорт для CSV из таблицы выше.
8. После каждой группы загрузки нажимайте **File → Save**.

Для курсовой отдельно покажите в Power Query:

- удаление служебных строк;
- изменение типов;
- удаление дубликатов;
- обработку пропусков;
- Merge по `date` или `period`;
- Group By для среднемесячного Brent;
- Conditional Column для `devaluation_event`.

Одного факта загрузки готового CSV недостаточно: на скриншотах должен быть виден сам процесс Power Query.

## 4. Какие связи создать

В основной таблице `CleanedMonthlyDataset` используется поле `date`.

Для таблицы прогноза:

- `CleanedMonthlyDataset[date]`
- `TimeSeriesForecast[date]`

Связь лучше оставить неактивной или использовать отдельную календарную таблицу, потому что прогноз содержит будущие даты.

Для кластеров и аномалий:

- `CleanedMonthlyDataset[date]`
- соответствующая таблица `[date]`.

Если Power BI создаёт неоднозначные связи, не объединяйте все таблицы напрямую. Для учебного проекта допустимо использовать отдельные визуалы без физической связи.

## 5. DAX measures

В таблице `CleanedMonthlyDataset` создайте:

```DAX
Средний курс =
AVERAGE(CleanedMonthlyDataset[usd_kzt])
```

```DAX
Максимальный курс =
MAX(CleanedMonthlyDataset[usd_kzt])
```

```DAX
Минимальный курс =
MIN(CleanedMonthlyDataset[usd_kzt])
```

```DAX
Количество девальваций =
SUM(CleanedMonthlyDataset[devaluation_event])
```

```DAX
Количество месяцев высокого риска =
SUM(CleanedMonthlyDataset[risk_high])
```

```DAX
Средняя цена Brent =
AVERAGE(CleanedMonthlyDataset[brent_usd])
```

```DAX
Средняя волатильность =
AVERAGE(CleanedMonthlyDataset[volatility_12m])
```

## 6. Структура Power BI-отчёта

### Страница 1 — Главная панель риска

Добавьте карточки:

- текущий курс;
- средний курс;
- максимальный курс;
- количество девальвационных событий;
- количество месяцев высокого риска;
- средняя волатильность.

Добавьте линейный график:

- Axis: `date`;
- Values: `usd_kzt`, `brent_usd`.

Для курса и Brent лучше использовать отдельные графики, потому что у них разные масштабы.

Добавьте график:

- Axis: `date`;
- Values: `usd_kzt_mom_pct`, `volatility_12m`.

Добавьте slicer по `date` и slicer по `risk_high`.

### Страница 2 — Курс, нефть и инфляция

Визуалы:

1. Line chart: `date` + `usd_kzt`.
2. Line chart: `date` + `brent_usd`.
3. Column chart: `year` + `cpi_total`.
4. Scatter chart:
   - X: `brent_usd`;
   - Y: `usd_kzt`;
   - Legend: `risk_high`.

### Страница 3 — Кластеры и режимы

Источник: `method_02_clustering_periods.csv`.

Добавьте:

- scatter chart: X = `brent_usd`, Y = `usd_kzt_mom_pct`, Legend = `cluster_name`;
- column chart: Axis = `cluster_name`, Values = Count of dates;
- table: `date`, `cluster`, `cluster_name`, `usd_kzt_mom_pct`, `volatility_12m`;
- card с Silhouette Score из `method_02_clustering_metrics.csv`.

### Страница 4 — Аномалии

Источник: `method_07_anomaly_detection.csv`.

Добавьте line chart:

- Axis: `date`;
- Values: `usd_kzt_mom_pct`;
- Legend: один из флагов `zscore_anomaly`, `iqr_anomaly`, `isolation_forest_anomaly`.

Добавьте table с датами аномалий и их методами обнаружения.

### Страница 5 — Прогноз

Источники:

- `CleanedMonthlyDataset`;
- `method_05_time_series_forecast.csv`.

Добавьте line chart с:

- историческим `usd_kzt`;
- `forecast_usd_kzt`;
- Axis = `date`.

Отдельно покажите таблицу прогноза на 12 месяцев.

### Страница 6 — Сравнение ML-моделей

Используйте:

- `method_08_neural_network_metrics.csv`;
- `method_09_naive_bayes_metrics.csv`;
- `method_10_knn_metrics.csv`.

Добавьте clustered column chart:

- Axis: `model`;
- Values: `accuracy`, `precision`, `recall`, `f1`.

Добавьте таблицу с теми же метриками.

### Страница 7 — Association Rules и PCA

Association Rules:

- table с `antecedents`, `consequents`, `support`, `confidence`, `lift`;
- bar chart по `lift`.

PCA:

- scatter chart: X = `PC1`, Y = `PC2`;
- table с explained variance;
- card с долей дисперсии PC1 и PC2.

## 7. Что обязательно добавить в Excel

В Excel создайте отдельный лист `Excel_Calculations` и покажите формулы:

- `AVERAGE`, `MIN`, `MAX`;
- `COUNTIF` или `COUNTIFS`;
- `STDEV.S`;
- `CORREL`;
- `LINEST`, `SLOPE`, `INTERCEPT`;
- `FORECAST.LINEAR` или `FORECAST.ETS`;
- `PERCENTILE.INC` или `QUARTILE.INC`.

Для регрессии:

- зависимая переменная: `usd_kzt`;
- независимые: `brent_usd`, `cpi_total`, группы CPI;
- показать R², коэффициенты и прогноз.

Для временного ряда:

- построить `date` и `usd_kzt`;
- добавить 12 будущих месяцев;
- рассчитать прогноз;
- сравнить прогноз с последними историческими значениями.

## 8. Что написать в интерпретации

Не нужно утверждать, что модель доказала причинность. Корректная формулировка:

> Регрессия показывает статистическую связь курса USD/KZT с ценой Brent и инфляционными показателями в используемой выборке. Отрицательный R² на временном тесте означает, что модель по абсолютному уровню курса недостаточна для надёжного прогноза и должна быть улучшена признаками лагов, доходностей и режимов рынка.

Для риска:

- высокая `volatility_12m` означает нестабильность курса;
- `devaluation_event = 1` означает сильное месячное изменение;
- `risk_high = 1` означает месяц из верхнего квартиля волатильности;
- кластеры интерпретируются как режимы рынка, а не как официальные экономические периоды;
- низкий Recall у MLP/Naive Bayes означает, что эти модели плохо находят месяцы высокого риска и не должны использоваться как единственный сигнал.

## 9. Финальный порядок работы

1. Импортировать основную таблицу в Power BI.
2. Импортировать все таблицы результатов.
3. Сохранить проект.
4. Создать DAX measures.
5. Сделать семь страниц отчёта.
6. Добавить скриншоты Power Query и Excel-формул в курсовую.
7. Добавить скриншоты каждого ML-результата.
8. Написать сравнение моделей.
9. Написать 5-тарау: риски, рекомендации и ожидаемый эффект.
10. Проверить, что все CSV и Excel-файлы находятся в приложениях к курсовой.

## 10. Честный итог текущего состояния

Подготовка данных и воспроизводимый Python-анализ всех 10 методов выполнены. Дополнительно созданы regression predictions, сравнение числа кластеров, association rules с 9 правилами, backtesting прогноза и Excel-лист с формулами.

Не завершено автоматически:

1. импорт всех CSV результатов в Power BI;
2. сборка 7 страниц отчёта, KPI-карточек, slicers и сценарной страницы;
3. ручные скриншоты процесса Power Query и Excel в курсовой;
4. оформление финального текста 5-тарау.

Текущий Power BI нельзя считать полностью готовым дашбордом: в нём сохранён базовый визуал, но не полный набор страниц из методички. После импорта результатов рекомендуется использовать единый стиль: тёмно-синий фон, акцентные цвета `#2F80ED` (курс), `#F2994A` (Brent), `#EB5757` (высокий риск), одинаковые заголовки и отдельные графики для показателей с разными шкалами.
