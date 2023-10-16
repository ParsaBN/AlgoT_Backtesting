# region imports
from datetime import datetime
from AlgorithmImports import *
from QuantConnect.Data.UniverseSelection import *
from dataclasses import dataclass

import QuantConnect.Data.UniverseSelection
# endregion

# @dataclass
# class Metric:
#     get: Callable[[FineFundamental], float]
#     threshold: float
    
# METRICS = {
#     'price_earnings_ratio': Metric(lambda x: x.ValuationRatios.PERatio, 15)
# }

# @dataclass
# class StockMetrics:
#     price_earnings_ratio: float
#     earnings_growth_rate: float
#     debt_equity_rato: float
#     cash_flow: float

#     def filter(self) -> bool:
#         return (
#             self.price_earnings_ratio < 15 and
#             self.earnings_growth_rate > 0.15 and
#             self.debt_equity_rato > 0 and # TODO: check
#             self.cash_flow > 0
#         )

#     def score(self) -> float:
#         return self.price_earnings_ratio

class SymbolData(object):
    def __init__(self, symbol):
        self.symbol = symbol
        self.fast_average = SimpleMovingAverage(50)
        self.slow_average = SimpleMovingAverage(200)
        self.rsi = RelativeStrengthIndex(14)
        # self.is_uptrend = False

    def is_ready(self) -> bool:
        return self.fast_average.IsReady and self.slow_average.IsReady and self.rsi.IsReady

    def update(self, time: datetime, value: float):
        # if self.fast_average.Update(time, value) and self.slow_average.Update(time, value):
        #     fast = self.fast_average.Current.Value
        #     slow = self.slow_average.Current.Value
        #     self.is_uptrend = fast > slow

        self.fast_average.Update(time, value)
        self.slow_average.Update(time, value)
        self.rsi.Update(time, value)

