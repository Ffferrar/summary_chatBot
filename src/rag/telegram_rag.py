import os
import uuid
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from sentence_transformers import SentenceTransformer
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue, Range
from rank_bm25 import BM25Okapi
import re
from nltk.stem.snowball import SnowballStemmer
from mistralai import Mistral

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
QDRANT_COLLECTION_EMBEDDINGS = "telegram_embeddings"
QDRANT_COLLECTION_BM25 = "telegram_bm25"
VECTOR_SIZE = 384

class TelegramRAGSystem:
    def __init__(self, data_dir: str = "./tele_bot/rag_data", mistral_api_key: Optional[str] = None):
        self.data_dir = data_dir
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        qdrant_host = os.getenv("QDRANT_HOST", "qdrant")
        qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.qdrant_embeddings = QdrantClient(host=qdrant_host, port=qdrant_port)
        self.qdrant_bm25 = self.qdrant_embeddings  # use same server, different collections
        self.bm25 = None
        self.bm25_documents = []
        self.bm25_doc_ids = []
        self.bm25_uuid_map = {}
        self.mistral_client = Mistral(api_key=mistral_api_key) if mistral_api_key else None
        self.stemmer = SnowballStemmer('russian')
        self.word_pattern = re.compile(r"[a-zA-Zа-яА-ЯёЁ0-9]+(?:[-'’][a-zA-Zа-яА-ЯёЁ0-9]+)*")
        self._initialize_collections()
        self._load_bm25_data()

    def _generate_uuid(self, original_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, original_id))

    def _initialize_collections(self):
        if not self.qdrant_embeddings.collection_exists(QDRANT_COLLECTION_EMBEDDINGS):
            self.qdrant_embeddings.create_collection(
                collection_name=QDRANT_COLLECTION_EMBEDDINGS,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
            )
        if not self.qdrant_bm25.collection_exists(QDRANT_COLLECTION_BM25):
            self.qdrant_bm25.create_collection(
                collection_name=QDRANT_COLLECTION_BM25,
                vectors_config=VectorParams(size=1, distance=Distance.COSINE)
            )

    def _load_bm25_data(self):
        points = self.qdrant_bm25.scroll(
            collection_name=QDRANT_COLLECTION_BM25,
            limit=10000
        )[0]
        documents = []
        doc_ids = []
        for point in points:
            if point.payload and 'text' in point.payload and 'original_id' in point.payload:
                documents.append(self._tokenize_text(point.payload['text']))
                doc_ids.append(point.payload['original_id'])
                self.bm25_uuid_map[point.id] = point.payload['original_id']
        if documents:
            self.bm25 = BM25Okapi(documents)
            self.bm25_documents = documents
            self.bm25_doc_ids = doc_ids

    def _tokenize_text(self, text: str) -> List[str]:
        text = text.lower()
        words = self.word_pattern.findall(text)
        tokens = [self.stemmer.stem(word) for word in words]
        tokens = [token for token in tokens if len(token) > 2]
        return tokens

    def add_documents(self, documents: List[Dict[str, Any]]):
        points_embeddings = []
        points_bm25 = []
        new_bm25_docs = []
        for doc in documents:
            doc_uuid = self._generate_uuid(str(doc['id']))
            embedding = self.embedding_model.encode(doc['text']).tolist()
            payload = {
                'text': doc['text'],
                'user_id': doc['user_id'],
                'timestamp': doc['timestamp'],
                'original_id': doc['id']
            }
            points_embeddings.append(PointStruct(
                id=doc_uuid,
                vector=embedding,
                payload=payload
            ))
            points_bm25.append(PointStruct(
                id=doc_uuid,
                vector=[1.0],
                payload=payload
            ))
            new_bm25_docs.append(self._tokenize_text(doc['text']))
            self.bm25_uuid_map[doc_uuid] = doc['id']
        if points_embeddings:
            self.qdrant_embeddings.upsert(
                collection_name=QDRANT_COLLECTION_EMBEDDINGS,
                points=points_embeddings
            )
        if points_bm25:
            self.qdrant_bm25.upsert(
                collection_name=QDRANT_COLLECTION_BM25,
                points=points_bm25
            )
            if self.bm25 is None:
                self.bm25 = BM25Okapi(new_bm25_docs)
                self.bm25_documents = new_bm25_docs
                self.bm25_doc_ids = [doc['id'] for doc in documents]
            else:
                self.bm25_documents.extend(new_bm25_docs)
                self.bm25_doc_ids.extend([doc['id'] for doc in documents])
                self.bm25 = BM25Okapi(self.bm25_documents)

    def recalculate_bm25(self):
        self._load_bm25_data()

    def search(self, query: str, k: int = 10, m: int = 50, user_id: Optional[str] = None, start_timestamp: Optional[float] = None, end_timestamp: Optional[float] = None) -> List[Tuple[str, float]]:
        filters = None
        if user_id or start_timestamp is not None or end_timestamp is not None:
            conditions = []
            if user_id:
                conditions.append(FieldCondition(
                    key="user_id",
                    match=MatchValue(value=user_id)
                ))
            if start_timestamp is not None or end_timestamp is not None:
                timestamp_range = {}
                if start_timestamp is not None:
                    timestamp_range["gte"] = start_timestamp
                if end_timestamp is not None:
                    timestamp_range["lte"] = end_timestamp
                conditions.append(FieldCondition(
                    key="timestamp",
                    range=Range(**timestamp_range)
                ))
            filters = Filter(must=conditions) if conditions else None
        query_embedding = self.embedding_model.encode(query).tolist()
        query_results = self.qdrant_embeddings.query_points(
            collection_name=QDRANT_COLLECTION_EMBEDDINGS,
            query=query_embedding,
            query_filter=filters,
            limit=m,
            with_payload=True,
        )
        embedding_results_converted = []
        for result in query_results.points:
            original_id = result.payload.get('original_id', result.id)
            embedding_results_converted.append((original_id, result.score))
        bm25_results = []
        if self.bm25:
            all_points = self.qdrant_bm25.scroll(
                collection_name=QDRANT_COLLECTION_BM25,
                scroll_filter=filters,
                limit=10000
            )[0]
            filtered_docs = []
            filtered_original_ids = []
            for point in all_points:
                original_id = point.payload.get('original_id')
                if original_id and original_id in self.bm25_doc_ids:
                    idx = self.bm25_doc_ids.index(original_id)
                    filtered_docs.append(self.bm25_documents[idx])
                    filtered_original_ids.append(original_id)
            if filtered_docs:
                temp_bm25 = BM25Okapi(filtered_docs)
                tokenized_query = self._tokenize_text(query)
                bm25_scores = temp_bm25.get_scores(tokenized_query)
                bm25_indices = np.argsort(bm25_scores)[::-1][:m]
                bm25_results = [(filtered_original_ids[i], float(bm25_scores[i])) for i in bm25_indices if bm25_scores[i] > 0]
        return self._rrf_fusion(embedding_results_converted, bm25_results, k=k)

    def _rrf_fusion(self, embedding_results: List, bm25_results: List, k: int = 10, k_rrf: int = 60) -> List[Tuple[str, float]]:
        ranked_lists = []
        if embedding_results:
            embedding_rank = {doc_id: rank for rank, (doc_id, _) in enumerate(embedding_results)}
            ranked_lists.append(embedding_rank)
        if bm25_results:
            bm25_rank = {doc_id: rank for rank, (doc_id, _) in enumerate(bm25_results)}
            ranked_lists.append(bm25_rank)
        rrf_scores = {}
        for ranking in ranked_lists:
            for doc_id, rank in ranking.items():
                if doc_id not in rrf_scores:
                    rrf_scores[doc_id] = 0
                rrf_scores[doc_id] += 1.0 / (k_rrf + rank + 1)
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)[:k]
        return sorted_results

    def get_document_texts(self, doc_ids: List[str]) -> List[Tuple[str, str]]:
        results = []
        uuid_ids = [self._generate_uuid(str(doc_id)) for doc_id in doc_ids]
        points = self.qdrant_bm25.retrieve(
            collection_name=QDRANT_COLLECTION_BM25,
            ids=uuid_ids
        )
        for point in points:
            if point and point.payload:
                original_id = point.payload.get('original_id', point.id)
                results.append((original_id, point.payload['text']))
        return results

    def run_mistral(self, inquiry: str, messages: list, user_format: bool = True, model: str = "mistral-tiny", api_key: Optional[str] = None) -> str:
        import logging
        client = self.mistral_client or (Mistral(api_key=api_key) if api_key else None)
        if not client:
            raise RuntimeError("Mistral API key not provided")
        if user_format:
            messages_fmt = self.user_message(inquiry, messages)
            messages = [{"role": "user", "content": messages_fmt}]
            logging.info("[Mistral Prompt] Sending prompt to LLM API:\n%s", messages_fmt)
        chat_response = client.chat.complete(
            model=model,
            messages=messages
        )
        return chat_response.choices[0].message.content

    def user_message(self, inquiry, messages=[]):
        formatted_messages = "\n".join([f"<{{{msg[0]}, {msg[1]}}}>" for msg in messages]) if messages else "Нет сообщений."
        user_message = f"""
РОЛЬ: Ты помощник по поиску информации в чатах Telegram.
ЗАДАЧА: На основе запроса пользователя и предоставленных сообщений составь ответ.
ФОРМАТ ДАННЫХ:
История сообщений в формате:
<{{message_id, message_text}}>
Каждое сообщение на отдельной строке.

ПРАВИЛА:
- Используй только предоставленные сообщения для ответа.
- Если нет подходящей информации, ответь "Извините, я не смог найти информацию по вашему запросу."
- Будь краток и точен.
- Не обязательно использовать все предоставленные сообщения, выбери только релевантные.

ФОРМАТ ОТВЕТА:
Ответ: [текст ответа]
Использованные сообщения: <{{message_id1, message_id2, ...}}>

История сообщений:
{formatted_messages}

Запрос пользователя: {inquiry}
"""
        return user_message
