from __future__ import annotations

import os

APP_NAME = "GARIBALDI MARKET ORACLE™"
DATABASE_PATH = os.getenv("DATABASE_PATH", "oracle.db")
STARTING_BALANCE = float(os.getenv("STARTING_BALANCE", "2000"))
STOCK_STARTING_BALANCE = float(os.getenv("STOCK_STARTING_BALANCE", "2000"))
CRYPTO_STARTING_BALANCE = float(os.getenv("CRYPTO_STARTING_BALANCE", "2000"))
API_CACHE_TTL_SECONDS = max(30, int(os.getenv("API_CACHE_TTL_SECONDS", "300")))
ROTATION_ENABLED = os.getenv("ROTATION_ENABLED", "true").lower() == "true"
ROTATION_MIN_SCORE_GAP = float(os.getenv("ROTATION_MIN_SCORE_GAP", "8"))
OPPORTUNITY_LIMIT = max(3, int(os.getenv("OPPORTUNITY_LIMIT", "12")))
WORKER_INTERVAL_SECONDS = max(60, int(os.getenv("WORKER_INTERVAL_SECONDS", "300")))
ENABLE_AUTOTRADE = os.getenv("ENABLE_AUTOTRADE", "true").lower() == "true"
ENABLE_NEWS = os.getenv("ENABLE_NEWS", "true").lower() == "true"
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() == "true"
AUTO_UPGRADE_EMPTY_PORTFOLIOS = (
    os.getenv("AUTO_UPGRADE_EMPTY_PORTFOLIOS", "true").lower() == "true"
)

# Broad economic coverage using liquid ETFs plus representative companies.
# The cash worker scans the major indexes, every primary U.S. sector, commodities,
# infrastructure, transportation, agriculture, defense, technology, healthcare,
# consumer markets, real estate, finance, energy, and emerging industries.
CASH_WATCHLIST = {
    # Broad market and style
    "SPY": "S&P 500 ETF",
    "QQQ": "Nasdaq-100 ETF",
    "IWM": "Russell 2000 ETF",
    "DIA": "Dow Jones ETF",
    "RSP": "Equal Weight S&P 500 ETF",
    "VTV": "Value ETF",
    "VUG": "Growth ETF",

    # Primary economic sectors
    "XLK": "Technology ETF",
    "XLF": "Financial ETF",
    "XLE": "Energy ETF",
    "XLV": "Healthcare ETF",
    "XLI": "Industrials ETF",
    "XLY": "Consumer Discretionary ETF",
    "XLP": "Consumer Staples ETF",
    "XLU": "Utilities ETF",
    "XLB": "Materials ETF",
    "XLRE": "Real Estate Sector ETF",
    "XLC": "Communication Services ETF",

    # Money, rates, currency, and real estate
    "TLT": "Long Treasury ETF",
    "IEF": "Intermediate Treasury ETF",
    "HYG": "High Yield Bond ETF",
    "UUP": "US Dollar ETF",
    "VNQ": "Real Estate ETF",
    "ITB": "Home Construction ETF",

    # Precious metals, industrial metals, mining, and strategic materials
    "GLD": "Gold ETF",
    "SLV": "Silver ETF",
    "COPX": "Copper Miners ETF",
    "PICK": "Global Metals and Mining ETF",
    "LIT": "Lithium and Battery Technology ETF",
    "REMX": "Rare Earth and Strategic Metals ETF",
    "URA": "Uranium ETF",

    # Oil, gas, clean energy, and utilities
    "XOM": "Exxon Mobil",
    "CVX": "Chevron",
    "OIH": "Oil Services ETF",
    "UNG": "Natural Gas ETF",
    "ICLN": "Clean Energy ETF",
    "TAN": "Solar ETF",
    "NEE": "NextEra Energy",

    # Technology, AI, semiconductors, cloud, cyber, and robotics
    "AAPL": "Apple",
    "MSFT": "Microsoft",
    "NVDA": "NVIDIA",
    "AMD": "AMD",
    "AVGO": "Broadcom",
    "SMH": "Semiconductor ETF",
    "AMZN": "Amazon",
    "META": "Meta",
    "GOOGL": "Alphabet",
    "PLTR": "Palantir",
    "CLOU": "Cloud Computing ETF",
    "CIBR": "Cybersecurity ETF",
    "BOTZ": "Robotics and AI ETF",
    "ARKQ": "Autonomous Technology ETF",
    "IONQ": "IonQ",
    "GLW": "Corning",

    # Aerospace, space, defense, infrastructure, and construction
    "ITA": "Aerospace and Defense ETF",
    "PPA": "Aerospace and Defense ETF",
    "RKLB": "Rocket Lab",
    "XAR": "Aerospace and Defense ETF",
    "PAVE": "US Infrastructure ETF",
    "CAT": "Caterpillar",
    "DE": "Deere",

    # Agriculture, food, staples, retail, and restaurants
    "MOO": "Agribusiness ETF",
    "DBA": "Agriculture ETF",
    "ADM": "Archer Daniels Midland",
    "WMT": "Walmart",
    "COST": "Costco",
    "XLP": "Consumer Staples ETF",
    "MCD": "McDonald's",
    "SBUX": "Starbucks",

    # Banks, insurance, payments, and financial services
    "JPM": "JPMorgan",
    "BAC": "Bank of America",
    "KRE": "Regional Banks ETF",
    "KIE": "Insurance ETF",
    "V": "Visa",
    "MA": "Mastercard",

    # Healthcare, pharmaceuticals, biotech, and medical devices
    "LLY": "Eli Lilly",
    "JNJ": "Johnson & Johnson",
    "PFE": "Pfizer",
    "IBB": "Biotechnology ETF",
    "IHI": "Medical Devices ETF",

    # Transportation, railroads, logistics, shipping, and airlines
    "IYT": "Transportation ETF",
    "UNP": "Union Pacific",
    "CSX": "CSX",
    "FDX": "FedEx",
    "UPS": "UPS",
    "JETS": "Airlines ETF",
    "SEA": "Global Shipping ETF",

    # Autos and electric vehicles
    "TSLA": "Tesla",
    "F": "Ford",
    "GM": "General Motors",
    "DRIV": "Autonomous and Electric Vehicles ETF",

    # Water and essential infrastructure
    "PHO": "Water Resources ETF",
}

