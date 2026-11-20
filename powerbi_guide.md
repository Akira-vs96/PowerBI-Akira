# Power BI есебін құру нұсқаулығы

## 1. Деректерді жүктеу және модель

1. `python3 -m venv .venv && .venv/bin/pip install -r requirements.txt` арқылы ортаны дайындап,
   ` .venv/bin/python analysis.py` командасын орындаңыз.
2. Power BI Desktop-та **Get data → Text/CSV** арқылы `output/` ішіндегі
   `usd_kzt_monthly.csv`, `forecast.csv`, `forecast_validation.csv`, `decomposition.csv`,
   `risk_yearly.csv`, `risk_var.csv`, `corr_brent.csv`, `brent_kzt_linked.csv`,
   `joint_currency_oil_risk.csv`, `shocks.csv`, `scenarios.csv`
   файлдарын жүктеңіз. Encoding: UTF-8, delimiter: comma, decimal: point.
3. Күнтізбе кестесін жасаңыз:

```DAX
Күнтізбе = CALENDAR(DATE(2006,11,1), DATE(2027,10,31))
Жыл = YEAR('Күнтізбе'[Date])
Ай нөмірі = MONTH('Күнтізбе'[Date])
Ай = FORMAT('Күнтізбе'[Date], "YYYY-MM")
Тоқсан = "Q" & FORMAT('Күнтізбе'[Date], "Q")
```

`Күнтізбе[Date]` → `usd_kzt_monthly[Date]` байланысын (one-to-many, single direction)
орнатыңыз. Басқа кестелерді қажет болса Date арқылы байланыстырыңыз; факт кестелерінде
бірдей Date қайталанған жағдайда оларды бөлек факт ретінде қалдырыңыз.

## 2. Дайын DAX өлшемдері

Мысалдар негізгі кесте атауы `usd_kzt_monthly` деп қабылдайды:

```DAX
Текущий курс = LASTNONBLANK('usd_kzt_monthly'[EndRate], [Средний курс])
Средний курс = AVERAGE('usd_kzt_monthly'[EndRate])
Макс курс = MAX('usd_kzt_monthly'[MaxRate])
Мин курс = MIN('usd_kzt_monthly'[MinRate])
Изменение к пред. месяцу % =
VAR CurrentRate = [Текущий курс]
VAR PreviousRate = CALCULATE([Текущий курс], DATEADD('Күнтізбе'[Date], -1, MONTH))
RETURN DIVIDE(CurrentRate - PreviousRate, PreviousRate)
Изменение YoY % =
VAR CurrentRate = [Текущий курс]
VAR PriorRate = CALCULATE([Текущий курс], DATEADD('Күнтізбе'[Date], -1, YEAR))
RETURN DIVIDE(CurrentRate - PriorRate, PriorRate)
Волатильность = AVERAGE('usd_kzt_monthly'[Volatility12])
VaR 95 = CALCULATE(MAX('risk_var'[Loss_KZT_per_1m_USD]), 'risk_var'[Confidence] = "95%")
Корреляция с Brent = CORREL('usd_kzt_monthly'[EndRate], 'usd_kzt_monthly'[Brent_USD_bbl])
Прогноз на последний период = MAX('forecast'[Forecast])
Орташа Brent (USD/баррель) = AVERAGE('usd_kzt_monthly'[Brent_USD_bbl])
Баррельдің теңгедегі бағасы = AVERAGE('usd_kzt_monthly'[Brent_KZT_bbl])
```

Процент форматтарын `Percentage`, курс пен VaR-ды `Decimal number`/`Whole number`
ретінде белгілеңіз. Көрсетілімге ыңғайлы болу үшін measure атауларын казахша
нұсқаға (`Ағымдағы курс`, `Орташа курс`, т.б.) ауыстыруға болады.

## 3. Беттер

* **1 — Шолу:** төрт карточка (ағымдағы курс, YoY %, волатильдік, VaR 95%);
  2006–2026 курсінің сызықтық графигі және жыл/тоқсан срезерлері.
* **2 — Уақыттық қатар:** `EndRate`, `MA3`, `MA6`, `MA12` сызықтары;
  decomposition кестесінен Trend/Seasonal/Residual үш сызық; Analytics → Forecast
  арқылы 12 ай және 95% confidence interval. Сонымен бірге `forecast.csv` файлынан
  есептелген Forecast/Lower95/Upper95 сызықтарын қосыңыз.
* **3 — Тәуекел:** `risk_yearly` бағандық графигі, түсін `RiskLevel` бойынша
  шартты форматтау; VaR кестесі; `shocks` кестесі; Brent пен USD/KZT scatter;
  `corr_brent` бойынша айлық өзгерістердің 24 айлық жылжымалы корреляциясы;
  `brent_kzt_linked` кестесінен Brent USD/баррель және Brent теңге/баррель
  графигін қосымша екі осьпен салыстырыңыз.
  `joint_currency_oil_risk` кестесінен үш KPI қатарын көрсетіңіз:
  USD/KZT, Brent USD/баррель және Brent теңге/баррель. `StressCount` бойынша
  айларды шартты түспен белгілеңіз: 0 — төмен, 1 — орташа, 2–3 — жоғары.
  Brent жоқ айлар `Дерек жоқ` ретінде көрсетілсін және тәуекел түсіне
  қосылмасын.
* **4 — Сценарийлер:** `scenarios` кестесінен үш сызық (`Scenario` легендасы),
  сценарий срезері және соңғы айдың мәнін көрсететін карточка.

Бірізді палитра қолданыңыз: негізгі курс — көк `#1F77B4`, Brent — қара-сұр,
базалық сценарий — көк, оптимистік — жасыл, пессимистік — қызыл. Барлық визуал
тақырыптары мен ось атауларын қазақша жазыңыз. Сандық өрістерде мыңдық бөлгішті,
даталарда `YYYY-MM` форматын қолданыңыз.

### Brent пен теңге байланысын түсіндіру

`Brent_USD_bbl` — бір баррель мұнайдың доллардағы бағасы. Оның теңгедегі
эквиваленті арнайы есептелді:

```text
Brent_KZT_bbl = Brent_USD_bbl × EndRate
```

Мысалы, Brent 80 USD/баррель және курс 450 KZT/USD болса, баррельдің құны
36 000 KZT болады. `usd_kzt_monthly` кестесіндегі `Brent_KZT_bbl` бағанын
USD/KZT графигімен бірге бөлек масштабта көрсетіңіз. `corr_brent.csv` файлындағы
`Correlation24M_USD` — USD-дегі Brent пен курс байланысы, ал
`Correlation24M_BrentKZT` — теңгедегі баррель құнының курсқа байланысы.
Екіншісі есептік түрде курсқа кіретіндіктен, оны себепті фактор емес,
импорттық/энергетикалық құн көрсеткіші ретінде түсіндіріңіз.
Себепке жақынырақ қысқа мерзімді салыстыру үшін `corr_brent.csv` ішіндегі
`ChangeCorrelation24M_USD` бағанын пайдаланыңыз: бұл курс пен Brent-тің
айлық пайыздық өзгерістерінің 24 айлық корреляциясы.
