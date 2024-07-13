from ibapi.client import *
from ibapi.wrapper import *
import time
import requests
import json
import currency_contracts
import os
import pandas as pd
import statsmodels.api as sm
from dotenv import load_dotenv

load_dotenv()

class TradeApp(EWrapper, EClient): 
    def __init__(self): 
        EClient.__init__(self, self)
        self.nextValidOrderId = None
        self.permId2ord = {}
        self.bid = 0
        self.ask = 0
        self.cashbalance = 0
        self.openOrders = []
        self.eur_usd_prices = []
        self.gbp_usd_prices = []
        self.aud_usd_prices = []
        self.gbp_ratio = 0
        self.aud_ratio = 0
        self.duration = "1 M"
        self.bar_size = "1 hour"
        self.dollar_quantity_factor = 100 # 1$ in an order is converted to 1/10 = 0.01 in the quantity field
        self.long_dollar_amount = 10
        self.long_quantity = self.long_dollar_amount / self.dollar_quantity_factor # 10/100 = quantity of 0.1
        self.profit_target = 0.005 # 50 pips
        self.sl_target = 0.0025 # 25 pips

    @iswrapper
    def nextValidId(self, orderId:int):
        super().nextValidId(orderId)
        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        
        #Load message queue
        self.reqAllOpenOrders() # Since we don't want to open multiple orders before one event
        self.reqAccountUpdates(True, os.getenv('ACCOUNT')) # To get current account balance
        self.reqMarketDataType(1)
        self.reqMktData(2, currency_contracts.EurUsd(), "", True, False, []) # Only want one snapshot price
        # Historical Data for hedging
        app.reqHistoricalData(reqId=3,
                          contract=currency_contracts.EurUsd(), 
                          endDateTime="", 
                          durationStr=self.duration, 
                          barSizeSetting=self.bar_size,
                          whatToShow="BID_ASK", 
                          useRTH=0, 
                          formatDate=1, 
                          keepUpToDate=False, 
                          chartOptions=[])
        app.reqHistoricalData(reqId=4,
                          contract=currency_contracts.GbpUsd(), 
                          endDateTime="", 
                          durationStr=self.duration, 
                          barSizeSetting=self.bar_size, 
                          whatToShow="BID_ASK", 
                          useRTH=0, 
                          formatDate=1, 
                          keepUpToDate=False, 
                          chartOptions=[])
        app.reqHistoricalData(reqId=5,
                          contract=currency_contracts.AudUsd(), 
                          endDateTime="", 
                          durationStr=self.duration, 
                          barSizeSetting=self.bar_size, 
                          whatToShow="BID_ASK", 
                          useRTH=0, 
                          formatDate=1, 
                          keepUpToDate=False, 
                          chartOptions=[])
    
    
    def create_long_order(self):
        longParentOrder = Order()
        longParentOrder.orderId = self.nextValidOrderId
        longParentOrder.action = "BUY"
        longParentOrder.orderType = "MKT"
        longParentOrder.totalQuantity = self.long_quantity
        longParentOrder.tif = "GTC"
        longParentOrder.transmit = False
        
        longTakeProfit = Order()
        longTakeProfit.orderId = longParentOrder.orderId + 1
        longTakeProfit.parentId = longParentOrder.orderId
        longTakeProfit.action = "SELL"
        longTakeProfit.orderType = "LMT"
        longTakeProfit.totalQuantity = self.long_quantity
        longTakeProfit.lmtPrice = self.ask + self.profit_target
        longTakeProfit.tif = "GTC"
        longTakeProfit.transmit = False

        longStopLoss = Order()
        longStopLoss.orderId = longParentOrder.orderId + 2
        longStopLoss.parentId = longParentOrder.orderId
        longStopLoss.action = "SELL"
        longStopLoss.orderType = "STP"
        longStopLoss.totalQuantity = self.long_quantity
        longStopLoss.tif = "GTC"
        longStopLoss.auxPrice = self.bid - self.sl_target
        # From Docs:
        #In this case, the low side order will be the last child being sent. Therefore, it needs to set this attribute to True 
        #to activate all its predecessors
        longStopLoss.transmit = True

        orders = [longParentOrder, longTakeProfit, longStopLoss]
        return orders
    
    def create_short_gbp_order(self):
        # Short GBP Order
        short_gbp_quantity = round(self.gbp_ratio * self.long_quantity, 2)
        short_gbp_lmt = round(self.gbp_ratio * self.profit_target, 5)
        short_gbp_stop = round(self.gbp_ratio * self.sl_target, 5)

        shortParentOrder = Order()
        shortParentOrder.orderId = self.nextValidOrderId+3
        shortParentOrder.action = "SELL"
        shortParentOrder.orderType = "MKT"
        shortParentOrder.totalQuantity = short_gbp_quantity
        shortParentOrder.tif = "GTC"
        shortParentOrder.transmit = False
        
        shortTakeProfit = Order()
        shortTakeProfit.orderId = shortParentOrder.orderId + 1
        shortTakeProfit.parentId = shortParentOrder.orderId
        shortTakeProfit.action = "BUY"
        shortTakeProfit.orderType = "LMT"
        shortTakeProfit.totalQuantity = short_gbp_quantity
        shortTakeProfit.lmtPrice = self.bid - short_gbp_lmt
        shortTakeProfit.tif = "GTC"
        shortTakeProfit.transmit = False

        shortStopLoss = Order()
        shortStopLoss.orderId = shortParentOrder.orderId + 2
        shortStopLoss.parentId = shortParentOrder.orderId
        shortStopLoss.action = "BUY"
        shortStopLoss.orderType = "STP"
        shortStopLoss.totalQuantity = short_gbp_quantity
        shortStopLoss.auxPrice = self.ask + short_gbp_stop
        shortStopLoss.tif = "GTC"
        shortStopLoss.transmit = True

        orders = [shortParentOrder, shortTakeProfit, shortStopLoss]
        return orders
    
    def create_short_aud_order(self):
        # Short GBP Order
        short_aud_quantity = round(self.aud_ratio * self.long_quantity, 2)
        short_aud_lmt = round(self.aud_ratio * self.profit_target, 5)
        short_aud_stop = round(self.aud_ratio * self.sl_target, 5)

        shortParentOrder = Order()
        shortParentOrder.orderId = self.nextValidOrderId+6
        shortParentOrder.action = "SELL"
        shortParentOrder.orderType = "MKT"
        shortParentOrder.totalQuantity = short_aud_quantity
        shortParentOrder.tif = "GTC"
        shortParentOrder.transmit = False
        
        shortTakeProfit = Order()
        shortTakeProfit.orderId = shortParentOrder.orderId + 1
        shortTakeProfit.parentId = shortParentOrder.orderId
        shortTakeProfit.action = "BUY"
        shortTakeProfit.orderType = "LMT"
        shortTakeProfit.totalQuantity = short_aud_quantity
        shortTakeProfit.lmtPrice = self.bid - short_aud_lmt
        shortTakeProfit.tif = "GTC"
        shortTakeProfit.transmit = False

        shortStopLoss = Order()
        shortStopLoss.orderId = shortParentOrder.orderId + 2
        shortStopLoss.parentId = shortParentOrder.orderId
        shortStopLoss.action = "BUY"
        shortStopLoss.orderType = "STP"
        shortStopLoss.totalQuantity = short_aud_quantity
        shortStopLoss.auxPrice = self.ask + short_aud_stop
        shortStopLoss.tif = "GTC"
        shortStopLoss.transmit = True

        orders = [shortParentOrder, shortTakeProfit, shortStopLoss]
        return orders

    def updateAccountValue(self, key: str, val: str, currency: str,accountName: str):
        if key == "CashBalance":
            self.cashbalance = val
            print("Cash Balance", currency, self.cashbalance)

    def contractDetailsEnd(self, reqId: int):
        print("ContractDetailsEnd. ReqId:", reqId)

    def openOrder(self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState):
        self.openOrders.append(orderId)
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        tick_type = TickTypeEnum.to_str(tickType)
        if tick_type == "BID":
            self.bid = price
            print("bid", self.bid)
        if tick_type == "ASK":
            self.ask = price
            print("ask", self.ask)

    def historicalData(self, reqId, bar):
        match reqId:
            case 3:
                self.eur_usd_prices.append([bar.date, bar.close])
            case 4:
                self.gbp_usd_prices.append([bar.date, bar.close])
            case 5:
                self.aud_usd_prices.append([bar.date, bar.close])

    def historicalDataEnd(self, reqId: int, start: str, end: str):
        if len(self.eur_usd_prices) > 0 and len(self.gbp_usd_prices) > 0 and len(self.aud_usd_prices) > 0:
            eur_df = pd.DataFrame(self.eur_usd_prices)
            eur_df.columns=["time","euroClose"]

            gbp_df = pd.DataFrame(self.gbp_usd_prices)
            gbp_df.columns=["time","gbpClose"]

            aud_df = pd.DataFrame(self.aud_usd_prices)
            aud_df.columns=["time", "audClose"]
            
            eur_df['gbpClose'] = gbp_df['gbpClose']
            eur_df['audClose'] = aud_df['audClose']

            eur_df['euroReturn'] = eur_df['euroClose'].pct_change()*100
            eur_df['gbpReturn'] = eur_df['gbpClose'].pct_change()*100
            eur_df['audReturn'] = eur_df['audClose'].pct_change()*100
            eur_df.dropna(inplace=True)
            eur_df = sm.add_constant(eur_df)
            model = sm.OLS(eur_df['euroReturn'], eur_df[['const', 'gbpReturn', 'audReturn']]).fit()
            hedge_ratios = model.params[['gbpReturn', 'audReturn']]
            print(eur_df)
            self.gbp_ratio = hedge_ratios['gbpReturn']
            self.aud_ratio = hedge_ratios['audReturn']
            print("GBP ratio", self.gbp_ratio)
            print("AUD ratio", self.aud_ratio)
            long_orders = self.create_long_order()
            for order in long_orders:
                print(order)
                self.placeOrder(order.orderId, currency_contracts.EurUsd(), order)
            short_gbp_orders = self.create_short_gbp_order()
            for order in short_gbp_orders:
                print(order)
                self.placeOrder(order.orderId, currency_contracts.GbpUsd(), order)
            short_aud_orders = self.create_short_aud_order()
            for order in short_aud_orders:
                print(order)
                self.placeOrder(order.orderId, currency_contracts.AudUsd(), order)
            time.sleep(5)
            self.disconnect() # move to the end of the last function being called




def timeToBuy():
    get = requests.get("https://calendar-api-v5-calendar-scraper.apps.okd4.csh.rit.edu/nextEventSoon")
    return json.loads(get.text)['buy']

# while True:
#     try:
#         if timeToBuy():
#             app = TradeApp()
#             app.connect("127.0.0.1", 4001, clientId=0)
#             time.sleep(1)
#             app.run()
#         time.sleep(60)
#     except requests.RequestException or requests.ConnectionError or requests.HTTPError:
#         time.sleep(10)
#         continue

app = TradeApp()
app.connect("127.0.0.1", 4001, clientId=0)
time.sleep(1)
app.run()