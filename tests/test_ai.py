from datetime import timedelta
from types import SimpleNamespace as S
from unittest.mock import patch

import pytest
from django.utils import timezone

from app.ai.models import Conversation, Generation, Message, UsageDay
from app.ai.services import (
    ENRICH_MAX_OUTPUT_TOKENS,
    BudgetExceeded,
    Enrichment,
    EventDraft,
    EventRetirement,
    LinkSuggestion,
    MajorEventProposal,
    MajorEventScan,
    answer_archive,
    audit_auto_events,
    discover_major_events,
    draft_event_update,
    enrich_article,
    event_ai,
    prepare_ai,
    queue_backfill,
    reserve,
    response_call,
    settle,
    structured,
    suggest_event_links,
)
from app.briefs.models import Briefing, BriefItem
from app.core.models import Job
from app.events.models import Candidate, Event, EventReview, Node
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


def test_event_calls_cannot_spend_the_morning_news_budget(config):
    config.ai_daily_tokens = 10000
    config.save(update_fields=["ai_daily_tokens"])
    midnight = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    with patch("app.ai.services.timezone.localtime", return_value=midnight):
        with pytest.raises(BudgetExceeded):
            reserve(1500, lane="event")
        day = reserve(100, lane="event")
        settle(day, 100, S(input_tokens=70, output_tokens=10), lane="event")
    usage = UsageDay.objects.get()
    assert usage.lane_used["event"] == 80


def test_event_lane_covers_measured_daily_tracking_demand(config):
    config.ai_daily_tokens = 10000
    config.save(update_fields=["ai_daily_tokens"])
    late = timezone.localtime().replace(hour=23, minute=59, second=59, microsecond=0)
    with patch("app.ai.services.timezone.localtime", return_value=late):
        day = reserve(3900, lane="event")
        with pytest.raises(BudgetExceeded):
            reserve(200, lane="event")
        settle(day, 3900, S(input_tokens=3000, output_tokens=800), lane="event")
    assert UsageDay.objects.get().lane_used["event"] == 3800


def test_routine_work_cannot_consume_the_brief_reserve(config):
    config.ai_daily_tokens = 10000
    config.save(update_fields=["ai_daily_tokens"])
    UsageDay.objects.create(day=timezone.localdate(), used=9000)
    with pytest.raises(BudgetExceeded):
        reserve(100, lane="fresh")
    day = reserve(100, lane="urgent")
    settle(day, 100, S(input_tokens=60, output_tokens=20), lane="urgent")
    assert UsageDay.objects.get().lane_used["urgent"] == 80


def test_structured_enrichment_uses_responses_and_cache(config, feed, item):
    english = {
        **item,
        "title": "New AI chip improves inference efficiency",
        "summary": "The new processor reduces latency and power use in production inference workloads.",
    }
    a, _ = ingest(feed, english)
    brief = Briefing.objects.create(
        key="ai-localization", title="简报", start=timezone.now(), end=timezone.now()
    )
    brief_item = BriefItem.objects.create(
        briefing=brief,
        version=a.current,
        position=1,
        title=a.current.title,
        summary=a.current.summary,
        source=feed.name,
        url=a.url,
    )
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
        assert payload["max_output_tokens"] == ENRICH_MAX_OUTPUT_TOKENS
        assert payload["reasoning"] == {"effort": "none"}
        assert len(payload["input"]) < 3000
    brief_item.refresh_from_db()
    assert brief_item.title == english["title"]
    assert brief_item.title_zh == "中文标题"
    assert brief_item.summary_zh == "忠实摘要"


def test_structured_truncates_capability_for_audit_column(config):
    response = S(
        status="completed",
        output_text='{"title":"中文标题","summary":"忠实摘要"}',
        usage=S(input_tokens=20, output_tokens=10),
    )
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value = response
        structured("重大事件自动发现" * 20, {"source": "test"}, Enrichment)
    assert len(Generation.objects.get().capability) == 40


def test_chinese_article_does_not_spend_ai_tokens(config, feed, item):
    article, _ = ingest(feed, item)
    with patch("app.ai.services.client") as factory:
        result = enrich_article(article.current_id)
    article.current.refresh_from_db()
    assert result["local"] is True
    assert article.current.title_zh == item["title"]
    assert article.current.summary_zh == item["summary"]
    factory.assert_not_called()
    assert not UsageDay.objects.exists()


