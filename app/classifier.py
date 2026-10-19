"""
Classifier and NLP reasoning engine for support tickets.
Uses TF-IDF + Logistic Regression trained on sample dataset with uncertainty thresholding.
"""

import os
import json
import re
from typing import Tuple, Dict, Any, Optional
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
import numpy as np

# Team routing map by category
TEAM_ROUTING = {
    "Billing": "Finance & Billing Ops Team",
    "Technical": "Tier-2 Technical Support & Engineering",
    "Access": "Identity & Access Management (IAM) Team",
    "General": "Customer Success & Information Desk"
}

# Priority policy keyword mappings
CRITICAL_KEYWORDS = ["outage", "completely down", "production outage", "503", "500 internal server error", "crash production", "blocking checkout"]
HIGH_KEYWORDS = ["double charged", "suspended", "payment failed", "unauthorized", "locked out", "urgent reset", "403", "security admin", "ssl handshake"]
MEDIUM_KEYWORDS = ["tax receipt", "vat invoice", "refund", "downgrade", "csv feature crashes", "sso", "saml", "forgot password", "reset link", "query results"]
LOW_KEYWORDS = ["dark mode", "css glitch", "contractor", "gdpr", "retention", "discounts", "demo", "roadmap", "feedback", "typo", "partnering", "feature requests"]

# Response templates per category
RESPONSE_TEMPLATES = {
    "Billing": (
        "Hello,\n\nThank you for contacting Cerevyn Billing Support. We have received your query regarding your billing "
        "or subscription status. Our finance team is reviewing your transaction records and invoice history. "
        "If this involves an unauthorized charge or payment failure, rest assured we will expedite resolution within 2-4 business hours.\n\n"
        "Best regards,\nCerevyn Finance Team"
    ),
    "Technical": (
        "Hello,\n\nThank you for reaching out to Cerevyn Technical Support. We have logged this technical issue and "
        "routed it directly to our engineering on-call team. If you are experiencing service degradation or error codes, "
        "our engineers are currently inspecting telemetry and system health logs to restore full functionality.\n\n"
        "Best regards,\nCerevyn Engineering Support"
    ),
    "Access": (
        "Hello,\n\nThank you for contacting Cerevyn Security & Identity Support. We understand you are having difficulties "
        "with account access, credentials, or permissions. To protect your workspace, our IAM specialists are verifying your identity "
        "and will dispatch a secure reset token or adjust role permissions promptly.\n\n"
        "Best regards,\nCerevyn IAM Team"
    ),
    "General": (
        "Hello,\n\nThank you for contacting Cerevyn Customer Success. We appreciate your interest and inquiry. "
        "A representative from our customer relations desk will follow up with detailed documentation and assistance shortly.\n\n"
        "Best regards,\nCerevyn Customer Success"
    )
}

