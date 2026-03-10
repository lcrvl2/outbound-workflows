#!/usr/bin/env python3
"""Compare Haiku vs Sonnet intel extraction on two fresh JDs (no prior context)."""

import json
import os
import requests
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / '.env')
except ImportError:
    pass

API_KEY = os.getenv('ANTHROPIC_API_KEY')
API_URL = 'https://api.anthropic.com/v1/messages'

# ── Fresh JDs scraped from WTTJ ──────────────────────────────────────────────

JDS = {
    "sharkninja": {
        "company_name": "SharkNinja",
        "employee_count": 3600,
        "industry": "E-commerce / Consumer Electronics",
        "country": "France",
        "company_context": "SharkNinja: Global product design and technology company. Diversified portfolio of 5-star rated lifestyle solutions across Home, Kitchen, and Beauty. Powered by Shark and Ninja brands. 3,600+ associates globally. Headquartered in Needham, Massachusetts. Revenue: $5.5 Billion. Founded 1994. Expanding in France/EMEA.",
        "jd_text": """Paid Social Creator, France

About Us
SharkNinja is a global product design and technology company with a diversified portfolio of 5-star rated lifestyle solutions across Home, Kitchen, and Beauty. Powered by our trusted Shark and Ninja brands, we're known for turning breakthrough innovation into products people love — and talk about. Headquartered in Needham, Massachusetts, with 3,600+ associates globally, SharkNinja operates across major international markets, including France.

As our brands scale, social is where growth is created — not just communicated. We're building a social creative engine that blends cultural relevance with performance rigor, and we're looking for creators who know how to make work that converts and connects.

Why This Role Matters
Paid social at SharkNinja isn't about polishing ads — it's about turning ideas into high-performing creative that earns attention across the funnel.

The Paid Social Editor is a hands-on maker responsible for transforming raw footage, creator content, and product assets into thumb-stopping, performance-driven social video. This role sits at the intersection of creative, culture, and conversion, supporting both paid and organic social across one core brand category (Beauty, Shark Home, or Ninja).

You'll move fast, test often, and ship constantly — while maintaining a high creative bar and strong point of view.

What You'll Do:

Create Performance-Driven Social Video
- Rapidly edit and optimize short-form video for paid social across Meta, TikTok, YouTube Shorts, and emerging placements
- Transform raw product footage, influencer/UCG, and internal content into high-converting assets aligned to full-funnel KPIs (awareness → consideration → conversion)
- Design creative with performance in mind — strong hooks, clear product moments, and compelling CTAs

Edit, Iterate, Scale
- Produce multiple creative variations for A/B testing and optimization
- Partner with performance marketing teams to iterate based on real-time results
- Repurpose influencer and internal content into fresh, native-feeling paid assets

Own Organic Execution for Your Brand
- Create organic-first social content that builds brand voice, community, and cultural relevance
- Shoot, edit, and publish TikToks, Reels, and short-form video content
- Balance planned content with reactive, trend-driven execution

Be a Social Creator, Not Just an Editor
- Pitch ideas, write short-form concepts, and proactively identify content opportunities
- Stay deeply fluent in platform trends, formats, and editing styles
- Help shape what "great" looks like for paid and organic social creative in France and EMEA

Collaborate Across Teams
- Work closely with Social, Integrated Marketing, Brand, and Performance teams on launches and evergreen programs
- Support ongoing content needs while helping identify creative gaps and solutions

What Success Looks Like
- Paid social creative that consistently improves performance across the funnel
- Organic content that feels native, relevant, and engaging in-feed
- Fast, reliable execution without sacrificing creative quality
- Strong partnership with performance and brand teams built on trust and results

What You'll Bring:
- 1-3 years of hands-on experience creating and editing short-form social video
- Deeply fluent in TikTok, Instagram Reels, and YouTube Shorts
- A fast editor with strong instincts for hooks, pacing, and storytelling under 60 seconds
- Comfortable working in a performance environment while still thinking creatively
- Curious, proactive, and excited to experiment

Qualifications
- Fluent in English and French (written and spoken)
- Proficiency in CapCut, TikTok in-app tools, and Adobe Creative Suite (Premiere Pro; After Effects a plus)
- Experience editing for performance marketing, DTC, eCommerce, or agency environments preferred
- Strong visual taste and attention to detail
- Ability to manage multiple projects in a fast-paced environment
- Graphic design skills are a plus

SharkNinja — 3600 collaborateurs, Bureau d'études et d'ingénierie, E-commerce, Digital. Créée en 1994. Chiffre d'affaires : 5.5 Billion. Also hiring: Senior Social Media Director, France.""",
    },
    "socialy": {
        "company_name": "Socialy",
        "employee_count": 42,
        "industry": "Marketing & Advertising (Agency)",
        "country": "France",
        "company_context": "Socialy: Social media agency ('Socialy crée des Social Brands'). 40+ collaborateurs, ~40 clients in France including Pizza Hut, Gîtes de France, Floa, JCDecaux. Services: conseil, stratégie, création, production, social media. Founded 2011. Great Place to Work certified. EcoVadis Silver. Based at 11 Rue Milton, 75009 Paris. Average age: 29. Turnover: 10%.",
        "jd_text": """Social Media Manager senior

Tu es à la recherche d'un poste de Social Media Manager Senior ? Hasard de dingue ! Nous recherchons justement un·e Social Media Manager (Sénior !). N'en dis pas plus, découvre tes missions !

Au sein d'une équipe 100% social media, tu pourras :

- Créer le calendrier éditorial : définir les prises de parole sur les différents comptes (Instagram, Tiktok, X, Facebook) en relation avec les actions marketing et communication de la marque
- Coordonner les différents métiers pour l'élaboration du calendrier éditorial : graphiste pour le brief et debrief créatif, community manager pour l'animation des comptes
- Suivre les tendances et organiser une veille : nouveaux usages, trends, nouvelles plateformes, nouveaux outils
- Réaliser les reportings des différents comptes : suivre les KPI's, t'assurer des résultats et être force de proposition pour leur amélioration
- Être garant de la bonne relation client, de la qualité du travail réalisé, du respect des budgets et des délais impartis

Profil recherché:
Sache que chez Socialy, on ne met personne dans des cases, mais si tu coches celles qui arrivent qu'attends-tu pour nous rejoindre ?
✅ Tu es diplômé·e (BAC+4/5) d'une école de communication, de commerce ou d'université.
✅ Tu as au moins 5 ans d'expérience en Social Media
✅ Tu as de solides compétences en Social Media, en brand content et en influence.
✅ De nature curieuse, tu es efficace, tu as le sens de l'initiative et du travail en équipe.
✅ Ton orthographe est irréprochable.

Assez parlé de nous. Clique sur le petit bouton jaune "Postuler" et parlons de toi !

Déroulement des entretiens: Tu rencontreras Guillaume notre Social Media Strategist puis un autre Associé de l'agence si tu es intéressé·e et que tu corresponds au profil que nous recherchons !

Rencontrez Marie, Directrice du Social Media. Rencontrez Charlotte, cheffe de projet social media.

Socialy — 42 collaborateurs, Stratégie, Marketing / Communication. Créée en 2011. Âge moyen : 29 ans. Turnover : 10%. Clients: Pizza Hut, Gîtes de France, Floa, JCDecaux. Great Place to Work. EcoVadis Silver.""",
    },
}

