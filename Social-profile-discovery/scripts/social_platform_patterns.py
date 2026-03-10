#!/usr/bin/env python3
"""
Social Platform Patterns - URL classification, normalization, and profile typing.

Provides:
- PLATFORMS: dict of platform definitions (domains, path patterns, exclusions)
- classify_url(url) -> (platform, normalized_url, handle) or None
- classify_profile_type(handle, company_name) -> 'main' | 'regional' | 'category'
- normalize_social_url(url) -> cleaned URL
- is_share_or_intent_url(url) -> bool
"""

import re
from urllib.parse import urlparse, urlunparse

# =============================================================================
# PLATFORM DEFINITIONS
# =============================================================================

PLATFORMS = {
    'facebook': {
        'domains': ['facebook.com', 'fb.com', 'm.facebook.com', 'www.facebook.com',
                     'web.facebook.com', 'business.facebook.com'],
        'profile_patterns': [
            r'^/[\w.-]+/?$',          # /pagename
            r'^/pages/.+',             # /pages/category/pagename
            r'^/profile\.php\?id=\d+', # /profile.php?id=123
            r'^/people/.+',            # /people/Name/id
        ],
        'exclude_patterns': [
            r'/sharer', r'/share', r'/dialog/', r'/plugins/', r'/groups/',
            r'/events/', r'/photo', r'/video', r'/watch', r'/reel',
            r'/login', r'/help', r'/policies', r'/privacy',
        ],
    },
    'instagram': {
        'domains': ['instagram.com', 'www.instagram.com', 'instagr.am'],
        'profile_patterns': [
            r'^/[\w.-]+/?$',           # /username
        ],
        'exclude_patterns': [
            r'^/p/', r'^/reel/', r'^/stories/', r'^/explore/',
            r'^/accounts/', r'^/about/', r'^/legal/',
        ],
    },
    'twitter': {
        'domains': ['twitter.com', 'www.twitter.com', 'x.com', 'www.x.com',
                     'mobile.twitter.com'],
        'profile_patterns': [
            r'^/[\w]+/?$',             # /username
        ],
        'exclude_patterns': [
            r'/intent/', r'/share', r'/status/', r'/hashtag/', r'/search',
            r'/i/', r'/home', r'/explore', r'/settings', r'/tos', r'/privacy',
        ],
    },
    'linkedin': {
        'domains': ['linkedin.com', 'www.linkedin.com', 'fr.linkedin.com',
                     'de.linkedin.com', 'uk.linkedin.com'],
        'profile_patterns': [
            r'^/company/[\w-]+',       # /company/name
            r'^/in/[\w-]+',            # /in/person (less useful for companies)
            r'^/school/[\w-]+',        # /school/name
            r'^/showcase/[\w-]+',      # /showcase/name
        ],
        'exclude_patterns': [
            r'/share', r'/pulse/', r'/feed/', r'/jobs/',
            r'/learning/', r'/posts/', r'/sharer',
        ],
    },
    'tiktok': {
        'domains': ['tiktok.com', 'www.tiktok.com', 'vm.tiktok.com'],
        'profile_patterns': [
            r'^/@[\w.-]+/?$',          # /@username
        ],
        'exclude_patterns': [
            r'^/video/', r'^/t/', r'^/tag/', r'^/music/',
            r'/embed/', r'/discover',
        ],
    },
    'youtube': {
        'domains': ['youtube.com', 'www.youtube.com', 'youtu.be', 'm.youtube.com'],
        'profile_patterns': [
            r'^/@[\w.-]+',             # /@handle
            r'^/c/[\w-]+',             # /c/channelname
            r'^/channel/[\w-]+',       # /channel/UCxxxx
            r'^/user/[\w-]+',          # /user/username (legacy)
        ],
        'exclude_patterns': [
            r'^/watch', r'^/playlist', r'^/embed/', r'^/shorts/',
            r'^/live/', r'^/feed/', r'^/results',
        ],
    },
    'pinterest': {
        'domains': ['pinterest.com', 'www.pinterest.com', 'pin.it',
                     'pinterest.fr', 'pinterest.de', 'pinterest.es',
                     'pinterest.co.uk', 'pinterest.ca', 'pinterest.com.au',
                     'pinterest.co.kr', 'pinterest.jp', 'pinterest.at',
                     'pinterest.ch', 'pinterest.cl', 'pinterest.pt',
                     'pinterest.se', 'pinterest.dk', 'pinterest.nz',
                     'pinterest.ie', 'pinterest.co.in', 'pinterest.ph',
                     'br.pinterest.com', 'ar.pinterest.com', 'nl.pinterest.com',
                     'in.pinterest.com'],
        'profile_patterns': [
            r'^/[\w-]+/?$',            # /username
        ],
        'exclude_patterns': [
            r'^/pin/', r'^/search/', r'^/ideas/',
            r'^/explore/', r'^/_/',
        ],
    },
    'threads': {
        'domains': ['threads.net', 'www.threads.net'],
        'profile_patterns': [
            r'^/@[\w.-]+/?$',          # /@username
        ],
        'exclude_patterns': [],
    },
    'bluesky': {
        'domains': ['bsky.app'],
        'profile_patterns': [
            r'^/profile/[\w.-]+',      # /profile/handle.bsky.social
        ],
        'exclude_patterns': [
            r'^/search', r'^/settings',
        ],
    },
}

