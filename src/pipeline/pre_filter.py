"""
Pre-filter for fast rejection of irrelevant messages before LLM calls.
"""
import re
from typing import Set, List
from ..core.models import Message


class PreFilter:
    """
    Fast pre-filtering to reject obviously irrelevant messages.
    Reduces LLM costs by filtering out ~80% of irrelevant messages using heuristics.
    """

    # Common spam/marketing keywords
    SPAM_KEYWORDS: Set[str] = {
        "unsubscribe", "newsletter", "marketing", "promotion",
        "discount", "sale", "offer", "click here", "buy now",
    }

    # LoA and financial services keywords
    RELEVANT_KEYWORDS: Set[str] = {
        "loa", "letter of authority", "policy", "plan number",
        "valuation", "pension", "investment", "platform",
        "client", "case", "annual review", "dob", "date of birth",
        "ni number", "national insurance",
    }

    # Known spam domains
    SPAM_DOMAINS: Set[str] = {
        "newsletter.com", "marketing.com", "randomcorp.com",
    }

    # Whitelisted domains (always process)
    WHITELIST_DOMAINS: Set[str] = {
        "firm.com", "example.com", "abcplatform.com",
    }

    def __init__(
        self,
        spam_keywords: Set[str] = None,
        relevant_keywords: Set[str] = None,
        spam_domains: Set[str] = None,
        whitelist_domains: Set[str] = None,
    ):
        """
        Initialize pre-filter with custom keyword lists.

        Args:
            spam_keywords: Keywords indicating spam
            relevant_keywords: Keywords indicating relevance
            spam_domains: Domains to blacklist
            whitelist_domains: Domains to whitelist
        """
        self.spam_keywords = spam_keywords or self.SPAM_KEYWORDS
        self.relevant_keywords = relevant_keywords or self.RELEVANT_KEYWORDS
        self.spam_domains = spam_domains or self.SPAM_DOMAINS
        self.whitelist_domains = whitelist_domains or self.WHITELIST_DOMAINS

    def should_process(self, message: Message) -> bool:
        """
        Determine if message should be processed by LLM.

        Args:
            message: Message to check

        Returns:
            True if message should be processed, False if can be filtered out
        """
        text = message.get_text_content().lower()

        # Check sender domain for emails
        if hasattr(message.content, 'from_address'):
            from_address = message.content.from_address.lower()

            # Whitelist check (always process)
            if any(domain in from_address for domain in self.whitelist_domains):
                return True

            # Blacklist check (skip)
            if any(domain in from_address for domain in self.spam_domains):
                return False

        # Spam keyword check
        spam_score = sum(1 for keyword in self.spam_keywords if keyword in text)
        if spam_score >= 2:
            # Multiple spam keywords, likely irrelevant
            return False

        # Relevant keyword check
        relevant_score = sum(1 for keyword in self.relevant_keywords if keyword in text)
        if relevant_score >= 1:
            # At least one relevant keyword
            return True

        # Default to processing if uncertain (let LLM decide)
        return True

    def get_filter_stats(self, messages: List[Message]) -> dict:
        """
        Get filtering statistics for a batch of messages.

        Args:
            messages: List of messages

        Returns:
            Dictionary with filtering statistics
        """
        total = len(messages)
        to_process = sum(1 for msg in messages if self.should_process(msg))
        filtered = total - to_process

        return {
            "total": total,
            "to_process": to_process,
            "filtered": filtered,
            "filter_rate": (filtered / total * 100) if total > 0 else 0,
        }
