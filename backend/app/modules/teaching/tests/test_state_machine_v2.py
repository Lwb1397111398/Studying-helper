from app.modules.teaching.state_machine_v2 import (
    ASSESS,
    ASSESSMENT_SKIPPED,
    ASSESSMENT_SUBMITTED,
    ASSET_READY,
    COMPLETED,
    DIAGNOSE,
    DIAGNOSIS_SUBMITTED,
    EXPLAIN,
    EXPLANATION_ACKNOWLEDGED,
    GUIDED_PRACTICE,
    PAUSED,
    PRACTICE_SUBMITTED,
    PREPARE,
    PREREQUISITE_INTERVENTION,
    REASSESS,
    REPAIR,
    REPAIR_COMPLETED,
    REFLECT,
    SESSION_STARTED,
    USER_ASKED,
    transition,
)


def test_main_happy_path():
    r = transition("?", SESSION_STARTED)
    assert r.next_state == PREPARE
    r = transition(PREPARE, ASSET_READY, {"asset_readiness": "teachable"})
    assert r.next_state == DIAGNOSE
    r = transition(DIAGNOSE, DIAGNOSIS_SUBMITTED, {"diagnosis_summary": "mixed"})
    assert r.next_state == "activate"
    r = transition("activate", EXPLANATION_ACKNOWLEDGED)
    assert r.next_state == EXPLAIN
    r = transition(EXPLAIN, EXPLANATION_ACKNOWLEDGED)
    assert r.next_state == GUIDED_PRACTICE
    r = transition(GUIDED_PRACTICE, PRACTICE_SUBMITTED)
    assert r.next_state == ASSESS
    r = transition(ASSESS, ASSESSMENT_SUBMITTED, {"required_objectives_passed": True})
    assert r.next_state == REFLECT
    r = transition(REFLECT, EXPLANATION_ACKNOWLEDGED, {"required_objectives_passed": True})
    assert r.next_state == "schedule_review"
    r = transition(
        "schedule_review",
        EXPLANATION_ACKNOWLEDGED,
        {"required_objectives_passed": True},
    )
    assert r.next_state == COMPLETED
    assert r.completion_status == "completed_mastered"


def test_repair_then_reassess():
    r = transition(
        ASSESS,
        ASSESSMENT_SUBMITTED,
        {"required_objectives_passed": False, "repairable_gaps": True, "repair_rounds": 0},
    )
    assert r.next_state == REPAIR
    r = transition(REPAIR, REPAIR_COMPLETED)
    assert r.next_state == REASSESS


def test_skip_assessment_not_mastered():
    r = transition(ASSESS, ASSESSMENT_SKIPPED)
    assert r.completion_status == "visited_only"
    assert "do_not_mark_mastered" in r.side_effects


def test_missing_prereq_spawns_child():
    r = transition(
        DIAGNOSE,
        DIAGNOSIS_SUBMITTED,
        {"diagnosis_summary": "missing_prereq"},
    )
    assert r.next_state == PREREQUISITE_INTERVENTION
    assert "spawn_prereq_child" in r.side_effects


def test_user_ask_keeps_state():
    r = transition(EXPLAIN, USER_ASKED)
    assert r.next_state == EXPLAIN
    assert "handle_question_interrupt" in r.side_effects


def test_repeated_failure_needs_support():
    r = transition(
        ASSESS,
        ASSESSMENT_SUBMITTED,
        {
            "required_objectives_passed": False,
            "repairable_gaps": True,
            "repair_rounds": 2,
            "max_repair_rounds": 2,
        },
    )
    assert r.next_state == PAUSED
    assert r.completion_status == "needs_support"
