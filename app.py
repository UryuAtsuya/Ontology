import streamlit as st
import re
import matplotlib.pyplot as plt

st.set_page_config(page_title="Ontology × LLM Demo", layout="wide")

# ====== 固定データ（あなたのruns10.txtの平均値） ======
metrics = {
    "EditSim":  {"zero": 0.143, "few": 0.342},
    "Token-F1": {"zero": 0.105, "few": 0.336},
    "Jaccard":  {"zero": 0.049, "few": 0.229},
    "ROUGE-L":  {"zero": 0.063, "few": 0.268},
    "chrF":     {"zero": 0.153, "few": 0.383},
    "BERTScore":{"zero": 0.569, "few": 0.765},
}

# ====== デモ用の超軽量“推論” ======
# ここは実システムがある場合はAPIコールに差し替えてください
def baseline_answer(question: str) -> str:
    # あえて“曖昧め”にする（Zero-shotの雰囲気）
    if "2000" in question:
        return ("It seems the building follows some seismic rules, "
                "but I cannot clearly determine if it matches the 2000 standard.")
    if "耐震" in question:
        return ("The building may have certain seismic considerations, "
                "but I’m not fully sure without more details.")
    return ("I’m not certain. I might need additional context to answer precisely.")

def ontology_answer(question: str, facts: dict) -> str:
    """
    facts にはあなたのパイプラインから取れる事実を渡す想定
    ここではデモ用に最低限を仮定:
      facts = {
        "year": 2010,
        "grade": "耐震等級3",
        "devices": ["免震支承"],
        "area": "東京都",
    }
    """
    year = facts.get("year")
    grade = facts.get("grade")
    devices = facts.get("devices", [])
    area = facts.get("area")

    # ルール例：2000年以降→2000基準、免震支承→免震構造_v
    seismic_standard = None
    if year is not None:
        if year < 1981:
            seismic_standard = "旧耐震_v（～1980）"
        elif 1981 <= year < 2000:
            seismic_standard = "新耐震1981_v（1981～1999）"
        else:
            seismic_standard = "2000基準_v（2000～）"

    tech = []
    if any("免震" in d for d in devices):
        tech.append("免震構造_v")
    if any("制震" in d for d in devices):
        tech.append("制震構造_v")

    # 質問に合わせてテンプレ
    if re.search(r"2000.*満た|2000.*基準|2000年.*基準", question):
        if seismic_standard and "2000" in seismic_standard:
            verdict = "はい。"
        else:
            verdict = "いいえ（または不明）。"
        explain = []
        if year is not None:
            explain.append(f"建築年: {year} → {seismic_standard}")
        if grade:
            explain.append(f"耐震等級: {grade}")
        if tech:
            explain.append("耐震技術: " + "・".join(tech))
        if area:
            explain.append(f"所在地: {area}")
        return f"{verdict}\n" + "\n".join(explain)

    # 汎用説明
    bits = []
    if year is not None:
        bits.append(f"建築年: {year}（区分: {seismic_standard}）")
    if grade:
        bits.append(f"耐震等級: {grade}")
    if devices:
        bits.append("装置: " + "・".join(devices))
    if tech:
        bits.append("耐震技術: " + "・".join(tech))
    if area:
        bits.append(f"所在地: {area}")
    if not bits:
        bits.append("根拠データが不足しています。")

    return "以下の根拠に基づき回答可能です：\n" + "\n".join(bits)

# ====== UI ======
st.title("Ontology × LLM: Poster-side Demo")
st.caption("左：Ontologyなし（Zero-shot）／ 右：Ontologyあり（Few-shot＋ルール）")

demo_q = "この建物は2000年の耐震基準を満たしていますか？"
question = st.text_input("質問を入力（例：この建物は2000年の耐震基準を満たしていますか？）", value=demo_q)

# デモ用の事実（ここをあなたの実データで差し替え）
with st.expander("デモ用の建物ファクト（差し替えポイント）", expanded=False):
    st.write("※ 実運用ではここをAPIやRAG＋オントロジー問い合わせ結果で埋めます")
    colf1, colf2, colf3, colf4 = st.columns(4)
    with colf1:
        year = st.number_input("建築年", value=2010, step=1)
    with colf2:
        grade = st.text_input("耐震等級", value="耐震等級3")
    with colf3:
        devices_str = st.text_input("装置（カンマ区切り）", value="免震支承")
    with colf4:
        area = st.text_input("所在地", value="東京都")
    facts = {
        "year": int(year) if year else None,
        "grade": grade.strip() or None,
        "devices": [d.strip() for d in devices_str.split(",") if d.strip()],
        "area": area.strip() or None,
    }

col1, col2 = st.columns(2)
with col1:
    st.subheader("Ontologyなし（Zero-shot）")
    if st.button("▶ 回答を生成（Baseline）"):
        st.code(baseline_answer(question), language="markdown")

with col2:
    st.subheader("Ontologyあり（Few-shot＋ルール）")
    if st.button("▶ 回答を生成（Ontology＋LLM）"):
        st.code(ontology_answer(question, facts), language="markdown")

st.markdown("---")
st.subheader("スコア比較（平均値）")

# 棒グラフを描画
labels = list(metrics.keys())
zero_vals = [metrics[m]["zero"] for m in labels]
few_vals = [metrics[m]["few"] for m in labels]

fig = plt.figure(figsize=(8, 4))
x = range(len(labels))
bar_w = 0.38
plt.bar([i - bar_w/2 for i in x], zero_vals, width=bar_w, label="Ontologyなし")
plt.bar([i + bar_w/2 for i in x], few_vals,  width=bar_w, label="Ontologyあり")
plt.xticks(list(x), labels, rotation=25)
plt.ylabel("Score")
plt.legend()
plt.tight_layout()
st.pyplot(fig)

st.info(
    "ポイント：Ontologyありでは BERTScore 0.569 → 0.765、ROUGE-L 0.063 → 0.268 など、"
    "定量・意味的評価が安定して向上。デモでは“回答の根拠（年・等級・装置→技術）”も併せて提示できます。"
)

st.markdown("---")
st.caption("実機では、右側の生成関数をAPI（RAG+Ontology）に差し替えるだけで、同UIで本番動作に移行できます。")
