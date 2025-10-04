from agents import news
from agents import requested_tickers
from agents import financial
from agents import evaluation
import datetime
import logging

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, **kwargs):
        self.params = kwargs

    async def act(self, observation=None):
        top_movers = requested_tickers.get_top_movers()
        if not top_movers:
            logger.error("No top movers data available.")
            return None

        gainers_limit = 5
        losers_limit = 3

        gainers = top_movers['gainers'][:gainers_limit]
        losers = top_movers['losers'][:losers_limit]

        all_tickers = [item['ticker'] for item in gainers] + \
                      [item['ticker'] for item in losers]
        logger.info(f"Retrieved top movers: {all_tickers}\ngainers: {gainers}, losers: {losers}")

        for ticker in all_tickers:
            logger.info(f"Getting news for: {ticker}")
            company_news = await news.get_news(ticker)
            logger.info(f"Getting financial report for {ticker}:")
            financials = financial.get_report(ticker)
            logger.info(f"Evaluating {ticker} based on news and financial report.")
            evaluation_result = evaluation.eval(company_news, financials)
            logger.info(f"[RESULT] Evaluation for {ticker}: {evaluation_result}")
            # store the evaluation results in a file.
            date = datetime.datetime.now().date().isoformat()

            result = {
                "ticker": ticker,
                "date": date,
                "news": company_news,
                "financial_report": financials,
                "evaluation": evaluation_result
            }

            with open(f"reports/evaluation_{ticker}_{date}.json", "w") as f:
                f.write(str(result))
