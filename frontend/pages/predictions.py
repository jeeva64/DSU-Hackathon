"""AI Predictions page: ML status, model metrics and on-demand predictions."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from frontend.components.metrics import (
    fallback_note,
    pipeline_diagram,
    section_header,
    severity_pill,
)
from frontend.components.tables import show_table
from frontend.config import DEMO_DPCS, DEMO_ML_PREDICTIONS, DEMO_ML_STATUS
from frontend.utils.formatting import fmt_metric, fmt_number, severity_label
from frontend.utils.state import bump_refresh, demo_mode_enabled, get_client, refresh_key

_REGRESSION_METRICS = ("mae", "rmse", "mape", "r2", "rmse_scaled")
_CLASSIFICATION_METRICS = ("accuracy", "precision", "recall", "f1", "roc_auc")
_TARGET_LABELS = {
    "arrival_count": "Expected Arrivals",
    "quantity": "Expected Quantity",
    "overload": "Overload Probability",
}


@st.cache_data(ttl=20, show_spinner=False)
def _load_ml_status(rev: int, demo: bool):
    if demo:
        return DEMO_ML_STATUS, "demo", None
    client = get_client()
    return client.get_ml_status(fallback=DEMO_ML_STATUS)


def _metric_table(targets: dict) -> pd.DataFrame:
    rows = []
    for target, state in targets.items():
        metrics = state.get("metrics") or {}
        is_classifier = target == "overload"
        cols = list(_CLASSIFICATION_METRICS) if is_classifier else list(_REGRESSION_METRICS)
        row = {
            "Target": _TARGET_LABELS.get(target, target),
            "Model": state.get("model_type", "-") if state.get("trained") else "-",
            "Version": str(state.get("version", "-") or "-") if state.get("trained") else "-",
            "n_train": state.get("n_train", 0),
            "n_valid": state.get("n_valid", 0),
            **{k: metrics.get(k) for k in cols},
        }
        rows.append(row)
    return pd.DataFrame(rows)


def _run_prediction(client, dpc: dict, target_date: str, target: str, trained: bool):
    dpc_id = dpc.get("id")
    dpc_name = dpc.get("name")
    demo_p = DEMO_ML_PREDICTIONS.get(dpc_name, DEMO_ML_PREDICTIONS["Thanjavur Central DPC"])

    demo_result = {
        "arrivals": {"predicted_value": demo_p["arrivals"], "confidence": None, "model_version": "demo"},
        "quantity": {"predicted_value": demo_p["quantity"], "confidence": None, "model_version": "demo"},
        "congestion": {"probability": demo_p["overload_pct"] / 100, "severity": demo_p["severity"],
                       "score": demo_p["overload_pct"], "model_version": "demo"},
    }

    if not trained:
        # Model absent: use statistical backend fallback for regressions.
        arrivals, a_src, _ = client.generate_prediction(dpc_id, target_date, "arrival_count")
        quantity, q_src, _ = client.generate_prediction(dpc_id, target_date, "quantity")
        if a_src == "demo" or q_src == "demo":
            return demo_result, "demo"
        return {
            "arrivals": {"predicted_value": arrivals.get("predicted_value"),
                         "confidence": arrivals.get("confidence"),
                         "model_version": arrivals.get("model_version")},
            "quantity": {"predicted_value": quantity.get("predicted_value"),
                         "confidence": quantity.get("confidence"),
                         "model_version": quantity.get("model_version")},
            "congestion": None,
        }, "statistical"

    response, src, _ = client.ml_predict(dpc_id, target_date, target)
    if src == "demo" or not response:
        return demo_result, "demo"
    if response.get("status") == "not_trained":
        return demo_result, "not_trained"

    results = response.get("results", {})
    out = {key: item for key in ("arrivals", "quantity", "congestion") if (item := results.get(key))}
    return out or None, "backend"


def render() -> None:
    demo = demo_mode_enabled()
    rev = refresh_key("predictions")
    status, source, error = _load_ml_status(rev, demo)

    st.markdown("## AI Predictions")

    pipeline_diagram([
        ("DATA LAYER", "DPC capacity + procurement + weather"),
        ("ML LAYER", "scikit-learn: RF / gradient boosting"),
        ("PREDICTION", "arrivals, quantity, overload"),
        ("OFFICER", "human decides: divert, extend, hold"),
    ])

    if demo:
        fallback_note()
    else:
        st.caption("Real ML predictions from trained scikit-learn models (synthetic history).")
        if source == "demo":
            st.caption("Demo fallback data - backend ML data unavailable.")

    trained = bool(status.get("trained"))
    st.markdown("#### Model Registry Status")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Status", "Trained" if trained else "Not trained")
    col2.metric("Current version", str(status.get("current_version") or "-").replace("v-", ""))
    col3.metric("Trained at", _pretty_timestamp(status.get("trained_at")))
    col4.metric("Validation window", "14 days")
    st.caption(status.get("message") or ".")

    section_header(
        "Holdout Metrics",
        "Chronological train/validate split; metrics on validation rows only.",
    )
    targets = status.get("targets", {}) or {}
    if targets:
        show_table(_metric_table(targets), height=160)
    else:
        st.info("No model metrics available.")

    st.markdown("---")
    section_header("Run a Prediction")
    c1, c2, c3 = st.columns(3)
    dpc_names = [d.get("name") for d in DEMO_DPCS]
    dpc_name = c1.selectbox("DPC", dpc_names)
    target_date = c2.date_input("Target date", value=date.today())
    target = c3.selectbox("Target", ["all", "arrivals", "quantity", "congestion"])
    target_date_iso = target_date.isoformat()

    dpc = next((d for d in DEMO_DPCS if d.get("name") == dpc_name), DEMO_DPCS[0])

    if st.button("Run prediction", type="primary"):
        result, how = _run_prediction(get_client(), dpc, target_date_iso, target, trained)
        st.session_state["ns_prediction_result"] = result
        st.session_state["ns_prediction_how"] = how

    result = st.session_state.get("ns_prediction_result")
    how = st.session_state.get("ns_prediction_how")

    if result:
        how_notes = {
            "backend": "Prediction computed from trained ML models.",
            "statistical": "Statistical fallback (mean + weekend factor) - ML models not trained.",
            "not_trained": "ML models not trained - regressions fell back to statistical; congestion is a synthetic estimate.",
            "demo": "Demo fallback data - Synthetic.",
        }
        st.caption(how_notes.get(how, ""))

        cols = st.columns(3)
        arr = result.get("arrivals")
        qty = result.get("quantity")
        con = result.get("congestion")

        if arr and arr.get("predicted_value") is not None:
            sub = f"conf {fmt_metric(arr.get('confidence'))}" if arr.get("confidence") is not None else None
            cols[0].metric("Expected arrivals", fmt_number(arr["predicted_value"]), sub or None)
        if qty and qty.get("predicted_value") is not None:
            sub = f"conf {fmt_metric(qty.get('confidence'))}" if qty.get("confidence") is not None else None
            cols[1].metric("Expected quantity (quintals)", fmt_number(qty["predicted_value"], 1), sub or None)
        if con and con.get("probability") is not None:
            cols[2].metric(
                "Overload probability",
                f"{float(con['probability']) * 100:.1f}%",
                severity_label(con.get("severity") or "low"),
            )
            st.markdown(severity_pill(con.get("severity") or "low"), unsafe_allow_html=True)
        else:
            cols[2].metric("Overload probability", "not trained", "statistical fallback")

    st.markdown("---")
    if st.button("Refresh ML status"):
        bump_refresh("predictions")
        st.rerun()


def _pretty_timestamp(value) -> str:
    if not value:
        return "-"
    return str(value)[:16].replace("T", " ")