import json
import datetime

import asyncio
import os
import httpx
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

from langchain_community.document_loaders import AsyncHtmlLoader, PyMuPDFLoader
from langchain_community.document_transformers import Html2TextTransformer
import hashlib

from langchain.schema import Document
import asyncio

from langchain_text_splitters import RecursiveCharacterTextSplitter
import numpy as np

from langchain.prompts import PromptTemplate

from options import options

from toolkit.cache import memory, timestamp_key
from toolkit.user_agent import get_user_agent
from tools import scrapping

logger = logging.getLogger(__name__)

def get_search_queries(query: str) -> dict:
    """
    Given a user's natural language query, this function uses an LLM to:
    1. Rewrite it into an effective search engine query.
    2. Determine if it's a 'news' or 'general' search.
    3. Decompose complex queries into focused sub-queries.
    4. Generate up to 6 additional related search queries.

    The output is a JSON object with two keys: `search_type` and `queries`.
    """
    prompt = PromptTemplate.from_template("""
        You are an AI assistant specialized in optimizing and expanding user queries for search engines.
        Current date-time in ISO format: {current_date}

        Given a user's natural language question, your primary task is to first rewrite it into the most effective and concise search engine query. Then, determine its primary search category (either 'news' or 'general'). If the user's query is complex or contains multiple distinct questions/facets, you must decompose it into individual, focused search queries to ensure all aspects are thoroughly addressed. Finally, generate up to 6 additional, related search queries that explore different facets or complete the user's original intent. Consider the current date for time-sensitive topics and time if required.

        All output must be a pure JSON object with two keys: `search_type` (either 'news' or 'general') and `queries`. The `queries` key should contain a JSON array of strings, where each string is a search query. The first element of the `queries` array should always be your rewritten primary search query. **Do not include any markdown formatting or code block delimiters (e.g., ```json) in the output.**

        Example User Query: How can I make my computer run faster without buying new hardware?
        Example Output: {{"search_type": "general", "queries": ["optimize computer performance without new hardware", "speed up slow pc software solutions", "free ways to improve computer speed", "clean up computer hard drive for performance", "manage startup programs windows mac", "defragment hard drive performance boost"]}}

        Example User Query: What are the latest developments in AI ethics?
        Example Output: {{"search_type": "news", "queries": ["latest AI ethics news 2025-09-15", "recent advancements responsible AI 2025-09-15", "controversies in AI morality", "AI governance updates 2025-09-15", "future of ethical AI"]}}

        Example User Query: What are the benefits of a plant-based diet, and how does it impact athletic performance?
        Example Output: {{"search_type": "general", "queries": ["benefits of plant-based diet", "health advantages vegan diet", "plant-based diet athletic performance", "vegan diet for athletes pros and cons", "impact of plant-based eating on sports endurance", "plant-based nutrition for muscle growth"]}}

        **Example User Query: What was Apple's Q3 2024 earnings, and what are the analyst forecasts for its stock performance next quarter?**
        **Example Output: {{"search_type": "news", "queries": ["Apple Q3 2024 earnings report", "Apple Inc. Q3 2024 financial results", "Apple analyst forecasts Q4 2024 stock performance", "AAPL stock price prediction next quarter", "Apple revenue and profit Q3 2024", "analyst ratings Apple stock"]}}**

        User Query: {query}
        Output:
    """)
        
    iso_current_date = datetime.datetime.now().date().isoformat()

    chain = prompt | options["models"]["query"]
    response = chain.invoke({
        "query": query,
        "current_date": iso_current_date
    })

    if options["verbose"]:
        logger.debug(f"LLM Response for search query of {query}: {response.content}")

    return json.loads(response.content)

