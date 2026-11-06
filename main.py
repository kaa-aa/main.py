import re
from collections import Counter
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="급식 연관 규칙 분석기", layout="wide")
st.title("🍽️ 송탄고 급식 연관 규칙 분석")


# 1. 데이터 로드 및 전처리
@st.cache_data
def load_and_preprocess_data():
    url = "https://raw.githubusercontent.com/it-teacher-go/data-share-/main/songtan_meals_184.csv"
    df = pd.read_csv(url, encoding="utf-8")
    transactions = []
    all_menus = set()

    for raw_menu in df["메뉴"].dropna():
        cleaned_menu_str = re.sub(r"\(.*?\)", "", str(raw_menu))
        items = [
            item.strip() for item in cleaned_menu_str.split("|") if item.strip()
        ]
        unique_items = sorted(list(set(items)))
        if unique_items:
            transactions.append(unique_items)
            all_menus.update(unique_items)

    return transactions, sorted(list(all_menus))


transactions, all_menus = load_and_preprocess_data()
total_days = len(transactions)

# 2. 빈도수 및 동시 출현 계산
item_counts = Counter()
pair_counts = Counter()

for tx in transactions:
    for item in tx:
        item_counts[item] += 1
    for pair in combinations(tx, 2):
        pair_counts[tuple(sorted(pair))] += 1


# 3. 연관 규칙 생성
@st.cache_data
def generate_rules(_transactions, _item_counts, _pair_counts, total_days):
    rules = []
    for (item_a, item_b), co_occurrence in _pair_counts.items():
        supp_a = _item_counts[item_a] / total_days
        supp_b = _item_counts[item_b] / total_days
        support = co_occurrence / total_days

        # 규칙 1: A -> B
        conf_a_b = co_occurrence / _item_counts[item_a]
        lift_a_b = conf_a_b / supp_b
        rules.append(
            {
                "조건": item_a,
                "결과": item_b,
                "동시": co_occurrence,
                "지지도": support,
                "신뢰도": conf_a_b,
                "향상도": lift_a_b,
                "규칙명": f"{item_a} ➔ {item_b}",
            }
        )

        # 규칙 2: B -> A
        conf_b_a = co_occurrence / _item_counts[item_b]
        lift_b_a = conf_b_a / supp_a
        rules.append(
            {
                "조건": item_b,
                "결과": item_a,
                "동시": co_occurrence,
                "지지도": support,
                "신뢰도": conf_b_a,
                "향상도": lift_b_a,
                "규칙명": f"{item_b} ➔ {item_a}",
            }
        )

    return pd.DataFrame(rules)


rules_df = generate_rules(transactions, item_counts, pair_counts, total_days)

# 4. 사이드바 컨트롤
st.sidebar.header("🔍 검색 및 필터 설정")
selected_menu = st.sidebar.selectbox(
    "메뉴 선택 (전체 보기는 '전체')", ["전체"] + all_menus
)
min_co_occurrence = st.sidebar.slider(
    "최소 동시 일수", min_value=1, max_value=10, value=1, step=1
)
sort_option = st.sidebar.radio(
    "정렬 기준 선택", options=["향상도 순", "신뢰도 순", "동시 순"]
)

sort_column_map = {"향상도 순": "향상도", "신뢰도 순": "신뢰도", "동시 순": "동시"}
sort_column = sort_column_map[sort_option]

# 데이터 필터링 및 정렬
filtered_df = rules_df[rules_df["동시"] >= min_co_occurrence].copy()
if selected_menu != "전체":
    filtered_df = filtered_df[
        (filtered_df["조건"] == selected_menu)
        | (filtered_df["결과"] == selected_menu)
    ]

filtered_df = filtered_df.sort_values(
    by=[sort_column, "동시"], ascending=False
).reset_index(drop=True)

# 5. 요약 정보 표시
st.markdown(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {len(all_menus)}개 | **함께 나온 적이 있는 메뉴 쌍의 수:** {len(pair_counts)}개"
)
st.info(
    f"💡 현재 필터 조건(최소 동시 일수 {min_co_occurrence}일 이상)에 해당하는 연관 규칙은 총 **{len(filtered_df)}개**입니다."
)
st.divider()

# 6. Plotly 가로 막대그래프
st.subheader("📊 향상도 상위 10개 규칙")
if not filtered_df.empty:
    top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10)
    top10_plot_df = top10_df.sort_values(by="향상도", ascending=True)

    fig = px.bar(
        top10_plot_df,
        x="향상도",
        y="규칙명",
        orientation="h",
        text=top10_plot_df["향상도"].apply(lambda x: f"{x:.2f}"),
        labels={"향상도": "향상도 (Lift)", "규칙명": "연관 규칙"},
        color="향상도",
        color_continuous_scale="Blues",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=450, showlegend=False)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("조건에 해당하는 규칙이 없습니다.")

# 7. 규칙 표 출력
st.subheader("📋 규칙 상세 목록")
display_columns = ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
st.dataframe(
    filtered_df[display_columns].style.format(
        {"지지도": "{:.4f}", "신뢰도": "{:.4f}", "향상도": "{:.4f}"}
    ),
    use_container_width=True,
)

st.divider()

# 8. 함께 나온 적 없는 짝 화면
st.subheader("❓ 함께 나온 적 없는 짝 찾아보기")
target_menu = st.selectbox("탐색할 메뉴 선택", all_menus)

if target_menu:
    target_days = item_counts[target_menu]
    co_occurring_menus = set()

    for (m1, m2), cnt in pair_counts.items():
        if cnt > 0:
            if m1 == target_menu:
                co_occurring_menus.add(m2)
            elif m2 == target_menu:
                co_occurring_menus.add(m1)

    never_together = [
        {"메뉴": menu, "단독 등장 일수": cnt}
        for menu, cnt in item_counts.items()
        if menu != target_menu
        and menu not in co_occurring_menus
        and cnt >= 10
    ]
    never_df = pd.DataFrame(never_together)

    st.write(
        f"**선택한 메뉴:** `{target_menu}` (총 등장 일수: **{target_days}일**)"
    )
    if not never_df.empty:
        never_df = never_df.sort_values(
            by="단독 등장 일수", ascending=False
        ).reset_index(drop=True)
        st.dataframe(never_df, use_container_width=True)
    else:
        st.write(
            "선택한 메뉴와 함께 나온 적 없으면서 10일 이상 등장한 메뉴가 없습니다."
        )
