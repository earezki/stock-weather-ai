import yfinance as yf
import pandas as pd
import logging

from toolkit.cache import memory, timestamp_key
from options import options

from tenacity import retry, stop_after_attempt, wait_exponential

from langchain.prompts import PromptTemplate

logger = logging.getLogger(__name__)

@memory.cache
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def _get_company_financial_data(ticker_symbol, timestamp_key):
    """
    Retrieves a comprehensive set of financial data for a given company.

    Args:
        ticker_symbol (str): The stock ticker symbol (e.g., 'AAPL' for Apple).
        timestamp_key: An integer used as a cache key to avoid redundant requests.

    Returns:
        dict: A dictionary containing various financial data points.
    """
    company_data = {}
    ticker = yf.Ticker(ticker_symbol)

    logger.info(f"Fetching data for {ticker_symbol}...")

    company_data = {}
    ticker = yf.Ticker(ticker_symbol)

    logger.info(f"Fetching lean data for {ticker_symbol}...")

    KEY_INCOME_STATEMENT_METRICS = [
        'Total Revenue', 'Gross Profit', 'Operating Income',
        'Net Income', 'Diluted EPS', 'Research And Development',
        'Selling General And Administration', 'Tax Provision'
    ]
    KEY_BALANCE_SHEET_METRICS = [
        'Total Assets', 'Total Liabilities', 'Stockholders Equity',
        'Cash Cash Equivalents And Short Term Investments', 'Total Debt',
        'Retained Earnings', 'Net PPE'
    ]
    KEY_CASH_FLOW_METRICS = [
        'Operating Cash Flow', 'Investing Cash Flow', 'Financing Cash Flow',
        'Capital Expenditure', 'Dividends Paid', 'Repurchase Of Capital Stock',
        'Free Cash Flow'
    ]

    try:
        info = ticker.info
        company_data['Summary Profile'] = {
            'Long Name': info.get('longName'),
            'Sector': info.get('sector'),
            'Industry': info.get('industry'),
            'Full Time Employees': info.get('fullTimeEmployees'),
            'Business Summary': info.get('longBusinessSummary'),
            'Market Cap': info.get('marketCap'),
            'Current Price': info.get('currentPrice'),
            'PE Ratio (TTM)': info.get('trailingPE'),
            'Forward PE': info.get('forwardPE'),
            'Dividend Yield': info.get('dividendYield'),
            'Beta': info.get('beta'),
            '52 Week High': info.get('fiftyTwoWeekHigh'),
            '52 Week Low': info.get('fiftyTwoWeekLow'),
            'Debt to Equity': info.get('debtToEquity'),
            'Return on Equity': info.get('returnOnEquity'),
            'Gross Margins': info.get('grossMargins')
        }
        logger.info("Fetched company profile.")
    except Exception as e:
        logger.error(f"Error fetching company profile: {e}")
        company_data['Summary Profile'] = "Could not retrieve summary profile."

    try:
        hist_data = ticker.history(period="5y", interval="1mo", auto_adjust=True)
        hist_data.index = hist_data.index.strftime('%Y-%m-%d')
        company_data['Historical Stock Data (Last 5 Years - Monthly)'] = hist_data.to_dict()
        logger.info("Fetched monthly historical stock data.")
    except Exception as e:
        logger.error(f"Error fetching monthly historical stock data: {e}")
        company_data['Historical Stock Data (Last 5 Years - Monthly)'] = "Could not retrieve monthly historical stock data."

    try:
        annual_income_stmt = ticker.income_stmt
        if isinstance(annual_income_stmt, pd.DataFrame) and not annual_income_stmt.empty:
            annual_income_stmt = annual_income_stmt.head(5) # Last 5 annual periods

            filtered_income_stmt = annual_income_stmt[annual_income_stmt.index.isin(KEY_INCOME_STATEMENT_METRICS)]
            filtered_income_stmt.columns = filtered_income_stmt.columns.strftime('%Y-%m-%d')
            company_data['Annual Income Statement (Key Metrics, Last 5 Years)'] = filtered_income_stmt.to_dict()
        else:
            company_data['Annual Income Statement (Key Metrics, Last 5 Years)'] = "Could not retrieve annual income statement."
        logger.info("Fetched filtered annual income statements.")
    except Exception as e:
        logger.error(f"Error fetching annual income statements: {e}")
        company_data['Annual Income Statement (Key Metrics, Last 5 Years)'] = "Could not retrieve annual income statement."

    try:
        annual_balance_sheet = ticker.balance_sheet
        if isinstance(annual_balance_sheet, pd.DataFrame) and not annual_balance_sheet.empty:
            annual_balance_sheet = annual_balance_sheet.head(5) # Last 5 annual periods

            filtered_balance_sheet = annual_balance_sheet[annual_balance_sheet.index.isin(KEY_BALANCE_SHEET_METRICS)]
            filtered_balance_sheet.columns = filtered_balance_sheet.columns.strftime('%Y-%m-%d')
            company_data['Annual Balance Sheet (Key Metrics, Last 5 Years)'] = filtered_balance_sheet.to_dict()
        else:
            company_data['Annual Balance Sheet (Key Metrics, Last 5 Years)'] = "Could not retrieve annual balance sheet."
        logger.info("Fetched filtered annual balance sheets.")
    except Exception as e:
        logger.error(f"Error fetching annual balance sheets: {e}")
        company_data['Annual Balance Sheet (Key Metrics, Last 5 Years)'] = "Could not retrieve annual balance sheet."

    try:
        annual_cashflow = ticker.cashflow
        if isinstance(annual_cashflow, pd.DataFrame) and not annual_cashflow.empty:
            annual_cashflow = annual_cashflow.head(5) # Last 5 annual periods

            filtered_cashflow = annual_cashflow[annual_cashflow.index.isin(KEY_CASH_FLOW_METRICS)]
            filtered_cashflow.columns = filtered_cashflow.columns.strftime('%Y-%m-%d')
            company_data['Annual Cash Flow Statement (Key Metrics, Last 5 Years)'] = filtered_cashflow.to_dict()
        else:
            company_data['Annual Cash Flow Statement (Key Metrics, Last 5 Years)'] = "Could not retrieve annual cash flow statement."
        logger.info("Fetched filtered annual cash flow statements.")
    except Exception as e:
        logger.error(f"Error fetching annual cash flow statements: {e}")
        company_data['Annual Cash Flow Statement (Key Metrics, Last 5 Years)'] = "Could not retrieve annual cash flow statement."

    try:
        dividends = ticker.dividends
        if isinstance(dividends, pd.Series) and not dividends.empty:
            # Get last 3 dividends
            recent_dividends = dividends.tail(3)
            company_data['Recent Dividends (Last 3)'] = {
                date.strftime('%Y-%m-%d'): amount for date, amount in recent_dividends.items()
            }
        else:
            company_data['Recent Dividends (Last 3)'] = "No recent dividends found."
        logger.info("Fetched recent dividends.")
    except Exception as e:
        logger.error(f"Error fetching recent dividends: {e}")
        company_data['Recent Dividends (Last 3)'] = "Could not retrieve recent dividends data."

    try:
        splits = ticker.splits
        if isinstance(splits, pd.Series) and not splits.empty:
            company_data['Stock Splits'] = {
                date.strftime('%Y-%m-%d'): ratio for date, ratio in splits.items()
            }
        else:
            company_data['Stock Splits'] = "No stock splits found."
        logger.info("Fetched stock splits data.")
    except Exception as e:
        logger.error(f"Error fetching stock splits data: {e}")
        company_data['Stock Splits'] = "Could not retrieve stock splits data."

    try:
        institutional_holders = ticker.institutional_holders
        if isinstance(institutional_holders, pd.DataFrame) and not institutional_holders.empty:
            # Sort by 'Shares' and take top 5
            top_5_holders = institutional_holders.nlargest(5, 'Shares')
            if 'Date Reported' in top_5_holders.columns:
                top_5_holders['Date Reported'] = top_5_holders['Date Reported'].dt.strftime('%Y-%m-%d')
            company_data['Top 5 Institutional Holders'] = top_5_holders.to_dict(orient='records')
        else:
            company_data['Top 5 Institutional Holders'] = "Could not retrieve institutional holders data."
        logger.info("Fetched top 5 institutional holders.")
    except Exception as e:
        logger.error(f"Error fetching institutional holders data: {e}")
        company_data['Top 5 Institutional Holders'] = "Could not retrieve institutional holders data."
        
    try:
        recommendations = ticker.recommendations
        if isinstance(recommendations, pd.DataFrame) and not recommendations.empty:
            company_data['Analyst Recommendations'] = recommendations.to_dict()
        else:
            company_data['Analyst Recommendations'] = "Could not retrieve analyst recommendations."
        logger.info("Fetched analyst recommendations.")
    except Exception as e:
        logger.error(f"Error fetching analyst recommendations: {e}")
        company_data['Analyst Recommendations'] = "Could not retrieve analyst recommendations."
    
    try:
        earnings_dates = ticker.earnings_dates
        if isinstance(earnings_dates, pd.DataFrame) and not earnings_dates.empty:
            # Filter for future dates
            current_time = pd.Timestamp.now(tz='UTC').tz_convert('America/New_York')
            upcoming_earnings = earnings_dates[earnings_dates.index >= current_time].head(2)
            
            # For past earnings, take the last 2 reported
            past_earnings = earnings_dates[earnings_dates.index < current_time].sort_index(ascending=False).head(2)
            
            combined_earnings = pd.concat([upcoming_earnings, past_earnings]).sort_index()
            combined_earnings.index = combined_earnings.index.strftime('%Y-%m-%d')
            company_data['Key Earnings Dates'] = combined_earnings.to_dict()
        else:
            company_data['Key Earnings Dates'] = "Could not retrieve earnings dates."
        logger.info("Fetched key earnings dates.")
    except Exception as e:
        logger.error(f"Error fetching earnings dates: {e}")
        company_data['Key Earnings Dates'] = "Could not retrieve earnings dates."

    return company_data