# Build reverse lookup: domain -> platform name
_DOMAIN_TO_PLATFORM = {}
for _platform, _config in PLATFORMS.items():
    for _domain in _config['domains']:
        _DOMAIN_TO_PLATFORM[_domain.lower()] = _platform


# =============================================================================
# SHARE / INTENT URL DETECTION
# =============================================================================

# Generic patterns that indicate a share/intent URL on any platform
SHARE_PATTERNS = [
    r'/share\b', r'/sharer\b', r'/intent/', r'/dialog/',
    r'/plugins/', r'share=', r'url=http',
]
_SHARE_RE = re.compile('|'.join(SHARE_PATTERNS), re.IGNORECASE)


def is_share_or_intent_url(url: str) -> bool:
    """Check if URL is a share/intent/plugin link rather than a profile."""
    return bool(_SHARE_RE.search(url))


# =============================================================================
# URL NORMALIZATION
# =============================================================================

def normalize_social_url(url: str) -> str:
    """
    Normalize a social media URL for deduplication:
    - Force https
    - Remove www., m., mobile. prefixes
    - Canonicalize x.com -> twitter.com
    - Strip query params and fragments
    - Remove trailing slashes
    - Lowercase domain and path
    """
    if not url:
        return ''

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return url

    try:
        parsed = urlparse(url)
    except Exception:
        return url

    # Force https
    scheme = 'https'

    # Normalize host
    host = (parsed.hostname or '').lower()
    for prefix in ('www.', 'm.', 'mobile.', 'web.', 'business.'):
        if host.startswith(prefix):
            host = host[len(prefix):]

    # Canonicalize x.com -> twitter.com
    if host == 'x.com':
        host = 'twitter.com'

    # Canonicalize localized linkedin (fr.linkedin.com -> linkedin.com)
    if host.endswith('.linkedin.com') and host != 'linkedin.com':
        host = 'linkedin.com'

    # Canonicalize localized pinterest subdomains
    if host.endswith('.pinterest.com') and host != 'pinterest.com':
        host = 'pinterest.com'

    # Normalize path: lowercase, strip trailing slash
    path = parsed.path.lower().rstrip('/')
    if not path:
        path = '/'

    # Drop query params and fragment
    normalized = urlunparse((scheme, host, path, '', '', ''))
    return normalized


# =============================================================================
# URL CLASSIFICATION
# =============================================================================

def _extract_handle(path: str, platform: str) -> str:
    """Extract the handle/identifier from a URL path."""
    path = path.strip('/').lower()
    parts = path.split('/')

    if not parts or not parts[0]:
        return ''

    if platform == 'linkedin':
        # /company/name -> name, /in/person -> person
        if len(parts) >= 2 and parts[0] in ('company', 'in', 'school', 'showcase'):
            return parts[1]
    elif platform == 'youtube':
        # /@handle -> handle, /c/name -> name, /channel/id -> id
        first = parts[0]
        if first.startswith('@'):
            return first[1:]
        if len(parts) >= 2 and first in ('c', 'channel', 'user'):
            return parts[1]
    elif platform in ('tiktok', 'threads'):
        # /@username -> username
        first = parts[0]
        if first.startswith('@'):
            return first[1:]
    elif platform == 'bluesky':
        # /profile/handle -> handle
        if len(parts) >= 2 and parts[0] == 'profile':
            return parts[1]
    else:
        # facebook, instagram, twitter, pinterest: /username -> username
        return parts[0]

    return parts[-1] if parts else ''