def test_japanese_article_gets_chinese_enrichment(config, feed, item):
    japanese = {
        **item,
        "title": "トランプ大統領が協定に署名",
        "summary": "トランプ大統領は新しい協定に署名しました。",
    }
    article, _ = ingest(feed, japanese)
    response = S(
        status="completed",
        output_text='{"title":"特朗普总统签署协议","summary":"特朗普总统签署了一项新协议。"}',
        usage=S(input_tokens=40, output_tokens=20),
    )
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value = response
        enrich_article(article.current_id)
    article.current.refresh_from_db()
    assert article.current.title_zh == "特朗普总统签署协议"
    assert article.current.summary_zh == "特朗普总统签署了一项新协议。"
    factory.return_value.responses.create.assert_called_once()


def test_chinese_article_with_only_content_still_gets_ai_summary(config, feed, item):
    source = {**item, "summary": "", "content": "这是一篇需要压缩成简介的完整中文新闻正文。"}
    article, _ = ingest(feed, source)
    response = S(
        status="completed",
        output_text='{"title":"人工智能芯片发布","summary":"中文新闻正文的忠实简介。"}',
        usage=S(input_tokens=40, output_tokens=20),
    )
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value = response
        enrich_article(article.current_id)
    article.current.refresh_from_db()
    assert article.current.summary_zh == "中文新闻正文的忠实简介。"
    factory.return_value.responses.create.assert_called_once()


def test_prepare_ai_stops_remote_queue_when_daily_budget_is_exhausted(config, feed, item):
    english = {**item, "title": "Foreign language report", "summary": "A detailed foreign report."}
    ingest(feed, english)
    config.ai_daily_tokens = 100
    config.save(update_fields=["ai_daily_tokens"])
    UsageDay.objects.create(day=timezone.localdate(), used=100)
    with patch("app.core.tasks.enqueue") as enqueue:
        result = prepare_ai()
    assert result["budget_available"] is False
    enqueue.assert_not_called()


def test_backfill_queues_imported_history(config, feed, item):
    english = {
        **item,
        "title": "Historical foreign report",
        "summary": "A historical report that still needs translation.",
    }
    article, _ = ingest(feed, english, imported=True)
    result = queue_backfill("imported", 10)
    job = Job.objects.get(kind="enrich", payload__version=article.current_id)
    assert result == {"queued": 1, "localized": 0, "scope": "imported"}
    assert job.priority == 80
    assert job.key.startswith("backfill-enrich:")


def test_stream_incomplete_not_accepted(config):
    response = S(status="incomplete", usage=S(input_tokens=20, output_tokens=5))
    events = [
        S(type="response.output_text.delta", delta="草稿"),
        S(type="response.incomplete", response=response),
    ]
    with patch("app.ai.services.client") as factory:
        factory.return_value.responses.create.return_value.__enter__.return_value = iter(events)
        parts = []
        with pytest.raises(RuntimeError, match="response_incomplete"):
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


def test_event_analysis_uses_high_reasoning(config, feed, item):
    article, _ = ingest(feed, item)
    event = Event.objects.create(name="芯片事件", description="跟踪芯片产业", keywords="芯片")
    with patch("app.ai.services.structured") as structured_call:
        structured_call.side_effect = [
            LinkSuggestion(relevant=True, reason="报道直接描述事件进展"),
            EventDraft(title="新进展", summary="事件出现新进展。", citations=[article.current_id]),
        ]
        suggest_event_links(event, article.current)
        draft_event_update(event, [article.current])
    assert structured_call.call_count == 2
    assert all(call.kwargs["reasoning_effort"] == "high" for call in structured_call.call_args_list)
    assert [call.kwargs["max_output_tokens"] for call in structured_call.call_args_list] == [4000, 6000]


def test_event_ai_automatically_publishes_relevant_report(config, feed, item):
    article, _ = ingest(feed, item)
    event = Event.objects.create(name="芯片事件", description="跟踪芯片产业", keywords="芯片")
    candidate = Candidate.objects.create(event=event, article=article)
    with (
        patch(
            "app.ai.services.suggest_event_links",
            return_value=LinkSuggestion(relevant=True, reason="直接报道事件进展"),
        ),
        patch(
            "app.ai.services.draft_event_update",
            return_value=EventDraft(
                title="芯片事件出现新进展",
                summary="报道提供了可核验的新信息。",
                citations=[article.current_id],
            ),
        ),
    ):
        result = event_ai(event.pk, article.pk)
    candidate.refresh_from_db()
    node = Node.objects.get(event=event)
    event.refresh_from_db()
    assert result == {"node": node.pk, "relevant": True, "published": True}
    assert candidate.status == "accepted"
    assert node.confirmed is True
    assert node.reports.get().version_id == article.current_id
    assert node.title in event.overview


