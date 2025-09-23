from typing import TypedDict

from langchain_openai import ChatOpenAI
from langchain_community.embeddings import InfinityEmbeddings

from langchain.embeddings import CacheBackedEmbeddings
from langchain.storage import LocalFileStore

from langchain.chat_models.base import BaseChatModel
from langchain.embeddings.base import Embeddings

from langchain_core.globals import set_llm_cache
from langchain_community.cache import SQLiteCache

import os

options = {
    "use_proxies": True,
    "cache_duration": 24*60*60,  # in seconds
    "cache_dir": "./.cache",
    "timeout": 30,  # in seconds
    "verbose": os.getenv("VERBOSE_LOGGING", "false").lower() == "true",

    "movers": {
        "cache_duration": 24*60*60, # in seconds
    },
    "financial": {
        "cache_duration": 7*24*60*60, # in seconds
    },
    "websearch": {
        "cache_duration": 1*24*60*60, # in seconds
    },

}

os.makedirs(options['cache_dir'], exist_ok=True)

set_llm_cache(SQLiteCache(database_path=f"{options['cache_dir']}/.langchain.db"))

llm = ChatOpenAI(
    model=os.getenv("OPENAI_MODEL"),
    temperature=0,
    max_retries=2,
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE"),
)

underlying_embeddings = InfinityEmbeddings(
    model=os.getenv("EMBEDDING_MODEL"),
    infinity_api_url=os.getenv("INFINITY_API_URL")
)

embeddings = CacheBackedEmbeddings.from_bytes_store(
    underlying_embeddings, 
    LocalFileStore(f"{options['cache_dir']}/"),
    namespace=underlying_embeddings.model
)

class ModelsDict(TypedDict):
    summary: BaseChatModel
    embeddings: Embeddings

models: ModelsDict = {
    "summary": llm,
    "query": llm,
    "embeddings": embeddings,
}

options["models"] = models