# ── Extraction prompt (same as extract_intel.py) ─────────────────────────────

PROMPT_TEMPLATE = """You are an expert at analyzing job descriptions to extract actionable sales intelligence.

Analyze the following job description and extract structured intel. Return ONLY valid JSON with these fields:

{{
  "job_title": "exact title from the posting",
  "seniority": "junior | mid | senior | lead | director | vp | c-level",
  "responsibility_summary": "1-2 sentence summary of key responsibilities",
  "tools_mentioned": ["list", "of", "tools", "platforms", "software"],
  "competitor_tools": ["only tools that compete with social media management platforms like Hootsuite, Sprout Social, etc."],
  "pain_signals": ["inferred pain points from the job description - what problems is this hire meant to solve?"],
  "team_context": "team size, reporting structure, first hire vs expanding team",
  "hiring_urgency": "low | medium | high",
  "key_metrics": ["any KPIs or metrics mentioned"],
  "platforms_managed": ["social platforms they manage - Instagram, LinkedIn, TikTok, etc."]
}}

Rules:
- For tools_mentioned and competitor_tools: ONLY include tools that are EXPLICITLY NAMED in the text. If the JD says "social media management tools" generically, do NOT guess specific tool names. Only list a tool if its exact name appears in the job description.
- For competitor_tools, only include tools that are social media management/scheduling/analytics platforms
- For pain_signals, INFER from context (e.g., "first dedicated hire" = they had no process before; "manage 5 platforms" = struggling with scale). Use the company website context below (if provided) to enrich your understanding of the company and refine pain signals.
- For hiring_urgency: high = ASAP/immediate/urgent language; medium = standard posting; low = pipeline/future role
- If a field cannot be determined, use null for strings or empty array [] for lists
- Return ONLY the JSON object, no other text

Company Website Context: {company_context}

Job Description:
{jd_text}"""

# ── Models to compare ────────────────────────────────────────────────────────

MODELS = {
    'haiku': 'claude-haiku-4-5-20251001',
    'sonnet': 'claude-sonnet-4-5-20250929',
}

# ── Run comparison ───────────────────────────────────────────────────────────

results = {}

for jd_key, jd_data in JDS.items():
    print(f"\n{'='*60}")
    print(f"Company: {jd_data['company_name']}")
    print(f"{'='*60}")

    prompt = PROMPT_TEMPLATE.format(
        company_context=jd_data['company_context'],
        jd_text=jd_data['jd_text'],
    )

    results[jd_key] = {
        'company_name': jd_data['company_name'],
        'employee_count': jd_data['employee_count'],
        'industry': jd_data['industry'],
        'jd_snippet': jd_data['jd_text'][:200] + '...',
    }

    for label, model_id in MODELS.items():
        print(f"  Running {label} ({model_id})...")
        resp = requests.post(API_URL, headers={
            'Content-Type': 'application/json',
            'x-api-key': API_KEY,
            'anthropic-version': '2023-06-01',
        }, json={
            'model': model_id,
            'max_tokens': 2048,
            'messages': [{'role': 'user', 'content': prompt}],
        }, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        text = data['content'][0]['text'].strip()

        # Parse JSON
        if text.startswith('```'):
            text = text.split('\n', 1)[1] if '\n' in text else text[3:]
            if text.endswith('```'):
                text = text[:-3]
            text = text.strip()
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            text = text[start:end + 1]

        results[jd_key][label] = json.loads(text)
        usage = data['usage']
        print(f"    Done. Input: {usage['input_tokens']} tokens, Output: {usage['output_tokens']} tokens")
        time.sleep(1)

# ── Save ─────────────────────────────────────────────────────────────────────

out_path = Path(__file__).parent.parent / 'generated-outputs/test_wttj/_model_comparison_v2.json'
with open(out_path, 'w') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\nSaved to {out_path}")