def optimize_query(query: str) -> str:
    """
    Given a user's natural language query, this function uses an LLM to rewrite it into an effective search engine query.

    The output is a single optimized search query string.
    """
    prompt = PromptTemplate.from_template("""
        You are an AI assistant specialized in optimizing user queries for generating highly effective semantic embeddings. Your goal is to transform a user's natural language question into a single, comprehensive, and context-rich query string that provides maximum information for an embedding model.
        Current date-time in ISO format: {current_date}
                                          
        When rewriting the query, consider the following:
        -   **Expand and Clarify:** Fully expand abbreviations, clarify vague terms, and add necessary context to make the query unambiguous.
        -   **Capture Full Intent:** Ensure the rewritten query clearly expresses the user's underlying intent, including any implied sub-questions or facets.
        -   **Identify Key Entities and Relationships:** Explicitly mention important entities, concepts, and the relationships between them.
        -   **Integrate Relevant Keywords:** Incorporate synonyms or related terms that an embedding model might find useful for broader semantic matching.
        -   **Focus on Semantic Richness:** The goal is not just keyword density, but to create a semantically rich statement that accurately represents the user's information need.
        -   **Time Sensitivity:** If the query is time-sensitive, include relevant dates or timeframes.
        -   **Output Format:** The output must be a JSON object with a single key: `optimized_embedding_query`. **Do not include any markdown formatting or code block delimiters (e.g., ```json) in the output.**

        Example User Query: "AI ethics latest?"
        Example Output: {{"optimized_embedding_query": "latest developments and controversies in artificial intelligence ethics, including responsible AI frameworks, governance updates, and societal impacts"}}

        Example User Query: "How to speed up my PC?"
        Example Output: {{"optimized_embedding_query": "methods and software solutions to optimize computer performance and increase PC speed without requiring new hardware purchases, covering aspects like disk cleanup, startup programs, and system settings"}}

        Example User Query: "Benefits of plant-based diet for athletes?"
        Example Output: {{"optimized_embedding_query": "health benefits and performance impacts of a plant-based diet specifically for athletes, including effects on endurance, muscle recovery, strength, and overall athletic performance and nutrition"}}

        **Example User Query: "Tesla stock performance last quarter?"**
        **Example Output: {{"optimized_embedding_query": "Tesla Inc. (TSLA) stock performance, share price movements, financial results, and market analysis for the most recent fiscal quarter, including revenue, earnings per share, and investor sentiment"}}**

        User Query: {query}
        Output:
    """)

    iso_current_date = datetime.datetime.now().date().isoformat()

    chain = prompt | options["models"]["query"]
    response = chain.invoke({
        "current_date": iso_current_date,
        "query": query
    })

    if options["verbose"]:
        logger.debug(f"LLM Response for optimized query of {query}: {response.content}")

    return response.content

@memory.cache(ignore=['client'])
@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
async def fetch_results(client: httpx.AsyncClient, 
                        query: str, category: str,
                        timestamp_key) -> dict:
    if options["verbose"]:
        logger.debug(f"searching internet for: {query}")

    params = {
        "q": query,
        "format": "json",
        "categories": category,
        "pageno": 1 #only first page.
    }

    searxng_host = os.getenv("SEARXNG_HOST")
    response = await client.get(f"{searxng_host}/search", params=params, timeout=options["timeout"])
    response.raise_for_status()
    return response.json()

async def web_search(search_queries: dict) -> list[dict]:
    """
    Given a set of search queries and a search type ('news' or 'general'),
    this function performs web searches using the SearXNG API and aggregates the results.
    """
    category = search_queries.get("search_type", "general")
    queries = search_queries.get("queries", [])

    seen = set()
    results = []

    limits = httpx.Limits(max_connections=10, max_keepalive_connections=10)

    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            fetch_results(client, query, category,
                          timestamp_key=timestamp_key(options["websearch"]["cache_duration"]))
            for query in queries
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        for query, resp in zip(queries, responses):
            if isinstance(resp, Exception):
                logger.error(f"Error querying '{query}': {resp}")
                continue

            for r in resp.get("results", []):
                url = r.get("url")
                if url and url not in seen:
                    seen.add(url)
                    results.append({
                        "url": url,
                        "title": r.get("title", ""),
                        "snippet": r.get("content", ""),
                    })

    return results

def get_score_threshold_or_top_k(ranked_docs, top_k, score_threshold):
    """
    From a list of (doc, score) tuples, return those with score >= score_threshold
    or the top_k highest scoring documents if none meet the threshold.
    """

    if not ranked_docs:
        return []

    filtered_docs = [(doc, score) for doc, score in ranked_docs if score >= score_threshold]

    if filtered_docs:
        return filtered_docs

    filtered_docs = sorted(filtered_docs, key=lambda x: x[1], reverse=True)

    return filtered_docs[:top_k]

def cosine_similarity(vec1, vec2):
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    return dot_product / (norm_vec1 * norm_vec2)

