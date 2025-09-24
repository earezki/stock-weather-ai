
import datetime
from langchain.prompts import PromptTemplate
from options import options

def eval(news: str, financial_report: str) -> str:
    """
    Evaluate the quality and relevance of the news article in relation to the financial report.

    Parameters:
    - news (str): The news article text.
    - financial_report (str): The financial report text.

    Returns:
    - str: An evaluation summary of the news article's relevance and quality.
    """

    prompt = PromptTemplate.from_template("""
    You are an expert quantitative market strategist and financial analyst. Your task is to evaluate a company's financial data and the latest market news to determine your confidence in its stock price increasing in the **upcoming days to weeks**.

    Current date-time in ISO format: {current_date}

    **Input Data:**

    1.  **Company Financial Data (Text):**
        {financial_data}

    2.  **Latest Relevant News (Text):**
        {news_data}

    **Instructions for your assessment:**

    1.  **Financial Health Analysis:**
        *   Quickly identify the company's recent financial trends (revenue growth, profitability, cash flow, debt levels) from the provided "Company Financial Data." Note any significant strengths or weaknesses.

    2.  **News Impact Assessment:**
        *   Analyze each news item. Is it fundamentally positive, negative, or neutral for the company's short-to-medium term stock price?
        *   Consider how the news might influence market sentiment, investor perception, and future financial performance.

    3.  **Synthesize & Predict:**
        *   Combine your financial understanding with the news impact. Does the news reinforce or contradict existing financial trends?
        *   Evaluate if the news is likely to be a strong catalyst for price movement in the short term.
        *   Based on all information, state whether you believe the stock will *increase* or *decrease* in the upcoming days/weeks.

    4.  **Confidence Score:**
        *   Assign a **confidence score from 1 to 10** for your prediction.
            *   **1-3 (Low Confidence):** Weak signals, conflicting data, high uncertainty, or minimal expected impact.
            *   **4-7 (Medium Confidence):** Clearer signals, but with some counteracting factors, moderate expected impact, or reliance on less certain events.
            *   **8-10 (High Confidence):** Strong, consistent, and impactful positive signals from both financial and news data, pointing to a high likelihood of an increase.

    **Output Format:**
    You must respond in the following JSON format. Do not include any markdown formatting or code block delimiters (e.g., ```json) in the output.

    {{
        "prediction": "<increase/decrease>",
        "confidence_score": <1-10>,
        "rationale": "<detailed explanation of your analysis and reasoning>"
    }}
    """)

    iso_current_date = datetime.datetime.now().date().isoformat()

    chain = prompt | options["models"]["financial"]
    response = chain.invoke({
        "current_date": iso_current_date,
        "financial_data": financial_report,
        "news_data": news
    })

    return response.content