CRYPTO_WATCHLIST = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ethereum",
    "SOL-USD": "Solana",
    "XRP-USD": "XRP",
    "DOGE-USD": "Dogecoin",
    "ADA-USD": "Cardano",
    "AVAX-USD": "Avalanche",
    "LINK-USD": "Chainlink",
    "LTC-USD": "Litecoin",
    "DOT-USD": "Polkadot",
    "UNI-USD": "Uniswap",
    "AAVE-USD": "Aave",
    "ATOM-USD": "Cosmos",
    "NEAR-USD": "NEAR Protocol",
}

WATCHLISTS = {
    "cash": CASH_WATCHLIST,
    "crypto": CRYPTO_WATCHLIST,
}

# Aggressive simulated-trading defaults. Railway environment variables can
# override every value without another code change.
MAX_POSITION_FRACTION = float(os.getenv("MAX_POSITION_FRACTION", "0.35"))
MIN_TRADE_VALUE = float(os.getenv("MIN_TRADE_VALUE", "1.00"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "14"))
STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "0.06"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.10"))
TRAILING_STOP_PCT = float(os.getenv("TRAILING_STOP_PCT", "0.045"))
SIGNAL_BUY_THRESHOLD = float(os.getenv("SIGNAL_BUY_THRESHOLD", "0.58"))
SIGNAL_SELL_THRESHOLD = float(os.getenv("SIGNAL_SELL_THRESHOLD", "0.42"))
TRADE_COOLDOWN_MINUTES = int(os.getenv("TRADE_COOLDOWN_MINUTES", "15"))
MAX_DAILY_DRAWDOWN_PCT = float(os.getenv("MAX_DAILY_DRAWDOWN_PCT", "0.12"))
MIN_COUNCIL_AGREEMENT = float(os.getenv("MIN_COUNCIL_AGREEMENT", "0.52"))

# Extra settings consumed by oracle_bot.py through `from config import *`.
FLEXIBLE_COOLDOWN_FACTOR = float(os.getenv("FLEXIBLE_COOLDOWN_FACTOR", "0.10"))
HIGH_CONFIDENCE_THRESHOLD = float(
    os.getenv("HIGH_CONFIDENCE_THRESHOLD", "0.48")
)
HIGH_SCORE_THRESHOLD = float(os.getenv("HIGH_SCORE_THRESHOLD", "52.0"))
EXTRA_OPEN_POSITIONS = int(os.getenv("EXTRA_OPEN_POSITIONS", "6"))
MIN_CASH_RESERVE_PCT = float(os.getenv("MIN_CASH_RESERVE_PCT", "0.01"))
MAX_TRADE_VALUE_PCT = float(os.getenv("MAX_TRADE_VALUE_PCT", "0.35"))

# Oracle Quantitative Trade Standard (institutional-style, retail-executable)
ENABLE_QUANT_TRADE_STANDARD = os.getenv("ENABLE_QUANT_TRADE_STANDARD", "true").lower() == "true"
QUANT_MIN_QUALITY = float(os.getenv("QUANT_MIN_QUALITY", "68.0"))
QUANT_MIN_NET_EV_PCT = float(os.getenv("QUANT_MIN_NET_EV_PCT", "0.001"))
QUANT_MAX_SPREAD_PCT = float(os.getenv("QUANT_MAX_SPREAD_PCT", "0.006"))
QUANT_MAX_SLIPPAGE_PCT = float(os.getenv("QUANT_MAX_SLIPPAGE_PCT", "0.005"))
QUANT_ADVERSE_REJECT_SCORE = float(os.getenv("QUANT_ADVERSE_REJECT_SCORE", "70.0"))
