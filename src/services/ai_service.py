"""AI service for tender analysis using OpenAI."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import Lock

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


@dataclass
class TokenUsage:
    """Track token usage and costs."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    requests_count: int = 0
    estimated_cost_usd: float = 0.0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    # Pricing per 1M tokens (as of 2024)
    MODEL_PRICING = {
        "gpt-4o": {"input": 2.50, "output": 10.00},
        "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    }

    def add_usage(self, prompt_tokens: int, completion_tokens: int, model: str = "gpt-4o-mini"):
        """Add token usage from a request."""
        self.prompt_tokens += prompt_tokens
        self.completion_tokens += completion_tokens
        self.total_tokens += prompt_tokens + completion_tokens
        self.requests_count += 1

        # Calculate cost based on model
        pricing = self.MODEL_PRICING.get(model, self.MODEL_PRICING["gpt-4o-mini"])
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        self.estimated_cost_usd += input_cost + output_cost

    def to_dict(self) -> dict:
        """Convert to dictionary for API response."""
        return {
            "total_tokens": self.total_tokens,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "requests_count": self.requests_count,
            "estimated_cost_usd": round(self.estimated_cost_usd, 4),
            "estimated_cost_rub": round(self.estimated_cost_usd * 95, 2),  # ~95 RUB/USD
            "last_reset": self.last_reset.isoformat(),
        }

    def reset(self):
        """Reset usage statistics."""
        self.total_tokens = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.requests_count = 0
        self.estimated_cost_usd = 0.0
        self.last_reset = datetime.utcnow()


@dataclass
class TeaserAnalysis:
    """Result of quick teaser analysis."""

    risk_score: int  # 0-100
    margin_estimate: str  # e.g., "15-25%", "низкая", "высокая"
    description: str  # 2 sentences summary


@dataclass
class DeepAnalysis:
    """Result of deep audit analysis."""

    equipment_models: list[str]  # Specific models found in spec
    unrealistic_deadlines: list[str]  # Problematic deadline items
    hidden_penalties: list[str]  # Hidden fines and traps
    legal_risks: list[str]  # Legal issues
    winning_strategy: str  # Recommended approach
    overall_assessment: str  # Summary
    recommended_price: str | None  # Price recommendation if possible


class AIService:
    """Service for AI-powered tender analysis."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "gpt-4o"  # For deep audit (paid product)
        self.teaser_model = "gpt-4o-mini"  # For teasers (15x cheaper)
        self.usage = TokenUsage()
        self._lock = Lock()

    def get_usage(self) -> dict:
        """Get current token usage statistics."""
        with self._lock:
            return self.usage.to_dict()

    def reset_usage(self):
        """Reset token usage statistics."""
        with self._lock:
            self.usage.reset()

    def _track_usage(self, response, model: str = None):
        """Track token usage from API response."""
        if hasattr(response, "usage") and response.usage:
            with self._lock:
                self.usage.add_usage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                    model=model or self.teaser_model,
                )

    async def analyze_teaser(self, text: str) -> TeaserAnalysis:
        """
        Quick analysis for teaser email.

        Args:
            text: Extracted tender documentation text

        Returns:
            TeaserAnalysis with risk score, margin estimate, and description
        """
        # Truncate text to fit context window
        truncated_text = text[:8000] if len(text) > 8000 else text

        system_prompt = """Ты — эксперт по государственным закупкам России с 15-летним опытом.
Твоя задача — быстро оценить тендер и написать ПРОДАЮЩИЙ тизер, который заинтересует потенциального участника.

Ответь строго в JSON формате:
{
    "risk_score": <число от 0 до 100, где 100 = максимальный риск>,
    "margin_estimate": "<оценка маржи: 'низкая (до 10%)', 'средняя (10-20%)', 'высокая (20%+)' или конкретный диапазон>",
    "description": "<тизер из 2-3 предложений с КОНКРЕТНЫМИ намёками>"
}

ВАЖНО для description:
- Начни с сути закупки (что закупают)
- ОБЯЗАТЕЛЬНО добавь 1-2 конкретных намёка на риски ИЛИ преимущества

Если есть риски, намекни конкретно (примеры):
- "Обратите внимание на сжатые сроки поставки — возможны штрафы"
- "В ТЗ указаны конкретные модели оборудования — риск ограничения конкуренции"
- "Крупное обеспечение контракта может заморозить оборотные средства"
- "Сложная логистика до отдалённых регионов"
- "Высокие требования к квалификации персонала"

Если рисков мало, укажи преимущества:
- "Стандартная закупка с понятными требованиями"
- "Типовое ТЗ без специфических ограничений — высокая конкуренция"
- "Комфортные сроки исполнения позволяют оптимизировать логистику"
- "Крупный заказчик с хорошей платёжной дисциплиной"

При оценке риска учитывай:
- Сложность технического задания
- Сроки выполнения (менее 30 дней = высокий риск)
- Наличие конкретных моделей/брендов
- Размер обеспечения (>5% от НМЦ = повышенный)
- Штрафные санкции
- Удалённость региона поставки"""

        user_prompt = f"""Оцени следующий тендер:

{truncated_text}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.teaser_model,  # Using mini for cost efficiency
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.4,
                max_tokens=700,
            )

            self._track_usage(response, model=self.teaser_model)
            result = json.loads(response.choices[0].message.content)

            return TeaserAnalysis(
                risk_score=min(100, max(0, int(result.get("risk_score", 50)))),
                margin_estimate=result.get("margin_estimate", "не определена"),
                description=result.get("description", "Описание недоступно"),
            )

        except Exception as e:
            logger.error(f"Error in teaser analysis: {e}")
            # Return safe defaults on error
            return TeaserAnalysis(
                risk_score=50,
                margin_estimate="требует анализа",
                description="Автоматический анализ недоступен. Требуется ручная проверка.",
            )

    def _split_into_chunks(self, text: str, chunk_size: int = 12000, overlap: int = 500) -> list[str]:
        """Split text into overlapping chunks for processing."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            # Try to break at paragraph or sentence boundary
            if end < len(text):
                # Look for paragraph break
                break_pos = text.rfind("\n\n", start + chunk_size - 1000, end)
                if break_pos == -1:
                    # Look for sentence break
                    break_pos = text.rfind(". ", start + chunk_size - 500, end)
                if break_pos != -1:
                    end = break_pos + 1

            chunks.append(text[start:end])
            start = end - overlap  # Overlap for context continuity

        return chunks

    async def _analyze_chunk(self, chunk: str, chunk_num: int, total_chunks: int) -> dict:
        """Analyze a single chunk for risks and issues."""
        system_prompt = """Ты — эксперт по госзакупкам. Анализируй фрагмент тендерной документации.

