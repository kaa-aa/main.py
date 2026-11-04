import re
from collections import Counter
from itertools import combinations
import pandas as pd
import plotly.express as px
import streamlit as st

# 페이지 기본 설정
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
        # 괄호 및 괄호 내부 내용 제거
        cleaned_menu_str = re.sub(r"\(.*?\)", "", str(raw_menu))

        # 파이프(|) 기호로 분리 및 공백 제거
        items = [
            item.strip() for item in cleaned_menu_str.split("|") if item.strip()
        ]

        # 중복 메뉴 제거 (하루 식단 내 동일 메뉴 중복 카운트 방지)
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
        pair_counts[pair] += 1


# 3. 연관 규칙 생성 (방향 고려: A->B, B->A)
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

# 4. 사이드바 컨트롤 (메뉴 선택 & 정렬)
st.sidebar.header("🔍 검색 및 정렬 설정")

selected_menu = st.sidebar.selectbox(
    "메뉴 선택 (전체 보기는 '전체')", ["전체"] + all_menus
)

sort_option = st.sidebar.radio(
    "정렬 기준 선택", options=["향상도 순", "신뢰도 순", "동시 순"]
)

sort_column_map = {
    "향상도 순": "향상도",
    "신뢰도 순": "신뢰도",
    "동시 순": "동시",
}
sort_column = sort_column_map[sort_option]

# 데이터 필터링 및 정렬
if selected_menu != "전체":
    filtered_df = rules_df[
        (rules_df["조건"] == selected_menu)
        | (rules_df["결과"] == selected_menu)
    ].copy()
else:
    filtered_df = rules_df.copy()

filtered_df = filtered_df.sort_values(
    by=[sort_column, "동시"], ascending=False
).reset_index(drop=True)

# 5. 요약 정보 표시 (한 줄로 출력)
unique_pairs_count = len(pair_counts)
menu_types_count = len(all_menus)

st.markdown(
    f"**급식 일수:** {total_days}일 | **메뉴 종류 수:** {menu_types_count}개 | **함께 나온 적이 있는 메뉴 쌍의 수:** {unique_pairs_count}개"
)
st.divider()

# 6. Plotly 가로 막대그래프 (상위 10개)
st.subheader("📊 향상도 상위 10개 규칙")

if not filtered_df.empty:
    # 향상도 기준으로 상위 10개 추출
    top10_df = filtered_df.sort_values(by="향상도", ascending=False).head(10)
    # 그래프 시각화를 위해 순서 정렬 (위에서부터 1위가 오도록)
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
    st.info("조건에 해당하는 규칙이 없습니다.")

# 7. 표 출력
st.subheader("📋 규칙 상세 목록")

display_columns = ["조건", "결과", "동시", "지지도", "신뢰도", "향상도"]
st.dataframe(
    filtered_df[display_columns].style.format(
        {"지지도": "{:.4f}", "신뢰도": "{:.4f}", "향상도": "{:.4f}"}
    ),
    use_container_width=True,
)
