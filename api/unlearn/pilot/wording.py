"""Every fixed sentence a pilot student can see. No model writes text for students: the pilot shows only these
strings, the approved questions, and the names of the constructs being practised.

This file is reviewed as one block in docs/pilot/ITEM_REVIEW.md (fingerprinted there). Change it and the block
goes back to PENDING until it is approved again. The Hindi strings are drafts and need a native speaker's check.
"""

# Shown on the assent screen in both languages, English first.
ASSENT = {
    "en": {
        "title": "Before we start",
        "body": [
            "This is a short maths activity about fractions. It takes about 20 minutes.",
            "It is not a test, and it does not count for marks.",
            "We save only your code and your answers, not your name.",
            "You can stop at any time. Just close the page.",
        ],
        "yes": "Yes, I'm happy to do this",
        "no": "I don't want to do this",
        "declined": "That's fine. You don't have to do this. You can close this page.",
    },
    "hi": {
        "title": "शुरू करने से पहले",
        "body": [
            "यह भिन्नों (fractions) के बारे में गणित की एक छोटी गतिविधि है। इसमें लगभग 20 मिनट लगेंगे।",
            "यह परीक्षा नहीं है, और इसके कोई अंक नहीं मिलेंगे।",
            "हम सिर्फ़ आपका कोड और आपके उत्तर सहेजते हैं, आपका नाम नहीं।",
            "आप कभी भी रुक सकते हैं। बस पेज बंद कर दें।",
        ],
        "yes": "हाँ, मैं तैयार हूँ",
        "no": "नहीं, मुझे यह नहीं करना है",
        "declined": "कोई बात नहीं। आपको यह करना ज़रूरी नहीं है। आप यह पेज बंद कर सकते हैं।",
    },
}

TEXT = {
    "title": "Fractions practice",
    "enter_code": "Type the code from your slip",
    "start": "Start",
    "bad_code": "That code didn't work. Check it with your teacher.",
    "too_many": "Too many tries. Wait a minute, then try again.",
    "warming": "Getting ready. Please wait a minute and try again.",
    "ready": "Ready",
    "not_open": "This activity is not open yet. Please ask your teacher.",
    "check_intro": "Answer each question.",
    "rule": "Give answers in simplest form, unless the question asks for an equivalent fraction.",
    "more_intro": "Thank you! Now a few more questions to find what to practise.",
    "progress": "Question {i} of {n}",
    "practise_title": "Let's practise: {construct}",
    "practise_teacher": "Your teacher will go through this with you.",
    "practise_try": "Now try this one:",
    "save_failed": "Your answer didn't save. Please tap Try again.",
    "error": "Something went wrong. Please tap Try again.",
    "try_again": "Try again",
    "done_all_right": "Great work, you got them all right. That's all for today. Thank you!",
    "done_s1": "That's all for today. Thank you!",
    "wait_s2": "You have finished session 1. Your teacher will tell you when session 2 starts.",
    "recall": "Last time we practised: {construct}.",
    "recall_none": "Last time you didn't need extra practice.",
    "done_s2": "That's all. Thank you for taking part!",
    "finished": "You have finished both sessions. Thank you!",
}


def bundle() -> dict:
    """What the student page loads: every string it may show."""
    return {"assent": ASSENT, "text": TEXT}