class TicketClassifierEngine:
    def __init__(self, confidence_threshold: Optional[float] = None, ambiguity_margin: Optional[float] = None):
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None
            else float(os.environ.get("MODEL_CONFIDENCE_THRESHOLD", 0.45))
        )
        self.ambiguity_margin = (
            ambiguity_margin if ambiguity_margin is not None
            else float(os.environ.get("AMBIGUITY_MARGIN_THRESHOLD", 0.25))
        )
        self.pipeline: Pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(ngram_range=(1, 2), stop_words='english', min_df=1)),
            ('clf', LogisticRegression(C=5.0, solver='lbfgs', random_state=42))
        ])
        self.is_trained = False
        self._train_default_dataset()

    def _train_default_dataset(self):
        data_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "tickets.json")
        if os.path.exists(data_path):
            with open(data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            train_items = data.get("train_tickets", [])
            if train_items:
                texts = [item["message"] for item in train_items]
                labels = [item["category"] for item in train_items]
                self.pipeline.fit(texts, labels)
                self.is_trained = True

    def classify_and_reason(self, message: str) -> Dict[str, Any]:
        """
        Classifies ticket message, evaluates confidence, determines priority policy,
        generates summary and draft response.
        """
        # 1. Clean message
        clean_text = message.strip()
        words = clean_text.split()
        
        # Guard: Extremely short or vague messages
        if len(words) < 3:
            return {
                "category": "General",
                "confidence": 0.25,
                "priority": "Medium",
                "priority_reason": "Low word count / ambiguous input requires human triage",
                "assigned_team": TEAM_ROUTING["General"],
                "summary": clean_text[:120],
                "draft_response": RESPONSE_TEMPLATES["General"],
                "needs_review": True,
                "review_reason": "Input text is too short or ambiguous for confident automatic routing"
            }

        # 2. Predict category & probabilities
        probs = self.pipeline.predict_proba([clean_text])[0]
        classes = self.pipeline.classes_
        best_idx = int(np.argmax(probs))
        predicted_category = str(classes[best_idx])
        top_confidence = float(probs[best_idx])

        # Check for ambiguity: if top two probabilities are close (diff < 0.25)
        sorted_probs = np.sort(probs)
        margin = float(sorted_probs[-1] - sorted_probs[-2]) if len(sorted_probs) > 1 else 1.0

        needs_review = False
        review_reasons = []

        if top_confidence < self.confidence_threshold:
            needs_review = True
            review_reasons.append(f"Model confidence ({top_confidence:.2f}) below threshold ({self.confidence_threshold:.2f})")
        
        if margin < self.ambiguity_margin:
            needs_review = True
            review_reasons.append(f"Prediction ambiguity detected: margin between top categories is only {margin:.2f}")

        # 3. Determine Priority according to state priority policy
        priority, priority_reason = self._determine_priority(clean_text, predicted_category)

        # 4. Generate brief summary
        summary = self._generate_summary(clean_text)

        # 5. Draft response
        draft = RESPONSE_TEMPLATES.get(predicted_category, RESPONSE_TEMPLATES["General"])

        return {
            "category": predicted_category,
            "confidence": round(top_confidence, 3),
            "priority": priority,
            "priority_reason": priority_reason,
            "assigned_team": TEAM_ROUTING.get(predicted_category, "Support Triage Team"),
            "summary": summary,
            "draft_response": draft,
            "needs_review": needs_review,
            "review_reason": "; ".join(review_reasons) if review_reasons else None
        }

    def _determine_priority(self, text: str, category: str) -> Tuple[str, str]:
        lower_text = text.lower()

        # Priority Policy Rules:
        # Rule 1: Production outage, gateway crash, 503, severe service unavailability -> Critical
        for kw in CRITICAL_KEYWORDS:
            if kw in lower_text:
                return "Critical", f"Triggered Critical priority keyword match: '{kw}'"

        # Rule 2: Double billing, unauthorized transaction, locked out admin -> High
        for kw in HIGH_KEYWORDS:
            if kw in lower_text:
                return "High", f"Triggered High priority keyword match: '{kw}'"

        # Rule 3: Technical or Billing issues without critical keywords -> Medium by default
        for kw in MEDIUM_KEYWORDS:
            if kw in lower_text:
                return "Medium", f"Triggered Medium priority keyword match: '{kw}'"

        # Rule 4: General inquiries, cosmetic UI, compliance questions -> Low
        for kw in LOW_KEYWORDS:
            if kw in lower_text:
                return "Low", f"Triggered Low priority keyword match: '{kw}'"

        # Category fallbacks
        if category == "Technical":
            return "Medium", "Technical category standard operational priority"
        elif category == "Billing":
            return "Medium", "Billing inquiry standard operational priority"
        elif category == "Access":
            return "Medium", "Identity & access standard operational priority"
        else:
            return "Low", "General inquiry default priority"

    def _generate_summary(self, text: str) -> str:
        # Create concise 1-sentence synopsis
        clean = re.sub(r'\s+', ' ', text).strip()
        if len(clean) <= 100:
            return clean
        first_period = clean.find('.')
        if 20 < first_period <= 120:
            return clean[:first_period+1]
        return clean[:97] + "..."

    def evaluate_test_set(self) -> Dict[str, Any]:
        """Evaluates model performance against the reserved 10 test tickets."""
        data_path = os.path.join(os.path.dirname(__file__), "..", "sample_data", "tickets.json")
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        test_items = data.get("test_tickets", [])
        
        correct = 0
        total = len(test_items)
        breakdown = {}

        for item in test_items:
            expected = item["expected_category"]
            prediction = self.classify_and_reason(item["message"])
            pred_cat = prediction["category"]
            is_match = (pred_cat == expected)
            if is_match:
                correct += 1
            if expected not in breakdown:
                breakdown[expected] = {"total": 0, "correct": 0}
            breakdown[expected]["total"] += 1
            if is_match:
                breakdown[expected]["correct"] += 1

        accuracy = (correct / total * 100.0) if total > 0 else 0.0
        return {
            "total_test_samples": total,
            "correct_predictions": correct,
            "accuracy_percentage": round(accuracy, 2),
            "category_breakdown": breakdown
        }


# Singleton engine instance
classifier_engine = TicketClassifierEngine()
