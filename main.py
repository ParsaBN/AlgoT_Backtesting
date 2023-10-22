# region imports
from collections import defaultdict
from datetime import datetime
import math
from AlgorithmImports import *
from QuantConnect.Data.UniverseSelection import *
from dataclasses import dataclass
import pandas as pd
# endregion

STOP_LOSS_FRACTION = 0.1
SECTOR_PROPORTION_MAX = 0.2

class SymbolData(object):
    def __init__(self, cf: CoarseFundamental):
        self.fast_average = SimpleMovingAverage(50)
        self.slow_average = SimpleMovingAverage(200)
        self.rsi = RelativeStrengthIndex(14)
        self.price_ceiling = cf.AdjustedPrice

    def is_ready(self) -> bool:
        return self.fast_average.IsReady and self.slow_average.IsReady and self.rsi.IsReady

    def update(self, time: datetime, value: float):
        self.fast_average.Update(time, value)
        self.slow_average.Update(time, value)
        self.rsi.Update(time, value)

@dataclass
class Metric:
    get: Callable[[FineFundamental, SymbolData], float]
    min: float
    max: float
    weighting: float
    reversed: bool = False
    hard_min: bool = True

METRICS = {
    'price_earnings_ratio': Metric(
        lambda f, d: f.ValuationRatios.PERatio,
        min=7.5, max=20.0,
        weighting=1.2,
        reversed=True
    ),

    'growth': Metric(
        lambda f, d: f.AssetClassification.GrowthScore,
        min=0.02, max=1.0,
        weighting=1.0
    ),

    'fast_slow_average_crossover': Metric(
        lambda f, d: (d.fast_average.Current.Value - d.slow_average.Current.Value) / d.slow_average.Current.Value,
        min=0.0, max=0.2,
        weighting=1.0
    ),

    'free_cash_flow': Metric(
        lambda f, d: f.FinancialStatements.CashFlowStatement.FreeCashFlow.SixMonths,
        min=0.0, max=1.0,
        weighting=0.0
    ),

    'relative_strength_index': Metric(
        lambda f, d: d.rsi.Current.Value,
        min=0.3, max=0.65,
        weighting=1.0
    ),
}

