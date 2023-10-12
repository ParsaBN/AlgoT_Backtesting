#region imports
from AlgorithmImports import *
#endregion
from System.Collections.Generic import List
from QuantConnect.Data.UniverseSelection import *
import operator
from math import ceil,floor

class UpgradedGreenHippopotamus(QCAlgorithm):
    def Initialize(self):
        '''Initialise the data and resolution required, as well as the cash and start-end dates for your algorithm. All algorithms must initialized.'''

        self.SetStartDate(2014,1,1)  #Set Start Date
        self.SetEndDate(2015,1,1)    #Set End Date
        self.SetCash(50000)            #Set Strategy Cash

        # what resolution should the data *added* to the universe be?
        self.UniverseSettings.Resolution = Resolution.Daily

        # this add universe method accepts two parameters:
        # - coarse selection function: accepts an IEnumerable<CoarseFundamental> and returns an IEnumerable<Symbol>
        # - fine selection function: accepts an IEnumerable<FineFundamental> and returns an IEnumerable<Symbol>
        self.AddUniverse(self.CoarseSelectionFunction, self.FineSelectionFunction)

        self.__numberOfSymbols = 500
        self.__numberOfSymbolsFine = 50
        self._changes = None
        self.symbols = []


    # sort the data by daily dollar volume and take the top 'NumberOfSymbols'
    def CoarseSelectionFunction(self, coarse):
        # sort descending by daily dollar volume
        #sortedByDollarVolume = sorted(coarse, key=lambda x: x.DollarVolume, reverse=True)
        filtered_stocks = [x for x in coarse if x.HasFundamentalData]
        # return the symbol objects of the top entries from our sorted collection
        sortedByDollarVolume = sorted(filtered_stocks, key=lambda x: x.DollarVolume, reverse=True) 
        top = sortedByDollarVolume[:self.__numberOfSymbols]
        for i in top:
            self.AddEquity(i.Symbol, Resolution.Daily)
        return [i.Symbol for i in top]
        
    def FineSelectionFunction(self, fine):
        
        filtered_fine = [x for x in fine if x.ValuationRatios.PERatio 
                            and x.FinancialStatements.BalanceSheet.Cash.OneMonth
                            and x.FinancialStatements.BalanceSheet.CurrentLiabilities.OneMonth
                            and x.FinancialStatements.CashFlowStatement.FreeCashFlow.OneMonth]
        sortedByfactor1 = sorted(filtered_fine, key=lambda x: x.ValuationRatios.PERatio, reverse=False)
        sortedByfactor2 = sorted(filtered_fine, key=lambda x: x.FinancialStatements.CashFlowStatement.FreeCashFlow.OneMonth, reverse=True)
        sortedByfactor3 = sorted(filtered_fine, key=lambda x: (x.FinancialStatements.BalanceSheet.Cash.OneMonth - x.FinancialStatements.BalanceSheet.CurrentLiabilities.OneMonth), reverse=True)
        sortedByfactor4 = sorted(filtered_fine, key=lambda x: self.RSI(x.Symbol, 14))
        self.Debug(f"STOCKS: {fine}")
        
        
        stock_dict = {}
        
        #filtered_fine = [x for x in fine if x.ValuationRatios.PERatio]
        #sortedByfactor1 = sorted(filtered_fine, key=lambda x: x.ValuationRatios.PERatio, reverse=False)
        #sortedByfactor4 = sorted(filtered_fine, key=lambda x: self.RSI(x.symbol, 14))
        num_stocks = len(filtered_fine)
        for i,ele in enumerate(sortedByfactor1):
            rank1 = i
            rank2 = sortedByfactor2.index(ele)
            rank3 = sortedByfactor3.index(ele)
            rank4 = sortedByfactor4.index(ele)
            #score = [ceil(rank1/num_stocks)]
            score = [ceil(rank1/num_stocks),
                    ceil(rank2/num_stocks),
                    ceil(rank3/num_stocks),
                    ceil(rank4/num_stocks)]
            score = sum(score)
            stock_dict[ele] = score
        self.sorted_stock = sorted(stock_dict.items(), key=lambda d:d[1],reverse=True)
        sorted_symbol = [self.sorted_stock[i][0] for i in range(len(self.sorted_stock))]
        topFine = sorted_symbol[:self.__numberOfSymbolsFine]
        self.chosen = []
        self.Debug(f"CHOSEN: {stock_dict}")
        
        for stock in topFine:
            # create a 15 day exponential moving average
            fast = self.SMA(stock.Symbol, 50, Resolution.Daily);

            # create a 30 day exponential moving average
            slow = self.SMA(stock.Symbol, 200, Resolution.Daily);
            if fast > slow:
                self.rsi = self.RSI(stock.Symbol, 14)
                if self.rsi < 30 and stock.Symbol not in self.Portfolio:
                    self.chosen.append(stock)
                elif self.rsi >= 30 and self.rsi < 70 and stock.Symbol in self.Portfolio:
                    self.chosen.append(stock)
        self.Debug(f"TOP FINE: {topFine}")
        self.Debug(f"CHOSEN: {self.chosen}")
        
        return [i.Symbol for i in self.chosen]

    def OnData(self, data):
        # if we have no changes, do nothing
        #if self._changes is None: return

        # liquidate removed securities
        #for security in self._changes.RemovedSecurities:
        ##    if security.Invested:
        #        self.Liquidate(security.Symbol)

        for security in self.chosen:
            if not (self.Portfolio[security.Symbol].Invested):
                self.SetHoldings(security.Symbol, 0.05)
        
        for symbol, security in self.Portfolio.items():
            if symbol not in self.chosen:
                self.Liquidate(security.Symbol)
        # we want 5% allocation in each security in our universe
        #for security in self._changes.AddedSecurities:
        #    self.Debug(f"ADDING SECURITY TO PORTFOLIO: {security.Symbol}")
        #    self.SetHoldings(security.Symbol, 0.05)

        self._changes = None


    # this event fires whenever we have changes to our universe
    def OnSecuritiesChanged(self, changes):
        self._changes = changes
