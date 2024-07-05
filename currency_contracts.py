from ibapi.contract import Contract

def EurUsd():
    #! [cashcontract]
    contract = Contract()
    contract.symbol = "EUR"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    #! [cashcontract]
    return contract

def GbpUsd():
    #! [cashcontract]
    contract = Contract()
    contract.symbol = "GBP"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    #! [cashcontract]
    return contract

def AudUsd():
    #! [cashcontract]
    contract = Contract()
    contract.symbol = "AUD"
    contract.secType = "CASH"
    contract.currency = "USD"
    contract.exchange = "IDEALPRO"
    #! [cashcontract]
    return contract