from ibapi.client import *
from ibapi.wrapper import *
import time
import requests
import json
import currency_contracts
import os
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

window_size = (24 * 60) - 15 # 60 mins per hour, 24 hours per day minus 15 since all IB data apparently starts 15 mins late from the hour
duration = "1 D"
bar_size = "1 min"

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

    @iswrapper
    def nextValidId(self, orderId:int):
        super().nextValidId(orderId)
        logging.debug("setting nextValidOrderId: %d", orderId)
        self.nextValidOrderId = orderId
        
        #Load message queue
        self.reqAllOpenOrders() # Since we don't want to open multiple orders before one event
        self.reqAccountUpdates(True, os.getenv('ACCOUNT')) # To get current account balance
        self.reqContractDetails(1, currency_contracts.EurUsd())
        self.reqMarketDataType(1)
        self.reqMktData(2, currency_contracts.EurUsd(), "", True, False, []) # Only want one snapshot price
        # Historical Data for hedging
        app.reqHistoricalData(reqId=3,
                          contract=currency_contracts.EurUsd(), 
                          endDateTime="", 
                          durationStr=duration, 
                          barSizeSetting=bar_size,
                          whatToShow="BID_ASK", 
                          useRTH=0, 
                          formatDate=1, 
                          keepUpToDate=False, 
                          chartOptions=[])
        app.reqHistoricalData(reqId=4,
                          contract=currency_contracts.GbpUsd(), 
                          endDateTime="", 
                          durationStr=duration, 
                          barSizeSetting=bar_size, 
                          whatToShow="BID_ASK", 
                          useRTH=0, 
                          formatDate=1, 
                          keepUpToDate=False, 
                          chartOptions=[])
        app.reqHistoricalData(reqId=5,
                          contract=currency_contracts.AudUsd(), 
                          endDateTime="", 
                          durationStr=duration, 
                          barSizeSetting=bar_size, 
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
        longParentOrder.totalQuantity = 0.01
        longParentOrder.transmit = False
        
        longTakeProfit = Order()
        longTakeProfit.orderId = longParentOrder.orderId + 1
        longTakeProfit.parentId = longParentOrder.orderId
        longTakeProfit.action = "SELL"
        longTakeProfit.orderType = "LMT"
        longTakeProfit.totalQuantity = 0.01
        longTakeProfit.lmtPrice = self.ask + 0.00250 # 25 pips
        longTakeProfit.transmit = False

        longStopLoss = Order()
        longStopLoss.orderId = longParentOrder.orderId + 2
        longStopLoss.parentId = longParentOrder.orderId
        longStopLoss.action = "SELL"
        longStopLoss.orderType = "STP"
        longStopLoss.totalQuantity = 0.01
        longStopLoss.auxPrice = self.bid - 0.00250 # 25 pips
        # From Docs:
        #In this case, the low side order will be the last child being sent. Therefore, it needs to set this attribute to True 
        #to activate all its predecessors
        longStopLoss.transmit = True

        orders = [longParentOrder, longTakeProfit, longStopLoss]
        return orders
    
    def create_short_order(self):
        shortParentOrder = Order()
        shortParentOrder.orderId = self.nextValidOrderId+3
        shortParentOrder.action = "SELL"
        shortParentOrder.orderType = "MKT"
        shortParentOrder.totalQuantity = 0.01
        shortParentOrder.transmit = False
        
        shortTakeProfit = Order()
        shortTakeProfit.orderId = shortParentOrder.orderId + 4
        shortTakeProfit.parentId = shortParentOrder.orderId
        shortTakeProfit.action = "BUY"
        shortTakeProfit.orderType = "LMT"
        shortTakeProfit.totalQuantity = 0.01
        shortTakeProfit.lmtPrice = self.bid - 0.00250 # 25 pips
        shortTakeProfit.transmit = False

        shortStopLoss = Order()
        shortStopLoss.orderId = shortParentOrder.orderId + 5
        shortStopLoss.parentId = shortParentOrder.orderId
        shortStopLoss.action = "BUY"
        shortStopLoss.orderType = "STP"
        shortStopLoss.totalQuantity = 0.01
        shortStopLoss.auxPrice = self.ask + 0.0025 # 25 pips
        shortStopLoss.transmit = True

        orders = [shortParentOrder, shortTakeProfit, shortStopLoss]
        return orders

    def updateAccountValue(self, key: str, val: str, currency: str,accountName: str):
        if key == "CashBalance":
            self.cashbalance = val
            print("Cash Balance", currency, self.cashbalance)
    
    def contractDetails(self, reqId: int, contractDetails: ContractDetails):
        print(reqId)
        print("Min tick", contractDetails.minTick)
        print("Min size", contractDetails.minSize)
        print("Price Magnifider", contractDetails.priceMagnifier)
        print("Size increment", contractDetails.sizeIncrement)
        # Print out contract details properties

    def contractDetailsEnd(self, reqId: int):
        print("ContractDetailsEnd. ReqId:", reqId)

    def openOrder(self, orderId: OrderId, contract: Contract, order: Order, orderState: OrderState):
        self.openOrders.append(orderId)
    
    def tickPrice(self, reqId: TickerId, tickType: TickType, price: float, attrib: TickAttrib):
        tick_type = TickTypeEnum.to_str(tickType)
        if tick_type == "BID":
            self.bid = price
            print("self.bid", self.bid)
        if tick_type == "ASK":
            self.ask = price
            print("self.ask", self.ask)
        
        # print("Length of open orders is:", len(self.openOrders))
        # if self.bid > 0 and self.ask > 0 and len(self.openOrders) < 3:
        #     long_orders = self.create_long_order()
        #     for order in long_orders:
        #         print(order)
        #         self.placeOrder(order.orderId, currency_contracts.EurUsdFx(), order)
        #     short_orders = self.create_short_order()
        #     for order in short_orders:
        #         print(order)
        #         self.placeOrder(order.orderId, currency_contracts.EurUsdFx(), order)
        #     time.sleep(5)
        # self.disconnect() # move to the end of the last function being called

    def historicalData(self, reqId, bar):
        match reqId:
            case 3:
                self.eur_usd_prices.append([bar.date, bar.close])
            case 4:
                self.gbp_usd_prices.append([bar.date, bar.close])
            case 5:
                self.aud_usd_prices.append([bar.date, bar.close])

        if len(self.eur_usd_prices) > window_size-1 and len(self.gbp_usd_prices) > window_size-1 and len(self.aud_usd_prices) > window_size-1:
                    eur_df = pd.DataFrame(self.eur_usd_prices)
                    eur_df.columns=["time","euroClose"]

                    gbp_df = pd.DataFrame(self.gbp_usd_prices)
                    gbp_df.columns=["time","gbpClose"]

                    aud_df = pd.DataFrame(self.aud_usd_prices)
                    aud_df.columns=["time", "audClose"]
                    
                    eur_df['gbpClose'] = gbp_df['gbpClose']
                    eur_df['audClose'] = aud_df['audClose']
                    print(eur_df)
                    print(eur_df.corr(method="pearson", numeric_only=True))



# For historical data
#app.reqHeadTimeStamp(1, app.EurUsdFx(), "BID_ASK", 1, 1)

def timeToBuy():
    get = requests.get("https://calendar-api-v5-calendar-scraper.apps.okd4.csh.rit.edu/nextEventSoon")
    return json.loads(get.text)['buy']

# while True:
#     if timeToBuy():
#         app = TradeApp()
#         app.connect("127.0.0.1", 4001, clientId=0)
#         time.sleep(1)
#         app.run()
#     time.sleep(60)

app = TradeApp()
app.connect("127.0.0.1", 4001, clientId=0)
time.sleep(1)
app.run()