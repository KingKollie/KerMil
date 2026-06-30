import streamlit as st
from recommender import get_recommendation

# Page config
st.set_page_config(
    page_title="KerMil Skin Care & Hair",
    page_icon="✨",
    layout="centered"
)

# Header
st.title("✨ KerMil Skin Care & Hair")
st.subheader("AI-Powered Beauty Recommendations for the Culture 🖤")
st.markdown("---")

# Questionnaire
st.markdown("### Tell us about yourself")

name = st.text_input("Your Name", placeholder="Enter your name")

gender = st.selectbox("Gender", [
    "Woman",
    "Man",
    "Non-binary / Other"
])

st.markdown("### 💇 Hair Profile")

hair_type = st.selectbox("Hair Type", [
    "Natural (4a/4b/4c)",
    "Natural (3a/3b/3c)",
    "Locs / Dreadlocks",
    "Relaxed",
    "Braids / Protective styles",
    "Men's Facial Hair",
    "Bald Head Care"
])

hair_concerns = st.multiselect("Hair Concerns (select all that apply)", [
    "Dryness",
    "Breakage",
    "Shrinkage",
    "Scalp itchiness",
    "Dandruff",
    "Slow growth",
    "Frizz",
    "Loc maintenance",
    "Edge care",
    "Shine / moisture"
])

st.markdown("### 🧴 Skin Profile")

skin_type = st.selectbox("Skin Type", [
    "Oily",
    "Dry",
    "Combination",
    "Normal",
    "Sensitive"
])

skin_concerns = st.multiselect("Skin Concerns (select all that apply)", [
    "Dark spots / hyperpigmentation",
    "Acne / breakouts",
    "Uneven skin tone",
    "Dullness",
    "Oiliness",
    "Dryness / ashy skin",
    "Fine lines",
    "Razor bumps",
    "Sensitivity / irritation"
])

st.markdown("### 💰 Budget")

budget = st.selectbox("Budget per product", [
    "Under $10",
    "Under $20",
    "Under $30",
    "$30 - $50",
    "No limit — just what works"
])

st.markdown("---")

# Submit
if st.button("✨ Get My Personalized Recommendations", use_container_width=True):
    if not name:
        st.warning("Please enter your name so we can personalize your results!")
    elif not hair_concerns:
        st.warning("Please select at least one hair concern.")
    elif not skin_concerns:
        st.warning("Please select at least one skin concern.")
    else:
        profile = {
            "name": name,
            "gender": gender,
            "hair_type": hair_type,
            "hair_concerns": ", ".join(hair_concerns),
            "skin_type": skin_type,
            "skin_concerns": ", ".join(skin_concerns),
            "budget": budget
        }

        with st.spinner("✨ Building your personalized routine..."):
            try:
                result = get_recommendation(profile)
                st.markdown("---")
                st.markdown(f"### 🖤 {name}'s Custom KerMil Routine")
                st.markdown(result)
            except Exception as e:
                st.error(f"Something went wrong: {e}")