class CryingRedRhinoceros(QCAlgorithm):
    def Initialize(self):
        # self.stock_metrics: Dict[Symbol, StockMetrics] = {}

        self.SetStartDate(2014, 1, 1)
        self.SetEndDate(2015, 1, 1)
        self.SetCash(50000)
        # self.SetWarmUp(200, Resolution.Daily)

        # self.AddEquity("AAPL")

        self.symbol_data: Dict[Symbol, SymbolData] = {}
        self.selected_securities: List[Security] = []

        self.UniverseSettings.Resolution = Resolution.Daily
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.Schedule.On(self.DateRules.EveryDay(), self.TimeRules.Midnight, self.Rebalance)

        # self.are_trackers_initialised = False
        # self.short_sma: Dict[Symbol, SimpleMovingAverage] = {}
        # self.long_sma: Dict[Symbol, SimpleMovingAverage] = {}
        # self.rsi: Dict[Symbol, RelativeStrengthIndex] = {}

    def CoarseSelectionFunction(self, coarse: List[CoarseFundamental]) -> List[Symbol]:
        filtered = [x for x in coarse if x.HasFundamentalData][:10]

        # sort descending by daily dollar volume
        #sortedByDollarVolume = sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)

        # return the symbol objects of the top entries from our sorted collection
        # sortedByDollarVolume = sorted(filtered_stocks, key=lambda x: x.DollarVolume, reverse=True) 
        # top = sortedByDollarVolume[:self.__numberOfSymbols]
        # for i in top:
        #     self.AddEquity(i.Symbol, Resolution.Daily)

        # return [i.Symbol for i in top]
            # self.AddSecurity

        # for x in filtered:
        #     if not x.Symbol in self.ActiveSecurities:
        #         self.AddSecurity(x.Symbol, Resolution.Daily) # TODO: finer resolution for stop loss?

        #         self.short_sma[x.Symbol] = self.SMA(x.Symbol, 50, Resolution.Daily)
        #         self.long_sma[x.Symbol] = self.SMA(x.Symbol, 200, Resolution.Daily)
        #         self.rsi[x.Symbol] = self.RSI(x.Symbol, 14, MovingAverageType.Simple, Resolution.Daily)

        #     # self.short_sma = { x: self.SMA(x.Symbol, 50, Resolution.Daily) for x in filtered }
        #     # self.long_sma = { x: self.SMA(x.Symbol, 200, Resolution.Daily) for x in filtered }
        #     # self.rsi = { x: self.RSI(x.Symbol, 14, MovingAverageType.Simple, Resolution.Daily) for x in filtered }

        #     # self.are_trackers_initialised = True

        for cf in filtered:
            if cf.Symbol not in self.symbol_data:
                self.symbol_data[cf.Symbol] = SymbolData(cf.Symbol)

            data = self.symbol_data[cf.Symbol]
            data.update(cf.EndTime, cf.AdjustedPrice)

        return [x.Symbol for x in filtered]

    def FineSelectionFunction(self, fine: List[FineFundamental]) -> List[Symbol]:
        # selected = [x.Symbol for x in fine if
        #     x.ValuationRatios.PERatio < 15 and
        #     x.AssetClassification.GrowthScore > 0.15 and
        
        #     self.short_sma[x.Symbol].IsReady and self.long_sma[x.Symbol].IsReady and
        #     self.short_sma[x.Symbol].Current.Value > self.long_sma[x].Current.Value and 

        #     self.rsi[x.Symbol].IsReady and
        #     self.rsi[x.Symbol].Current.Value > 0
        # ]

        # if len(selected) > 0:
        #     self.Log(len(selected))
        #     self.Log(selected[0])

        # return selected

        selected = []
        for ff in fine:
            data = self.symbol_data[ff.Symbol]
            should_select = (data.is_ready() and
                ff.ValuationRatios.PERatio < 20 and
                ff.AssetClassification.GrowthScore > 0.075 and
                data.fast_average.Current.Value > data.slow_average.Current.Value and
                data.rsi.Current.Value > 0)

            if should_select:
                selected.append(ff.Symbol)

        return selected


        # filtered_fine = [x for x in fine if x.ValuationRatios.PERatio 
        #                     and x.FinancialStatements.BalanceSheet.Cash.OneMonth
        #                     and x.FinancialStatements.BalanceSheet.CurrentLiabilities.OneMonth
        #                     and x.FinancialStatements.CashFlowStatement.FreeCashFlow.OneMonth]
        # sortedByfactor1 = sorted(filtered_fine, key=lambda x: x.ValuationRatios.PERatio, reverse=False)
        # sortedByfactor2 = sorted(filtered_fine, key=lambda x: x.FinancialStatements.CashFlowStatement.FreeCashFlow.OneMonth, reverse=True)
        # sortedByfactor3 = sorted(filtered_fine, key=lambda x: (x.FinancialStatements.BalanceSheet.Cash.OneMonth - x.FinancialStatements.BalanceSheet.CurrentLiabilities.OneMonth), reverse=True)
        # sortedByfactor4 = sorted(filtered_fine, key=lambda x: self.RSI(x.Symbol, 14))
        # self.Debug(f"STOCKS: {fine}")
        
        
        # stock_dict = {}
        
        # #filtered_fine = [x for x in fine if x.ValuationRatios.PERatio]
        # #sortedByfactor1 = sorted(filtered_fine, key=lambda x: x.ValuationRatios.PERatio, reverse=False)
        # sortedByfactor4 = sorted(filtered_fine, key=lambda x: self.RSI(x.symbol, 14))
        # num_stocks = len(filtered_fine)
        # for i,ele in enumerate(sortedByfactor1):
        #     rank1 = i
        #     rank2 = sortedByfactor2.index(ele)
        #     rank3 = sortedByfactor3.index(ele)
        #     rank4 = sortedByfactor4.index(ele)
        #     #score = [ceil(rank1/num_stocks)]
        #     score = [ceil(rank1/num_stocks),
        #             ceil(rank2/num_stocks),
        #             ceil(rank3/num_stocks),
        #             ceil(rank4/num_stocks)]
        #     score = sum(score)
        #     stock_dict[ele] = score
        # self.sorted_stock = sorted(stock_dict.items(), key=lambda d:d[1],reverse=True)
        # sorted_symbol = [self.sorted_stock[i][0] for i in range(len(self.sorted_stock))]
        # topFine = sorted_symbol[:self.__numberOfSymbolsFine]
        # self.chosen = []
        # self.Debug(f"CHOSEN: {stock_dict}")
        
        # for stock in topFine:
        #     # create a 15 day exponential moving average
        #     fast = self.SMA(stock.Symbol, 50, Resolution.Daily);

        #     # create a 30 day exponential moving average
        #     slow = self.SMA(stock.Symbol, 200, Resolution.Daily);
        #     if fast > slow:
        #         self.rsi = self.RSI(stock.Symbol, 14)
        #         if self.rsi < 30 and stock.Symbol not in self.Portfolio:
        #             self.chosen.append(stock)
        #         elif self.rsi >= 30 and self.rsi < 70 and stock.Symbol in self.Portfolio:
        #             self.chosen.append(stock)
        # self.Debug(f"TOP FINE: {topFine}")
        # self.Debug(f"CHOSEN: {self.chosen}")
        
        # return [x.Symbol for x in self.chosen]

    def Rebalance(self):
        if self.Time.month != 1 and self.Time.month != 7:
            return
        
        self.Log('rebalancing!')

        self.Log('self.Portfolio')
        for s in self.Portfolio.Keys:
            self.Log(s)

        self.Log('self.Securities')
        for s in self.Securities.Keys:
            self.Log(s)

        self.Log('self.ActiveSecurities')
        for s in self.ActiveSecurities:
            self.Log(s)

        # for symbol in self.ActiveSecurities:
        #     self.Liquidate(symbol)
        #     self.Log(f'was active: {symbol}')

        # if len(self.UniverseSelection) > 0:
        #     percentage = 1 / len(self.Securities)
        #     for symbol in self.Securities:
        #         self.SetHoldings(symbol, percentage)

        #     self.Log('current securities:')
        #     for s in self.Securities:
        #         self.Log(f'{s}: {percentage}')


    def AllocatePortfolio(self, selection: List[str]): # TODO: is selection: List[], also is selection ordered? no
        # second, assume selection is ordered? or like [(a, score_a), (b, score_b)]

        # max allocation to one stock is 5-10%
        # keep a dictionary of sectors and ensure total sector 

        # liquidate everything
        self.Liquidate()

        for stock in selection[:10]:
            self.SetHoldings(stock, 0.1)

    def ScoreStock(self, stock) -> float:
        # given a stock return score between 0 and 1
        pass

    def OnSecuritiesChanged(self, changes: SecurityChanges):
        for security in changes.RemovedSecurities:
            self.selected_securities.remove(security)

        for security in changes.AddedSecurities:
            self.SetHoldings(security.Symbol, 0.01)
            self.selected_securities.append(security)

    def OnData(self, data: Slice):
        # if not self.Portfolio.Invested:
        #     # self.SetHoldings("SPY", 0.33)
        #     # self.SetHoldings("BND", 0.33)
        #     self.SetHoldings("AAPL", 0.33)
        
        pass
