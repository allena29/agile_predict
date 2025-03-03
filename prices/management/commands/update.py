import xgboost as xg
from sklearn.metrics import mean_squared_error as MSE
import numpy as np

from django.core.management.base import BaseCommand
from ...models import History, PriceHistory, Forecasts, ForecastData, AgileData, Nordpool

from config.utils import *

DAYS_TO_INCLUDE = 7
MODEL_ITERS = 50
MIN_HIST = 7
MAX_HIST = 28


class Command(BaseCommand):
    def add_arguments(self, parser):
        # Positional arguments
        # parser.add_argument("poll_ids", nargs="+", type=int)

        # Named (optional) arguments
        parser.add_argument(
            "--no_forecast",
            action="store_true",
        )
        parser.add_argument(
            "--no_dow",
            action="store_true",
        )
        parser.add_argument(
            "--no_hist",
            action="store_true",
        )

        parser.add_argument(
            "--drop_last",
        )

        parser.add_argument(
            "--min_hist",
        )

        parser.add_argument(
            "--max_hist",
        )

        parser.add_argument(
            "--iters",
        )

        parser.add_argument(
            "--ignore_forecast",
            action="append",
        )

    def handle(self, *args, **options):
        no_forecast = options.get("no_forecast", False)
        no_hist = options.get("no_hist", False)

        drop_cols = ["total_wind"]
        if options.get("no_dow", False):
            drop_cols += ["day_of_week"]

        drop_last = int(options.get("drop_last", 0) or 0)

        min_hist = int(options.get("min_hist", MIN_HIST) or MIN_HIST)
        max_hist = int(options.get("max_hist", MAX_HIST) or MAX_HIST)

        iters = int(options.get("iters", MODEL_ITERS) or MODEL_ITERS)
        if options.get("ignore_forecast", []) is None:
            ignore_forecast = []
        else:
            ignore_forecast = [int(x) for x in options.get("ignore_forecast", [])]

        # Clean any invalid forecasts
        for f in Forecasts.objects.all():
            q = ForecastData.objects.filter(forecast=f)
            a = AgileData.objects.filter(forecast=f)

            print(f.name, q.count(), a.count())
            if q.count() < 600 or a.count() < 8000:
                f.delete()

        print("Getting history from model")
        hist = get_history_from_model()

        print("Database History:")
        print(hist)
        start = pd.Timestamp("2023-07-01", tz="GB")
        if len(hist) > 0:
            start = hist.index[-1] + pd.Timedelta("30min")

        print(f"New data from {start.strftime(TIME_FORMAT)}:")

        new_hist = get_latest_history(start=start)
        if len(new_hist) > 0:
            print(new_hist)
            df_to_Model(new_hist, History)

        else:
            print("None")

        hist = pd.concat([hist, new_hist]).sort_index()

        print("Getting Historic Prices")

        prices, start = model_to_df(PriceHistory)
        agile = get_agile(start=start)

        day_ahead = day_ahead_to_agile(agile, reverse=True)

        new_prices = pd.concat([day_ahead, agile], axis=1)
        if len(prices) > 0:
            new_prices = new_prices[new_prices.index > prices.index[-1]]
        print(new_prices)
        if len(new_prices) > 0:
            print(new_prices)
            df_to_Model(new_prices, PriceHistory)

        prices = pd.concat([prices, new_prices]).sort_index()

        if drop_last > 0:
            print(f"drop_last: {drop_last}")
            print(f"len: {len(prices)} last:{prices.index[-1]}")
            prices = prices.iloc[:-drop_last]
            print(f"len: {len(prices)} last:{prices.index[-1]}")

        print("Getting NP from Model")
        nordpool, start = model_to_df(Nordpool)
        print(nordpool)

        new_nordpool = get_nordpool(start)
        print(new_nordpool)

        new_name = pd.Timestamp.now(tz="GB").strftime("%Y-%m-%d %H:%M")
        if new_name not in [f.name for f in Forecasts.objects.all()]:
            base_forecasts = Forecasts.objects.exclude(id__in=ignore_forecast).order_by("-created_at")

            print("Getting latest Forecast")
            fc = get_latest_forecast()
            print(fc)

            if len(fc) > 0:
                for i in range(iters):
                    cols = hist.drop(drop_cols, axis=1).columns

                    X = hist[cols].iloc[-48 * np.random.randint(min_hist, max_hist) :]
                    y = prices["day_ahead"].loc[X.index]

                    if not no_hist:
                        X1 = [X.copy()]
                        y1 = [y.copy()]
                    else:
                        X1 = []
                        y1 = []

                    if not no_forecast:
                        for f in base_forecasts:
                            days_since_forecast = (pd.Timestamp.now(tz="GB") - f.created_at).days
                            if days_since_forecast < 14:

                                # if f != this_forecast and days_since_forecast < 14:
                                df = get_forecast_from_model(forecast=f).loc[: prices.index[-1]]
                                # print(prices.loc[df.index])
                                # print(df.columns)

                                if len(df) > 0:
                                    rng = np.random.default_rng()
                                    max_len = DAYS_TO_INCLUDE * 48
                                    samples = rng.triangular(0, 0, max_len, max_len).astype(int)
                                    samples = samples[samples < len(df)]
                                    print(
                                        f"{f.id:3d}:, {df.index[0].strftime('%d-%b %H:%M')} - {df.index[-1].strftime('%d-%b %H:%M')}  Length: {len(df.iloc[samples]):3d} Oversampling:{len(df.iloc[samples])/len(df) * 100:0.0f}%"
                                    )

                                    df = df.iloc[samples]

                                    X1.append(df[cols])
                                    y1.append(prices["day_ahead"].loc[df.index])

                    X1 = pd.concat(X1)
                    y1 = pd.concat(y1)

                    model = xg.XGBRegressor(
                        objective="reg:squarederror",
                        booster="dart",
                        # max_depth=0,
                        gamma=0.3,
                        eval_metric="rmse",
                    )

                    model.fit(X1, y1, verbose=True)
                    model_day_ahead = pd.Series(index=y1.index, data=model.predict(X1))

                    model_agile = day_ahead_to_agile(model_day_ahead)
                    rmse = MSE(model_agile, prices["agile"].loc[X1.index]) ** 0.5

                    print(f"\nInteration: {i+1}")
                    print("--------------")
                    print(f"       RMS Error: {rmse: 0.2f} p/kWh")
                    print(f"Lengths: History: {(len(X) / len(X1)*100):0.1f}%")
                    print(f"       Forecasts: {((len(X1) - len(X))/len(X1)*100):0.1f}%")
                    fc[f"day_ahead_{i}"] = model.predict(fc[cols])

                day_ahead_cols = [f"day_ahead_{i}" for i in range(iters)]
                fc["day_ahead"] = fc[day_ahead_cols].mean(axis=1)
                if iters > 9:
                    fc["day_ahead_low"] = fc[day_ahead_cols].quantile(0.1, axis=1)
                    fc["day_ahead_high"] = fc[day_ahead_cols].quantile(0.9, axis=1)
                else:
                    fc["day_ahead_low"] = fc[day_ahead_cols].min(axis=1)
                    fc["day_ahead_high"] = fc[day_ahead_cols].max(axis=1)

                ag = pd.concat(
                    [
                        pd.DataFrame(
                            index=fc.index,
                            data={
                                "region": region,
                                "agile_pred": day_ahead_to_agile(fc["day_ahead"], region=region)
                                .astype(float)
                                .round(2),
                                "agile_low": day_ahead_to_agile(fc["day_ahead_low"], region=region)
                                .astype(float)
                                .round(2),
                                "agile_high": day_ahead_to_agile(fc["day_ahead_high"], region=region)
                                .astype(float)
                                .round(2),
                            },
                        )
                        for region in regions
                    ]
                )

                fc = fc.drop(day_ahead_cols, axis=1)
                fc.drop(["time", "day_of_week", "day_ahead_low", "day_ahead_high"], axis=1, inplace=True)

                this_forecast = Forecasts(name=new_name)
                this_forecast.save()
                fc["forecast"] = this_forecast
                ag["forecast"] = this_forecast
                df_to_Model(fc, ForecastData)
                df_to_Model(ag, AgileData)

        for f in Forecasts.objects.all():
            print(f"{f.id:4d}: {f.name}")
