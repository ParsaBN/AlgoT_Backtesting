# region imports
from datetime import datetime
from AlgorithmImports import *
from QuantConnect.Data.UniverseSelection import *
from dataclasses import dataclass
# endregion

class SymbolData(object):
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_average = SimpleMovingAverage(50)
        self.slow_average = SimpleMovingAverage(200)
        self.rsi = RelativeStrengthIndex(14)

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
    importance: float
    reversed: bool = False
    hard_min: bool = True

METRICS = {
    'price_earnings_ratio': Metric(
        lambda f, d: f.ValuationRatios.PERatio,
        min=7.5, max=20.0,
        importance=1.5,
        reversed=True
    ),

    'growth': Metric(
        lambda f, d: f.AssetClassification.GrowthScore,
        min=0.02, max=1.0,
        importance=1.0
    ),

    'fast_slow_average_crossover': Metric(
        lambda f, d: (d.fast_average.Current.Value - d.slow_average.Current.Value) / d.slow_average.Current.Value,
        min=0.0, max=0.2,
        importance=1.0
    ),
    
    # 'relative_strength_index': Metric(lambda f, d: d.rsi.Current.Value, 7.5, 20),
}

class CryingRedRhinoceros(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2013, 12, 30)
        self.SetEndDate(2015, 7, 1)
        self.SetCash(100000)
        self.SetWarmUp(1, Resolution.Daily)

        # something is kinda broken
        # see: https://www.quantconnect.com/forum/discussion/8779/security-doesn-039-t-have-a-bar-of-data-trade-error-options-trading/p1
        # self.SetSecurityInitializer(lambda x: x.SetMarketPrice(self.GetLastKnownPrice(x)))

        self.symbol_data: Dict[Symbol, SymbolData] = {}
        self.selected_scores: Dict[Security, float] = {}

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelection, self.FineSelection)

        self.Schedule.On(self.DateRules.MonthStart(0), self.TimeRules.Midnight, self.Rebalance)

    def CoarseSelection(self, coarse: List[CoarseFundamental]) -> List[Symbol]:
        filtered = [x for x in coarse if x.HasFundamentalData][:100]

        for cf in filtered:
            if cf.Symbol not in self.symbol_data:
                self.symbol_data[cf.Symbol] = SymbolData(cf.Symbol)

            data = self.symbol_data[cf.Symbol]
            data.update(cf.EndTime, cf.AdjustedPrice)

        return [x.Symbol for x in filtered]

    def FineSelection(self, fine: List[FineFundamental]) -> List[Symbol]:
        self.selected_scores = {}
        for ff in fine:
            ff.Price
            data = self.symbol_data[ff.Symbol]
            score = self.CalculateScore(ff, data)

            if score is not None:
                self.selected_scores[ff.Symbol] = score
                
        return list(self.selected_scores.keys())

    def Rebalance(self):
        if not (self.Time.month == 1 or self.Time.month == 7):
            return

        self.Log(f'rebalancing! {self.Time}')

        for security in self.Portfolio.Values:
            if security.Invested:
                self.Liquidate(security.Symbol)

        if self.selected_scores:
            total_score = sum(self.selected_scores.values())

            for symbol, score in self.selected_scores.items():
                self.SetHoldings(symbol, score / total_score)
                self.Log(f'set holding for {symbol}: {score / total_score} (score: {score})')

    def CalculateScore(self, fine: FineFundamental, data: SymbolData) -> Union[float, None]:
        score = 0
        for metric in METRICS.values():
            raw = (metric.get(fine, data) - metric.min) / (metric.max - metric.min)

            if metric.reversed:
                raw = 1 - raw

            if metric.hard_min and raw < 0:
                return None
            
            clamped = min(raw, 1.0) # already clamped > 0
            score += clamped * metric.importance

        return score # should we normalise 0 to 1?

    # def OnSecuritiesChanged(self, changes: SecurityChanges):
    #     pass

    def OnData(self, data: Slice):
        pass
