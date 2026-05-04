"""Scene definitions for the CritMatch automated video demo.

Each scene has:
  - id: short identifier (used for file names)
  - url: page to navigate to
  - narration: text spoken by edge-tts (~150 wpm)
  - actions: list of Playwright actions to perform AFTER navigation
            and AFTER initial wait, before the scene ends.
  - duration: minimum seconds the scene must run (waits if narration is shorter)
"""

SCENES = [
    {
        "id": "01_intro",
        "url": "/",
        "duration": 12.0,
        "narration": (
            "CritMatch is a HIPAA-aligned platform that turns clinical trial eligibility "
            "criteria into structured cohorts, and matches them against your patient population. "
            "Let me show you how it works."
        ),
        "actions": [],
    },
    {
        "id": "02_demo_open",
        "url": "/demo",
        "duration": 10.0,
        "narration": (
            "This is the public demo. No sign-in required. The matching engine runs entirely "
            "in your browser against eight bundled sample patients."
        ),
        "actions": [
            {"kind": "wait", "selector": "h2", "timeout": 5000},
        ],
    },
    {
        "id": "03_preset",
        "url": None,
        "duration": 10.0,
        "narration": (
            "Pick a trial preset. We'll start with Heart Failure plus Type 2 Diabetes \u2014 "
            "a common cardio-metabolic study population. The criteria panel auto-populates."
        ),
        "actions": [
            {"kind": "click_text", "text": "Heart Failure"},
            {"kind": "wait_ms", "ms": 1500},
        ],
    },
    {
        "id": "04_run_match",
        "url": None,
        "duration": 14.0,
        "narration": (
            "Click Run Match. The engine evaluates every patient against inclusion and "
            "exclusion criteria, then ranks them by confidence: high, moderate, low, or excluded. "
            "Results appear instantly."
        ),
        "actions": [
            {"kind": "click_text", "text": "Run Match"},
            {"kind": "wait_ms", "ms": 1500},
            {"kind": "scroll_to_text", "text": "Match Results"},
        ],
    },
    {
        "id": "05_results",
        "url": None,
        "duration": 14.0,
        "narration": (
            "Each candidate card shows matched criteria, exclusion flags, and any missing data. "
            "This transparency is critical \u2014 coordinators see exactly why the engine made "
            "each call, so they can verify against the chart."
        ),
        "actions": [
            {"kind": "click_text", "text": "Candidates only"},
            {"kind": "wait_ms", "ms": 1500},
            {"kind": "scroll_by", "y": 300},
            {"kind": "wait_ms", "ms": 2500},
            {"kind": "scroll_by", "y": 300},
        ],
    },
    {
        "id": "06_oncology",
        "url": None,
        "duration": 10.0,
        "narration": (
            "Switch to a different therapeutic area \u2014 the Oncology preset for HER2-positive "
            "breast cancer. Different criteria, same engine, instant re-ranking."
        ),
        "actions": [
            {"kind": "scroll_to_top"},
            {"kind": "click_text", "text": "Oncology"},
            {"kind": "wait_ms", "ms": 1200},
            {"kind": "click_text", "text": "Run Match"},
            {"kind": "wait_ms", "ms": 1500},
        ],
    },
    {
        "id": "07_outro",
        "url": "/",
        "duration": 12.0,
        "narration": (
            "Behind the demo, the full CritMatch platform adds SMART-on-FHIR EHR integration, "
            "multi-site collaboration, audit trails, and notifications. "
            "Visit the live demo to try it yourself, or contact us for a pilot."
        ),
        "actions": [],
    },
]