def rerank_documents(docs: list, query: str) -> list:
    """
    Rerank documents based on their relevance to the query.
    Given a list of documents and a user query, this function reranks the documents
    based on their relevance to the query using cosine similarity of embeddings.
    Args:
        docs: List of Document objects to be reranked.
        query: The user query string.
        Returns:
        A list of reranked Document objects.
    """
    overlap_percentage = 10  # 10% overlap
    chunk_size = 1800
    chunk_overlap = int(chunk_size * overlap_percentage / 100)
    top_k = 50
    score_threshold = 0.7

    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", " ", ""],
    )

    # Add unique document IDs
    for i, doc in enumerate(docs):
        doc.metadata["doc_id"] = f"doc_{i}"

    splitted_docs = text_splitter.split_documents(docs)

    embeddings = options["models"]["embeddings"]
    vectors = embeddings.embed_documents([doc.page_content for doc in splitted_docs])
    query_vector = embeddings.embed_query(query)

    if options["verbose"]:
        logger.debug(f"Generated {len(vectors)} vectors for {len(splitted_docs)} documents.")
        logger.debug(f"vector length: {len(query_vector)}")

    similarities = [cosine_similarity(query_vector, vec) for vec in vectors]
    ranked_docs = sorted(zip(splitted_docs, similarities), key=lambda x: x[1], reverse=True)
    ranked_docs = get_score_threshold_or_top_k(ranked_docs, top_k=top_k, score_threshold=score_threshold)

    if options["verbose"]:
        logger.debug(f"{len(ranked_docs)} documents passed the relevance threshold of {score_threshold} or are in the top {top_k}.")

    original_lookup = {doc.metadata["doc_id"]: doc for doc in docs}
    retained_docs = [(original_lookup[doc.metadata["doc_id"]]) for doc, score in ranked_docs]
    retained_docs = list({doc.metadata["hash"]: doc for doc in retained_docs}.values())

    return retained_docs

async def summarize_with_context(query: str, query_context: str) -> str:
    prompt = PromptTemplate.from_template("""
    You are a web search summarizer, tasked with summarizing a piece of text retrieved from a web search. Your primary goal is to summarize the 
    provided text into a detailed, 2-4 paragraph explanation that directly answers the given query.
    Current date-time in ISO format: {current_date}    

    **CRITICAL INSTRUCTION:** If, and only if, the provided text **does not contain enough factual information to directly and comprehensively answer the query**, you **MUST** respond with "Insufficient-information". Do not attempt to guess, infer, or use outside knowledge; strictly rely on the given text.

    - **Journalistic tone**: The summary should sound professional and journalistic, not too casual or vague.
    - **Thorough and detailed**: Ensure that every key point from the text relevant to the query is captured and that the summary directly answers the query.
    - **Not too lengthy, but detailed**: The summary should be informative but not excessively long (2-4 paragraphs). Focus on providing detailed information in a concise format.
    - **Source-dependent**: Your response must solely be based on the information provided within the `<text>` tags. Do not introduce any external knowledge.
    - **No external knowledge**: Do not use any information that is not contained within the provided text. If the text does not provide enough information to answer the query, respond with "Insufficient-information".
    - **Time sensitivity**: If the query is time-sensitive, ensure that the summary reflects the most current information available in the text.

    The text will be shared inside the `text` XML tag, and the query inside the `query` XML tag.

    <example>
    `<text>
    Docker is a set of platform-as-a-service products that use OS-level virtualization to deliver software in packages called containers. 
    It was first released in 2013 and is developed by Docker, Inc. Docker is designed to make it easier to create, deploy, and run applications 
    by using containers.
    </text>

    <query>
    What is Docker and how does it work?
    </query>

    Response:
    Docker is a revolutionary platform-as-a-service product developed by Docker, Inc., that uses container technology to make application 
    deployment more efficient. It allows developers to package their software with all necessary dependencies, making it easier to run in 
    any environment. Released in 2013, Docker has transformed the way applications are built, deployed, and managed.
    `
    </example>

    <example>
    `<text>
    The capital of France is Paris. It is a major European city and a global center for art, fashion, gastronomy, and culture. The Eiffel Tower, built in 1889, is its most iconic landmark.
    </text>

    <query>
    What is the current population of Paris and what are its main industries?
    </query>

    Response:
    Insufficient-information
    `
    </example>

    Everything below is the actual data you will be working with. Good luck!

    <query>
    {query}
    </query>

    <text>
    {query_context}
    </text>

    Make sure to answer the query in the summary, or respond with "Insufficient-information" if the text does not allow for a complete answer.
    """)

    if options["verbose"]:
        logger.debug(f"Summarizing documents for {query}: {query_context[:200]}...")


    iso_current_date = datetime.datetime.now().date().isoformat()
    
    chain = prompt | options["models"]["summary"]
    response = await chain.ainvoke({
        "query": query,
        "query_context": query_context,
        "current_date": iso_current_date
    })

    return response.content

async def summarize_docs(docs, query) -> list[Document]:
    """
    Summarizes documents.
    
    Args:
        docs: list of original Documents
        query: the user query
        summarize_with_context: function(query, query_context) -> str
    
    Returns:
        summarized_docs: list of new summarized Documents
        query_context: concatenated summary string
    """
    async def summarize_doc(doc):
        try:
            summary = await summarize_with_context(query=query, query_context=doc.page_content)
            
            return Document(
                page_content=summary,
                metadata=doc.metadata
            )
        except Exception as e:
            logger.error(f"Failed to summarize document {doc.metadata.get('url', '')}: {e}")
            return None

    tasks = [summarize_doc(doc) for doc in docs]
    results = await asyncio.gather(*tasks)

    return [doc for doc in results if doc is not None and "Insufficient-information" not in doc.page_content]

