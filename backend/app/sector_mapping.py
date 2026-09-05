"""
Sector mapping for Indian stocks
This defines which sector each stock belongs to
"""

SECTORS = {
    "Banking": [
        "SBIN", "HDFC", "ICICIBANK", "KOTAKBANK", 
        "AXISBANK", "YESBANK", "BANKBARODA", "PNB",
        "IDFCFIRSTB", "FEDERALBNK", "INDUSINDBK"
    ],
    "IT": [
        "TCS", "INFY", "WIPRO", "HCLTECH", "TECHM",
        "LTTS", "MINDTREE", "MPHASIS", "COFORGE"
    ],
    "Oil & Gas": [
        "RELIANCE", "BPCL", "ONGC", "IOCL", "GAIL",
        "HINDPETRO", "PETRONET", "GUJGAS"
    ],
    "FMCG": [
        "HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA",
        "MARICO", "DABUR", "GODREJCP"
    ],
    "Auto": [
        "TATAMOTORS", "MARUTI", "HEROMOTOCO", "BAJAJ-AUTO",
        "ESCORTS", "ASHOKLEY", "TVSMOTOR", "EICHERMOT"
    ],
    "Pharma": [
        "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
        "LUPIN", "AUROPHARMA", "APOLLOHOSP"
    ],
    "Metals": [
        "TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL",
        "NALCO", "SAIL", "JINDALSTEL"
    ],
    "Telecom": [
        "BHARTIARTL", "JIOFIN", "IDEA", "TATACOMM"
    ],
    "Consumer Durables": [
        "TITAN", "VOLTAS", "HAVELLS", "WHIRLPOOL",
        "BLUESTAR", "CROMPTON"
    ],
    "Real Estate": [
        "DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE"
    ]
}

def get_sector(symbol: str) -> str:
    """Get the sector for a given symbol"""
    for sector, stocks in SECTORS.items():
        if symbol in stocks:
            return sector
    return "Unknown"

def get_sector_stocks(sector: str) -> list:
    """Get all stocks in a sector"""
    return SECTORS.get(sector, [])

def get_all_sectors() -> list:
    """Get all sector names"""
    return list(SECTORS.keys())

def get_sector_breakdown() -> dict:
    """Get sector breakdown with count of stocks"""
    return {sector: len(stocks) for sector, stocks in SECTORS.items()}