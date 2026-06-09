class TradingMemory:

    def __init__(self):
        self.memory = []

    def add_trade(self, trade):

        self.memory.append(trade)

    def get_recent_trades(self):

        return self.memory[-10:]