def combine_summaries(query: str, docs: list[Document]) -> str:
    """
    Combines multiple summarized documents into a single context string.
    """
    formatted_snippets = []

    for i, doc in enumerate(docs):
        snippet_index = i + 1        
        content = doc.page_content
        formatted_snippet = f"[{snippet_index}] {content}"
        formatted_snippets.append(formatted_snippet)
        if options["verbose"]:
            logger.debug(f"Snippet [{snippet_index}] (from {doc.metadata.get('url', '')}): {content[:200]}...")

    query_context = "\n\n".join(formatted_snippets)

    prompt = PromptTemplate.from_template("""
    You are an advanced AI assistant tasked with producing **detailed, well-structured answers** strictly based on the provided context snippets.  
    Your role is not just to summarize but to **synthesize, elaborate, and explain comprehensively** so the reader gains a complete understanding of the topic.  

    ---

    ### Output Guidelines

    #### 1. Concise Initial Answer
    - Start with a short, **direct 1–2 sentence summary** that immediately addresses the query.  
    - This should capture the **most essential fact(s)** before expanding further.  

    #### 2. Extended Detailed Explanation
    - After the short answer, provide a **thorough, structured explanation**.  
    - Expand on each relevant point from the snippets with **specifics, details, and supporting context**.  
    - Follow this structure:  
    - **Headings or subsections** for major themes.  
    - **Bullet points or numbered lists** for clarity when multiple distinct items are involved.  
    - **Comprehensive detail for each fact**: include descriptive phrases, metrics (dates, percentages, version numbers, JEP/project names, technical identifiers) when available.  
    - Do not stop at naming an item—explain its **nature, purpose, role, or impact**.  

    #### 3. Integration of Sources
    - Synthesize information across snippets, weaving details into a cohesive explanation.  
    - If multiple snippets discuss the same topic, **merge them into a unified, expanded explanation** rather than repeating separately.  
    - Do not leave out any relevant detail from the snippets.  

    #### 4. Citations
    - Every factual statement must be followed by a citation in the form `[INDEX]`.  
    - If multiple snippets support the same statement, cite all of them `[INDEX1, INDEX2]`.  
    - Purely integrative or high-level summary sentences do **not** need a citation, but all details must be grounded in the context.  

    #### 5. Restrictions
    - **No external knowledge** — only use the provided snippets.  
    - **Ignore irrelevant content**.  
    - **Neutral, professional tone** at all times.  
    - **Do not give overly short answers** — answers lacking detail are considered incomplete.  

    ---

    ### Final Answer Format

    **Question:**  
    {query}  

    **Context Snippets:**  
    {query_context}  

    **Your Answer:**  
    """
    )

    if options["verbose"]:
        logger.debug(f"Summarizing final version for {len(docs)} documents !")

    chain = prompt | options["models"]["summary"]
    response = chain.invoke({
        "query": query,
        "query_context": query_context
    })

    return response.content


async def get_news(ticker: str) -> list[dict]:
    """
    Given a stock ticker symbol, this function generates relevant search queries,
    performs web searches, and returns aggregated news results.
    """

    query = f"latest news about {ticker} stock"

    query = optimize_query(query)
    if options["verbose"]:
        logger.debug(f"Optimized query for {ticker}: {query}")

    search_queries = get_search_queries(query)

    if options["verbose"]:
        logger.debug(f"Generated search queries for {ticker}: {search_queries}")

    query_results = await web_search(search_queries)
    if options["verbose"]:
        logger.debug(f"Retrieved {len(query_results)} results for {ticker}")

    if not query_results:
        logger.error(f"No results were found for ticker = {ticker}")
        return []

    urls_list = [qr["url"] for qr in query_results]
    docs = scrapping.load_documents_from_urls(urls_list)
    if options["verbose"]:
        logger.debug(f"Loaded {len(docs)} documents from internet for {ticker}")

    if not docs:
        logger.info(f"no docs were returned from load_documents_from_urls, for ticker {ticker}")
        return []

    docs = rerank_documents(docs, query)
    if options["verbose"]:
        logger.debug(f"Reranked to {len(docs)} relevant documents for {ticker}")

    docs = await summarize_docs(docs, query)
    if options["verbose"]:
        logger.debug(f"Summarized to {len(docs)} documents for {ticker}")

    return combine_summaries(query=query, docs=docs)