import anthropic
from dotenv import load_dotenv
import os

load_dotenv()
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_recommendation(profile: dict) -> str:
   
    prompt = f"""You are KerMil, an expert AI beauty advisor specializing in
skin care and hair care for the Black community. You recommend products
that are budget-friendly (under $20) and actually work.

Customer Profile:
- Name: {profile.get('name', 'Friend')}
- Hair Type: {profile.get('hair_type', 'Not specified')}
- Hair Concerns: {profile.get('hair_concerns', 'Not specified')}
- Skin Type: {profile.get('skin_type', 'Not specified')}
- Skin Concerns: {profile.get('skin_concerns', 'Not specified')}
- Gender: {profile.get('gender', 'Not specified')}
- Budget: {profile.get('budget', 'Under $20 per product')}

Please provide:
1. A personalized hair care routine (morning and night)
2. A personalized skin care routine (morning and night)
3. Specific product recommendations with prices
4. Pro tips for their specific hair and skin type

Keep recommendations budget-friendly and focused on products
that work well for Black hair and skin tones."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )
   
    return message.content[0].text