def test_event_ai_automatically_rejects_unrelated_report(config, feed, item):
    article, _ = ingest(feed, item)
    event = Event.objects.create(name="芯片事件", description="跟踪芯片产业", keywords="芯片")
    candidate = Candidate.objects.create(event=event, article=article)
    with patch(
        "app.ai.services.suggest_event_links",
        return_value=LinkSuggestion(relevant=False, reason="只有关键词重合"),
    ):
        result = event_ai(event.pk, article.pk)
    candidate.refresh_from_db()
    assert result == {"relevant": False, "filtered": True}
    assert candidate.status == "rejected"
    assert candidate.reason == "只有关键词重合"
    assert not Node.objects.filter(event=event).exists()


def test_ai_discovers_and_creates_major_event(config, feed, item):
    first, _ = ingest(feed, item)
    first.breaking = True
    first.save(update_fields=["breaking"])
    second, _ = ingest(
        feed,
        {
            **item,
            "url": "https://example.org/news/2",
            "guid": "news2",
            "title": "人工智能芯片供应出现重大变化",
            "summary": "多家机构正在评估这一变化带来的影响。",
        },
    )
    result = MajorEventScan(
        proposals=[
            MajorEventProposal(
                name="人工智能芯片供应变化",
                description="全球人工智能芯片供应出现持续变化。",
                keywords=["人工智能芯片", "芯片供应"],
                update_title="芯片供应出现新变化",
                update_summary="两篇报道显示相关变化正在持续。",
                citations=[first.current_id, second.current_id],
                significance="影响产业供应并可能继续发展",
            )
        ],
        retirements=[],
    )
    with patch("app.ai.services.identify_major_events", return_value=result):
        outcome = discover_major_events(limit=10)
    event = Event.objects.get()
    node = event.nodes.get()
    assert outcome["created_events"] == 1
    assert event.auto_managed is True and event.status == "tracking"
    assert node.confirmed is True and node.reports.count() == 2
    assert EventReview.objects.filter(status="selected").count() == 2
    with patch("app.ai.services.identify_major_events") as identify:
        repeated = discover_major_events(limit=10)
    identify.assert_not_called()
    assert repeated["reviewed"] == 0
    assert Event.objects.count() == 1 and Node.objects.count() == 1


def test_ai_does_not_create_single_source_non_breaking_event(config, feed, item):
    article, _ = ingest(feed, item)
    result = MajorEventScan(
        proposals=[
            MajorEventProposal(
                name="普通单篇动态",
                description="只有一篇普通报道。",
                keywords=["普通动态"],
                update_title="普通动态",
                update_summary="缺少第二来源或突发信号。",
                citations=[article.current_id],
                significance="模型建议但证据门槛不足",
            )
        ],
        retirements=[],
    )
    with patch("app.ai.services.identify_major_events", return_value=result):
        outcome = discover_major_events(limit=10)
    assert outcome["created_events"] == 0
    assert not Event.objects.exists()
    assert EventReview.objects.get(article=article).status == "excluded"


def test_ai_ends_stale_auto_event_but_keeps_audit_history(config, feed, item):
    ingest(feed, item)
    stale = timezone.now() - timedelta(days=2)
    event = Event.objects.create(
        name="已结束的自动事件",
        description="用于生命周期检查",
        keywords="自动事件",
        auto_managed=True,
        created_at=stale,
        overview_at=stale,
    )
    result = MajorEventScan(
        proposals=[],
        retirements=[EventRetirement(event_id=event.pk, reason="事件已经明确结束")],
    )
    with patch("app.ai.services.identify_major_events", return_value=result):
        outcome = discover_major_events(limit=10)
    event.refresh_from_db()
    assert outcome["retired_events"] == 1
    assert event.status == "ended"
    assert event.lifecycle_note == "事件已经明确结束"
    assert event.end is not None


def test_forced_event_audit_can_remove_new_false_positive(config):
    event = Event.objects.create(
        name="普通产品动态",
        description="不应作为重大事件持续追踪",
        keywords="产品动态",
        auto_managed=True,
    )
    result = MajorEventScan(
        proposals=[],
        retirements=[EventRetirement(event_id=event.pk, reason="不足以构成重大事件")],
    )
    with patch("app.ai.services.identify_major_events", return_value=result):
        outcome = audit_auto_events(force=True)
    event.refresh_from_db()
    assert outcome == {"reviewed_events": 1, "retired_events": 1}
    assert event.status == "ended"