Ответь в JSON:
{
    "equipment_models": ["конкретные модели/бренды/артикулы оборудования, ограничивающие конкуренцию"],
    "unrealistic_deadlines": ["пункты с нереалистичными сроками"],
    "hidden_penalties": ["штрафы, неустойки, финансовые ловушки"],
    "legal_risks": ["юридические риски, неоднозначные формулировки"]
}

Если в этом фрагменте ничего не найдено — верни пустые массивы."""

        user_prompt = f"""Фрагмент {chunk_num}/{total_chunks} тендерной документации:

{chunk}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2000,
            )
            self._track_usage(response, model=self.model)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error analyzing chunk {chunk_num}: {e}")
            return {"equipment_models": [], "unrealistic_deadlines": [], "hidden_penalties": [], "legal_risks": []}

    async def _synthesize_findings(self, findings: dict, text_preview: str) -> dict:
        """Synthesize all findings into final strategy and assessment."""
        system_prompt = """Ты — ведущий эксперт по госзакупкам России.
На основе собранных данных сформируй итоговую стратегию.

Ответь в JSON:
{
    "winning_strategy": "детальная стратегия победы (3-5 пунктов)",
    "overall_assessment": "общая оценка: участвовать или нет, с обоснованием",
    "recommended_price": "рекомендуемая цена или null если невозможно оценить"
}"""

        findings_summary = f"""
НАЙДЕННЫЕ ПРОБЛЕМЫ:

Модели оборудования (ограничение конкуренции): {len(findings['equipment_models'])} шт.
{chr(10).join('- ' + item for item in findings['equipment_models'][:10])}

Нереалистичные сроки: {len(findings['unrealistic_deadlines'])} шт.
{chr(10).join('- ' + item for item in findings['unrealistic_deadlines'][:10])}

Скрытые штрафы: {len(findings['hidden_penalties'])} шт.
{chr(10).join('- ' + item for item in findings['hidden_penalties'][:10])}

Юридические риски: {len(findings['legal_risks'])} шт.
{chr(10).join('- ' + item for item in findings['legal_risks'][:10])}

НАЧАЛО ДОКУМЕНТАЦИИ (для контекста):
{text_preview[:3000]}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": findings_summary},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=2000,
            )
            self._track_usage(response, model=self.model)
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error(f"Error synthesizing findings: {e}")
            return {
                "winning_strategy": "Требуется индивидуальный анализ",
                "overall_assessment": "Требуется дополнительный анализ",
                "recommended_price": None,
            }

    async def analyze_deep_audit(self, text: str) -> DeepAnalysis:
        """
        Deep analysis using Map-Reduce for large documents.

        1. Split document into chunks
        2. Analyze each chunk for risks (Map)
        3. Merge all findings (Reduce)
        4. Synthesize final strategy

        Args:
            text: Full tender documentation text

        Returns:
            DeepAnalysis with comprehensive audit results
        """
        import asyncio

        if not text or len(text.strip()) < 100:
            logger.warning("Empty or too short text for deep analysis")
            return DeepAnalysis(
                equipment_models=[],
                unrealistic_deadlines=[],
                hidden_penalties=[],
                legal_risks=["Документация недоступна или слишком короткая"],
                winning_strategy="Невозможно провести анализ без документации",
                overall_assessment="Требуется загрузить документацию",
                recommended_price=None,
            )

        # Split into chunks
        chunks = self._split_into_chunks(text)
        logger.info(f"Deep analysis: {len(text)} chars split into {len(chunks)} chunks")

        # Map: analyze each chunk in parallel
        tasks = [
            self._analyze_chunk(chunk, i + 1, len(chunks))
            for i, chunk in enumerate(chunks)
        ]
        chunk_results = await asyncio.gather(*tasks)

        # Reduce: merge all findings
        merged = {
            "equipment_models": [],
            "unrealistic_deadlines": [],
            "hidden_penalties": [],
            "legal_risks": [],
        }

        for result in chunk_results:
            for key in merged:
                items = result.get(key, [])
                if isinstance(items, list):
                    merged[key].extend(items)

        # Deduplicate (simple approach - exact matches)
        for key in merged:
            merged[key] = list(dict.fromkeys(merged[key]))

        logger.info(
            f"Findings: {len(merged['equipment_models'])} models, "
            f"{len(merged['unrealistic_deadlines'])} deadlines, "
            f"{len(merged['hidden_penalties'])} penalties, "
            f"{len(merged['legal_risks'])} risks"
        )

        # Synthesize final strategy
        synthesis = await self._synthesize_findings(merged, text)

        return DeepAnalysis(
            equipment_models=merged["equipment_models"],
            unrealistic_deadlines=merged["unrealistic_deadlines"],
            hidden_penalties=merged["hidden_penalties"],
            legal_risks=merged["legal_risks"],
            winning_strategy=synthesis.get("winning_strategy", "Требуется индивидуальный анализ"),
            overall_assessment=synthesis.get("overall_assessment", "Требуется дополнительный анализ"),
            recommended_price=synthesis.get("recommended_price"),
        )


# Singleton instance
ai_service = AIService()
