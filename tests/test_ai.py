from types import SimpleNamespace as S
from unittest.mock import patch
import pytest
from app.ai.services import reserve, settle, BudgetExceeded, response_call, enrich_article, answer_archive
from app.ai.models import UsageDay, Conversation, Message
from app.news.services import ingest


def test_budget_reservation_is_conservative(config):
    config.ai_daily_tokens = 1000
    config.save()
    day = reserve(600)
    with pytest.raises(BudgetExceeded):
        reserve(500)
    settle(day, 600, S(input_tokens=100, output_tokens=50))
    assert UsageDay.objects.get().used == 150
    day = reserve(200)
    settle(day, 200, None)
    assert UsageDay.objects.get().estimated == 200


def test_structured_enrichment_uses_responses_and_cache(config, feed, item):
    a, _ = ingest(feed, item)
    response = S(
        status="completed",
        output_text='{"title":"中文标题","summary":"忠实摘要"}',
        usage=S(input_tokens=50, output_tokens=20),
    )
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value = response
        assert enrich_article(a.current_id)["title"] == "中文标题"
        enrich_article(a.current_id)
        assert factory.return_value.responses.create.call_count == 1
        payload = factory.return_value.responses.create.call_args.kwargs
        assert "text" in payload and "previous_response_id" not in payload and "background" not in payload


def test_stream_incomplete_not_accepted(config):
    response = S(status="incomplete", usage=S(input_tokens=20, output_tokens=5))
    events = [
        S(type="response.output_text.delta", delta="草稿"),
        S(type="response.incomplete", response=response),
    ]
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value.__enter__.return_value = iter(events)
        parts = []
        with pytest.raises(RuntimeError):
            response_call("test", "input", on_delta=parts.append)
        assert parts == ["草稿"]
    assert UsageDay.objects.get().used == 25


def test_hallucinated_citation_rejected(config):
    conv = Conversation.objects.create(title="问答")
    with patch("app.ai.services.response_call", return_value=S(output=[], output_text="消息已确认[999999]")):
        with pytest.raises(ValueError):
            answer_archive(conv.pk, "有什么新进展")
    assert not Message.objects.filter(role="assistant", status="completed").exists()


def test_missing_evidence_returns_honest_answer(config):
    conv = Conversation.objects.create(title="问答")
    with patch("app.ai.services.response_call", return_value=S(output=[], output_text="没有依据的猜测")):
        result = answer_archive(conv.pk, "有什么新进展")
    assert "未获得" in result["text"]