class CryingRedRhinoceros(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2005, 12, 30)
        self.SetEndDate(2012, 7, 1)
        self.SetCash(100000)
        self.SetWarmUp(1, Resolution.Daily)

        # something is kinda broken
        # see: https://www.quantconnect.com/forum/discussion/8779/security-doesn-039-t-have-a-bar-of-data-trade-error-options-trading/p1
        # self.SetSecurityInitializer(lambda x: x.SetMarketPrice(self.GetLastKnownPrice(x)))

        self.symbol_data: Dict[Symbol, SymbolData] = {}
        self.selected_scores: Dict[Symbol, float] = {}
        self.selected_sectors: Dict[Symbol, str] = {}
        self.rebalance_requested = False

        self.metric_score_history = []
        self.metric_raw_history = []

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelection, self.FineSelection)

        self.Schedule.On(self.DateRules.MonthStart(0), self.TimeRules.Midnight, self.Rebalance)

    def CoarseSelection(self, coarse: List[CoarseFundamental]) -> List[Symbol]:
        filtered = [x for x in coarse if x.HasFundamentalData][:100]

        for cf in filtered:
            if cf.Symbol not in self.symbol_data:
                self.symbol_data[cf.Symbol] = SymbolData(cf)

            data = self.symbol_data[cf.Symbol]
            data.update(cf.EndTime, cf.AdjustedPrice)

        if not self.rebalance_requested:
            return []
        
        self.Log(f'coarse len: {len(filtered)}')
        
        return [x.Symbol for x in filtered]

    def FineSelection(self, fine: List[FineFundamental]) -> List[Symbol]:
        if not self.rebalance_requested:
            return []

        self.selected_scores = {}
        self.selected_sectors = {}
        for ff in fine:
            data = self.symbol_data[ff.Symbol]
            score = self.CalculateCombinedScore(ff, data)

            if score is not None:
                self.selected_scores[ff.Symbol] = score
                self.selected_sectors[ff.Symbol] = ff.CompanyReference.IndustryTemplateCode

        self.Log(f'fine len: {len(self.selected_sectors)}')
        
        self.allocation_event = self.Schedule.On(self.DateRules.Tomorrow, self.TimeRules.Midnight, self.AllocatePortfolio)
        return list(self.selected_scores.keys())

    def Rebalance(self):
        if self.Time.month == 1 or self.Time.month == 7:
            self.Log(f'rebalance requested! {self.Time}')
            self.rebalance_requested = True

    def AllocatePortfolio(self):
        if not self.allocation_event:
            self.Error('this shouldnt have happened')
            return
        
        self.Schedule.Remove(self.allocation_event)
        self.Log(f'allocating new portfolio {self.Time}')

        for security in self.Portfolio.Values:
            if security.Invested:
                self.Liquidate(security.Symbol)

        if self.selected_scores:
            total_score = sum(self.selected_scores.values())
            holdings = {symbol: score / total_score for symbol, score in self.selected_scores.items()}

            sector_holdings = defaultdict(float)
            for symbol, score in holdings.items():
                sector_holdings[self.selected_sectors[symbol]] += score

            sector_holdings_capped = {sector: min(proportion, SECTOR_PROPORTION_MAX) for sector, proportion in sector_holdings.items()}
            sector_holdings_rebalanced = {sector: proportion / sum(sector_holdings_capped.values()) for sector, proportion in sector_holdings_capped.items()}

            self.Log(f'settings holdings for {len(self.selected_scores)} securities')
            for symbol, holding in holdings.items():
                sector = self.selected_sectors[symbol]
                balanced_holding = holding * (sector_holdings_rebalanced[sector] / sector_holdings[sector])
                self.SetHoldings(symbol, balanced_holding)
                # self.Log(f'set holding for {symbol}: {score / total_score} (score: {score})')

        self.rebalance_requested = False

    def CalculateCombinedScore(self, fine: FineFundamental, data: SymbolData) -> Union[float, None]:
        metric_scores = self.CalculateMetricScores(fine, data)

        score = 0
        for name, value in metric_scores.items():
            if math.isinf(value):
                return None

            score += value * METRICS[name].weighting

        return score
    
    def CalculateMetricScores(self, fine: FineFundamental, data: SymbolData) -> Dict[str, float]:
        scores = {}
        raws = {}
        for name, metric in METRICS.items():
            raw = metric.get(fine, data)
            raws[name] = raw

            unclamped = (raw - metric.min) / (metric.max - metric.min)

            if metric.reversed:
                unclamped = 1 - unclamped

            if metric.hard_min and unclamped < 0:
                unclamped = -math.inf

            scores[name] = min(unclamped, 1.0)

        self.metric_score_history.append(scores)
        self.metric_raw_history.append(raws)
        return scores

    def OnData(self, slice: Slice):
        self.HandleStopLosses(slice)

    def HandleStopLosses(self, slice: Slice):
        to_remove = []
        for symbol in self.selected_scores:
            data = self.symbol_data[symbol]

            if symbol in slice and slice[symbol]:
                price = slice[symbol].Price

                if price < data.price_ceiling * (1 - STOP_LOSS_FRACTION):
                    self.Log(f'hit stop-loss! {symbol}')
                    self.Liquidate(symbol)
                    to_remove.append(symbol)
                else:
                    data.price_ceiling = max(data.price_ceiling, price)

        for symbol in to_remove:
            self.selected_scores.pop(symbol)

    def OnEndOfAlgorithm(self):
        # means = {}
        # for key in METRICS.keys():
        #     means[key] = sum(d[key] for d in self.metric_scores_history) / len(self.metric_scores_history)

        # self.Log(f'metric means: {means}')

        score_df = pd.DataFrame(self.metric_score_history)
        score_df.replace(-math.inf, math.nan, inplace=True)
        score_df.dropna(inplace=True)

        self.Log('scores')
        self.Log(f'mean: {score_df.mean(axis=0)}')
        self.Log(f'median: {score_df.median(axis=0)}')
        self.Log(f'std: {score_df.std(axis=0)}')

        raws_df = pd.DataFrame(self.metric_raw_history)
        raws_df.replace(-math.inf, math.nan, inplace=True)
        raws_df.dropna(inplace=True)

        self.Log('raw')
        self.Log(f'mean: {raws_df.mean(axis=0)}')
        self.Log(f'median: {raws_df.median(axis=0)}')
        self.Log(f'std: {raws_df.std(axis=0)}')

        # for _, row in df.iterrows():
        #     self.Log(row.to_frame().T)
