"""AI service for tender analysis using OpenAI."""

import json
import logging
from dataclasses import dataclass

from openai import AsyncOpenAI

from src.config import settings

logger = logging.getLogger(__name__)


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
        self.model = "gpt-4o"

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
Твоя задача — быстро оценить тендер и дать краткую характеристику.

Ответь строго в JSON формате:
{
    "risk_score": <число от 0 до 100, где 100 = максимальный риск>,
    "margin_estimate": "<оценка маржи: 'низкая (до 10%)', 'средняя (10-20%)', 'высокая (20%+)' или конкретный диапазон>",
    "description": "<краткое описание сути закупки в 2 предложениях>"
}

При оценке риска учитывай:
- Сложность технического задания
- Сроки выполнения
- Наличие специфических требований
- Размер обеспечения
- Репутационные риски"""

        user_prompt = f"""Оцени следующий тендер:

{truncated_text}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.3,
                max_tokens=500,
            )

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

    async def analyze_deep_audit(self, text: str) -> DeepAnalysis:
        """
        Deep analysis after payment for detailed report.

        Args:
            text: Full tender documentation text

        Returns:
            DeepAnalysis with comprehensive audit results
        """
        # Allow more text for deep analysis
        truncated_text = text[:30000] if len(text) > 30000 else text

        system_prompt = """Ты — ведущий эксперт по государственным закупкам России.
Проведи ДЕТАЛЬНЫЙ аудит тендерной документации.

Ответь строго в JSON формате:
{
    "equipment_models": ["список конкретных моделей оборудования, 'зашитых' в ТЗ, которые ограничивают конкуренцию"],
    "unrealistic_deadlines": ["список пунктов с нереалистичными сроками поставки/работ"],
    "hidden_penalties": ["список скрытых штрафов, неустоек и финансовых ловушек"],
    "legal_risks": ["юридические риски и неоднозначные формулировки"],
    "winning_strategy": "детальная стратегия победы в этом тендере",
    "overall_assessment": "общая оценка и рекомендация (участвовать/не участвовать)",
    "recommended_price": "рекомендуемая цена предложения (если возможно оценить) или null"
}

ОБЯЗАТЕЛЬНО найди:
1. Конкретные модели оборудования — ищи артикулы, бренды, характеристики, которые подходят только одному поставщику
2. Нереалистичные сроки — сравни со стандартными сроками в отрасли
3. Скрытые штрафы — ищи пени, неустойки, условия расторжения
4. Юридические ловушки — двойственные формулировки, противоречия в документах"""

        user_prompt = f"""Проведи полный аудит тендера:

{truncated_text}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=4000,
            )

            result = json.loads(response.choices[0].message.content)

            return DeepAnalysis(
                equipment_models=result.get("equipment_models", []),
                unrealistic_deadlines=result.get("unrealistic_deadlines", []),
                hidden_penalties=result.get("hidden_penalties", []),
                legal_risks=result.get("legal_risks", []),
                winning_strategy=result.get("winning_strategy", "Требуется индивидуальный анализ"),
                overall_assessment=result.get("overall_assessment", "Требуется дополнительный анализ"),
                recommended_price=result.get("recommended_price"),
            )

        except Exception as e:
            logger.error(f"Error in deep analysis: {e}")
            raise RuntimeError(f"Deep analysis failed: {e}") from e


# Singleton instance
ai_service = AIService()