def get_company_financial_data(ticker_symbol):
    return _get_company_financial_data(
        ticker_symbol, 
        timestamp_key=timestamp_key(options['financial']['cache_duration'])
    )

def get_report(ticker):
    prompt = PromptTemplate.from_template(
    """
    You are a financial analyst. Analyze the following company data and produce a detailed report 
    that assesses the company’s financial health and stock outlook.  
    Use structured reasoning, covering profitability, growth, balance sheet strength, risks, 
    market sentiment, and stock performance. End with an investment outlook (bullish, bearish, neutral).

    Company Data (in JSON):
    {company_data}

    Your analysis should include:
    1. **Business Overview** – What does the company do, and what sector/industry is it in?  
    2. **Financial Health** – Evaluate profitability, cash flow, debt levels, margins, 
    and capital expenditures.  
    3. **Stock Performance** – Discuss historical trends, volatility, momentum, 
    and recent market movements.  
    4. **Institutional & Analyst Sentiment** – What are institutional holders doing? 
    What do analysts recommend?  
    5. **Risks & Red Flags** – Highlight key risks (debt, negative cash flow, volatility, 
    missing profitability, etc.).  
    6. **Investment Outlook** – Based on the above, should investors view this stock 
    as bullish, bearish, or neutral? Justify your reasoning.

    Write the report in a professional tone, suitable for an investor presentation.
    """
    )

    company_data = get_company_financial_data(ticker)
    chain = prompt | options["models"]["financial"]
    response = chain.invoke({
        "company_data": company_data,
    })

    if options['verbose']:
        logger.debug(f"Financial report for {ticker}:\n{response.content}")

    return response.content