def classify_url(url: str):
    """
    Classify a URL as a social media profile.

    Returns: (platform, normalized_url, handle) or None if not a social profile.
    """
    if not url or not url.strip():
        return None

    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        return None

    # Quick reject: share/intent URLs
    if is_share_or_intent_url(url):
        return None

    try:
        parsed = urlparse(url)
    except Exception:
        return None

    host = (parsed.hostname or '').lower()

    # Strip common prefixes for matching
    match_host = host
    for prefix in ('www.', 'm.', 'mobile.', 'web.', 'business.'):
        if match_host.startswith(prefix):
            match_host = match_host[len(prefix):]

    # Canonicalize x.com for lookup
    if match_host == 'x.com':
        match_host = 'twitter.com'

    # Check localized linkedin
    if match_host.endswith('.linkedin.com'):
        match_host = 'linkedin.com'

    # Check localized pinterest subdomains
    if match_host.endswith('.pinterest.com'):
        match_host = 'pinterest.com'

    # Find platform by domain
    platform = _DOMAIN_TO_PLATFORM.get(match_host)
    if not platform:
        # Also check if host itself is a pinterest TLD variant
        for dom in PLATFORMS.get('pinterest', {}).get('domains', []):
            if match_host == dom.lower():
                platform = 'pinterest'
                break
    if not platform:
        return None

    config = PLATFORMS[platform]
    path = parsed.path

    # Check exclusion patterns
    for pattern in config['exclude_patterns']:
        if re.search(pattern, path, re.IGNORECASE):
            return None

    # Check if path matches a profile pattern
    is_profile = False
    for pattern in config['profile_patterns']:
        if re.search(pattern, path, re.IGNORECASE):
            is_profile = True
            break

    if not is_profile:
        # If no profile pattern matched, still accept if it's a single-segment path
        # (e.g., /pagename) — covers edge cases not in our patterns
        stripped = path.strip('/')
        if stripped and '/' not in stripped and not stripped.startswith(('.', '_')):
            is_profile = True

    if not is_profile:
        return None

    # Reject bare root paths (no actual handle)
    if path.strip('/') == '':
        return None

    normalized = normalize_social_url(url)
    handle = _extract_handle(path, platform)

    return (platform, normalized, handle)


# =============================================================================
# PROFILE TYPE CLASSIFICATION
# =============================================================================

REGIONAL_SUFFIXES = [
    '_fr', '_de', '_es', '_it', '_pt', '_nl', '_be', '_ch', '_at', '_se',
    '_dk', '_no', '_fi', '_pl', '_cz', '_ro', '_hu', '_gr', '_tr',
    '_uk', '_ie', '_us', '_ca', '_mx', '_br', '_ar', '_cl', '_co', '_pe',
    '_au', '_nz', '_in', '_jp', '_kr', '_cn', '_tw', '_hk', '_sg',
    '_th', '_my', '_ph', '_id', '_vn', '_za', '_ng', '_ke', '_eg',
    '_ae', '_sa', '_il', '_ru', '_ua',
    'france', 'deutschland', 'espana', 'italia', 'brasil', 'mexico',
    'canada', 'australia', 'japan', 'korea', 'india', 'china',
    'uk', 'us', 'eu', 'asia', 'latam', 'apac', 'emea', 'mena',
]

CATEGORY_KEYWORDS = [
    'careers', 'jobs', 'hiring', 'recruiting', 'talent',
    'engineering', 'dev', 'developers', 'tech', 'design',
    'support', 'help', 'helpdesk', 'service',
    'news', 'press', 'media', 'pr', 'blog',
    'sales', 'marketing', 'partners', 'partner',
    'community', 'events', 'education', 'learn', 'academy',
    'security', 'status', 'legal',
    'sports', 'gaming', 'music', 'entertainment',
]


def _slugify(text: str) -> str:
    """Simple slug: lowercase, alphanumeric + underscores."""
    return re.sub(r'[^a-z0-9]', '', text.lower())


def classify_profile_type(handle: str, company_name: str) -> str:
    """
    Classify a profile as main, regional, or category.

    Args:
        handle: The extracted profile handle (e.g., 'hootsuite_fr')
        company_name: The company name for comparison

    Returns: 'main', 'regional', or 'category'
    """
    if not handle:
        return 'main'

    handle_lower = handle.lower()
    company_slug = _slugify(company_name) if company_name else ''

    # Check regional
    for suffix in REGIONAL_SUFFIXES:
        if handle_lower.endswith(suffix):
            return 'regional'
        # Also check with underscore: hootsuitefr -> regional
        if handle_lower.endswith(suffix.lstrip('_')):
            # But only if the base part matches company
            base = handle_lower[:-(len(suffix.lstrip('_')))]
            if base and company_slug and (base in company_slug or company_slug in base):
                return 'regional'

    # Check category
    for keyword in CATEGORY_KEYWORDS:
        if keyword in handle_lower:
            # Make sure it's not just the company name containing the keyword
            if company_slug and keyword in company_slug:
                continue
            return 'category'

    return 'main'
