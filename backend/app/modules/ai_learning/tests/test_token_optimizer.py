import pytest
from app.modules.ai_learning.token_optimizer import TokenOptimizer, CostEstimate

def test_estimate_cost_based_on_unit_count():
    """Token 估算与单元数成正比"""
    optimizer = TokenOptimizer()

    small = optimizer.estimate_cost(unit_count=1)
    large = optimizer.estimate_cost(unit_count=10)

    assert large.total_tokens == small.total_tokens * 10
    assert large.estimated_cost_usd == small.estimated_cost_usd * 10
    assert small.estimated_cost_usd > 0

def test_cost_estimate_has_actual_tokens_field():
    """CostEstimate 有 actual_tokens 字段，默认 None"""
    est = CostEstimate(total_tokens=5000, estimated_cost_usd=0.15, unit_count=10)
    assert est.actual_tokens is None

    est.actual_tokens = 4800
    assert est.actual_tokens == 4800

def test_estimate_cost_default_content_length():
    """默认 avg_content_length=2000"""
    optimizer = TokenOptimizer()
    est = optimizer.estimate_cost(unit_count=1)
    # tokens = 2000//4 + 500 = 1000
    assert est.total_tokens == 1000
